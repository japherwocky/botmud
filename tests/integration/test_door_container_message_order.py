"""MOVE-008 — do_open/do_close container arm checks CONT_CLOSED before CONT_CLOSEABLE.

ROM ``do_open`` / ``do_close`` (src/act_move.c) evaluate the container guards in the
order **CLOSED → CLOSEABLE → LOCKED**:

    if (!IS_SET (obj->value[1], CONT_CLOSED))   send "It's already open.";  return;
    if (!IS_SET (obj->value[1], CONT_CLOSEABLE)) send "You can't do that.";  return;

The port checked ``CLOSEABLE`` first, so an already-open (or already-closed)
NON-closeable container reported "You can't do that." where ROM reports
"It's already open." / "It's already closed."
"""

from __future__ import annotations

from mud.commands.doors import do_close, do_open
from mud.models.character import Character
from mud.models.constants import ContainerFlag, ItemType, Position
from mud.models.object import Object, ObjIndex
from mud.models.room import Room


def _pc_with_container(value1: int) -> Character:
    room = Room(vnum=9700, name="test-room")
    pc = Character(name="pc", is_npc=False, level=10, position=Position.STANDING)
    room.add_character(pc)
    proto = ObjIndex(vnum=8700, name="basket", short_descr="a wicker basket", item_type=int(ItemType.CONTAINER))
    obj = Object(instance_id=0, prototype=proto)
    obj.short_descr = "a wicker basket"
    obj.item_type = int(ItemType.CONTAINER)
    obj.value = [0, value1, 0, 0, 0]  # value[1] = container flags
    pc.add_object(obj)
    return pc


def test_open_already_open_non_closeable_container_reports_already_open():
    """ROM checks CONT_CLOSED first — an open non-closeable container is 'already open'."""
    pc = _pc_with_container(0)  # open, not closeable
    assert do_open(pc, "basket") == "It's already open."


def test_close_already_closed_non_closeable_container_reports_already_closed():
    """ROM do_close checks CONT_CLOSED first — a closed non-closeable container is 'already closed'."""
    pc = _pc_with_container(int(ContainerFlag.CLOSED))  # closed, not closeable
    assert do_close(pc, "basket") == "It's already closed."
