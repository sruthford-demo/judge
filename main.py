"""FastAPI app for Judge: a Cards-Against-Humanity-style party game judged by Claude.

Run with: python main.py

(Not `uvicorn main:app` directly -- lib/sdk_parser resolves its log directory
relative to the running __main__ script, so the app needs to be launched as a
script for logs/ to land in this project directory instead of wherever
uvicorn's own entry point lives.)
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from game.schemas import (
    GameOverOut,
    GameStateOut,
    HandOut,
    RoundResultOut,
    StartGameIn,
    SubmitCardIn,
)
from game.state import GameError, manager

app = FastAPI(title="Judge")

STATIC_DIR = Path(__file__).parent / "static"


@app.exception_handler(GameError)
async def game_error_handler(request, exc: GameError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.post("/api/game", response_model=GameStateOut)
async def start_game(body: StartGameIn) -> GameStateOut:
    return await manager.start_game(body.player_names)


@app.get("/api/game", response_model=GameStateOut | GameOverOut)
async def get_game() -> GameStateOut | GameOverOut:
    return manager.get_state()


@app.get("/api/game/players/{player_id}/hand", response_model=HandOut)
async def get_hand(player_id: str) -> HandOut:
    return manager.get_hand(player_id)


@app.post("/api/game/players/{player_id}/submit", response_model=GameStateOut)
async def submit_card(player_id: str, body: SubmitCardIn) -> GameStateOut:
    return await manager.submit_card(player_id, body.card_id)


@app.post("/api/game/judge", response_model=RoundResultOut)
async def judge_round() -> RoundResultOut:
    return await manager.judge_round()


@app.post("/api/game/next-round", response_model=GameStateOut | GameOverOut)
async def next_round() -> GameStateOut | GameOverOut:
    return await manager.next_round()


@app.post("/api/game/reset")
async def reset_game() -> dict:
    await manager.reset()
    return {}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
