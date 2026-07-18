"""Pydantic request/response models for the Judge API."""

from typing import Literal

from pydantic import BaseModel


class CardOut(BaseModel):
    id: str
    text: str
    emoji: str
    image_url: str


class PlayerPublic(BaseModel):
    id: str
    name: str
    score: int
    is_judge: bool
    ready: bool


class SubmissionOut(BaseModel):
    player_id: str
    name: str
    card: CardOut


class RoundResultOut(BaseModel):
    round_number: int
    judge_name: str
    loser: SubmissionOut
    submissions: list[SubmissionOut]
    scores: list[PlayerPublic]


class RoomStateOut(BaseModel):
    room_code: str
    phase: Literal["lobby", "round", "reveal"]
    host_player_id: str
    round_number: int
    judge_player_id: str | None
    am_i_judge: bool
    my_card: CardOut | None
    my_ready: bool
    ready_count: int
    players_to_ready: int
    players: list[PlayerPublic]
    reveal_cards: list[SubmissionOut] | None = None
    last_round_result: RoundResultOut | None = None


class GameOverOut(BaseModel):
    phase: Literal["game_over"] = "game_over"
    room_code: str
    host_player_id: str
    winner: PlayerPublic
    final_scores: list[PlayerPublic]


class CreateRoomIn(BaseModel):
    host_name: str


class JoinRoomIn(BaseModel):
    name: str


class JudgePickIn(BaseModel):
    loser_player_id: str


class RoomJoinedOut(BaseModel):
    room_code: str
    player_id: str
    player_token: str
