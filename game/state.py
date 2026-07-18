"""In-memory multi-room state and round lifecycle for Judge.

Rooms live in a process-wide dict keyed by room code -- no external store.
This is a known, accepted tradeoff on Vercel's stateless serverless functions:
state can occasionally reset under real concurrent multi-device load (a cold
start, or requests landing on a different warm instance). Running
`python main.py` locally (one process) is far more reliable for an actual
in-person game than the Vercel deployment.

Every mutating RoomManager method takes the room's own asyncio.Lock so a
double-tapped button can't corrupt that room's state; separate rooms don't
block each other.
"""

import asyncio
import random
import secrets
import string
from dataclasses import dataclass, field
from typing import Literal

from .cards import RESPONSE_BY_ID, RESPONSE_CARDS
from .schemas import (
    CardOut,
    GameOverOut,
    PlayerPublic,
    RoomStateOut,
    RoundResultOut,
    SubmissionOut,
)

MIN_PLAYERS = 4
TARGET_SCORE = 5
ROOM_CODE_CHARS = string.ascii_uppercase
ROOM_CODE_LENGTH = 4


class GameError(Exception):
    status_code = 400


class RoomNotFoundError(GameError):
    status_code = 404


class UnknownPlayerError(GameError):
    status_code = 404


class InvalidTokenError(GameError):
    status_code = 403


class InvalidPhaseError(GameError):
    status_code = 409


class NotHostError(GameError):
    status_code = 403


class NotJudgeError(GameError):
    status_code = 403


class DuplicateNameError(GameError):
    status_code = 400


class NotEnoughPlayersError(GameError):
    status_code = 400


@dataclass
class Player:
    id: str
    name: str
    token: str
    score: int = 0
    ready: bool = False
    card_id: str | None = None


@dataclass
class Room:
    code: str
    host_player_id: str
    players: list[Player] = field(default_factory=list)
    phase: Literal["lobby", "round", "reveal", "game_over"] = "lobby"
    round_number: int = 0
    judge_player_id: str | None = None
    response_deck: list[str] = field(default_factory=list)
    response_discard: list[str] = field(default_factory=list)
    last_round_result: RoundResultOut | None = None
    target_score: int = TARGET_SCORE
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class RoomManager:
    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}

    # -- room lifecycle -------------------------------------------------------

    async def create_room(self, host_name: str) -> tuple[Room, Player]:
        name = host_name.strip()
        if not name:
            raise GameError("Host name is required.")
        code = self._new_room_code()
        host = Player(id=_new_id(), name=name, token=_new_token())
        room = Room(code=code, host_player_id=host.id, players=[host])
        self._rooms[code] = room
        return room, host

    async def join_room(self, code: str, name: str) -> tuple[Room, Player]:
        room = self._get_room(code)
        async with room.lock:
            if room.phase != "lobby":
                raise InvalidPhaseError("This game has already started.")
            name = name.strip()
            if not name:
                raise GameError("Name is required.")
            if any(p.name.lower() == name.lower() for p in room.players):
                raise DuplicateNameError("That name is already taken in this room.")
            player = Player(id=_new_id(), name=name, token=_new_token())
            room.players.append(player)
            return room, player

    async def start_game(self, code: str, player_id: str, token: str) -> RoomStateOut:
        room = self._get_room(code)
        async with room.lock:
            self._authorize(room, player_id, token)
            if player_id != room.host_player_id:
                raise NotHostError("Only the host can start the game.")
            if room.phase != "lobby":
                raise InvalidPhaseError("The game has already started.")
            if len(room.players) < MIN_PLAYERS:
                raise NotEnoughPlayersError(f"Need at least {MIN_PLAYERS} players to start.")

            room.response_deck = [c.id for c in RESPONSE_CARDS]
            random.shuffle(room.response_deck)
            self._begin_round(room, 1)
            return self._state_out(room, player_id)

    def get_state(self, code: str, player_id: str, token: str) -> RoomStateOut | GameOverOut:
        room = self._get_room(code)
        self._authorize(room, player_id, token)
        if room.phase == "game_over":
            return self._game_over_out(room)
        return self._state_out(room, player_id)

    async def set_ready(self, code: str, player_id: str, token: str) -> RoomStateOut:
        room = self._get_room(code)
        async with room.lock:
            self._authorize(room, player_id, token)
            if room.phase != "round":
                raise InvalidPhaseError("There's no active round to ready up for.")
            if player_id == room.judge_player_id:
                raise NotJudgeError("The judge doesn't hold up a card.")
            player = self._find_player(room, player_id)
            player.ready = True
            return self._state_out(room, player_id)

    async def judge_pick(
        self, code: str, judge_player_id: str, token: str, loser_player_id: str
    ) -> RoomStateOut:
        room = self._get_room(code)
        async with room.lock:
            self._authorize(room, judge_player_id, token)
            if room.phase != "round":
                raise InvalidPhaseError("There's no active round to judge.")
            if judge_player_id != room.judge_player_id:
                raise NotJudgeError("Only the current judge can pick the worst card.")

            non_judges = [p for p in room.players if p.id != room.judge_player_id]
            if not all(p.ready for p in non_judges):
                raise InvalidPhaseError("Not everyone has revealed their card yet.")

            loser = self._find_player(room, loser_player_id)
            if loser.id == room.judge_player_id:
                raise GameError("The judge can't pick themself.")
            loser.score += 1

            judge = self._find_player(room, judge_player_id)
            submissions_out = [
                SubmissionOut(player_id=p.id, name=p.name, card=self._card_out(p.card_id))
                for p in non_judges
            ]
            loser_out = next(s for s in submissions_out if s.player_id == loser.id)

            room.last_round_result = RoundResultOut(
                round_number=room.round_number,
                judge_name=judge.name,
                loser=loser_out,
                submissions=submissions_out,
                scores=[self._player_public(room, p) for p in room.players],
            )
            room.response_discard.extend(p.card_id for p in non_judges if p.card_id)
            room.phase = "reveal"
            return self._state_out(room, judge_player_id)

    async def next_round(
        self, code: str, player_id: str, token: str
    ) -> RoomStateOut | GameOverOut:
        room = self._get_room(code)
        async with room.lock:
            self._authorize(room, player_id, token)
            if room.phase != "reveal":
                raise InvalidPhaseError("The current round hasn't been judged yet.")

            if any(p.score >= room.target_score for p in room.players):
                room.phase = "game_over"
                return self._game_over_out(room)

            self._begin_round(room, room.round_number + 1)
            return self._state_out(room, player_id)

    async def new_game(self, code: str, player_id: str, token: str) -> RoomStateOut:
        room = self._get_room(code)
        async with room.lock:
            self._authorize(room, player_id, token)
            if player_id != room.host_player_id:
                raise NotHostError("Only the host can start a new game.")
            for p in room.players:
                p.score = 0
                p.ready = False
                p.card_id = None
            room.last_round_result = None
            room.response_discard = []
            self._begin_round(room, 1)
            return self._state_out(room, player_id)

    # -- internal helpers -------------------------------------------------------

    def _new_room_code(self) -> str:
        while True:
            code = "".join(secrets.choice(ROOM_CODE_CHARS) for _ in range(ROOM_CODE_LENGTH))
            if code not in self._rooms:
                return code

    def _get_room(self, code: str) -> Room:
        room = self._rooms.get(code.upper())
        if room is None:
            raise RoomNotFoundError(f"No room with code {code!r}.")
        return room

    def _authorize(self, room: Room, player_id: str, token: str) -> Player:
        player = self._find_player(room, player_id)
        if not secrets.compare_digest(player.token, token or ""):
            raise InvalidTokenError("Invalid player token.")
        return player

    def _find_player(self, room: Room, player_id: str) -> Player:
        for player in room.players:
            if player.id == player_id:
                return player
        raise UnknownPlayerError(f"Unknown player_id {player_id!r}")

    def _begin_round(self, room: Room, number: int) -> None:
        room.round_number = number
        judge_index = (number - 1) % len(room.players)
        room.judge_player_id = room.players[judge_index].id
        room.phase = "round"
        for player in room.players:
            player.ready = False
            player.card_id = (
                None if player.id == room.judge_player_id else self._draw_response_card(room)
            )

    def _draw_response_card(self, room: Room) -> str:
        if not room.response_deck:
            room.response_deck, room.response_discard = room.response_discard, []
            random.shuffle(room.response_deck)
        return room.response_deck.pop()

    def _card_out(self, card_id: str | None) -> CardOut | None:
        if card_id is None:
            return None
        c = RESPONSE_BY_ID[card_id]
        return CardOut(
            id=c.id, text=c.text, emoji=c.emoji, image_url=f"/card-images/{c.id}.webp"
        )

    def _player_public(self, room: Room, player: Player) -> PlayerPublic:
        return PlayerPublic(
            id=player.id,
            name=player.name,
            score=player.score,
            is_judge=player.id == room.judge_player_id,
            ready=player.ready,
        )

    def _state_out(self, room: Room, requesting_player_id: str) -> RoomStateOut:
        requester = self._find_player(room, requesting_player_id)
        non_judges = [p for p in room.players if p.id != room.judge_player_id]
        ready_count = sum(1 for p in non_judges if p.ready)
        am_i_judge = requesting_player_id == room.judge_player_id

        reveal_cards = None
        if am_i_judge and room.phase == "round" and non_judges and ready_count == len(non_judges):
            reveal_cards = [
                SubmissionOut(player_id=p.id, name=p.name, card=self._card_out(p.card_id))
                for p in non_judges
            ]

        return RoomStateOut(
            room_code=room.code,
            phase=room.phase,
            host_player_id=room.host_player_id,
            round_number=room.round_number,
            judge_player_id=room.judge_player_id,
            am_i_judge=am_i_judge,
            my_card=self._card_out(requester.card_id) if room.phase == "round" else None,
            my_ready=requester.ready,
            ready_count=ready_count,
            players_to_ready=len(non_judges),
            players=[self._player_public(room, p) for p in room.players],
            reveal_cards=reveal_cards,
            last_round_result=room.last_round_result,
        )

    def _game_over_out(self, room: Room) -> GameOverOut:
        ranked = sorted(
            (self._player_public(room, p) for p in room.players),
            key=lambda p: p.score,
            reverse=True,
        )
        return GameOverOut(
            room_code=room.code,
            host_player_id=room.host_player_id,
            winner=ranked[0],
            final_scores=ranked,
        )


def _new_id() -> str:
    return secrets.token_hex(8)


def _new_token() -> str:
    return secrets.token_urlsafe(24)


manager = RoomManager()
