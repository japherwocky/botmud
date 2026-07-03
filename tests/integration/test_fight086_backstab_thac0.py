"""FIGHT-086 — backstab applies ROM's THAC0 bonus (near-auto-hit below skill 100).

ROM one_hit (src/fight.c:474-475):

    if (dt == gsn_backstab)
        thac0 -= 10 * (100 - get_skill (ch, gsn_backstab));

A backstab below skill 100 subtracts a large amount from THAC0 (10 per missing
skill point), making the strike a near-guaranteed hit. The Python port ported
the backstab *damage* multiplier but not this THAC0 branch, so sub-100
backstabs missed far more often than ROM. This test locks the branch by
constructing a diceroll at which a *normal* attack misses but a backstab lands.
"""

from __future__ import annotations

import pytest

from mud.combat import engine as combat_engine
from mud.combat.engine import _backstab_skill
from mud.models.constants import ActFlag
from mud.world import create_test_character, initialize_world


def test_backstab_thac0_bonus_hits_where_normal_misses(monkeypatch: pytest.MonkeyPatch) -> None:
    initialize_world("area/area.lst")
    attacker = create_test_character("Backstabber", 3001)
    victim = create_test_character("Victim", 3001)
    victim.is_npc = True
    attacker.is_npc = False
    attacker.ch_class = 3
    attacker.level = 10
    attacker.hitroll = 0
    attacker.skills["backstab"] = 50
    victim.hit = 100
    victim.max_hit = 100

    # With this setup: th=15, victim_ac=10 → normal miss when diceroll < 5.
    # Backstab subtracts 10*(100-50)=500 from THAC0, so it hits for any diceroll.
    # ROM src/fight.c:510 — miss if diceroll==0 or (diceroll!=19 and diceroll < th-ac).
    monkeypatch.setattr("mud.utils.rng_mm.number_bits", lambda *_: 4)

    # Normal attack at diceroll 4 misses (validates the setup is discriminating).
    victim.hit = 100
    combat_engine.attack_round(attacker, victim, dt=None)
    assert victim.hit == 100, "normal attack should miss at this diceroll"

    # Same diceroll, backstab: the THAC0 bonus makes it land.
    victim.hit = 100
    attacker.fighting = None
    combat_engine.attack_round(attacker, victim, dt="backstab")
    assert victim.hit < 100, "backstab THAC0 bonus should turn the miss into a hit"


def test_backstab_skill_mirrors_rom_get_skill() -> None:
    # ROM get_skill (src/handler.c:346) for gsn_backstab:
    # PC → learned percent; NPC ACT_THIEF → 20 + 2*level; other NPC → 0.
    pc = create_test_character("Thief", 3001)
    pc.is_npc = False
    pc.skills["backstab"] = 73
    assert _backstab_skill(pc) == 73

    npc_thief = create_test_character("Cutpurse", 3001)
    npc_thief.is_npc = True
    npc_thief.level = 15
    npc_thief.act = int(ActFlag.THIEF)
    assert _backstab_skill(npc_thief) == 20 + 2 * 15

    npc_plain = create_test_character("Rat", 3001)
    npc_plain.is_npc = True
    npc_plain.level = 15
    npc_plain.act = 0
    assert _backstab_skill(npc_plain) == 0
