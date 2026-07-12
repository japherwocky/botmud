"""Combined MUD server: WebSocket, Telnet, and SSH in one process.

Uvicorn owns the asyncio event loop. The FastAPI lifespan bootstraps the
world once, starts a single game-loop task, and starts telnet and SSH
listeners as background tasks. The WebSocket endpoint is served natively by
Uvicorn alongside the HTTP app.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from mud.config import CORS_ORIGINS, HOST, PORT
from mud.game_loop import async_game_loop
from mud.net.connection import handle_connection_with_stream
from mud.net.ssh_server import create_server as create_ssh_server
from mud.net.telnet_server import create_server as create_telnet_server
from mud.network.websocket_stream import WebSocketStream
from mud.server_bootstrap import bootstrap_server

# Configurable via configure() before uvicorn starts the app.
_telnet_host: str = "0.0.0.0"
_telnet_port: int = 5001
_ssh_host: str = "0.0.0.0"
_ssh_port: int = 2222


def configure(
    telnet_host: str = "0.0.0.0",
    telnet_port: int = 5001,
    ssh_host: str = "0.0.0.0",
    ssh_port: int = 2222,
) -> None:
    """Set the telnet and SSH listener addresses used by the multi-server."""
    global _telnet_host, _telnet_port, _ssh_host, _ssh_port
    _telnet_host = telnet_host
    _telnet_port = telnet_port
    _ssh_host = ssh_host
    _ssh_port = ssh_port


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Bootstrap the world once and start all background servers."""
    # Shared one-time initialization.
    bootstrap_server("area/area.lst")

    # Single game loop for every transport.
    game_task = asyncio.create_task(async_game_loop())

    # Start telnet and SSH listeners in Uvicorn's loop.
    telnet_server = await create_telnet_server(host=_telnet_host, port=_telnet_port)
    ssh_server = await create_ssh_server(host=_ssh_host, port=_ssh_port)

    # Log listening addresses.
    for sock in telnet_server.sockets or []:
        addr = sock.getsockname()
        print(f"[Telnet] Serving on {addr[0]}:{addr[1]}")
    for sock in getattr(ssh_server, "sockets", []) or []:
        addr = sock.getsockname()
        print(f"[SSH] Serving on {addr[0]}:{addr[1]} (connect: ssh -p {addr[1]} player@{addr[0]})")

    print("🎮 Multi-server game loop started")

    try:
        yield
    finally:
        print("Shutting down multi-server...")

        game_task.cancel()
        try:
            await game_task
        except asyncio.CancelledError:
            pass

        telnet_server.close()
        await telnet_server.wait_closed()

        # asyncssh.SSHAcceptor mirrors asyncio.Server's close/wait_closed API.
        try:
            ssh_server.close()
            await ssh_server.wait_closed()
        except AttributeError:
            pass

        print("Multi-server stopped")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    stream = WebSocketStream(websocket)
    await handle_connection_with_stream(
        stream,
        host_for_ban=stream.peer_host,
        connection_type="WebSocket",
    )


def run(
    host: str = HOST,
    port: int = PORT,
    telnet_host: str = "0.0.0.0",
    telnet_port: int = 5001,
    ssh_host: str = "0.0.0.0",
    ssh_port: int = 2222,
) -> None:
    """Run the combined server with Uvicorn owning the event loop."""
    configure(
        telnet_host=telnet_host,
        telnet_port=telnet_port,
        ssh_host=ssh_host,
        ssh_port=ssh_port,
    )
    uvicorn.run("mud.multi_server:app", host=host, port=port)


if __name__ == "__main__":
    run()
