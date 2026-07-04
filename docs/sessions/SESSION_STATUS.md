# Session Status — 2026-07-03 — HANDLER-008 fully complete (get_skill port done)

## Current State

- **Active focus**: Cross-file invariants / cold-path divergence hunting (per-file
  audit tracker exhausted). **HANDLER-008 — the unified `get_skill` port — is now
  fully complete.** The defensive-check trio and the do_trip NPC trip-chance
  follow-up are both migrated; no dict-sourced NPC skill lookups remain.
- **Last completed**:
  - **`HANDLER-008` do_trip NPC trip-chance** (`a74371ea`, ✅ FIXED, 2.14.242) —
    do_trip's NPC branch now uses `get_skill(char, "trip")` (`10+3*level`) instead of
    a hardcoded `skill_level = 100`; a low-level OFF_TRIP mob no longer trips far too
    often. Test: `test_fight_026...::test_npc_trip_chance_uses_get_skill_not_hardcoded_100`
    (+ over-correction guard). Closes the last dict-sourced NPC skill lookup.
- **Prior** (`8ff6e290`, 2.14.241, re-verified against ROM C + empirical
  `get_skill` output first):
  - **`HANDLER-008`** (✅ FIXED) — `check_shield_block`/`check_parry`/`check_dodge`
    now source their skill from unified `get_skill(victim, …)` instead of the
    dict-reading `_get_skill_percent`. **NPC mobs can now dodge/parry/shield-block**
    (ROM `level*2` / `10+2*level`, `src/handler.c:373-432`); before, the empty mob
    dict returned 0 so they never defended. PCs are class-gated. Retires the last
    dict-sourced defensive site.
  - 13 pre-existing tests triaged (PC → class that learns the skill early preserving
    the level-diff; the one NPC-defender test had its expected chance **recomputed**
    from the ROM formula — the old dict value is inert for NPCs; defense-ordering NPC
    tests switched to `off_flags` with equalized levels).
  - **`test_fight035` disarm caster** (✅ FIXED, same commit) — a level-30 mage that
    only passed because the file never calls `initialize_world` (empty registry →
    disarm gate skipped); flaked once a sibling xdist test populated the registry.
    Fixed with `ch_class=3` (warrior). The full-suite spillover the handoff predicted.
- **Pointer to latest summary**:
  [SESSION_SUMMARY_2026-07-03_HANDLER008_DEFENSIVE_COMPLETE.md](SESSION_SUMMARY_2026-07-03_HANDLER008_DEFENSIVE_COMPLETE.md)

## Project Status (snapshot)

| Metric | Value |
|--------|-------|
| Version | 2.14.242 |
| Tests | Full suite green (6078 baseline; parallel runs 0 failures modulo an intermittent pre-existing xdist teardown hang + 4 pre-existing aiohttp/starlette collection-error files) |
| Cross-file invariants | INV-054 latest (unchanged) |
| get_skill port | ✅ **fully complete** — all sites migrated (5 offensive + 3 defensive + do_trip NPC); no dict-sourced NPC skill lookups remain |
| Active focus | Cross-file invariants / cold-path divergence hunting |

## Next Intended Task

**HANDLER-008 is fully complete** — the do_trip NPC trip-chance follow-up closed
this session (2.14.242), so every dict-sourced NPC skill lookup now routes through
`get_skill`. Resume cross-file invariants / cold-path divergence hunting (the
per-file audit tracker has no ⚠️ Partial / ❌ Not Audited rows, so cross-INV is the
active pass). Candidate INV areas per AGENTS.md: affect ticks, position transitions,
mob script triggers, group/follower chain — run the probe-then-scope method (read
ROM C contract → read Python equivalent → one failing test), then close as a gap or
file the next free INV-NNN.

One opportunistic (non-urgent) item remains: the **PC** side of `do_trip` still uses
`_character_skill_percent` instead of `get_skill` (no class-gate / daze / drunk) —
migrate when the surface is next touched; not the documented HANDLER-008 gap.

**Tooling note:** the GitNexus MCP server is disconnected; the on-disk index was
reindexed in the background after the 2.14.241 commit. Restart the MCP server before
relying on `gitnexus_impact` / `gitnexus_detect_changes`; grep fallback was used this
session (AGENTS.md-sanctioned). An intermittent xdist teardown hang (master sleeps
after all workers exit) surfaced during full-suite runs — environmental, not a test
failure; worth a look if it recurs.
