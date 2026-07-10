"""LOOK-017 — room list appends a standing PC's title (show_char_to_char_0).

ROM `show_char_to_char_0` (src/act_info.c:285-288) appends the victim's
`pcdata->title` after `PERS(victim, ch)` when
`!IS_NPC(victim) && !IS_SET(ch->comm, COMM_BRIEF) && victim->position ==
POS_STANDING && ch->on == NULL`, before the " is here." position suffix — so a
standing titled PC lists as "Bob the Great is here.".

The port's `_room_occupant_line` built `pers(victim) + position_suffix` with no
title, so a titled PC listed as just "Bob is here.". Note the guard keys on the
OBSERVER's `comm`/`on` (ROM `ch`), a deliberate ROM quirk.
"""

from __future__ import annotations

from mud.models.constants import CommFlag, Position
from mud.world import create_test_character, initialize_world
from mud.world.look import look


def _two_pcs():
    initialize_world("area/area.lst")
    observer = create_test_character("Observer", 3001)
    victim = create_test_character("Bob", 3001)
    victim.pcdata.title = " the Great"  # ROM titles carry a leading space
    victim.position = Position.STANDING
    return observer, victim


def test_room_list_appends_standing_pc_title():
    observer, victim = _two_pcs()
    result = look(observer, "")
    assert "Bob the Great is here." in result, f"title missing from room list: {result!r}"


def test_brief_observer_suppresses_title():
    """ROM keys the title on the OBSERVER's COMM_BRIEF (ch->comm), not the victim's."""
    observer, victim = _two_pcs()
    observer.comm = int(CommFlag.BRIEF)
    result = look(observer, "")
    assert "Bob is here." in result
    assert "the Great" not in result


def test_observer_on_furniture_suppresses_title():
    """ROM keys the title on ch->on == NULL — an observer on furniture sees no title."""
    from mud.models.object import Object, ObjIndex

    observer, victim = _two_pcs()
    chair = Object(instance_id=1, prototype=ObjIndex(vnum=70000, short_descr="a chair"))
    observer.on = chair
    result = look(observer, "")
    assert "Bob is here." in result
    assert "the Great" not in result
