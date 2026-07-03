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
  - **`HANDLER-008`** (🔄 IN PROGRESS, 2.14.232–238) — the unified `get_skill` port:
    core at `mud/skills/skill_lookup.py:get_skill` (self-contained,
    `tests/test_get_skill.py` × 16); **all 5 offensive-skill sites migrated**
    (do_kick, backstab, disarm hand-to-hand, disarm-skill gate, do_rescue — every
    partial mirror retired, NPC formulas + daze/drunk + PC class-gate now apply);
    8 cross-file disarm/rescue tests fixed to set warrior `ch_class`. Remaining:
    the defensive `check_dodge`/`check_parry`/`check_shield_block` NPC lookups.
- **Pointer to latest summary**:
  [SESSION_SUMMARY_2026-07-03_FIGHT_COLD_PATH_TAIL_GETSKILL.md](SESSION_SUMMARY_2026-07-03_FIGHT_COLD_PATH_TAIL_GETSKILL.md)

## Project Status (snapshot)

| Metric | Value |
|--------|-------|
| Version | 2.14.238 |
| Tests | 6079 passed, 4 skipped, 0 failed (+40 pre-existing aiohttp env collection errors) |
| Cross-file invariants | INV-054 latest (unchanged) |
| Cold-path queue | FIGHT-085/086/087/088/089/091 closed; HANDLER-008 core + all 5 offensive sites done; FIGHT-090 + MAGIC-046 + HANDLER-008 defensive tail OPEN |
| Active focus | HANDLER-008 get_skill consolidation (5/5 offensive sites); defensive check migration is the last piece |

## Next Intended Task

**Finish HANDLER-008 — migrate the defensive checks.** The unified `get_skill`
core is landed and all 5 offensive-skill sites are migrated. The last piece is the
defensive trio in `mud/combat/engine.py`: `check_dodge`/`check_parry`/
`check_shield_block` still read `_get_skill_percent(defender, …)` (0 for NPC
defenders), so NPC mobs never dodge/parry/shield-block — ROM `get_skill` gives an
OFF_DODGE dodger `level*2`, OFF_PARRY parry `level*2`, shield_block `10+2*level`.
Migrate each to `get_skill(victim, …)`. **Watch the same class-gate blast radius**:
per the session just closed, the per-area runs will pass but the full suite will
catch PC-defender tests that create default mage-class chars — run the FULL suite
and expect to set a real `ch_class` on the affected defense tests (and mind the
`_get_skill_percent` `fallback_attr` pattern, e.g. `parry_skill`, which get_skill
does not read). Then **MAGIC-046** (ROM-ordered `carrying` accessor for
`heat_metal`) and **FIGHT-090** (unify the two `do_trip` impls), then resume
cold-path / cross-INV divergence hunting.

**Tooling note:** the GitNexus MCP server is disconnected; the on-disk index was
reindexed twice this session (fresh as of the FIGHT-091 commit). Restart the MCP
server before relying on `gitnexus_impact` / `gitnexus_detect_changes`; grep
fallback was used throughout (AGENTS.md-sanctioned).
