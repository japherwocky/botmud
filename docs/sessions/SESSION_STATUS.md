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
  - **`HANDLER-008`** (🔄 IN PROGRESS, 2.14.232–235) — the unified `get_skill` port:
    core landed at `mud/skills/skill_lookup.py:get_skill` (self-contained,
    `tests/test_get_skill.py` × 16); **3 of 5 sites migrated** (do_kick, backstab,
    disarm hand-to-hand — partial mirrors retired, daze/drunk now apply); the
    disarm-skill gate + do_rescue roll deferred (class-gate migration follow-up).
- **Pointer to latest summary**:
  [SESSION_SUMMARY_2026-07-03_FIGHT_COLD_PATH_TAIL_GETSKILL.md](SESSION_SUMMARY_2026-07-03_FIGHT_COLD_PATH_TAIL_GETSKILL.md)

## Project Status (snapshot)

| Metric | Value |
|--------|-------|
| Version | 2.14.235 |
| Tests | 6079 passed, 4 skipped, 0 failed (+40 pre-existing aiohttp env collection errors) |
| Cross-file invariants | INV-054 latest (unchanged) |
| Cold-path queue | FIGHT-085/086/087/088/089/091 closed; HANDLER-008 core + 3/5 sites done; FIGHT-090 + MAGIC-046 + HANDLER-008 tail OPEN |
| Active focus | HANDLER-008 get_skill consolidation (3/5 sites migrated); class-gate migration follow-up next |

## Next Intended Task

**Finish HANDLER-008 — the class-gate migration follow-up.** The unified
`get_skill` core is landed and 3 of 5 sites migrated. The remaining two
(`disarm`-skill gate, `do_rescue` roll) both read the skills dict; migrating them
onto `get_skill` enforces ROM's PC class-level gate — correct, but it makes the
~10 `TestDisarmRomParity` PC tests (and any rescue PC tests) fail because they
create a char named "warrior" but leave `ch_class=0` (mage), below the
`disarm.levels=(53,53,12,11)` / `rescue.levels=(53,53,53,1)` mage requirement.
The follow-up: set a real warrior `ch_class` on those ROM-parity test chars (a
faithful correction — they assert non-ROM ungated behavior), then migrate both
lookups and retire the last dict reads. After that, migrate the remaining ad-hoc
`_lookup_skill_percent`/`_character_skill_percent` sites opportunistically to
close HANDLER-008. Then **MAGIC-046** (ROM-ordered `carrying` accessor for
`heat_metal`) and **FIGHT-090** (unify the two `do_trip` impls), then resume
cold-path / cross-INV divergence hunting.

**Tooling note:** the GitNexus MCP server is disconnected; the on-disk index was
reindexed twice this session (fresh as of the FIGHT-091 commit). Restart the MCP
server before relying on `gitnexus_impact` / `gitnexus_detect_changes`; grep
fallback was used throughout (AGENTS.md-sanctioned).
