import os

# Bind every test run to a private in-memory SQLite database. Done BEFORE
# `mud.db.session` is imported because that module creates the engine at
# import time from $DATABASE_URL. `setdefault` (not `environ =`) lets an
# explicit `DATABASE_URL=sqlite:///some/path.db pytest ...` invocation
# still target a file DB (handy for poking at a real DB after a failure).
#
# xdist isolation: each xdist worker is a separate subprocess, so its
# :memory: DB is naturally isolated — no per-worker file logic needed.
# `mud/db/session.py` pairs :memory: with StaticPool so the engine holds a
# single shared connection; otherwise each new SQLAlchemy connection would
# see a fresh empty DB and tests would race the schema.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import gc as _gc

import pytest  # noqa: E402  (must follow the DATABASE_URL setup above)
from helpers import ensure_can_move as _ensure_can_move_helper  # noqa: E402

# Periodic-GC counter. Without periodic Gen-2 collection, ~900 iterations
# of initialize_world exhaust RAM (circular refs never freed).
_gc_counter: int = 0


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------
# `mud.db.session.engine` is module-level and built at import time from
# $DATABASE_URL. By the time this conftest runs, the engine already points
# at sqlite:///:memory: with StaticPool (a single shared connection). We
# create the schema once per pytest session here so every test sees the
# same tables; individual tests that need a clean slate still call
# drop_all/create_all themselves — that's now near-instant on :memory:.
@pytest.fixture(scope="session", autouse=True)
def _init_db():
    from mud.db.models import Base
    from mud.db.session import engine

    Base.metadata.create_all(engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(engine)


# ---------------------------------------------------------------------------
# World setup / teardown
# ---------------------------------------------------------------------------
# Per-test world isolation. Replaces the duplicated `setup_world` autouse
# fixture that lived in tests/test_player_*.py, tests/test_spec_fun_behaviors.py,
# tests/test_mob_act_flags.py, and tests/test_mob_damage_modifiers.py.
#
# Function scope: every test starts with a freshly-initialized world and
# ends with empty world registries, so tests can't leak mobs/objects/rooms
# into each other. (The `character_registry` clear is belt-and-suspenders —
# `initialize_world` already clears it at the top, but the explicit clear
# here is the contract that lets the next test rely on a clean slate even
# if the production code adds early returns to `initialize_world` later.)
#
# Tests that need extra cleanup (e.g. `global_registry.descriptor_list = []`
# in tests/test_player_info_commands.py) keep a small local fixture that
# runs alongside this one.
@pytest.fixture(autouse=True)
def _isolate_world():
    from mud.models.character import character_registry
    from mud.registry import (
        area_registry,
        mob_registry,
        obj_registry,
        room_registry,
    )
    from mud.world import initialize_world

    initialize_world("area/area.lst")
    yield
    area_registry.clear()
    mob_registry.clear()
    obj_registry.clear()
    room_registry.clear()
    character_registry.clear()
    # Periodically force Gen-2 GC to free circular-referenced world
    # objects (Room → people, Character → room, inventories, etc.).
    # Without this, ~900 iterations exhaust RAM (~32 GB typ.).
    global _gc_counter
    _gc_counter += 1
    if _gc_counter % 100 == 0:
        _gc.collect()


# ---------------------------------------------------------------------------
# ROM parity test gating
# ---------------------------------------------------------------------------
# tests/integration/ holds 2987 tests that originally formed a "ROM 2.4 port
# completion" parity harness — they lock the Python port to ROM C source
# line-by-line. The project no longer treats ROM parity as a goal (see
# docs/integration_test_framework.md and the github issue thread), so the
# suite is preserved for reference but EXCLUDED FROM COLLECTION BY DEFAULT
# (so the test session doesn't print 3000 skipped tests).
#
# To run the parity suite:    pytest --include-parity    (or: make test-parity)
# ---------------------------------------------------------------------------
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--include-parity",
        action="store_true",
        default=False,
        help=(
            "Include the ROM parity test suite in tests/integration/. Excluded "
            "from collection by default because the project no longer treats "
            "ROM parity as a goal. See tests/integration/README.md."
        ),
    )


def pytest_ignore_collect(collection_path: object, config: pytest.Config) -> bool | None:
    """Skip walking into tests/integration/ unless --include-parity is set.

    We return True (not None) so pytest not only doesn't run these tests — it
    doesn't even COLLECT them. The 3000-test progress display in
    `pytest -q`/`make test` then shows only the ~1700 active tests, with no
    noise from parity skips.
    """
    if config.getoption("--include-parity"):
        return None  # user opted in: collect everything
    # os.sep for Windows compat: str(path) uses backslashes on Windows.
    if f"tests{os.sep}integration" in str(collection_path):
        return True
    return None


# Session-scoped fixture to make sure the help greeting text is loaded once.
# Several test files (e.g. tests/test_account_auth.py) spin up the real
# telnet server and expect _send_help_greeting() to emit the ROM welcome
# banner; that function reads from the module-level `help_greeting` global
# populated by `load_help_file`. Without this fixture the global is empty
# and the banner is never sent.
@pytest.fixture(autouse=True, scope="session")
def _load_help_greeting():
    from mud.loaders.help_loader import load_help_file

    load_help_file("data/help.json")
    yield


@pytest.fixture(autouse=True)
def _enable_world_invariant_checks(request):
    """Opt-in: assert steady-state ROM world invariants after every game_tick.

    The checker (`mud.diagnostics.invariants.check_world_invariants`) walks the
    GLOBAL `character_registry` / `room_registry`, so running it after every
    game_tick suite-wide was flaky: tests legitimately leave those un-isolated
    registries in incoherent cross-test states (a registered char whose room no
    longer lists it, in-place `room.people` mutations), which tripped the checker
    in an unrelated sibling depending on xdist worker grouping. It is therefore
    **opt-in**: only tests marked `@pytest.mark.check_invariants` enable it, and
    such a test is responsible for a coherent world (typically a fresh
    `initialize_world` or a self-contained setup). Production leaves the flag off.
    """
    if not request.node.get_closest_marker("check_invariants"):
        yield
        return
    import mud.game_loop as game_loop

    prev = game_loop._INVARIANT_CHECK_ENABLED
    game_loop._INVARIANT_CHECK_ENABLED = True
    try:
        yield
    finally:
        game_loop._INVARIANT_CHECK_ENABLED = prev


@pytest.fixture(autouse=True)
def _reset_tick_prompt_state():
    """Reset INV-053 tick-output prompt tracking between tests.

    ``mud.utils.messaging`` keeps a module-level ``_in_tick`` flag and
    ``_prompt_dirty`` list to mirror ROM's per-pulse output phase. A test that
    drives ``async_game_loop`` (or wraps ``begin_tick_output``) could leave the
    flag set or a char queued; clear before and after so it never leaks across
    the files sharing an xdist worker.
    """
    from mud.utils import messaging

    messaging.reset_prompt_dirty()
    yield
    messaging.reset_prompt_dirty()


@pytest.fixture(autouse=True)
def _reset_bootstrap():
    """Reset `bootstrap_server`'s idempotency guard between tests.

    `mud.server_bootstrap.bootstrap_server` is idempotent at runtime (so
    telnet/SSH/WebSocket can each call it safely in the multi-server
    lifespan), but the test suite wants every test to start with a clean
    world. Reset the guard before each test so a fresh `bootstrap_server`
    call will re-run migrations and `initialize_world` for the test.
    """
    from mud.server_bootstrap import reset_bootstrap

    reset_bootstrap()
    yield


@pytest.fixture(autouse=True)
def _reset_descriptor_list():
    """Prevent `registry.descriptor_list` leaking across tests.

    `wiznet()` (mud/wiznet.py) iterates `registry.descriptor_list` when it is
    present and non-empty, otherwise falls back to `character_registry`. Many
    net/wiznet tests set `registry.descriptor_list` directly; if one leaks a
    non-empty list, a later registry-only test (e.g.
    test_logging_admin::test_log_all_notifies_secure_wiznet) silently takes the
    descriptor path and never sees its test character. Snapshot/restore makes
    each test's mutation non-leaking while preserving any module-scoped setup.
    """
    from mud import registry

    had = hasattr(registry, "descriptor_list")
    snapshot = getattr(registry, "descriptor_list", None)
    yield
    if had:
        registry.descriptor_list = snapshot
    elif hasattr(registry, "descriptor_list"):
        delattr(registry, "descriptor_list")


@pytest.fixture(autouse=True)
def _redirect_save_area_list(tmp_path, monkeypatch):
    """Keep OLC `asave` tests from rewriting the repo's `data/areas/area.lst`.

    `mud/olc/save.py:save_area_list` defaults to the relative path
    `data/areas/area.lst`; `cmd_asave` ("list"/"world"/"changed") calls it with
    no argument, so any asave test that doesn't redirect the write clobbers the
    tracked file with the in-memory registry (dropping entries like `test.json`).
    Redirect only the default path to a per-test tmp file; explicit paths (the
    tests that pass `output_file=tmp_path/...`) pass through unchanged. cmd_asave
    re-imports the symbol at call time, so patching the module attribute works.
    """
    import mud.olc.save as _olc_save

    _real_save_area_list = _olc_save.save_area_list
    _default = "data/areas/area.lst"

    def _redirected(output_file=_default):
        if str(output_file) == _default:
            output_file = str(tmp_path / "area.lst")
        return _real_save_area_list(output_file=output_file)

    monkeypatch.setattr(_olc_save, "save_area_list", _redirected)


@pytest.fixture(autouse=True)
def _reset_object_registry():
    """INV-012: object_registry is global mutable state populated by
    spawn_object. Without this fixture, tests that call spawn_object would
    leak instances across the whole suite.

    NOTE: The old snapshot/restore pattern accumulated objects across tests
    because initialize_world (from _isolate_world) adds objects BEFORE this
    fixture runs, so the snapshot captured both old and new worlds' objects.
    The objects live in object_registry permanently, preventing GC and causing
    OOM after ~900 tests. Simple clear at both ends suffices — initialize_world
    repopulates the registry fresh each test.
    """
    from mud.models.obj import object_registry

    object_registry.clear()
    yield
    object_registry.clear()


@pytest.fixture
def ensure_can_move():
    """Callable fixture to provision movement points on a character-like entity.

    Usage: ensure_can_move(char[, points])
    """
    return _ensure_can_move_helper


@pytest.fixture
def movable_char_factory():
    """Factory fixture that creates a test character with movement set.

    Example:
        ch = movable_char_factory('Tester', 3001, points=200)
    """
    from mud.world import create_test_character

    def _factory(name: str, room_vnum: int, *, points: int = 100):
        ch = create_test_character(name, room_vnum)
        _ensure_can_move_helper(ch, points)
        return ch

    return _factory


@pytest.fixture
def movable_mob_factory():
    """Factory fixture that spawns a mob and ensures it can move.

    Example:
        mob = movable_mob_factory(3000, 3001, points=150)
    """
    from mud.registry import room_registry
    from mud.spawning.mob_spawner import spawn_mob

    def _factory(vnum: int, room_vnum: int, *, points: int = 100):
        mob = spawn_mob(vnum)
        room = room_registry[room_vnum]
        room.add_mob(mob)
        _ensure_can_move_helper(mob, points)
        return mob

    return _factory


@pytest.fixture
def place_object_factory():
    """Factory that places an object in a room.

    Usage:
        obj = place_object_factory(room_vnum=3001, vnum=3031)
        obj = place_object_factory(room_vnum=3001, proto_kwargs={"vnum": 9999, "short_descr": "a stone"})
    """
    from mud.models.obj import ObjIndex
    from mud.models.object import Object
    from mud.registry import room_registry
    from mud.spawning.obj_spawner import spawn_object

    def _factory(*, room_vnum: int, vnum: int | None = None, proto_kwargs: dict | None = None):
        room = room_registry[room_vnum]
        if vnum is not None:
            obj = spawn_object(vnum)
            assert obj is not None
        else:
            proto_kwargs = proto_kwargs or {}
            proto = ObjIndex(**proto_kwargs)
            obj = Object(instance_id=None, prototype=proto)
        room.add_object(obj)
        return obj

    return _factory


@pytest.fixture
def object_factory():
    """Factory that returns an object instance without placing it in a room.

    Usage:
        obj = object_factory({"vnum": 9999, "short_descr": "a stone"})
    """
    from mud.models.obj import ObjIndex
    from mud.models.object import Object

    def _factory(proto_kwargs: dict):
        proto = ObjIndex(**proto_kwargs)
        return Object(instance_id=None, prototype=proto)

    return _factory


@pytest.fixture
def inventory_object_factory():
    """Factory that spawns a ROM object by vnum for inventory use.

    Wraps spawn_object(vnum) for clarity in tests.
    """
    from mud.spawning.obj_spawner import spawn_object

    def _factory(vnum: int):
        obj = spawn_object(vnum)
        assert obj is not None
        return obj

    return _factory


@pytest.fixture
def portal_factory(place_object_factory):
    """Convenience to create a portal object in a room.

    Example:
        portal_factory(3001, to_vnum=3054, closed=True)
    """
    from mud.models.constants import EX_CLOSED, ItemType

    def _factory(
        room_vnum: int,
        *,
        to_vnum: int,
        closed: bool = False,
        gate_flags: int = 0,
        charges: int = 1,
    ):
        flags = EX_CLOSED if closed else 0
        obj = place_object_factory(
            room_vnum=room_vnum,
            proto_kwargs={
                "vnum": 9998,
                "name": "shimmering portal",
                "short_descr": "a shimmering portal",
                "item_type": int(ItemType.PORTAL),
            },
        )
        # ROM portal values: [charges, exit_flags, portal_flags, to_vnum, placeholder]
        values = [charges, flags, gate_flags, to_vnum, 0]
        obj.prototype.value = values.copy()
        if hasattr(obj, "value"):
            obj.value = values.copy()
        return obj

    return _factory
