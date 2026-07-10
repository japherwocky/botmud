# Session Summary — 2026-07-09 — Autonomous loop: differential harness finds 5 render-layer divergences

**Mode:** autonomous loop ("complete 10 sessions"), reframed per advisor as **10
committed, self-maintaining units** — real gap closures + differential-harness
locks + a verified doc reconciliation — never a fabricated fix to hit a number.

## Headline

The per-file audit tracker was declared "converging / awaiting review" at the
start (v2.14.273). **This session disproves that for the command render layer.**
Driving the **differential harness** (C-oracle ⇄ Python replay) at *unswept
command surfaces* surfaced **five real ROM-parity divergences** that the per-file
audits had marked complete — because each bug lived in a name-render call, a
swapped constant, a list-iteration order, or a missing capitalization, not in the
audited control flow.

**Takeaway for the next agent: the differential-harness-on-unswept-command-
surfaces mode is finding real bugs the per-file audits miss. Keep going.**

## Units delivered (10)

| # | Unit | Kind | Result |
|---|------|------|--------|
| 1 | Reconcile stale OLC/JSON audit function-inventory rows (HEDIT/OLC_MPCODE/OLC_SAVE/JSON_LOADER) | doc | verified each ✅ against code+ROM, flipped stale ❌/⚠️ → ✅/N/A |
| 2 | `position_transitions` scenario | lock | do_stand/rest/sit/sleep/wake — converges |
| 3 | **LOOK-012** — `look <dir>` reported every door "closed" | **bug** | swapped `EX_ISDOOR`/`EX_CLOSED` bits |
| 4 | **FINDING-042** — `scan` leaked aura tags | **bug** | `describe_character` where ROM uses bare PERS |
| 5 | `exits_listing` scenario | lock | do_exits closed-exit hiding — converges |
| 6 | **LOOK-013 / FINDING-043** — fight-line leaked aura tags | **bug** | found by `describe_character` call-site sweep |
| 7 | **FINDING-044** — `where <name>` returned wrong duplicate | **bug** | char_list head-insert (LIFO) vs registry append order |
| 8 | `drink_liquid_messages` scenario (act_obj.c) | lock | do_drink liquid names + thirst-quenched — converges |
| 9 | `emote_command` scenario (act_comm.c) | lock | do_emote incl. "Moron!" quirk — converges |
| 10 | **LOOK-014 / FINDING-045** — look-at-char health line not capitalized | **bug** | missing ROM `buf[0]=UPPER` |

**5 real bugs fixed, 4 clean differential locks, 1 verified doc reconciliation.**

## The five bugs (all `act_info.c` render/list functions except FINDING-044/where)

- **LOOK-012** (`_look_direction`): hardcoded `EX_ISDOOR=2, EX_CLOSED=1` — swapped
  vs ROM `merc.h` (`ISDOOR=1, CLOSED=2`). Every door has the ISDOOR bit, so the
  swapped `& EX_CLOSED(1)` was always truthy → every keyword'd door read "closed".
  Fix: import canonical constants. (v2.14.274)
- **FINDING-042** (`do_scan`): rendered characters via `describe_character` (aura
  tags) where ROM `scan_char` uses bare `PERS`. Fix: `pers()`. (v2.14.275)
- **LOOK-013 / FINDING-043** (`_room_occupant_line` fight branch): same
  `describe_character`-vs-PERS class; found by sweeping every `describe_character`
  call site after FINDING-042. Fix: `pers()`. (v2.14.276)
- **FINDING-044** (`do_where` arg-search): iterated `character_registry`
  (append/oldest-first) forward; ROM walks `char_list` head-first (newest-first,
  because `create_mobile` head-inserts) and returns the first match. Fix:
  `reversed(character_registry)`. (v2.14.277)
- **LOOK-014 / FINDING-045** (`_look_char`): health line not capitalized; ROM
  `show_char_to_char_1` does `buf[0]=UPPER`. A mob's lowercase short_descr stayed
  lowercase ("the beastly fido is in excellent condition."). Fix: capitalize the
  first char. (v2.14.278)

## Notable

- **`describe_character` is now production-dead** — after FINDING-042/043 removed
  its two remaining callers, it is referenced only by two tests
  (`test_spell_affects_persistence`, `test_sanctuary_affect_visual_indicator`)
  that exercise it directly. This is correct, not a regression: ROM renders auras
  only in the room-occupant tag block, which Python does via `_char_tags`
  (LOOK-011). **Follow-up:** consider deleting `describe_character` + migrating
  those two tests to `_char_tags`, OR keep it as the canonical name+aura helper —
  maintainer call. It is not a live code path today.
- **Diversification held:** all 5 bugs are name-render/list functions; the
  `act_obj.c` (drink) and `act_comm.c` (emote) probes both converged first pass.
  The render-layer bug cluster is `act_info.c`-specific.

## Test / infra

- Suite: **6125 passed, 4 skipped, 0 failed** (full parallel run excluding the 1
  documented-flaky file `test_character_advancement.py`; validated the LOOK-014
  fix + all new scenarios). The default parallel run over the *whole* tree is
  currently blocked by the known xdist worker-crash — `KeyError: <WorkerController
  gwN>` in loadscope `_assign_work_unit`, which aborts the run and eats the
  failure summary. Both parallel attempts crashed; the serial run is the
  authoritative green check this session).**
- 4 new diff_harness scenarios converge; 2 (`look_direction`, `scan_directions`,
  `where_command`, `look_at_character`) were red-then-green across their fixes.
- Version 2.14.273 → **2.14.278**.

## Outstanding / next

1. **xdist worker-crash (environmental).** `KeyError: <WorkerController gwN>` in
   `loadscope.py:_assign_work_unit` intermittently aborts the *parallel* full
   suite (session memory notes a root-cause + local fix plan already exists). Not
   a test failure — serial `-n0` is clean. Worth landing the known fix so CI/full
   runs are reliable.
2. **Keep mining the differential harness at unswept command surfaces** — this
   session shows it still finds real bugs. Candidate render surfaces not yet
   locked: `do_score`/`do_worth`, `do_socials`, container/`look in` deep contents,
   object extra-descr rendering, `do_wear`/`do_remove` full cycle messages.
   Sweep other ROM `buf[0]=UPPER`/`capitalize()` sites (LOOK-014 class).
3. **`describe_character` cleanup** (see Notable) — small, optional.
4. All commits are **local on `master`, UNPUSHED** — awaiting user review, per
   prior-session convention. Do not push without confirmation.

## Method notes (for reuse)

- The high-yield loop: pick an unswept command with a deterministic surface →
  author a diff_harness scenario → `capture --scenario X` (C oracle) → run the
  replay → a divergence is a **finding** (triage vs ROM source, fix Python, never
  edit the golden). Converged scenarios are still valuable locks.
- After fixing a bug, **sweep for the same class** (FINDING-042 → 043 came free
  from grepping every `describe_character` call site).
