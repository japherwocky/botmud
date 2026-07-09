"""FIGHT-093 — damage() 1200-point loophole cap + weapon-extract cheat penalty.

ROM src/fight.c:700-713 — before the dam>35 / dam>80 reduction, damage() clamps
any physical hit (``dt >= TYPE_HIT``) whose raw damage exceeds 1200 back to 1200,
logs a bug, and — unless the attacker is an immortal — sends "You really
shouldn't cheat." and extracts the attacker's wielded weapon.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mud.combat.engine import apply_damage, get_wielded_weapon
from mud.combat.messages import TYPE_HIT
from mud.models.constants import DamageType, ItemType, WeaponType, WearLocation
from mud.world import initialize_world


@pytest.fixture(autouse=True)
def setup_world():
    """Populate room_registry so movable_mob_factory can spawn into room 3001."""
    initialize_world("area/area.lst")


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


def test_over_1200_physical_hit_caps_and_extracts_weapon(movable_char_factory, movable_mob_factory, object_factory):
    """A non-immortal wielder dealing >1200 physical damage loses their weapon.

    Mirrors ROM src/fight.c:700-713 — dam capped to 1200, "You really shouldn't
    cheat." to the attacker, and extract_obj on the wielded weapon. Victim is an
    NPC so is_safe (ROM's PC-vs-PC clan gate) does not short-circuit the hit.
    """
    attacker = movable_char_factory("cheater", 3001)
    victim = movable_mob_factory(3000, 3001)
    victim.max_hit = 5000
    victim.hit = 5000

    weapon = _weapon(object_factory, 2701, "exploit blade")
    attacker.equip_object(weapon, int(WearLocation.WIELD))
    assert get_wielded_weapon(attacker) is weapon

    # Patch weapon defenses off so the capped damage lands deterministically —
    # the cap gate (dt >= TYPE_HIT) also enables parry/dodge/shield checks, and
    # this test targets the loophole cap, not defense RNG.
    with (
        patch("mud.combat.engine.check_parry", return_value=False),
        patch("mud.combat.engine.check_dodge", return_value=False),
        patch("mud.combat.engine.check_shield_block", return_value=False),
        patch("mud.combat.engine._riv_check", return_value=0),  # neutral RIV — cap math only
    ):
        apply_damage(attacker, victim, 1500, DamageType.SLASH, dt=TYPE_HIT)

    # Weapon extracted from the game (ROM extract_obj) — no longer wielded.
    assert get_wielded_weapon(attacker) is None
    assert weapon not in (attacker.inventory or [])
    # Cheat penalty message delivered to the attacker.
    assert any("shouldn't cheat" in m for m in attacker.messages)
    # Damage clamped to 1200 before the >35/>80 reduction: 1200 -> 617 -> 348.
    assert victim.hit == 5000 - 348


def test_over_1200_spell_hit_does_not_trigger_cheat_penalty(movable_char_factory, object_factory):
    """The loophole cap gates on ``dt >= TYPE_HIT`` — spells (string dt) are exempt.

    Mirrors ROM src/fight.c:700 — ``dam > 1200 && dt >= TYPE_HIT``; a spell dt is
    below TYPE_HIT, so the weapon is not extracted even on a >1200 raw hit.
    """
    attacker = movable_char_factory("mage", 3001)
    victim = movable_char_factory("target", 3001)
    victim.max_hit = 5000
    victim.hit = 5000

    weapon = _weapon(object_factory, 2702, "mage dagger")
    attacker.equip_object(weapon, int(WearLocation.WIELD))

    apply_damage(attacker, victim, 1500, DamageType.FIRE, dt="fireball")

    assert get_wielded_weapon(attacker) is weapon
    assert not any("shouldn't cheat" in m for m in attacker.messages)
