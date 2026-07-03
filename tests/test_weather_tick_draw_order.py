"""ROM parity: weather_tick RNG draw order/count.

Locks the exact Mitchell-Moore draw sequence of ROM ``weather_update``
(``src/update.c:522``). The pressure line is a *single* C expression:

    weather_info.change += diff * dice (1, 4) + dice (2, 6) - dice (2, 6);

The evaluation order of the three ``dice()`` calls in ``a + b - c`` is
UNSPECIFIED in C — but each ``dice()`` advances the shared MM RNG, so the
compiled order fixes which draw is added versus subtracted. On the diff-harness
build platform (clang/gcc, darwin + linux CI) ``cc`` evaluates this expression
strictly left-to-right (``dice(1,4)`` → ``+dice(2,6)`` → ``-dice(2,6)``), which
is exactly the order ``mud.game_loop.weather_tick`` draws in. This test pins
that contract so a future refactor cannot silently swap the two ``dice(2,6)``
draws (which would flip ``change`` by ``2*(d2-d3)`` and desync every subsequent
MM draw shared with combat/spells) or drop/add a draw.

Also pins the per-branch ``number_bits(2)`` draw count for each sky state, since
ROM's ``||``/``&&`` short-circuit determines whether the roll fires at all
(``src/update.c:586-641``).
"""

from __future__ import annotations

import mud.game_loop as game_loop
from mud.game_loop import SkyState, weather, weather_tick


def _install_draw_recorder(monkeypatch):
    """Patch rng_mm.dice / number_bits to record call args in draw order."""
    dice_calls: list[tuple[int, int]] = []
    bits_calls: list[int] = []
    dice_returns = iter([1, 5, 2])  # dice(1,4)=1, +dice(2,6)=5, -dice(2,6)=2

    def fake_dice(number: int, size: int) -> int:
        dice_calls.append((number, size))
        return next(dice_returns)

    def fake_number_bits(width: int) -> int:
        bits_calls.append(width)
        return 0  # 0 => triggers every ``number_bits(2) == 0`` sky transition

    monkeypatch.setattr(game_loop.rng_mm, "dice", fake_dice)
    monkeypatch.setattr(game_loop.rng_mm, "number_bits", fake_number_bits)
    monkeypatch.setattr(game_loop, "broadcast_global", lambda *a, **k: None)
    return dice_calls, bits_calls


def test_weather_tick_draws_dice_in_rom_left_to_right_order(monkeypatch):
    """diff*dice(1,4) + dice(2,6) - dice(2,6): mul, then +add, then -sub."""
    dice_calls, _bits = _install_draw_recorder(monkeypatch)

    # month 0 => low-pressure band; mmhg 1000 <= 1015 => diff = +2.
    monkeypatch.setattr(weather, "mmhg", 1000, raising=False)
    monkeypatch.setattr(weather, "change", 0, raising=False)
    monkeypatch.setattr(weather, "sky", SkyState.CLOUDLESS, raising=False)
    from mud.time import time_info

    monkeypatch.setattr(time_info, "month", 0, raising=False)

    weather_tick()

    # Exactly three dice draws, in ROM order and with ROM operands.
    assert dice_calls == [(1, 4), (2, 6), (2, 6)]
    # change = diff*d1 + d2 - d3 = 2*1 + 5 - 2 = 5 (NOT 2*1 + 2 - 5 = -1).
    # This asserts the SECOND dice(2,6) is subtracted, not the first.
    assert weather.change == 5
    assert weather.mmhg == 1005


def test_weather_tick_cloudless_draws_one_number_bits_in_transition_band(monkeypatch):
    """CLOUDLESS + 990<=mmhg<1010 draws number_bits(2) exactly once."""
    _dice, bits_calls = _install_draw_recorder(monkeypatch)

    monkeypatch.setattr(weather, "mmhg", 1000, raising=False)
    monkeypatch.setattr(weather, "change", 0, raising=False)
    monkeypatch.setattr(weather, "sky", SkyState.CLOUDLESS, raising=False)
    from mud.time import time_info

    monkeypatch.setattr(time_info, "month", 0, raising=False)

    weather_tick()

    # mmhg after change = 1005 (< 1010, >= 990): the CLOUDLESS branch draws
    # number_bits(2) once (fake returns 0 => sky becomes CLOUDY).
    assert bits_calls == [2]
    assert weather.sky == SkyState.CLOUDY
