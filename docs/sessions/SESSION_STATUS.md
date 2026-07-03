# Session Status — 2026-07-03 — Cold-path divergence hunt (GET-015, PICK-003, GL-045)

## Current State

- **Active focus**: Cross-file invariants / divergence-class roster; cold-path
  divergence hunting (per-file audit tracker exhausted).
- **Last completed** (five-unit autonomous batch):
  - **Unit 1** — non-death `get all corpse` autosplit differential scenario
    (`get_corpse_money_autosplit`), locking the shared `do_get` → `_get_obj`
    autosplit path (`src/act_obj.c:162-184`) via a manual (non-death) entry.
    Converges. (v2.14.216)
  - **Unit 2** — `weather_tick` MM draw-order regression lock
    (`tests/test_weather_tick_draw_order.py`), pinning ROM `weather_update`'s
    unspecified-eval-order `dice()` expression (`src/update.c:578`) against a
    silent draw-swap. (v2.14.217)
  - **`GET-015`** — `get all <pit>` greed gate hardcoded `trust >= 51`; a
    level-51 mortal hero could empty a donation pit. Fixed to `>= LEVEL_IMMORTAL`
    (52); ROM `!IS_IMMORTAL` (`src/act_obj.c:320`). (v2.14.218)
  - **`PICK-003`** — `do_pick` door immortal check hardcoded `trust >= 51` on raw
    `char.trust` (wrong threshold + missing `get_trust` level fallback). Fixed to
    `char.is_immortal()`; ROM `!IS_IMMORTAL` (`src/act_move.c:958,963,973`).
    Contradicted a stale "immortal bypass FIXED" audit claim. (v2.14.219)
  - **`GL-045`** — `obj_update` object-affect fade skipped its `number_range(0,4)`
    draw at level 0 (swapped `&&` operands); ROM draws unconditionally
    (`src/update.c:933`). Object-side twin of GL-026. Fixed. (v2.14.220)
  - Filed OPEN (out-of-scope hunt findings): `FIGHT-081` (HIGH, verified — AC
    scale/order), `FIGHT-082..087` + `MAGIC-045` (hunter-reported, verify first).
- **Pointer to latest summary**:
  [SESSION_SUMMARY_2026-07-03_COLD_PATH_HUNT_GET015_PICK003_GL045.md](SESSION_SUMMARY_2026-07-03_COLD_PATH_HUNT_GET015_PICK003_GL045.md)

## Project Status (snapshot)

| Metric | Value |
|--------|-------|
| Version | 2.14.220 |
| Tests | 6032 passed, 4 skipped (+40 pre-existing aiohttp env collection errors) |
| Cross-file invariants | INV-054 latest (unchanged); GL-045 added to UPDATE_C_AUDIT |
| Differential scenarios | 56 committed (`get_corpse_money_autosplit` added) |
| Active focus | Cold-path divergence hunt; FIGHT-081 AC scale next |

## Next Intended Task

**Top priority: `FIGHT-081` (HIGH, already verified against ROM C).** Fix the AC
modifier scale/order in `mud/combat/engine.py:attack_round` — ROM `one_hit`
(`src/fight.c:483-503`) divides AC by 10 **first**, then applies the `<-15` clamp
and the −4/+4/+6 modifiers on the /10 scale; Python applies them to raw AC and
divides last, making armor/position modifiers ~10× too weak and over-triggering
the clamp for every armored character. HIGH blast radius (shared PC+NPC melee) —
scope with a differential combat scenario whose victim AC is in the divergent
band and expect combat-test re-baselining. Then re-verify and close
`FIGHT-082..087` and `MAGIC-045` (exact ROM cites in the audit docs). Separately,
the `Router.__init__()` aiohttp collection errors (6042→6032 passing) are an
environmental dependency issue, not a parity regression.
