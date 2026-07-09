"""MAGIC-046 (remainder) — MobInstance.iter_carrying walks ROM ``victim->carrying`` order.

ROM keeps every mob's worn+carried items in a single LIFO ``carrying`` list
(``src/handler.c:1626`` obj_to_char head-inserts; equip only flips wear_loc).
Mechanics that mirror ROM's ``for (obj = victim->carrying; ...)`` walk — notably
``heat_metal`` (``src/magic.c:3134``) — must iterate that order so their
per-object ``number_range``/``saves_spell`` draws land on the same objects ROM
hits. ``Character.iter_carrying`` re-merges the PC's split inventory/equipment;
``MobInstance`` keeps everything in one head-inserted ``inventory`` list, so its
``iter_carrying`` is that list in natural (newest-first) order. Before this fix
``MobInstance`` had no ``iter_carrying``, so ``heat_metal`` fell to a generic
branch instead of a first-class mob carrying walk.
"""

from __future__ import annotations

import pytest

from mud.models.constants import ItemType, WeaponType, WearLocation
from mud.models.mob import MobIndex
from mud.models.room import Room
from mud.registry import room_registry
from mud.spawning.templates import MobInstance


def _weapon(object_factory, vnum: int, name: str):
    obj = object_factory(
        {
            "vnum": vnum,
            "name": name,
            "short_descr": f"a {name}",
            "item_type": int(ItemType.WEAPON),
            "value": [int(WeaponType.SWORD), 1, 6, 0, 0],
        }
    )
    obj.extra_flags = 0
    return obj


@pytest.fixture
def mob():
    room = Room(vnum=3001, name="Test Room", description="A test room")
    room_registry[3001] = room
    m = MobInstance(
        name="mob",
        level=10,
        current_hp=100,
        max_hit=100,
        prototype=MobIndex(vnum=3000, short_descr="a mob"),
        room=room,
        perm_stat=[13, 13, 13, 13, 13],
    )
    room.people.append(m)
    return m


def test_mob_iter_carrying_is_lifo_acquisition_order(mob, object_factory):
    """A mob that acquires A then B walks [B, A] — ROM head-insert LIFO."""
    a = _weapon(object_factory, 4101, "sword A")
    b = _weapon(object_factory, 4102, "sword B")

    mob.add_to_inventory(a)
    mob.add_to_inventory(b)

    order = list(mob.iter_carrying())
    assert order[0] is b
    assert order[1] is a


def test_mob_iter_carrying_includes_worn_items_in_order(mob, object_factory):
    """Equipped items stay in the single carrying list at their acquisition slot."""
    carried = _weapon(object_factory, 4103, "carried blade")
    worn = _weapon(object_factory, 4104, "worn blade")

    mob.equip(worn, int(WearLocation.WIELD))  # acquired first
    mob.add_to_inventory(carried)  # acquired second (newest)

    order = list(mob.iter_carrying())
    assert order[0] is carried
    assert order[1] is worn
    assert worn.wear_loc == int(WearLocation.WIELD)
