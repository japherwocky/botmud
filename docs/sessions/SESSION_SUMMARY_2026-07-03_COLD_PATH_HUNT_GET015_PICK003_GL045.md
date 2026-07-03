# Session Summary — 2026-07-03 — Cold-path divergence hunt (GET-015, PICK-003, GL-045) + coverage locks

## Scope

Autonomous five-unit batch continuing the cross-file-invariant / divergence-class
pass. The session picked up from the 2026-06-23 death auto-action differential
work (v2.14.215; `KNOWN_DIVERGENCES` empty, per-file audit tracker exhausted).
Method: probe structurally-risky surfaces by hand, and — because the hot paths
proved exceptionally faithful — parallelize the search with three cold-path
divergence-hunter agents (spells/`magic.c`, combat+update/`fight.c`+`update.c`,
objects+movement/`act_obj.c`+`act_move.c`). Every finding was re-verified against
ROM C source before acting (per AGENTS.md). Result: 2 committed coverage locks,
3 committed parity fixes, and 8 out-of-scope divergences filed durably (1
verified, 7 hunter-reported).

## Outcomes

### Unit 1 — non-death `get all corpse` autosplit differential — ✅ COVERAGE LOCK (v2.14.216)

- **Scenario**: `tools/diff_harness/scenarios/get_corpse_money_autosplit.json` + C golden
- **ROM C**: `src/act_obj.c:162-184` (`get_obj` autosplit)
- **What**: exercises the shared `do_get` → `_get_obj` autosplit path via a
  **manual** `get all corpse` (autoloot/autogold OFF) rather than the death
  auto-branch — a distinct entry into the FIGHT-080 surface. A grouped level-5 PC
  with `PLR_AUTOSPLIT` picks up 17 silver / 2 gold from a slain janitor corpse;
  ROM emits "You get ..." plus both `do_split` share lines (9 silver / 1 gold).
  Python converges on the first pass. Confirmed the golden genuinely exercises the
  split path (not a silent both-empty false-green).

### Unit 2 — `weather_tick` MM draw-order regression — ✅ RNG LOCK (v2.14.217)

- **Python**: `mud/game_loop.py:weather_tick`; test `tests/test_weather_tick_draw_order.py`
- **ROM C**: `src/update.c:578`
- **What**: ROM's pressure line `change += diff*dice(1,4) + dice(2,6) - dice(2,6)`
  is a single C expression whose three `dice()` calls have *unspecified*
  evaluation order. Verified empirically (a `cc` probe at `-O0` and `-O2`) that
  the diff-harness build platform evaluates it strictly left-to-right — the order
  the Python port draws in. The test pins the draw count, order, operand sizes,
  and the +/− assignment (so a refactor can't silently swap the two `dice(2,6)`
  draws and desync the shared MM stream), plus the per-sky-state `number_bits(2)`
  draw count. No behavior change — path was previously unguarded.

### `GET-015` — pit greed gate uses `LEVEL_IMMORTAL` not 51 — ✅ FIXED (v2.14.218)

- **Python**: `mud/commands/inventory.py:600` (`do_get` pit branch)
- **ROM C**: `src/act_obj.c:320-321` (`!IS_IMMORTAL(ch)`), `src/merc.h:149,2091`
- **Gap**: `GET-015` — `get all <pit>` hardcoded `char_trust >= 51`, so a
  level/trust-51 **mortal hero** was treated as immortal and could empty a
  donation pit in one command. `LEVEL_IMMORTAL = MAX_LEVEL-8 = 52`; 51 is
  `LEVEL_HERO`. Reachable in normal play (the `trust or level` fallback puts a
  level-51 mortal at 51).
- **Fix**: compare `>= LEVEL_IMMORTAL`. The prior `test_immortal_can_get_all_from_pit`
  encoded the misread (`trust = 51 # ROM: god = 51`, citing fabricated C
  `get_trust(ch) < god`) and was corrected to trust 52 with the real
  `!IS_IMMORTAL` citation.
- **Tests**: `tests/integration/test_container_retrieval.py` — added
  `test_hero_trust_51_mortal_cannot_get_all_from_pit` (RED→GREEN); corrected the
  false immortal test. 3/3 pit tests green.

### `PICK-003` — `do_pick` door immortal check via `is_immortal()` — ✅ FIXED (v2.14.219)

- **Python**: `mud/commands/doors.py:660` (`do_pick` door branch)
- **ROM C**: `src/act_move.c:958,963,973` (`!IS_IMMORTAL(ch)`), `src/merc.h:149,2091`
- **Gap**: `PICK-003` — two bugs on one line (`is_immortal = trust >= 51` reading
  raw `char.trust`): (a) wrong threshold (51 = LEVEL_HERO mortal), so a trust-51
  hero wrongly bypassed pickproof/open-door gates; (b) missing `get_trust` level
  fallback, so a level-52 immortal with trust 0 was wrongly refused ("You failed.")
  on a pickproof door. **Contradicts a stale "immortal bypass FIXED" audit claim.**
- **Fix**: `is_immortal = char.is_immortal()` (canonical helper: trust-or-level
  fallback, `>= LEVEL_IMMORTAL`).
- **Tests**: `tests/integration/test_pick003_immortal_threshold.py` (2, RED→GREEN):
  trust-51 hero refused on pickproof; level-52/trust-0 immortal bypasses via the
  level fallback. 15/15 pick+door tests green.

### `GL-045` — `obj_update` affect-fade RNG draw is unconditional — ✅ FIXED (v2.14.220)

- **Python**: `mud/game_loop.py:_tick_object_affects`
- **ROM C**: `src/update.c:933`
- **Gap**: `GL-045` — object-side twin of GL-026. The fade roll had swapped
  operands (`level > 0 and number_range(0,4) == 0`), so a level-0 object affect
  (duration>0) short-circuited past the draw. ROM `if (number_range(0,4) == 0 &&
  paf->level > 0)` consumes the roll unconditionally; `level>0` only gates the
  decrement. Each skipped draw desynced the shared MM stream — the exact hazard
  GL-026 fixed on the character path (`mud/affects/engine.py:65`), left un-fixed
  on the object path.
- **Fix**: roll first (`fades = number_range(0,4) == 0; … if fades and level > 0:`).
- **Tests**: `tests/test_obj_update_affect_fade_rng.py` (2, RED→GREEN): level-0
  duration>0 affect draws exactly one `number_range(0,4)`; level>0 unchanged.

## Out-of-scope divergences filed durably (OPEN)

From the cold-path hunt — see `docs/parity/FIGHT_C_AUDIT.md` and `MAGIC_C_AUDIT.md`:

- **`FIGHT-081` (HIGH, VERIFIED)** — `attack_round` applies the AC `<-15` clamp
  and −4/+4/+6 modifiers on **raw** AC then `/10` last; ROM `one_hit`
  (`src/fight.c:483-503`) divides by 10 **first**, then clamps/modifies on that
  scale. Modifiers ~10× too weak, clamp over-fires for any armored character;
  worked example raw AC −100 → ROM effective −10 vs Python −3 (~7 AC easier to
  hit). **This is the top-priority next-session item.** Also a sub-divergence:
  the −4 gates on `AffectFlag.INVISIBLE` vs ROM `!can_see(ch, victim)`.
- **`FIGHT-082..087` (hunter-reported, verify first)** — do_trip cluster (dmg
  term, missing haste gate, wait/daze); dirt_kicking `%5` hack + zero test;
  check_parry visibility inversion; skill wait-state haste/slow adjustment;
  backstab THAC0 term; disarm hth floor.
- **`MAGIC-045` (HIGH, hunter-reported)** — `heat_metal` hardcodes
  `can_drop_obj = True`, collapsing ROM cursed-item branches (message, damage,
  item state, RNG); + `victim->carrying`-order and `get_curr_stat(DEX)` sub-findings.

## Files Modified

- `tools/diff_harness/scenarios/get_corpse_money_autosplit.json` + golden — new differential scenario (Unit 1).
- `tests/test_weather_tick_draw_order.py` — new RNG-order lock (Unit 2).
- `mud/commands/inventory.py` — GET-015 `LEVEL_IMMORTAL`.
- `mud/commands/doors.py` — PICK-003 `is_immortal()`.
- `mud/game_loop.py` — GL-045 unconditional fade roll.
- `tests/integration/test_container_retrieval.py` — GET-015 tests (+ false-test correction).
- `tests/integration/test_pick003_immortal_threshold.py` — new (PICK-003).
- `tests/test_obj_update_affect_fade_rng.py` — new (GL-045).
- `docs/parity/ACT_OBJ_C_AUDIT.md` — GET-015 ✅ FIXED.
- `docs/parity/ACT_MOVE_C_AUDIT.md` — PICK-003 ✅ FIXED.
- `docs/parity/UPDATE_C_AUDIT.md` — GL-045 ✅ FIXED.
- `docs/parity/FIGHT_C_AUDIT.md` — FIGHT-081..087 OPEN.
- `docs/parity/MAGIC_C_AUDIT.md` — MAGIC-045 OPEN.
- `CHANGELOG.md`, `pyproject.toml` — entries + 2.14.215 → 2.14.220.

## Test Status

- Targeted areas (game_loop, differential, obj_update, pit, pick/door): green.
- Full suite: **6032 passed, 4 skipped**. The 40 collection errors in
  `test_websocket_server.py` / `test_prompt_cmd_parity.py` are a **pre-existing
  environmental** issue (`TypeError: Router.__init__() got an unexpected keyword
  argument` — aiohttp version mismatch), confirmed present with this session's
  changes stashed. Not a regression from this work; flagged for env attention.

## Next Steps

1. **`FIGHT-081` (HIGH, verified)** — fix the AC scale/order in `attack_round`
   (`/10` first, clamp, then modifiers; drop trailing `c_div(victim_ac,10)`;
   consider `!attacker.can_see(victim)` for the −4). HIGH blast radius — scope
   with a differential combat scenario whose victim AC is in the divergent range;
   expect combat-test re-baselining.
2. Re-verify and close `FIGHT-082..087` and `MAGIC-045` against ROM C (each has
   exact cites in the audit docs).
3. Environmental: the `Router.__init__()` aiohttp collection errors dropped the
   suite from 6042→6032 passing; investigate the aiohttp pin (not a parity bug).
