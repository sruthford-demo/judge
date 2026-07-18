"""In-memory game state and round lifecycle for a single local Judge game.

One game is active per server process (local pass-and-play, no persistence).
All mutating GameManager methods take an asyncio.Lock so a double-tapped
button can't corrupt state or double-judge a round.
"""

import asyncio
import random
from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

from . import judge
from .cards import PROMPT_BY_ID, PROMPT_CARDS, RESPONSE_BY_ID, RESPONSE_CARDS
from .schemas import (
    CardOut,
    GameOverOut,
    GameStateOut,
    HandOut,
    PlayerPublic,
    RoundResultOut,
    SubmissionOut,
)

HAND_SIZE = 7
TARGET_SCORE = 7
MIN_PLAYERS = 4


class GameError(Exception):
    status_code = 400


class NoActiveGameError(GameError):
    status_code = 404


class UnknownPlayerError(GameError):
    status_code = 404


class InvalidPhaseError(GameError):
    status_code = 409


class NotYourTurnError(GameError):
    status_code = 409


class CardNotInHandError(GameError):
    status_code = 400


@dataclass
class Player:
    id: str
    name: str
    score: int = 0
    hand: list[str] = field(default_factory=list)


@dataclass
class Round:
    number: int
    prompt_id: str
    pending_player_ids: list[str]
    submissions: dict[str, str] = field(default_factory=dict)
    submission_order: list[str] = field(default_factory=list)
    phase: Literal["submitting", "judging", "reveal"] = "submitting"
    winner_player_id: str | None = None
    roast: str | None = None
    judge_error: str | None = None


@dataclass
class Game:
    id: str
    players: list[Player]
    round: Round
    response_deck: list[str] = field(default_factory=list)
    response_discard: list[str] = field(default_factory=list)
    prompt_deck: list[str] = field(default_factory=list)
    prompt_discard: list[str] = field(default_factory=list)
    phase: Literal["in_round", "game_over"] = "in_round"
    target_score: int = TARGET_SCORE
    last_round_result: RoundResultOut | None = None


class GameManager:
    def __init__(self) -> None:
        self._game: Game | None = None
        self._lock = asyncio.Lock()

    # -- public API -------------------------------------------------------

    async def start_game(self, player_names: list[str]) -> GameStateOut:
        async with self._lock:
            names = [n.strip() for n in player_names if n.strip()]
            if len(names) < MIN_PLAYERS:
                raise GameError(f"At least {MIN_PLAYERS} player names are required.")

            response_deck = [c.id for c in RESPONSE_CARDS]
            random.shuffle(response_deck)
            prompt_deck = [c.id for c in PROMPT_CARDS]
            random.shuffle(prompt_deck)

            players = [Player(id=str(uuid4()), name=name) for name in names]
            placeholder_round = Round(
                number=0, prompt_id=PROMPT_CARDS[0].id, pending_player_ids=[]
            )

            self._game = Game(
                id=str(uuid4()),
                players=players,
                round=placeholder_round,
                response_deck=response_deck,
                prompt_deck=prompt_deck,
            )

            for player in players:
                player.hand = self._draw_response_cards(HAND_SIZE)

            self._game.round = self._begin_round(1)
            return self._state_out(self._game)

    def get_state(self) -> GameStateOut | GameOverOut:
        game = self._require_game()
        if game.phase == "game_over":
            return self._game_over_out(game)
        return self._state_out(game)

    def get_hand(self, player_id: str) -> HandOut:
        game = self._require_game()
        player = self._find_player(game, player_id)
        hand = [self._card_out(card_id) for card_id in player.hand]
        return HandOut(
            player_id=player.id,
            name=player.name,
            hand=hand,
            has_submitted=player.id in game.round.submissions,
        )

    async def submit_card(self, player_id: str, card_id: str) -> GameStateOut:
        async with self._lock:
            game = self._require_game()
            round_ = game.round
            if round_.phase != "submitting":
                raise InvalidPhaseError("Submissions are closed for this round.")
            if not round_.pending_player_ids or round_.pending_player_ids[0] != player_id:
                raise NotYourTurnError("It's not this player's turn to submit.")

            player = self._find_player(game, player_id)
            if card_id not in player.hand:
                raise CardNotInHandError("That card is not in this player's hand.")

            player.hand.remove(card_id)
            round_.submissions[player_id] = card_id
            round_.pending_player_ids.pop(0)

            if not round_.pending_player_ids:
                order = [p.id for p in game.players]
                random.shuffle(order)
                round_.submission_order = order
                round_.phase = "judging"

            return self._state_out(game)

    async def judge_round(self) -> RoundResultOut:
        async with self._lock:
            game = self._require_game()
            round_ = game.round
            if round_.phase != "judging":
                raise InvalidPhaseError("This round is not ready to be judged.")

            prompt = PROMPT_BY_ID[round_.prompt_id]
            texts = [
                RESPONSE_BY_ID[round_.submissions[pid]].text for pid in round_.submission_order
            ]

            result = await judge.judge_round(prompt.text, texts)

            winner_player_id = round_.submission_order[result.winner_index]
            winner_player = self._find_player(game, winner_player_id)
            winner_player.score += 1

            round_.winner_player_id = winner_player_id
            round_.roast = result.roast
            round_.judge_error = result.error
            round_.phase = "reveal"

            submissions_out = [
                SubmissionOut(
                    player_id=pid,
                    name=self._find_player(game, pid).name,
                    card=self._card_out(round_.submissions[pid]),
                )
                for pid in round_.submission_order
            ]
            winner_out = next(s for s in submissions_out if s.player_id == winner_player_id)

            result_out = RoundResultOut(
                round_number=round_.number,
                prompt=self._prompt_out(round_.prompt_id),
                winner=winner_out,
                roast=result.roast,
                submissions=submissions_out,
                scores=[self._player_public(p, round_) for p in game.players],
                judge_error=result.error,
            )
            game.last_round_result = result_out
            return result_out

    async def next_round(self) -> GameStateOut | GameOverOut:
        async with self._lock:
            game = self._require_game()
            if game.round.phase != "reveal":
                raise InvalidPhaseError("The current round hasn't been judged yet.")

            if any(p.score >= game.target_score for p in game.players):
                game.phase = "game_over"
                return self._game_over_out(game)

            game.response_discard.extend(game.round.submissions.values())
            for player in game.players:
                refill = self._draw_response_cards(HAND_SIZE - len(player.hand))
                player.hand.extend(refill)

            game.round = self._begin_round(game.round.number + 1)
            return self._state_out(game)

    async def reset(self) -> None:
        async with self._lock:
            self._game = None

    # -- internal helpers ---------------------------------------------------

    def _require_game(self) -> Game:
        if self._game is None:
            raise NoActiveGameError("No active game. Start a new game first.")
        return self._game

    def _find_player(self, game: Game, player_id: str) -> Player:
        for player in game.players:
            if player.id == player_id:
                return player
        raise UnknownPlayerError(f"Unknown player_id {player_id!r}")

    def _begin_round(self, number: int) -> Round:
        prompt_id = self._draw_prompt()
        pending = self._turn_order(number)
        return Round(number=number, prompt_id=prompt_id, pending_player_ids=pending)

    def _turn_order(self, round_number: int) -> list[str]:
        game = self._game
        assert game is not None
        ids = [p.id for p in game.players]
        offset = (round_number - 1) % len(ids)
        return ids[offset:] + ids[:offset]

    def _draw_prompt(self) -> str:
        game = self._game
        assert game is not None
        if not game.prompt_deck:
            game.prompt_deck, game.prompt_discard = game.prompt_discard, []
            random.shuffle(game.prompt_deck)
        prompt_id = game.prompt_deck.pop()
        game.prompt_discard.append(prompt_id)
        return prompt_id

    def _draw_response_cards(self, n: int) -> list[str]:
        game = self._game
        assert game is not None
        drawn: list[str] = []
        for _ in range(n):
            if not game.response_deck:
                if not game.response_discard:
                    break
                game.response_deck, game.response_discard = game.response_discard, []
                random.shuffle(game.response_deck)
            drawn.append(game.response_deck.pop())
        return drawn

    def _card_out(self, card_id: str) -> CardOut:
        c = RESPONSE_BY_ID[card_id]
        return CardOut(id=c.id, text=c.text, emoji=c.emoji)

    def _prompt_out(self, prompt_id: str) -> CardOut:
        c = PROMPT_BY_ID[prompt_id]
        return CardOut(id=c.id, text=c.text, emoji=c.emoji)

    def _player_public(self, player: Player, round_: Round) -> PlayerPublic:
        return PlayerPublic(
            id=player.id,
            name=player.name,
            score=player.score,
            hand_size=len(player.hand),
            has_submitted=player.id in round_.submissions,
        )

    def _state_out(self, game: Game) -> GameStateOut:
        current_player_id = (
            game.round.pending_player_ids[0]
            if game.round.phase == "submitting" and game.round.pending_player_ids
            else None
        )
        return GameStateOut(
            game_id=game.id,
            phase=game.round.phase,
            round_number=game.round.number,
            prompt=self._prompt_out(game.round.prompt_id),
            players=[self._player_public(p, game.round) for p in game.players],
            current_player_id=current_player_id,
            last_round_result=game.last_round_result,
        )

    def _game_over_out(self, game: Game) -> GameOverOut:
        ranked = sorted(
            (self._player_public(p, game.round) for p in game.players),
            key=lambda p: p.score,
            reverse=True,
        )
        return GameOverOut(winner=ranked[0], final_scores=ranked)


manager = GameManager()
