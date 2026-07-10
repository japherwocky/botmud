# Session Summary — 2026-07-10 — Autonomous /loop command-handler sweep (8 fixes)

## Scope

Autonomous `/loop` run (self-paced, 10-session budget; this handoff covers
sessions 1–5, `v2.14.288 → v2.14.296`). Picked up from the 2026-07-09 batch-2
render/wear session. Mode: **source-read + parallel-hunter sweeps of unswept
command handlers** — `general-purpose` subagents compared batches of command
functions against their ROM C originals, and **every** candidate divergence was
re-verified against `src/*.c` by hand before closing. The hunters surfaced real
divergences (wrong message strings, guard-order inversions, a phantom-attribute
dead-code block) that the per-file audits had marked complete; the manual probes
confirmed the recently-implemented complex systems (combat, shops) are already
faithful.

All commits are **LOCAL on `master`, UNPUSHED** — awaiting user review.

## Outcomes

### `LOCK-001` — ✅ FIXED (2.14.289)
- **Python**: `mud/commands/doors.py:do_lock`/`do_unlock` (container arms)
- **ROM C**: `src/act_move.c:627-656,761-791`
- **Gap**: lock/unlock container arm carried a spurious `CONT_CLOSEABLE` check ROM's `do_lock`/`do_unlock` do not have (only `do_open`/`do_close` do — MOVE-008). 98 stock open non-closeable containers (pouches/packs) returned "You can't do that." where ROM returns "It's not closed."
- **Fix**: removed the guard, restoring ROM's `CLOSED → key → has_key → LOCKED` order.
- **Tests**: `tests/integration/test_lock001_container_closeable_guard.py` (2)

### `LOCK-002` — ✅ FIXED (2.14.290)
- **ROM C**: `src/act_move.c:637,773`
- **Gap**: container key guard used `value[2] <= 0` vs ROM's `< 0`; 14 stock keyless closed containers said "It can't be locked." where ROM says "You lack the key." (the portal sibling arm already used `< 0`).
- **Tests**: `tests/integration/test_lock002_container_key_threshold.py` (2)

### `PASSWORD-002` — ✅ FIXED (2.14.291)
- **ROM C**: `src/act_info.c:2889,2896`
- **Gap**: `do_password` syntax line dropped ROM's trailing period; wrong-password line had one space where ROM has two ("Wrong password.  Wait 10 seconds.").
- **Tests**: `tests/integration/test_password002_message_fidelity.py` (2, exact-byte `==`)

### `HEALER-007` — ✅ FIXED (2.14.292)
- **ROM C**: `src/healer.c:67`
- **Gap**: `heal` price-list header not first-letter-capitalized (ROM `act()` caps `buf[0]`); the sibling "not enough gold" branch already used `capitalize_act_line`.
- **Tests**: `tests/integration/test_healer007_header_capitalization.py` (1)

### `LOOK-016` — ✅ FIXED (2.14.293) — **HIGH**
- **Python**: `mud/world/look.py:_show_equipment`
- **ROM C**: `src/act_info.c:483-499` (`show_char_to_char_1`)
- **Gap**: `look <character>` **never showed any worn equipment** — `_show_equipment` read a phantom `char.equipped` attribute (real attr is `char.equipment`, int-keyed; there is no `equipped`), so `getattr(..., {})` always returned `{}` and the whole "X is using:" block was dead code. Equipment-key convention class (school-light/combat-shield) via a wrong **attribute NAME** — invisible to the string-key grep-guard.
- **Fix**: rewrote `_show_equipment(victim, observer)` to mirror ROM: ascending slot order, `can_see_object` gate, `where_name + format_obj_to_char` (aura/status tags), no indent, capitalized header.
- **Tests**: `tests/integration/test_look016_char_equipment_block.py` (2)

### `LOOK-017` — ✅ FIXED (2.14.294)
- **ROM C**: `src/act_info.c:285-288` (`show_char_to_char_0`)
- **Gap**: room list omitted a standing PC's title. ROM appends `pcdata->title` after `PERS` when `!IS_NPC && !COMM_BRIEF(observer) && position==STANDING && observer->on==NULL`. Guard keys on the observer (ROM quirk) — replicated faithfully.
- **Tests**: `tests/integration/test_look017_standing_pc_title.py` (3)

### `KICK-001` — ✅ FIXED (2.14.295)
- **ROM C**: `src/fight.c:3109-3124`
- **Gap**: `do_kick` checked `fighting == NULL` before the PC level gate; a sub-level PC not in combat saw "You aren't fighting anyone." where ROM shows "You better leave the martial arts to fighters." Relocated the fighting check below the level/OFF_KICK gates. Three existing tests encoded the pre-fix order with a below-level char and were corrected to level the char past the kick requirement.
- **Tests**: `tests/integration/test_kick001_guard_order.py` (2)

### `TRIP-001` — ✅ FIXED (2.14.296)
- **ROM C**: `src/fight.c:2654`
- **Gap**: `do_trip` no-skill message "Tripping?  What's that?" had one space vs ROM's two.
- **Tests**: `tests/integration/test_trip001_message_fidelity.py` (1)

## Durable rows filed (verified vs ROM, NOT closed)

- **`LOCK-003`** (`ACT_MOVE_C_AUDIT`) — door key `<=0` vs ROM `<0`; unreachable (all stock exit keys are `-1`). Latent.
- **`DESC-001`** (`ACT_INFO_C_AUDIT`) — `do_description` plain-replace 1024 guard checks the argument where ROM checks an empty buf; unreachable (`MAX_INPUT_LENGTH=256` caps a single command below 1024). Latent.
- **`WIMPY-002`** (`ACT_INFO_C_AUDIT`) + **`DROP-001`** (`ACT_OBJ_C_AUDIT`) — the **is_number/atoi parity class**: ROM's numeric parsers accept a sign/partial-numeric prefix, Python's `isdigit`/`int()` don't. Wants one shared `rom_is_number`/`rom_atoi` helper.
- **`do_title`** UB note (`ACT_INFO_C_AUDIT`) — Python's `i>1` guard intentionally avoids ROM's out-of-bounds `argument[-1]` read on a lone `{`; noted so a future audit doesn't "fix" it back.
- **`BASH-001`** (`FIGHT_C_AUDIT`, MEDIUM, open) — `do_bash` never delivers the attacker's TO_CHAR flavor line and all bash broadcasts drop ROM's `{5…{x` color. Fix must reconcile ROM's two-caster-lines (damage dam_message + flavor TO_CHAR) with the single-string command return via `apply_damage`'s push-vs-return single-delivery contract (INV-001) — model on `do_trip`. Deserves a dedicated gap-closer.
- **`STEAL-001`** (`FIGHT_C_AUDIT`, minor) — `do_steal` never calls `check_improve` (same stub class as PICK-001/RECALL-002).
- **`RESCUE-002`** (`FIGHT_C_AUDIT`, low) — `skill_handlers.rescue` uses raw name vs ROM `$N`/PERS; only diverges when an NPC is party (dispatched `do_rescue` is clean).

## Verified CLEAN (no gap)

`dam_message` thresholds/punct, `do_consider`, `do_sacrifice`, `do_split`,
`do_pour`, `do_practice`, `do_worth`, `do_where`, `get_cost`, `do_drink`,
`do_give`, `do_report`, `do_affects`, `do_examine`, `do_look` health tiers,
`do_sneak`, `do_hide`, `do_rescue` (command), `do_recite`.

## Files Modified

- `mud/commands/doors.py` — LOCK-001/002 container guard sequence
- `mud/commands/character.py` — PASSWORD-002 strings
- `mud/commands/healer.py` — HEALER-007 header capitalization
- `mud/world/look.py` — LOOK-016 (`_show_equipment` rewrite) + LOOK-017 (title)
- `mud/commands/combat.py` — KICK-001 guard order + TRIP-001 string
- `tests/integration/test_{lock001,lock002,password002,healer007,look016,look017,kick001,trip001}*.py` — new
- `tests/{test_combat,test_skill_combat_rom_parity}.py`, `tests/integration/test_skills_integration_combat_specials.py`, `tests/integration/test_fight_026_npc_offensive_skill_no_crash.py` — corrected pre-fix-order / stale-string assertions
- `docs/parity/{ACT_MOVE,ACT_INFO,ACT_OBJ,HEALER,FIGHT}_C_AUDIT.md` — new/updated rows
- `CHANGELOG.md` — Fixed entries; `pyproject.toml` — 2.14.288 → 2.14.296

## Test Status

- Per-area suites green throughout (lock/door 287, look/equip/room 454+, kick 57, trip 111, healer 7).
- Full suite: **exit 0 (green)** — see SESSION_STATUS for the pass count.

## Next Steps

Loop continues (~4–5 sessions remaining). Next hunter batch: `do_cast`
failure/mana messages, `do_quaff`/`do_zap` wand, `do_eat`, `do_wear`/`do_remove`
edge messages, `do_sit`/`do_rest`/`do_sleep` furniture messages. Prioritise the
open **BASH-001** (medium, player-facing) as a dedicated closer once the
`apply_damage` single-delivery contract is confirmed. Consider a shared
`rom_is_number`/`rom_atoi` helper to close the DROP-001/WIMPY-002 class at once.
**All commits are unpushed — user review + push is the gating next action.**

### Roster insight (for `DIVERGENCE_CLASS_ROSTER.md`)

`getattr(obj, "wrong_name", default)` — an attribute-name typo that silently
returns the default — is a blind spot the Layer-A equipment-key grep-guard
(`test_equipment_key_convention.py`) cannot see (it forbids string slot keys like
`.get("shield")`, not wrong attribute names). LOOK-016 was this class. Worth a
roster note: attribute-name reads with a default are the invisible sibling of the
equipment-key convention.
