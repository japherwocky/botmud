"""GL-048 — mp_delay_trigger parity with ROM's mobile_update TRIG_DELAY block.

ROM ``src/update.c:448-454``::

    if (HAS_TRIGGER (ch, TRIG_DELAY) && ch->mprog_delay > 0)
        if (--ch->mprog_delay <= 0) {
            mp_percent_trigger (ch, NULL, NULL, NULL, TRIG_DELAY);
            continue;                  /* UNCONDITIONAL — return value discarded */
        }

Two contracts the port broke (``mud/mobprog.py:mp_delay_trigger``, consumed at
``mud/ai/__init__.py`` ``if mp_delay_trigger(mob): continue``):

1. **HAS_TRIGGER gate.** The whole block only runs for a mob that has a
   ``TRIG_DELAY`` program; a mob without one never counts its ``mprog_delay``
   down. The port decremented ``mprog_delay`` for *any* mob with delay > 0.
2. **Unconditional continue.** On expiry ROM fires the trigger for its side
   effects and ``continue``s **unconditionally**, discarding
   ``mp_percent_trigger``'s bool, so the mob's tick ends before scavenge/wander.
   The port *returned* that bool, so when the percent roll fails the caller did
   not ``continue`` and fell through into the random-trigger + scavenge
   (``number_bits(6)``) + wander (``number_bits(3/5)``) blocks — extra RNG draws
   off the shared stream plus item pickup / movement ROM never performs that tick.
"""

from __future__ import annotations

from mud.mobprog import Trigger, mp_delay_trigger
from mud.models.character import Character
from mud.models.constants import Position
from mud.models.mob import MobProgram


def _delay_mob(*, delay: int, phrase: str) -> Character:
    mob = Character(name="Ticker", is_npc=True, position=Position.STANDING, mprog_delay=delay)
    mob.default_pos = Position.STANDING
    mob.mob_programs = [MobProgram(trig_type=int(Trigger.DELAY), trig_phrase=phrase, vnum=4900, code="mob echo tick")]
    return mob


def test_expired_delay_signals_continue_even_when_percent_roll_fails() -> None:
    """ROM :453 `continue` is unconditional — a phrase='0' program never fires, tick still ends."""
    mob = _delay_mob(delay=1, phrase="0")  # number_percent() < 0 is never true -> program does not fire
    assert mp_delay_trigger(mob) is True  # signals the caller's unconditional `continue`
    assert mob.mprog_delay == 0


def test_delay_not_decremented_without_a_delay_program() -> None:
    """ROM :448 gates the whole block on HAS_TRIGGER(TRIG_DELAY)."""
    mob = Character(name="Idler", is_npc=True, position=Position.STANDING, mprog_delay=3)
    mob.default_pos = Position.STANDING
    mob.mob_programs = []  # no TRIG_DELAY program
    assert mp_delay_trigger(mob) is False
    assert mob.mprog_delay == 3  # untouched — ROM would not count it down


def test_delay_still_pending_decrements_without_firing_or_continuing() -> None:
    """delay > 1: decrement only, no fire, no `continue` (mob falls through to scavenge/wander)."""
    mob = _delay_mob(delay=3, phrase="100")
    assert mp_delay_trigger(mob) is False
    assert mob.mprog_delay == 2
