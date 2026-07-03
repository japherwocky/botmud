"""FIGHT-089 — check_dodge's visibility halving must key on can_see(victim, attacker).

ROM ``check_dodge`` (src/fight.c:1363): ``if (!can_see(victim, ch)) chance /= 2;`` —
victim is the defender, ch the attacker, so the halving asks whether the DEFENDER
can see the ATTACKER (the opposite direction from check_parry's
``can_see(ch, victim)``; can_see is not symmetric).

The pre-fix port used ``getattr(victim, "can_see", lambda x: True)(attacker)`` —
the runtime entities have no ``can_see`` method, so the ``lambda x: True`` fallback
made the halving never fire. This test pins both the functionality and the
direction (the twin of the FIGHT-084 check_parry fix).
"""

from __future__ import annotations

import pytest

from mud.combat.engine import check_dodge
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
    victim.skills["dodge"] = 100  # base chance = 100 / 2 = 50
    victim.position = Position.STANDING
    attacker.position = Position.STANDING
    # mid-combat so can_see_character's sneak branch draws no RNG
    attacker.fighting = victim
    victim.fighting = attacker
    attacker.room.light = 5  # lit so can_see is not dark-gated
    return attacker, victim


def test_dodge_halved_when_victim_cannot_see_attacker(monkeypatch):
    # Attacker invisible + victim has no detect-invis => victim can't see attacker =>
    # ROM halves 50 -> 25. Roll 30: 30 >= 25 -> dodge FAILS. The pre-fix inert lambda
    # never halved (30 >= 50 False -> dodge succeeded).
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 30)
    attacker, victim = _pair()
    attacker.add_affect(AffectFlag.INVISIBLE)
    assert check_dodge(attacker, victim) is False


def test_dodge_not_halved_when_victim_sees_attacker(monkeypatch):
    # Both visible: victim sees attacker => chance stays 50; 30 >= 50 False -> dodge succeeds.
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 30)
    attacker, victim = _pair()
    assert check_dodge(attacker, victim) is True


def test_dodge_direction_is_victim_to_attacker(monkeypatch):
    # Direction lock: victim invisible (the attacker can't see the victim) but the
    # victim CAN see the visible attacker. ROM keys on can_see(victim, attacker) -> not
    # halved -> dodge succeeds. An attacker->victim implementation would halve (attacker
    # blind to the invisible victim) and the dodge would fail.
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 30)
    attacker, victim = _pair()
    victim.add_affect(AffectFlag.INVISIBLE)
    assert check_dodge(attacker, victim) is True
