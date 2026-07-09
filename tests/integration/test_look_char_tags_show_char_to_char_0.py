"""LOOK char-tags — show_char_to_char_0 renders all 12 status tags in ROM order.

ROM ``show_char_to_char_0`` (``src/act_info.c:253-276``) prepends, in this fixed
order: ``[AFK]`` ``(Invis)`` ``(Wizi)`` ``(Hide)`` ``(Charmed)`` ``(Translucent)``
``(Pink Aura)`` ``(Red Aura)`` ``(Golden Aura)`` ``(White Aura)`` ``(KILLER)``
``(THIEF)``. The Python room-occupant line rendered only ``(Pink Aura)`` and
``(White Aura)`` (via ``describe_character``); the other ten were missing.
"""

from __future__ import annotations

from mud.models.character import Character
from mud.models.constants import AffectFlag, CommFlag, PlayerFlag, Position
from mud.models.room import Room
from mud.world.look import _room_occupant_line


def _pc(name: str, **kw) -> Character:
    c = Character(name=name, level=30, is_npc=False, position=Position.STANDING)
    c.messages = []
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def test_room_occupant_line_renders_all_tags_in_rom_order():
    room = Room(vnum=3001, name="Test Room", description="A test room.")
    # Observer: HOLYLIGHT (sees everything) + DETECT_EVIL/GOOD to trigger the auras.
    observer = _pc("Observer")
    observer.act = int(PlayerFlag.HOLYLIGHT)
    observer.affected_by = int(AffectFlag.DETECT_EVIL) | int(AffectFlag.DETECT_GOOD)

    victim = _pc("Victim")
    victim.comm = int(CommFlag.AFK)
    victim.invis_level = 60  # >= LEVEL_HERO (51) → (Wizi)
    victim.affected_by = (
        int(AffectFlag.INVISIBLE)
        | int(AffectFlag.HIDE)
        | int(AffectFlag.CHARM)
        | int(AffectFlag.PASS_DOOR)
        | int(AffectFlag.FAERIE_FIRE)
        | int(AffectFlag.SANCTUARY)
    )
    victim.alignment = -1000  # IS_EVIL → (Red Aura) with observer DETECT_EVIL
    victim.act = int(PlayerFlag.KILLER) | int(PlayerFlag.THIEF)

    room.add_character(observer)
    room.add_character(victim)

    line = _room_occupant_line(observer, victim)

    expected_order = [
        "[AFK]",
        "(Invis)",
        "(Wizi)",
        "(Hide)",
        "(Charmed)",
        "(Translucent)",
        "(Pink Aura)",
        "(Red Aura)",
        "(White Aura)",  # golden requires IS_GOOD; this victim is evil, so it is absent
        "(KILLER)",
        "(THIEF)",
    ]
    positions = []
    for tag in expected_order:
        assert tag in line, f"{tag!r} missing from {line!r}"
        positions.append(line.index(tag))
    assert positions == sorted(positions), f"tags out of ROM order in {line!r}"
    assert "(Golden Aura)" not in line  # victim is evil, not good


def test_golden_aura_requires_good_alignment_and_observer_detect_good():
    room = Room(vnum=3001, name="Test Room", description="A test room.")
    observer = _pc("Observer")
    observer.act = int(PlayerFlag.HOLYLIGHT)
    observer.affected_by = int(AffectFlag.DETECT_GOOD)

    victim = _pc("Saint")
    victim.alignment = 1000  # IS_GOOD

    room.add_character(observer)
    room.add_character(victim)

    line = _room_occupant_line(observer, victim)
    assert "(Golden Aura)" in line
    assert "(Red Aura)" not in line
