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
from mud.skills.handlers import _hand_to_hand_skill, disarm
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
    caster.skills = {"disarm": 100}  # ROM disarm-skill gate; isolate the hand-to-hand term
    caster.off_flags = int(OffFlag.DISARM)  # unarmed NPC allowed to disarm
    # wait > 0 so the disarm-success path drops the weapon to the room rather than the
    # NPC-recovery branch (which is MobInstance-only; a flag-flipped Character lacks
    # add_to_inventory). Irrelevant to the chance under test.
    victim.wait = 5
    _wield(victim)

    # roll 0: chance = disarm(100) * hth / 150 + modifiers(=-16).
    #   floor path (hth=1):   c_div(100,150)=0  → chance clamps to 0  → 0>=0 → FAIL
    #   ROM path  (hth=40+2*10=60): c_div(6000,150)=40 → chance 24    → 0<24 → SUCCEED
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 0)
    monkeypatch.setattr(skill_handlers.rng_mm, "number_percent", lambda: 0)

    assert disarm(caster, victim) is True, "unarmed NPC disarm should use raw hand-to-hand skill"


def test_hand_to_hand_skill_mirrors_rom_get_skill() -> None:
    # ROM get_skill (src/handler.c:394): PC → learned percent; NPC → 40 + 2*level
    # (hand-to-hand has no ACT gate, unlike backstab's ACT_THIEF).
    pc = create_test_character("Monk", _ROOM)
    pc.is_npc = False
    pc.skills["hand to hand"] = 55
    assert _hand_to_hand_skill(pc) == 55

    npc = create_test_character("Brawler", _ROOM)
    npc.is_npc = True
    npc.level = 12
    assert _hand_to_hand_skill(npc) == 40 + 2 * 12
