"""GL-046 — plague-spread RNG draw order/count parity (char-side twin of GL-045/GL-026).

ROM ``src/update.c:824,829-841`` computes the infection roll as:

    plague.duration = number_range (1, 2 * plague.level);   // ONCE, before the loop
    for (vch = ch->in_room->people; vch; vch = vch->next_in_room)
        if (!saves_spell (plague.level - 2, vch, DAM_DISEASE)  // drawn for EVERY occupant
            && !IS_IMMORTAL (vch)
            && !IS_AFFECTED (vch, AFF_PLAGUE)
            && number_bits (4) == 0)                            // drawn LAST, only if prior pass
            { affect_join (vch, &plague); }

Two RNG contracts follow:

1. ``saves_spell`` (which draws ``number_percent``) is evaluated for **every**
   occupant of the room — including the plagued character itself, immortals, and
   already-plagued victims (they fail the later non-RNG terms, but the save draw
   still happens because it is the first ``&&`` operand). ``number_bits(4)`` is
   only drawn for a victim who failed the save and is neither immortal nor
   already plagued.
2. The affect ``duration`` is drawn **once**, before the loop, so every victim
   infected in the same tick shares the same duration.

The pre-fix Python pre-filtered occupants (skipping ch/immortal/plagued with no
save draw), drew ``number_bits`` *before* the save, and drew ``duration``
per-infected-victim inside the loop — three ways to desync the shared
Mitchell-Moore stream from ROM.
"""

from __future__ import annotations

import pytest

from mud.models.character import AffectData, Character, character_registry
from mud.models.constants import AffectFlag, Position, Sex
from mud.models.room import Room
from mud.registry import room_registry

_LEVEL_IMMORTAL = 52


@pytest.fixture(autouse=True)
def _cleanup():
    snapshot = list(character_registry)
    character_registry.clear()
    yield
    character_registry.clear()
    character_registry.extend(snapshot)
    room_registry.pop(9590, None)


def _make_room() -> Room:
    room = Room(vnum=9590, name="Pesthouse", description="", room_flags=0)
    room.people = []
    room.contents = []
    room_registry[9590] = room
    return room


def _add_char(room: Room, name: str, *, level: int = 10, plagued: bool = False) -> Character:
    ch = Character(
        name=name,
        is_npc=False,
        level=level,
        room=room,
        sex=int(Sex.MALE),
        position=int(Position.STANDING),
        default_pos=int(Position.STANDING),
    )
    ch.messages = []
    if plagued:
        ch.affected_by = int(AffectFlag.PLAGUE)
        ch.affected = [
            AffectData(type="plague", level=12, duration=10, location=0, modifier=-5, bitvector=int(AffectFlag.PLAGUE))
        ]
    room.people.append(ch)
    character_registry.append(ch)
    return ch


def _plague_duration(ch: Character) -> int | None:
    for af in getattr(ch, "affected", []) or []:
        if (getattr(af, "type", None) or getattr(af, "spell_name", None)) == "plague":
            return int(getattr(af, "duration", 0) or 0)
    return None


def test_saves_spell_drawn_for_every_occupant_number_bits_last(monkeypatch: pytest.MonkeyPatch) -> None:
    """ROM :832 — the save roll fires once per room occupant; number_bits is gated behind it."""
    from mud import game_loop as gl
    from mud.affects import saves as saves_module
    from mud.game_loop import _char_update_tick_effects

    room = _make_room()
    plagued = _add_char(room, "Carrier", level=20, plagued=True)
    _add_char(room, "AliceNormal")
    _add_char(room, "BobNormal")
    _add_char(room, "Highgod", level=_LEVEL_IMMORTAL)
    _add_char(room, "SickAlready", plagued=True)

    save_calls: list = []
    bits_calls: list = []

    def _spy_save(*args, **kwargs):
        save_calls.append(args)
        return True  # everyone saves -> nobody infected, number_bits short-circuited away

    monkeypatch.setattr(saves_module, "saves_spell", _spy_save)
    monkeypatch.setattr(gl.rng_mm, "number_bits", lambda _bits: bits_calls.append(_bits) or 0)

    _char_update_tick_effects(plagued)

    # saves_spell drawn once per occupant (5) — including the carrier, the immortal,
    # and the already-plagued bystander (ROM's first-&&-operand semantics).
    assert len(save_calls) == len(room.people) == 5
    # number_bits is never drawn when every save succeeds (short-circuit).
    assert bits_calls == []


def test_plague_duration_drawn_once_and_shared_by_all_victims(monkeypatch: pytest.MonkeyPatch) -> None:
    """ROM :824 — plague.duration is drawn once before the loop, so co-infected victims share it."""
    from mud import game_loop as gl
    from mud.affects import saves as saves_module
    from mud.game_loop import _char_update_tick_effects

    room = _make_room()
    plagued = _add_char(room, "Carrier", level=20, plagued=True)
    alice = _add_char(room, "AliceNormal")
    bob = _add_char(room, "BobNormal")

    # Distinct value every number_range call, so a per-victim draw would differ.
    seq = iter(range(3, 100))
    monkeypatch.setattr(gl.rng_mm, "number_range", lambda _low, _high: next(seq))
    monkeypatch.setattr(gl.rng_mm, "number_bits", lambda _bits: 0)
    monkeypatch.setattr(saves_module, "saves_spell", lambda *a, **k: False)

    _char_update_tick_effects(plagued)

    da = _plague_duration(alice)
    db = _plague_duration(bob)
    assert da is not None and db is not None, "both bystanders should be infected"
    assert da == db, f"co-infected victims must share the single pre-loop duration draw, got {da} != {db}"
