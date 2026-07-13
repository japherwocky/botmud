from __future__ import annotations

import asyncio

from mud.config import get_qmconfig
from mud.server_bootstrap import bootstrap_server

from .connection import handle_connection


async def create_server(
    host: str = "0.0.0.0", port: int = 4000, area_list: str = "area/area.lst"
) -> asyncio.AbstractServer:
    """Return a started telnet server without blocking the loop.

    Initializes the world via `bootstrap_server` (idempotent — safe to call
    before the multi-server's lifespan bootstrap). The combined multi-server
    and any caller that has already bootstrapped can simply call this; the
    bootstrap will be a no-op-equivalent the second time around.
    """
    bootstrap_server(area_list)
    qmconfig = get_qmconfig()
    configured_host = (qmconfig.ip_address or "").strip()
    bind_host = host.strip() if isinstance(host, str) else ""
    if not bind_host or bind_host == "0.0.0.0":
        bind_host = configured_host or "0.0.0.0"
    return await asyncio.start_server(handle_connection, bind_host, port)


async def start_server(host: str = "0.0.0.0", port: int = 4000, area_list: str = "area/area.lst") -> None:
    from mud.game_loop import async_game_loop

    # Initialize database, world data, and persistent state.
    bootstrap_server(area_list)
    server = await create_server(host, port, area_list)
    sockets = getattr(server, "sockets", None)
    if sockets:
        addr = sockets[0].getsockname()
        print(f"Serving on {addr}")

    # Start game loop as background task
    game_task = asyncio.create_task(async_game_loop())
    print("🎮 Game loop started")

    try:
        async with server:
            await server.serve_forever()
    finally:
        # Clean shutdown: cancel game loop
        game_task.cancel()
        try:
            await game_task
        except asyncio.CancelledError:
            print("Game loop stopped")
            pass


if __name__ == "__main__":
    asyncio.run(start_server())
