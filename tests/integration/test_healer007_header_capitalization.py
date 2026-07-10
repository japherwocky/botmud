"""HEALER-007 — do_heal price-list header must be first-letter-capitalized.

ROM `src/healer.c:67` prints the header via
`act("$N says 'I offer the following spells:'", ch, NULL, mob, TO_CHAR)`.
`act_new` (`src/comm.c:2379`) capitalizes the first character of every rendered
line, so a healer whose `short_descr` is lowercase-initial (e.g. "a healer")
renders "**A** healer says 'I offer the following spells:'".

The port built the header with a bare f-string and no capitalization — unlike
the sibling "not enough gold" branch, which correctly uses `capitalize_act_line`
(INV-029/ACT-CAP). So the header rendered "a healer says ..." (lowercase).
"""

from __future__ import annotations

from mud.commands.dispatcher import process_command
from mud.models.character import Character
from mud.models.constants import ActFlag


def _place_healer(room) -> Character:
    healer = Character(
        name="Healer",
        short_descr="a healer",  # lowercase initial — ROM act_new capitalizes it
        level=30,
        room=room,
        is_npc=True,
        act=int(ActFlag.IS_HEALER),
    )
    healer.messages = []
    room.people.append(healer)
    return healer


def test_heal_header_first_letter_capitalized(test_room, test_player):
    """ROM act_new caps buf[0] → 'A healer says ...', not 'a healer says ...'."""
    _place_healer(test_room)
    result = process_command(test_player, "heal")
    assert "A healer says 'I offer the following spells:'" in result
    assert "a healer says 'I offer the following spells:'" not in result
