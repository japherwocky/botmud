"""TRIP-001 — do_trip's no-skill message must match ROM byte-for-byte.

ROM `do_trip` (src/fight.c:2654) sends `"Tripping?  What's that?\n\r"` — TWO
spaces after "Tripping?". The port had one space. Exact `==` assertion so a
whitespace-normalizing test can't pass on the wrong byte.
"""

from __future__ import annotations

from mud.commands.combat import do_trip
from mud.world import create_test_character, initialize_world


def test_trip_without_skill_message_has_two_spaces():
    initialize_world("area/area.lst")
    char = create_test_character("Klutz", 3001)
    char.skills.pop("trip", None)  # ensure no trip skill → skill_level 0
    result = do_trip(char, "someone")
    assert result == "Tripping?  What's that?", repr(result)
