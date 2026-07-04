"""Coverage-lock — gain_condition DRUNK "You are sober." fires only on a real 0-crossing.

ROM ``gain_condition`` (``src/update.c:391-394``) announces sobriety only when the
DRUNK slot's **old** value was non-zero before the tick drove it to 0:

    case COND_DRUNK:
        if (condition != 0)              // `condition` = the pre-update value
            send_to_char ("You are sober.\n\r", ch);
        break;

So an already-sober player (slot 0) ticking `-1` (clamped back to 0) must stay
silent, whereas HUNGER/THIRST announce unconditionally whenever the slot reaches
0. This branch (the DRUNK ``current != 0`` guard, ``conditions.py:49``) had no
direct regression test; this locks it so a future refactor to
``if updated == 0`` (dropping the old-value guard) would spam "You are sober."
every idle tick once a player is dry.
"""

from __future__ import annotations

from mud.characters.conditions import gain_condition
from mud.models.character import Character
from mud.models.constants import Condition


class _PCData:
    def __init__(self) -> None:
        self.condition = [0, 0, 0, 0]  # HUNGER, THIRST, DRUNK, FULL


def _make_pc() -> Character:
    pc = Character(name="Tippler", is_npc=False, level=10)
    pc.pcdata = _PCData()
    return pc


def test_drunk_reaching_zero_from_nonzero_announces_sober() -> None:
    pc = _make_pc()
    pc.pcdata.condition[int(Condition.DRUNK)] = 1
    gain_condition(pc, Condition.DRUNK, -1)
    assert pc.pcdata.condition[int(Condition.DRUNK)] == 0
    assert pc.messages == ["You are sober."]


def test_drunk_already_zero_stays_silent() -> None:
    """ROM's `if (condition != 0)` guard — an already-sober player is not re-notified."""
    pc = _make_pc()
    pc.pcdata.condition[int(Condition.DRUNK)] = 0
    gain_condition(pc, Condition.DRUNK, -1)
    assert pc.pcdata.condition[int(Condition.DRUNK)] == 0
    assert pc.messages == []


def test_hunger_at_zero_announces_unconditionally() -> None:
    """Contrast: HUNGER has no old-value guard — it fires whenever the slot is at 0."""
    pc = _make_pc()
    pc.pcdata.condition[int(Condition.HUNGER)] = 0
    gain_condition(pc, Condition.HUNGER, -1)
    assert pc.messages == ["You are hungry."]
