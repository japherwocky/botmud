"""BASH-001 — do_bash delivers the attacker's TO_CHAR flavor line + {5..{x color.

ROM `do_bash` (src/fight.c:2460-2482) calls `damage(..., FALSE)` on BOTH branches
— `show=FALSE` suppresses the dam_message entirely — so the three `{5…{x`
`act()` flavor lines are the only output:

  success: TO_VICT "{5$n sends you sprawling with a powerful bash!{x"
           TO_CHAR "{5You slam into $N, and send $M flying!{x"
           TO_NOTVICT "{5$n sends $N sprawling with a powerful bash.{x"
  failure: TO_CHAR "{5You fall flat on your face!{x"
           TO_NOTVICT "{5$n falls flat on $s face.{x"
           TO_VICT "{5You evade $n's bash, causing $m to fall flat on $s face.{x"

The port sent only TO_VICT/TO_NOTVICT (plain f-strings, no color) and returned
`apply_damage(...)` (default show=True), so the basher saw only a raw damage line
(never the flavor TO_CHAR), broadcasts were uncolored, and a dam_message ROM
suppresses leaked out.
"""

from __future__ import annotations

from mud.models.character import Character
from mud.models.constants import Position
from mud.models.room import Room
from mud.skills import handlers as skill_handlers


def _combatants():
    room = Room(vnum=9800, name="arena")
    attacker = Character(name="Basher", is_npc=False, level=30, position=Position.FIGHTING)
    victim = Character(name="Victim", is_npc=True, level=30, position=Position.FIGHTING)
    for c in (attacker, victim):
        c.max_hit = c.hit = 200
        c.messages = []
        room.add_character(c)
    return attacker, victim


def test_bash_success_returns_char_flavor_line_with_color():
    attacker, victim = _combatants()
    result = skill_handlers.bash(attacker, victim, success=True, chance=80)
    # TO_CHAR flavor line is the command return, colored.
    assert result == "{5You slam into Victim, and send it flying!{x", repr(result)
    # Delivered exactly once — not also pushed to the attacker's mailbox.
    assert attacker.messages.count(result) == 0, attacker.messages
    # Victim sees the colored TO_VICT flavor line.
    assert any("{5" in m and "sends you sprawling with a powerful bash!" in m for m in victim.messages), victim.messages
    # show=FALSE: no dam_message verb (miss/maul/scratch/…) reaches the victim.
    assert not any("bash" in m.lower() and "sprawling" not in m for m in victim.messages), victim.messages


def test_bash_failure_returns_fall_flat_line_with_color():
    attacker, victim = _combatants()
    result = skill_handlers.bash(attacker, victim, success=False)
    assert result == "{5You fall flat on your face!{x", repr(result)
    assert attacker.messages.count(result) == 0, attacker.messages
    # Victim sees the colored TO_VICT "You evade ..." line.
    assert any("{5" in m and "You evade Basher's bash" in m for m in victim.messages), victim.messages
