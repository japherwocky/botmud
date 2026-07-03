"""PICK-003 — do_pick door immortal check uses IS_IMMORTAL (get_trust >= 52).

ROM ``do_pick`` gates the three door bypasses on ``!IS_IMMORTAL(ch)``
(``src/act_move.c:958,963,973``):

    if (!IS_SET (pexit->exit_info, EX_CLOSED) && !IS_IMMORTAL (ch)) ...
    if (pexit->key < 0 && !IS_IMMORTAL (ch)) ...
    if (IS_SET (pexit->exit_info, EX_PICKPROOF) && !IS_IMMORTAL (ch)) ...

``IS_IMMORTAL(ch) = get_trust(ch) >= LEVEL_IMMORTAL`` (``src/merc.h:2091``),
``LEVEL_IMMORTAL = MAX_LEVEL-8 = 52`` (``src/merc.h:149``), and
``get_trust(ch)`` returns ``ch->trust`` when set else ``ch->level``
(``src/handler.c``). The Python port hardcoded ``trust >= 51`` (a comment even
mislabelled it "LEVEL_HERO threshold" — ROM uses IS_IMMORTAL, not IS_HERO) AND
read raw ``char.trust`` with no ``get_trust`` level fallback. That produced two
divergences, both fixed by routing through the canonical ``Character.is_immortal()``:

1. A trust-51 mortal hero was wrongly treated as immortal (bypassed pickproof).
2. A level-52 immortal with trust unset (0) was wrongly treated as mortal
   (refused on a pickproof door), because ``get_trust`` should fall back to level.
"""

from __future__ import annotations

import pytest

from mud.models.character import character_registry
from mud.models.constants import EX_CLOSED, EX_ISDOOR, EX_LOCKED, EX_PICKPROOF
from mud.models.room import Exit, Room
from mud.registry import room_registry
from mud.utils import rng_mm
from mud.world import create_test_character


@pytest.fixture(autouse=True)
def _clean_state():
    rooms = set(room_registry)
    char_ids = {id(c) for c in character_registry}
    yield
    for vnum in list(room_registry):
        if vnum not in rooms:
            room_registry.pop(vnum, None)
    character_registry[:] = [c for c in character_registry if id(c) in char_ids]


def _room(vnum: int) -> Room:
    room = Room(vnum=vnum, name=f"Room {vnum}", description="")
    room_registry[vnum] = room
    return room


def _make_pickproof_door(here: Room, there: Room) -> None:
    pexit = Exit(
        to_room=there,
        keyword="gate iron",
        # Closed + locked + PICKPROOF, positive key (pickable only by an immortal).
        exit_info=EX_ISDOOR | EX_CLOSED | EX_LOCKED | EX_PICKPROOF,
        key=88800,
    )
    here.exits = [None, pexit, None, None, None, None]  # EAST


def _picker(name: str, room_vnum: int, *, level: int, trust: int):
    char = create_test_character(name, room_vnum)
    char.level = level
    char.trust = trust
    char.skills = {"pick lock": 100}  # never fails the skill roll (percent <= 100)
    char.messages = []
    return char


def test_pick003_trust51_hero_is_mortal_cannot_pick_pickproof_door():
    """RED for the threshold bug: trust 51 (LEVEL_HERO) must NOT bypass pickproof."""
    from mud.commands.doors import do_pick

    rng_mm.seed_mm(42)
    here = _room(50300)
    there = _room(50301)
    _make_pickproof_door(here, there)
    picker = _picker("Hero", 50300, level=51, trust=51)

    result = do_pick(picker, "gate")

    # ROM: 51 < LEVEL_IMMORTAL(52) => not immortal => pickproof gate fires.
    assert result == "You failed."
    # The door stays locked.
    assert here.exits[1].exit_info & EX_LOCKED


def test_pick003_immortal_with_unset_trust_falls_back_to_level_and_bypasses():
    """RED for the get_trust fallback bug: level-52 immortal, trust unset, bypasses."""
    from mud.commands.doors import do_pick

    rng_mm.seed_mm(42)
    here = _room(50310)
    there = _room(50311)
    _make_pickproof_door(here, there)
    # trust=0 (unset) => get_trust falls back to level 52 => IS_IMMORTAL true.
    picker = _picker("Deity", 50310, level=52, trust=0)

    result = do_pick(picker, "gate")

    # ROM: get_trust(ch)=level=52 >= LEVEL_IMMORTAL => bypass pickproof => *Click*.
    assert result == "*Click*"
    assert not (here.exits[1].exit_info & EX_LOCKED)
