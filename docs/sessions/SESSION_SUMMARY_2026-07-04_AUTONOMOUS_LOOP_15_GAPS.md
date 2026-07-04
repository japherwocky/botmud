# Session Summary — 2026-07-04 — Autonomous /loop: 15 cold-path parity units

## Scope

A self-paced `/loop` session that ran **15 parity units** back-to-back, each a
probe-then-scope close following the standard TDD discipline (failing test first →
fix → audit row → CHANGELOG → version bump → one local commit). Method per unit:
dispatch one synchronous probe subagent on a fresh cold-path area, re-verify its
finding against ROM C by hand, then close. Result: **13 ROM-parity bug fixes + 2
coverage-locks** across eight subsystems (object/shop, combat, movement/doors,
buff/offensive/cleanse spells, act_info affects/look, advancement). Versions
2.14.249 → **2.14.264**. **All commits are LOCAL on `master` and UNPUSHED**,
awaiting the user's review.

The finder/container/shop area (act_obj) was exhausted first, then combat
`damage()`, movement/doors, the spell engine, and act_info display commands.

## Outcomes

### `EAT-008` — ✅ FIXED (2.14.250)
- **Python**: `mud/commands/consumption.py:do_eat`; **ROM C**: `src/act_obj.c:1296`
- `do_eat` used a substring-only finder instead of `get_obj_carry`, so `eat 2.mushroom` (the `N.name` count prefix) never resolved. Wired to `get_obj_carry`. Test: `test_consumables.py::test_eat_count_prefix_selects_nth_item`.

### `WEAR-010` — ✅ FIXED (2.14.251)
- **Python**: `mud/commands/equipment.py:do_wear`; **ROM C**: `src/act_obj.c:1726`
- Same weak-finder class as EAT-008; `wear/wield/hold 2.ring` never resolved (wield/hold delegate to do_wear). Test: `test_equipment_system.py::test_wear_count_prefix_selects_nth_item`.

### `PUT-004` — ✅ FIXED (2.14.252) — INV-011
- **Python**: `mud/commands/obj_manipulation.py:_obj_to_obj`; **ROM C**: `src/handler.c:1971-1984`
- Putting an item into a **carried** bag dropped `carry_weight`/`carry_number` (subtract with no re-add), letting a player slip under `can_carry_w`. Added ROM's carried-container re-add walk (`weight * WEIGHT_MULT/100`). Cross-ref INV-011. Test: `test_put_weight_mult.py::test_put_into_carried_bag_is_net_zero_on_carry_weight`.

### `GET-016` — ✅ FIXED (2.14.253)
- **Python**: `mud/commands/inventory.py` + `obj_manipulation.py` `_get_obj_weight`; **ROM C**: `src/handler.c get_obj_weight`
- The do_get/do_put carry-gate weight helpers summed container contents at full weight, ignoring `WEIGHT_MULT`, so a `get <magic-bag>` ROM allows was refused. Both helpers now apply the multiplier. Test: `test_get_weight_mult.py`.

### `BUY-011` — ✅ FIXED (2.14.254)
- **Python**: `mud/commands/shop.py:_collect_matching_stock`; **ROM C**: `src/act_obj.c:2667-2686`
- `do_buy`'s stock check counted non-adjacent duplicates; ROM counts only a **consecutive** run and breaks at the first mismatch. `buy 2*lantern` on `[lantern, dagger, lantern]` wrongly sold both. Added the ROM break. Test: `test_shops.py::test_buy_multi_stock_requires_consecutive_run`.

### `SELL-005` — ✅ FIXED (2.14.255)
- **Python**: `mud/commands/shop.py:_obj_to_keeper`; **ROM C**: `src/act_obj.c:2424`
- `obj_to_keeper` standardizes a sold item's cost to an existing same-proto duplicate **unconditionally**; the port skipped it when the duplicate's cost was 0. Removed the guard. Test: `test_shops.py::test_obj_to_keeper_standardizes_cost_even_when_existing_is_zero`.

### `FIGHT-092` — ✅ FIXED (2.14.256)
- **Python**: `mud/combat/engine.py:apply_damage`; **ROM C**: `src/fight.c:763-769`
- ROM `damage()` strips an invisible **attacker's** invis + broadcasts "$n fades into existence." on every connecting hit; the port did nothing, so an invisible caster/thief stayed hidden through a whole fight. Added the strip after the parry/dodge checks. Filed FIGHT-093 (1200 loophole cap + check_killer). Test: `test_invisibility_combat.py::test_invisible_attacker_revealed_on_connecting_hit`. (Also corrected 2 latent masking tests that predated this reveal.)

### `MOVE-008` — ✅ FIXED (2.14.257)
- **Python**: `mud/commands/doors.py:do_open`/`do_close`; **ROM C**: `src/act_move.c:266,272-ish`
- Container arms checked `CLOSEABLE` before `CLOSED`; ROM checks CLOSED first, so an already-open non-closeable container returned "You can't do that." instead of "It's already open." Reordered both arms. Filed MOVE-009 (do_flee inline movement). Test: `test_door_container_message_order.py`.

### `MAGIC-047` — ✅ FIXED (2.14.258)
- **Python**: `mud/skills/handlers.py:stone_skin`; **ROM C**: `src/magic.c:4447`
- ROM `spell_stone_skin` uniquely gates on `is_affected(CASTER)`, not the victim; the port checked the target. Replicated the ROM quirk (guard on caster, affect still on target). Corrected 4 tests that encoded the target-gating. Test: `test_skills_buffs.py::test_stone_skin_guard_checks_caster_not_victim`.

### `MAGIC-048` — ✅ FIXED (2.14.259)
- **Python**: `mud/skills/handlers.py:chain_lightning`; **ROM C**: `src/magic.c:1259-1278`
- The bounce loop had an extra `if level <= 0: break` ROM lacks; ROM arcs to every valid target in the pass (0 damage past level 0, but still draws saves + messages). Removed the break. Corrected `test_chain_lightning_arcs_room_targets` + 2 FIGHT-092 collateral tests. Test: `test_skills_damage.py::test_chain_lightning_arcs_to_every_target_in_the_pass`.

### `AFFECTS-001` — ✅ FIXED (2.14.260)
- **Python**: `mud/commands/affects.py:do_affects`; **ROM C**: `src/act_info.c:1726,1736`
- The level-20+ duplicate-affect continuation line rendered a double colon (`: :`). ROM emits 22 spaces then `": modifies…"`. Dropped the extra `": "`. Test: `test_do_affects.py::test_affects_level_20_plus_duplicate_continuation_single_colon`.

### `MAGIC-049` — ✅ FIXED (2.14.261)
- **Python**: `mud/skills/handlers.py:dispel_magic`; **ROM C**: `src/magic.c:2082-2088`
- `dispel_magic` was missing ROM's wholesale opening `saves_spell(level, victim, DAM_OTHER)` gate (a missing RNG draw + abort messages + early return). Added it. Corrected 4 "dispel proceeds" tests (bypass the new gate). Filed MAGIC-050 (effect-list order + per-effect messages). Test: `test_utility_spells_parity.py::test_dispel_magic_aborts_when_victim_saves`.

### `LOOK-010` — ✅ FIXED (2.14.262)
- **Python**: `mud/world/vision.py:describe_character` + `mud/world/look.py:_room_occupant_line`; **ROM C**: `src/act_info.c:266,272`
- Aura tags rendered reversed (`(White Aura)` before `(Pink Aura)`; ROM is Pink→White) **and** doubled in the room list (both sites prepended them). Fixed the order in both and removed the duplicate prepend. Filed the ~10 missing char tags as a backlog note. Test: `test_do_look_command.py::test_room_occupant_line_aura_order_pink_before_white`.

### xp_compute neutral-align `c_div` — ✅ COVERAGE-LOCK (2.14.263)
- **Python**: `mud/groups/xp.py:189`; **ROM C**: `src/fight.c:1908`
- A probe verified the XP/group award math is ROM-faithful; locked the one signed-math site test_fight055's ±500 branches didn't cover — the neutral-alignment change must truncate toward 0 (`c_div`) for a negative killer, not floor. Also filed **SPLIT-001** (an intentional non-ROM `do_split` `N gold`/`silver` keyword form) for maintainer review — NOT autonomously removed (documented+tested feature). Test: `test_fight055…::test_fight055_neutral_align_change_truncates_toward_zero`.

### `PRACTICE-002` — ✅ FIXED (2.14.264)
- **Python**: `mud/commands/advancement.py:do_practice`; **ROM C**: `src/act_info.c:2744-2757`
- The `level < skill_level[class]` gate was applied only to a 0%-known skill; ROM rejects it **unconditionally**, so a below-level char with a known-at-1% spell (the normal group-granted state) could practice it in the port. Dropped the `current <= 0 and` qualifier. Gave 2 existing tests `level=25`. Test: `test_do_practice_command.py::test_practice_below_class_level_known_skill_is_rejected`.

## Files Modified (production code)

- `mud/commands/consumption.py`, `mud/commands/equipment.py`, `mud/commands/obj_manipulation.py`, `mud/commands/inventory.py`, `mud/commands/shop.py`, `mud/commands/doors.py`, `mud/commands/affects.py`, `mud/commands/advancement.py`
- `mud/combat/engine.py`, `mud/skills/handlers.py`, `mud/world/look.py`, `mud/world/vision.py`
- Audit docs: `ACT_OBJ_C_AUDIT.md`, `ACT_MOVE_C_AUDIT.md`, `MAGIC_C_AUDIT.md`, `ACT_INFO_C_AUDIT.md`, `ACT_COMM_C_AUDIT.md`, `UPDATE_C_AUDIT.md`, `FIGHT_C_AUDIT.md`, `CROSS_FILE_INVARIANTS_TRACKER.md`
- `CHANGELOG.md`, `pyproject.toml` (2.14.249 → 2.14.264)

## Test Status

- Every unit: relevant slice green (red-before-fix verified), run via `.venv/bin/python -m pytest -n0`.
- **Full suite: 6127 passed, 4 skipped, 0 failed** (180s, via `.venv`).
- Known: `tests/integration/test_character_advancement.py` (a `spec_cast_mage` test that mocks `number_bits`→19) hangs when run **in isolation** (`-n0` single file) but passes in the full suite — a pre-existing RNG-leak isolation flake, confirmed present on HEAD without this session's changes; the `--timeout` addopts guard would surface it if it ever hung the full run.

## Open follow-ups filed this session (not yet closed)

- **FIGHT-093** — damage() 1200 loophole cap + check_killer absent from apply_damage (low pri).
- **MOVE-009** — do_flee re-implements movement inline, skipping `$n leaves`/arrival broadcasts + follower cascade.
- **MAGIC-046** — heat_metal MobInstance carry-order (no `_carry_seq`).
- **MAGIC-050** — dispel_magic iterates `spell_effects` dict vs ROM's fixed spell list + per-effect room messages.
- **SPLIT-001** — do_split accepts a non-ROM `N gold`/`silver` keyword form (intentional QuickMUD convenience; maintainer to decide whether to strip for strict parity).
- **LOOK missing tags** — Python renders only 2 of ROM's ~12 char tags (AFK/Invis/Wizi/Hide/Charmed/Translucent/Red-Aura/Golden-Aura/KILLER/THIEF).

## Next Steps

1. **Review + push.** All 15 commits (`bfe11040` → `86179e98`) are local on `master`, unpushed. Review, then `git push origin master`; optionally release 2.14.264 to PyPI.
2. **Reindex GitNexus** at session start (`npx gitnexus analyze --skip-agents-md`) — the on-disk index is stale (last `bfe1104`); the background reindex was failing with exit 144 this session (grep fallback used, AGENTS.md-sanctioned).
3. **Run tests from `.venv`** (`.venv/bin/python -m pytest`) — the system framework Python is over-constrained (see AGENTS.md "Environment").
4. Continue cold-path / cross-INV divergence hunting, or burn down the six OPEN follow-ups above (FIGHT-093, MOVE-009, MAGIC-046, MAGIC-050, SPLIT-001, LOOK tags).
