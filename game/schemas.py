"""Pydantic request/response models for the Judge API."""

from typing import Literal

from pydantic import BaseModel


class CardOut(BaseModel):
    id: str
    text: str
    emoji: str


class PlayerPublic(BaseModel):
    id: str
    name: str
    score: int
    hand_size: int
    has_submitted: bool


class SubmissionOut(BaseModel):
    player_id: str
    name: str
    card: CardOut


class RoundResultOut(BaseModel):
    round_number: int
    prompt: CardOut
    winner: SubmissionOut
    roast: str
    submissions: list[SubmissionOut]
    scores: list[PlayerPublic]
    judge_error: str | None = None


class GameStateOut(BaseModel):
    game_id: str
    phase: Literal["submitting", "judging", "reveal"]
    round_number: int
    prompt: CardOut
    players: list[PlayerPublic]
    current_player_id: str | None
    last_round_result: RoundResultOut | None = None


class GameOverOut(BaseModel):
    phase: Literal["game_over"] = "game_over"
    winner: PlayerPublic
    final_scores: list[PlayerPublic]


class HandOut(BaseModel):
    player_id: str
    name: str
    hand: list[CardOut]
    has_submitted: bool


class StartGameIn(BaseModel):
    player_names: list[str]


class SubmitCardIn(BaseModel):
    card_id: str
