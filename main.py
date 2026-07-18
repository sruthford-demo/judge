"""FastAPI app for Judge: a multi-device, Heads-Up-style party game.

Run with: python main.py
"""

from pathlib import Path

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from game.schemas import (
    CreateRoomIn,
    GameOverOut,
    JoinRoomIn,
    JudgePickIn,
    RoomJoinedOut,
    RoomStateOut,
)
from game.state import GameError, manager

app = FastAPI(title="Judge")

STATIC_DIR = Path(__file__).parent / "static"


@app.exception_handler(GameError)
async def game_error_handler(request, exc: GameError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.post("/api/rooms", response_model=RoomJoinedOut)
async def create_room(body: CreateRoomIn) -> RoomJoinedOut:
    room, player = await manager.create_room(body.host_name)
    return RoomJoinedOut(room_code=room.code, player_id=player.id, player_token=player.token)


@app.post("/api/rooms/{code}/join", response_model=RoomJoinedOut)
async def join_room(code: str, body: JoinRoomIn) -> RoomJoinedOut:
    room, player = await manager.join_room(code, body.name)
    return RoomJoinedOut(room_code=room.code, player_id=player.id, player_token=player.token)


@app.get("/api/rooms/{code}/state", response_model=RoomStateOut | GameOverOut)
async def get_state(code: str, player_id: str = Header(..., alias="X-Player-Id"), player_token: str = Header(..., alias="X-Player-Token")) -> RoomStateOut | GameOverOut:
    return await manager.get_state(code, player_id, player_token)


@app.post("/api/rooms/{code}/start", response_model=RoomStateOut)
async def start_game(code: str, player_id: str = Header(..., alias="X-Player-Id"), player_token: str = Header(..., alias="X-Player-Token")) -> RoomStateOut:
    return await manager.start_game(code, player_id, player_token)


@app.post("/api/rooms/{code}/judge/pick", response_model=RoomStateOut)
async def judge_pick(code: str, body: JudgePickIn, player_id: str = Header(..., alias="X-Player-Id"), player_token: str = Header(..., alias="X-Player-Token")) -> RoomStateOut:
    return await manager.judge_pick(code, player_id, player_token, body.loser_player_id)


@app.post("/api/rooms/{code}/next-round", response_model=RoomStateOut | GameOverOut)
async def next_round(code: str, player_id: str = Header(..., alias="X-Player-Id"), player_token: str = Header(..., alias="X-Player-Token")) -> RoomStateOut | GameOverOut:
    return await manager.next_round(code, player_id, player_token)


@app.post("/api/rooms/{code}/new-game", response_model=RoomStateOut)
async def new_game(code: str, player_id: str = Header(..., alias="X-Player-Id"), player_token: str = Header(..., alias="X-Player-Token")) -> RoomStateOut:
    return await manager.new_game(code, player_id, player_token)


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
