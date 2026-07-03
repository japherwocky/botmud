# Session Summary — 2026-07-03 — FIGHT/MAGIC cold-path gap closure (081/082/045/083/084)

## Scope

Continued the cold-path divergence work from the prior batch (GET-015, PICK-003,
GL-045). Picked up from `SESSION_STATUS.md`'s queue of 8 open findings
(FIGHT-081..087 + MAGIC-045) and closed the top five **by severity**: all three
HIGHs (FIGHT-081, FIGHT-082, MAGIC-045) and two MEDIUMs (FIGHT-083, FIGHT-084).
Per the AGENTS.md "re-verify any status claim against ROM C" rule, every
hunter-reported sub-claim was line-verified against `src/fight.c` / `src/magic.c`
before writing the fix (failing-test-first each time). Reading the source also
surfaced three *additional* divergences the hunters missed — filed durably as
FIGHT-088, FIGHT-089, MAGIC-046 rather than silently fixed or dropped.

Interpretation note: "five sessions" was read as five gap-closer units (one
gap = one failing-test-first commit), matching the prior batch's granularity.
All HIGH-severity findings are now closed; the remaining queue is MEDIUM/LOW.

## Outcomes

### `FIGHT-081` — ✅ FIXED (2.14.221) — HIGH

- **Python**: `mud/combat/engine.py:_compute_victim_ac` / `attack_round`
- **ROM C**: `src/fight.c:480-503` (`one_hit`)
- **Fix**: ROM divides `GET_AC` by 10 **first**, then applies the `<-15` rescale
  and the `-4/+4/+6` visibility/position modifiers on the /10 scale. The port
  applied them to the raw (×10) AC and divided by 10 last, making the modifiers
  ~10× too weak and mis-firing the rescale for nearly every armored character.
  Extracted `_compute_victim_ac` mirroring ROM order; the hit test now uses
  `victim_ac` directly. Also gated the `-4` on `not can_see_character(attacker,
  victim)` (blind/dark/hide/detect-invis aware) instead of the victim's INVISIBLE
  affect (ROM `:496`).
- **Tests**: `tests/integration/test_fight081_ac_scale_order.py` (3) — pass. No
  existing combat test needed re-baselining (mob AC sits in the non-divergent band).

### `FIGHT-082` — ✅ FIXED (2.14.222) — HIGH

- **Python**: `mud/commands/combat.py:do_trip`
- **ROM C**: `src/fight.c:2711-2753`
- **Fix**: all four hunter sub-claims confirmed and fixed — (a) dropped the
  spurious `skill_level // 20` term from the bash-damage bound; (b) added the
  OFF_FAST/AFF_HASTE speed modifier (+10 self / −20 victim); (c) success WAITs the
  attacker for the skill's **raw beats** (24) and **DAZE**s the victim
  (`2*PULSE_VIOLENCE`) instead of WAITing it, failure WAITs `beats*2/3` (16),
  self-trip WAITs `2*beats` (48) — all previously a flat `PULSE_VIOLENCE`.
- **Tests**: `tests/integration/test_fight082_do_trip_cluster.py` (5) — pass.
- **Filed**: `FIGHT-088` (do_trip uses plain return strings vs ROM `act()`
  TO_VICT/TO_CHAR/TO_NOTVICT + omits the failure `damage(0)` call).

### `MAGIC-045` — ✅ FIXED (2.14.223) — HIGH

- **Python**: `mud/skills/handlers.py:heat_metal`
- **ROM C**: `src/magic.c:3123-3277` (`spell_heat_metal`)
- **Fix**: the port hardcoded `can_drop_obj` to `True`, collapsing ROM's cursed
  (NODROP) else-branches — a worn/carried cursed weapon/armor was dropped for the
  wrong damage instead of searing the victim and staying. Restored the real
  `can_drop_obj` (NODROP + immortal bypass) in all four branches, modelled
  `remove_obj`'s ITEM_NOREMOVE failure, and preserved ROM's `&&` short-circuit so
  the worn-armor DEX `number_range` is only drawn when droppable (RNG parity).
  Switched that bound to `get_curr_stat(Stat.DEX)`. Closes sub-findings (a) + (c).
- **Tests**: `tests/test_spell_heat_metal_rom_parity.py` (+3, verified red→green) — pass.
- **Filed**: `MAGIC-046` (sub-finding (b) — iteration order: Python's split
  inventory/equipment cannot reproduce ROM's single `victim->carrying` order;
  needs a unified ROM-ordered carrying accessor on `Character`).

### `FIGHT-083` — ✅ FIXED (2.14.224) — MEDIUM

- **Python**: `mud/skills/handlers.py:dirt_kicking`
- **ROM C**: `src/fight.c:2566-2608`
- **Fix**: restored ROM's "sloppy hack to prevent false zeroes"
  (`c_mod(chance,5)==0 → +=1`, before the terrain switch) and changed the
  post-terrain gate from `chance <= 0` to `chance == 0`, so a weak/low-dex kicker
  on dry land no longer wrongly sees "There isn't any dirt to kick." and correctly
  eats the guaranteed-miss WAIT_STATE; only water/air report no dirt.
- **Tests**: `tests/integration/test_fight083_dirt_kick_false_zero.py` (3) — pass.

### `FIGHT-084` — ✅ FIXED (2.14.225) — MEDIUM

- **Python**: `mud/combat/engine.py:check_parry`
- **ROM C**: `src/fight.c:1311`
- **Fix**: ROM halves parry on `!can_see(attacker, victim)` (attacker→victim); the
  port used `victim.can_see(attacker)` (wrong direction) with a `lambda x: True`
  fallback that made the halving **inert**. Now `not can_see_character(attacker,
  victim)` — correct direction and functional. Re-baselined
  `test_visibility_affects_defense` (had encoded the buggy victim→attacker
  direction via a mocked `victim.can_see`).
- **Tests**: `tests/integration/test_fight084_parry_visibility_direction.py` (3) — pass.
- **Filed**: `FIGHT-089` (identical inert `can_see` lambda in `check_dodge`;
  direction already correct, but the `/2` never fires).

## Files Modified

- `mud/combat/engine.py` — added `_compute_victim_ac`; `can_see_character` import;
  FIGHT-084 parry visibility predicate.
- `mud/commands/combat.py` — `do_trip` speed modifier + raw-beats/DAZE/damage-bound.
- `mud/skills/handlers.py` — `heat_metal` cursed-item branches; `dirt_kicking`
  false-zero hack + `chance==0` gate; `c_mod` import.
- `tests/integration/test_fight081_ac_scale_order.py`, `..._fight082_do_trip_cluster.py`,
  `..._fight083_dirt_kick_false_zero.py`, `..._fight084_parry_visibility_direction.py` — new.
- `tests/test_spell_heat_metal_rom_parity.py` — +3 cursed-item tests.
- `tests/test_combat_rom_parity.py` — re-baselined `test_visibility_affects_defense`.
- `docs/parity/FIGHT_C_AUDIT.md` — flipped FIGHT-081/082/083/084 → ✅; filed
  FIGHT-088, FIGHT-089.
- `docs/parity/MAGIC_C_AUDIT.md` — flipped MAGIC-045 → ✅; filed MAGIC-046.
- `CHANGELOG.md` — 5 Fixed entries.
- `pyproject.toml` — 2.14.220 → 2.14.225.

## Test Status

- Area suites: `test_fight081..084` (14) + `test_spell_heat_metal_rom_parity` (12)
  + combat defense/parity suites — all green.
- Full suite: **6049 passed, 4 skipped, 0 failed** (+17 vs the session-start 6032 —
  the 17 new tests; + the documented 40 pre-existing `Router.__init__` aiohttp
  collection errors — environmental, not a regression).
- `ruff check` clean on all touched files.

## Next Steps

Remaining open queue (all MEDIUM/LOW), by severity:

- `FIGHT-085` (MEDIUM) — skill wait-states are haste/slow-adjusted via
  `_compute_skill_lag`; ROM `WAIT_STATE` uses raw beats. Affects
  do_bash/do_kick/do_backstab/do_rescue. (FIGHT-082 already reads raw beats for
  do_trip — use that as the pattern.)
- `FIGHT-086` (MEDIUM) — backstab THAC0 bonus missing in `compute_thac0`
  (ROM `src/fight.c:474-475`). Moot at skill 100.
- `MAGIC-046` (MEDIUM) — heat_metal iteration order; needs a unified ROM-ordered
  `carrying` accessor (cross-cutting).
- `FIGHT-088` (MEDIUM) — do_trip act()-render + failure `damage(0)`.
- `FIGHT-089` (LOW) — check_dodge inert visibility halving (one-line:
  `not can_see_character(victim, attacker)`).
- `FIGHT-087` (LOW) — disarm floors unarmed hand-to-hand to 1.

Note: the GitNexus MCP server disconnected mid-session (after the FIGHT-082
reindex); impact/detect_changes fell back to `git diff` scope verification for
FIGHT-083/084. The index is stale — next agent should run
`npx gitnexus analyze --skip-agents-md` and restart the MCP server before relying
on `gitnexus_*` queries.
