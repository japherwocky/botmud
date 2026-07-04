"""GET-016 — command-local get_obj_weight must apply ROM's WEIGHT_MULT to contents.

ROM ``get_obj_weight`` (src/handler.c) scales a container's contents by its
``WEIGHT_MULT`` (``merc.h:2137`` — ``value[4]`` for ITEM_CONTAINER, else 100)::

    weight = obj->weight;
    for (tobj = obj->contains; tobj; tobj = tobj->next_content)
        weight += get_obj_weight (tobj) * WEIGHT_MULT (obj) / 100;

So a magic bag (``value[4]=50``) holding a 100-lb item weighs ``bag + 50``, not
``bag + 100``. The command-local ``_get_obj_weight`` helpers used by the
``do_get`` / ``do_put`` carry-weight gates recursed into contents WITHOUT the
``* WEIGHT_MULT / 100`` factor, so Python's ``can_carry_w`` gate could REFUSE a
pickup ROM allows. (The canonical ``Character`` carry-weight already applied the
multiplier; only these two duplicated command-gate helpers diverged.)
"""

from __future__ import annotations

import pytest

from mud.commands.inventory import _get_obj_weight as _inv_get_obj_weight
from mud.commands.inventory import do_get
from mud.commands.obj_manipulation import _get_obj_weight as _put_get_obj_weight
from mud.models.constants import ItemType
from mud.models.object import Object, ObjIndex
from mud.registry import area_registry, mob_registry, obj_registry, room_registry
from mud.world import initialize_world

_VNUM = [90600]


def _uv() -> int:
    _VNUM[0] += 1
    return _VNUM[0]


@pytest.fixture(scope="module", autouse=True)
def _world():
    initialize_world("area/area.lst")
    yield
    area_registry.clear()
    room_registry.clear()
    obj_registry.clear()
    mob_registry.clear()


@pytest.fixture
def room():
    from mud.models.room import Room

    if 3001 not in room_registry:
        room_registry[3001] = Room(vnum=3001, name="Test Room", description="A test room")
    r = room_registry[3001]
    r.contents = []
    return r


def _magic_bag_with_heavy_item(room):
    """A carried-capacity magic bag (value[4]=50) on the ground holding a 100-lb item."""
    bag_proto = ObjIndex(
        vnum=_uv(),
        name="bag",
        short_descr="a magic bag",
        item_type=ItemType.CONTAINER,
        wear_flags=1,
        value=[100, 0, 0, 100, 50],  # value[4]=50 → WEIGHT_MULT 50
        weight=10,
    )
    obj_registry[bag_proto.vnum] = bag_proto
    bag = Object(prototype=bag_proto, instance_id=None)
    bag.value = list(bag_proto.value)
    bag.location = room
    bag.contained_items = []

    heavy_proto = ObjIndex(vnum=_uv(), name="anvil", short_descr="an iron anvil", item_type=ItemType.TRASH, weight=100)
    obj_registry[heavy_proto.vnum] = heavy_proto
    heavy = Object(prototype=heavy_proto, instance_id=None)
    heavy.in_obj = bag
    bag.contained_items.append(heavy)

    room.contents = [bag]
    return bag


def test_get_obj_weight_helpers_apply_weight_mult(room):
    """Both duplicated command-gate helpers scale contents by WEIGHT_MULT."""
    bag = _magic_bag_with_heavy_item(room)
    # base 10 + 100 * 50 / 100 = 60 (ROM), not 10 + 100 = 110.
    assert _inv_get_obj_weight(bag) == 60
    assert _put_get_obj_weight(bag) == 60


def test_do_get_allows_magic_bag_within_capacity(room):
    """do_get must not refuse a magic bag whose WEIGHT_MULT-scaled weight fits."""
    from mud.models.character import Character

    bag = _magic_bag_with_heavy_item(room)

    char = Character(name="Hauler", is_npc=False, race=0, ch_class=0)
    char.room = room
    char.location = room
    char.level = 1
    char.inventory = []
    char.carry_weight = 0
    char.carry_number = 0
    # No STR stat → can_carry_w == 100. Scaled bag weight 60 fits; unscaled 110 would not.

    result = do_get(char, "bag")
    text = result[0] if isinstance(result, tuple) else result

    assert "you get" in str(text).lower(), f"magic bag should be picked up, got: {text!r}"
    assert bag in char.inventory
