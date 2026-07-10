"""KICK-001 — do_kick checks the level gate BEFORE the `fighting == NULL` gate.

ROM `do_kick` (src/fight.c:3109-3124) evaluates guards in this order:
  1. PC below class kick level → "You better leave the martial arts to fighters."
  2. NPC without OFF_KICK → silent return.
  3. `ch->fighting == NULL` → "You aren't fighting anyone."

The port checked `fighting is None` FIRST, so a sub-level PC who is not in
combat saw "You aren't fighting anyone." where ROM shows the martial-arts
message.
"""

from __future__ import annotations

from mud.commands.combat import do_kick
from mud.world import create_test_character, initialize_world


def test_kick_below_level_and_not_fighting_shows_martial_arts_message():
    initialize_world("area/area.lst")
    # A level-0, class-0 PC needs kick level 53 (kick levels = (53,12,14,8)),
    # and is not fighting anyone.
    char = create_test_character("Novice", 3001)
    char.fighting = None

    result = do_kick(char, "")

    assert result == "You better leave the martial arts to fighters.", result


def test_kick_at_level_but_not_fighting_still_reports_not_fighting():
    """A PC who passes the level gate but isn't fighting still gets ROM's fighting message."""
    initialize_world("area/area.lst")
    char = create_test_character("Veteran", 3001)
    char.level = 60  # above the class-0 kick level (53)
    char.fighting = None

    result = do_kick(char, "")

    assert result == "You aren't fighting anyone.", result
