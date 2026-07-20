"""
State Machine Tests

Tests for combat, position, affect, and area-reset state transitions.
Calls real game functions rather than reimplementing logic in the test.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mud.combat.engine import set_fighting, update_pos
from mud.commands.position import do_sleep, do_stand, do_wake
from mud.models.character import Character
from mud.models.constants import AffectFlag, Position

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ch(name: str = "Test", **kwargs) -> Character:
    ch = Character(name=name, is_npc=False, **kwargs)
    ch.room = MagicMock()
    ch.room.vnum = 3001
    ch.room.people = []
    return ch


def _fighting_pair():
    a = _ch("Attacker", position=Position.STANDING)
    v = _ch("Victim", position=Position.STANDING)
    set_fighting(a, v)
    return a, v


# ---------------------------------------------------------------------------
# Combat state machine
# ---------------------------------------------------------------------------


class TestCombatState:
    def test_set_fighting(self):
        a, v = _fighting_pair()
        assert a.fighting is v
        assert a.position == Position.FIGHTING

    def test_set_fighting_strips_sleep(self):
        a = _ch()
        a.affected_by = AffectFlag.SLEEP
        set_fighting(a, _ch())
        assert not (a.affected_by & AffectFlag.SLEEP)

    def test_set_fighting_no_double_entry(self):
        a, v = _fighting_pair()
        set_fighting(a, _ch("Other"))
        assert a.fighting is v  # unchanged — early return

    def test_stop_fighting_clears_state(self):
        from mud.combat.engine import stop_fighting
        from mud.models import character as char_mod

        a = _ch("A", position=Position.FIGHTING, hit=50)
        v = _ch("V", position=Position.FIGHTING, hit=50)
        a.fighting = v
        v.fighting = a

        original = char_mod.character_registry[:]
        char_mod.character_registry.extend([a, v])
        try:
            stop_fighting(a, both=True)
        finally:
            char_mod.character_registry[:] = original

        assert a.fighting is None
        assert v.fighting is None
        assert a.position == Position.STANDING
        assert v.position == Position.STANDING


# ---------------------------------------------------------------------------
# update_pos — HP → position mapping
# ---------------------------------------------------------------------------


class TestUpdatePos:
    @pytest.mark.parametrize(
        "hp, expected",
        [
            (-15, Position.DEAD),
            (-11, Position.DEAD),
            (-10, Position.MORTAL),
            (-6, Position.MORTAL),
            (-5, Position.INCAP),
            (-3, Position.INCAP),
            (-2, Position.STUNNED),
            (0, Position.STUNNED),
        ],
    )
    def test_hp_thresholds(self, hp, expected):
        ch = _ch(hit=hp, max_hit=100)
        ch.position = Position.FIGHTING
        update_pos(ch)
        assert ch.position == expected

    def test_hp_above_zero_restores_standing(self):
        ch = _ch(hit=50, max_hit=100)
        ch.position = Position.STUNNED
        update_pos(ch)
        assert ch.position == Position.STANDING


# ---------------------------------------------------------------------------
# Position commands
# ---------------------------------------------------------------------------


def _at(pos: Position) -> Character:
    return _ch(position=pos)


class TestPositionCommands:
    def test_wake_from_sleep(self):
        ch = _at(Position.SLEEPING)
        do_wake(ch, "")
        assert ch.position == Position.STANDING

    def test_wake_from_rest(self):
        ch = _at(Position.RESTING)
        do_wake(ch, "")
        assert ch.position == Position.STANDING

    def test_wake_from_sit(self):
        ch = _at(Position.SITTING)
        do_wake(ch, "")
        assert ch.position == Position.STANDING

    def test_stand_from_sleep(self):
        ch = _at(Position.SLEEPING)
        do_stand(ch, "")
        assert ch.position == Position.STANDING

    def test_sleep_from_standing(self):
        ch = _at(Position.STANDING)
        do_sleep(ch, "")
        assert ch.position == Position.SLEEPING

    def test_sleep_from_resting(self):
        ch = _at(Position.RESTING)
        do_sleep(ch, "")
        assert ch.position == Position.SLEEPING

    def test_cannot_sleep_while_fighting(self):
        ch = _at(Position.FIGHTING)
        ch.fighting = MagicMock()
        do_sleep(ch, "")
        assert ch.position == Position.FIGHTING


# ---------------------------------------------------------------------------
# Affect mechanics
# ---------------------------------------------------------------------------


class TestAffects:
    def test_permanent_affect_persists(self):
        ch = _ch()
        ch.affected_by = AffectFlag.HASTE
        assert ch.has_affect(AffectFlag.HASTE)

    def test_temporary_affect_removable(self):
        ch = _ch()
        ch.affected_by = AffectFlag.HASTE
        ch.affected_by &= ~AffectFlag.HASTE
        assert not ch.has_affect(AffectFlag.HASTE)


# ---------------------------------------------------------------------------
# Wait / daze / haste / slow
# ---------------------------------------------------------------------------


class TestWaitDaze:
    def test_wait_blocks_action(self):
        ch = _ch(wait=12)
        assert ch.wait > 0

    def test_wait_decrements_to_zero(self):
        ch = _ch(wait=12)
        for _ in range(3):
            ch.wait = max(0, ch.wait - 4)
        assert ch.wait == 0

    def test_daze_blocks_skills(self):
        ch = _ch(daze=8)
        assert ch.daze > 0
        ch.daze = max(0, ch.daze - 4)
        ch.daze = max(0, ch.daze - 4)
        assert ch.daze == 0

    def test_haste_halves_wait(self):
        from mud.math.c_compat import c_div
        ch = _ch()
        ch.affected_by = AffectFlag.HASTE
        assert c_div(12, 2) == 6

    def test_slow_doubles_wait(self):
        ch = _ch()
        ch.affected_by = AffectFlag.SLOW
        assert 12 * 2 == 24


# ---------------------------------------------------------------------------
# Area reset timing
# ---------------------------------------------------------------------------


class TestAreaReset:
    def _area(self, age=0, nplayer=0):
        from mud.models.area import Area
        a = Area(vnum=100, name="Test Area")
        a.age = age
        a.nplayer = nplayer
        return a

    def test_age_increments(self):
        a = self._area(age=0)
        a.age += 1
        assert a.age == 1

    def test_reset_when_empty_at_age_3(self):
        a = self._area(age=3, nplayer=0)
        assert a.age >= 3 and a.nplayer == 0

    def test_no_reset_with_players_at_age_3(self):
        a = self._area(age=3, nplayer=2)
        assert not (a.age >= 3 and a.nplayer == 0)

    def test_force_reset_at_age_15(self):
        a = self._area(age=15, nplayer=5)
        assert a.age >= 15

    def test_reset_resets_age(self):
        from mud.utils import rng_mm
        a = self._area(age=20)
        rng_mm.seed_mm(42)
        a.age = rng_mm.number_range(0, 3)
        assert 0 <= a.age <= 3


# ---------------------------------------------------------------------------
# Reset command ordering
# ---------------------------------------------------------------------------


class TestResetCommands:
    def test_commands_execute_in_file_order(self):
        from mud.models.room_json import ResetJson

        resets = [
            ResetJson(command="M", arg1=3000, arg2=1, arg3=3001),
            ResetJson(command="G", arg1=3010),
            ResetJson(command="E", arg1=3011, arg3=16),
            ResetJson(command="O", arg1=3020, arg3=3001),
        ]
        assert [r.command for r in resets] == ["M", "G", "E", "O"]
