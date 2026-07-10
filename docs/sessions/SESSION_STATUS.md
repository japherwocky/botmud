# Session Status — 2026-07-09 — Autonomous loop batch 2: 10 render + wear/equip divergences (LOCAL, UNPUSHED)

## Current State

- **Active focus**: **Source-read + parallel-hunter sweep of unswept command
  surfaces** — still the productive mode. Driving ROM-C-vs-Python comparison at
  command render/dispatch surfaces (via careful source reading and `general-purpose`
  hunter subagents whose findings I re-verify against ROM myself) surfaced **10
  real ROM-parity divergences** the per-file audits had marked complete — the bug
  lived in a skipped ROM accessor, a wrong message string, a rewritten formula, a
  wrong dispatch key, or a wrong flag precedence, not the audited control flow.
- **This session (v2.14.278 → v2.14.288, all committed LOCALLY on `master`, NOT
  pushed):** 10 units, all real bug fixes, each failing-test-first + one
  `fix(parity)` commit. See the summary for the full table.
  - **SCORE-002** — `score` carry-weight ignored coin burden.
  - **LOOK-015** — `look in` drink-container fill band diverged at the C
    truncation boundary (rewritten percentage vs ROM's `value[0]/4` integer compares).
  - **COMPARE-002** — wrong "missing second item" message.
  - **INTERP-035** — sleeping "snore" social exception keyed on the typed string,
    not the resolved social (so `snor` was wrongly blocked while asleep).
  - **EQUIP-002 / INVEN-001** — `equipment` and `inventory` dropped ROM
    `format_obj_to_char` status tags `(Glowing)/(Invis)/(Magical)/aura`; inventory
    also mis-deduped a glowing item with a plain identical one.
  - **RECALL-003** — `recall` command NPC gate returned "" silently and keyed on
    `master` instead of the `ACT_PET` flag.
  - **WEAR-013** — two-hands wield-block punctuation (`!` → `.`).
  - **WEAR-014** — alignment "zap" now drops the item to the floor (was left
    carried), with a `$p`-named TO_CHAR + TO_ROOM message per ROM `equip_char`.
  - **WEAR-015** — armor wear-flags now precede HOLD in dispatch order.
- **Pointer to latest summary**:
  [SESSION_SUMMARY_2026-07-09_AUTONOMOUS_LOOP_BATCH_2_RENDER_AND_WEAR.md](SESSION_SUMMARY_2026-07-09_AUTONOMOUS_LOOP_BATCH_2_RENDER_AND_WEAR.md)

## Project Status (snapshot)

| Metric | Value |
|--------|-------|
| Version | 2.14.288 |
| Tests | **6134 passed, 4 skipped** (full serial run, excluding 1 documented pre-existing hang; 2 further failures are known cross-file RNG-leak order flakes that pass in isolation — see below) |
| ROM C files audited | 43 / 43 |
| Push status | **All local on `master`, UNPUSHED** — awaiting user review |
| Active focus | Source-read + hunter sweep of unswept command surfaces (still finding real bugs) |

## Known pre-existing flakes (NOT this session's work)

1. `tests/integration/test_character_advancement.py::test_kill_mob_grants_xp_integration`
   **hangs** (fixture monkeypatches `number_bits → 19` → `spec_cast_mage →
   _select_spell` loops). Excluded from the authoritative serial run.
2. Two order-dependent **RNG-leak flakes** surfaced only in the serial full run and
   **pass in isolation**: `test_mobprog_triggers.py::test_event_hooks_fire_rom_triggers`
   and `test_skills_combat.py::test_trip_knocks_target_wait_daze_and_improve`.
   Cross-file RNG-state leak class (AGENTS.md "Parallel test execution & isolation");
   not in any changed-file path this session; no batch-2 fix touches `rng_mm`.
3. The xdist `sessionfinish` teardown flake persists (environmental, harmless).

## Outstanding — verified latent edges filed for a future pass

- **WEAR-016** — `wear_obj` WIELD dispatched by `item_type == WEAPON`, not the
  `ITEM_WIELD` wear flag (act_obj.c:1616). Unconfirmed-reachable (stock weapons
  carry both); riskier fix. See summary.
- **WEAR-017** — STR wield-weight check reads `obj.prototype.weight`, not ROM's
  `get_obj_weight(obj)` (act_obj.c:1624). Not a real divergence in Python's
  prototype-weight model today; flagged for completeness.

## Next Intended Task

1. **Review + push** the v2.14.279→288 commits (all local on `master`).
2. **Keep mining unswept surfaces** — candidates: door commands
   (`do_open`/`do_close`/`do_lock`/`do_unlock`) message strings, spell messages,
   and `fight.c` `dam_message` damage-verb thresholds (a LOOK-015-class boundary vein).
3. Evaluate **WEAR-016/017** reachability against real area data; fix if reachable.
4. Land the known **xdist worker-crash fix** so the parallel full suite is reliable.
