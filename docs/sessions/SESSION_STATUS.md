# Session Status — 2026-07-10 — Autonomous /loop command-handler sweep (8 fixes, LOCAL/UNPUSHED)

## Current State

- **Active focus**: **Source-read + parallel-hunter sweep of unswept command
  handlers** — still the productive mode. Hunters compare batches of command
  functions against ROM C; every candidate is re-verified against `src/*.c` by
  hand before closing. This run closed **8 real parity divergences** the per-file
  audits had marked complete (spurious inserted guard, wrong key threshold, wrong
  guard order, dropped message bytes, a phantom-attribute dead-code block).
- **This run (v2.14.288 → v2.14.296, all committed LOCALLY on `master`, NOT
  pushed):** 8 `fix(parity)` commits + 2 `docs(parity)` filing commits. See the
  summary for the full table.
  - **LOCK-001 / LOCK-002** — container lock/unlock guard sequence (spurious
    `CLOSEABLE` check; `<=0` vs `<0` key threshold).
  - **PASSWORD-002** — `do_password` syntax period + wrong-password double-space.
  - **HEALER-007** — `heal` price-list header capitalization.
  - **LOOK-016** (HIGH) — `look <char>` never showed worn equipment (phantom
    `char.equipped` attribute; real attr is `char.equipment`).
  - **LOOK-017** — room list omitted a standing PC's title.
  - **KICK-001** — `do_kick` level gate must precede the `fighting==NULL` check.
  - **TRIP-001** — `do_trip` no-skill message double-space.
- **Pointer to latest summary**:
  [SESSION_SUMMARY_2026-07-10_AUTONOMOUS_LOOP_COMMAND_SWEEP.md](SESSION_SUMMARY_2026-07-10_AUTONOMOUS_LOOP_COMMAND_SWEEP.md)

## Project Status (snapshot)

| Metric | Value |
|--------|-------|
| Version | 2.14.296 |
| Tests | Full suite **green (exit 0)**; ~13 new tests added across the 8 fixes (prior baseline 6134 passed / 4 skipped) |
| ROM C files audited | 43 / 43 |
| Push status | **All local on `master`, UNPUSHED** — awaiting user review |
| Active focus | Source-read + hunter sweep of unswept command handlers |

## Outstanding — verified rows filed for a future pass

- **BASH-001** (MEDIUM, open) — `do_bash` never delivers the attacker's TO_CHAR
  flavor line and all bash broadcasts drop ROM's `{5…{x` color. Needs the
  `apply_damage` push-vs-return single-delivery contract (INV-001) worked out;
  model on `do_trip`. Highest-priority open item — player-facing.
- **STEAL-001** (minor) — `do_steal` never calls `check_improve`.
- **RESCUE-002** (low) — `skill_handlers.rescue` name vs ROM `$N`/PERS (NPC edge).
- **is_number/atoi class** — DROP-001 + WIMPY-002 want one shared
  `rom_is_number`/`rom_atoi` helper.
- **Latent (unreachable in stock data):** LOCK-003 (door key `<=0`), DESC-001
  (`do_description` plain-replace 1024 guard).

## Next Intended Task

1. **Review + push** the v2.14.289→296 commits (all local on `master`).
2. **Continue the hunter sweep** — next batch: `do_cast` failure/mana messages,
   `do_quaff`/`do_zap` wand, `do_eat`, `do_wear`/`do_remove` edge messages,
   `do_sit`/`do_rest`/`do_sleep` furniture messages.
3. **Close BASH-001** as a dedicated gap-closer (confirm the single-delivery
   contract first).
4. Consider a shared `rom_is_number`/`rom_atoi` helper to close DROP-001 +
   WIMPY-002 together.
