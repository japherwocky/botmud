"""Tests for mud.game_loop — game tick, char/obj/weather updates, mobile AI."""

from types import SimpleNamespace

import mud.game_loop as gl
import mud.mobprog as mobprog
from mud.ai import mobile_update
from mud.config import get_pulse_tick, get_pulse_violence
from mud.game_loop import (
    SkyState,
    char_update,
    events,
    game_tick,
    obj_update,
    schedule_event,
    weather,
    weather_tick,
)
from mud.models.area import Area
from mud.models.character import AffectData, Character, PCData, SpellEffect, character_registry
from mud.models.constants import (
    ROOM_VNUM_LIMBO,
    ActFlag,
    AffectFlag,
    ItemType,
    Position,
    RoomFlag,
    Size,
    WearFlag,
    WearLocation,
)
from mud.models.mob import MobIndex
from mud.models.obj import ObjIndex, object_registry
from mud.models.object import Object
from mud.models.room import Room, room_registry
from mud.models.shop import Shop
from mud.time import time_info
from mud.utils import rng_mm
from mud.wiznet import WiznetFlag

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_room(vnum, name="Test", *, flags=0, light=0):
    """Create an Area + Room pair and register the room."""
    area = Area(name=name)
    room = Room(vnum=vnum, area=area, room_flags=flags, light=light)
    room_registry[room.vnum] = room
    return area, room


def _make_char(name, *, is_npc=False, position=Position.STANDING, room=None, **kwargs):
    """Create a Character, optionally place it in a room, and register it."""
    ch = Character(name=name, is_npc=is_npc, position=int(position), **kwargs)
    if room is not None:
        room.add_character(ch)
    character_registry.append(ch)
    return ch


def _make_npc(name, *, position=Position.STANDING, default_pos=None, room=None, **kwargs):
    """Create an NPC with sensible defaults (standing, default_pos = position)."""
    if default_pos is None:
        default_pos = position
    return _make_char(
        name,
        is_npc=True,
        position=position,
        default_pos=int(default_pos),
        room=room,
        **kwargs,
    )


def _make_trig_act_listener(monkeypatch, room, *, vnum=9900, name="watcher"):
    """Create an NPC listener that records mp_act_trigger calls.

    Returns ``(listener, fired)`` where *fired* is a list of
    ``(message_str, actor_or_None)`` tuples.
    """
    listener = _make_npc(name, room=room)
    proto = MobIndex(vnum=vnum, short_descr=f"a {name}", level=5)
    proto.mprogs = []
    listener.prototype = proto

    fired: list[tuple[str, object | None]] = []
    original = mobprog.mp_act_trigger

    def _probe(argument, recipient, actor=None, *args, **kwargs):
        if recipient is listener:
            fired.append((str(argument), actor))
        return original(argument, recipient, actor, *args, **kwargs)

    monkeypatch.setattr(mobprog, "mp_act_trigger", _probe)
    return listener, fired


def _apply_poison(char, *, level=20, duration=5):
    """Apply a poison affect to a character."""
    char.add_affect(AffectFlag.POISON)
    char.affected.append(
        AffectData(
            type="poison",  # type: ignore[arg-type]
            level=level,
            duration=duration,
            location=0,
            modifier=0,
            bitvector=int(AffectFlag.POISON),
        )
    )


# ---------------------------------------------------------------------------
# Reset global state between tests
# ---------------------------------------------------------------------------


def setup_function(_):
    character_registry.clear()
    events.clear()
    weather.sky = SkyState.CLOUDLESS
    weather.mmhg = 1016
    weather.change = 0
    gl._pulse_counter = 0
    gl._point_counter = 0
    gl._violence_counter = 0
    gl._area_counter = 0
    gl._AUTOSAVE_ROTATION = 0
    object_registry.clear()
    room_registry.clear()


# ---------------------------------------------------------------------------
# Regen / tick
# ---------------------------------------------------------------------------


def test_regen_tick_increases_resources():
    _, room = _make_room(10, "Inn")
    ch = _make_char(
        "Bob",
        hit=5,
        max_hit=10,
        mana=3,
        max_mana=10,
        move=4,
        max_move=10,
        ch_class=3,
        pcdata=PCData(condition=[48, 48, 48, 48]),
        perm_stat=[13, 13, 13, 13, 13],
        room=room,
    )
    pulses = get_pulse_tick()

    game_tick()
    assert ch.hit == 8 and ch.mana == 4 and ch.move == 10

    for _ in range(max(0, pulses - 1)):
        game_tick()
    assert ch.hit == 8 and ch.mana == 4 and ch.move == 10

    game_tick()
    assert ch.hit == 10 and ch.mana == 5 and ch.move == 10


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------


def test_weather_pressure_and_sky_transitions(monkeypatch):
    dice_rolls = iter([4, 2, 12] * 5)
    bit_rolls = iter([0, 0, 0, 0, 0])
    monkeypatch.setattr(rng_mm, "dice", lambda *_: next(dice_rolls))
    monkeypatch.setattr(rng_mm, "number_bits", lambda *_: next(bit_rolls))

    time_info.month = 0
    weather.sky = SkyState.CLOUDLESS
    weather.mmhg = 1016
    weather.change = 0

    weather_tick()
    assert weather.sky == SkyState.CLOUDY
    assert weather.change == -12
    assert weather.mmhg == 1004

    weather_tick()
    assert weather.sky == SkyState.CLOUDY
    assert weather.mmhg == 992

    weather_tick()
    assert weather.sky == SkyState.RAINING
    assert weather.mmhg == 980

    weather_tick()
    assert weather.sky == SkyState.LIGHTNING
    assert weather.mmhg == 968

    weather_tick()
    assert weather.sky == SkyState.LIGHTNING
    assert weather.mmhg == 960


def test_weather_broadcasts_outdoor_characters(monkeypatch):
    _, outside = _make_room(101, "Field")
    _, inside = _make_room(102, "Field", flags=int(RoomFlag.ROOM_INDOORS))
    _, sleepy_room = _make_room(103, "Field")

    awake_outdoor = _make_char("Scout", room=outside)
    awake_indoor = _make_char("Hermit", room=inside)
    asleep_outdoor = _make_char("Sleeper", position=Position.SLEEPING, room=sleepy_room)

    time_info.month = 0
    weather.sky = SkyState.CLOUDLESS
    weather.mmhg = 980
    weather.change = 0

    monkeypatch.setattr(rng_mm, "dice", lambda *_: 0)
    monkeypatch.setattr(rng_mm, "number_bits", lambda *_: 1)

    weather_tick()

    assert awake_outdoor.messages == ["The sky is getting cloudy.\r\n"]
    assert not awake_indoor.messages
    assert not asleep_outdoor.messages


# ---------------------------------------------------------------------------
# Timed events
# ---------------------------------------------------------------------------


def test_timed_event_fires_after_delay():
    triggered: list[int] = []
    schedule_event(2, lambda: triggered.append(1))
    game_tick()
    assert not triggered
    game_tick()
    assert triggered == [1]


# ---------------------------------------------------------------------------
# Pulse ordering
# ---------------------------------------------------------------------------


def test_point_pulse_emits_tick_wiznet_before_updates(monkeypatch):
    gl._pulse_counter = 0
    gl._point_counter = 1
    gl._area_counter = 999999
    gl._music_counter = 999999
    gl._mobile_counter = 999999
    gl._violence_counter = 999999

    calls: list[object] = []

    def fake_wiznet(message, sender=None, obj=None, flag=None, flag_skip=None, min_level=0):
        calls.append(("wiznet", message, flag))

    monkeypatch.setattr(gl, "wiznet", fake_wiznet)
    monkeypatch.setattr(gl, "time_tick", lambda: calls.append("time_tick"))
    monkeypatch.setattr(gl, "weather_tick", lambda: calls.append("weather_tick"))
    monkeypatch.setattr(gl, "char_update", lambda: calls.append("char_update"))
    monkeypatch.setattr(gl, "obj_update", lambda: calls.append("obj_update"))
    monkeypatch.setattr(gl, "pump_idle", lambda: calls.append("pump_idle"))
    monkeypatch.setattr(gl, "event_tick", lambda: calls.append("event_tick"))
    monkeypatch.setattr(gl, "aggressive_update", lambda: calls.append("aggressive_update"))

    game_tick()

    assert calls[0] == ("wiznet", "TICK!", WiznetFlag.WIZ_TICKS)
    assert calls[1:6] == ["time_tick", "weather_tick", "char_update", "obj_update", "pump_idle"]


def test_violence_update_waits_for_pulse_violence(monkeypatch):
    room = object()
    attacker = _make_char("Attacker", position=Position.FIGHTING)
    victim = _make_char("Victim", position=Position.FIGHTING)
    attacker.room = room
    victim.room = room
    attacker.fighting = victim
    victim.fighting = attacker

    gl._pulse_counter = 0
    gl._point_counter = 999999
    gl._area_counter = 999999
    gl._music_counter = 999999
    gl._mobile_counter = 999999
    gl._violence_counter = get_pulse_violence()

    calls: list[int] = []
    monkeypatch.setattr("mud.combat.engine.multi_hit", lambda ch, vic, dt=None: calls.append(gl._pulse_counter))
    monkeypatch.setattr("mud.combat.engine.stop_fighting", lambda ch, both=False: None)

    for _ in range(get_pulse_violence() - 1):
        game_tick()
    assert calls == []

    game_tick()
    assert calls == [get_pulse_violence(), get_pulse_violence()]


# ---------------------------------------------------------------------------
# Mobile AI — aggression
# ---------------------------------------------------------------------------


def test_aggressive_mobile_attacks_player(monkeypatch):
    _, room = _make_room(42, "Arena")
    hero = _make_char("Hero", level=5, hit=20, max_hit=20, mana=10, max_mana=10, move=10, max_move=10, room=room)
    _make_npc("Brute", level=5, hit=20, max_hit=20, act=int(ActFlag.AGGRESSIVE), room=room)

    monkeypatch.setattr(rng_mm, "number_bits", lambda _: 1)

    game_tick()

    brute = character_registry[-1]
    assert brute.fighting is hero
    assert hero.fighting is brute


# ---------------------------------------------------------------------------
# Mobile AI — mobile_update
# ---------------------------------------------------------------------------


def test_mobile_update_runs_random_trigger(monkeypatch):
    _, room = _make_room(200, "Shrine")
    oracle = _make_npc("Oracle", room=room)

    calls: list[Character] = []
    monkeypatch.setattr(mobprog, "mp_delay_trigger", lambda mob: False)
    monkeypatch.setattr(mobprog, "mp_random_trigger", lambda mob: calls.append(mob) or True)

    mobile_update()

    assert calls == [oracle]
    assert oracle.room is room


def test_mobile_update_mobprog_default_position_gate(monkeypatch):
    """Mobprog triggers fire only while mob is at default_pos; non-standing
    mobs skip scavenging afterward."""
    _, room = _make_room(202, "Shrine")

    resting_guard = _make_npc(
        "Resting Guard",
        position=Position.RESTING,
        default_pos=Position.STANDING,
        act=int(ActFlag.SCAVENGER),
        mprog_delay=1,
        room=room,
    )
    sleeping_oracle = _make_npc(
        "Sleeping Oracle",
        position=Position.SLEEPING,
        act=int(ActFlag.SCAVENGER),
        room=room,
    )

    relic = Object(
        instance_id=None,
        prototype=ObjIndex(vnum=0, item_type=int(ItemType.TRASH), short_descr="silver relic"),
        wear_flags=int(WearFlag.TAKE),
        cost=50,
    )
    room.add_object(relic)

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(mobprog, "mp_delay_trigger", lambda mob: calls.append(("delay", mob.name)) or False)
    monkeypatch.setattr(mobprog, "mp_random_trigger", lambda mob: calls.append(("random", mob.name)) or False)
    monkeypatch.setattr(rng_mm, "number_bits", lambda _: 0)

    mobile_update()

    assert calls == [("delay", "Sleeping Oracle"), ("random", "Sleeping Oracle")]
    assert relic in room.contents
    assert relic not in resting_guard.inventory
    assert relic not in sleeping_oracle.inventory


def test_mobile_update_scavenges_room_loot(monkeypatch):
    _, room = _make_room(201, "Dump")
    scavenger = _make_npc(
        "Picker",
        act=int(ActFlag.SCAVENGER),
        carry_number=0,
        carry_weight=0,
        room=room,
    )

    cheap = Object(
        instance_id=None,
        prototype=ObjIndex(vnum=0, item_type=int(ItemType.TRASH), short_descr="tin can"),
        wear_flags=int(WearFlag.TAKE),
        cost=5,
    )
    pricey = Object(
        instance_id=None,
        prototype=ObjIndex(vnum=0, item_type=int(ItemType.TRASH), short_descr="bright gem"),
        wear_flags=int(WearFlag.TAKE),
        cost=25,
    )
    room.add_object(cheap)
    room.add_object(pricey)

    def fake_number_bits(width: int) -> int:
        if width == 6:
            return 0  # scavenge fires
        if width == 3:
            return 1
        if width == 5:
            return 6
        return 0

    monkeypatch.setattr(rng_mm, "number_bits", fake_number_bits)

    mobile_update()

    assert pricey in scavenger.inventory
    assert pricey.carried_by is scavenger
    assert cheap in room.contents
    assert pricey not in room.contents
    assert scavenger.carry_number == 1


def test_scavenger_pickup_dispatches_trig_act(monkeypatch):
    """Scavenger pickup broadcast must dispatch TRIG_ACT to NPC observers."""
    _, room = _make_room(202, "Dump")
    _make_npc("Picker", act=int(ActFlag.SCAVENGER), carry_number=0, carry_weight=0, room=room)

    gem = Object(
        instance_id=None,
        prototype=ObjIndex(vnum=0, item_type=int(ItemType.TRASH), short_descr="bright gem"),
        wear_flags=int(WearFlag.TAKE),
        cost=25,
    )
    room.add_object(gem)

    _, fired = _make_trig_act_listener(monkeypatch, room, vnum=9801, name="watcher")

    def fake_number_bits(width: int) -> int:
        if width == 6:
            return 0
        if width == 3:
            return 1
        if width == 5:
            return 6
        return 0

    monkeypatch.setattr(rng_mm, "number_bits", fake_number_bits)

    mobile_update()

    assert any("bright gem" in msg for msg, _ in fired), (
        "scavenger pickup must dispatch mp_act_trigger with '$n gets $p.'"
    )


def test_mobile_update_refreshes_shopkeeper_wealth(monkeypatch):
    _, room = _make_room(305, "Market")

    shop_proto = MobIndex(vnum=5000, wealth=6000)
    shop_proto.pShop = Shop(keeper=shop_proto.vnum)

    keeper = _make_npc("Clerk", gold=0, silver=50, room=room)
    keeper.prototype = shop_proto

    rolls = iter([20, 20, 10, 10])
    monkeypatch.setattr(rng_mm, "number_range", lambda *_: next(rolls))

    mobile_update()
    assert keeper.gold == 0
    assert keeper.silver == 52

    mobile_update()
    assert keeper.gold == 0
    assert keeper.silver == 53


# ---------------------------------------------------------------------------
# char_update — conditions, idle, autosave
# ---------------------------------------------------------------------------


def test_char_update_applies_conditions(monkeypatch):
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 75)

    _, room = _make_room(42, "Rest")
    hero = _make_char(
        "Hero",
        level=5,
        ch_class=3,
        hit=5,
        max_hit=10,
        mana=3,
        max_mana=10,
        move=4,
        max_move=10,
        size=int(Size.MEDIUM),
        pcdata=PCData(condition=[1, 2, 1, 1]),
        perm_stat=[13, 13, 13, 13, 13],
        room=room,
    )

    effect = SpellEffect(name="armor", duration=1, ac_mod=-10, wear_off_message="You feel less protected.")
    hero.apply_spell_effect(effect)

    char_update()

    assert hero.hit == 9
    assert hero.mana == 4
    assert hero.move == 10
    assert hero.pcdata.condition == [0, 0, 0, 0]
    assert "armor" in hero.spell_effects
    assert hero.spell_effects["armor"].duration == 0
    assert hero.messages == [
        "You are sober.",
        "You are thirsty.",
        "You are hungry.",
    ]


def test_char_update_idles_linkdead():
    _, room = _make_room(100, "Void")
    limbo = Room(vnum=ROOM_VNUM_LIMBO, area=Area(name="Limbo"))
    room_registry[limbo.vnum] = limbo

    idle = _make_char(
        "Sleeper",
        level=10,
        hit=20,
        max_hit=20,
        mana=15,
        max_mana=15,
        move=10,
        max_move=10,
        pcdata=PCData(condition=[48, 48, 48, 48]),
        timer=11,
        room=room,
    )
    idle.desc = None

    watcher = _make_char(
        "Watcher",
        pcdata=PCData(condition=[48, 48, 48, 48]),
        room=room,
    )
    watcher.desc = object()

    char_update()

    assert idle.room is limbo
    assert idle.was_in_room is room
    assert idle in limbo.people
    assert idle not in room.people
    assert idle.messages[-1] == "You disappear into the void."
    assert "Sleeper disappears into the void." in watcher.messages


def test_char_update_autosaves_on_rotation(monkeypatch):
    _, room = _make_room(501, "Inn")

    hero = _make_char(
        "Saver",
        level=10,
        pcdata=PCData(condition=[48, 48, 48, 48]),
        room=room,
    )
    hero.desc = SimpleNamespace(descriptor_id=30)

    bystander = _make_char(
        "Skipper",
        level=10,
        pcdata=PCData(condition=[48, 48, 48, 48]),
        room=room,
    )
    bystander.desc = SimpleNamespace(descriptor_id=17)

    saved: list[Character] = []
    monkeypatch.setattr(gl, "save_character", lambda ch: saved.append(ch))

    gl._AUTOSAVE_ROTATION = gl._AUTOSAVE_WINDOW - 1
    char_update()

    assert saved == [hero]


def test_char_update_auto_quits_linkdead(monkeypatch):
    _, room = _make_room(200, "LimboLand")
    limbo = Room(vnum=ROOM_VNUM_LIMBO, area=Area(name="Limbo"))
    room_registry[limbo.vnum] = limbo

    ghost = _make_char(
        "Ghost",
        level=10,
        pcdata=PCData(condition=[48, 48, 48, 48]),
    )
    ghost.timer = 31
    ghost.room = limbo
    ghost.was_in_room = room
    limbo.add_character(ghost)

    saved: list[Character] = []
    monkeypatch.setattr(gl, "save_character", lambda ch: saved.append(ch))

    char_update()

    assert saved == [ghost]
    assert ghost not in character_registry
    assert ghost.room is None


# ---------------------------------------------------------------------------
# char_update — light decay
# ---------------------------------------------------------------------------


def _make_torch(owner, *, name="bronze torch"):
    """Create a lit torch worn by *owner*."""
    torch = Object(
        instance_id=None,
        prototype=ObjIndex(vnum=0, item_type=int(ItemType.LIGHT), short_descr=name),
    )
    torch.value = [0, 0, 1]
    torch.wear_loc = int(WearLocation.LIGHT)
    torch.carried_by = owner
    object_registry.append(torch)
    owner.equipment[int(WearLocation.LIGHT)] = torch
    return torch


def test_light_decay_extinguishes_worn_torch():
    _, room = _make_room(300, "Cavern", light=2)

    hero = _make_char("Torchbearer", level=5, pcdata=PCData(condition=[48, 48, 48, 48]), room=room)
    watcher = _make_char("Watcher", level=5, pcdata=PCData(condition=[48, 48, 48, 48]), room=room)
    torch = _make_torch(hero)

    char_update()

    assert hero.equipment == {}
    assert torch not in object_registry
    assert room.light == 1
    assert "bronze torch flickers and goes out." in hero.messages
    assert "Bronze torch goes out." in watcher.messages


def test_char_update_decays_light_before_lethal_poison_tick():
    _, room = _make_room(301, "Cavern", light=2)

    hero = _make_char(
        "Poisoned",
        level=5,
        hit=1,
        max_hit=1,
        mana=1,
        max_mana=1,
        move=1,
        max_move=1,
        pcdata=PCData(condition=[48, 48, 48, 48]),
        room=room,
    )
    watcher = _make_char("Watcher", level=5, pcdata=PCData(condition=[48, 48, 48, 48]), room=room)
    torch = _make_torch(hero, name="brass lantern")

    # Worn-light decay runs before affect-tick poison damage,
    # even when the poison tick is lethal.
    _apply_poison(hero, level=120, duration=-1)

    char_update()

    assert room.light == 1
    assert torch not in object_registry
    assert "brass lantern flickers and goes out." in hero.messages
    assert "Brass lantern goes out." in watcher.messages
    assert "Poisoned shivers and suffers." in watcher.messages


# ---------------------------------------------------------------------------
# char_update — out-of-zone mob extraction
# ---------------------------------------------------------------------------


def test_char_update_extracts_out_of_zone_mob(monkeypatch):
    area_home = Area(name="Town")
    area_foreign = Area(name="Dungeon")
    home_room = Room(vnum=400, area=area_home)
    away_room = Room(vnum=401, area=area_foreign)
    room_registry[home_room.vnum] = home_room
    room_registry[away_room.vnum] = away_room

    wanderer = _make_npc(
        "Rover",
        short_descr="Rover",
        default_pos=Position.STANDING,
        room=away_room,
    )
    wanderer.zone = area_home

    watcher = _make_char("Watcher", pcdata=PCData(condition=[48, 48, 48, 48]), room=away_room)

    monkeypatch.setattr(rng_mm, "number_percent", lambda: 0)

    char_update()

    assert wanderer.room is None
    assert wanderer not in character_registry
    assert wanderer not in home_room.people
    assert wanderer not in away_room.people
    assert "Rover wanders on home." in watcher.messages


def test_wanders_home_dispatches_trig_act(monkeypatch):
    """NPC wanders-home broadcast must dispatch TRIG_ACT to NPC observers."""
    area_home = Area(name="Town2")
    area_foreign = Area(name="Dungeon2")
    home_room = Room(vnum=405, area=area_home)
    away_room = Room(vnum=406, area=area_foreign)
    room_registry[home_room.vnum] = home_room
    room_registry[away_room.vnum] = away_room

    wanderer = _make_npc(
        "Drifter",
        short_descr="Drifter",
        default_pos=Position.STANDING,
        room=away_room,
    )
    wanderer.zone = area_home

    _, fired = _make_trig_act_listener(monkeypatch, away_room, vnum=9802, name="listener")

    monkeypatch.setattr(rng_mm, "number_percent", lambda: 0)

    char_update()

    assert any("wanders on home" in msg for msg, _ in fired), (
        "wanders-on-home must dispatch mp_act_trigger to NPC observers"
    )


# ---------------------------------------------------------------------------
# char_update — poison tick
# ---------------------------------------------------------------------------


def test_poison_shiver_dispatches_trig_act(monkeypatch):
    """Poison tick broadcast must dispatch TRIG_ACT to NPC observers."""
    _, room = _make_room(407, "Swamp")

    victim = _make_char(
        "Vic",
        hit=50,
        max_hit=50,
        pcdata=PCData(condition=[48, 48, 48, 48]),
        room=room,
    )
    _apply_poison(victim)

    _, fired = _make_trig_act_listener(monkeypatch, room, vnum=9803, name="watcher")

    char_update()

    assert any("shivers" in msg for msg, _ in fired), "poison broadcast must dispatch mp_act_trigger"


# ---------------------------------------------------------------------------
# obj_update — corpse decay
# ---------------------------------------------------------------------------


def test_obj_update_decays_corpse():
    _, room = _make_room(200, "Battlefield")

    _make_char("Onlooker", pcdata=PCData(condition=[48, 48, 48, 48]), room=room)

    proto = ObjIndex(vnum=1, short_descr="orc corpse", item_type=int(ItemType.CORPSE_NPC))
    corpse = Object(instance_id=None, prototype=proto, timer=1)
    corpse.in_room = room
    room.contents.append(corpse)
    object_registry.append(corpse)

    obj_update()

    assert corpse not in object_registry
    assert corpse not in room.contents
    assert "Orc corpse decays into dust." in room.people[0].messages


def test_obj_update_decay_dispatches_trig_act(monkeypatch):
    """Object decay broadcast must dispatch TRIG_ACT to NPC observers."""
    _, room = _make_room(207, "Ruins")
    _make_char("First", pcdata=PCData(condition=[48, 48, 48, 48]), room=room)
    listener, fired = _make_trig_act_listener(monkeypatch, room, vnum=9804, name="watcher")

    corpse = Object(
        instance_id=None,
        prototype=ObjIndex(vnum=2, short_descr="kobold corpse", item_type=int(ItemType.CORPSE_NPC)),
        timer=1,
    )
    room.add_object(corpse)
    object_registry.append(corpse)

    obj_update()

    assert any("Kobold corpse decays into dust" in msg for msg, _ in fired), "object decay must dispatch mp_act_trigger"
    # The act() loop passes room.people[0] (the first rch) as the actor.
    assert any(actor is room.people[0] for _, actor in fired), "object decay TRIG_ACT actor must be a room observer"


# ---------------------------------------------------------------------------
# obj_update — object affect wear-off
# ---------------------------------------------------------------------------


def test_object_affect_wear_off_dispatches_trig_act(monkeypatch):
    """Object affect wear-off broadcast must dispatch TRIG_ACT."""
    _, room = _make_room(208, "Vault")
    _make_char("First", pcdata=PCData(condition=[48, 48, 48, 48]), room=room)
    listener, fired = _make_trig_act_listener(monkeypatch, room, vnum=9805, name="watcher")

    amulet = Object(
        instance_id=None,
        prototype=ObjIndex(vnum=3, short_descr="silver amulet", item_type=int(ItemType.TREASURE)),
        timer=0,
    )
    room.add_object(amulet)
    affect = AffectData(type="bless", level=10, duration=0, location=0, modifier=0, bitvector=0)
    affect.wear_off_message = "$p stops glowing."
    amulet.affected = [affect]

    gl._tick_object_affects(amulet)

    assert any("Silver amulet stops glowing" in msg for msg, _ in fired), (
        "object affect wear-off must dispatch mp_act_trigger"
    )
    # The act() loop passes room.people[0] (the first rch) as the actor.
    assert any(actor is room.people[0] for _, actor in fired), "wear-off TRIG_ACT actor must be a room observer"


def test_carried_object_affect_wear_off_is_to_char_only(monkeypatch):
    """Carried object affect wear-off is TO_CHAR only."""
    _, room = _make_room(209, "Vault")
    carrier = _make_char("Carrier", pcdata=PCData(condition=[48, 48, 48, 48]), room=room)
    _, fired = _make_trig_act_listener(monkeypatch, room, vnum=9806, name="watcher")

    amulet = Object(
        instance_id=None,
        prototype=ObjIndex(vnum=4, short_descr="silver amulet", item_type=int(ItemType.TREASURE)),
        timer=0,
    )
    carrier.add_object(amulet)
    affect = AffectData(type="bless", level=10, duration=0, location=0, modifier=0, bitvector=0)
    affect.wear_off_message = "$p stops glowing."
    amulet.affected = [affect]

    gl._tick_object_affects(amulet)

    assert "Silver amulet stops glowing." in carrier.messages
    assert not fired


# ---------------------------------------------------------------------------
# obj_update — floating container spill
# ---------------------------------------------------------------------------


def test_obj_update_spills_floating_container():
    _, room = _make_room(300, "Treasure")

    _make_char("Collector", pcdata=PCData(condition=[48, 48, 48, 48]), room=room)

    chest = Object(
        instance_id=None,
        prototype=ObjIndex(vnum=0, item_type=int(ItemType.CONTAINER), short_descr="drifting chest"),
        wear_flags=int(WearFlag.WEAR_FLOAT),
        wear_loc=int(WearLocation.FLOAT),
        timer=1,
    )
    gem = Object(
        instance_id=None,
        prototype=ObjIndex(vnum=0, item_type=int(ItemType.GEM), short_descr="shiny gem"),
        timer=0,
    )
    chest.contained_items.append(gem)
    gem.in_obj = chest

    room.contents.append(chest)
    chest.in_room = room
    object_registry.extend([chest, gem])

    obj_update()

    assert chest not in object_registry
    assert chest not in room.contents
    assert gem in room.contents
    assert gem.in_room is room
    assert "Drifting chest flickers and vanishes, spilling its contents on the floor." in room.people[0].messages
