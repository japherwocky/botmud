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
    `do_trip`/`skill_handlers.trip` duplicate impls), **`HANDLER-008`** (MODERATE —
    unified `get_skill` port; the NPC-formula workaround now spans **5 sites**).
- **Pointer to latest summary**:
  [SESSION_SUMMARY_2026-07-03_FIGHT_COLD_PATH_TAIL_GETSKILL.md](SESSION_SUMMARY_2026-07-03_FIGHT_COLD_PATH_TAIL_GETSKILL.md)

## Project Status (snapshot)

| Metric | Value |
|--------|-------|
| Version | 2.14.231 |
| Tests | 6061 passed, 4 skipped, 0 failed (+40 pre-existing aiohttp env collection errors) |
| Cross-file invariants | INV-054 latest (unchanged) |
| Cold-path queue | FIGHT-085/086/087/088/089/091 closed; FIGHT-090 + HANDLER-008 + MAGIC-046 OPEN |
| Active focus | Cold-path divergence hunt — FIGHT tail closed; get_skill consolidation queued |

## Next Intended Task

**Port ROM `get_skill` (HANDLER-008) — the #1 priority.** The get_skill
NPC-formula workaround now appears at five combat sites (`_backstab_skill`,
`_hand_to_hand_skill`, `do_kick` inline, the `disarm`-skill lookup, and
`do_rescue`'s roll), and the daze/drunk skill modifiers are unported everywhere.
Build a faithful unified `get_skill(ch, sn)` mirroring `src/handler.c:346-448`
(PC learned + class-level gate; NPC formula dispatch; daze `skill/2`/`2*skill/3`;
drunk `9*skill/10`; `URANGE(0,skill,100)`) — add it self-contained + unit-tested
first (zero call-site changes), then migrate the five sites and retire the
partial mirrors. `Skill` exposes `type`/`levels`; `Character` exposes
`daze`/`condition[COND_DRUNK]`. Then **MAGIC-046** (ROM-ordered `carrying`
accessor for `heat_metal`) and **FIGHT-090** (unify the two `do_trip` impls),
then resume cold-path / cross-INV divergence hunting.

**Tooling note:** the GitNexus MCP server is disconnected; the on-disk index was
reindexed twice this session (fresh as of the FIGHT-091 commit). Restart the MCP
server before relying on `gitnexus_impact` / `gitnexus_detect_changes`; grep
fallback was used throughout (AGENTS.md-sanctioned).
