"""FIGHT-087 — unarmed disarm uses ROM's raw hand-to-hand skill, not a floor of 1.

ROM do_disarm (src/fight.c:3186-3189):

    if (get_eq_char (ch, WEAR_WIELD) == NULL)
        chance = chance * hth / 150;      // hth = get_skill(ch, gsn_hand_to_hand)

For an unarmed attacker the disarm chance scales by the hand-to-hand skill. The
gate above it (src/fight.c:3160-3164) rejects an unarmed attacker when
``hth == 0 || (IS_NPC(ch) && !OFF_DISARM)`` — so on the unarmed path ROM's hth is
always the real ``get_skill`` value (for an NPC, ``40 + 2*level``; never 0).

The Python port fetched hand-to-hand via ``_skill_percent`` (skills-dict only,
0 for NPCs) and papered over the resulting 0 with ``max(hand_to_hand, 1)``, so an
unarmed NPC disarmer computed ``chance * 1 / 150`` instead of ROM's
``chance * (40+2*level) / 150`` — a near-guaranteed failure. The gate also used
``hth<=0 AND !OFF_DISARM`` where ROM is ``hth==0 OR (IS_NPC AND !OFF_DISARM)``.
This test locks the raw-hth chance and the ROM gate.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from mud.models.constants import OffFlag, WeaponType, WearLocation
from mud.skills import handlers as skill_handlers
from mud.skills.handlers import disarm
from mud.skills.skill_lookup import get_skill
from mud.utils import rng_mm
from mud.world import create_test_character, initialize_world

_ROOM = 3001


@pytest.fixture(autouse=True)
def _world():
    initialize_world("area/area.lst")


def _wield(victim) -> SimpleNamespace:
    weapon = SimpleNamespace(
        prototype=SimpleNamespace(
            name="longsword",
            short_descr="a longsword",
            item_type="weapon",
            value=[int(WeaponType.SWORD), 0, 0, 0],
            level=20,
        ),
        value=[int(WeaponType.SWORD), 0, 0, 0],
        extra_flags=0,
        short_descr="a longsword",
        item_type="weapon",
        wear_loc=int(WearLocation.WIELD),
        location=None,
    )
    victim.equipment[int(WearLocation.WIELD)] = weapon
    return weapon


def test_unarmed_npc_disarm_uses_rom_hand_to_hand_skill(monkeypatch: pytest.MonkeyPatch) -> None:
    caster = create_test_character("Disarmer", _ROOM)
    victim = create_test_character("Foe", _ROOM)
    caster.is_npc = True
    victim.is_npc = True
    caster.level = 10
    victim.level = 10
    caster.skills = {"disarm": 100}  # disarm-skill gate (still dict-sourced; see handlers.py)
    # HANDLER-008: the hand-to-hand skill now comes from get_skill (NPC 40+2*10 = 60),
    # so an unarmed NPC computes a real chance instead of the old floor-of-1.
    caster.off_flags = int(OffFlag.DISARM)
    # wait > 0 so the disarm-success path drops the weapon to the room rather than the
    # NPC-recovery branch (which is MobInstance-only; a flag-flipped Character lacks
    # add_to_inventory). Irrelevant to the chance under test.
    victim.wait = 5
    _wield(victim)

    # roll 0: chance = disarm(50) unarmed → c_div(50*60,150)=20; + modifiers(=-16) = 4;
    # 0 < 4 → SUCCEED. (The pre-HANDLER-008 skills-dict lookup gave disarm=0 → the
    # "You don't know how to disarm" gate, or hand-to-hand=0 → floor-of-1 → chance 0.)
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 0)
    monkeypatch.setattr(skill_handlers.rng_mm, "number_percent", lambda: 0)

    assert disarm(caster, victim) is True, "unarmed NPC disarm should use ROM get_skill values"


def test_disarm_hand_to_hand_uses_unified_get_skill() -> None:
    # HANDLER-008: disarm's unarmed hand-to-hand skill now comes from get_skill.
    # NPC → 40+2*level (no ACT gate); PC → learned percent.
    npc = create_test_character("Brawler", _ROOM)
    npc.is_npc = True
    npc.level = 12
    assert get_skill(npc, "hand to hand") == 40 + 2 * 12

    pc = create_test_character("Monk", _ROOM)
    pc.is_npc = False
    pc.level = 60  # above class gate
    pc.skills["hand to hand"] = 55
    assert get_skill(pc, "hand to hand") == 55
