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

# Module-level guard so multiple callers (e.g. a combined server's lifespan
# followed by the telnet/SSH `create_server` helpers) can all call
# `bootstrap_server` without re-running migrations or re-initializing the
# world. This keeps `create_server` a self-contained entry point while
# remaining safe for the multi-server which already bootstraps once.
_BOOTSTRAPPED: bool = False


def bootstrap_server(area_list: str = DEFAULT_AREA_LIST) -> None:
    """Initialize the database, world data, and persistent runtime state.

    This mirrors the startup sequence used by every standalone server:
    load configuration, run DB migrations, load areas/resets, then restore
    persistent bans. Idempotent: safe to call from multiple entry points
    (e.g. a combined server's lifespan followed by `create_server`); the
    second and subsequent calls are no-ops.
    """
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    _BOOTSTRAPPED = True

    load_qmconfig()
    run_migrations()
    initialize_world(area_list)
    # Reload persistent ban entries after world bootstrap clears runtime registries.
    bans.load_bans_file()


def reset_bootstrap() -> None:
    """Reset the bootstrap guard. Test-only: lets a test suite re-bootstrap
    between isolated test cases that each want a fresh world."""
    global _BOOTSTRAPPED
    _BOOTSTRAPPED = False
