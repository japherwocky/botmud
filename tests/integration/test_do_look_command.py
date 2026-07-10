"""Integration tests for do_look command ROM C parity.

ROM Reference: src/act_info.c do_look (lines 1037-1313)
"""

from __future__ import annotations

from mud.commands.inspection import do_look
from mud.models.character import Character
from mud.models.constants import AffectFlag, ContainerFlag, Direction, ItemType, PlayerFlag, Position, RoomFlag, Sector
from mud.models.room import Exit, Room
from mud.world.look import _room_occupant_line


def _basic_room() -> Room:
    room = Room(vnum=3001)
    room.name = "Midgaard Temple"
    room.description = "You are in the temple."
    room.sector_type = int(Sector.INSIDE)
    room.room_flags = 0
    room.light = 1
    room.people = []
    room.contents = []
    room.exits = [None, None, None, None, None, None]
    return room


def _basic_char() -> Character:
    char = Character()
    char.name = "Looker"
    char.level = 1
    char.trust = 0
    char.is_npc = False
    char.position = int(Position.STANDING)
    char.act = 0
    char.comm = 0
    return char


def test_look_room_without_autoexit_does_not_show_exit_line():
    """ROM only calls do_exits('auto') when PLR_AUTOEXIT is set."""
    room = _basic_room()
    north = Room(vnum=3002)
    north.name = "Temple Square"
    north.description = "A busy square."
    north.sector_type = int(Sector.CITY)
    north.room_flags = 0
    north.light = 1
    north.people = []
    north.contents = []
    north.exits = [None, None, None, None, None, None]
    room.exits[int(Direction.NORTH)] = Exit(to_room=north, vnum=north.vnum)

    char = _basic_char()
    char.room = room
    room.people = [char]

    output = do_look(char, "")

    assert output == "Midgaard Temple\nYou are in the temple."


def test_look_room_with_autoexit_shows_exit_line_once():
    """ROM appends auto exits once when PLR_AUTOEXIT is set."""
    room = _basic_room()
    north = Room(vnum=3002)
    north.name = "Temple Square"
    north.description = "A busy square."
    north.sector_type = int(Sector.CITY)
    north.room_flags = 0
    north.light = 1
    north.people = []
    north.contents = []
    north.exits = [None, None, None, None, None, None]
    room.exits[int(Direction.NORTH)] = Exit(to_room=north, vnum=north.vnum)

    char = _basic_char()
    char.act |= int(PlayerFlag.AUTOEXIT)
    char.room = room
    room.people = [char]

    output = do_look(char, "")

    assert output == "Midgaard Temple\nYou are in the temple.\n{o[Exits: north]{x\n"


def test_look_room_contents_are_not_prefixed_with_objects_label():
    """ROM room look appends object lines directly via show_list_to_char."""
    room = _basic_room()

    class Obj:
        # ROM format_obj_to_char(fShort=FALSE) lists ground objects by description.
        short_descr = "a wooden sword"
        description = "A wooden sword lies here."
        name = "sword"
        wear_loc = -1

    obj = Obj()
    room.contents = [obj]

    char = _basic_char()
    char.room = room
    room.people = [char]

    output = do_look(char, "")

    assert output == "Midgaard Temple\nYou are in the temple.\nA wooden sword lies here."


def test_look_room_people_are_not_prefixed_with_characters_label():
    """ROM room look appends visible character lines directly via show_char_to_char."""
    room = _basic_room()

    char = _basic_char()
    char.room = room

    other = Character()
    other.name = "Sneaky"
    other.level = 1
    other.trust = 0
    other.is_npc = False
    other.position = int(Position.STANDING)
    other.room = room

    room.people = [char, other]

    output = do_look(char, "")

    assert output == "Midgaard Temple\nYou are in the temple.\nSneaky is here."


def test_look_dark_room_shows_raw_visible_character_lines_without_label():
    """ROM dark-room look prints the pitch-black line plus raw show_char_to_char output."""
    room = _basic_room()
    room.light = 0
    room.room_flags = int(RoomFlag.ROOM_DARK)

    char = _basic_char()
    char.affected_by = int(AffectFlag.INFRARED)
    char.room = room

    other = Character()
    other.name = "Sneaky"
    other.level = 1
    other.trust = 0
    other.is_npc = False
    other.position = int(Position.STANDING)
    other.room = room

    room.people = [char, other]

    output = do_look(char, "")

    assert output == "It is pitch black ...\nSneaky is here."


def test_look_in_drink_container_uses_rom_liquid_color_wording():
    """ROM drink containers show the amount band and liquid color."""
    room = _basic_room()

    class Drink:
        name = "flask water"
        short_descr = "a flask of water"
        item_type = int(ItemType.DRINK_CON)
        value = [10, 10, 0, 0, 0]

    drink = Drink()
    room.contents = [drink]

    char = _basic_char()
    char.room = room
    room.people = [char]

    output = do_look(char, "in flask")

    assert output == "It's more than half-filled with  a clear liquid."


def test_look_in_drink_container_fill_band_matches_rom_truncation():
    """LOOK-015: the fill-level band must use ROM's exact integer comparisons
    `value[1] < value[0]/4` and `value[1] < 3*value[0]/4` (src/act_info.c:1141-1145),
    NOT a rewritten `value[1]*100//value[0]` percentage. C truncates each
    expression independently, so at value[0]=10 the two forms disagree:
    value[1]=2 is "about half-" in ROM (2 < 10/4=2 is false; 2 < 30/4=7 is true)
    but "less than half-" under the percent form (20 < 25); value[1]=7 is
    "more than half-" in ROM (7 < 7 false) but "about half-" under percent (70 < 75).
    """
    room = _basic_room()

    def _drink(v0: int, v1: int):
        class Drink:
            name = "flask water"
            short_descr = "a flask of water"
            item_type = int(ItemType.DRINK_CON)
            value = [v0, v1, 0, 0, 0]

        return Drink()

    char = _basic_char()
    char.room = room
    room.people = [char]

    # value[0]=10, value[1]=2 → ROM "about half-" (percent form gives "less than half-")
    room.contents = [_drink(10, 2)]
    assert do_look(char, "in flask") == "It's about half-filled with  a clear liquid."

    # value[0]=10, value[1]=7 → ROM "more than half-" (percent form gives "about half-")
    room.contents = [_drink(10, 7)]
    assert do_look(char, "in flask") == "It's more than half-filled with  a clear liquid."


def test_look_in_closed_container_uses_rom_cont_closed_bit():
    """ROM uses CONT_CLOSED=4, not a hardcoded low bit."""
    room = _basic_room()

    class Container:
        name = "chest wooden"
        short_descr = "a wooden chest"
        item_type = int(ItemType.CONTAINER)
        value = [50, int(ContainerFlag.CLOSED), 0, 0, 0]
        contained_items = []

    container = Container()
    room.contents = [container]

    char = _basic_char()
    char.room = room
    room.people = [char]

    output = do_look(char, "in chest")

    assert output == "It is closed."


def test_look_blind_character_gets_rom_blind_message():
    """ROM check_blind gate blocks look before any room/object output."""
    room = _basic_room()

    char = _basic_char()
    char.affected_by = int(AffectFlag.BLIND)
    char.room = room
    room.people = [char]

    output = do_look(char, "")

    assert output == "You can't see a thing!"


# ---------------------------------------------------------------------------
# _room_occupant_line FIGHTING branches — ROM src/act_info.c:404-416
# ---------------------------------------------------------------------------


def _fighting_victim(room, *, name: str = "Goblin") -> Character:
    """A minimal PC in FIGHTING position."""
    victim = Character()
    victim.name = name
    victim.level = 1
    victim.trust = 0
    victim.is_npc = False
    victim.position = int(Position.FIGHTING)
    victim.room = room
    victim.fighting = None
    return victim


def test_room_occupant_line_fighting_no_target_shows_thin_air():
    """ROM branch 1: victim.fighting is None → 'fighting thin air??'."""
    room = _basic_room()
    observer = _basic_char()
    observer.room = room

    victim = _fighting_victim(room)
    victim.fighting = None

    line = _room_occupant_line(observer, victim)

    assert line == "Goblin is here, fighting thin air??"


def test_room_occupant_line_fighting_observer_shows_YOU():
    """ROM branch 2: victim.fighting is observer → 'fighting YOU!'."""
    room = _basic_room()
    observer = _basic_char()
    observer.room = room

    victim = _fighting_victim(room)
    victim.fighting = observer

    line = _room_occupant_line(observer, victim)

    assert line == "Goblin is here, fighting YOU!"


def test_room_occupant_line_fighting_same_room_shows_name_with_period():
    """ROM branch 3: victim.fighting in same room → 'fighting Name.'."""
    room = _basic_room()
    observer = _basic_char()
    observer.room = room

    third = Character()
    third.name = "Orc"
    third.level = 1
    third.trust = 0
    third.is_npc = False
    third.room = room

    victim = _fighting_victim(room)
    victim.fighting = third

    line = _room_occupant_line(observer, victim)

    assert line == "Goblin is here, fighting Orc."


def test_room_occupant_line_fighting_left_room_shows_someone_who_left():
    """ROM branch 4: victim.fighting in different room → 'fighting someone who left??'."""
    room = _basic_room()
    other_room = _basic_room()
    other_room.vnum = 9999

    observer = _basic_char()
    observer.room = room

    third = Character()
    third.name = "Orc"
    third.level = 1
    third.trust = 0
    third.is_npc = False
    third.room = other_room  # left the room

    victim = _fighting_victim(room)
    victim.fighting = third

    line = _room_occupant_line(observer, victim)

    assert line == "Goblin is here, fighting someone who left??"


def test_room_occupant_line_aura_order_pink_before_white():
    """LOOK-010 — ROM show_char_to_char_0 prints (Pink Aura) before (White Aura).

    ROM ``src/act_info.c:266,272`` appends FAERIE_FIRE's ``(Pink Aura)`` before
    SANCTUARY's ``(White Aura)`` (the strcat order is the print order). The port
    emitted ``(White Aura)`` first, so a room occupant with both auras displayed
    them in the wrong order.
    """
    room = _basic_room()
    observer = _basic_char()
    observer.room = room

    victim = _basic_char()
    victim.name = "Guard"
    victim.room = room
    victim.position = int(Position.STANDING)
    victim.add_affect(AffectFlag.SANCTUARY)
    victim.add_affect(AffectFlag.FAERIE_FIRE)

    line = _room_occupant_line(observer, victim)

    assert line.startswith("(Pink Aura) (White Aura) "), f"aura order: {line!r}"
    assert line.index("(Pink Aura)") < line.index("(White Aura)")
