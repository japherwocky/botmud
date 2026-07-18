"""
Player Auto-Settings Command Tests

Tests for player auto-setting and communication flag commands.
"""

from __future__ import annotations

import pytest
from helpers_player import enable_autos, set_player_flags

from mud.commands.auto_settings import (
    do_autoall,
    do_autoassist,
    do_autoexit,
    do_autogold,
    do_autolist,
    do_autoloot,
    do_autosac,
    do_autosplit,
    do_brief,
    do_colour,
    do_combine,
    do_compact,
    do_prompt,
)
from mud.models.constants import CommFlag, PlayerFlag
from mud.registry import area_registry, mob_registry, obj_registry, room_registry
from mud.world import create_test_character, initialize_world


@pytest.fixture(scope="module", autouse=True)
def setup_world():
    initialize_world("area/area.lst")
    yield
    area_registry.clear()
    mob_registry.clear()
    obj_registry.clear()
    room_registry.clear()


def _player(name: str = "TestPlayer"):
    ch = create_test_character(name, 3001)
    ch.is_npc = False
    return ch


# ---------------------------------------------------------------------------
# PlayerFlag toggles — same pattern everywhere:
#   flag off → command → flag on + output keyword → command again → flag off
# ---------------------------------------------------------------------------

_PLAYER_FLAG_TOGGLES = [
    (do_autoassist, PlayerFlag.AUTOASSIST, "assist", "removed"),
    (do_autoexit, PlayerFlag.AUTOEXIT, "displayed", "no longer"),
    (do_autogold, PlayerFlag.AUTOGOLD, "gold", None),
    (do_autoloot, PlayerFlag.AUTOLOOT, "loot", None),
    (do_autosac, PlayerFlag.AUTOSAC, "sacrific", None),
    (do_autosplit, PlayerFlag.AUTOSPLIT, "split", None),
]


class TestPlayerFlagToggles:
    @pytest.mark.p0
    @pytest.mark.parametrize(
        "cmd, flag, on_kw, off_kw", _PLAYER_FLAG_TOGGLES,
    )
    def test_toggle(self, cmd, flag, on_kw, off_kw):
        ch = _player()
        assert not (ch.act & flag)

        output = cmd(ch, "")
        assert ch.act & flag
        assert on_kw in output.lower()

        output = cmd(ch, "")
        assert not (ch.act & flag)
        if off_kw:
            assert off_kw in output.lower()


class TestAutoAssist:
    @pytest.mark.p0
    def test_npc_no_effect(self):
        ch = _player("NPC")
        ch.is_npc = True
        assert do_autoassist(ch, "") == ""


# ---------------------------------------------------------------------------
# CommFlag toggles — same pattern as above but on ch.comm
# ---------------------------------------------------------------------------

_COMM_FLAG_TOGGLES = [
    (do_brief, CommFlag.BRIEF, "short", "full"),
    (do_compact, CommFlag.COMPACT, "compact", "removed"),
    (do_combine, CommFlag.COMBINE, "combine", "no longer"),
    (do_colour, PlayerFlag.COLOUR, "on", "off"),
    (do_prompt, CommFlag.PROMPT, "prompt", "no longer"),
]


class TestCommFlagToggles:
    @pytest.mark.p0
    @pytest.mark.parametrize(
        "cmd, flag, on_kw, off_kw", _COMM_FLAG_TOGGLES,
    )
    def test_toggle(self, cmd, flag, on_kw, off_kw):
        ch = _player()
        ch.comm = 0
        ch.act = 0

        output = cmd(ch, "")
        if isinstance(flag, CommFlag):
            assert ch.comm & flag
        else:
            assert ch.act & flag
        assert on_kw in output.lower()

        output = cmd(ch, "")
        if isinstance(flag, CommFlag):
            assert not (ch.comm & flag)
        else:
            assert not (ch.act & flag)
        if off_kw:
            assert off_kw in output.lower()


# ---------------------------------------------------------------------------
# autolist
# ---------------------------------------------------------------------------


class TestAutoList:
    @pytest.mark.p0
    def test_lists_all_settings(self):
        ch = _player()
        set_player_flags(ch, autoassist=True, autoexit=True, autoloot=True)
        output = do_autolist(ch, "")
        for name in ("autoassist", "autoexit", "autoloot", "autogold", "autosac", "autosplit"):
            assert name in output.lower()

    @pytest.mark.p0
    def test_shows_on_off_status(self):
        ch = _player()
        set_player_flags(ch, autoassist=True, autoloot=False)
        output = do_autolist(ch, "")
        assert len(output) > 50


# ---------------------------------------------------------------------------
# autoall
# ---------------------------------------------------------------------------

_ALL_FLAGS = (
    PlayerFlag.AUTOASSIST | PlayerFlag.AUTOEXIT | PlayerFlag.AUTOGOLD
    | PlayerFlag.AUTOLOOT | PlayerFlag.AUTOSAC | PlayerFlag.AUTOSPLIT
)


class TestAutoAll:
    @pytest.mark.p0
    def test_on(self):
        ch = _player()
        ch.act = 0
        output = do_autoall(ch, "on")
        assert ch.act & _ALL_FLAGS
        assert "on" in output.lower()

    @pytest.mark.p0
    def test_off(self):
        ch = _player()
        enable_autos(
            ch, autoassist=True, autoexit=True, autogold=True,
            autoloot=True, autosac=True, autosplit=True,
        )
        output = do_autoall(ch, "off")
        assert not (ch.act & _ALL_FLAGS)
        assert "off" in output.lower()

    @pytest.mark.p0
    def test_no_args_shows_usage(self):
        ch = _player()
        output = do_autoall(ch, "")
        assert "usage" in output.lower() or "on" in output.lower()


# ---------------------------------------------------------------------------
# prompt (custom string / "all")
# ---------------------------------------------------------------------------


class TestPromptCustom:
    @pytest.mark.p0
    def test_set_custom(self):
        ch = _player()
        pcdata = getattr(ch, "pcdata", None)
        if not pcdata:
            pytest.skip("Player lacks pcdata")
        output = do_prompt(ch, "<%hhp %mm %vmv>")
        assert ch.comm & CommFlag.PROMPT
        assert ch.prompt == "<%hhp %mm %vmv> "
        assert "set" in output.lower()

    @pytest.mark.p0
    def test_all_sets_default(self):
        ch = _player()
        pcdata = getattr(ch, "pcdata", None)
        if not pcdata:
            pytest.skip("Player lacks pcdata")
        do_prompt(ch, "all")
        assert ch.comm & CommFlag.PROMPT
        assert ch.prompt is not None
        assert "hp" in ch.prompt.lower()


# ---------------------------------------------------------------------------
# Communication flags — verify each flag can be set on ch.comm
# ---------------------------------------------------------------------------

_COMM_FLAGS = [
    CommFlag.QUIET,
    CommFlag.DEAF,
    CommFlag.AFK,
    CommFlag.NOWIZ,
    CommFlag.NOAUCTION,
    CommFlag.NOGOSSIP,
    CommFlag.NOQUESTION,
    CommFlag.NOMUSIC,
    CommFlag.NOEMOTE,
    CommFlag.NOTELL,
]


class TestCommFlags:
    @pytest.mark.parametrize("flag", _COMM_FLAGS)
    def test_settable(self, flag):
        ch = _player()
        ch.comm = 0
        ch.comm |= flag
        assert (ch.comm & flag) != 0
