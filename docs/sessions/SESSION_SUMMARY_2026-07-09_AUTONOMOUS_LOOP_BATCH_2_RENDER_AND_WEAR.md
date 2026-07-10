# Session Summary — 2026-07-09 — Autonomous loop batch 2: render + wear/equip parity divergences

**Mode:** Autonomous `/loop` — "complete 10 more sessions." Reframed (as in batch 1)
as **10 committed, self-maintaining units of parity work**: real ROM-C→Python
divergences found by source-reading command surfaces + parallel hunter subagents,
each closed failing-test-first with one `fix(parity)` commit. No fabricated fixes;
stopped honestly when the reachable core surfaces converged.

**Version:** v2.14.278 → **v2.14.288** (10 commits, all LOCAL on `master`, UNPUSHED).

## Method

Same productive mode as batch 1 (differential-harness-on-unswept-surfaces), plus a
**parallel-hunter** force-multiplier: dispatched `general-purpose` subagents to
compare specific ROM C command functions against their Python ports and report
concrete divergences, which I then **re-verified against ROM source myself** (per
AGENTS.md's "re-verify ✅ claims" rule — subagent findings are leads, not truth)
before closing each as a gap-closer unit. 5 hunters run; every reported finding
was source-verified before any fix.

## The 10 units (all committed)

| # | Gap | File | Commit | What was wrong |
|---|-----|------|--------|----------------|
| 1 | **SCORE-002** | act_info.c | ffd61df0 | `score` carry-weight line used bare `ch.carry_weight`, dropping coin burden. ROM `get_carry_weight(ch)/10` adds `silver/10 + gold*2/5` (merc.h:2118). Codebase already had two faithful `get_carry_weight` helpers `do_score` never called. |
| 2 | **LOOK-015** | act_info.c | a7827d74 | `look in <drink container>` fill band rewritten as `value[1]*100//value[0]` vs 25/75. ROM uses `value[1] < value[0]/4` / `< 3*value[0]/4`; C truncates each expression independently, so labels diverge at boundary amounts (value=(10,2): ROM "about half-" vs "less than half-"). |
| 3 | **COMPARE-002** | act_info.c | b785b902 | `compare X Y` missing second item returned `"You do not have that second item."`; ROM emits the same `"You do not have that item."` as the first-item branch (act_info.c:2338). |
| 4 | **INTERP-035** | interp.c | 22e5fcad | Sleeping "snore" social exception compared the *typed* string, not the *resolved* social. ROM `!str_cmp(social_table[cmd].name, "snore")` — so `snor` (prefix → snore) is allowed while asleep; Python blocked it. |
| 5 | **EQUIP-002** | act_info.c | 79a64bf4 | `equipment` built names from bare `obj.short_descr`, dropping ROM `format_obj_to_char` status tags `(Invis)/(Red Aura)/(Blue Aura)/(Magical)/(Glowing)/(Humming)` (act_info.c:2279). A faithful helper existed but wasn't wired in. |
| 6 | **INVEN-001** | act_info.c | 3ccd5efb | Same root as EQUIP-002 in `inventory`: dropped status tags AND keyed the combine/dedup on the prefix-blind string, so a glowing item + a plain identical item wrongly collapsed to `( 2)` (act_info.c:166,180). Both display paths now route through `format_obj_to_char`. |
| 7 | **RECALL-003** | act_move.c | cf18eb43 | The `recall` **command** (`do_recall`, session.py) returned `""` silently for a non-pet NPC (comment wrongly claimed "ROM returns silently") and gated on `master` instead of the `ACT_PET` flag. ROM sends `"Only players can recall."` and checks ACT_PET (act_move.c:1569-1573). The recall *spell* handler was already correct. |
| 8 | **WEAR-013** | act_obj.c | 0adf52cd | Two-hands-free wield block ended with `!`; ROM ends it with a period: `"You need two hands free for that weapon."` (act_obj.c:1635). Sibling shield-branch `"...weapon!"` correctly keeps its `!`. |
| 9 | **WEAR-014** | act_obj.c / handler.c | 99fe9326 | Alignment "zap" returned a generic "the item" message, emitted no room line, and **left the item carried**. ROM `equip_char` (handler.c:1765-1777) emits a `$p`-named TO_CHAR + TO_ROOM message and **drops the item to the floor**. Added `_zap_align` routing all 4 zap sites. Minor documented residual: ROM prints the "You wear" line before the zap (Python emits only the zap line — item resting state now matches). |
| 10 | **WEAR-015** | act_obj.c | f08a9a20 | `_wear_obj` checked the HOLD flag before armor slots; ROM `wear_obj` dispatches wear flags in bit order (armor/shield all below HOLD's 1<<14). An object flagged both an armor slot and HOLD is worn on the slot, not held. Added `_PRE_HOLD_WEAR_MASK` precedence guard. Unreachable in stock data; required for custom-area parity. |

**Shape:** 8 of 10 are the batch-1 pattern — an audited-"complete" function whose
render/dispatch skipped a ROM accessor, message, flag, or precedence. The two
`format_obj_to_char` misses (EQUIP-002/INVEN-001) share one root; WEAR-014's
item-drop is the only observable *state* divergence (rest are output/wording).

## Converging surfaces (probed, faithful — no unit)

Source-read and confirmed ROM-faithful (documented here so the next agent doesn't
re-probe): `do_worth`, `do_consider`, `do_practice`, `do_wimpy` (modulo the
shared `atoi("5x")→5` edge), `do_examine`, `do_sacrifice` (SAC-001–006),
`do_put` (two-part weight check), `do_give` (GIVE-001–005), `do_drink`/`do_eat`/
`do_fill`/`do_pour` (hunter-verified: `c_div` on negative `liq_affect`, all
thresholds), the room-occupant line (`_room_occupant_line` capitalization),
and the act_comm say/tell capitalize sites (color-code-prefixed → `buf[0]=UPPER`
is a no-op).

## Outstanding — verified latent edges NOT fixed (file durably per AGENTS.md)

Two hunter findings verified against ROM but **not stock-reachable** / architecture-marginal;
left for a future careful pass rather than a rushed/risky fix:

- **WEAR-016 (D3b) — WIELD dispatched by `item_type == WEAPON`, not the `ITEM_WIELD`
  wear flag.** ROM `wear_obj` (act_obj.c:1616) uses `CAN_WEAR(obj, ITEM_WIELD)`. In
  Python (`equipment.py:212`) a WEAPON-type item without the WIELD flag would still
  be wielded, and a non-weapon flagged ITEM_WIELD would not. Stock weapons carry
  both, so unconfirmed-reachable; the dispatch *key* genuinely differs. Fixing is
  riskier (many paths assume `item_type==WEAPON → wield`). File under ACT_OBJ if a
  reachable case is found.
- **WEAR-017 (D4) — STR wield-weight check reads `obj.prototype.weight`, not ROM's
  `get_obj_weight(obj)`** (instance weight incl. contained items; act_obj.c:1624).
  In Python's prototype-based weight model there's no independent instance weight
  for a (contents-less) weapon, so this is not a real divergence today — flagged
  for completeness only.

## Test / validation

- Every unit: failing-test-first, then fix, then per-area suite green. Corrected two
  stale test assertions that pinned buggy behavior (`test_recall_npc_blocked` `== ""`,
  per AGENTS.md "a test contradicting ROM C is a bug in the test").
- Full serial regression (`-n0`, excluding the documented pre-existing hang
  `test_character_advancement.py::test_kill_mob_grants_xp_integration`):
  **6134 passed, 4 skipped, 2 failed**. Both failures
  (`test_mobprog_triggers.py::test_event_hooks_fire_rom_triggers`,
  `test_skills_combat.py::test_trip_knocks_target_wait_daze_and_improve`) **pass in
  isolation** (`pytest -n0 <both>` → 2 passed) — they are the known cross-file
  **RNG-leak order flakes** (AGENTS.md "Parallel test execution & isolation"),
  surfaced by the serial full run's test ordering. Neither is in any changed-file
  call path, and none of this batch's fixes touch `rng_mm`, so they are
  pre-existing, not regressions.
- `ruff check` / `ruff format` clean (pre-commit enforced on every commit).

## Known pre-existing flake (unchanged, NOT this session)

`test_character_advancement.py::test_kill_mob_grants_xp_integration` hangs (fixture
monkeypatches `number_bits → 19`, `spec_cast_mage → _select_spell` loops). Present
on HEAD before this session; orthogonal to render/wear changes. Also the xdist
`sessionfinish` teardown flake persists — authoritative green is the serial `-n0`
run minus the flaky file.

## Next intended task

1. **Review + push** the v2.14.279→288 commits (all local on `master`).
2. Keep mining unswept surfaces (do_open/close/lock door messages, spell messages,
   fight.c `dam_message` verb thresholds — a LOOK-015-class boundary vein).
3. Evaluate WEAR-016/017 reachability against real area data; fix if reachable.
4. Land the known xdist worker-crash fix so the parallel full suite is reliable.
