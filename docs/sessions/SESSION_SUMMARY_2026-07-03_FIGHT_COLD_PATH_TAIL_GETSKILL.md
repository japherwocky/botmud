# Session Summary — 2026-07-03 — FIGHT cold-path tail (085–089, 091) + get_skill class

## Scope

Picked up from `SESSION_SUMMARY_2026-07-03_FIGHT_MAGIC_HIGH_MEDIUM_CLOSURE.md`
(FIGHT/MAGIC HIGH+MEDIUM closure), whose "Next Intended Task" queued the FIGHT
cold-path MEDIUM/LOW tail. The instruction was to complete "the next five
sessions" then write the handoff. Interpreting a *session* as the project's own
unit (~5 gap-closer commits + summary + status refresh — the prior session
closed exactly five), this was executed as **batch 1 = the queued FIGHT tail
(five gaps)**, then a **batch 2 start (FIGHT-091)** that surfaced the systemic
root cause behind several of these fixes: ROM's `get_skill` NPC-formula path is
unported (**HANDLER-008**), which the port has been papering over with per-skill
partial mirrors. Rather than proliferate more mirrors (the anti-pattern), the
class is enumerated and queued for a unified port. All work re-verified against
ROM C first per the AGENTS.md re-verify rule; full suite regression-clean.

## Outcomes

### `FIGHT-085` — ✅ FIXED (2.14.226) — skill wait-states use raw beats

- **Python**: `mud/skills/registry.py:_compute_skill_lag`
- **ROM C**: `src/merc.h:2116` (`WAIT_STATE` = bare `UMAX`); `src/fight.c:2469/2952/3081/3126`
- **Gap**: `_compute_skill_lag` halved lag under `AFF_HASTE` and doubled under `AFF_SLOW`; ROM applies raw `skill_table[sn].beats` — haste/slow only change `multi_hit` attack count, never lag.
- **Fix**: removed the HASTE/SLOW scaling (now `max(1, base_lag)`); dropped the dead `c_div`/`AffectFlag` imports. Rewrote the pre-existing unit test that asserted the wrong scaling.
- **Tests**: `tests/integration/test_fight085_skill_wait_raw_beats.py` (3) + rewritten `tests/test_skills.py::test_skill_wait_is_raw_beats_regardless_of_haste_slow`. Green.

### `FIGHT-086` — ✅ FIXED (2.14.227) — backstab THAC0 bonus restored

- **Python**: `mud/combat/engine.py:attack_round` / new `_backstab_skill`
- **ROM C**: `src/fight.c:474-475`; `src/handler.c:346`
- **Gap**: `one_hit` subtracts `10 * (100 - get_skill(ch, gsn_backstab))` from THAC0 (near-auto-hit below skill 100); the port had the damage multiplier but not the THAC0 branch.
- **Fix**: added the branch in `attack_round` plus `_backstab_skill` (PC learned / NPC ACT_THIEF `20+2*level`). Filed **HANDLER-008** for the still-unported systemic daze/drunk get_skill modifiers.
- **Tests**: `tests/integration/test_fight086_backstab_thac0.py` (2). Green.

### `FIGHT-089` — ✅ FIXED (2.14.228) — check_dodge visibility halving now functional

- **Python**: `mud/combat/engine.py:check_dodge`
- **ROM C**: `src/fight.c:1363` (`!can_see(victim, ch)`)
- **Gap**: the `getattr(victim, "can_see", lambda x: True)(attacker)` fallback never fired (runtime entities have no `can_see`), so a blind defender dodged at full chance. Twin of the already-fixed FIGHT-084 (`check_parry`).
- **Fix**: `not can_see_character(victim, attacker)` — functional and correct direction.
- **Tests**: `tests/integration/test_fight089_dodge_visibility_direction.py` (3). Green.

### `FIGHT-087` — ✅ FIXED (2.14.229) — unarmed disarm uses raw hand-to-hand skill

- **Python**: `mud/skills/handlers.py:disarm` / new `_hand_to_hand_skill`
- **ROM C**: `src/fight.c:3160-3164, 3186-3189`; `src/handler.c:394`
- **Gap**: unarmed disarm floored hand-to-hand to 1 (`max(hand_to_hand, 1)`) over a skills-dict lookup (0 for NPCs), so an unarmed NPC computed `chance*1/150` vs ROM's `chance*(40+2*level)/150`. The unarmed gate also used `hth<=0 AND !OFF_DISARM` where ROM is `hth==0 OR (IS_NPC AND !OFF_DISARM)`.
- **Fix**: `_hand_to_hand_skill` (PC learned / NPC `40+2*level`), dropped the floor (raw `hth`; the gate guarantees `hth != 0`), aligned the gate boolean to ROM. The sibling disarm-**skill** NPC lookup is filed under HANDLER-008.
- **Tests**: `tests/integration/test_fight087_disarm_unarmed_hth.py` (2). Green.

### `FIGHT-088` — ✅ FIXED (2.14.230) — do_trip act() lines + failure damage(0)

- **Python**: `mud/commands/combat.py:do_trip`
- **ROM C**: `src/fight.c:2735-2751`
- **Gap**: (a) success returned a single baked `"You trip X and they go down!"` — no room broadcast, no `$N`/`$M` PERS render; (b) failure only set the wait, never calling `damage(ch, victim, 0, gsn_trip, …)`, so a cold trip miss didn't start the fight or emit the miss combat message.
- **Fix**: success pushes the TO_VICT line, broadcasts the `$M`-gendered TO_NOTVICT via `act_to_room`, returns the TO_CHAR `act_format` line (success damage now `dt="trip"`); failure calls `apply_damage(char, victim, 0, DamageType.BASH, dt="trip")` before the `beats*2//3` wait and returns its (unpushed, single-delivery) TO_CHAR miss line. Filed **FIGHT-090** (do_trip vs skill_handlers.trip duplication).
- **Tests**: `tests/integration/test_fight088_do_trip_act_render.py` (2 — cold miss starts the fight via `victim.fighting is char`; success broadcasts `$M` to a bystander). Green.

### `FIGHT-091` — ✅ FIXED (2.14.231) — NPC kick chance uses ROM get_skill (10+3*level)

- **Python**: `mud/commands/combat.py:do_kick`
- **ROM C**: `src/fight.c:3125`; `src/handler.c:410`
- **Gap**: `do_kick` read the kick percent from the skills dict (empty for mobs), so an NPC's `chance == 0` and an aggressive OFF_KICK mob could never land a kick. ROM `get_skill(ch, gsn_kick)` returns `10 + 3*level` for an NPC.
- **Fix**: NPC branch now `max(0, min(100, 10 + 3*level))`; PC branch unchanged. Fourth site of the HANDLER-008 get_skill NPC-formula class.
- **Tests**: `tests/integration/test_fight091_npc_kick_skill.py` (1 — NPC kick lands at a roll where the 0-chance path always missed). Green.

### `HANDLER-008` — 🔄 IN PROGRESS (2.14.232–235) — unified `get_skill` port

The systemic root cause was tackled directly rather than papering over more sites.

- **Core (2.14.232)** — `mud/skills/skill_lookup.py:get_skill`, a faithful port of
  ROM `get_skill` (`src/handler.c:346-448`): PC class-level gate + learned; the full
  NPC formula dispatch (spell `40+2*level`, weapon `40+5*level/2`, kick `10+3*level`,
  backstab+ACT_THIEF, dodge/parry/trip/bash/disarm/berserk by off/act flags, …); the
  daze (`skill/2` spell, `2*skill/3` skill) and drunk (`9*skill/10`, PC) reductions;
  `URANGE(0,skill,100)`. `c_div` on the daze/drunk divisions (the "third attack"
  branch `4*level-40` is negative below level 10). Self-contained + unit-tested
  (`tests/test_get_skill.py`, 16). Zero call-site changes → zero regression risk.
- **Site migrations — all five offensive-skill sites** routed onto `get_skill`,
  retiring every partial mirror and newly applying ROM's daze/drunk (and the PC
  class-level gate) at each:
  - `do_kick` (2.14.233) — retired the inline NPC `10+3*level`.
  - backstab THAC0 in `attack_round` (2.14.234) — removed `engine._backstab_skill`.
  - `disarm` hand-to-hand (2.14.235) — removed `handlers._hand_to_hand_skill`.
  - `disarm`-**skill** gate (2.14.236) — NPC disarm now works (OFF_DISARM → 20+3*level;
    was 0 → always rejected).
  - `do_rescue` roll (2.14.237) — NPC rescue now works (40+level; was 0 → never succeeded).
- **Class-gate test fixes (2.14.238)** — the disarm-skill/rescue migrations enforce
  ROM's PC class-level gate; **the per-area runs passed but the full suite caught 8
  cross-file failures** (disarm/rescue tests in 5 files creating default *mage*-class
  casters that get_skill correctly gates to 0). Fixed ROM-faithfully by setting
  `ch_class=3` (warrior) + adequate level on those casters — they were asserting
  ungated behavior a mage-class char can't have. A worked example of the advisor's
  "run the full suite, not just per-area" rule.
- **Remaining before HANDLER-008 is ✅:** the *defensive* checks
  `check_dodge`/`check_parry`/`check_shield_block` still read the dict for their
  NPC-defender skill (ROM: OFF_DODGE dodger `level*2`, etc.) — so NPC mobs never
  dodge/parry/shield-block. Documented in the audit row; same class-gate blast radius.
- **Tests**: `tests/test_get_skill.py` (16) + daze-integration at the kick site +
  get_skill-based assertions replacing retired-helper unit tests + 8 cross-file
  class-gate fixes. Full suite **6079 passed, 0 failed**.

## New findings filed (durable, not fixed this session)

- **`FIGHT-090`** (MEDIUM, `FIGHT_C_AUDIT.md`) — `do_trip` (command) and `skill_handlers.trip` (skill-registry `"function": "trip"`) are divergent duplicate implementations of ROM `do_trip`; both live, each with its own gate ordering/message wording. Unify to one implementation.
- **`HANDLER-008`** (MODERATE, `HANDLER_C_AUDIT.md`) — ROM `get_skill` (`src/handler.c:346-448`) is unported: no unified helper applying the NPC formula defaults, the PC skill-level-by-class gate, the daze (`skill/2` spell, `2*skill/3` skill) / drunk (`9*skill/10`) modifiers, and the `URANGE(0,skill,100)` clamp. **The get_skill NPC-formula workaround now appears at five sites** — `engine._backstab_skill` (FIGHT-086), `handlers._hand_to_hand_skill` (FIGHT-087), `do_kick` inline (FIGHT-091), plus the still-unfixed `disarm`-skill lookup and `do_rescue`'s `get_skill(gsn_rescue)` roll. A unified `get_skill` would retire all of them and add daze/drunk uniformly. **This is the #1 next-session priority.**

## Files Modified

- `mud/skills/registry.py` — FIGHT-085 (removed haste/slow lag scaling + dead imports)
- `mud/combat/engine.py` — FIGHT-086 (backstab THAC0 + `_backstab_skill`), FIGHT-089 (check_dodge)
- `mud/skills/handlers.py` — FIGHT-087 (`disarm` raw hth + `_hand_to_hand_skill`)
- `mud/commands/combat.py` — FIGHT-088 (`do_trip` act lines + failure damage(0)), FIGHT-091 (`do_kick` NPC chance)
- `tests/integration/test_fight085…091*.py` — 6 new integration test files (13 tests)
- `tests/test_skills.py` — rewrote the wait-state haste/slow unit test to assert ROM behavior
- `docs/parity/FIGHT_C_AUDIT.md` — flipped rows FIGHT-085/086/087/088/089/091 → ✅ FIXED; filed FIGHT-090
- `docs/parity/HANDLER_C_AUDIT.md` — filed HANDLER-008 (get_skill), enumerated the 5-site class
- `CHANGELOG.md` — 6 Fixed entries
- `pyproject.toml` — 2.14.225 → 2.14.231

## Test Status

- Per-area suites (skills/combat/disarm/trip/kick/dodge): all green throughout.
- **Full suite**: `6061 passed, 4 skipped, 0 failed` (+40 pre-existing aiohttp/`Router` env collection errors, unchanged baseline). 6049 → 6061 = the 12 new passing tests (the 13th is parametrized). `ruff check .` clean.

## Next Steps

**Scope note for the next agent:** "five sessions" (≈25 gap-closer units) exceeds
a single context window at parity quality; this window completed **one full
session (batch 1: FIGHT-085/086/087/088/089) + one batch-2 gap (FIGHT-091)** and
enumerated the systemic follow-ups. Continue from here:

1. **HANDLER-008 — unified `get_skill(ch, sn)` port (highest value).** Build a
   faithful `get_skill` mirroring `src/handler.c:346-448`: PC learned + the
   `level < skill.levels[ch_class] → 0` gate; the NPC formula dispatch
   (spell→`40+2*level`, sneak/hide, dodge/parry+off_flags, shield_block,
   second/third attack, hand_to_hand→`40+2*level`, trip/bash/disarm+off_flags,
   berserk, kick→`10+3*level`, backstab+ACT_THIEF→`20+2*level`, rescue/recall,
   weapon skills→`40+5*level/2`, else 0); the daze (`skill/2` spell, `2*skill/3`)
   and drunk (`9*skill/10`, PC only) modifiers; and `URANGE(0,skill,100)`. Add it
   self-contained + unit-tested first (zero call-site changes = zero regression
   risk), then migrate the five sites listed above one at a time, retiring
   `_backstab_skill`/`_hand_to_hand_skill` and the inline `do_kick`/`disarm`
   workarounds. The `Skill` model already exposes `type` ("spell") and `levels`
   (per-class); `Character` exposes `daze` and `condition[COND_DRUNK]` (index 0).
2. **MAGIC-046 — unified ROM-ordered `carrying` accessor** (`heat_metal` RNG
   draw-order + remove_obj act lines). Structural; needs an acquisition-order walk
   over `inventory + equipment`.
3. **FIGHT-090 — unify `do_trip` / `skill_handlers.trip`** into one implementation.
4. Then resume cold-path / cross-file-invariant divergence hunting (the active
   mode per AGENTS.md) for further batches.
