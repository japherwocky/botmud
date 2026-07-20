"""Tests for shop commands: buy, sell, list, value."""

import re
from contextlib import contextmanager

from mud.commands.dispatcher import process_command
from mud.commands.shop import _get_cost, _obj_to_keeper, do_buy, do_list
from mud.math.c_compat import c_div, c_mod
from mud.models.character import Character, character_registry
from mud.models.constants import (
    ITEM_HAD_TIMER,
    ITEM_INVENTORY,
    ITEM_INVIS,
    ITEM_NODROP,
    ITEM_SELL_EXTRACT,
    ActFlag,
    AffectFlag,
    CommFlag,
    ItemType,
    RoomFlag,
    WearLocation,
)
from mud.models.mob import MobIndex
from mud.models.object import Object
from mud.models.room import Room
from mud.registry import mob_registry, room_registry, shop_registry
from mud.spawning.mob_spawner import spawn_mob
from mud.spawning.obj_spawner import spawn_object
from mud.spawning.templates import MobInstance
from mud.time import time_info
from mud.utils import rng_mm
from mud.utils.act import capitalize_act_line
from mud.world import create_test_character
from mud.world.movement import can_carry_n, can_carry_w

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _total_wealth(char: Character) -> int:
    return int(char.gold) * 100 + int(char.silver)


def _create_shop_character(name: str, room_vnum: int) -> Character:
    char = create_test_character(name, room_vnum)
    char.level = 20
    char.perm_stat = [20, 15, 15, 15, 15]
    char.mod_stat = [0, 0, 0, 0, 0]
    return char


def _find_keeper(char, keeper_vnum=3002):
    """Locate the shopkeeper in char's room, spawning one if missing."""
    keeper = next(
        (
            p
            for p in char.room.people
            if getattr(p, "prototype", None) and p.prototype.vnum in shop_registry
        ),
        None,
    )
    if keeper is None:
        keeper = spawn_mob(keeper_vnum)
        assert keeper is not None
        keeper.move_to_room(char.room)
    return keeper


def _clean_keeper_inventory(keeper, exclude="lantern"):
    """Strip items whose prototype short_descr contains *exclude*."""
    keeper.inventory = [
        obj
        for obj in getattr(keeper, "inventory", [])
        if exclude
        not in (getattr(obj.prototype, "short_descr", "") or "").lower()
    ]


def _ensure_lantern(keeper):
    """Guarantee a hooded brass lantern is in keeper stock; return it."""
    match = next(
        (
            obj
            for obj in keeper.inventory
            if (obj.short_descr or "").lower().startswith("a hooded brass lantern")
        ),
        None,
    )
    if match is None:
        match = spawn_object(3031)
        assert match is not None
        match.prototype.short_descr = "a hooded brass lantern"
        keeper.inventory.append(match)
    return match


@contextmanager
def shop_hour(hour=10):
    """Temporarily set the in-game clock for business-hours tests."""
    prev = time_info.hour
    try:
        time_info.hour = hour
        yield
    finally:
        time_info.hour = prev

# ---------------------------------------------------------------------------
# Pet-shop helper (self-contained – uses its own isolated registries)
# ---------------------------------------------------------------------------

def _setup_pet_shop(proto_level=5):
    room_registry.clear()
    mob_registry.clear()
    character_registry.clear()

    storefront = Room(vnum=9600, name="Pet Shop Lobby")
    storefront.room_flags = int(RoomFlag.ROOM_PET_SHOP)
    kennel = Room(vnum=9601, name="Kennel")
    room_registry[storefront.vnum] = storefront
    room_registry[kennel.vnum] = kennel

    proto = MobIndex(
        vnum=9602, short_descr="a cuddly companion", player_name="companion pet"
    )
    proto.description = "A bright-eyed pet watches you expectantly.\n"
    proto.level = proto_level
    proto.act_flags = int(ActFlag.PET)
    mob_registry[proto.vnum] = proto

    kennel.add_mob(MobInstance.from_prototype(proto))

    buyer = Character(name="Buyer", level=10, is_npc=False)
    buyer.gold = 5
    buyer.silver = 0
    storefront.add_character(buyer)
    character_registry.append(buyer)

    return buyer, storefront, kennel, proto

# ---------------------------------------------------------------------------
# Buy tests
# ---------------------------------------------------------------------------

def test_buy_from_grocer():
    char = _create_shop_character("Buyer", 3010)
    char.gold = 100
    keeper = _find_keeper(char)
    with shop_hour():
        _ensure_lantern(keeper)
        listing = process_command(char, "list")
        assert "[Lv Price Qty] Item" in listing
        lantern_line = next(
            line
            for line in listing.splitlines()
            if "hooded brass lantern" in line
        )
        assert "--" in lantern_line
        assert "112" in lantern_line
        buy_output = process_command(char, "buy lantern")
        assert "buy a hooded brass lantern" in buy_output.lower()
        assert char.gold == 98
        assert char.silver == 88
        assert any(
            (obj.short_descr or "").lower().startswith("a hooded brass lantern")
            for obj in char.inventory
        )


def test_buy_uses_gold_and_silver():
    char = _create_shop_character("Buyer", 3010)
    char.gold = 0
    char.silver = 6050
    keeper = _find_keeper(char)
    with shop_hour():
        _ensure_lantern(keeper)
        before = _total_wealth(char)
        buy_output = process_command(char, "buy lantern")
        assert "buy a hooded brass lantern" in buy_output.lower()
        match = re.search(r"for (\d+) silver", buy_output)
        assert match is not None
        price_paid = int(match.group(1))
        assert _total_wealth(char) == before - price_paid
        assert char.gold == 0


def test_buy_rejects_items_above_level():
    char = _create_shop_character("Newbie", 3010)
    char.gold = 200
    char.level = 1
    keeper = _find_keeper(char)
    with shop_hour():
        weapon = spawn_object(3032)
        assert weapon is not None
        weapon.prototype.short_descr = "a massive greatsword"
        weapon.prototype.cost = 20
        weapon.prototype.level = 10
        keeper.inventory.append(weapon)
        before_gold = char.gold
        response = process_command(char, "buy greatsword")
        keeper_name = (
            getattr(keeper, "short_descr", None)
            or getattr(keeper, "name", None)
            or "The shopkeeper"
        )
        weapon_name = (
            getattr(weapon, "short_descr", None)
            or getattr(weapon, "name", None)
            or "it"
        )
        assert response == capitalize_act_line(
            f"{keeper_name} tells you 'You can't use {weapon_name} yet'."
        )
        assert char.gold == before_gold
        assert not any(
            "greatsword" in (obj.short_descr or "").lower()
            for obj in char.inventory
        )
        assert any(
            "greatsword" in (obj.short_descr or "").lower()
            for obj in keeper.inventory
        )


def test_buy_respects_carry_limits():
    char = _create_shop_character("Packrat", 3010)
    char.gold = 200
    char.silver = 0
    keeper = _find_keeper(char)
    with shop_hour():
        lantern = _ensure_lantern(keeper)
        proto = getattr(lantern, "prototype", None)
        if proto is not None:
            proto.weight = max(int(getattr(proto, "weight", 0) or 0), 5)
        before_gold = char.gold
        before_silver = char.silver

        def lantern_count():
            return sum(
                1
                for obj in keeper.inventory
                if (obj.short_descr or obj.name or "")
                .lower()
                .startswith("a hooded brass lantern")
            )

        baseline_count = lantern_count()
        limit_number = can_carry_n(char)
        limit_weight = can_carry_w(char)

        # Slot-limit denial
        char.carry_number = limit_number
        char.carry_weight = 0
        response = process_command(char, "buy lantern")
        assert response == "You can't carry that many items."
        assert char.gold == before_gold
        assert char.silver == before_silver
        assert not any(
            (obj.short_descr or obj.name or "")
            .lower()
            .startswith("a hooded brass lantern")
            for obj in char.inventory
        )
        assert lantern_count() == baseline_count

        # Weight-limit denial
        char.carry_number = limit_number - 1
        char.carry_weight = limit_weight
        response = process_command(char, "buy lantern")
        assert response == "You can't carry that much weight."
        assert char.gold == before_gold
        assert char.silver == before_silver
        assert not any(
            (obj.short_descr or obj.name or "")
            .lower()
            .startswith("a hooded brass lantern")
            for obj in char.inventory
        )
        assert lantern_count() == baseline_count


def test_buy_denied_when_coins_exceed_weight_cap():
    char = create_test_character("HeavyPurse", 3010)
    char.gold = 1000
    char.silver = 0
    char.carry_number = 0
    char.carry_weight = 0
    keeper = _find_keeper(char)
    with shop_hour():
        _ensure_lantern(keeper)
        assert can_carry_w(char) == 100
        response = process_command(char, "buy lantern")
        assert response == "You can't carry that much weight."
        assert char.gold == 1000
        assert char.silver == 0
        assert not any(
            (obj.short_descr or obj.name or "")
            .lower()
            .startswith("a hooded brass lantern")
            for obj in char.inventory
        )


def test_buy_preserves_infinite_stock():
    char = _create_shop_character("Quartermaster", 3010)
    char.gold = 200
    keeper = _find_keeper(char)
    with shop_hour():
        ration = spawn_object(3031)
        assert ration is not None
        ration.prototype.short_descr = "a stack of ration packs"
        ration.prototype.cost = 25
        ration.prototype.extra_flags = (
            int(getattr(ration.prototype, "extra_flags", 0) or 0)
            | int(ITEM_INVENTORY)
        )
        ration.extra_flags = (
            int(getattr(ration, "extra_flags", 0) or 0) | int(ITEM_INVENTORY)
        )
        ration.timer = 12
        keeper.inventory.append(ration)

        before_wealth = _total_wealth(char)
        baseline_ids = {id(obj) for obj in keeper.inventory}

        response = process_command(char, "buy ration")
        assert "buy a stack of ration packs" in response.lower()
        match = re.search(r"for (\d+) silver", response)
        assert match is not None
        price_paid = int(match.group(1))
        assert _total_wealth(char) == before_wealth - price_paid
        assert {id(obj) for obj in keeper.inventory} == baseline_ids
        assert ration in keeper.inventory

        purchased = next(
            obj
            for obj in char.inventory
            if (obj.short_descr or obj.name or "")
            .lower()
            .startswith("a stack of ration packs")
        )
        assert purchased is not ration
        assert purchased.prototype is ration.prototype
        assert purchased.timer == 0
        assert int(getattr(purchased, "extra_flags", 0) or 0) & int(ITEM_HAD_TIMER) == 0


def test_buy_handles_multiple_inventory_copies():
    char = _create_shop_character("Quartermaster", 3010)
    char.gold = 300
    keeper = _find_keeper(char)
    with shop_hour():

        def _make():
            obj = spawn_object(3031)
            assert obj is not None
            p = obj.prototype
            p.short_descr = "a stack of ration packs"
            p.cost = 25
            p.extra_flags = (
                int(getattr(p, "extra_flags", 0) or 0) | int(ITEM_INVENTORY)
            )
            obj.extra_flags = (
                int(getattr(obj, "extra_flags", 0) or 0) | int(ITEM_INVENTORY)
            )
            obj.timer = 12
            return obj

        ration_a = _make()
        ration_b = _make()
        keeper.inventory.extend([ration_a, ration_b])
        baseline_ids = {id(ration_a), id(ration_b)}

        def buy_one():
            before = _total_wealth(char)
            resp = process_command(char, "buy ration")
            assert "buy a stack of ration packs" in resp.lower()
            m = re.search(r"for (\d+) silver", resp)
            assert m is not None
            price = int(m.group(1))
            assert _total_wealth(char) == before - price
            bought = [
                obj
                for obj in char.inventory
                if (obj.short_descr or obj.name or "")
                .lower()
                .startswith("a stack of ration packs")
            ][-1]
            assert bought.prototype is ration_a.prototype
            assert bought.timer == 0
            assert int(getattr(bought, "extra_flags", 0) or 0) & int(ITEM_HAD_TIMER) == 0
            return bought

        first = buy_one()
        second = buy_one()
        assert first is not ration_a
        assert second is not ration_b
        remaining = {
            id(obj)
            for obj in keeper.inventory
            if (obj.short_descr or obj.name or "")
            .lower()
            .startswith("a stack of ration packs")
        }
        assert baseline_ids <= remaining


def test_buy_inventory_fallback_uses_original_object():
    char = _create_shop_character("Forager", 3010)
    char.gold = 200
    keeper = _find_keeper(char)
    with shop_hour():
        template = Object(instance_id=None, prototype=None)
        template.short_descr = "a rare ration pack"
        template.level = 0
        template.weight = 1
        template.cost = 30
        template.extra_flags = (
            int(getattr(template, "extra_flags", 0) or 0) | int(ITEM_INVENTORY)
        )
        template.timer = 9
        keeper.inventory.append(template)

        before_wealth = _total_wealth(char)
        response = process_command(char, "buy ration")
        assert "buy a rare ration pack" in response.lower()
        match = re.search(r"for (\d+) silver", response)
        assert match is not None
        price = int(match.group(1))
        assert price == 0
        assert _total_wealth(char) == before_wealth
        assert template not in keeper.inventory
        assert template in char.inventory
        assert template.timer == 0
        assert int(getattr(template, "extra_flags", 0) or 0) & int(ITEM_HAD_TIMER) == 0


def test_buy_multiple_items_from_inventory():
    char = _create_shop_character("BulkBuyer", 3010)
    char.gold = 5
    char.silver = 0
    keeper = _find_keeper(char)
    with shop_hour():
        keeper.inventory = []
        for _ in range(3):
            ration = spawn_object(3001)
            assert ration is not None
            ration.prototype.short_descr = "a ration pack"
            ration.short_descr = "a ration pack"
            ration.prototype.cost = 18
            keeper.inventory.append(ration)

        before_wealth = _total_wealth(char)
        response = process_command(char, "buy 3*ration")
        assert "buy a ration pack[3]" in response.lower()
        match = re.search(r"for (\d+) silver", response)
        assert match is not None
        total_price = int(match.group(1))
        assert total_price > 0
        assert _total_wealth(char) == before_wealth - total_price
        ration_count = sum(
            1
            for obj in char.inventory
            if (obj.short_descr or "").lower() == "a ration pack"
        )
        assert ration_count == 3
        assert (
            sum(
                1
                for obj in keeper.inventory
                if (obj.short_descr or "").lower() == "a ration pack"
            )
            == 0
        )


def test_buy_specific_stock_slot():
    char = _create_shop_character("TargetBuyer", 3010)
    char.gold = 5
    keeper = _find_keeper(char)
    with shop_hour():
        keeper.inventory = []
        items = []
        for _ in range(3):
            ration = spawn_object(3001)
            assert ration is not None
            ration.prototype.short_descr = "a ration pack"
            ration.short_descr = "a ration pack"
            ration.prototype.cost = 18
            keeper.inventory.append(ration)
            items.append(ration)

        before = _total_wealth(char)
        response = process_command(char, "buy 2.ration")
        assert "buy a ration pack" in response.lower()
        match = re.search(r"for (\d+) silver", response)
        assert match is not None
        paid = int(match.group(1))
        assert _total_wealth(char) == before - paid
        first, second, third = items
        assert any(existing is second for existing in char.inventory)
        assert any(existing is first for existing in keeper.inventory)
        assert all(existing is not second for existing in keeper.inventory)
        assert any(existing is third for existing in keeper.inventory)

# ---------------------------------------------------------------------------
# Sell tests
# ---------------------------------------------------------------------------

def test_sell_to_grocer():
    char = _create_shop_character("Seller", 3010)
    char.gold = 0
    keeper = _find_keeper(char)
    keeper.gold = 100
    keeper.silver = 0
    _clean_keeper_inventory(keeper)
    lantern = spawn_object(3031)
    assert lantern is not None
    lantern.prototype.item_type = int(ItemType.LIGHT)
    char.add_object(lantern)
    with shop_hour():
        sell_output = process_command(char, "sell lantern")
        assert "sell a hooded brass lantern" in sell_output.lower()
        match = re.search(r"for (\d+) silver", sell_output)
        assert match is not None
        price = int(match.group(1))
        assert _total_wealth(char) == price
        assert char.gold == price // 100
        assert char.silver == price % 100
        assert any(
            (obj.short_descr or "").lower().startswith("a hooded brass lantern")
            for obj in keeper.inventory
        )


def test_sell_awards_gold_and_silver():
    char = _create_shop_character("Seller", 3010)
    char.gold = 0
    char.silver = 25
    keeper = _find_keeper(char)
    keeper.gold = 100
    keeper.silver = 0
    _clean_keeper_inventory(keeper)
    lantern = spawn_object(3031)
    assert lantern is not None
    lantern.prototype.item_type = int(ItemType.LIGHT)
    char.add_object(lantern)
    with shop_hour():
        before = _total_wealth(char)
        sell_output = process_command(char, "sell lantern")
        assert "sell a hooded brass lantern" in sell_output.lower()
        match = re.search(r"for (\d+) silver", sell_output)
        assert match is not None
        price = int(match.group(1))
        assert _total_wealth(char) == before + price


def test_sell_reports_gold_and_silver():
    char = _create_shop_character("Merchant", 3010)
    char.gold = 0
    char.silver = 0
    keeper = _find_keeper(char)
    keeper.gold = 200
    keeper.silver = 50
    lantern = spawn_object(3031)
    assert lantern is not None
    lantern.prototype.item_type = int(ItemType.LIGHT)
    char.add_object(lantern)
    with shop_hour():
        response = process_command(char, "sell lantern")
        match = re.search(
            r"for (\d+) silver(?: and (\d+) gold piece(s?))?\.\Z", response
        )
        assert match is not None
        silver = int(match.group(1))
        gold = int(match.group(2)) if match.group(2) is not None else 0
        suffix = match.group(3) or ""
        total_price = silver + gold * 100
        assert _total_wealth(char) == total_price
        if gold:
            assert suffix == ("" if gold == 1 else "s")


def test_sell_respects_drop_and_visibility_gates():
    char = _create_shop_character("Seller", 3010)
    char.gold = 0
    char.silver = 0
    keeper = _find_keeper(char)
    keeper.gold = 200
    keeper.silver = 0
    _clean_keeper_inventory(keeper)

    nodrop_obj = None
    invis_obj = None
    try:
        with shop_hour():
            nodrop_obj = spawn_object(3031)
            assert nodrop_obj is not None
            nodrop_obj.extra_flags = int(ITEM_NODROP)
            nodrop_obj.prototype.item_type = int(ItemType.LIGHT)
            char.add_object(nodrop_obj)
            assert process_command(char, "sell lantern") == "You can't let go of it."
            assert _total_wealth(char) == 0
            char.remove_object(nodrop_obj)

            invis_obj = spawn_object(3031)
            assert invis_obj is not None
            invis_obj.extra_flags = int(ITEM_INVIS)
            invis_obj.prototype.item_type = int(ItemType.LIGHT)
            if len(invis_obj.value) > 2:
                invis_obj.value[2] = 0
            char.add_object(invis_obj)
            response = process_command(char, "sell lantern")
            keeper_name = (
                getattr(keeper, "short_descr", None)
                or getattr(keeper, "name", None)
                or "The shopkeeper"
            )
            assert response == capitalize_act_line(
                f"{keeper_name} doesn't see what you are offering."
            )
            assert _total_wealth(char) == 0
    finally:
        if nodrop_obj and nodrop_obj in char.inventory:
            char.remove_object(nodrop_obj)
        if invis_obj and invis_obj in char.inventory:
            char.remove_object(invis_obj)


def test_sell_sets_reply_after_missing_item():
    char = _create_shop_character("ReplyLess", 3010)
    char.gold = 0
    char.silver = 0
    keeper = _find_keeper(char)
    with shop_hour():
        response = process_command(char, "sell lantern")
        keeper_name = (
            getattr(keeper, "short_descr", None)
            or getattr(keeper, "name", None)
            or "The shopkeeper"
        )
        assert (
            capitalize_act_line(
                f"{keeper_name} tells you 'You don't have that item'."
            )
            == response
        )
        assert char.reply is keeper


def test_sell_extracts_and_resets_timer():
    char = _create_shop_character("Seller", 3010)
    char.gold = 0
    char.silver = 0
    keeper = _find_keeper(char)
    keeper.gold = 500
    keeper.silver = 0
    keeper.affected_by = 0
    _clean_keeper_inventory(keeper)

    with shop_hour():
        # SELL_EXTRACT item is destroyed
        obj = spawn_object(3031)
        assert obj is not None
        obj.extra_flags = int(ITEM_SELL_EXTRACT)
        obj.prototype.item_type = int(ItemType.LIGHT)
        char.add_object(obj)
        before = _total_wealth(char)
        assert "you sell" in process_command(char, "sell lantern").lower()
        assert obj not in keeper.inventory
        assert obj not in char.inventory
        assert _total_wealth(char) > before
        char.gold = 0
        char.silver = 0
        _clean_keeper_inventory(keeper)

        # Fresh object (timer=0) gets a random timer 50-100
        fresh = spawn_object(3031)
        assert fresh is not None
        fresh.timer = 0
        fresh.extra_flags = 0
        fresh.prototype.item_type = int(ItemType.LIGHT)
        char.add_object(fresh)
        assert "you sell" in process_command(char, "sell lantern").lower()
        assert fresh in keeper.inventory
        assert 50 <= fresh.timer <= 100
        assert not (int(fresh.extra_flags) & int(ITEM_HAD_TIMER))
        char.gold = 0
        char.silver = 0

        # Timer-bearing object preserves timer and sets HAD_TIMER
        timed = spawn_object(3031)
        assert timed is not None
        timed.timer = 12
        timed.extra_flags = 0
        timed.prototype.item_type = int(ItemType.LIGHT)
        char.add_object(timed)
        assert "you sell" in process_command(char, "sell lantern").lower()
        assert timed in keeper.inventory
        assert timed.timer == 12
        assert int(timed.extra_flags) & int(ITEM_HAD_TIMER)


def test_sell_haggle_applies_discount():
    char = _create_shop_character("Haggler", 3010)
    char.gold = 0
    char.silver = 0
    char.skills = {"haggle": 85}
    keeper = _find_keeper(char)
    keeper.gold = 500
    keeper.silver = 0
    _clean_keeper_inventory(keeper)

    lantern = spawn_object(3031)
    assert lantern is not None
    lantern.extra_flags = 0
    lantern.prototype.item_type = int(ItemType.LIGHT)
    lantern.timer = 0
    char.add_object(lantern)

    base_sell = _get_cost(keeper, lantern, buy=False)
    buy_price = _get_cost(keeper, lantern, buy=True)
    proto_cost = int(
        getattr(lantern.prototype, "cost", getattr(lantern, "cost", 0)) or 0
    )

    original_roll = rng_mm.number_percent
    try:
        rng_mm.number_percent = lambda: 40
        response = process_command(char, "sell lantern")
    finally:
        rng_mm.number_percent = original_roll

    match = re.search(r"for (\d+) silver(?: and (\d+) gold)?", response)
    assert match is not None
    silver = int(match.group(1))
    gold = int(match.group(2)) if match.group(2) is not None else 0
    total_price = silver + gold * 100

    expected_bonus = (proto_cost // 2) * 40 // 100
    cap_by_buy = (95 * buy_price) // 100 if buy_price > 0 else base_sell + expected_bonus
    expected_total = min(
        base_sell + expected_bonus, cap_by_buy, keeper.gold * 100 + keeper.silver + base_sell
    )
    assert total_price == expected_total
    assert "You haggle with the shopkeeper." in getattr(char, "messages", [])


def test_sell_numbered_selector():
    char = _create_shop_character("Vendor", 3010)
    char.gold = 0
    char.silver = 0
    keeper = _find_keeper(char)
    keeper.gold = 50
    keeper.silver = 500
    _clean_keeper_inventory(keeper)

    first = spawn_object(3031)
    second = spawn_object(3031)
    assert first is not None and second is not None
    for obj in (first, second):
        proto = getattr(obj, "prototype", None)
        if proto is not None:
            proto.item_type = int(ItemType.LIGHT)
            proto.cost = 120
        obj.item_type = int(ItemType.LIGHT)
        char.add_object(obj)

    with shop_hour():
        before_char = _total_wealth(char)
        before_keeper = keeper.gold * 100 + keeper.silver

        response = process_command(char, "sell 2.lantern")
        assert "you sell" in response.lower()
        match = re.search(
            r"for (\d+) silver(?: and (\d+) gold piece(s?))?\.\Z", response
        )
        assert match is not None
        silver = int(match.group(1))
        gold = int(match.group(2)) if match.group(2) is not None else 0
        price = silver + gold * 100

        assert _total_wealth(char) == before_char + price
        assert keeper.gold * 100 + keeper.silver == before_keeper - price
        # Head-insert: 2.lantern == first (older item), second stays
        assert second in char.inventory
        assert all(obj is not first for obj in char.inventory)
        assert any(obj is first for obj in keeper.inventory)

# ---------------------------------------------------------------------------
# GetCost unit tests
# ---------------------------------------------------------------------------

def test_get_cost_sell_extract_skips_dupe_discount():
    char = _create_shop_character("Extractor", 3010)
    char.gold = 0
    char.silver = 0
    keeper = _find_keeper(char)
    keeper.gold = 500
    keeper.silver = 0
    _clean_keeper_inventory(keeper)

    obj = spawn_object(3031)
    assert obj is not None
    obj.prototype.item_type = int(ItemType.LIGHT)
    obj.extra_flags = 0
    obj.cost = 100
    base = _get_cost(keeper, obj, buy=False)
    assert base > 0

    dupe = spawn_object(3031)
    assert dupe is not None
    dupe.extra_flags = 0
    dupe.cost = 100
    keeper.inventory.append(dupe)

    # Plain object gets the dupe discount
    assert _get_cost(keeper, obj, buy=False) < base

    # SELL_EXTRACT skips the dupe discount
    obj.extra_flags = int(ITEM_SELL_EXTRACT)
    assert _get_cost(keeper, obj, buy=False) == base


def test_get_cost_wand_charge_scaling_uses_runtime_value():
    char = _create_shop_character("Charger", 3010)
    char.gold = 0
    char.silver = 0
    keeper = spawn_mob(3000)
    assert keeper is not None
    keeper.move_to_room(char.room)
    keeper.inventory = []

    wand = spawn_object(3031)
    assert wand is not None
    wand.prototype.item_type = int(ItemType.WAND)
    wand.prototype.cost = 100
    wand.cost = 100
    wand.extra_flags = 0
    wand.prototype.value = [0, 10, 5, 0, 0]
    wand.value = [0, 10, 2, 0, 0]

    assert _get_cost(keeper, wand, buy=False) == 3


def test_get_cost_dupe_discount_requires_matching_short_descr():
    char = _create_shop_character("Renamer", 3010)
    char.gold = 0
    char.silver = 0
    keeper = _find_keeper(char)
    keeper.gold = 500
    keeper.silver = 0
    _clean_keeper_inventory(keeper)

    obj = spawn_object(3031)
    assert obj is not None
    obj.prototype.item_type = int(ItemType.LIGHT)
    obj.extra_flags = 0
    obj.cost = 100
    obj.short_descr = "a glowing blue lantern"
    base = _get_cost(keeper, obj, buy=False)
    assert base > 0

    same = spawn_object(3031)
    assert same is not None
    same.extra_flags = 0
    same.cost = 100
    same.short_descr = "a glowing blue lantern"
    keeper.inventory.append(same)
    assert _get_cost(keeper, obj, buy=False) < base

    keeper.inventory.remove(same)
    diff = spawn_object(3031)
    assert diff is not None
    diff.extra_flags = 0
    diff.cost = 100
    diff.short_descr = "a rusty red lantern"
    assert diff.prototype is obj.prototype
    keeper.inventory.append(diff)
    assert _get_cost(keeper, obj, buy=False) == base


def test_get_cost_dupe_discount_compounds_per_copy():
    char = _create_shop_character("Compounder", 3010)
    char.gold = 0
    char.silver = 0
    keeper = _find_keeper(char)
    keeper.gold = 500
    keeper.silver = 0
    _clean_keeper_inventory(keeper)

    obj = spawn_object(3031)
    assert obj is not None
    obj.prototype.item_type = int(ItemType.LIGHT)
    obj.extra_flags = 0
    obj.cost = 100
    base = _get_cost(keeper, obj, buy=False)
    assert base > 0

    dupe1 = spawn_object(3031)
    assert dupe1 is not None
    dupe1.extra_flags = 0
    dupe1.cost = 100
    keeper.inventory.append(dupe1)
    one = _get_cost(keeper, obj, buy=False)
    assert one == c_div(base * 3, 4)

    dupe2 = spawn_object(3031)
    assert dupe2 is not None
    dupe2.extra_flags = 0
    dupe2.cost = 100
    keeper.inventory.append(dupe2)
    two = _get_cost(keeper, obj, buy=False)
    assert two == c_div(one * 3, 4)
    assert two < one

# ---------------------------------------------------------------------------
# Value tests
# ---------------------------------------------------------------------------

def test_value_respects_drop_and_visibility_gates():
    char = _create_shop_character("Appraiser", 3010)
    char.gold = 0
    char.silver = 0
    keeper = _find_keeper(char)
    _clean_keeper_inventory(keeper)

    nodrop_obj = None
    invis_obj = None
    try:
        with shop_hour():
            nodrop_obj = spawn_object(3031)
            assert nodrop_obj is not None
            nodrop_obj.extra_flags = int(ITEM_NODROP)
            nodrop_obj.prototype.item_type = int(ItemType.LIGHT)
            char.add_object(nodrop_obj)
            assert process_command(char, "value lantern") == "You can't let go of it."
            char.remove_object(nodrop_obj)

            invis_obj = spawn_object(3031)
            assert invis_obj is not None
            invis_obj.extra_flags = int(ITEM_INVIS)
            invis_obj.prototype.item_type = int(ItemType.LIGHT)
            if len(invis_obj.value) > 2:
                invis_obj.value[2] = 0
            char.add_object(invis_obj)
            response = process_command(char, "value lantern")
            assert "doesn't see what you are offering" in response
            assert "the shopkeeper" not in response.lower()
    finally:
        if nodrop_obj and nodrop_obj in char.inventory:
            char.remove_object(nodrop_obj)
        if invis_obj and invis_obj in char.inventory:
            char.remove_object(invis_obj)


def test_value_lists_offer():
    char = _create_shop_character("Barter", 3010)
    char.gold = 0
    char.silver = 0
    keeper = _find_keeper(char)
    keeper.gold = 500
    keeper.silver = 0
    _clean_keeper_inventory(keeper)

    with shop_hour():
        lantern = spawn_object(3031)
        assert lantern is not None
        lantern.prototype.item_type = int(ItemType.LIGHT)
        char.add_object(lantern)

        expected_cost = _get_cost(keeper, lantern, buy=False)
        response = process_command(char, "value lantern")
        descriptor = getattr(lantern, "short_descr", None) or getattr(lantern, "name", None) or "it"
        keeper_name = getattr(keeper, "short_descr", None) or getattr(keeper, "name", None) or "The shopkeeper"
        expected = (
            f"{keeper_name} tells you "
            f"'I'll give you {expected_cost % 100} silver and {expected_cost // 100} gold coins for {descriptor}'."
        )
        assert response == expected[:1].upper() + expected[1:]
        assert char.reply is keeper
        assert lantern in char.inventory


def test_value_uses_keeper_voice_with_item_name():
    char = _create_shop_character("Appraiser2", 3010)
    char.gold = 0
    keeper = _find_keeper(char)
    keeper.gold = 500
    keeper.silver = 0

    with shop_hour():
        lantern = spawn_object(3031)
        assert lantern is not None
        lantern.prototype.item_type = int(ItemType.LIGHT)
        char.add_object(lantern)

        response = process_command(char, "value lantern")
        keeper_name = getattr(keeper, "short_descr", None) or getattr(keeper, "name", None) or "The shopkeeper"
        item_name = getattr(lantern, "short_descr", None) or getattr(lantern, "name", None) or "it"
        prefix = f"{keeper_name} tells you '"
        assert response.startswith(prefix[:1].upper() + prefix[1:])
        assert item_name in response
        assert "silver" in response
        assert "gold coins" in response

# ---------------------------------------------------------------------------
# List tests
# ---------------------------------------------------------------------------

def test_list_price_matches_buy_price():
    char = _create_shop_character("Buyer", 3010)
    char.gold = 100
    keeper = _find_keeper(char)
    with shop_hour():
        _ensure_lantern(keeper)
        out = process_command(char, "list")
        lantern_line = next(
            line for line in out.splitlines() if "hooded brass lantern" in line
        )
        match = re.search(r"\[\s*\d+\s+(\d+)\s+", lantern_line)
        assert match
        price = int(match.group(1))
        before = _total_wealth(char)
        process_command(char, "buy lantern")
        assert _total_wealth(char) == before - price


def test_list_shows_columns_and_filters():
    char = _create_shop_character("List patron", 3001)
    char.gold = 500
    keeper = spawn_mob(3006)
    assert keeper is not None
    keeper.move_to_room(char.room)
    keeper.inventory.clear()

    r1 = spawn_object(3050)
    r2 = spawn_object(3050)
    assert r1 is not None and r2 is not None
    for r in (r1, r2):
        r.prototype.short_descr = "a travel ration"
        r.prototype.item_type = int(ItemType.FOOD)
        r.prototype.cost = 15

    apples = spawn_object(3051)
    assert apples is not None
    apples.prototype.short_descr = "a rack of apples"
    apples.prototype.item_type = int(ItemType.FOOD)
    apples.prototype.cost = 10
    apples.extra_flags = getattr(apples, "extra_flags", 0) | int(ITEM_INVENTORY)

    keeper.inventory.extend([r1, r2, apples])

    with shop_hour():
        listing = process_command(char, "list")
        assert "[Lv Price Qty] Item" in listing
        lines = listing.splitlines()
        ration_line = next(line for line in lines if "travel ration" in line)
        apples_line = next(line for line in lines if "rack of apples" in line)
        assert " 2 ]" in ration_line
        assert "--" in apples_line

        filtered = process_command(char, "list ration")
        assert "travel ration" in filtered
        assert "rack of apples" not in filtered

        mix = process_command(char, "list TrAveL RAtion")
        assert "travel ration" in mix
        assert "rack of apples" not in mix

        empty = process_command(char, "list dagger")
        assert empty == "You can't buy anything here."


def test_list_filters_empty_inventory():
    char = _create_shop_character("Filter patron", 3001)
    keeper = spawn_mob(3006)
    assert keeper is not None
    keeper.move_to_room(char.room)
    keeper.inventory.clear()

    ration = spawn_object(3050)
    assert ration is not None
    ration.prototype.short_descr = "a travel ration"
    ration.prototype.item_type = int(ItemType.FOOD)
    ration.prototype.cost = 15
    keeper.inventory.append(ration)

    with shop_hour():
        baseline = process_command(char, "list")
        assert "travel ration" in baseline
        no_match = process_command(char, "list lantern")
        assert no_match == "You can't buy anything here."


def test_list_hides_items_blind_buyer_cannot_see():
    char = _create_shop_character("Blind browser", 3001)
    char.gold = 500
    keeper = spawn_mob(3006)
    assert keeper is not None
    keeper.move_to_room(char.room)

    raft = spawn_object(3050)
    assert raft is not None
    raft.prototype.short_descr = "a small river raft"
    raft.prototype.item_type = int(ItemType.BOAT)
    raft.prototype.cost = 200
    keeper.inventory.append(raft)

    with shop_hour():
        sighted = process_command(char, "list")
        assert "small river raft" in sighted
        char.add_affect(AffectFlag.BLIND)
        blind = process_command(char, "list")
        assert "small river raft" not in blind


def test_list_skips_keeper_worn_items():
    char = _create_shop_character("Browser", 3010)
    keeper = _find_keeper(char)
    keeper.inventory = []

    with shop_hour():
        worn = spawn_object(3031)
        assert worn is not None
        worn.prototype.short_descr = "a worn lantern"
        worn.prototype.cost = 50
        worn.wear_loc = int(WearLocation.LIGHT)
        keeper.inventory.append(worn)

        normal = spawn_object(3031)
        assert normal is not None
        normal.prototype.short_descr = "a normal lantern"
        normal.prototype.cost = 50
        normal.wear_loc = int(WearLocation.NONE)
        keeper.inventory.append(normal)

        listing = process_command(char, "list")
        assert "normal lantern" in listing
        assert "worn lantern" not in listing

# ---------------------------------------------------------------------------
# Shop behavior tests
# ---------------------------------------------------------------------------

def test_shop_respects_open_hours():
    char = _create_shop_character("Captain patron", 3001)
    char.gold = 500
    keeper = spawn_mob(3006)
    assert keeper is not None
    keeper.move_to_room(char.room)

    raft = spawn_object(3050)
    assert raft is not None
    raft.prototype.short_descr = "a small river raft"
    raft.prototype.item_type = int(ItemType.BOAT)
    raft.prototype.cost = 200
    keeper.inventory.append(raft)

    canoe = spawn_object(3051)
    assert canoe is not None
    canoe.prototype.short_descr = "a spare canoe"
    canoe.prototype.item_type = int(ItemType.BOAT)
    canoe.prototype.cost = 180
    canoe.cost = 180
    char.add_object(canoe)

    with shop_hour(3):
        assert process_command(char, "list") == "Sorry, I am closed. Come back later."
        assert process_command(char, "buy raft") == "Sorry, I am closed. Come back later."
        assert process_command(char, "sell canoe") == "Sorry, I am closed. Come back later."

    with shop_hour(23):
        assert process_command(char, "list") == "Sorry, I am closed. Come back tomorrow."
        assert process_command(char, "buy raft") == "Sorry, I am closed. Come back tomorrow."
        assert process_command(char, "sell canoe") == "Sorry, I am closed. Come back tomorrow."

    with shop_hour():
        listing = process_command(char, "list")
        assert "small river raft" in listing
        before = char.gold
        assert "buy a small river raft" in process_command(char, "buy raft").lower()
        assert char.gold < before
        after = char.gold
        assert "sell a spare canoe" in process_command(char, "sell canoe").lower()
        assert char.gold > after


def test_shop_refuses_invisible_customers():
    char = _create_shop_character("Sneaky patron", 3001)
    char.gold = 500
    char.add_affect(AffectFlag.INVISIBLE)
    keeper = spawn_mob(3006)
    assert keeper is not None
    keeper.move_to_room(char.room)

    raft = spawn_object(3050)
    assert raft is not None
    raft.prototype.short_descr = "a small river raft"
    raft.prototype.item_type = int(ItemType.BOAT)
    raft.prototype.cost = 200
    keeper.inventory.append(raft)

    with shop_hour():
        assert process_command(char, "list") == "I don't trade with folks I can't see."
        keeper.affected_by = getattr(keeper, "affected_by", 0) | int(AffectFlag.DETECT_INVIS)
        assert "small river raft" in process_command(char, "list")


def test_buy_blind_buyer_cannot_see_item():
    char = _create_shop_character("Blind patron", 3001)
    char.gold = 500
    keeper = spawn_mob(3006)
    assert keeper is not None
    keeper.move_to_room(char.room)

    raft = spawn_object(3050)
    assert raft is not None
    raft.prototype.short_descr = "a small river raft"
    raft.prototype.item_type = int(ItemType.BOAT)
    raft.prototype.cost = 200
    keeper.inventory.append(raft)

    char.add_affect(AffectFlag.BLIND)
    with shop_hour():
        name = getattr(keeper, "short_descr", None) or getattr(keeper, "name", None) or "The shopkeeper"
        denied = process_command(char, "buy raft")
        assert denied == capitalize_act_line(f"{name} tells you 'I don't sell that -- try 'list''.")
        assert raft in keeper.inventory
        assert raft not in char.inventory
        assert char.gold == 500


def test_shop_respects_keeper_wealth():
    char = _create_shop_character("Consigner", 3001)
    char.gold = 0
    keeper = spawn_mob(3006)
    assert keeper is not None
    keeper.move_to_room(char.room)

    canoe = spawn_object(3051)
    assert canoe is not None
    canoe.prototype.short_descr = "a spare canoe"
    canoe.prototype.item_type = int(ItemType.BOAT)
    canoe.prototype.cost = 180
    canoe.cost = 180
    char.add_object(canoe)

    with shop_hour():
        keeper.gold = 1; keeper.silver = 0
        name = getattr(keeper, "short_descr", None) or getattr(keeper, "name", None) or "The shopkeeper"
        canoe_name = getattr(canoe, "short_descr", None) or getattr(canoe, "name", None) or "it"
        denied = process_command(char, "sell canoe")
        assert denied == capitalize_act_line(
            f"{name} tells you 'I'm afraid I don't have enough wealth to buy {canoe_name}."
        )
        assert char.gold == 0
        assert canoe in char.inventory
        assert canoe not in keeper.inventory

        keeper.gold = 2; keeper.silver = 0
        accepted = process_command(char, "sell canoe")
        silver_match = re.search(r"(\d+) silver", accepted)
        assert silver_match is not None
        silver = int(silver_match.group(1))
        gold_match = re.search(r"(\d+) gold", accepted)
        gold = int(gold_match.group(1)) if gold_match is not None else 0
        price = gold * 100 + silver
        assert _total_wealth(char) == price
        assert char.gold == price // 100
        assert char.silver == price % 100
        assert canoe not in char.inventory
        assert canoe in keeper.inventory
        assert keeper.gold == 0
        assert keeper.silver == 38


def test_buy_cant_afford_uses_keeper_voice():
    char = _create_shop_character("Broke", 3010)
    char.gold = 0
    char.silver = 0
    keeper = _find_keeper(char)
    with shop_hour():
        _ensure_lantern(keeper)
        response = process_command(char, "buy lantern")
        name = getattr(keeper, "short_descr", None) or getattr(keeper, "name", None) or "The shopkeeper"
        assert capitalize_act_line(f"{name} tells you '") in response
        assert "You can't afford" in response

# ---------------------------------------------------------------------------
# Haggle tests
# ---------------------------------------------------------------------------

def test_buy_haggle_reduces_cost_on_success():
    char = _create_shop_character("Haggler", 3010)
    char.gold = 200
    char.silver = 0
    char.skills = {"haggle": 95}
    keeper = _find_keeper(char)

    with shop_hour():
        ration = spawn_object(3031)
        assert ration is not None
        ration.prototype.short_descr = "a haggle test ration"
        ration.prototype.cost = 100
        proto_extra = int(getattr(ration.prototype, "extra_flags", 0) or 0)
        ration.prototype.extra_flags = proto_extra | int(ITEM_INVENTORY)
        ration.extra_flags = int(getattr(ration, "extra_flags", 0) or 0) | int(ITEM_INVENTORY)
        keeper.inventory.append(ration)
        for stock in keeper.inventory:
            if getattr(stock.prototype, "vnum", None) == 3031:
                stock.cost = 100

        base = (ration.prototype.cost * shop_registry.get(3002).profit_buy) // 100

        original_roll = rng_mm.number_percent
        try:
            rng_mm.number_percent = lambda: 40
            before = _total_wealth(char)
            response = process_command(char, "buy ration")
        finally:
            rng_mm.number_percent = original_roll

        assert "buy a haggle test ration" in response.lower()
        match = re.search(r"for (\d+) silver", response)
        assert match is not None
        paid = int(match.group(1))
        discount = c_div(c_div(100, 2) * 40, 100)
        expected = max(0, base - discount)
        assert paid == expected
        assert paid < base
        assert _total_wealth(char) == before - paid
        assert "You haggle with the shopkeeper." in getattr(char, "messages", [])


def test_buy_haggle_discount_uses_runtime_cost():
    char = _create_shop_character("Haggler", 3001)
    char.gold = 500
    char.silver = 0
    char.skills = {"haggle": 95}
    keeper = spawn_mob(3006)
    assert keeper is not None
    keeper.move_to_room(char.room)

    raft = spawn_object(3050)
    assert raft is not None
    raft.prototype.short_descr = "a small river raft"
    raft.prototype.item_type = int(ItemType.BOAT)
    raft.prototype.cost = 200
    for stock in keeper.inventory:
        if getattr(stock.prototype, "vnum", None) == 3050:
            stock.cost = 100
    raft.cost = 100
    keeper.inventory.append(raft)

    original_roll = rng_mm.number_percent
    try:
        with shop_hour():
            rng_mm.number_percent = lambda: 40
            response = process_command(char, "buy raft")
    finally:
        rng_mm.number_percent = original_roll

    match = re.search(r"for (\d+) silver", response)
    assert match is not None
    paid = int(match.group(1))
    # Runtime cost 100 -> discount 20 -> paid 100 (not proto 200 -> discount 40 -> 80)
    assert paid == 100


def test_buy_negative_total_cost_keeper_split_uses_c_truncation():
    char = _create_shop_character("Haggler", 3001)
    char.gold = 500
    char.silver = 0
    char.skills = {"haggle": 100}
    keeper = spawn_mob(3006)
    assert keeper is not None
    keeper.move_to_room(char.room)
    keeper.gold = 0
    keeper.silver = 0

    raft = spawn_object(3050)
    assert raft is not None
    raft.prototype.short_descr = "a small river raft"
    raft.prototype.item_type = int(ItemType.BOAT)
    raft.prototype.cost = 100
    for stock in keeper.inventory:
        if getattr(stock.prototype, "vnum", None) == 3050:
            stock.cost = 100
    raft.cost = 100
    keeper.inventory.append(raft)

    shop = shop_registry.get(3006)
    saved = shop.profit_buy
    rollback = rng_mm.number_percent
    try:
        with shop_hour():
            shop.profit_buy = 40
            rng_mm.number_percent = lambda: 99
            process_command(char, "buy raft")
    finally:
        shop.profit_buy = saved
        rng_mm.number_percent = rollback

    total_cost = -9
    assert keeper.gold == c_div(total_cost, 100) == 0
    assert keeper.silver == c_mod(total_cost, 100) == -9


def test_sell_haggle_bonus_uses_runtime_cost():
    char = _create_shop_character("Haggler", 3001)
    char.gold = 0
    char.silver = 0
    char.skills = {"haggle": 95}
    keeper = spawn_mob(3006)
    assert keeper is not None
    keeper.move_to_room(char.room)
    keeper.gold = 1000
    keeper.silver = 0

    raft = spawn_object(3050)
    assert raft is not None
    raft.prototype.short_descr = "a small river raft"
    raft.prototype.item_type = int(ItemType.BOAT)
    raft.prototype.cost = 200
    raft.cost = 100
    char.add_object(raft)

    shop = shop_registry.get(3006)
    saved = shop.profit_buy
    rollback = rng_mm.number_percent
    try:
        with shop_hour():
            shop.profit_buy = 300
            rng_mm.number_percent = lambda: 40
            process_command(char, "sell raft")
            assert _total_wealth(char) == 110
    finally:
        shop.profit_buy = saved
        rng_mm.number_percent = rollback


def test_sell_uses_runtime_cost_not_prototype():
    char = _create_shop_character("Reseller", 3001)
    char.gold = 0
    char.silver = 0
    keeper = spawn_mob(3006)
    assert keeper is not None
    keeper.move_to_room(char.room)
    keeper.gold = 100
    keeper.silver = 0

    raft = spawn_object(3050)
    assert raft is not None
    raft.prototype.short_descr = "a small river raft"
    raft.prototype.item_type = int(ItemType.BOAT)
    raft.prototype.cost = 200
    raft.cost = 40
    char.add_object(raft)

    with shop_hour():
        process_command(char, "sell raft")
        assert _total_wealth(char) == 36
        assert raft in keeper.inventory
        assert raft not in char.inventory


def test_sell_haggle_cap_applies_when_buy_price_zero():
    char = _create_shop_character("Haggler", 3001)
    char.gold = 0
    char.silver = 0
    char.skills = {"haggle": 95}
    keeper = spawn_mob(3006)
    assert keeper is not None
    keeper.move_to_room(char.room)
    keeper.gold = 100
    keeper.silver = 0

    raft = spawn_object(3050)
    assert raft is not None
    raft.prototype.short_descr = "a small river raft"
    raft.prototype.item_type = int(ItemType.BOAT)
    raft.prototype.cost = 100
    raft.cost = 100
    char.add_object(raft)

    shop = shop_registry.get(3006)
    saved = shop.profit_buy
    rollback = rng_mm.number_percent
    try:
        with shop_hour():
            shop.profit_buy = 0
            rng_mm.number_percent = lambda: 40
            process_command(char, "sell raft")
            assert _total_wealth(char) == 0
    finally:
        shop.profit_buy = saved
        rng_mm.number_percent = rollback


def test_wand_staff_price_scales_with_charges_and_inventory_discount():
    ch = create_test_character("Seller", 3001)
    keeper = spawn_mob(3000)
    assert keeper is not None
    keeper.move_to_room(ch.room)

    wand = spawn_object(3031)
    assert wand is not None
    wand.prototype.short_descr = "a test wand"
    wand.prototype.item_type = int(ItemType.WAND)
    wand.prototype.cost = 100
    wand.cost = 100
    wand.prototype.value[1] = 10
    wand.prototype.value[2] = 5
    wand.value = [0, 10, 5, 0, 0]
    ch.add_object(wand)

    with shop_hour():
        assert process_command(ch, "sell wand").endswith("7 silver and 0 gold pieces.")

        copy = spawn_object(3031)
        assert copy is not None
        copy.prototype.short_descr = "a test wand"
        copy.prototype.item_type = int(ItemType.WAND)
        copy.prototype.cost = 100
        copy.cost = 100
        copy.prototype.value[1] = 10
        copy.prototype.value[2] = 5
        copy.extra_flags = int(ITEM_INVENTORY)
        keeper.inventory.append(copy)

        wand2 = spawn_object(3031)
        assert wand2 is not None
        wand2.prototype.short_descr = "a test wand"
        wand2.prototype.item_type = int(ItemType.WAND)
        wand2.prototype.cost = 100
        wand2.cost = 100
        wand2.prototype.value[1] = 10
        wand2.prototype.value[2] = 5
        wand2.value = [0, 10, 5, 0, 0]
        ch.add_object(wand2)
        # base=15, non-inv dupe -> 11, inv copy -> 5, charge 5/10 -> 2
        assert process_command(ch, "sell wand").endswith("2 silver and 0 gold pieces.")

# ---------------------------------------------------------------------------
# Pet-shop tests
# ---------------------------------------------------------------------------

def test_pet_shop_purchase_creates_charmed_pet():
    rng_mm.seed_mm(1)
    buyer, storefront, _, proto = _setup_pet_shop()
    buyer.skills["haggle"] = 95
    response = do_buy(buyer, "companion Fluffy")
    assert response == "Enjoy your pet."
    assert buyer.gold == 2
    assert buyer.silver == 90
    assert buyer.messages[-2:] == [
        "You haggle the price down to 210 coins.",
        "A cuddly companion now follows you.",
    ]

    pet = buyer.pet
    assert pet is not None
    assert pet.master is buyer
    assert pet.leader is buyer
    assert pet.messages[-2:] == [
        "You now follow Buyer.",
        "Buyer bought a cuddly companion as a pet.",
    ]
    assert pet in storefront.people
    assert pet.room is storefront
    assert pet in character_registry
    assert pet.short_descr == proto.short_descr
    assert pet.name.endswith("Fluffy")
    assert "I belong to Buyer" in pet.description
    assert pet.has_affect(AffectFlag.CHARM)
    assert pet.act & int(ActFlag.PET)
    assert pet.comm & int(CommFlag.NOTELL)
    assert pet.comm & int(CommFlag.NOSHOUT)
    assert pet.comm & int(CommFlag.NOCHANNELS)


def test_pet_shop_rejects_second_pet():
    rng_mm.seed_mm(5)
    buyer, storefront, kennel, proto = _setup_pet_shop()
    assert do_buy(buyer, "companion") == "Enjoy your pet."
    original = buyer.pet
    assert original is not None

    assert do_buy(buyer, "companion") == "You already own a pet."
    assert buyer.pet is original
    assert sum(1 for e in character_registry if getattr(e, "master", None) is buyer) == 1
    assert isinstance(kennel.people[0], MobInstance)
    assert int(getattr(proto, "act_flags", 0) or 0) & int(ActFlag.PET)


def test_list_in_pet_shop_room_shows_pets():
    room_registry.clear()
    mob_registry.clear()
    character_registry.clear()

    storefront = Room(vnum=9700, name="Pet Shop")
    storefront.room_flags = int(RoomFlag.ROOM_PET_SHOP)
    kennel = Room(vnum=9701, name="Kennel")
    room_registry[storefront.vnum] = storefront
    room_registry[kennel.vnum] = kennel

    proto = MobIndex(vnum=9702, short_descr="a fluffy bunny", player_name="bunny")
    proto.level = 3
    proto.act_flags = int(ActFlag.PET)
    mob_registry[proto.vnum] = proto
    kennel.add_mob(MobInstance.from_prototype(proto))

    buyer = Character(name="Lister", level=10, is_npc=False)
    storefront.add_character(buyer)
    character_registry.append(buyer)

    response = do_list(buyer)
    assert "Pets for sale:" in response
    assert "fluffy bunny" in response
    assert "3" in response
    assert "90" in response


def test_sell_inventory_item_dedups_via_obj_to_keeper():
    char = _create_shop_character("Seller", 3010)
    char.gold = 0
    keeper = _find_keeper(char)
    keeper.gold = 500
    keeper.silver = 0
    keeper.inventory = []

    with shop_hour():
        template = spawn_object(3031)
        assert template is not None
        template.prototype.item_type = int(ItemType.LIGHT)
        template.prototype.cost = 100
        template.prototype.extra_flags = (
            int(getattr(template.prototype, "extra_flags", 0) or 0) | int(ITEM_INVENTORY)
        )
        template.extra_flags = (
            int(getattr(template, "extra_flags", 0) or 0) | int(ITEM_INVENTORY)
        )
        keeper.inventory.append(template)

        before = len(keeper.inventory)

        sold = spawn_object(3031)
        assert sold is not None
        sold.prototype.item_type = int(ItemType.LIGHT)
        sold.prototype.cost = 100
        char.add_object(sold)

        assert "you sell" in process_command(char, "sell lantern").lower()
        assert len(keeper.inventory) == before
        assert sold not in keeper.inventory
        assert sold not in char.inventory


def test_buy_multi_stock_requires_consecutive_run():
    char = _create_shop_character("Buyer", 3010)
    char.gold = 1000
    keeper = _find_keeper(char)
    with shop_hour():
        l1 = spawn_object(3031)
        dag = spawn_object(3020)
        l2 = spawn_object(3031)
        for o in (l1, dag, l2):
            assert o is not None
            o.wear_loc = -1
        keeper.inventory = [l1, dag, l2]

        result = process_command(char, "buy 2*lantern")
        assert "don't have that many in stock" in result.lower()
        assert l1 in keeper.inventory and l2 in keeper.inventory
        assert not any(
            (o.short_descr or "").lower().startswith("a hooded brass lantern")
            for o in char.inventory
        )


def test_obj_to_keeper_standardizes_cost_even_when_existing_is_zero():
    existing = spawn_object(3021)
    sold = spawn_object(3021)
    assert existing is not None and sold is not None
    existing.cost = 0
    sold.cost = 250

    keeper = Character(name="Keeper", is_npc=True)
    keeper.inventory = [existing]

    assert _obj_to_keeper(sold, keeper) is False
    assert sold.cost == 0, "sold cost must be standardized to existing (ROM keeps it standard)"
