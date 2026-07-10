"""LOOK-016 — `look <char>` must show the victim's worn equipment.

ROM `show_char_to_char_1` (src/act_info.c:483-499) loops `iWear` 0..MAX_WEAR,
and for each `get_eq_char(victim, iWear)` the observer `can_see_obj`, prints:
  "\n\r"  (once) + act("$N is using:")   — header, capitalized
  where_name[iWear] + format_obj_to_char(obj, ch, TRUE) + "\n\r"   — per item

The port's `_show_equipment` read `getattr(char, "equipped", {})` — but the
attribute is `char.equipment` (int-keyed by WearLocation), and there is NO
`equipped` attribute, so `getattr(..., {})` always returned `{}` and the entire
"is using:" block was dead code. This is the equipment-key convention class
(AGENTS.md school-light/combat-shield bug), via a phantom attribute NAME that a
string-key grep-guard can't see.

Also verifies the ROM rendering: the `where_name` prefix, `format_obj_to_char`
status tags (e.g. "(Glowing)"), and ascending slot order.
"""

from __future__ import annotations

from mud.models.constants import ExtraFlag, ItemType, WearLocation
from mud.models.object import Object, ObjIndex
from mud.world import create_test_character, initialize_world
from mud.world.look import look


def _make_obj(vnum: int, short: str, wear_loc: int, *, glow: bool = False) -> Object:
    proto = ObjIndex(vnum=vnum, short_descr=short, item_type=int(ItemType.ARMOR))
    obj = Object(instance_id=vnum, prototype=proto)
    obj.short_descr = short
    obj.item_type = int(ItemType.ARMOR)
    obj.wear_loc = wear_loc
    if glow:
        obj.extra_flags = int(ExtraFlag.GLOW)
    return obj


def _setup():
    initialize_world("area/area.lst")
    observer = create_test_character("Observer", 3001)
    victim = create_test_character("Victim", 3001)
    return observer, victim


def test_look_char_shows_equipment_block():
    observer, victim = _setup()
    helm = _make_obj(80001, "a steel helm", int(WearLocation.HEAD))
    victim.equip_object(helm, int(WearLocation.HEAD))

    result = look(observer, "Victim")

    assert "is using:" in result, f"equipment block missing: {result!r}"
    assert "a steel helm" in result
    assert "<worn on head>" in result


def test_look_char_equipment_uses_format_obj_to_char_tags_and_order():
    observer, victim = _setup()
    # A glowing shield + a wielded weapon; ROM lists in ascending slot order,
    # and each line carries format_obj_to_char status tags.
    shield = _make_obj(80002, "a bright shield", int(WearLocation.SHIELD), glow=True)
    weapon = _make_obj(80003, "a long sword", int(WearLocation.WIELD))
    victim.equip_object(shield, int(WearLocation.SHIELD))
    victim.equip_object(weapon, int(WearLocation.WIELD))

    result = look(observer, "Victim")

    assert "(Glowing) a bright shield" in result, f"missing status tag: {result!r}"
    # SHIELD (slot 12) precedes WIELD (slot 16) in ascending ROM order.
    assert result.index("a bright shield") < result.index("a long sword")
    # No non-ROM 2-space indent before the where_name marker.
    assert "  <worn as shield>" not in result
