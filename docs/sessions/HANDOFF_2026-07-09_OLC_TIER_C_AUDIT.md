# Handoff — 2026-07-09 — OLC audit state & the real remaining work

**For the next agent picking up "the OLC audit" (option #2 from the
2026-07-09 loop session).** Read this before touching any OLC code or doc —
it corrects a false premise that would otherwise send you chasing already-done
work.

## TL;DR

**OLC is NOT an open audit.** Per the authoritative
`docs/parity/ROM_C_SUBSYSTEM_AUDIT_TRACKER.md` (lines 104–109), every OLC file
is **✅ AUDITED, 100% on CRITICAL/IMPORTANT**:

| File | Tracker status | Verified in code |
|------|---------------|------------------|
| `olc.c` | ✅ 100% (OLC-001..023) | — |
| `olc_act.c` | ✅ 100% CRIT/IMP (OLC_ACT-001..014) | — |
| `olc_save.c` | ✅ 100% CRIT/IMP/MINOR (OLC_SAVE-001..017) | `save_specials` `mud/olc/save.py:324`, `save_shops`/`_collect_shops` `save.py:342` |
| `olc_mpcode.c` | ✅ 100% (MPEDIT-001..006, 23 tests) | `_mpedit_create/show/code/list` `mud/commands/imm_olc.py:579-658` |
| `hedit.c` | ✅ 100% (HEDIT-001..014, 24 tests) | `_hedit_delete` `mud/commands/build.py:4239`, `_hedit_list` `build.py:4289` |
| `bit.c` | ✅ 100% (BIT-001..003) | `flag_value` `mud/utils/bit.py` |

I verified the allegedly-missing functions **exist and cite their ROM source**
(2026-07-09). So the "port the OLC functions" framing is wrong.

## Why it *looked* open (the trap — do not fall in)

The **per-file OLC audit docs have stale rows** that contradict the authoritative
tracker and the actual code:

- `HEDIT_C_AUDIT.md:21-22` — `hedit_delete`/`hedit_list` marked `❌ MISSING`.
  **Actually ported** (`build.py:4239,4289`).
- `OLC_MPCODE_C_AUDIT.md:13-19` — `mpedit_*` marked `❌ MISSING`. **Actually ported**
  (`imm_olc.py`).
- `OLC_SAVE_C_AUDIT.md:76-87` — `save_mobprogs/specials/shops/helps` `❌ MISSING`.
  **`save_specials`/`save_shops` ported** (`olc/save.py`); verify the rest.
- `JSON_LOADER_C_AUDIT.md:46-48` — `convert_mobile/objects/object` `❌ MISSING`.
  **N/A by design** — these only convert old-format `.are` mobs; QuickMUD uses ROM
  2.4 new-format + JSON (see `JSON_LOADER_C_AUDIT.md:50`). Not a gap.

This is the same **systemic stale-doc pattern** the 2026-07-09 session found in
CONST/BAN/BIT (stale `⚠️ PARTIAL` summary headers over `✅ FIXED` sub-gaps —
corrected in commits `82c32cf2`, `fc38bb7c`). The per-file docs rot; the
subsystem tracker + the code are the sources of truth. **Re-verify every `❌`/
`⚠️` against the tracker and the code before acting on it** (AGENTS.md
"re-verify status" rule).

## What is *genuinely* left in OLC

1. **`olc_act.c` TIER-C deep audit (~78 functions)** — the one real deferred item.
   These are per-field setters (`redit_heal`, `oedit_weight`, `medit_level`, …)
   marked `🔄 NEEDS DEEP AUDIT` in `OLC_ACT_C_AUDIT.md`. Per that doc's line 424
   they are "individually low-risk and covered by the existing inline dispatch in
   `_interpret_redit/oedit/medit`. **No gameplay-visible CRITICAL gaps remain.**"
   This is a completeness/verification pass, not a bug hunt — expect mostly ✅
   confirmations with the occasional message-string or bound divergence.

2. **Deferred display sub-gaps** (filed, low priority):
   - `OLC_ACT-010b` — dice/AC stored as strings ("15d8+50") in Python vs ROM's 3
     ints; `medit show` emits as-is until the model exposes components.
   - `OLC_ACT-010c` — shop/mprogs/spec_fun rendering in `medit show` needs
     MobShop/MProg model alignment + `spec_name` lookup.
   - `OLC_ACT-010d` — ROM-faithful flag-table name strings (e.g. ROM `stay_area`
     vs Python `STAY_AREA`) — needs display tables like OLC_ACT-009's
     `_WEAR_FLAG_DISPLAY` for act/affect/form/part/imm/res/vuln/off/size/position.
   - `show_version` (`olc_act.c:62-74`) — TIER C, low priority, genuinely absent.

## Recommended first steps for the next session

1. **Reconcile the stale per-file OLC docs FIRST** (one doc-hygiene commit): flip
   the `❌ MISSING` rows in `HEDIT_C_AUDIT.md`, `OLC_MPCODE_C_AUDIT.md`,
   `OLC_SAVE_C_AUDIT.md`, and `JSON_LOADER_C_AUDIT.md` to `✅`/`N/A` where the
   tracker+code confirm they're done. This stops the next agent (and you) from
   re-auditing ported functions. ~30 min, high value.
2. **Then decide scope for the TIER-C pass.** It is explicitly deferred and
   low-risk. If you take it, run it as `/rom-parity-audit olc_act.c` focused on
   the TIER-C setters — expect a verification sweep, not gap closures. Batch the
   ✅ confirmations; only the rare real divergence becomes a `/rom-gap-closer`.
3. **Higher-leverage alternative** (recommended): the per-file surface has
   converged (2026-07-09 session closed the last 5 clean gaps and found the rest
   already-fixed). The productive next mode is the **enumeration-independent**
   check — a `/rom-divergence-sweep` pass on an unswept divergence class, or a new
   `diff_harness` scenario for C-ground-truth divergences the per-file trackers
   can't name. See `docs/parity/DIVERGENCE_CLASS_ROSTER.md` and
   `tools/diff_harness/README.md`.

## Non-OLC genuinely-open items (for completeness)

- `DB_C_AUDIT.md:264` — `check_pet_affected` (pet affect save/load) — Not
  implemented; niche.
- `DB2-005` — multi-line `fread_string` for mob/obj name/short_descr — theoretical
  (canonical areas never use it); `read_string_tilde` is not a faithful
  `fread_string` (whitespace/blank-line handling differs), so it's a risky loader
  change for a non-occurring case. Correctly deferred.
- `DB2-004` — `kill_table[level].number` not maintained; no command surface.

## State at handoff

- Master is at `dfdf90e8` (pushed), v2.14.273. Full suite: 6133 passed / 0 failed.
- Latest session summary:
  [SESSION_SUMMARY_2026-07-09_AUTONOMOUS_LOOP_5_GAPS.md](SESSION_SUMMARY_2026-07-09_AUTONOMOUS_LOOP_5_GAPS.md).
- Canonical state pointer: [SESSION_STATUS.md](SESSION_STATUS.md).
