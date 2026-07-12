"""Shared server bootstrap used by all MUD server entry points.

Centralizes the world-initialization sequence so telnet, SSH, WebSocket,
and the combined multi-server do not duplicate it.
"""

from __future__ import annotations

from mud.config import load_qmconfig
from mud.db.migrations import run_migrations
from mud.security import bans
from mud.world.world_state import initialize_world

DEFAULT_AREA_LIST = "area/area.lst"


def bootstrap_server(area_list: str = DEFAULT_AREA_LIST) -> None:
    """Initialize the database, world data, and persistent runtime state.

    This mirrors the startup sequence used by every standalone server:
    load configuration, run DB migrations, load areas/resets, then restore
    persistent bans. It is safe to call exactly once per process.
    """
    load_qmconfig()
    run_migrations()
    initialize_world(area_list)
    # Reload persistent ban entries after world bootstrap clears runtime registries.
    bans.load_bans_file()
