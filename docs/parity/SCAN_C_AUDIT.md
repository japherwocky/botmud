# scan.c Audit — ROM 2.4b6 parity

## Scope

ROM reference: `src/scan.c`

Python implementation:

- `mud/commands/inspection.py::do_scan`
- `mud/skills/handlers.py::farsight` delegates to `do_scan`, matching ROM `spell_farsight`

## Audit result

**Status:** ✅ Complete

`scan.c` is already implemented and wired. The old tracker row claiming the command was
missing was stale.

## Verified ROM behaviors

- No-argument scan broadcasts `$n looks all around.` to the room and returns
  `Looking around you see:` to the actor.
- No-argument scan lists the current room at depth `0` and adjacent exits at depth `1`
  in ROM order: north, east, south, west, up, down.
- Directional scan accepts ROM direction tokens: `n/e/s/w/u/d` and full names.
- Invalid direction returns `Which way do you want to scan?`
- Directional scan emits only:
  - `You peer intently <dir>.` to the actor
  - `$n peers intently <dir>.` to the room
- The ROM local `buf` string `Looking <dir> you see:` is intentionally **not** sent.
- Directional scan follows exits up to depth `3`.
- Visibility filtering matches the intended ROM surface:
  - self excluded
  - invisible players above trust hidden
  - only visible characters listed
- Empty scans do **not** invent Python-only fallbacks like `No one is nearby.` or
  `Nothing of note.`
- Each listed character is rendered with **bare PERS** (`PERS(victim, ch)`,
  `src/scan.c:133`) — the short_descr/name only, with **no** `show_char_to_char`
  aura tags. An aura'd target (e.g. a healer with sanctuary) shows just its name,
  not `(White Aura) the healer` (FINDING-042, fixed 2.14.275). Python's `do_scan`
  now uses `pers()`, not `describe_character()`, for this reason.

## Test coverage

- `tests/test_scan_parity.py`
- `tests/integration/test_scan_broadcasts.py`
- `tests/test_commands.py`
- `tests/test_spell_farsight_rom_parity.py`

## Notes

- This audit closed the stale tracker row for `scan.c`.
- **Follow-up (2026-07-09, v2.14.275):** the differential harness scenario
  `scan_directions` surfaced FINDING-042 — `do_scan` rendered visible characters
  via `describe_character` (aura tags) instead of ROM's bare `PERS`. Fixed by
  switching to `pers()`. The per-file audit had marked scan complete because the
  divergence lived in the name-render call, not the audited control flow — an
  enumeration-independent catch.
