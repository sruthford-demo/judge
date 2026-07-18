"""Shared room storage.

On Vercel, each request may hit a different serverless instance, so an
in-process dict can't reliably hold room state (that was the cause of
"room no longer available" errors under real multi-device play). When
Upstash Redis credentials are present in the environment, rooms are stored
there instead -- a plain HTTP REST API, no persistent connection needed,
which fits serverless well. Locally, with no credentials set, everything
falls back to a plain in-memory dict, so `python main.py` still needs zero
setup.
"""

import json
import os
import time
from typing import Protocol

import httpx

ROOM_TTL_SECONDS = 12 * 60 * 60  # abandoned rooms expire instead of piling up


class RoomStore(Protocol):
    async def get(self, code: str) -> dict | None: ...
    async def set(self, code: str, data: dict) -> None: ...


class InMemoryRoomStore:
    def __init__(self) -> None:
        self._data: dict[str, tuple[dict, float]] = {}

    async def get(self, code: str) -> dict | None:
        entry = self._data.get(code)
        if entry is None:
            return None
        data, expires_at = entry
        if time.monotonic() > expires_at:
            del self._data[code]
            return None
        return data

    async def set(self, code: str, data: dict) -> None:
        self._data[code] = (data, time.monotonic() + ROOM_TTL_SECONDS)


class RedisRoomStore:
    def __init__(self, base_url: str, token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )

    async def get(self, code: str) -> dict | None:
        resp = await self._client.post("/", json=["GET", _key(code)])
        resp.raise_for_status()
        result = resp.json().get("result")
        return json.loads(result) if result else None

    async def set(self, code: str, data: dict) -> None:
        resp = await self._client.post(
            "/", json=["SET", _key(code), json.dumps(data), "EX", str(ROOM_TTL_SECONDS)]
        )
        resp.raise_for_status()


def _key(code: str) -> str:
    return f"room:{code}"


def build_default_store() -> RoomStore:
    url = os.environ.get("KV_REST_API_URL")
    token = os.environ.get("KV_REST_API_TOKEN")
    if url and token:
        return RedisRoomStore(url, token)
    return InMemoryRoomStore()
