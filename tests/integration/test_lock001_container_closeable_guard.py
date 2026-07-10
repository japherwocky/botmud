"""LOCK-001 — do_lock/do_unlock container arm must NOT check CONT_CLOSEABLE.

Unlike ``do_open`` / ``do_close`` (which DO check ``CONT_CLOSEABLE`` after
``CONT_CLOSED`` — see MOVE-008), ROM's ``do_lock`` (src/act_move.c:627-656) and
``do_unlock`` (761-791) container branches have **no** ``CONT_CLOSEABLE`` check
at all.  Their first guard is ``!IS_SET(value[1], CONT_CLOSED)`` →
``"It's not closed."``

The port inserted a spurious ``if not CLOSEABLE: "You can't do that."`` as the
first guard, so a common **open non-closeable** container (a pouch/pack/belt
pouch — ``value[1] == 0``, 98 such protos ship in the stock areas) reported
"You can't do that." on ``lock``/``unlock`` where ROM reports "It's not closed."
"""

from __future__ import annotations

from mud.commands.doors import do_lock, do_unlock
from mud.models.character import Character
from mud.models.constants import ItemType, Position
from mud.models.object import Object, ObjIndex
from mud.models.room import Room


def _pc_with_container(value1: int, key_vnum: int = 0) -> Character:
    room = Room(vnum=9701, name="test-room")
    pc = Character(name="pc", is_npc=False, level=10, position=Position.STANDING)
    room.add_character(pc)
    proto = ObjIndex(vnum=8701, name="pouch", short_descr="a belt pouch", item_type=int(ItemType.CONTAINER))
    obj = Object(instance_id=0, prototype=proto)
    obj.short_descr = "a belt pouch"
    obj.item_type = int(ItemType.CONTAINER)
    obj.value = [0, value1, key_vnum, 0, 0]  # value[1] = flags, value[2] = key vnum
    pc.add_object(obj)
    return pc


def test_lock_open_non_closeable_container_reports_not_closed():
    """ROM do_lock container arm: first guard is CONT_CLOSED, not CONT_CLOSEABLE."""
    pc = _pc_with_container(0)  # open, not closeable (a belt pouch)
    assert do_lock(pc, "pouch") == "It's not closed."


def test_unlock_open_non_closeable_container_reports_not_closed():
    """ROM do_unlock container arm: first guard is CONT_CLOSED, not CONT_CLOSEABLE."""
    pc = _pc_with_container(0)  # open, not closeable
    assert do_unlock(pc, "pouch") == "It's not closed."
