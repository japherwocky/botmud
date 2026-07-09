# Session Summary — 2026-07-09 — Autonomous loop: 5 ROM-parity gaps + convergence finding

## Scope

Continued the autonomous parity loop requested as "a loop of 10 sessions."
Interpreted as sequential gap-closure units. Worked the pre-filed follow-up
backlog from `SESSION_STATUS.md` first (FIGHT-093, MOVE-009, MAGIC-046 remainder,
MAGIC-050, LOOK char-tags), then switched to fresh cold-path / cross-INV probing.
The probing hit **convergence** — every fresh probe (movement commands, affect
ticks, `wear all`, str-app) turned out already-faithful, already-fixed, or
design-heavy — so the loop was **stopped at 5 high-value fixes rather than padded
to 10** with marginal or risky changes (per the AGENTS.md autonomous
"stop-on-scope-completion" rule and an advisor consult). Full suite green.

`v2.14.268 → v2.14.273`, 6 commits (`db31a1a0` → `82c32cf2`), local on `master`,
**NOT pushed** — awaiting user review.

## Outcomes

### `FIGHT-093` — ✅ FIXED (2.14.269)

- **Python**: `mud/combat/engine.py:apply_damage`
- **ROM C**: `src/fight.c:697-713`
- **Gap**: the 1200-point "residual loophole" cap + weapon-extract cheat penalty
  were absent from `apply_damage`.
- **Fix**: physical hits (`dt >= TYPE_HIT`) dealing >1200 raw damage are clamped
  to 1200 before the >35/>80 reduction; non-immortal attackers get "You really
  shouldn't cheat." and lose their wielded weapon (`_extract_obj`). Spell dt exempt.
- **Tests**: `tests/integration/test_fight093_damage_1200_loophole.py` (2) — red→green.
- **Filed remainder**: `FIGHT-094` (OPEN) — `check_killer(ch, victim)` at
  `fight.c:733` is not in `apply_damage`. On re-analysis there is **no observable
  KILLER-flag gap** (round 1 flags via the command layer; round 2+ has
  `attacker.fighting is victim` so `check_killer` early-returns). Leave filed; its
  faithful closure is a subsystem-centralization decision, not a bugfix.

### `MOVE-009` — ✅ FIXED (2.14.270)

- **Python**: `mud/commands/combat.py:do_flee`
- **ROM C**: `src/fight.c:3002` → `src/act_move.c:196-202`
- **Gap**: `do_flee` re-implemented the move inline and emitted only "$n has
  fled!", omitting `move_char`'s "$n leaves $T." / "$n has arrived." broadcasts.
- **Fix**: emit both, gated on `!AFF_SNEAK && invis_level < LEVEL_HERO`
  (`show_movement`), PERS-masked per witness via `act_to_room`.
- **Tests**: `tests/integration/test_move009_flee_leave_arrive_broadcast.py` (2).
- **Filed remainder**: `MOVE-010` (OPEN) — `move_char`'s follower cascade
  (`act_move.c:206-234`, runs even on flee since the `follow` param is unused)
  drags standing charmed followers. Design-heavy (door-index follower drag);
  filed for a dedicated session.

### `MAGIC-046` (remainder) — ✅ FIXED (2.14.271)

- **Python**: `mud/spawning/templates.py:MobInstance.iter_carrying`; `mud/skills/handlers.py:heat_metal`
- **ROM C**: `src/magic.c:3134` (`heat_metal` `victim->carrying` walk)
- **Gap**: `MobInstance` lacked `iter_carrying`, so `heat_metal` fell to a generic
  `inventory + equipment.values()` branch for mobs.
- **Fix**: `MobInstance.iter_carrying()` returns `list(self.inventory)` — mobs keep
  worn+carried gear in one head-inserted list (FINDING-025), so it is already ROM
  `ch->carrying` LIFO order. Behaviorally identical, now first-class.
- **Tests**: `tests/integration/test_magic046_mob_iter_carrying.py` (2).

### `MAGIC-050` — ✅ FIXED (2.14.272)

- **Python**: `mud/skills/handlers.py:dispel_magic`
- **ROM C**: `src/magic.c:2089-2251`
- **Gap**: past the wholesale save, `dispel_magic` iterated the `spell_effects`
  dict (arbitrary order) instead of ROM's fixed hardcoded spell list — dropping the
  per-effect TO_ROOM wear-off messages, the AFF_SANCTUARY-bit fallback, and the
  final "Ok."/"Spell failed." — and desyncing the per-effect RNG draw order.
- **Fix**: rewrote the post-save body to mirror the sibling `cancellation`
  fixed-list walk (same list/messages) minus its NPC gate and `level+2`, plus the
  sanctuary-bit fallback and result message.
- **Tests**: `tests/test_spell_dispel_magic_order_messages_rom_parity.py` (2).

### `LOOK-011` — ✅ FIXED (2.14.273)

- **Python**: `mud/world/look.py:_char_tags` / `_room_occupant_line`
- **ROM C**: `src/act_info.c:253-276` (`show_char_to_char_0`)
- **Gap**: room occupant lines rendered only 2 of ROM's 12 status tags.
- **Fix**: new `_char_tags(observer, victim)` builds the full ROM-ordered prefix
  (`[AFK] (Invis) (Wizi) (Hide) (Charmed) (Translucent) (Pink Aura) (Red Aura)
  (Golden Aura) (White Aura) (KILLER) (THIEF)`), gating Red/Golden on the
  observer's DETECT_EVIL/GOOD + victim alignment; base name via pure `pers()` so
  tags render once and in order. `describe_character` left untouched (its aura
  output is test-locked by `test_spell_affects_persistence.py`).
- **Tests**: `tests/integration/test_look_char_tags_show_char_to_char_0.py` (2).

### Doc hygiene — CONST str_app header (2.14.273)

- `docs/parity/CONST_C_AUDIT.md` — the `str_app[26]` summary row still read
  "⚠️ PARTIAL (CONST-002, CONST-003)" though both sub-gaps are ✅ FIXED. Header
  corrected to match the sub-rows (AGENTS.md re-verify-status hygiene; no code).

## Convergence finding (why the loop stopped at 5)

After the pre-filed backlog was exhausted, fresh probes all came back clean:

- **Movement commands** — `do_visible` (faithful), `do_recall` (faithful bar a
  near-zero NPC-facing gate message), `do_sleep` (furniture branch ported).
- **Affect ticks** — char-side (`mud/affects/engine.py:tick_spell_effects`) and
  object-side (`mud/game_loop.py:_tick_object_affects`) both faithfully port the
  `number_range(0,4)` level-fade and the wear-off dedup gate (update.c:762-786/927).
- **`wear all` (WEAR-012 / FINDING-032)** — already fixed via the shared `_wear_obj`.
- **str-app tohit/todam (CONST-002/003)** — already fixed; only the header was stale.

Remaining truly-OPEN gaps are low-value OLC/admin/loader minutiae (BAN-001..004,
HEDIT-*, BIT-001, DB2-004/005 — several marked "deferred"/"theoretical") or the
two design-heavy filed items (FIGHT-094, MOVE-010). Manufacturing 5 more fixes from
that backlog would be padding, not parity progress.

## Files Modified

- `mud/combat/engine.py` — FIGHT-093 loophole cap.
- `mud/commands/combat.py` — MOVE-009 flee broadcasts + `_FLEE_DIR_NAMES`/`LEVEL_HERO`.
- `mud/spawning/templates.py` — `MobInstance.iter_carrying`.
- `mud/skills/handlers.py` — MAGIC-050 dispel_magic rewrite + heat_metal comment.
- `mud/world/look.py` — LOOK-011 `_char_tags` + `_room_occupant_line`.
- `tests/integration/test_fight093_*`, `test_move009_*`, `test_magic046_mob_iter_carrying.py`, `test_look_char_tags_*` + `tests/test_spell_dispel_magic_order_messages_rom_parity.py` — 10 new tests.
- `docs/parity/FIGHT_C_AUDIT.md` (FIGHT-093 ✅ + FIGHT-094 filed), `ACT_MOVE_C_AUDIT.md` (MOVE-009 ✅ + MOVE-010 filed), `MAGIC_C_AUDIT.md` (MAGIC-046 remainder ✅, MAGIC-050 ✅), `ACT_INFO_C_AUDIT.md` (LOOK-011 ✅), `CONST_C_AUDIT.md` (header fix).
- `CHANGELOG.md` — 5 Fixed entries.
- `pyproject.toml` — 2.14.268 → 2.14.273.

## Test Status

- New tests: 10/10 passing (red→green verified for each fix).
- Area suites (combat, flee, dispel/cancellation, look/room) — green, no regressions.
- **Full suite: 6133 passed, 4 skipped, 0 failed (EXIT 0, ~330s)** — halfway checkpoint.
- `ruff check` clean on all touched files.

## Next Steps

1. **Review + push.** 6 commits local on `master`, unpushed (`db31a1a0`→`82c32cf2`).
   Optionally release 2.14.273 to PyPI.
2. **Design-heavy filed gaps** (dedicated sessions, not loop units):
   - `MOVE-010` — flee follower cascade (charmed pets follow a fleeing master).
     Faithful fix wants delegating `do_flee` to `move_character`.
   - `FIGHT-094` — centralize `check_killer` into `apply_damage` (remove the ~10
     command-layer calls) vs. leave as-is; no observable gap today.
3. **Low-value OPEN backlog** if quantity is wanted: BAN-001..004, HEDIT-*, BIT-001,
   DB2-004/005 (mostly OLC/admin/loader; several explicitly deferred).
4. The high-value parity surface is **converging** — the productive next mode is a
   `/rom-divergence-sweep` pass or a `diff_harness` scenario on an unswept class,
   not per-file probing.
