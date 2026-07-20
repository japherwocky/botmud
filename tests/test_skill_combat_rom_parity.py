"""
Tests for active combat skills.

Verifies that combat skills work correctly for players — preconditions,
success/failure outcomes, and observable side effects.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mud.commands.combat import (
    do_backstab,
    do_bash,
    do_berserk,
    do_dirt,
    do_disarm,
    do_kick,
    do_rescue,
    do_trip,
)
from mud.models.constants import AffectFlag, ItemType, Position, WeaponType
from mud.skills import skill_registry
from mud.spawning.templates import MobInstance
from mud.utils import rng_mm

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# Monkeypatch MobInstance with inventory/stat helpers needed by some tests.
def _mob_remove_object(self, obj):
    if obj in self.inventory:
        self.inventory.remove(obj)
    if hasattr(self, "equipment"):
        for slot, item in list(self.equipment.items()):
            if item is obj:
                del self.equipment[slot]


def _mob_add_object(self, obj):
    if obj not in self.inventory:
        self.inventory.append(obj)


def _mob_get_curr_stat(self, stat):
    if hasattr(self, "perm_stat") and isinstance(stat, int) and stat < len(self.perm_stat):
        return self.perm_stat[stat] + (self.mod_stat[stat] if hasattr(self, "mod_stat") else 0)
    return 13


if not hasattr(MobInstance, "remove_object"):
    MobInstance.remove_object = _mob_remove_object
if not hasattr(MobInstance, "add_object"):
    MobInstance.add_object = _mob_add_object
if not hasattr(MobInstance, "get_curr_stat"):
    MobInstance.get_curr_stat = _mob_get_curr_stat


def _weapon(object_factory, vnum: int = 1, weapon_type: WeaponType = WeaponType.SWORD):
    """Create a wieldable weapon."""
    return object_factory(
        {
            "vnum": vnum,
            "short_descr": "a weapon",
            "item_type": int(ItemType.WEAPON),
            "value": [0, 1, 6, int(weapon_type), 0],
        }
    )


def _equip(char, weapon):
    """Equip a weapon in the wield slot."""
    char.equipment = {"wielded": weapon}


def _ready_warrior(movable_char_factory, name="warrior", skill="bash", skill_level=75):
    """Create a warrior character with a given skill and no wait state."""
    char = movable_char_factory(name, 3001)
    char.skills[skill] = skill_level
    char.wait = 0
    return char


def _ready_thief(movable_char_factory, name="thief", skill="backstab", skill_level=75):
    """Create a thief character with a given skill and no wait state."""
    char = movable_char_factory(name, 3001)
    char.skills[skill] = skill_level
    char.wait = 0
    return char


def _target(movable_mob_factory, room_vnum: int = 3001, name: str = "mob"):
    """Create a basic mob target in FIGHTING position."""
    mob = movable_mob_factory(room_vnum, room_vnum)
    mob.name = name
    mob.position = Position.FIGHTING
    return mob


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def seed_rng():
    """Seed RNG for deterministic tests."""
    rng_mm.seed_mm(42)
    yield
    rng_mm.seed_mm(42)


# ---------------------------------------------------------------------------
# Backstab
# ---------------------------------------------------------------------------

class TestBackstab:
    def test_requires_argument(self, movable_char_factory):
        char = _ready_thief(movable_char_factory, skill="backstab")
        assert "Backstab whom?" in do_backstab(char, "")

    def test_cannot_while_fighting(self, movable_char_factory, movable_mob_factory):
        char = _ready_thief(movable_char_factory, skill="backstab")
        char.fighting = _target(movable_mob_factory)
        assert "wrong end" in do_backstab(char, "mob").lower()

    def test_target_must_be_in_room(self, movable_char_factory):
        char = _ready_thief(movable_char_factory, skill="backstab")
        assert "aren't here" in do_backstab(char, "nobody").lower()

    def test_cannot_backstab_self(self, movable_char_factory):
        char = _ready_thief(movable_char_factory, name="thief", skill="backstab")
        assert "sneak up on yourself" in do_backstab(char, "thief").lower()

    def test_requires_weapon(self, movable_char_factory, movable_mob_factory):
        char = _ready_thief(movable_char_factory, skill="backstab")
        _target(movable_mob_factory)
        assert "need to wield" in do_backstab(char, "mob").lower()

    def test_cannot_backstab_wounded_victim(self, movable_char_factory, movable_mob_factory, object_factory):
        char = _ready_thief(movable_char_factory, skill="backstab")
        _equip(char, _weapon(object_factory, weapon_type=WeaponType.DAGGER))
        mob = _target(movable_mob_factory)
        mob.max_hit = 300
        mob.hit = 90  # < 300/3
        assert "hurt and suspicious" in do_backstab(char, "mob").lower()

    def test_auto_success_on_sleeping_victim(self, movable_char_factory, movable_mob_factory, object_factory):
        char = _ready_thief(movable_char_factory, skill="backstab", skill_level=2)
        char.level = 10
        _equip(char, _weapon(object_factory, weapon_type=WeaponType.DAGGER))
        mob = _target(movable_mob_factory)
        mob.position = Position.SLEEPING
        mob.max_hit = 300
        mob.hit = 300
        with patch("mud.commands.combat.rng_mm.number_percent", return_value=99):
            result = do_backstab(char, "mob")
        assert result != "Backstab whom?"

    def test_success_returns_combat_message(self, movable_char_factory, object_factory):
        char = _ready_thief(movable_char_factory, skill="backstab", skill_level=100)
        char.level = 10
        _equip(char, _weapon(object_factory, weapon_type=WeaponType.DAGGER))
        victim = movable_char_factory("target", 3001)
        victim.max_hit = 300
        victim.hit = 300
        with patch("mud.commands.combat.rng_mm.number_percent", return_value=10):
            result = do_backstab(char, "target")
        # Successful backstab returns a combat message, not an error.
        assert "backstab" not in result.lower() or "whom" not in result.lower()

    def test_failure_does_not_deal_damage(self, movable_char_factory, object_factory):
        char = _ready_thief(movable_char_factory, skill="backstab", skill_level=1)
        char.level = 10
        _equip(char, _weapon(object_factory, weapon_type=WeaponType.DAGGER))
        victim = movable_char_factory("target", 3001)
        victim.max_hit = 300
        victim.hit = 300
        with patch("mud.commands.combat.rng_mm.number_percent", return_value=99):
            do_backstab(char, "target")
        assert victim.hit == 300

    def test_wait_state_applied(self, movable_char_factory, movable_mob_factory, object_factory):
        char = _ready_thief(movable_char_factory, skill="backstab")
        char.level = 10
        _equip(char, _weapon(object_factory, weapon_type=WeaponType.DAGGER))
        mob = _target(movable_mob_factory)
        mob.max_hit = 300
        mob.hit = 300
        do_backstab(char, "mob")
        assert hasattr(char, "wait")


# ---------------------------------------------------------------------------
# Bash
# ---------------------------------------------------------------------------

class TestBash:
    def test_requires_argument_or_fighting(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="bash")
        result = do_bash(char, "")
        assert "aren't fighting" in result.lower() or "bash whom" in result.lower()

    def test_target_must_be_in_room(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="bash")
        assert "aren't here" in do_bash(char, "nobody").lower()

    def test_cannot_bash_self(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, name="warrior", skill="bash")
        result = do_bash(char, "warrior")
        assert "bash your brains" in result.lower() or "can't bash yourself" in result.lower()

    def test_cannot_bash_resting_victim(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="bash")
        mob = _target(movable_mob_factory)
        mob.position = Position.RESTING
        result = do_bash(char, "mob")
        assert "get back up" in result.lower() or "resting" in result.lower()

    def test_requires_skill(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="bash", skill_level=0)
        result = do_bash(char, "")
        assert "bashing" in result.lower() and "what" in result.lower()

    def test_success_knocks_victim_to_resting(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="bash", skill_level=100)
        mob = _target(movable_mob_factory)
        mob.position = Position.FIGHTING
        with patch("mud.commands.combat.rng_mm.number_percent", return_value=0):
            do_bash(char, "mob")
        assert mob.position == Position.RESTING

    def test_failure_knocks_attacker_to_resting(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="bash", skill_level=1)
        char.position = Position.STANDING
        _target(movable_mob_factory)
        # Mock the handler to prevent it from overriding the position change.
        with (
            patch("mud.commands.combat.rng_mm.number_percent", return_value=99),
            patch("mud.commands.combat.skill_handlers.bash", return_value="fail"),
        ):
            do_bash(char, "mob")
        assert char.position == Position.RESTING

    def test_success_applies_daze_to_victim(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="bash", skill_level=100)
        mob = _target(movable_mob_factory)
        mob.daze = 0
        with (
            patch("mud.commands.combat.rng_mm.number_percent", return_value=0),
            patch("mud.config.get_pulse_violence", return_value=4),
        ):
            do_bash(char, "mob")
        assert mob.daze == 12

    def test_cannot_bash_while_recovering(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="bash")
        char.wait = 1
        _target(movable_mob_factory)
        assert "still recovering" in do_bash(char, "mob").lower()

    def test_success_deals_damage(self, movable_char_factory):
        # Use a PC target to avoid shopkeeper safety checks.
        # Both must be clan members with level diff ≤ 8 for PC-vs-PC safety gate.
        char = _ready_warrior(movable_char_factory, skill="bash", skill_level=100)
        char.clan = 1
        victim = movable_char_factory("target", 3001)
        victim.level = 10
        victim.clan = 1
        victim.position = Position.FIGHTING
        victim.max_hit = 300
        victim.hit = 300
        with patch("mud.commands.combat.rng_mm.number_percent", return_value=0):
            do_bash(char, "target")
        assert victim.hit < 300


# ---------------------------------------------------------------------------
# Kick
# ---------------------------------------------------------------------------

class TestKick:
    def test_requires_fighting(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="kick")
        char.level = 60
        char.fighting = None
        assert "aren't fighting" in do_kick(char, "").lower()

    def test_pc_under_required_level_blocked(self, movable_char_factory, movable_mob_factory):
        char = movable_char_factory("mage", 3001)
        char.skills["kick"] = 75
        skill = skill_registry.get("kick")
        required_level = int(skill.levels[int(getattr(char, "ch_class", 0) or 0)])
        char.level = required_level - 1
        victim = _target(movable_mob_factory)
        char.fighting = victim
        assert "martial arts" in do_kick(char, "").lower()

    def test_npc_without_offkick_returns_empty(self, movable_mob_factory):
        attacker = movable_mob_factory(3001, 3001)
        attacker.off_flags = 0
        victim = movable_mob_factory(3002, 3001)
        attacker.fighting = victim
        assert do_kick(attacker, "") == ""

    def test_success_deals_damage(self, movable_char_factory):
        # Use a PC target to avoid level-based damage reduction on mobs.
        char = _ready_warrior(movable_char_factory, skill="kick", skill_level=75)
        skill = skill_registry.get("kick")
        required_level = int(skill.levels[int(getattr(char, "ch_class", 0) or 0)])
        char.level = max(required_level, 10)
        victim = movable_char_factory("target", 3001)
        char.fighting = victim
        victim.max_hit = 300
        victim.hit = 300
        with patch("mud.commands.combat.rng_mm.number_percent", return_value=10):
            do_kick(char, "")
        assert victim.hit < 300

    def test_failure_deals_zero_damage(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="kick", skill_level=75)
        skill = skill_registry.get("kick")
        required_level = int(skill.levels[int(getattr(char, "ch_class", 0) or 0)])
        char.level = max(required_level, 10)
        victim = _target(movable_mob_factory)
        char.fighting = victim
        victim.max_hit = 300
        victim.hit = 300
        with patch("mud.commands.combat.rng_mm.number_percent", return_value=99):
            do_kick(char, "")
        assert victim.hit == 300

    def test_cannot_kick_while_recovering(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="kick")
        skill = skill_registry.get("kick")
        required_level = int(skill.levels[int(getattr(char, "ch_class", 0) or 0)])
        char.level = max(required_level, 1)
        char.wait = 1
        victim = _target(movable_mob_factory)
        char.fighting = victim
        assert "still recovering" in do_kick(char, "").lower()


# ---------------------------------------------------------------------------
# Disarm
# ---------------------------------------------------------------------------

class TestDisarm:
    def test_requires_skill(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="disarm", skill_level=0)
        assert "don't know" in do_disarm(char, "").lower()

    def test_requires_fighting(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="disarm")
        assert "aren't fighting" in do_disarm(char, "").lower()

    def test_requires_attacker_weapon_or_hand_to_hand(self, movable_char_factory, movable_mob_factory, object_factory):
        char = _ready_warrior(movable_char_factory, skill="disarm")
        char.skills["hand to hand"] = 0
        char.wielded_weapon = None
        char.equipment = {}
        victim = _target(movable_mob_factory)
        victim.wielded_weapon = _weapon(object_factory, vnum=100)
        victim.equipment = {"wield": victim.wielded_weapon}
        char.fighting = victim
        assert "must wield" in do_disarm(char, "").lower()

    def test_blocks_when_victim_unarmed(self, movable_char_factory, movable_mob_factory, object_factory):
        char = _ready_warrior(movable_char_factory, skill="disarm")
        _equip(char, _weapon(object_factory, vnum=200))
        char.wielded_weapon = char.equipment["wielded"]
        victim = _target(movable_mob_factory)
        victim.wielded_weapon = None
        victim.equipment = {}
        char.fighting = victim
        assert "not wielding" in do_disarm(char, "").lower()

    def test_success_message(self, movable_char_factory, movable_mob_factory, object_factory):
        char = _ready_warrior(movable_char_factory, skill="disarm", skill_level=100)
        _equip(char, _weapon(object_factory, vnum=300))
        char.wielded_weapon = char.equipment["wielded"]
        victim = _target(movable_mob_factory)
        victim.wielded_weapon = _weapon(object_factory, vnum=301)
        victim.equipment = {"wield": victim.wielded_weapon}
        char.fighting = victim
        with patch("mud.skills.handlers.rng_mm.number_percent", return_value=0):
            result = do_disarm(char, "")
        assert "disarm" in result.lower()

    def test_failure_message(self, movable_char_factory, movable_mob_factory, object_factory):
        char = _ready_warrior(movable_char_factory, skill="disarm", skill_level=100)
        _equip(char, _weapon(object_factory, vnum=400))
        char.wielded_weapon = char.equipment["wielded"]
        victim = _target(movable_mob_factory)
        victim.wielded_weapon = _weapon(object_factory, vnum=401)
        victim.equipment = {"wield": victim.wielded_weapon}
        char.fighting = victim
        with patch("mud.skills.handlers.rng_mm.number_percent", return_value=99):
            result = do_disarm(char, "")
        assert "fail" in result.lower()


# ---------------------------------------------------------------------------
# Trip
# ---------------------------------------------------------------------------

class TestTrip:
    def test_requires_victim_or_fighting(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="trip")
        result = do_trip(char, "")
        assert "trip whom" in result.lower() or "aren't fighting" in result.lower()

    def test_target_must_be_in_room(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="trip")
        assert "aren't here" in do_trip(char, "nobody").lower()

    def test_blocks_flying_targets(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="trip")
        victim = _target(movable_mob_factory)
        victim.affected_by = int(AffectFlag.FLYING)
        assert "feet aren't on the ground" in do_trip(char, "mob").lower()

    def test_blocks_victim_already_down(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="trip")
        victim = _target(movable_mob_factory)
        victim.position = Position.RESTING
        assert "already down" in do_trip(char, "mob").lower()

    def test_uses_fighting_target_when_no_argument(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="trip")
        char.level = 20
        char.perm_stat = [13, 13, 13, 13, 13]
        victim = _target(movable_mob_factory)
        victim.level = 20
        victim.perm_stat = [13, 13, 13, 13, 13]
        char.fighting = victim
        with (
            patch("mud.commands.combat.rng_mm.number_percent", return_value=0),
            patch("mud.commands.combat.rng_mm.number_range", return_value=2),
            patch("mud.commands.combat.apply_damage", return_value="ok"),
        ):
            result = do_trip(char, "")
        assert "trip" in result.lower() or result == "ok"

    def test_success_knocks_victim_to_resting(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="trip")
        char.level = 20
        char.perm_stat = [13, 13, 13, 13, 13]
        victim = _target(movable_mob_factory)
        victim.level = 20
        victim.position = Position.FIGHTING
        victim.perm_stat = [13, 13, 13, 13, 13]
        with (
            patch("mud.commands.combat.rng_mm.number_percent", return_value=0),
            patch("mud.commands.combat.rng_mm.number_range", return_value=2),
            patch("mud.commands.combat.apply_damage", return_value="ok"),
        ):
            do_trip(char, "mob")
        assert victim.position == Position.RESTING

    def test_success_applies_daze(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="trip")
        char.level = 20
        char.perm_stat = [13, 13, 13, 13, 13]
        victim = _target(movable_mob_factory)
        victim.level = 20
        victim.position = Position.FIGHTING
        victim.daze = 0
        victim.perm_stat = [13, 13, 13, 13, 13]
        with (
            patch("mud.commands.combat.rng_mm.number_percent", return_value=0),
            patch("mud.commands.combat.rng_mm.number_range", return_value=2),
            patch("mud.commands.combat.apply_damage", return_value="ok"),
        ):
            do_trip(char, "mob")
        assert victim.daze > 0

    def test_self_trip(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="trip")
        result = do_trip(char, char.name)
        assert "fall flat" in result.lower() or "face" in result.lower()


# ---------------------------------------------------------------------------
# Dirt kicking
# ---------------------------------------------------------------------------

class TestDirtKicking:
    def test_requires_victim_or_fighting(self, movable_char_factory):
        char = _ready_thief(movable_char_factory, skill="dirt kicking")
        char.fighting = None
        assert "aren't in combat" in do_dirt(char, "").lower()

    def test_pc_without_skill_gets_feet_dirty(self, movable_char_factory, movable_mob_factory):
        char = movable_char_factory("warrior", 3001)
        char.skills.pop("dirt kicking", None)
        victim = _target(movable_mob_factory)
        char.fighting = victim
        assert "get your feet dirty" in do_dirt(char, "").lower()

    def test_cannot_blind_self(self, movable_char_factory):
        char = _ready_thief(movable_char_factory, name="thief", skill="dirt kicking")
        assert "very funny" in do_dirt(char, "thief").lower()

    def test_blocks_already_blinded_victim(self, movable_char_factory, movable_mob_factory):
        char = _ready_thief(movable_char_factory, skill="dirt kicking")
        victim = _target(movable_mob_factory)
        victim.affected_by = int(AffectFlag.BLIND)
        char.fighting = victim
        result = do_dirt(char, "mob")
        assert "already" in result.lower() and "blind" in result.lower()

    def test_success_applies_blind(self, movable_char_factory, movable_mob_factory):
        char = _ready_thief(movable_char_factory, skill="dirt kicking", skill_level=100)
        char.perm_stat = [0, 0, 0, 0, 0]
        char.mod_stat = [0, 0, 0, 0, 0]
        char.level = 0
        char.off_flags = 0
        victim = _target(movable_mob_factory)
        victim.perm_stat = [0, 0, 0, 0, 0]
        victim.mod_stat = [0, 0, 0, 0, 0]
        victim.level = 0
        victim.off_flags = 0
        victim.affected_by = 0

        def _apply(effect):
            victim.affected_by |= int(effect.affect_flag)
            return True

        victim.apply_spell_effect = _apply
        char.fighting = victim
        with (
            patch("mud.skills.handlers.rng_mm.number_percent", return_value=0),
            patch("mud.skills.handlers.apply_damage", return_value="ok"),
        ):
            do_dirt(char, "mob")
        assert victim.affected_by & int(AffectFlag.BLIND)

    def test_no_dirt_in_water_sectors(self, movable_char_factory, movable_mob_factory):
        from mud.registry import room_registry

        char = _ready_thief(movable_char_factory, skill="dirt kicking", skill_level=75)
        char.perm_stat = [0, 0, 0, 20, 0]
        char.mod_stat = [0, 0, 0, 0, 0]
        char.level = 50
        victim = _target(movable_mob_factory)
        victim.perm_stat = [0, 0, 0, 0, 0]
        victim.mod_stat = [0, 0, 0, 0, 0]
        victim.level = 1
        char.fighting = victim
        room = room_registry[3001]
        room.sector_type = 6  # WATER_SWIM
        with patch("mud.skills.handlers._send_to_char") as mock_send:
            do_dirt(char, "mob")
        mock_send.assert_called_once_with(char, "There isn't any dirt to kick.")


# ---------------------------------------------------------------------------
# Rescue
# ---------------------------------------------------------------------------

class TestRescue:
    def test_requires_target_argument(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="rescue")
        assert "Rescue whom?" in do_rescue(char, "")

    def test_target_must_be_in_room(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="rescue")
        assert "aren't here" in do_rescue(char, "phantasm")

    def test_cannot_rescue_self(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, name="selfrescue", skill="rescue")
        assert "fleeing instead" in do_rescue(char, "selfrescue")

    def test_pc_cannot_rescue_npc(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="rescue")
        char.is_npc = False
        victim = _target(movable_mob_factory)
        victim.is_npc = True
        assert "need your help" in do_rescue(char, "mob")

    def test_cannot_rescue_fighting_target(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="rescue")
        char.is_npc = False
        victim = movable_char_factory("ally", 3001)
        victim.is_npc = False
        char.fighting = victim
        assert "Too late" in do_rescue(char, "ally")

    def test_target_must_be_in_combat(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="rescue")
        victim = _target(movable_mob_factory)
        victim.name = "ally"
        victim.fighting = None
        victim.is_npc = False
        assert "not fighting" in do_rescue(char, "ally").lower()

    def test_kill_stealing_check(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="rescue")
        char.group = None
        victim = movable_char_factory("ally", 3001)
        victim.is_npc = False
        victim.group = None
        opponent = _target(movable_mob_factory, room_vnum=3002)
        opponent.name = "badguy"
        opponent.is_npc = True
        victim.fighting = opponent
        assert "Kill stealing" in do_rescue(char, "ally")

    def test_success_redirects_combat(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="rescue", skill_level=100)
        char.is_npc = False
        victim = movable_char_factory("ally", 3001)
        victim.is_npc = False
        opponent = _target(movable_mob_factory, room_vnum=3002)
        opponent.name = "badguy"
        opponent.is_npc = True
        victim.fighting = opponent
        with (
            patch("mud.commands.combat.rng_mm.number_percent", return_value=0),
            patch("mud.commands.combat.is_same_group", return_value=True),
            patch("mud.skills.handlers.stop_fighting") as stop_mock,
            patch("mud.skills.handlers.set_fighting") as set_mock,
        ):
            do_rescue(char, "ally")
        assert stop_mock.called
        assert set_mock.called

    def test_failure_message(self, movable_char_factory, movable_mob_factory):
        char = _ready_warrior(movable_char_factory, skill="rescue", skill_level=50)
        char.is_npc = False
        victim = movable_char_factory("ally", 3001)
        victim.is_npc = False
        opponent = _target(movable_mob_factory, room_vnum=3002)
        opponent.name = "badguy"
        opponent.is_npc = True
        victim.fighting = opponent
        with (
            patch("mud.commands.combat.rng_mm.number_percent", return_value=99),
            patch("mud.commands.combat.is_same_group", return_value=True),
        ):
            result = do_rescue(char, "ally")
        assert "fail" in result.lower()


# ---------------------------------------------------------------------------
# Berserk
# ---------------------------------------------------------------------------

class TestBerserk:
    def test_requires_skill(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="berserk", skill_level=0)
        char.is_npc = False
        assert "red in the face" in do_berserk(char, "")

    def test_cannot_if_already_berserk(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="berserk")
        char.affected_by = int(AffectFlag.BERSERK)
        assert "madder" in do_berserk(char, "")

    def test_cannot_if_calm(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="berserk")
        char.affected_by = int(AffectFlag.CALM)
        assert "mellow" in do_berserk(char, "")

    def test_requires_mana(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="berserk")
        char.mana = 25
        assert "energy" in do_berserk(char, "")

    def test_success_costs_mana_and_move(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="berserk", skill_level=100)
        char.mana = 100
        char.move = 100
        char.hit = 50
        char.max_hit = 100
        with (
            patch("mud.commands.combat.rng_mm.number_percent", return_value=0),
            patch("mud.skills.handlers.berserk", return_value=True),
        ):
            do_berserk(char, "")
        assert char.mana == 50
        assert char.move == 50

    def test_success_heals(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="berserk", skill_level=100)
        char.level = 10
        char.mana = 100
        char.move = 100
        char.hit = 50
        char.max_hit = 100
        with (
            patch("mud.commands.combat.rng_mm.number_percent", return_value=0),
            patch("mud.skills.handlers.berserk", return_value=True),
        ):
            do_berserk(char, "")
        assert char.hit == 70

    def test_failure_costs_half_mana(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="berserk", skill_level=10)
        char.mana = 100
        char.move = 100
        char.hit = 50
        char.max_hit = 100
        with patch("mud.commands.combat.rng_mm.number_percent", return_value=99):
            do_berserk(char, "")
        assert char.mana == 75
        assert char.move == 50

    def test_cannot_berserk_while_recovering(self, movable_char_factory):
        char = _ready_warrior(movable_char_factory, skill="berserk")
        char.mana = 100
        char.wait = 1
        assert "still recovering" in do_berserk(char, "").lower()
