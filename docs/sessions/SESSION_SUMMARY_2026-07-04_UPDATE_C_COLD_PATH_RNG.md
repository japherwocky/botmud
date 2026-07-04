# Session Summary — 2026-07-04 — update.c cold-path RNG/math divergence hunt

## Scope

Cross-file / cold-path divergence hunting on `src/update.c` (the per-tick
`char_update` / `mobile_update` / regen / weather / obj decay surface). The
per-file audit tracker has no ⚠️ Partial / ❌ Not Audited rows, so cross-INV /
cold-path probing is the active pass. Method: dispatched **six parallel probe
agents**, each pairing one ROM C tick function against its Python equivalent and
reporting concrete behavioral divergences (RNG draw order/count, signed math,
missing branches) with line citations. Divergences were re-verified against ROM C
source by hand before closing. Five self-contained units landed: **3 fixes + 2
coverage-locks** (2.14.243 → 2.14.247).

The three fixes share one root theme — **shared Mitchell-Moore RNG-stream
determinism**: ROM's RNG is global state, so a single spurious/misordered draw in
any per-tick path shifts every downstream roll in that pulse (combat, saves,
other mobs). All three are siblings of the earlier GL-026/GL-045 draw-order class.

## Outcomes

### `GL-046` — ✅ FIXED — plague-spread RNG draw order/count

- **Python**: `mud/game_loop.py:_char_update_tick_effects` (plague block ~789)
- **ROM C**: `src/update.c:824,829-841`
- **Gap**: the per-tick plague infection loop desynced the shared RNG stream three
  ways vs ROM's `for (vch = ch->in_room->people …)` loop.
- **Fix**: (1) `plague.duration = number_range(1, 2*level)` now drawn **once**
  before the loop (was per-infected-victim); (2) `saves_spell` (a `number_percent`
  draw) now evaluated for **every** occupant as ROM's first `&&` operand (was
  skipped for the carrier/immortals/already-plagued); (3) `number_bits(4)` now
  drawn **last**, only after the save fails and the non-RNG gates pass (was first).
- **Tests**: `tests/integration/test_gl046_plague_spread_rng_order.py` (2) — save
  drawn per-occupant + number_bits gated behind it; duration drawn once and shared
  by co-infected victims. Red pre-fix, green post-fix.

### `GL-047` — ✅ FIXED — regen drain-room UMIN clamp + signed rate math

- **Python**: `mud/game_loop.py:hit_gain` / `mana_gain` / `move_gain`
- **ROM C**: `src/update.c:215-229,297-315,365-366` (returns `UMIN(gain, max-cur)`)
- **Gap**: ROM returns a plain `min` that goes **negative** when a room's
  `heal_rate`/`mana_rate` is negative (a "drain room", representable via OLC
  `redit_heal`/`redit_mana` or the signed area loader), and the caller subtracts
  it to drain the pool (`:698`). The port returned `max(0, min(gain, deficit))`,
  swallowing the drain. Separately, once the rate multiply makes `gain` negative,
  the rate `/100`, furniture `/100`, and poison `/4` / plague `/8` / haste `/2`
  divisions must truncate toward 0 like C; the port floored with bare `//`.
- **Fix**: removed the `max(0, …)` clamp (return `min(gain, deficit)` = ROM UMIN,
  raw signed deficit since the caller gates on `< max`); switched the six
  post-rate divisions in each of the three functions to `c_div`.
- **Tests**: `tests/integration/test_gl047_regen_drain_room.py` (4) — drain returns
  negative; rate multiply + post-rate poison division truncate toward 0; mana/move
  share the contract.

### `GL-048` — ✅ FIXED — mob delay-trigger ends the tick unconditionally

- **Python**: `mud/mobprog.py:mp_delay_trigger` (consumed at `mud/ai/__init__.py`)
- **ROM C**: `src/update.c:448-454` (`mobile_update` TRIG_DELAY block)
- **Gap**: on delay expiry ROM fires the trigger and `continue`s **unconditionally**
  (discarding `mp_percent_trigger`'s bool), so the mob never scavenges/wanders that
  tick. The port returned that bool, so a **failed** percent roll let the mob fall
  through into `_maybe_scavenge` (`number_bits(6)`) + `_maybe_wander`
  (`number_bits(3/5)`) — extra draws off the shared stream plus item pickup /
  movement ROM never performs. Also missing the `HAS_TRIGGER(TRIG_DELAY)` gate, so
  a mob with no delay program still counted its `mprog_delay` down.
- **Fix**: gate on `mob_has_trigger(mob, Trigger.DELAY)`; on expiry call
  `mp_percent_trigger` for side effects then `return True` unconditionally.
  Diff-harness `mob_delay_trigger` C-golden still converges (56 smoke tests green).
- **Tests**: `tests/integration/test_gl048_mp_delay_trigger_parity.py` (3).

### Coverage-lock — `gain_condition` DRUNK sober-message old-value guard

- **Python**: `mud/characters/conditions.py:49`
- **ROM C**: `src/update.c:391-394` (`if (condition != 0) send "You are sober."`)
- Probe found `gain_condition` a faithful port (no divergence). Locked the
  previously-untested DRUNK branch: "You are sober." fires only when the slot was
  non-zero before ticking to 0, so an already-sober idle player is not re-notified
  (unlike HUNGER/THIRST, which fire unconditionally at 0).
- **Tests**: `tests/integration/test_gain_condition_drunk_sober_guard.py` (3).

### Coverage-lock — `aggr_update` victim reservoir selection

- **Python**: `mud/ai/aggressive.py:101-106`
- **ROM C**: `src/update.c:1115-1131`
- Probe confirmed the reservoir matches ROM. Locked the draw sequence (one
  `number_range(0, count)` per eligible victim in `room.people` order; count==0
  always selects the first, later victims replace iff their roll wins) — a classic
  shared-RNG desync site with only probabilistic coverage before.
- **Tests**: `TestAggressiveUpdateVictimReservoir` in
  `tests/integration/test_mob_ai.py` (2).

## Probes that found no divergence (verified faithful)

- **`weather_update`** — `time_tick`/`weather_tick` match ROM's dice/number_bits
  draw sequence, sky state machine, thresholds, recipient filter. Draw order
  already locked by `tests/test_weather_tick_draw_order.py`. (One C-unspecified
  operand-order risk on `diff*dice(1,4)+dice(2,6)-dice(2,6)` is already frozen
  left-to-right by that test.)
- **`obj_update`** — every decay string, timer branch, affect wear-off, RNG draw,
  and head-insert content-dump order matches (GL-039/040/045 hold; no sibling).
- **`update_pos`** — HP bands / NPC-vs-PC branch match `src/fight.c` exactly.
- **`mobile_update` scavenge/wander & `aggr_update` gates** — RNG draw order/count,
  eligibility, head-insert walk order all match (GL-043/044 hold).

## Files Modified

- `mud/game_loop.py` — GL-046 (plague loop) + GL-047 (hit/mana/move_gain drain +
  c_div)
- `mud/mobprog.py` — GL-048 (`mp_delay_trigger` gate + unconditional True)
- `tests/integration/test_gl046_plague_spread_rng_order.py` — new (2)
- `tests/integration/test_gl047_regen_drain_room.py` — new (4)
- `tests/integration/test_gl048_mp_delay_trigger_parity.py` — new (3)
- `tests/integration/test_gain_condition_drunk_sober_guard.py` — new (3)
- `tests/integration/test_mob_ai.py` — appended `TestAggressiveUpdateVictimReservoir` (2)
- `docs/parity/UPDATE_C_AUDIT.md` — added GL-046 / GL-047 / GL-048 rows (all ✅ FIXED)
- `CHANGELOG.md` — Fixed: GL-046/047/048; Added: 2 coverage-locks
- `pyproject.toml` — 2.14.242 → 2.14.247

## Test Status

- New tests: `test_gl046…` (2), `test_gl047…` (4), `test_gl048…` (3),
  `test_gain_condition_drunk_sober_guard` (3), reservoir (2) — 14 new, all green.
- Regression slices run green: `test_char_update_rom_parity`, `test_game_loop`,
  `test_update_c_parity`, `test_mobprog_triggers`, `test_mob_ai`,
  differential smoke (56).
- **Full suite: 6092 passed, 4 skipped, 0 failed** (173s). 40 errors are the
  documented pre-existing starlette/aiohttp `Router.__init__()` collection errors
  in 4 network/session files (`test_websocket_server`, `test_prompt_cmd_parity`,
  `test_inv009_registry_disconnect_cleanup`, `test_nanny_saveload_runtime_path`) —
  unrelated to this session's changed areas.

## Next Steps

Continue cold-path / cross-INV divergence hunting — `src/update.c` per-tick
functions are now swept (regen, gain_condition, weather, obj_update, char_update,
update_pos, aggr_update, mobile_update all probed). Candidate next areas: the
`affect_update` / `tick_spell_effects` wear-off path, the `damage()` core, or
`move_char` follower/portal edges. Opportunistic non-urgent item still open from
the prior session: the **PC** side of `do_trip` uses `_character_skill_percent`
instead of `get_skill` (no class-gate/daze/drunk) — migrate when that surface is
next touched.

**Not yet pushed to remote / released to PyPI** — commits are local on `master`
(ac71e82f → 5a095690). Awaiting confirmation before the outward-facing push.
