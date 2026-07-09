"""MOVE-009 — do_flee omits move_char's "$n leaves"/"$n has arrived" broadcasts.

ROM ``do_flee`` (``src/fight.c:3002``) performs the escape by calling
``move_char(ch, door, FALSE)``, which broadcasts ``act("$n leaves $T.", ...)``
to the fled-from room and ``act("$n has arrived.", ...)`` to the destination
room (``src/act_move.c:196-202``) — unless the fleer is sneaking or wizinvis.
The Python ``mud/commands/combat.py:do_flee`` re-implemented the move inline and
emitted only the ``"$n has fled!"`` line, so bystanders never saw the fleer
leave or arrive.
"""

from __future__ import annotations

import pytest

from mud.commands.combat import do_flee
from mud.models.constants import AffectFlag, Position
from mud.models.room import Exit
from mud.registry import area_registry, room_registry
from mud.utils import rng_mm
from mud.world import create_test_character, initialize_world


@pytest.fixture(autouse=True)
def _restore_world_registries():
    rooms_before = dict(room_registry)
    areas_before = dict(area_registry)
    yield
    room_registry.clear()
    room_registry.update(rooms_before)
    area_registry.clear()
    area_registry.update(areas_before)


def _setup(monkeypatch):
    initialize_world()
    src_vnum = 3001
    fleer = create_test_character("Fleer", src_vnum)
    src_room = fleer.room
    assert src_room is not None

    opponent = create_test_character("Attacker", src_vnum)
    opponent.position = Position.FIGHTING
    opponent.messages = []

    dst_room = next(r for v, r in room_registry.items() if v != src_vnum and r is not None)
    arrival_witness = create_test_character("Arrival", src_vnum)
    src_room.remove_character(arrival_witness)  # created in src; move it to the destination
    dst_room.add_character(arrival_witness)
    arrival_witness.messages = []

    exits_list = [None] * 6
    exits_list[0] = Exit(to_room=dst_room, exit_info=0, keyword="north", key=0)
    src_room.exits = exits_list

    fleer.position = Position.FIGHTING
    fleer.hit = fleer.max_hit = 100
    fleer.wait = 0
    fleer.move = fleer.max_move = 100
    fleer.fighting = opponent

    monkeypatch.setattr(rng_mm, "number_door", lambda: 0)
    return fleer, opponent, arrival_witness


def test_flee_broadcasts_leaves_and_arrives(monkeypatch: pytest.MonkeyPatch) -> None:
    """ROM move_char emits '$n leaves $T.' to the old room and '$n has arrived.' to the new."""
    fleer, opponent, arrival_witness = _setup(monkeypatch)

    do_flee(fleer, "")

    # "$n leaves north." to the fled-from room (opponent left behind).
    left_behind = "\n".join(opponent.messages)
    assert "Fleer leaves north." in left_behind, f"no leave broadcast: {opponent.messages!r}"
    # "$n has arrived." to the destination room. ($n PERS-masks to "Someone" when
    # the arbitrary destination room is unlit — correct ROM behavior; the gap under
    # test is delivery of the arrival broadcast, not the name rendering.)
    arrived = "\n".join(arrival_witness.messages)
    assert "has arrived." in arrived, f"no arrival broadcast: {arrival_witness.messages!r}"


def test_sneaking_fleer_suppresses_leave_arrive(monkeypatch: pytest.MonkeyPatch) -> None:
    """ROM src/act_move.c:196/201 gate the leave/arrive lines on !AFF_SNEAK."""
    fleer, opponent, arrival_witness = _setup(monkeypatch)
    fleer.affected_by = int(getattr(fleer, "affected_by", 0) or 0) | int(AffectFlag.SNEAK)

    do_flee(fleer, "")

    assert "leaves" not in "\n".join(opponent.messages)
    assert "has arrived" not in "\n".join(arrival_witness.messages)
