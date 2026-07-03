"""FIGHT-085 — skill wait-states use raw beats, not haste/slow-scaled.

ROM's WAIT_STATE macro (src/merc.h:2116) is a bare UMAX:

    #define WAIT_STATE(ch, npulse) ((ch)->wait = UMAX((ch)->wait, (npulse)))

Every skill applies its raw ``skill_table[sn].beats`` (e.g. do_kick at
src/fight.c:3126, do_bash at :2469, do_backstab at :2952, do_rescue at
:3081). Haste/slow never scale a skill's wait-state in ROM — they affect the
number of attacks via multi_hit, not lag. The Python port erroneously halved
lag under AFF_HASTE and doubled it under AFF_SLOW in
``SkillRegistry._compute_skill_lag``; this test locks the raw-beats contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mud.models.character import Character
from mud.models.constants import AffectFlag
from mud.skills.registry import SkillRegistry
from mud.utils import rng_mm


def _registry() -> SkillRegistry:
    reg = SkillRegistry()
    reg.load(Path("data/skills.json"))
    return reg


@pytest.mark.parametrize("affect", [0, int(AffectFlag.HASTE), int(AffectFlag.SLOW)])
def test_skill_wait_is_raw_beats_regardless_of_haste_slow(monkeypatch: pytest.MonkeyPatch, affect: int) -> None:
    reg = _registry()
    skill = reg.get("acid blast")
    # Guarantee the skill fires so wait is applied.
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 1)

    caster = Character(
        mana=20,
        is_npc=False,
        affected_by=affect,
        skills={"acid blast": 100},
    )
    target = Character()
    reg.use(caster, "acid blast", target)

    # ROM: raw beats, never scaled by haste/slow (src/merc.h:2116 WAIT_STATE).
    assert caster.wait == skill.beats
