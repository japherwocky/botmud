# Session Status — 2026-07-09 — Autonomous loop: differential harness finds 5 render-layer divergences (LOCAL, UNPUSHED)

## Current State

- **Active focus**: **Differential-harness-on-unswept-command-surfaces** — this is
  the productive mode right now. The per-file audit tracker was declared
  "converging" last session; **that is now disproven for the command render
  layer.** Driving the C-oracle ⇄ Python replay at unswept commands surfaced
  **5 real ROM-parity divergences** the per-file audits marked complete (the bug
  lived in a name-render call / swapped constant / list order / capitalization,
  not the audited control flow).
- **This session (v2.14.273 → v2.14.278, all committed LOCALLY on `master`,
  NOT pushed):** 10 units — 5 real bug fixes, 4 differential locks, 1 verified
  doc reconciliation. See the summary for the full table.
  - **LOOK-012** — `look <dir>` reported every door "closed" (swapped `EX_ISDOOR`/
    `EX_CLOSED` bits).
  - **FINDING-042** — `scan` leaked aura tags (`describe_character` vs bare PERS).
  - **LOOK-013 / FINDING-043** — fight-line leaked aura tags (found by sweeping
    every `describe_character` call site after 042).
  - **FINDING-044** — `where <name>` returned the wrong duplicate (char_list
    head-insert order vs registry append order).
  - **LOOK-014 / FINDING-045** — look-at-char health line not capitalized (missing
    ROM `buf[0]=UPPER`).
  - 4 new converging locks: `position_transitions`, `exits_listing`,
    `drink_liquid_messages` (act_obj.c), `emote_command` (act_comm.c).
  - Doc: reconciled stale OLC/JSON audit function-inventory rows.
- **Pointer to latest summary**:
  [SESSION_SUMMARY_2026-07-09_AUTONOMOUS_LOOP_RENDER_DIVERGENCES.md](SESSION_SUMMARY_2026-07-09_AUTONOMOUS_LOOP_RENDER_DIVERGENCES.md)

## Project Status (snapshot)

| Metric | Value |
|--------|-------|
| Version | 2.14.278 |
| Tests | **6125 passed, 4 skipped, 0 failed** (full parallel run excluding the 1 documented pre-existing flake, see below) |
| ROM C files audited | 43 / 43 |
| Push status | **All local on `master`, UNPUSHED** — awaiting user review |
| Active focus | Differential harness at unswept command surfaces (finding real bugs) |

## Known pre-existing flake (NOT this session's work)

`tests/integration/test_character_advancement.py::test_kill_mob_grants_xp_integration`
**hangs** (→ `--timeout=120` fires): its fixture monkeypatches
`mud.utils.rng_mm.number_bits → 19`, and `game_tick → mobile_update → spec_mayor
→ spec_cast_mage → _select_spell` (`spec_funs.py:850`) loops forever on the
never-valid roll. Documented on HEAD before this session; orthogonal to the
render/where changes here (not in the call stack). It also masks itself in a
parallel run behind the separate **xdist worker-crash** (`KeyError:
<WorkerController gwN>` in `loadscope.py:_assign_work_unit`), which aborts the
default `-n auto` full run and eats the failure summary — so the authoritative
green check this session was a serial `-n0` run (minus the flaky file).

## Next Intended Task

1. **Review + push** the 2.14.274→278 commits (all local on `master`).
2. **Keep mining the differential harness at unswept command surfaces** — it is
   still finding real bugs. Candidates: `do_score`/`do_worth`, `do_socials`,
   `look in` deep contents, object extra-descr, `do_wear`/`do_remove` message
   cycle; sweep other ROM `buf[0]=UPPER`/`capitalize()` sites (LOOK-014 class).
3. **Land the known xdist worker-crash fix** (session memory notes a root cause +
   local plan) so the parallel full suite is reliable again.
4. Optional: `describe_character` is now production-dead (auras render via
   `_char_tags`); delete it + migrate its 2 remaining test callers, or keep as the
   canonical name+aura helper — maintainer call.
