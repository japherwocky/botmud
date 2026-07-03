"""FIGHT-081 — AC modifiers must apply at the ÷10 scale, in ROM order.

Mirrors ROM one_hit `src/fight.c:480-503`:

    victim_ac = GET_AC(victim, AC_x) / 10;         # divide FIRST
    if (victim_ac < -15)                            # rescale on /10 scale
        victim_ac = (victim_ac + 15) / 5 - 15;
    if (!can_see(ch, victim))  victim_ac -= 4;      # visibility on /10 scale
    if (victim->position < POS_FIGHTING) victim_ac += 4;
    if (victim->position < POS_RESTING)  victim_ac += 6;

The pre-fix Python applied the -4/+4/+6 modifiers and the <-15 rescale to the
*raw* AC (×10 scale) and divided by 10 last, making the modifiers ~10× too
weak and mis-triggering the rescale for nearly every armored character.
"""

from __future__ import annotations

import pytest

from mud.combat.engine import _compute_victim_ac
from mud.models.character import Character
from mud.models.constants import AffectFlag, Position
from mud.world import create_test_character, initialize_world

_ROOM = 3001  # temple of Mota — lit, non-dark
AC_BASH = 1  # ROM merc.h — armor[] index order PIERCE,BASH,SLASH,EXOTIC


@pytest.fixture(autouse=True)
def _world():
    initialize_world("area/area.lst")


def _sleeping_victim(ac_value: int) -> Character:
    """A sleeping victim so get_ac returns raw armor (no DEX bonus, IS_AWAKE false)."""
    victim = create_test_character("Victim", _ROOM)
    victim.armor = [ac_value, ac_value, ac_value, ac_value]
    victim.position = Position.SLEEPING
    return victim


def test_ac_minus_100_sleeping_visible() -> None:
    # raw AC_BASH = -100, sleeping (pos < FIGHTING and < RESTING), attacker sees victim.
    # ROM: -100/10 = -10; not < -15; +4 (pos<FIGHTING) = -6; +6 (pos<RESTING) = 0.
    attacker = create_test_character("Att", _ROOM)
    victim = _sleeping_victim(-100)
    ac = _compute_victim_ac(attacker, victim, AC_BASH, victim.position)
    assert ac == 0


def test_ac_minus_200_triggers_rescale_on_tenths_scale() -> None:
    # raw AC_BASH = -200, sleeping, visible.
    # ROM: -200/10 = -20; -20 < -15 -> (-20+15)/5 - 15 = -1-15 = -16; +4 = -12; +6 = -6.
    attacker = create_test_character("Att", _ROOM)
    victim = _sleeping_victim(-200)
    ac = _compute_victim_ac(attacker, victim, AC_BASH, victim.position)
    assert ac == -6


def test_invisible_victim_minus4_only_without_detect_invis() -> None:
    # ROM gates the -4 on !can_see(ch, victim), not on the victim's INVISIBLE affect.
    # A standing (no position mods) invisible victim: an attacker WITHOUT detect-invis
    # cannot see -> -4; WITH detect-invis can see -> no -4. Delta must be exactly -4.
    victim = create_test_character("Victim", _ROOM)
    victim.armor = [0, 0, 0, 0]
    victim.position = Position.STANDING
    victim.add_affect(AffectFlag.INVISIBLE)
    victim.fighting = None

    blind_attacker = create_test_character("Blind", _ROOM)
    seeing_attacker = create_test_character("Seer", _ROOM)
    seeing_attacker.add_affect(AffectFlag.DETECT_INVIS)

    ac_no_detect = _compute_victim_ac(blind_attacker, victim, AC_BASH, victim.position)
    ac_detect = _compute_victim_ac(seeing_attacker, victim, AC_BASH, victim.position)
    assert ac_no_detect - ac_detect == -4
