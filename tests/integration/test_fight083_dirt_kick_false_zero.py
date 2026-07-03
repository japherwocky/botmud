"""FIGHT-083 — do_dirt's false-zero hack + `chance == 0` (not `<= 0`).

ROM ``do_dirt`` (src/fight.c:2566-2608):

    if (chance % 5 == 0) chance += 1;      # sloppy hack to prevent false zeroes
    switch (sector) { ... water/air: chance = 0; ... }
    if (chance == 0) { "There isn't any dirt to kick."; return; }

The hack guarantees a dry-land chance never lands exactly on 0, so a post-terrain
`chance == 0` uniquely means water/air. The pre-fix port omitted the hack and used
`chance <= 0`, so a weak/low-dex kicker on dry land (chance ≤ 0) wrongly saw
"There isn't any dirt to kick." and skipped the guaranteed-miss WAIT_STATE.
"""

from __future__ import annotations

import pytest

from mud.models.constants import Position, Sector
from mud.skills.handlers import dirt_kicking
from mud.world import create_test_character, initialize_world

_ROOM = 3001
_NO_DIRT = "There isn't any dirt to kick."


@pytest.fixture(autouse=True)
def _world():
    initialize_world("area/area.lst")


def _setup(skill: int, sector: Sector):
    caster = create_test_character("Kicker", _ROOM)
    victim = create_test_character("Target", _ROOM)
    caster.is_npc = False
    caster.skills["dirt kicking"] = skill
    caster.wait = 0
    caster.messages = []
    caster.position = Position.STANDING
    victim.position = Position.STANDING
    victim.messages = []
    victim.affected_by = 0  # not blinded
    caster.room.sector_type = int(sector)
    return caster, victim


def test_false_zero_hack_lets_dry_land_kick_proceed():
    # skill 20 INSIDE: pre-fix chance = 20 - 20 = 0 -> false "no dirt". ROM hack bumps
    # 20 -> 21 before terrain, so 21 - 20 = 1 -> the kick proceeds (guaranteed miss).
    caster, victim = _setup(skill=20, sector=Sector.INSIDE)
    dirt_kicking(caster, victim)
    assert _NO_DIRT not in caster.messages
    assert caster.wait > 0  # WAIT_STATE applied, unlike the pre-fix false-zero return


def test_negative_dry_land_chance_still_proceeds():
    # skill 5 INSIDE: chance 5 -> hack 6 -> terrain -20 = -14. ROM's `== 0` lets a
    # negative dry-land chance proceed (roll<chance always false -> miss + WAIT_STATE);
    # the pre-fix `<= 0` wrongly reported "no dirt".
    caster, victim = _setup(skill=5, sector=Sector.INSIDE)
    dirt_kicking(caster, victim)
    assert _NO_DIRT not in caster.messages
    assert caster.wait > 0


def test_water_still_reports_no_dirt():
    # Regression guard: water/air hard-set chance to 0, which still uniquely triggers
    # the ROM "no dirt" message (src/fight.c:2604) after the fix.
    caster, victim = _setup(skill=75, sector=Sector.WATER_SWIM)
    dirt_kicking(caster, victim)
    assert _NO_DIRT in caster.messages
    assert caster.wait == 0  # returned before WAIT_STATE, as in ROM
