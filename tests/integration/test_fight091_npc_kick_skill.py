"""FIGHT-091 — an NPC's kick chance uses ROM get_skill (10 + 3*level), not 0.

ROM do_kick (src/fight.c:3125):

    if (get_skill (ch, gsn_kick) > number_percent ())
        damage (ch, victim, number_range (1, ch->level), gsn_kick, DAM_BASH, TRUE);

For an NPC, ``get_skill(ch, gsn_kick) = 10 + 3*ch->level`` (src/handler.c:410).
The Python port read the kick percent from the skills dict, which is empty for
mobs, so ``chance == 0`` and an NPC's kick could never land — aggressive
OFF_KICK mobs silently never kicked. This is the do_kick site of the HANDLER-008
get_skill NPC-formula class. This test locks the NPC kick chance.
"""

from __future__ import annotations

import pytest

from mud.commands.combat import do_kick
from mud.models.constants import OffFlag, Position
from mud.utils import rng_mm
from mud.world import create_test_character, initialize_world

_ROOM = 3001


@pytest.fixture(autouse=True)
def _world():
    initialize_world("area/area.lst")


def test_npc_kick_uses_rom_get_skill_and_can_land(monkeypatch: pytest.MonkeyPatch) -> None:
    mob = create_test_character("Brawler", _ROOM)
    victim = create_test_character("Traveller", _ROOM)
    mob.is_npc = True
    mob.level = 10  # ROM get_skill kick = 10 + 3*10 = 40
    mob.off_flags = int(OffFlag.KICK)
    mob.position = Position.FIGHTING
    victim.is_npc = False
    victim.position = Position.FIGHTING
    victim.hit = 200
    victim.max_hit = 200
    mob.fighting = victim
    victim.fighting = mob

    # roll 5: ROM chance 40 > 5 -> kick lands. Pre-fix chance 0 (skills dict) -> 0 > 5
    # False -> always miss.
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 5)
    do_kick(mob, "")
    assert victim.hit < 200, "an NPC's kick should be able to land (ROM get_skill 10+3*level)"


def test_dazed_npc_kick_chance_reduced_by_get_skill(monkeypatch: pytest.MonkeyPatch) -> None:
    # HANDLER-008: ROM get_skill applies a daze reduction (2*skill/3 for a skill),
    # so a dazed kicker lands less often. Level-20 NPC: base 70, dazed 2*70/3 = 46.
    # At roll 50 the base chance would hit (70 > 50) but the dazed chance misses
    # (46 > 50 is False) — locks the daze modifier at the do_kick site.
    mob = create_test_character("Groggy", _ROOM)
    victim = create_test_character("Traveller", _ROOM)
    mob.is_npc = True
    mob.level = 20
    mob.off_flags = int(OffFlag.KICK)
    mob.daze = 4
    mob.position = Position.FIGHTING
    victim.is_npc = False
    victim.position = Position.FIGHTING
    victim.hit = 200
    victim.max_hit = 200
    mob.fighting = victim
    victim.fighting = mob

    monkeypatch.setattr(rng_mm, "number_percent", lambda: 50)
    do_kick(mob, "")
    assert victim.hit == 200, "a dazed NPC's kick chance should be reduced (ROM get_skill daze)"
