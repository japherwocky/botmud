from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from mud.config import CORS_ORIGINS, HOST, PORT
from mud.game_loop import async_game_loop
from mud.net.connection import handle_connection_with_stream
from mud.server_bootstrap import bootstrap_server

from .websocket_stream import WebSocketStream

_game_task = None


async def startup() -> None:
    global _game_task
    bootstrap_server("area/area.lst")
    # Start game loop as background task
    _game_task = asyncio.create_task(async_game_loop())
    print("🎮 Game loop started for WebSocket server")


async def shutdown() -> None:
    global _game_task
    if _game_task:
        _game_task.cancel()
        try:
            await _game_task
        except asyncio.CancelledError:
            print("Game loop stopped")
            pass


@asynccontextmanager
async def lifespan(_: FastAPI):
    await startup()
    try:
        yield
    finally:
        await shutdown()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    stream = WebSocketStream(websocket)
    await handle_connection_with_stream(
        stream,
        host_for_ban=stream.peer_host,
        connection_type="WebSocket",
    )


def run(host: str = HOST, port: int = PORT) -> None:
    uvicorn.run("mud.network.websocket_server:app", host=host, port=port)


if __name__ == "__main__":
    run()
