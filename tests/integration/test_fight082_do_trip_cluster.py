"""FIGHT-082 — do_trip must match ROM src/fight.c:2641-2754.

Four confirmed divergences from ROM ``do_trip``:

(a) damage bound — Python used ``number_range(2, 2 + 2*size + skill_level//20)``;
    ROM (:2744) is ``number_range(2, 2 + 2*victim->size)`` (no skill term).
(b) speed modifier — Python omitted ROM :2722-2726:
    ``chance += 10`` if attacker OFF_FAST/AFF_HASTE, ``chance -= 20`` if victim is.
(c) wait/daze — Python applied PULSE_VIOLENCE waits and WAIT'd the victim; ROM:
    success WAIT_STATE(ch, beats) (:2742) + DAZE_STATE(victim, 2*PULSE_VIOLENCE) (:2741);
    failure WAIT_STATE(ch, beats*2/3) (:2750); self-trip WAIT_STATE(ch, 2*beats) (:2700).

trip beats = 24, PULSE_VIOLENCE = 12. For two default test characters all of
size/dex/level modifiers are 0, so ``chance == trip skill percent`` exactly.
"""

from __future__ import annotations

import pytest

from mud.commands.combat import do_trip
from mud.config import get_pulse_violence
from mud.models.character import Character
from mud.models.constants import AffectFlag, Position
from mud.utils import rng_mm
from mud.world import create_test_character, initialize_world

_ROOM = 3001
_TRIP_BEATS = 24  # skill metadata "trip": beats=24


@pytest.fixture(autouse=True)
def _world():
    initialize_world("area/area.lst")


def _setup(skill: int, att_name: str = "Tripper", vic_name: str = "Target") -> tuple[Character, Character]:
    attacker = create_test_character(att_name, _ROOM)
    victim = create_test_character(vic_name, _ROOM)
    attacker.is_npc = False
    attacker.skills["trip"] = skill
    attacker.wait = 0
    attacker.position = Position.STANDING
    victim.is_npc = True
    victim.position = Position.STANDING
    victim.wait = 0
    victim.daze = 0
    victim.hit = 500  # survive the trip's bash damage so position stays RESTING
    victim.max_hit = 500
    # Trip is a mid-combat action: both already fighting each other, so damage()'s
    # set_fighting is not re-triggered (mirrors ROM — victim stays POS_RESTING after
    # the knockdown rather than being re-seated to POS_FIGHTING by a fresh set_fighting).
    attacker.fighting = victim
    victim.fighting = attacker
    attacker.room.room_flags = 0  # clear ROOM_SAFE so is_safe does not pre-empt
    return attacker, victim


def test_success_uses_raw_beats_and_dazes_victim(monkeypatch) -> None:
    attacker, victim = _setup(skill=100)
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 1)  # 1 < 100 -> success
    monkeypatch.setattr(rng_mm, "number_range", lambda a, b: a)
    do_trip(attacker, "Target")
    # ROM :2742 WAIT_STATE(ch, skill_table[trip].beats) — raw beats, not PULSE_VIOLENCE.
    assert attacker.wait == _TRIP_BEATS
    # ROM :2741 DAZE_STATE(victim, 2*PULSE_VIOLENCE) — victim is DAZED, not WAIT'd.
    assert victim.daze == 2 * get_pulse_violence()
    assert victim.wait == 0
    # ROM :2743 sets POS_RESTING, but damage() (:743-744) re-seats a timer<=4 victim
    # to POS_FIGHTING — so a normal (non-linkdead) tripped victim ends at FIGHTING.
    assert victim.position == Position.FIGHTING


def test_failure_uses_two_thirds_beats(monkeypatch) -> None:
    attacker, victim = _setup(skill=50)
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 99)  # 99 < 50 false -> fail
    do_trip(attacker, "Target")
    # ROM :2750 WAIT_STATE(ch, skill_table[trip].beats * 2 / 3) = 24*2//3 = 16.
    assert attacker.wait == _TRIP_BEATS * 2 // 3


def test_self_trip_uses_two_beats() -> None:
    attacker, _victim = _setup(skill=100, att_name="Solo", vic_name="Bystander")
    do_trip(attacker, "Solo")  # target self by name
    # ROM :2700 WAIT_STATE(ch, 2 * skill_table[trip].beats) = 48.
    assert attacker.wait == 2 * _TRIP_BEATS


def test_success_damage_bound_has_no_skill_level_term(monkeypatch) -> None:
    attacker, victim = _setup(skill=100)  # victim size 0 -> ROM bound (2, 2)
    calls: list[tuple[int, int]] = []

    def rec(a, b):
        calls.append((a, b))
        return a

    monkeypatch.setattr(rng_mm, "number_range", rec)
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 1)  # success
    do_trip(attacker, "Target")
    # ROM :2744 number_range(2, 2 + 2*victim->size); size 0 -> (2, 2).
    assert (2, 2) in calls
    # the pre-fix bound was (2, 2 + skill_level//20) = (2, 7) for skill 100.
    assert (2, 7) not in calls


def test_haste_speed_modifier_adds_ten(monkeypatch) -> None:
    # ROM :2722-2723 — attacker OFF_FAST/AFF_HASTE adds +10 to chance.
    # base chance 45, percent roll fixed at 50: without haste 50<45 fails; with haste 50<55 succeeds.
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 50)
    monkeypatch.setattr(rng_mm, "number_range", lambda a, b: a)

    # Discriminate success from failure via the victim DAZE (success only), which is
    # independent of the position/damage re-seat quirk.
    slow_att, slow_vic = _setup(skill=45, att_name="SlowA", vic_name="TargetA")
    do_trip(slow_att, "TargetA")
    assert slow_vic.daze == 0  # failed without the +10 -> no DAZE

    fast_att, fast_vic = _setup(skill=45, att_name="FastB", vic_name="TargetB")
    fast_att.add_affect(AffectFlag.HASTE)
    do_trip(fast_att, "TargetB")
    assert fast_vic.daze == 2 * get_pulse_violence()  # +10 crossed the boundary -> success
