"""FIGHT-084 — check_parry's visibility halving must key on can_see(attacker, victim).

ROM ``check_parry`` (src/fight.c:1311): ``if (!can_see(ch, victim)) chance /= 2;`` —
ch is the attacker, victim the defender, so the halving asks whether the ATTACKER
can see the VICTIM. (``check_dodge`` at :1363 is the opposite direction,
``!can_see(victim, ch)``; can_see is not symmetric.)

The pre-fix port used ``victim.can_see(attacker)`` (wrong direction) AND fell back
to a ``lambda x: True`` when the method was absent — so the halving never fired at
all. This test pins both the functionality and the direction.
"""

from __future__ import annotations

import pytest

from mud.combat.engine import check_parry
from mud.models.constants import AffectFlag, Position
from mud.utils import rng_mm
from mud.world import create_test_character, initialize_world

_ROOM = 3001


@pytest.fixture(autouse=True)
def _world():
    initialize_world("area/area.lst")


def _pair():
    attacker = create_test_character("Attacker", _ROOM)
    victim = create_test_character("Victim", _ROOM)
    victim.skills["parry"] = 100  # base chance = 100 / 2 = 50
    victim.has_weapon_equipped = True
    victim.position = Position.STANDING
    attacker.position = Position.STANDING
    # mid-combat so can_see_character's sneak branch draws no RNG
    attacker.fighting = victim
    victim.fighting = attacker
    attacker.room.light = 5  # lit so can_see is not dark-gated
    return attacker, victim


def test_parry_halved_when_attacker_cannot_see_victim(monkeypatch):
    # Victim invisible + attacker has no detect-invis => attacker can't see victim =>
    # ROM halves 50 -> 25. Roll 30: 30 >= 25 -> parry FAILS. The pre-fix inert lambda
    # never halved (30 >= 50 False -> parry succeeded).
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 30)
    attacker, victim = _pair()
    victim.add_affect(AffectFlag.INVISIBLE)
    assert check_parry(attacker, victim) is False


def test_parry_not_halved_when_attacker_sees_victim(monkeypatch):
    # Both visible: attacker sees victim => chance stays 50; 30 >= 50 False -> parry succeeds.
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 30)
    attacker, victim = _pair()
    assert check_parry(attacker, victim) is True


def test_parry_direction_is_attacker_to_victim(monkeypatch):
    # Direction lock: attacker invisible (the victim can't see the attacker) but the
    # attacker CAN see the visible victim. ROM keys on can_see(attacker, victim) -> not
    # halved -> parry succeeds. A victim->attacker implementation would halve (victim
    # blind to the invisible attacker) and the parry would fail.
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 30)
    attacker, victim = _pair()
    attacker.add_affect(AffectFlag.INVISIBLE)
    assert check_parry(attacker, victim) is True
