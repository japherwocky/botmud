"""LOCK-002 — do_lock/do_unlock container key guard is `value[2] < 0`, not `<= 0`.

ROM's `do_lock` (src/act_move.c:637) and `do_unlock` (773) container branches
gate "It can't be [un]locked." on `obj->value[2] < 0` — key vnum **0** falls
through to the `has_key` check, which fails for a keyless container and yields
"You lack the key." (has_key never matches vnum 0 — no real object protos to it).

The port used `value[2] <= 0`, so a common **closed keyless** container
(`value[2] == 0` — 14 such protos ship in the stock areas, e.g. `hitower.json`)
short-circuited to "It can't be locked." where ROM says "You lack the key."
The portal sibling one branch up correctly uses `< 0`, proving the intent.
"""

from __future__ import annotations

from mud.commands.doors import do_lock, do_unlock
from mud.models.character import Character
from mud.models.constants import ContainerFlag, ItemType, Position
from mud.models.object import Object, ObjIndex
from mud.models.room import Room


def _pc_with_closed_keyless_container() -> Character:
    room = Room(vnum=9702, name="test-room")
    pc = Character(name="pc", is_npc=False, level=10, position=Position.STANDING)
    room.add_character(pc)
    proto = ObjIndex(vnum=8702, name="chest", short_descr="an iron chest", item_type=int(ItemType.CONTAINER))
    obj = Object(instance_id=0, prototype=proto)
    obj.short_descr = "an iron chest"
    obj.item_type = int(ItemType.CONTAINER)
    # CLOSEABLE|CLOSED, key vnum 0 (keyless) — value[2] == 0.
    obj.value = [0, int(ContainerFlag.CLOSEABLE | ContainerFlag.CLOSED), 0, 0, 0]
    pc.add_object(obj)
    return pc


def test_lock_closed_keyless_container_reports_lack_the_key():
    """ROM value[2] < 0 → key vnum 0 falls through has_key → 'You lack the key.'"""
    pc = _pc_with_closed_keyless_container()
    assert do_lock(pc, "chest") == "You lack the key."


def test_unlock_closed_keyless_container_reports_lack_the_key():
    """Symmetric to lock — do_unlock container arm gates on value[2] < 0."""
    pc = _pc_with_closed_keyless_container()
    assert do_unlock(pc, "chest") == "You lack the key."
