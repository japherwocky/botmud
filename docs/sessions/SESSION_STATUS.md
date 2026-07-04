# Session Status — 2026-07-04 — Autonomous /loop: 15 cold-path parity units (LOCAL, UNPUSHED)

## Current State

- **Active focus**: Cross-file invariants / cold-path divergence hunting (per-file
  audit tracker exhausted). This session ran a 15-unit autonomous `/loop`.
- **Last completed** (2.14.249 → **2.14.264**, all committed **locally on
  `master`, NOT pushed** — `bfe11040` → `86179e98`):
  - **13 ROM-parity bug fixes**: EAT-008, WEAR-010, PUT-004 (INV-011), GET-016,
    BUY-011, SELL-005 (act_obj object/shop); FIGHT-092 (invisible attacker revealed
    on hit); MOVE-008 (container open/close order); MAGIC-047 (stone_skin
    caster-gate), MAGIC-048 (chain_lightning bounce), MAGIC-049 (dispel_magic save
    gate); AFFECTS-001 (affects double-colon), LOOK-010 (aura order + double-render);
    PRACTICE-002 (below-level practice gate).
  - **2 coverage-locks**: `aggr_update` reservoir (earlier session), and this
    session's xp_compute neutral-align `c_div` truncation.
- **Pointer to latest summary**:
  [SESSION_SUMMARY_2026-07-04_AUTONOMOUS_LOOP_15_GAPS.md](SESSION_SUMMARY_2026-07-04_AUTONOMOUS_LOOP_15_GAPS.md)
  (the earlier same-day update.c cold-path session is
  [SESSION_SUMMARY_2026-07-04_UPDATE_C_COLD_PATH_RNG.md](SESSION_SUMMARY_2026-07-04_UPDATE_C_COLD_PATH_RNG.md))

## Project Status (snapshot)

| Metric | Value |
|--------|-------|
| Version | 2.14.264 |
| Tests | **6127 passed, 4 skipped, 0 failed** (full suite via `.venv`, 180s) |
| Cross-file invariants | INV-054 latest (unchanged); INV-011 touched by PUT-004 |
| Push status | **All local on `master`, UNPUSHED** — awaiting user review |
| Active focus | Cross-file invariants / cold-path divergence hunting |

## Open follow-ups (filed this session, not yet closed)

- **FIGHT-093** — damage() 1200 loophole cap + check_killer absent from apply_damage.
- **MOVE-009** — do_flee inline movement skips act broadcasts + follower cascade.
- **MAGIC-046** — heat_metal MobInstance carry-order.
- **MAGIC-050** — dispel_magic effect-list order + per-effect room messages.
- **SPLIT-001** — do_split non-ROM `N gold`/`silver` keyword form (intentional
  QuickMUD convenience; maintainer to decide whether to strip for strict parity).
- **LOOK missing char tags** — Python renders 2 of ROM's ~12 (AFK/Invis/Wizi/Hide/
  Charmed/Translucent/Red-Aura/Golden-Aura/KILLER/THIEF).

## Next Intended Task

1. **Review + push.** 15 commits are local on `master`, unpushed. Review, then
   `git push origin master`; optionally release 2.14.264 to PyPI.
2. **Reindex GitNexus** — the on-disk index is stale (last `bfe1104`); the
   background `npx gitnexus analyze` was failing with exit 144 this session (grep
   fallback used, AGENTS.md-sanctioned). Run `npx gitnexus analyze --skip-agents-md`.
3. **Run tests from `.venv`** (`.venv/bin/python -m pytest`) — the system framework
   Python is over-constrained (see AGENTS.md "Build / Lint / Test → Environment").
4. Continue cold-path / cross-INV hunting, or burn down the six OPEN follow-ups.

**Known flake:** `tests/integration/test_character_advancement.py` (a
`spec_cast_mage` test mocking `number_bits`→19) hangs when run in isolation
(`-n0` single file) but passes in the full suite — a pre-existing RNG-leak
isolation flake, present on HEAD independent of this session.
