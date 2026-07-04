# Session Status — 2026-07-03 — FIGHT cold-path tail (085–089, 091) + get_skill class

## Current State

- **Active focus**: Cross-file invariants / cold-path divergence hunting (per-file
  audit tracker exhausted). The FIGHT cold-path MEDIUM/LOW tail queued by the prior
  session is now **fully closed**; the session surfaced the systemic `get_skill`
  NPC-formula root cause (**HANDLER-008**) behind several of these fixes.
- **Last completed** (six gap-closer units, all re-verified against ROM C first):
  - **`FIGHT-085`** (2.14.226) — skill wait-states use raw `beats`; removed the
    non-ROM haste/slow lag scaling (`src/merc.h:2116` `WAIT_STATE`).
  - **`FIGHT-086`** (2.14.227) — backstab THAC0 bonus restored in `attack_round`
    (`src/fight.c:474-475`); added `_backstab_skill`.
  - **`FIGHT-089`** (2.14.228) — `check_dodge` visibility halving made functional
    (`src/fight.c:1363`); twin of FIGHT-084.
  - **`FIGHT-087`** (2.14.229) — unarmed `disarm` uses raw hand-to-hand skill +
    ROM gate (`src/fight.c:3160-3189`); added `_hand_to_hand_skill`.
  - **`FIGHT-088`** (2.14.230) — `do_trip` three act() lines + failure `damage(0)`
    (`src/fight.c:2735-2751`).
  - **`FIGHT-091`** (2.14.231) — NPC kick chance uses ROM `get_skill` `10+3*level`
    (`src/fight.c:3125`); NPC kicks could never land before.
  - Filed OPEN (out-of-scope, surfaced while reading ROM): **`FIGHT-090`** (MEDIUM —
    `do_trip`/`skill_handlers.trip` duplicate impls).
  - **`HANDLER-008`** (🔄 IN PROGRESS, 2.14.232–238) — unified `get_skill` port:
    core + **all 5 offensive-skill sites migrated** (do_kick, backstab, disarm×2,
    do_rescue). Remaining: the **defensive** `check_dodge`/`check_parry`/
    `check_shield_block` NPC lookups — attempted + reverted this session (blast
    radius); full handoff at
    [HANDOFF_2026-07-03_HANDLER-008_DEFENSIVE_CHECK_MIGRATION.md](HANDOFF_2026-07-03_HANDLER-008_DEFENSIVE_CHECK_MIGRATION.md).
  - **`MAGIC-046`** (✅ FIXED, 2.14.239) — `heat_metal` now walks ROM's single
    `victim->carrying` LIFO list via new `Character.iter_carrying()` (descending
    `_carry_seq`) + restored `remove_obj`'s stop-using act lines.
  - **`FIGHT-090`** (✅ FIXED, 2.14.240) — unified the two `do_trip` impls;
    `skill_handlers.trip` now delegates to the canonical `do_trip`, which absorbed
    three fixes that had landed only on the handler copy (self-trip broadcast, PERS
    gate messages, check_improve). Filed a do_trip NPC-trip-chance HANDLER-008 note.
- **Pointer to latest summary**:
  [SESSION_SUMMARY_2026-07-03_FIGHT_COLD_PATH_TAIL_GETSKILL.md](SESSION_SUMMARY_2026-07-03_FIGHT_COLD_PATH_TAIL_GETSKILL.md)

## Project Status (snapshot)

| Metric | Value |
|--------|-------|
| Version | 2.14.240 |
| Tests | 6076 passed, 4 skipped, 0 failed (+40 pre-existing aiohttp env collection errors) |
| Cross-file invariants | INV-054 latest (unchanged) |
| Cold-path queue | FIGHT-085/086/087/088/089/090/091 + MAGIC-046 closed; HANDLER-008 offensive done; HANDLER-008 defensive tail OPEN (handoff written) |
| Active focus | HANDLER-008 defensive-check migration (handoff ready) is the last get_skill piece |

## Next Intended Task

**Finish HANDLER-008 — migrate the defensive checks.** This is the last
`get_skill` piece. The 3-line code change is trivial but the test blast radius is
large and semantically delicate (PC class-gate, level-diff-preserving fixes, NPC
formula expected-value rewrites, the `fallback_attr` pattern, and a structural
parry+dodge class-gate constraint) — it was attempted and reverted this session
precisely to avoid rushing silently-wrong test rewrites. **The full method,
hazards, ROM refs, and the ~13 affected tests are documented in the dedicated
handoff:**
[HANDOFF_2026-07-03_HANDLER-008_DEFENSIVE_CHECK_MIGRATION.md](HANDOFF_2026-07-03_HANDLER-008_DEFENSIVE_CHECK_MIGRATION.md).
Follow it, run the FULL suite (per-area runs lie — the checks fire on every hit).
After that, HANDLER-008 is complete (modulo the small do_trip NPC trip-chance
follow-up in the audit row); then resume cold-path / cross-INV divergence hunting.

**Tooling note:** the GitNexus MCP server is disconnected; the on-disk index was
reindexed twice this session (fresh as of the FIGHT-091 commit). Restart the MCP
server before relying on `gitnexus_impact` / `gitnexus_detect_changes`; grep
fallback was used throughout (AGENTS.md-sanctioned).
