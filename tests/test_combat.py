from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from mud.combat import engine as combat_engine
from mud.commands import process_command
from mud.config import get_pulse_violence
from mud.models.character import Character
from mud.models.constants import (
    AC_BASH,
    AC_EXOTIC,
    AC_PIERCE,
    AC_SLASH,
    WEAPON_POISON,
    AffectFlag,
    DamageType,
    DefenseBit,
    ImmFlag,
    PlayerFlag,
    Position,
    RoomFlag,
    VulnFlag,
    WeaponType,
    WearLocation,
    attack_lookup,
)
from mud.models.room import Room
from mud.skills import load_skills, skill_registry
from mud.utils import rng_mm
from mud.world import create_test_character, initialize_world

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def setup_combat() -> tuple[Character, Character]:
    initialize_world("area/area.lst")
    room_vnum = 3001
    attacker = create_test_character("Attacker", room_vnum)
    attacker.skills["hand to hand"] = 100
    victim = create_test_character("Victim", room_vnum)
    victim.is_npc = True
    return attacker, victim


def assert_attack_message(message: str, victim_name: str = "Victim") -> None:
    assert message.startswith("{2")
    assert victim_name in message
    assert message.endswith("{x")


def deliver_kill(char: Character, target: str) -> str:
    """Run ``kill <target>`` and return the attacker-facing combat line."""
    before = len(char.messages)
    process_command(char, f"kill {target}")
    pushed = char.messages[before:]
    return pushed[0] if pushed else ""


def _make_pvp_pair(monkeypatch, *, victim_name="Duelist", victim_hit=50):
    """Create attacker/victim PVP pair with deterministic RNG."""
    initialize_world("area/area.lst")
    attacker = create_test_character("Attacker", 3001)
    victim = create_test_character(victim_name, 3001)
    attacker.desc = object()
    victim.desc = object()
    attacker.clan = 1
    victim.clan = 1
    attacker.skills["hand to hand"] = 100
    attacker.hitroll = 100
    victim.hit = victim_hit
    victim.max_hit = victim_hit
    monkeypatch.setattr("mud.utils.rng_mm.number_percent", lambda: 1)
    monkeypatch.setattr("mud.utils.rng_mm.number_range", lambda low, high: low)
    return attacker, victim


def _reset_fight(char, target):
    """Reset combat state so char can attack again."""
    char.position = Position.STANDING
    char.fighting = None
    target.position = Position.STANDING
    target.fighting = None


def _make_weapon(
    *,
    weapon_type=WeaponType.SWORD,
    dice_num=2,
    dice_size=6,
    attack="slash",
    flags=0,
    stats=None,
    name="practice sword",
    level=20,
):
    """Create a SimpleNamespace weapon for combat tests."""
    attack_idx = attack_lookup(attack)
    proto = SimpleNamespace(
        item_type="weapon",
        value=[int(weapon_type), dice_num, dice_size, attack_idx],
        new_format=True,
        level=level,
    )
    return SimpleNamespace(
        prototype=proto,
        value=proto.value,
        item_type="weapon",
        weapon_flags=flags,
        weapon_stats=stats or set(),
        new_format=True,
        level=level,
        name=name,
    )


def _make_multi_hit_combatants(
    monkeypatch,
    *,
    victim_hp=10,
    damroll=1,
    second_attack=False,
    third_attack=False,
    haste=False,
    slow=False,
    pin_hits=True,
):
    """Set up attacker/victim for multi_hit tests with common defaults."""
    attacker, victim = setup_combat()
    attacker.hitroll = 100
    attacker.damroll = damroll
    victim.hit = victim_hp
    victim.max_hit = victim_hp
    if second_attack:
        attacker.second_attack_skill = 100
    if third_attack:
        attacker.third_attack_skill = 100
    if haste:
        attacker.add_affect(AffectFlag.HASTE)
    if slow:
        attacker.add_affect(AffectFlag.SLOW)
    if pin_hits:
        monkeypatch.setattr("mud.utils.rng_mm.number_bits", lambda *_: 19)
    return attacker, victim


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def kick_skill():
    """Load kick skill for the duration of the test."""
    load_skills(Path("data/skills.json"))
    yield
    skill_registry.skills.clear()
    skill_registry.handlers.clear()


# ---------------------------------------------------------------------------
# Kill command tests
# ---------------------------------------------------------------------------


def test_rescue_checks_group_permission(monkeypatch):
    load_skills(Path("data/skills.json"))

    rescuer = Character(name="Rescuer", level=35, is_npc=False, skills={"rescue": 75})
    stranger = Character(name="Stranger", is_npc=False)
    foe = Character(name="Ogre", is_npc=True)

    room = Room(vnum=3001)
    for ch in (rescuer, stranger, foe):
        room.add_character(ch)

    stranger.fighting = foe
    stranger.position = Position.FIGHTING
    foe.fighting = stranger
    foe.position = Position.FIGHTING

    rescuer.wait = 0
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 1)

    out = process_command(rescuer, "rescue stranger")

    assert out == "Kill stealing is not permitted."
    assert rescuer.wait == 0
    assert rescuer.fighting is None


def test_kill_blocks_safe_room_for_npc():
    attacker, victim = setup_combat()
    attacker.room.room_flags = int(RoomFlag.ROOM_SAFE)

    out = process_command(attacker, "kill victim")

    assert out == "Not in this room."
    assert attacker.fighting is None
    assert victim.fighting is None


def test_kill_requires_clan_for_player_targets():
    initialize_world("area/area.lst")
    attacker = create_test_character("Attacker", 3001)
    victim = create_test_character("Target", 3001)

    out = process_command(attacker, "kill target")

    assert out == "Join a clan if you want to kill players."
    assert attacker.fighting is None
    assert victim.fighting is None


def test_kill_flags_player_as_killer(monkeypatch):
    attacker, victim = _make_pvp_pair(monkeypatch)

    process_command(attacker, "kill duelist")

    assert attacker.act & int(PlayerFlag.KILLER)
    assert "*** You are now a KILLER!! ***" in attacker.messages
    assert attacker.wait >= get_pulse_violence()
    assert any(m.startswith("{2") for m in attacker.messages)


def test_kill_does_not_flag_attacker_when_target_already_killer(monkeypatch):
    attacker, victim = _make_pvp_pair(monkeypatch, victim_name="Outlaw")
    victim.act = int(PlayerFlag.KILLER)

    process_command(attacker, "kill outlaw")

    assert not (int(attacker.act) & int(PlayerFlag.KILLER))
    assert "*** You are now a KILLER!! ***" not in attacker.messages


def test_kill_with_charmed_attacker_stops_following_without_killer_flag(monkeypatch):
    attacker, victim = _make_pvp_pair(monkeypatch, victim_name="Victim")
    master = create_test_character("Master", 3001)
    attacker.master = master
    attacker.add_affect(AffectFlag.CHARM)

    process_command(attacker, "kill victim")

    assert attacker.master is None
    assert not (int(attacker.act) & int(PlayerFlag.KILLER))
    assert "*** You are now a KILLER!! ***" not in attacker.messages


def test_kill_blocks_stealing_existing_fight():
    attacker, victim = setup_combat()
    ally = create_test_character("Ally", 3001)
    victim.fighting = ally
    ally.fighting = victim

    out = process_command(attacker, "kill victim")

    assert out == "Kill stealing is not permitted."
    assert attacker.fighting is None


def test_kill_blocks_charmed_player_attacking_master():
    initialize_world("area/area.lst")
    thrall = create_test_character("Thrall", 3001)
    master = create_test_character("Master", 3001)
    master.is_npc = True
    master.short_descr = "Master"

    thrall.add_affect(AffectFlag.CHARM)
    thrall.master = master

    out = process_command(thrall, "kill master")

    assert out == "Master is your beloved master."


def test_fight064_beloved_master_message_uses_pers_shortdescr_capitalized():
    """The beloved-master message renders the NPC short_descr, capitalized."""
    initialize_world("area/area.lst")
    thrall = create_test_character("Thrall", 3001)
    master = create_test_character("wizard", 3001)
    master.is_npc = True
    master.short_descr = "a dark wizard"

    thrall.add_affect(AffectFlag.CHARM)
    thrall.master = master

    out = process_command(thrall, "kill wizard")

    assert out == "A dark wizard is your beloved master.", out
    assert thrall.fighting is None
    assert master.fighting is None


# ---------------------------------------------------------------------------
# apply_damage tests
# ---------------------------------------------------------------------------


def test_apply_damage_charm_master_breaks_follow():
    """Attacking your own charmed follower breaks the follow bond."""
    from mud.combat.engine import apply_damage

    initialize_world("area/area.lst")
    attacker = create_test_character("Master", 3001)
    victim = create_test_character("Pet", 3001)
    victim.is_npc = True
    victim.hit = 200
    victim.max_hit = 200

    victim.master = attacker
    victim.leader = attacker
    victim.add_affect(AffectFlag.CHARM)

    with (
        patch("mud.combat.engine.check_parry", return_value=False),
        patch("mud.combat.engine.check_dodge", return_value=False),
        patch("mud.combat.engine.check_shield_block", return_value=False),
    ):
        apply_damage(attacker, victim, 10, int(DamageType.BASH))

    assert victim.master is None, "stop_follower must break the follow bond"


@pytest.mark.parametrize(
    "v_hp, damage, expect_hurt, expect_bleeding, expected_position",
    [
        (200, 30, True, False, Position.FIGHTING),  # big hit, healthy → HURT only
        (20, 5, False, True, Position.FIGHTING),  # small hit, low HP → BLEEDING only
        (40, 30, True, True, Position.FIGHTING),  # big hit, low HP → both
        (30, 30, False, False, Position.STUNNED),  # knocks to STUNNED → neither
    ],
)
def test_apply_damage_hurt_and_bleeding(
    v_hp,
    damage,
    expect_hurt,
    expect_bleeding,
    expected_position,
):
    """HURT/BLEEDING injury-feedback messages for non-critical positions."""
    from mud.combat.engine import apply_damage

    initialize_world("area/area.lst")

    attacker = create_test_character("Attacker", 3001)
    attacker.hit = 200
    attacker.max_hit = 200
    attacker.clan = 1

    victim = create_test_character("Victim", 3001)
    victim.is_npc = False
    victim.max_hit = 100
    victim.hit = v_hp
    victim.position = Position.FIGHTING
    victim.clan = 1
    victim.messages.clear()

    with (
        patch("mud.combat.engine.check_parry", return_value=False),
        patch("mud.combat.engine.check_dodge", return_value=False),
        patch("mud.combat.engine.check_shield_block", return_value=False),
    ):
        apply_damage(attacker, victim, damage, int(DamageType.BASH))

    assert victim.position == expected_position
    assert any("{RThat really did HURT!{x" in m for m in victim.messages) == expect_hurt
    assert any("{RYou sure are BLEEDING!{x" in m for m in victim.messages) == expect_bleeding


# ---------------------------------------------------------------------------
# Attack round / damage tests
# ---------------------------------------------------------------------------


def test_attack_damages_but_not_kill(monkeypatch):
    attacker, victim = setup_combat()
    attacker.level = 10
    attacker.skills["hand to hand"] = 100
    attacker.damroll = 3
    attacker.hitroll = 100
    victim.hit = 10
    victim.max_hit = 10
    monkeypatch.setattr("mud.utils.rng_mm.number_percent", lambda: 1)
    monkeypatch.setattr("mud.utils.rng_mm.number_range", lambda low, high: low)
    monkeypatch.setattr("mud.utils.rng_mm.number_bits", lambda *_: 19)

    out = deliver_kill(attacker, "victim")

    assert out == "{2You *** DEVASTATE *** Victim!{x"
    assert any("{4Attacker *** DEVASTATES *** you!{x" == m for m in victim.messages), (
        "DEVASTATES hit-verb must appear in victim.messages"
    )
    assert victim.hit == 2
    assert attacker.position == Position.FIGHTING
    assert victim.position == Position.FIGHTING
    assert victim in attacker.room.people


def test_attack_kills_target(monkeypatch):
    attacker, victim = setup_combat()
    attacker.level = 10
    attacker.skills["hand to hand"] = 100
    attacker.damroll = 0
    attacker.hitroll = 100
    victim.hit = 5
    victim.max_hit = 5
    monkeypatch.setattr("mud.utils.rng_mm.number_percent", lambda: 1)
    monkeypatch.setattr("mud.utils.rng_mm.number_range", lambda low, high: low)
    monkeypatch.setattr("mud.utils.rng_mm.number_bits", lambda *_: 19)

    out = deliver_kill(attacker, "victim")

    assert_attack_message(out)
    assert not any("You kill" in m for m in attacker.messages)
    assert victim.hit == 0
    assert attacker.position == Position.STANDING
    assert victim.position == Position.DEAD
    assert victim not in attacker.room.people
    assert "{RVictim is DEAD!!{x" in attacker.messages


def test_attack_misses_target(monkeypatch):
    attacker, victim = setup_combat()
    attacker.hitroll = -100
    victim.hit = 10
    monkeypatch.setattr("mud.utils.rng_mm.number_percent", lambda: 100)
    monkeypatch.setattr("mud.utils.rng_mm.number_bits", lambda *_: 0)

    out = deliver_kill(attacker, "victim")

    assert out == "{2You miss Victim.{x"
    assert victim.hit == 10
    assert attacker.position == Position.FIGHTING
    assert victim.position == Position.FIGHTING
    assert victim in attacker.room.people


def test_defense_order_and_early_out(monkeypatch):
    attacker, victim = setup_combat()
    attacker.hitroll = 100
    attacker.damroll = 3

    calls: list[str] = []

    def parry(a, v):
        calls.append("parry")
        return False

    def dodge(a, v):
        calls.append("dodge")
        return True  # early-out

    def shield(a, v):
        calls.append("shield")
        return False

    monkeypatch.setattr(combat_engine, "check_parry", parry)
    monkeypatch.setattr(combat_engine, "check_dodge", dodge)
    monkeypatch.setattr(combat_engine, "check_shield_block", shield)

    assert process_command(attacker, "kill victim") == ""
    assert calls == ["parry", "dodge"]


def test_parry_blocks_when_skill_learned(monkeypatch):
    attacker, victim = setup_combat()
    attacker.hitroll = 100
    attacker.is_npc = True
    victim.is_npc = False
    victim.ch_class = 3  # warrior learns parry at level 1
    victim.level = 1
    victim.skills["parry"] = 75
    victim.has_weapon_equipped = True

    recorded: list[tuple[Character, str, bool, int]] = []

    def fake_check_improve(ch, name, success, multiplier=1):
        recorded.append((ch, name, success, multiplier))

    monkeypatch.setattr(combat_engine, "check_improve", fake_check_improve)
    monkeypatch.setattr("mud.utils.rng_mm.number_percent", lambda: 1)

    out = deliver_kill(attacker, "victim")

    assert out == "Victim parries your attack."
    assert "You parry Attacker's attack." in victim.messages
    assert recorded == [(victim, "parry", True, 6)]


def test_shield_block_requires_shield(monkeypatch):
    attacker, victim = setup_combat()
    attacker.hitroll = 100
    attacker.damroll = 3
    victim.skills["shield block"] = 95
    victim.has_shield_equipped = False

    monkeypatch.setattr("mud.utils.rng_mm.number_percent", lambda: 1)
    monkeypatch.setattr("mud.utils.rng_mm.number_range", lambda low, high: low)

    out = deliver_kill(attacker, "victim")

    assert "blocks your attack" not in out
    assert_attack_message(out)


# ---------------------------------------------------------------------------
# Multi-hit tests
# ---------------------------------------------------------------------------


def test_multi_hit_single_attack(monkeypatch):
    attacker, victim = _make_multi_hit_combatants(monkeypatch)

    results = combat_engine.multi_hit(attacker, victim)

    assert len(results) == 1
    assert_attack_message(results[0])
    assert victim.hit == 4  # 10 - 6 = 4


def test_multi_hit_with_haste(monkeypatch):
    attacker, victim = _make_multi_hit_combatants(monkeypatch, victim_hp=20, haste=True)
    monkeypatch.setattr("mud.utils.rng_mm.number_range", lambda low, high: low)

    results = combat_engine.multi_hit(attacker, victim)

    assert len(results) == 2
    for message in results:
        assert_attack_message(message)
    assert victim.hit == 8  # 20 - (6 + 6) = 8


def test_multi_hit_second_attack(monkeypatch):
    attacker, victim = _make_multi_hit_combatants(
        monkeypatch,
        victim_hp=20,
        second_attack=True,
    )

    combat_engine.set_fighting(attacker, victim)
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 1)

    results = combat_engine.multi_hit(attacker, victim)

    assert len(results) == 2
    assert attacker.fighting == victim
    assert victim.fighting == attacker
    assert victim.hit == 8
    for message in results:
        assert_attack_message(message)


def test_multi_hit_third_attack(monkeypatch):
    attacker, victim = _make_multi_hit_combatants(
        monkeypatch,
        victim_hp=20,
        second_attack=True,
        third_attack=True,
        pin_hits=False,
    )
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 1)

    results = combat_engine.multi_hit(attacker, victim)

    assert len(results) == 3
    assert attacker.fighting == victim


def test_multi_hit_with_slow(monkeypatch):
    attacker, victim = _make_multi_hit_combatants(
        monkeypatch,
        victim_hp=10,
        second_attack=True,
        third_attack=True,
        slow=True,
    )

    results = combat_engine.multi_hit(attacker, victim)

    assert len(results) >= 1


def test_multi_hit_victim_dies_early(monkeypatch):
    attacker, victim = _make_multi_hit_combatants(
        monkeypatch,
        victim_hp=3,
        damroll=5,
        second_attack=True,
    )

    results = combat_engine.multi_hit(attacker, victim)

    assert len(results) == 1
    assert results[0] == "You kill Victim."
    assert attacker.fighting is None
    assert victim.fighting is None


# ---------------------------------------------------------------------------
# Kick command tests
# ---------------------------------------------------------------------------


def test_kick_command_requires_fighting(kick_skill):
    attacker, victim = setup_combat()
    attacker.position = int(Position.FIGHTING)
    attacker.skills["kick"] = 75
    attacker.level = 60
    attacker.max_hit = attacker.hit = 100
    victim.max_hit = victim.hit = 100

    out = process_command(attacker, "kick")

    assert out == "You aren't fighting anyone."


def test_kick_command_success(kick_skill, monkeypatch):
    attacker, victim = setup_combat()
    attacker.level = 20
    attacker.ch_class = 3  # warrior learns kick at level 8
    attacker.position = int(Position.FIGHTING)
    attacker.skills["kick"] = 75
    attacker.max_hit = attacker.hit = 100
    victim.max_hit = victim.hit = 100
    attacker.fighting = victim
    victim.fighting = attacker

    monkeypatch.setattr(rng_mm, "number_percent", lambda: 10)
    monkeypatch.setattr(rng_mm, "number_range", lambda a, b: 12)

    out = process_command(attacker, "kick")

    assert_attack_message(out)
    assert victim.hit == 88
    assert attacker.wait == 12
    assert attacker.cooldowns.get("kick") == 0


def test_kick_command_failure(kick_skill, monkeypatch):
    attacker, victim = setup_combat()
    attacker.level = 20
    attacker.ch_class = 3
    attacker.position = int(Position.FIGHTING)
    attacker.skills["kick"] = 5
    attacker.max_hit = attacker.hit = 100
    victim.max_hit = victim.hit = 100
    attacker.fighting = victim
    victim.fighting = attacker

    monkeypatch.setattr(rng_mm, "number_percent", lambda: 100)
    monkeypatch.setattr(rng_mm, "number_range", lambda a, b: 12)

    out = process_command(attacker, "kick")

    # dt=gsn_kick != TYPE_HIT, so the skill noun renders even on a miss
    assert out == "{2Your kick misses Victim.{x"
    assert victim.hit == 100
    assert attacker.wait == 12
    assert attacker.cooldowns.get("kick") == 0


def test_kick_command_requires_level(kick_skill):
    attacker, victim = setup_combat()
    attacker.is_npc = False
    attacker.ch_class = 3  # warrior table entry uses level 8
    attacker.level = 5
    attacker.position = int(Position.FIGHTING)
    attacker.fighting = victim
    victim.fighting = attacker

    out = process_command(attacker, "kick")

    assert out == "You better leave the martial arts to fighters."
    assert attacker.wait == 0
    assert "kick" not in getattr(attacker, "cooldowns", {})
    assert victim.hit == victim.max_hit


def test_kick_command_requires_off_flag(kick_skill):
    attacker, victim = setup_combat()
    attacker.is_npc = True
    attacker.off_flags = 0
    attacker.level = 20
    attacker.position = int(Position.FIGHTING)
    attacker.fighting = victim
    victim.fighting = attacker

    out = process_command(attacker, "kick")

    assert out == ""
    assert attacker.wait == 0
    assert "kick" not in getattr(attacker, "cooldowns", {})
    assert victim.hit == victim.max_hit


# ---------------------------------------------------------------------------
# Weapon tests
# ---------------------------------------------------------------------------


def test_one_hit_uses_equipped_weapon(monkeypatch):
    attacker, victim = setup_combat()
    attacker.level = 20
    attacker.damroll = 0
    attacker.hitroll = 0
    attacker.skills["sword"] = 100
    victim.hit = 100
    victim.max_hit = 100

    weapon = _make_weapon(dice_size=6, attack="slash")
    attacker.equipment[int(WearLocation.WIELD)] = weapon

    monkeypatch.setattr("mud.utils.rng_mm.number_percent", lambda: 1)
    monkeypatch.setattr("mud.utils.rng_mm.dice", lambda number, size: number * size)
    monkeypatch.setattr("mud.utils.rng_mm.number_range", lambda low, high: low)
    monkeypatch.setattr("mud.utils.rng_mm.number_bits", lambda *_: 19)

    out = deliver_kill(attacker, "victim")

    assert_attack_message(out)
    assert victim.hit == 85


def test_sharp_weapon_doubles_damage_on_proc(monkeypatch):
    attacker, victim = setup_combat()
    attacker.level = 30
    attacker.damroll = 0
    attacker.hitroll = 100
    attacker.has_shield_equipped = True
    attacker.enhanced_damage_skill = 0
    attacker.skills["sword"] = 100
    victim.position = Position.FIGHTING

    weapon = _make_weapon(dice_size=4, name="razorblade", level=30)
    attacker.equipment[int(WearLocation.WIELD)] = weapon

    monkeypatch.setattr(rng_mm, "dice", lambda number, size: number * size)
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 10)

    base_damage = combat_engine.calculate_weapon_damage(
        attacker,
        victim,
        int(DamageType.SLASH),
        wield=weapon,
        skill=120,
    )

    weapon.weapon_stats = {"sharp"}

    sharp_damage = combat_engine.calculate_weapon_damage(
        attacker,
        victim,
        int(DamageType.SLASH),
        wield=weapon,
        skill=120,
    )

    expected_bonus = (base_damage * 2 * 10) // 100
    assert sharp_damage == base_damage * 2 + expected_bonus


def test_poison_weapon_applies_affect(monkeypatch):
    attacker, victim = setup_combat()
    attacker.hitroll = 100
    attacker.damroll = 0
    attacker.enhanced_damage_skill = 0
    victim.hit = 100
    victim.max_hit = 100
    victim.armor = [0, 0, 0, 0]

    weapon = _make_weapon(dice_size=4, flags=int(WEAPON_POISON), name="Viperblade")
    attacker.equipment[int(WearLocation.WIELD)] = weapon
    victim.messages.clear()

    monkeypatch.setattr(rng_mm, "dice", lambda number, size: number * size)
    monkeypatch.setattr(rng_mm, "number_range", lambda low, high: low)
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 1)
    monkeypatch.setattr(combat_engine, "saves_spell", lambda *args, **kwargs: False)
    monkeypatch.setattr(rng_mm, "number_bits", lambda *_: 19)

    combat_engine.attack_round(attacker, victim)

    assert victim.has_affect(AffectFlag.POISON)
    assert any("poison" in msg.lower() for msg in victim.messages)


# ---------------------------------------------------------------------------
# AC / miscellaneous tests
# ---------------------------------------------------------------------------


def test_ac_mapping_and_sign_semantics():
    # Mapping: NONE/unarmed→BASH, BASH→BASH, PIERCE→PIERCE, SLASH→SLASH, FIRE→EXOTIC
    assert combat_engine.ac_index_for_dam_type(DamageType.NONE) == AC_BASH
    assert combat_engine.ac_index_for_dam_type(DamageType.BASH) == AC_BASH
    assert combat_engine.ac_index_for_dam_type(DamageType.PIERCE) == AC_PIERCE
    assert combat_engine.ac_index_for_dam_type(DamageType.SLASH) == AC_SLASH
    assert combat_engine.ac_index_for_dam_type(DamageType.FIRE) == AC_EXOTIC

    # AC is better when more negative
    assert combat_engine.is_better_ac(-10, -5)
    assert combat_engine.is_better_ac(-1, 5)
    assert not combat_engine.is_better_ac(5, 0)


def test_ac_influences_hit_chance(monkeypatch):
    attacker, victim = setup_combat()
    attacker.hitroll = 10
    attacker.damroll = 3
    attacker.dam_type = int(DamageType.BASH)

    monkeypatch.setattr("mud.utils.rng_mm.number_bits", lambda bits: 10)

    # Positive AC (worse defence) → hit lands
    victim.armor = [200, 200, 200, 200]
    victim.hit = 50
    out = deliver_kill(attacker, "victim")
    assert_attack_message(out)

    _reset_fight(attacker, victim)

    # Strongly negative AC (better defence) → same roll misses
    victim.hit = 50
    victim.armor = [-200, -200, -200, -200]
    out = deliver_kill(attacker, "victim")
    assert out == "{2Your slice misses Victim.{x"


def test_visibility_and_position_modifiers(monkeypatch):
    attacker, victim = setup_combat()
    attacker.hitroll = 10
    attacker.damroll = 3
    attacker.dam_type = int(DamageType.BASH)
    victim.armor = [0, 0, 0, 0]
    victim.hit = 50

    # Baseline: roll 60 → hit
    monkeypatch.setattr("mud.utils.rng_mm.number_percent", lambda: 60)
    out = deliver_kill(attacker, "victim")
    assert_attack_message(out)

    _reset_fight(attacker, victim)

    # Invisible victim → not findable by kill command
    victim.hit = 50
    victim.add_affect(AffectFlag.INVISIBLE)
    out = process_command(attacker, "kill victim")
    assert out == "They aren't here."

    _reset_fight(attacker, victim)

    # Sleeping target → easier to hit
    victim.hit = 50
    victim.remove_affect(AffectFlag.INVISIBLE)
    monkeypatch.setattr("mud.utils.rng_mm.number_percent", lambda: 62)
    victim.position = Position.SLEEPING
    out = deliver_kill(attacker, "victim")
    assert_attack_message(out)


def test_riv_scaling_applies_before_side_effects(monkeypatch):
    attacker, victim = setup_combat()
    attacker.hitroll = 100
    attacker.damroll = 0
    attacker.dam_type = 0
    victim.hit = 50

    captured: list[int] = []

    def on_hit(a, v, d):
        captured.append(d)

    monkeypatch.setattr(combat_engine, "on_hit_effects", on_hit)
    monkeypatch.setattr("mud.utils.rng_mm.number_bits", lambda *_: 19)

    # Resistant: actual hit damage = 5 - 5//3 = 4; on_hit_effects sees pre-RIV = 5
    victim.res_flags = int(DefenseBit.BASH)
    out = combat_engine.attack_round(attacker, victim)
    assert_attack_message(out)
    assert len(captured) == 1
    assert captured[0] > 0
    assert captured[-1] == 5

    # Vulnerable: actual hit damage = 5 + 5//2 = 7; on_hit_effects sees pre-RIV = 5
    victim.hit = 50
    victim.res_flags = 0
    victim.vuln_flags = int(VulnFlag.BASH)
    out = combat_engine.attack_round(attacker, victim)
    assert_attack_message(out)
    assert captured[-1] == 5

    # Immune: apply_damage returns early, but on_hit_effects fires before apply_damage
    victim.hit = 50
    victim.vuln_flags = 0
    victim.imm_flags = int(ImmFlag.BASH)
    out = combat_engine.attack_round(attacker, victim)
    assert out == "{2Victim is unaffected by your attack!{x"
    assert captured[-1] == 5
