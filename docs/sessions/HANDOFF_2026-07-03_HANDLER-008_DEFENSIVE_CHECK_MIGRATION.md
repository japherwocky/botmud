# Handoff — 2026-07-03 — HANDLER-008 defensive-check migration (the last piece)

## What this is

HANDLER-008 (the unified `get_skill` port, `mud/skills/skill_lookup.py`) is done
for all **offensive** skill sites (do_kick, backstab, disarm, do_rescue — see the
audit row). The **one remaining piece** is migrating the three defensive checks in
`mud/combat/engine.py` from the ad-hoc `_get_skill_percent(defender, …)` to the
unified `get_skill(defender, …)`:

- `check_shield_block` (`~:1578`) — `get_skill(victim, "shield block")`
- `check_parry` (`~:1611`) — `get_skill(victim, "parry")`
- `check_dodge` (`~:1657`) — `get_skill(victim, "dodge")`

This was **attempted and reverted this session** (commit `aa6cea3a` documents the
revert). The revert was correct: the code change is 3 lines but the test blast
radius is large and *semantically delicate* — rushing the test rewrites risks
shipping a green suite that asserts **non-ROM chances** (the exact anti-pattern the
project's "a test asserting non-ROM behavior is a test bug" rule guards against).
This handoff captures everything learned so the next session can do it cleanly.

## Why it matters (the parity bug)

`_get_skill_percent(defender, …)` reads the defender's skills dict, which is **empty
for mobs → 0**. So **NPC mobs currently never dodge, parry, or shield-block.** ROM
`get_skill` (`src/handler.c:373-432`) gives an NPC:
- `gsn_dodge` + `OFF_DODGE` → `level*2`; `gsn_parry` + `OFF_PARRY` → `level*2`
- `gsn_shield_block` → `10 + 2*level` (no flag gate)

ROM refs: `check_parry` = `get_skill(victim, gsn_parry)/2` (`src/fight.c`),
`check_dodge` = `get_skill(victim, gsn_dodge)/2`, `check_shield_block` =
`get_skill(victim, gsn_shield_block)/5 + 3`.

## The 3-line code change (trivial)

Replace each `shield_skill = _get_skill_percent(victim, "shield block", "shield_block_skill")`
/ `parry_skill = _get_skill_percent(victim, "parry", "parry_skill")` /
`dodge_skill = _get_skill_percent(victim, "dodge", "dodge_skill")` with
`get_skill(victim, "…")`. (`get_skill` is already imported in engine.py.) **Migrate
all three together — a partial (e.g. shield-only) leaves the trio inconsistent.**

## Why it's delicate — the five hazards (all confirmed this session)

1. **PC class-level gate.** `get_skill` returns 0 for a PC below the skill's class
   level. `parry.levels = (22,20,13,1)`, `dodge.levels = (20,22,1,13)`,
   `shield block.levels = (1,1,1,1)` (order: mage, cleric, thief, warrior). Test
   defenders default to `ch_class=0` (mage) — below parry(22)/dodge(20) at typical
   test levels → gated to 0 → the check never fires.

2. **Level-diff-preserving class fixes.** The `check_*` formula tests assert
   `chance = skill/K + (victim.level - attacker.level)`. You **cannot** just raise
   the defender's level to clear the gate — that shifts the level-diff modifier and
   breaks the assertion. Fix by setting a **class** that learns the skill early
   (warrior for parry, thief for dodge) at the *existing* level, OR raise **both**
   attacker and victim levels equally. Caveat: the latter shifts THAC0/damage in
   full-combat `deliver_kill` tests — so per-test judgment, not a blanket sweep.

3. **NPC formula expected-value rewrites (the silently-wrong trap).** NPC defense
   tests set `victim.skills["parry"] = 60` and assert 60-based chances. ROM
   `get_skill` **ignores the dict for NPCs** and uses the `level*2` formula, so the
   expected chance changes (e.g. `60/2` → `(level*2)/2`). These tests assert non-ROM
   numbers and need their **expected values recomputed** — verify each against
   `get_skill`'s actual output; do not guess. Known NPC-defender test:
   `test_combat_rom_parity.py::test_npc_unarmed_parry_half_chance`.

4. **`fallback_attr` pattern.** `_get_skill_percent(victim, "parry", "parry_skill")`
   reads a `victim.parry_skill` attribute fallback; `get_skill` does **not**. Three
   test files set the fallback attrs directly:
   `tests/integration/test_fight_031_combat_act_capitalization.py`,
   `tests/integration/test_fight_032_defense_pers.py` (`defender.parry_skill = 100`
   etc.). Switch these to `defender.skills["parry"] = …` (PC, with proper class/level)
   or NPC `off_flags` (OFF_PARRY/OFF_DODGE).

5. **Combined parry+dodge is structurally gated.** No single class learns both parry
   (warrior=1, mage=22) and dodge (thief=1, warrior=13) below level 13. A test that
   sets a defender's parry AND dodge at a low level is **incompatible with ROM's
   class-gate** — such a defender can't exist. Give it `level ≥ 13` (bump both
   attacker+victim to hold the level-diff) or split the test.

## Method (do it this way)

1. Migrate all three lookups.
2. Run the **full** suite (`pytest`) — the per-area runs *lie*: the defensive
   checks run on **every combat hit**, so spillover appears in non-defense-named
   combat tests. (This session's disarm/rescue migration hit exactly this — per-area
   green, full-suite red with cross-file failures.)
3. Triage each failure by category above. For a PC test → class/level fix
   (level-diff-preserving). For an NPC test → recompute the expected chance from the
   formula and verify against `get_skill`. For a fallback-attr test → switch to the
   dict/off_flags. For a combined test → level ≥ 13 or split.
4. **Stop-and-stage signal:** if a failure needs behavioral judgment you can't verify
   mechanically against `get_skill`'s known output, that's the same signal that
   triggered this revert — don't force it.

## Affected tests (the ~13 confirmed when the migration was live)

- `tests/test_critical_function_parity.py::TestDefenseChecks::{test_check_parry_formula, test_check_dodge_formula}`
- `tests/test_combat_defenses_prob.py::{test_parry_triggers_before_dodge_and_shield_block, test_parry_triggers_when_no_shield, test_dodge_triggers_when_no_shield_or_parry}`
- `tests/test_combat_rom_parity.py::{test_parry_skill_calculation, test_dodge_skill_calculation, test_npc_unarmed_parry_half_chance}`
- `tests/test_combat.py::test_parry_blocks_when_skill_learned` (PC defender; the *attacker* is the NPC)
- `tests/integration/test_fight084_parry_visibility_direction.py` (2 — PC defender, class/level fix)
- `tests/integration/test_fight089_dodge_visibility_direction.py` (2 — PC defender, class/level fix)
- `tests/integration/test_fight_031_*` + `test_fight_032_*` (fallback-attr → dict/off_flags)

Expect a few more from full-suite combat spillover; run the full suite to enumerate.

## After it lands

Flip the HANDLER-008 audit row (`docs/parity/HANDLER_C_AUDIT.md`) to ✅ — the
defensive trio is the last dict-sourced site; with it migrated, the unified
`get_skill` port is complete (modulo the small `do_trip` NPC trip-chance follow-up
already noted in that row).
