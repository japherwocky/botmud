"""GL-045 — obj_update affect-fade RNG draw is unconditional (update.c:933).

ROM ``obj_update`` fades each object affect's strength with:

    if (number_range (0, 4) == 0 && paf->level > 0)   /* src/update.c:933 */
        paf->level--;

C ``&&`` short-circuits left-to-right and ``number_range`` advances the shared
Mitchell-Moore stream as a side effect, so the roll is consumed
**unconditionally** for every object affect with ``duration > 0`` — the
``level > 0`` test only gates the decrement, not the draw. This is the exact
GL-026 hazard already fixed on the *character* affect-fade path
(``mud/affects/engine.py:65``, whose comment documents it). The object path in
``mud/game_loop.py:_tick_object_affects`` had the operands swapped
(``level > 0 and number_range(...) == 0``), so a level-0 object affect skipped
the draw and desynced every subsequent RNG consumer in the pulse relative to
ROM (breaking lockstep differential replay).
"""

from __future__ import annotations

from types import SimpleNamespace

import mud.game_loop as game_loop
from mud.game_loop import _tick_object_affects


def _count_number_range(monkeypatch) -> list[tuple[int, int]]:
    calls: list[tuple[int, int]] = []
    real = game_loop.rng_mm.number_range

    def counting(low: int, high: int) -> int:
        calls.append((low, high))
        return real(low, high)

    monkeypatch.setattr(game_loop.rng_mm, "number_range", counting)
    return calls


def test_level0_object_affect_still_draws_number_range(monkeypatch):
    """A level-0, duration>0 object affect must consume one number_range(0,4)."""
    calls = _count_number_range(monkeypatch)
    game_loop.rng_mm.seed_mm(12345)

    affect = SimpleNamespace(type=1, duration=5, level=0)
    obj = SimpleNamespace(affected=[affect])

    _tick_object_affects(obj)

    # ROM draws the fade roll unconditionally for every duration>0 affect.
    assert calls == [(0, 4)], f"expected exactly one number_range(0,4) draw, got {calls}"
    # duration decremented; level stays 0 (already floored).
    assert affect.duration == 4
    assert affect.level == 0


def test_positive_level_object_affect_draws_number_range(monkeypatch):
    """A level>0, duration>0 affect also draws exactly once (unchanged path)."""
    calls = _count_number_range(monkeypatch)
    game_loop.rng_mm.seed_mm(12345)

    affect = SimpleNamespace(type=1, duration=5, level=10)
    obj = SimpleNamespace(affected=[affect])

    _tick_object_affects(obj)

    assert calls == [(0, 4)]
    assert affect.duration == 4
