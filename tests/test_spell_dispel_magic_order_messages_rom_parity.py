"""MAGIC-050 — dispel_magic must walk ROM's fixed spell list and emit its
per-effect TO_ROOM wear-off messages, in ROM order.

ROM ``spell_dispel_magic`` (``src/magic.c:2089-2247``) runs ``check_dispel`` over
a hardcoded spell list in a fixed order, and for certain spells broadcasts a
room ``act`` line ("$n is no longer blinded.", fly → "$n falls to the ground!",
etc.). The Python port iterated the ``spell_effects`` dict (arbitrary order) and
emitted none of these room messages. This locks the fixed order + the messages.
"""

from __future__ import annotations

from mud.models.character import Character, SpellEffect
from mud.models.constants import Position
from mud.models.room import Room
from mud.skills import handlers as h

_RNG_PATH = "mud.utils.rng_mm.number_percent"


def _force_roll(monkeypatch, value: int) -> None:
    # number_percent() >= save → per-effect check_dispel SUCCEEDS (effect removed).
    monkeypatch.setattr(_RNG_PATH, lambda: value)


def make_character(**overrides) -> Character:
    base = {
        "name": overrides.get("name", "mob"),
        "level": overrides.get("level", 30),
        "hit": overrides.get("hit", 100),
        "max_hit": overrides.get("max_hit", 100),
        "position": overrides.get("position", Position.STANDING),
        "is_npc": overrides.get("is_npc", True),
    }
    char = Character(**base)
    for key, value in overrides.items():
        setattr(char, key, value)
    char.messages = []
    return char


def make_room() -> Room:
    return Room(vnum=3001, name="Test Room", description="A test room.")


def test_dispel_magic_emits_room_messages_in_fixed_order(monkeypatch):
    """blindness precedes fly in ROM's list, so the room sees the blind line first."""
    monkeypatch.setattr(h, "saves_spell", lambda level, tgt, dtype: False)  # pass wholesale gate
    _force_roll(monkeypatch, 100)  # every per-effect dispel succeeds

    room = make_room()
    caster = make_character(name="caster", level=50, is_npc=False, room=room)
    target = make_character(name="target", level=10, room=room)
    witness = make_character(name="witness", level=10, room=room)
    witness.messages = []
    room.people = [caster, target, witness]

    # Applied in the "wrong" order relative to ROM's list to prove order comes
    # from the fixed walk, not insertion order.
    target.apply_spell_effect(SpellEffect(name="fly", duration=10, level=10))
    target.apply_spell_effect(SpellEffect(name="blindness", duration=10, level=10))

    result = h.dispel_magic(caster, target)

    assert result is True
    joined = "\n".join(witness.messages)
    assert "is no longer blinded." in joined, witness.messages
    assert "falls to the ground!" in joined, witness.messages
    # Fixed-list order: blindness (ROM :2097) before fly (:2152).
    assert joined.index("no longer blinded") < joined.index("falls to the ground")
    # ROM :2249 — "Ok." to the caster when something was dispelled.
    assert "Ok." in caster.messages


def test_dispel_magic_reports_spell_failed_when_nothing_dispelled(monkeypatch):
    """ROM :2251 — 'Spell failed.' to the caster when found == FALSE."""
    monkeypatch.setattr(h, "saves_spell", lambda level, tgt, dtype: False)  # pass wholesale gate

    room = make_room()
    caster = make_character(name="caster", level=50, is_npc=False, room=room)
    target = make_character(name="target", level=10, room=room)
    room.people = [caster, target]

    result = h.dispel_magic(caster, target)

    assert result is False
    assert "Spell failed." in caster.messages
