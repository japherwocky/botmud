"""HANDLER-008 — unit tests for the faithful ROM ``get_skill`` port.

Mirrors src/handler.c:346-448. Uses ``Character`` directly (no world needed).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mud.math.c_compat import c_div
from mud.models.character import Character, PCData
from mud.models.constants import ActFlag, OffFlag
from mud.skills.registry import SkillRegistry, skill_registry
from mud.skills.skill_lookup import get_skill


@pytest.fixture(autouse=True)
def _load_skills() -> None:
    # get_skill reads the module-level skill_registry for type/levels.
    skill_registry.load(Path("data/skills.json"))


# --- PC path -----------------------------------------------------------------


def test_pc_returns_learned_percent_when_level_meets_class_gate() -> None:
    reg = SkillRegistry()
    reg.load(Path("data/skills.json"))
    kick = reg.get("kick")
    ch_class = 3  # warrior
    req = int(kick.levels[ch_class])
    pc = Character(is_npc=False, level=req + 10, ch_class=ch_class, skills={"kick": 75})
    assert get_skill(pc, "kick") == 75


def test_pc_gated_to_zero_below_class_skill_level() -> None:
    reg = SkillRegistry()
    reg.load(Path("data/skills.json"))
    kick = reg.get("kick")
    ch_class = 0  # mage — high kick requirement
    req = int(kick.levels[ch_class])
    pc = Character(is_npc=False, level=max(1, req - 1), ch_class=ch_class, skills={"kick": 75})
    assert get_skill(pc, "kick") == 0


# --- NPC formula dispatch ----------------------------------------------------


def test_npc_spell_is_40_plus_2_level() -> None:
    npc = Character(is_npc=True, level=10)
    assert get_skill(npc, "acid blast") == 40 + 2 * 10  # acid blast is a spell


def test_npc_kick_is_10_plus_3_level() -> None:
    npc = Character(is_npc=True, level=20)
    assert get_skill(npc, "kick") == min(100, 10 + 3 * 20)


def test_npc_hand_to_hand_is_40_plus_2_level() -> None:
    npc = Character(is_npc=True, level=15)
    assert get_skill(npc, "hand to hand") == 40 + 2 * 15


def test_npc_backstab_requires_act_thief() -> None:
    thief = Character(is_npc=True, level=10, act=int(ActFlag.THIEF))
    plain = Character(is_npc=True, level=10, act=0)
    assert get_skill(thief, "backstab") == 20 + 2 * 10
    assert get_skill(plain, "backstab") == 0


def test_npc_dodge_requires_off_dodge() -> None:
    dodger = Character(is_npc=True, level=20, off_flags=int(OffFlag.DODGE))
    plain = Character(is_npc=True, level=20, off_flags=0)
    assert get_skill(dodger, "dodge") == 20 * 2
    assert get_skill(plain, "dodge") == 0


def test_npc_disarm_via_warrior_or_off_disarm() -> None:
    warrior = Character(is_npc=True, level=10, act=int(ActFlag.WARRIOR))
    off = Character(is_npc=True, level=10, off_flags=int(OffFlag.DISARM))
    plain = Character(is_npc=True, level=10)
    assert get_skill(warrior, "disarm") == 20 + 3 * 10
    assert get_skill(off, "disarm") == 20 + 3 * 10
    assert get_skill(plain, "disarm") == 0


def test_npc_weapon_skill_is_40_plus_5_level_over_2() -> None:
    npc = Character(is_npc=True, level=10)
    assert get_skill(npc, "sword") == 40 + c_div(5 * 10, 2)  # 40 + 25 = 65


def test_npc_third_attack_negative_clamps_to_zero() -> None:
    # 4*level - 40 is negative below level 10; URANGE clamps to 0.
    npc = Character(is_npc=True, level=5, act=int(ActFlag.WARRIOR))
    assert get_skill(npc, "third attack") == 0


def test_npc_unknown_skill_is_zero() -> None:
    npc = Character(is_npc=True, level=30)
    assert get_skill(npc, "nonexistent skill") == 0


def test_npc_value_clamped_to_100() -> None:
    npc = Character(is_npc=True, level=50)  # hand to hand = 40 + 100 = 140
    assert get_skill(npc, "hand to hand") == 100


# --- daze / drunk modifiers --------------------------------------------------


def test_daze_reduces_skill_by_two_thirds() -> None:
    npc = Character(is_npc=True, level=10, daze=5)  # kick base 40
    assert get_skill(npc, "kick") == c_div(2 * 40, 3)  # 26


def test_daze_halves_a_spell() -> None:
    npc = Character(is_npc=True, level=10, daze=5)  # acid blast base 60
    assert get_skill(npc, "acid blast") == c_div(60, 2)  # 30


def test_drunk_pc_reduced_by_nine_tenths() -> None:
    reg = SkillRegistry()
    reg.load(Path("data/skills.json"))
    kick = reg.get("kick")
    ch_class = 3
    pc = Character(
        is_npc=False,
        level=int(kick.levels[ch_class]) + 10,
        ch_class=ch_class,
        skills={"kick": 80},
    )
    pc.pcdata = PCData(condition=[15, 48, 48, 48])  # COND_DRUNK = 15 > 10
    assert get_skill(pc, "kick") == c_div(9 * 80, 10)  # 72


def test_drunk_below_threshold_is_not_reduced() -> None:
    reg = SkillRegistry()
    reg.load(Path("data/skills.json"))
    kick = reg.get("kick")
    ch_class = 3
    pc = Character(
        is_npc=False,
        level=int(kick.levels[ch_class]) + 10,
        ch_class=ch_class,
        skills={"kick": 80},
    )
    pc.pcdata = PCData(condition=[10, 48, 48, 48])  # exactly 10 — not > 10
    assert get_skill(pc, "kick") == 80
