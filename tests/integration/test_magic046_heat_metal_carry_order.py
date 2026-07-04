"""MAGIC-046 — heat_metal walks ROM's single ``ch->carrying`` list + remove_obj lines.

(a) ROM spell_heat_metal (src/magic.c:3134) iterates ``victim->carrying`` — one LIFO
    list interleaving worn and carried items in acquisition order. The port walked
    ``inventory + equipment.values()`` (all carried, then all worn), so the per-object
    ``number_range``/``saves_spell`` draws landed on different objects than ROM. Fixed
    by iterating ``Character.iter_carrying()`` (descending ``_carry_seq``).

(d) ROM's worn-item branch calls ``remove_obj`` (src/act_obj.c:1389-1390), which emits
    ``act("$n stops using $p.", TO_ROOM)`` / ``act("You stop using $p.", TO_CHAR)``
    BEFORE the "yelps and throws"/"red-hot weapon" heat lines. The port modelled
    remove_obj as a boolean and dropped those two lines.
"""

from __future__ import annotations

import mud.skills.handlers as handlers
from mud.models.character import Character
from mud.models.constants import ItemType, WearLocation
from mud.models.object import Object, ObjIndex
from mud.models.room import Room
from mud.skills.handlers import heat_metal
from mud.utils import rng_mm


def _obj(name: str, **kw) -> Object:
    proto = ObjIndex(
        vnum=kw.get("vnum", 1),
        short_descr=name,
        item_type=kw.get("item_type", ItemType.ARMOR),
        level=kw.get("level", 10),
        extra_flags=kw.get("extra_flags", 0),
        weight=kw.get("weight", 10),
    )
    obj = Object(instance_id=None, prototype=proto)
    obj.short_descr = name
    for k, v in kw.items():
        setattr(obj, k, v)
    return obj


def test_iter_carrying_merges_inventory_and_equipment_in_lifo_order() -> None:
    ch = Character(name="mob", level=30, is_npc=True)
    a = _obj("alpha")
    ch.add_object(a)  # carried, seq 1
    b = _obj("bravo")
    ch.add_object(b)
    ch.equip_object(b, int(WearLocation.BODY))  # worn, seq 2 (kept)
    c = _obj("charlie")
    ch.add_object(c)  # carried, seq 3

    # ROM ch->carrying is newest-first → charlie, bravo, alpha (descending seq),
    # interleaving the worn bravo. The old inventory+equipment walk gave
    # [charlie, alpha] + [bravo] = charlie, alpha, bravo.
    assert [o.short_descr for o in ch.iter_carrying()] == ["charlie", "bravo", "alpha"]


def test_worn_armor_removal_emits_remove_obj_stop_using_lines(monkeypatch) -> None:
    room = Room(vnum=3001)
    room.contents = []
    caster = Character(name="caster", level=30, is_npc=True, room=room)
    victim = Character(name="victim", level=10, is_npc=True, imm_flags=0, room=room)
    victim.perm_stat = [18, 18, 18, 18, 18]
    victim.messages = []
    caster.messages = []

    armor = _obj("a steel helm", item_type=ItemType.ARMOR, level=5, weight=10, wear_loc=int(WearLocation.HEAD))
    victim.equipment = {int(WearLocation.HEAD): armor}

    # Force the heat gate + dex-removal path deterministically.
    monkeypatch.setattr(handlers, "saves_spell", lambda *a, **k: False)
    monkeypatch.setattr(rng_mm, "number_range", lambda lo, hi: hi)

    heat_metal(caster, victim)

    # ROM remove_obj lines fire before the heat "remove and drop" line.
    assert any("You stop using a steel helm" in m for m in victim.messages), victim.messages
    assert any("You remove and drop a steel helm" in m for m in victim.messages), victim.messages
    stop_idx = next(i for i, m in enumerate(victim.messages) if "You stop using" in m)
    throw_idx = next(i for i, m in enumerate(victim.messages) if "You remove and drop" in m)
    assert stop_idx < throw_idx, "remove_obj 'stop using' line must precede the heat 'throws' line"
