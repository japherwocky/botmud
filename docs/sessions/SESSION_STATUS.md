# Session Status — 2026-07-10 — Autonomous /loop command-handler sweep COMPLETE (10 fixes, LOCAL/UNPUSHED)

## Current State

- **Active focus**: **Source-read + parallel-hunter sweep of unswept command
  handlers** — still the productive mode. Hunters compare batches of command
  functions against ROM C; every candidate is re-verified against `src/*.c` by
  hand before closing. This run closed **8 real parity divergences** the per-file
  audits had marked complete (spurious inserted guard, wrong key threshold, wrong
  guard order, dropped message bytes, a phantom-attribute dead-code block).
- **This run (v2.14.288 → v2.14.298, all committed LOCALLY on `master`, NOT
  pushed) — the loop is now COMPLETE and STOPPED:** 10 `fix(parity)` commits +
  several `docs(parity)` filing commits. See the summary for the full table.
  - **LOCK-001 / LOCK-002** — container lock/unlock guard sequence (spurious
    `CLOSEABLE` check; `<=0` vs `<0` key threshold).
  - **PASSWORD-002** — `do_password` syntax period + wrong-password double-space.
  - **HEALER-007** — `heal` price-list header capitalization.
  - **LOOK-016** (HIGH) — `look <char>` never showed worn equipment (phantom
    `char.equipped` attribute; real attr is `char.equipment`).
  - **LOOK-017** — room list omitted a standing PC's title.
  - **KICK-001** — `do_kick` level gate must precede the `fighting==NULL` check.
  - **TRIP-001** — `do_trip` no-skill message double-space.
  - **BASH-001** — `do_bash` attacker flavor TO_CHAR line + `{5…{x` color
    (ROM `damage(…,FALSE)` suppresses the dam_message; flavor replaces it).
  - **PUT-005** — `put all <container>` with nothing eligible now silent (ROM has
    no message).
- **Pointer to latest summary**:
  [SESSION_SUMMARY_2026-07-10_AUTONOMOUS_LOOP_COMMAND_SWEEP.md](SESSION_SUMMARY_2026-07-10_AUTONOMOUS_LOOP_COMMAND_SWEEP.md)

## Project Status (snapshot)

| Metric | Value |
|--------|-------|
| Version | 2.14.298 |
| Tests | **6163 passed, 4 skipped** (full parallel run). One run exited 0; a second showed the 2 documented cross-file RNG-leak order flakes (`test_mobprog_triggers::test_event_hooks_fire_rom_triggers`, `test_skills_combat::test_trip_knocks_target_wait_daze_and_improve`) — both **pass in isolation** (`-n0`), confirmed, plus the harmless xdist `sessionfinish` teardown error. No regression from this run's 8 fixes. |
| ROM C files audited | 43 / 43 |
| Push status | **All local on `master`, UNPUSHED** — awaiting user review |
| Active focus | Source-read + hunter sweep of unswept command handlers |

## Outstanding — verified rows filed for a future pass

- **~~BASH-001~~ ✅ FIXED (2.14.297)** — `do_bash` flavor TO_CHAR line + `{5…{x`
  color. ROM's `damage(…, FALSE)` suppresses the dam_message so the flavor line
  replaces it; rendered via `act_format`, single-delivery via `show=False`.
- **TRIP-002** (CONFIRMED REAL, DEFERRED — filed in `FIGHT_C_AUDIT`) — `do_trip`
  failure double-delivers the miss dam_message (push at `engine.py:231` + command
  return; empirically count==2). The fix is one line (`return ""`) but it breaks
  `TestTripRomParity::test_trip_chance_{size,level}_...`, which are themselves
  mis-specified (expected chances ignore the dex modifier). Rewriting those as
  differentials surfaced a **second unverified suspicion**: the trip size modifier
  shifts chance by ~7 where ROM's `*10` predicts 20 — needs its own probe. Deferred
  to a dedicated pass (fix + 3 chance-test rewrites + size-delta probe) rather than
  force it through a red/questionable suite.
- **STEAL-001** (minor) — `do_steal` never calls `check_improve`.
- **RESCUE-002** (low) — `skill_handlers.rescue` name vs ROM `$N`/PERS (NPC edge).
- **is_number/atoi class** — DROP-001 + WIMPY-002 want one shared
  `rom_is_number`/`rom_atoi` helper.
- **Latent (unreachable in stock data):** LOCK-003 (door key `<=0`), DESC-001
  (`do_description` plain-replace 1024 guard).

## Next Intended Task

The autonomous `/loop` run is **complete and stopped** — five hunter batches plus
extensive manual probing have thoroughly swept the command surface (recent
batches mostly clean; only edge-cases and judgment calls remain).

1. **Review + push** the `v2.14.289 → v2.14.298` commits (all local on `master`).
   This is the gating next action.
2. **Close TRIP-002** (dedicated pass): one-line `return ""` fix + rewrite the 3
   mis-specified `TestTripRomParity` chance tests as differentials + probe the
   trip size-modifier suspicion (chance shifts ~7 where ROM's `*10` predicts 20).
3. **Decide GIVE-006** (parity-vs-UX): keep the helpful "You must remove it
   first." or match ROM's "You do not have that item."
4. **Close the `is_number`/`atoi` class** (DROP-001 + WIMPY-002) with one shared
   `rom_is_number`/`rom_atoi` helper.
5. Lower priority: STEAL-001, RESCUE-002, PUT-006; latent LOCK-003, DESC-001.
