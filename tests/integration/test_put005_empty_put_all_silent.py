"""PUT-005 — `put all <container>` with nothing eligible is SILENT (ROM adds no message).

ROM `do_put` (src/act_obj.c:451-491) implements the `put all <container>` /
`put all.x <container>` branch as a bare `for` loop with **no `found` flag and no
trailing message**: if nothing is eligible, ROM prints nothing at all. The port
added `if count == 0: return "You have nothing to put."`, a non-ROM line (same
class as MOVE-006's invented gate). Trigger: `put all bag` when only the bag is
carried (a container cannot be put into itself) → count 0.
"""

from __future__ import annotations

from mud.commands.obj_manipulation import do_put
from mud.models.constants import ContainerFlag, ItemType, Position
from mud.models.object import Object, ObjIndex
from mud.models.room import Room


def _pc_with_only_a_container():
    room = Room(vnum=9760, name="hall")
    from mud.models.character import Character

    pc = Character(name="putter", is_npc=False, level=20, position=Position.STANDING)
    pc.inventory = []
    pc.equipment = {}
    room.add_character(pc)
    proto = ObjIndex(vnum=8760, name="bag", short_descr="a leather bag", item_type=int(ItemType.CONTAINER))
    bag = Object(instance_id=0, prototype=proto)
    bag.short_descr = "a leather bag"
    bag.item_type = int(ItemType.CONTAINER)
    # Open, closeable, roomy — eligible as a target but the only carried item.
    bag.value = [100, int(ContainerFlag.CLOSEABLE), 0, 0, 0]
    pc.inventory.append(bag)
    bag.carried_by = pc
    return pc


def test_put_all_with_nothing_eligible_is_silent():
    pc = _pc_with_only_a_container()
    # Only the bag is carried; a container can't be put into itself → nothing eligible.
    result = do_put(pc, "all bag")
    assert result == "", f"ROM prints nothing on an empty put-all; got {result!r}"
