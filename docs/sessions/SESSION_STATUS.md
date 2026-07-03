# Session Status — 2026-07-03 — FIGHT/MAGIC HIGH+MEDIUM closure (081/082/045/083/084)

## Current State

- **Active focus**: Cross-file invariants / divergence-class roster; cold-path
  divergence hunting (per-file audit tracker exhausted). Closing the cold-path
  finding queue filed in the prior batch.
- **Last completed** (five gap-closer units, all re-verified against ROM C first):
  - **`FIGHT-081`** (HIGH, v2.14.221) — melee AC modifiers now apply on the /10
    scale in ROM order (`_compute_victim_ac`, `src/fight.c:480-503`); `-4` gated on
    `can_see_character` not the INVISIBLE affect.
  - **`FIGHT-082`** (HIGH, v2.14.222) — `do_trip` damage bound / speed modifier /
    raw-beats WAIT + victim DAZE (`src/fight.c:2711-2753`). Filed FIGHT-088.
  - **`MAGIC-045`** (HIGH, v2.14.223) — `heat_metal` cursed-item (NODROP) branches
    restored (`src/magic.c:3123-3277`). Filed MAGIC-046 (iteration order).
  - **`FIGHT-083`** (MEDIUM, v2.14.224) — `dirt_kicking` false-zero hack +
    `chance == 0` terrain gate (`src/fight.c:2566-2608`).
  - **`FIGHT-084`** (MEDIUM, v2.14.225) — `check_parry` visibility direction +
    functional (`src/fight.c:1311`). Filed FIGHT-089 (check_dodge twin).
  - Filed OPEN (out-of-scope, surfaced while reading ROM): `FIGHT-088` (MEDIUM),
    `FIGHT-089` (LOW), `MAGIC-046` (MEDIUM).
- **Pointer to latest summary**:
  [SESSION_SUMMARY_2026-07-03_FIGHT_MAGIC_HIGH_MEDIUM_CLOSURE.md](SESSION_SUMMARY_2026-07-03_FIGHT_MAGIC_HIGH_MEDIUM_CLOSURE.md)

## Project Status (snapshot)

| Metric | Value |
|--------|-------|
| Version | 2.14.225 |
| Tests | 6049 passed, 4 skipped, 0 failed (+40 pre-existing aiohttp env collection errors) |
| Cross-file invariants | INV-054 latest (unchanged) |
| Cold-path queue | FIGHT-081/082/083/084 + MAGIC-045 closed; FIGHT-085/086/087/088/089 + MAGIC-046 OPEN |
| Active focus | Cold-path divergence hunt — all HIGHs closed; MEDIUM/LOW tail remains |

## Next Intended Task

**Continue the FIGHT cold-path tail (all MEDIUM/LOW).** Highest value:
`FIGHT-085` (skill wait-states haste/slow-adjusted; ROM `WAIT_STATE` uses raw
beats — `mud/skills/registry.py:_compute_skill_lag`, affects
do_bash/do_kick/do_backstab/do_rescue; FIGHT-082's raw-beats read is the pattern),
then `FIGHT-086` (backstab THAC0 bonus in `compute_thac0`, `src/fight.c:474-475`),
`FIGHT-088` (do_trip act()-render + failure `damage(0)`), `FIGHT-089` (one-line
check_dodge visibility fix), `FIGHT-087` (disarm hth floor). `MAGIC-046`
(heat_metal iteration order) is cross-cutting — needs a unified ROM-ordered
`carrying` accessor on `Character`, so scope it separately.

**Tooling note:** the GitNexus MCP server disconnected mid-session; the index is
stale (last indexed `241c454`). Run `npx gitnexus analyze --skip-agents-md` and
restart the MCP server before relying on `gitnexus_impact` / `gitnexus_detect_changes`.
