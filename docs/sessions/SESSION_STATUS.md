# Session Status — 2026-07-04 — update.c cold-path RNG/math sweep (GL-046..048 + 2 locks)

## Current State

- **Active focus**: Cross-file invariants / cold-path divergence hunting (per-file
  audit tracker exhausted). This session swept `src/update.c`'s per-tick surface
  via six parallel probe agents and closed five self-contained units.
- **Last completed** (2.14.243 → 2.14.247, all committed locally on `master`):
  - **`GL-046`** (✅ FIXED, `ac71e82f`) — plague-spread RNG draw order/count in
    `char_update`. Duration drawn once before the loop; `saves_spell` drawn for
    every occupant (ROM's first `&&` operand); `number_bits(4)` drawn last.
    `src/update.c:824,829-841`.
  - **`GL-047`** (✅ FIXED, `5932df92`) — regen drain-room clamp + signed math.
    `hit_gain`/`mana_gain`/`move_gain` now return `min(gain, deficit)` (ROM UMIN,
    can drain in a negative-rate room) and use `c_div` for the six post-rate-multiply
    divisions. `src/update.c:215-229,297-315,365-366`.
  - **`GL-048`** (✅ FIXED, `4b0d1cf1`) — `mp_delay_trigger` now returns `True`
    unconditionally on delay expiry (ROM's unconditional `continue`) and is gated on
    `HAS_TRIGGER(TRIG_DELAY)`, so a failed delay roll no longer leaks into
    scavenge/wander. `src/update.c:448-454`. Diff-harness golden still converges.
  - **Coverage-lock** (`6a04a5c8`) — `gain_condition` DRUNK sober-message old-value
    guard (`src/update.c:391-394`).
  - **Coverage-lock** (`5a095690`) — `aggr_update` victim reservoir selection order
    (`src/update.c:1115-1131`).
- **Pointer to latest summary**:
  [SESSION_SUMMARY_2026-07-04_UPDATE_C_COLD_PATH_RNG.md](SESSION_SUMMARY_2026-07-04_UPDATE_C_COLD_PATH_RNG.md)

## Project Status (snapshot)

| Metric | Value |
|--------|-------|
| Version | 2.14.248 |
| Tests | Full suite green — **6110 passed, 4 skipped, 0 failed** (the 40 prior starlette-collection errors resolved via the project `.venv`). Run tests from `.venv` — see AGENTS.md "Environment". |
| Cross-file invariants | INV-054 latest (unchanged) |
| update.c cold paths | regen / gain_condition / weather / obj_update / char_update / update_pos / aggr_update / mobile_update all probed this session |
| Active focus | Cross-file invariants / cold-path divergence hunting |

## Next Intended Task

`src/update.c`'s per-tick functions are now swept. Continue cold-path / cross-INV
divergence hunting on adjacent surfaces: the `affect_update` / `tick_spell_effects`
wear-off path, the `damage()` core, or `move_char` follower/portal edges. Use the
probe-then-scope method (read ROM C contract → read Python equivalent → one failing
test), then close as a gap or file the next free INV-NNN.

Opportunistic (non-urgent) carryover: the **PC** side of `do_trip` still uses
`_character_skill_percent` instead of `get_skill` (no class-gate/daze/drunk) —
migrate when that surface is next touched.

**Tooling note:** GitNexus MCP was up this session; the on-disk index was reindexed
after each commit. **Environment:** run tests from the project `.venv`
(`.venv/bin/python -m pytest`), not the system Python — the shared framework Python
is over-constrained across projects (fastapi/gradio vs sse-starlette on starlette)
and silently broke 4 web/session test files at collection. One-time setup + full
rationale in AGENTS.md "Build / Lint / Test → Environment". A per-test
`--timeout=120` hang-guard is now in the default addopts. The intermittent xdist
**sessionfinish** teardown flake still recurs (harmless — a worker IPC hang/error
*after* all tests report); if the summary line doesn't flush, re-run or trust the
`0 failed` from the progress stream.

**Push status:** the five commits (`ac71e82f` → `5a095690`) are **local on
`master`, not pushed to remote or released to PyPI** — awaiting confirmation for the
outward-facing step.
