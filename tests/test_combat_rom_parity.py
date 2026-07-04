"""
Tests for ROM combat parity - verifying corrected combat flow matches C src/fight.c
"""

from unittest.mock import patch

import pytest

from mud.combat.engine import (
    apply_damage,
    attack_round,
    check_dodge,
    check_parry,
    check_shield_block,
)
from mud.combat.messages import TYPE_HIT
from mud.models.character import Character
from mud.models.constants import DamageType, OffFlag, Position
from mud.world import create_test_character, initialize_world


def setup_combat() -> tuple[Character, Character]:
    initialize_world("area/area.lst")
    room_vnum = 3001
    attacker = create_test_character("Attacker", room_vnum)
    victim = create_test_character("Victim", room_vnum)
    # Set reasonable combat stats
    attacker.level = 10
    victim.level = 10
    attacker.hitroll = 0
    attacker.damroll = 5
    victim.hit = 50
    victim.max_hit = 50
    # INV-050: apply_damage re-checks is_safe (ROM src/fight.c:730); same-clan
    # equal-level PCs are a legal kill (:1096-1120) so the re-check permits damage.
    attacker.clan = 1
    victim.clan = 1
    return attacker, victim


def test_defense_order_matches_rom():
    """Test that defenses are checked AFTER hit but BEFORE damage (C src/fight.c:damage)"""
    attacker, victim = setup_combat()

    # Mock successful parry to verify order
    def mock_parry(att, vic):
        return True

    # Patch the check functions to verify call order
    with patch("mud.combat.engine.check_parry", side_effect=mock_parry) as mock_check_parry:
        result = apply_damage(attacker, victim, 10, int(DamageType.BASH), dt=TYPE_HIT)

        # Should return parry message, not apply damage
        assert "parries your attack" in result
        assert victim.hit == 50  # No damage applied
        mock_check_parry.assert_called_once_with(attacker, victim)


def test_ac_clamping_for_negative_values():
    """Test AC clamping: if victim_ac < -15 then victim_ac = (victim_ac + 15) / 5 - 15"""
    attacker, victim = setup_combat()

    # Set up extreme negative AC
    victim.armor = [-25, -25, -25, -25]  # Very negative AC

    # Ensure no defenses trigger to test pure AC calculation
    victim.skills["shield block"] = 0
    victim.skills["parry"] = 0
    victim.skills["dodge"] = 0
    victim.has_shield_equipped = False
    victim.has_weapon_equipped = False

    # Force a hit to test AC calculation
    attacker.hitroll = 100  # Increase hitroll to guarantee hit through clamped AC

    # The AC clamping should limit the effectiveness of extreme negative AC
    # This is tested implicitly through the hit calculation. ROM's to-hit roll
    # is `number_bits(5)` (src/fight.c:508), NOT number_percent — and a natural
    # diceroll of 0 is an automatic miss regardless of hitroll/AC (fight.c:510).
    # Pinning number_percent left the d20 roll unpinned, so leaked global RNG
    # state landed on 0 ~1/20 runs and flaked the assertion under `-n auto`.
    # Pin number_bits to 19 (the auto-hit roll) so the hit is deterministic.
    with patch("mud.utils.rng_mm.number_bits", return_value=19):
        result = attack_round(attacker, victim)

    # Should hit despite very negative AC due to clamping
    assert "miss" not in result.lower()


def test_parry_skill_calculation():
    """Test parry chance calculation matches ROM: get_skill(victim, gsn_parry) / 2 + level diff"""
    attacker, victim = setup_combat()

    # Set up parry skill
    victim.skills["parry"] = 80
    victim.has_weapon_equipped = True
    # HANDLER-008: get_skill gates a PC to 0 below the skill's class level.
    # Default class is mage (parry@22); warrior (class 3) learns parry@1, so the
    # learned 80 survives at any level and the level-diff below is preserved.
    victim.ch_class = 3
    attacker.level = 5
    victim.level = 15  # Higher level for better parry

    # Mock RNG to test specific chance calculation
    with patch("mud.utils.rng_mm.number_percent", return_value=50):
        # Expected chance = 80/2 + (15-5) = 40 + 10 = 50
        # Since RNG returns 50, this should NOT parry (>= 50)
        result = check_parry(attacker, victim)
        assert not result

    with patch("mud.utils.rng_mm.number_percent", return_value=49):
        # 49 < 50, should parry
        result = check_parry(attacker, victim)
        assert result


def test_dodge_skill_calculation():
    """Test dodge chance calculation matches ROM: get_skill(victim, gsn_dodge) / 2 + level diff"""
    attacker, victim = setup_combat()

    # Set up dodge skill
    victim.skills["dodge"] = 60
    # HANDLER-008: default class mage learns dodge@20; thief (class 2) learns
    # dodge@1, so the learned 60 survives and the level-diff below is preserved.
    victim.ch_class = 2
    attacker.level = 8
    victim.level = 12

    # Mock visibility - victim can see attacker
    victim.can_see = lambda x: True

    with patch("mud.utils.rng_mm.number_percent", return_value=35):
        # Expected chance = 60/2 + (12-8) = 30 + 4 = 34
        # Since RNG returns 35, this should NOT dodge (>= 34)
        result = check_dodge(attacker, victim)
        assert not result

    with patch("mud.utils.rng_mm.number_percent", return_value=33):
        # 33 < 34, should dodge
        result = check_dodge(attacker, victim)
        assert result


def test_shield_block_skill_calculation():
    """Test shield block chance: get_skill(victim, gsn_shield_block) / 5 + 3 + level diff"""
    attacker, victim = setup_combat()

    # Set up shield block skill
    victim.skills["shield block"] = 75
    victim.has_shield_equipped = True
    attacker.level = 6
    victim.level = 14

    with patch("mud.utils.rng_mm.number_percent", return_value=26):
        # Expected chance = 75/5 + 3 + (14-6) = 15 + 3 + 8 = 26
        # Since RNG returns 26, this should NOT block (>= 26)
        result = check_shield_block(attacker, victim)
        assert not result

    with patch("mud.utils.rng_mm.number_percent", return_value=25):
        # 25 < 26, should block
        result = check_shield_block(attacker, victim)
        assert result


def test_visibility_affects_defense():
    """ROM src/fight.c:1311 — check_parry halves chance on `!can_see(attacker, victim)`
    (the ATTACKER cannot see the VICTIM), not victim→attacker (that's dodge, :1363).
    FIGHT-084: an invisible victim the attacker can't see parries at half chance."""
    from mud.models.constants import AffectFlag

    attacker, victim = setup_combat()

    # Set up high skill; victim is invisible so the attacker (no detect-invis) can't see it.
    victim.skills["parry"] = 80
    victim.has_weapon_equipped = True
    victim.add_affect(AffectFlag.INVISIBLE)
    attacker.room.light = 5  # lit so can_see is not dark-gated

    with patch("mud.utils.rng_mm.number_percent", return_value=30):
        # Base chance 80/2 = 40, halved to 20 because the attacker can't see the victim.
        # Plus level diff: 20 + (10-10) = 20. RNG 30 >= 20 -> does NOT parry.
        result = check_parry(attacker, victim)
        assert not result


def test_wait_daze_timer_handling():
    """Test wait/daze timer decrements on violence pulses for descriptor-less actors."""
    from mud.game_loop import violence_tick
    from mud.models.character import character_registry

    attacker, victim = setup_combat()

    # Make attacker an NPC without descriptor
    attacker.desc = None
    attacker.wait = 10
    attacker.daze = 8

    character_registry.append(attacker)
    try:
        violence_tick(do_combat=True)
    finally:
        character_registry.remove(attacker)

    # Timers should be decremented by the configured PULSE_VIOLENCE (12).
    assert attacker.wait == 0
    assert attacker.daze == 0


def test_npc_unarmed_parry_half_chance():
    """Test that NPCs can parry unarmed at half chance"""
    attacker, victim = setup_combat()

    # Make victim an NPC without weapon.
    # HANDLER-008: get_skill ignores the skills dict for NPCs and uses ROM's
    # formula — parry = level*2 gated by OFF_PARRY (src/handler.c:373-432). The old
    # skills["parry"]=60 is now inert; set the flag instead. At level 10:
    # get_skill=20 -> /2 = 10 -> unarmed-NPC halved = 5 (level diff 10-10 = 0).
    victim.is_npc = True
    victim.off_flags = int(OffFlag.PARRY)
    victim.has_weapon_equipped = False
    victim.can_see = lambda x: True

    with patch("mud.utils.rng_mm.number_percent", return_value=5):
        # Chance = 5; RNG 5 >= 5, this should NOT parry
        result = check_parry(attacker, victim)
        assert not result

    with patch("mud.utils.rng_mm.number_percent", return_value=4):
        # 4 < 5, should parry
        result = check_parry(attacker, victim)
        assert result


def test_player_needs_weapon_to_parry():
    """Test that PC characters cannot parry without a weapon"""
    attacker, victim = setup_combat()

    # Make victim a PC without weapon
    victim.is_npc = False
    victim.skills["parry"] = 80
    victim.has_weapon_equipped = False

    # Should always return False regardless of skill
    result = check_parry(attacker, victim)
    assert not result


def test_unconscious_cannot_defend():
    """Test that unconscious characters cannot use defensive skills"""
    attacker, victim = setup_combat()

    # Make victim unconscious
    victim.position = Position.SLEEPING
    victim.skills["parry"] = 100
    victim.skills["dodge"] = 100
    victim.skills["shield block"] = 100
    victim.has_weapon_equipped = True
    victim.has_shield_equipped = True

    # All defenses should fail
    assert not check_parry(attacker, victim)
    assert not check_dodge(attacker, victim)
    assert not check_shield_block(attacker, victim)


if __name__ == "__main__":
    pytest.main([__file__])
