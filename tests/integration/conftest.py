"""
Integration test framework for player workflows.

These tests simulate complete player scenarios to ensure end-to-end
functionality beyond unit testing of individual components.

DEFAULT BEHAVIOUR (changed 2026-07): these tests are skipped by default.
They were originally a "ROM 2.4 port completion" parity harness — tests that
lock the Python port to ROM C source line-by-line.  The project no longer
treats ROM parity as a goal (see `docs/integration_test_framework.md` for the
original charter), so the 2987-test suite is preserved for reference but not
run on every CI / dev invocation.

The skip is implemented in ``tests/conftest.py`` (top-level) so it applies
whether the user runs ``pytest``, ``pytest tests/``, or ``pytest tests/integration/``.
Run them with ``--include-parity`` (or ``make test-parity``).
"""

from __future__ import annotations

import pytest

from mud.models.character import Character
from mud.models.room import Room
from mud.registry import room_registry
from mud.utils import rng_mm


@pytest.fixture(autouse=True)
def _seed_rng():
    """Seed Mitchell-Moore RNG to a known state before every integration test.

    DO NOT REMOVE. The Mitchell-Moore RNG (mud.utils.rng_mm) is global
    mutable state. Without this fixture, RNG state leaks across test
    boundaries and the suite is flaky on any test depending on a
    probabilistic outcome — scavenger 1/64 action roll, AoE saves,
    holy_word damage rolls, combat hit/miss, etc. Different tests fail
    on different runs purely based on test execution order.

    Added in v2.6.2 alongside the giant_strength test fix. See
    CHANGELOG.md and AGENTS.md "Test determinism (RNG)" for context.

    To override the default seed for a specific test, call
    rng_mm.seed_mm(your_seed) inside the test body after fixture setup.
    """
    rng_mm.seed_mm(12345)


@pytest.fixture
def test_room():
    """Create a basic test room"""
    room = Room(
        vnum=1000, name="Test Room", description="A room for testing player interactions.", room_flags=0, sector_type=0
    )
    room.people = []  # Initialize people list
    room.contents = []  # Initialize contents list
    room_registry[1000] = room
    yield room
    room_registry.pop(1000, None)


@pytest.fixture
def test_player(test_room):
    """Create a test player character"""
    from mud.models.character import character_registry

    char = Character(
        name="TestPlayer",
        level=5,
        room=test_room,
        gold=1000,
        hit=100,
        max_hit=100,
        is_npc=False,
    )
    test_room.people.append(char)
    character_registry.append(char)  # Add to registry so game_tick() processes it
    yield char
    if char in test_room.people:
        test_room.people.remove(char)
    if char in character_registry:
        character_registry.remove(char)


@pytest.fixture
def test_mob(test_room):
    """Create a test mob in the room"""
    mob = Character(
        name="test mob",
        short_descr="a test mob",
        long_descr="A test mob is standing here.",
        level=3,
        room=test_room,
        is_npc=True,
        hit=50,
        max_hit=50,
    )
    test_room.people.append(mob)

    yield mob

    if mob in test_room.people:
        test_room.people.remove(mob)


def create_shopkeeper(room: Room, name: str = "shopkeeper") -> Character:
    """Helper to create a shopkeeper mob"""
    mob = Character(
        name=name,
        short_descr=f"a {name}",
        long_descr=f"A {name} is standing here.",
        level=10,
        room=room,
        is_npc=True,
    )
    room.people.append(mob)
    return mob
