# Test Failure Tracker

Bug tickets discovered while trimming the test suite to focus on gameplay.
Each ticket describes a real issue a player would hit, not ROM parity trivia.

## Status legend

- [FIXED] - merged to master
- [OPEN] - known bug, not yet fixed
- [DEFERRED] - known bug, intentionally left for a later pass

---

## TELNET-001 - Plain prompts render as raw text, missing ANSI escape

**Status:** [FIXED] in commit 7e966d66

`TelnetStream.send_prompt` did not wrap plain prompts (e.g. `Name: `) in
`{g...{x` when ANSI was enabled and the prompt had no `{X` token. Clients
and tests asserting `b'\x1b['` in the greeting failed.

**Fix:** when `ansi_enabled and "{" not in text`, prepend `{g` and append
`{x`.

**Tests affected:**
- `tests/test_account_auth.py::test_new_player_receives_motd` (now
  passes)

---

## CONFTEST-001 - `help_greeting` was empty in test_account_auth

**Status:** [FIXED] in commit 7e966d66

`tests/test_account_auth.py` spins up the real telnet server and expects
`_send_help_greeting` to emit the ROM welcome banner. That function
reads from the module-level `help_greeting` global populated by
`load_help_file("data/help.json")`. The previous conftest did not
preload the help file, so the greeting was empty and the banner was
never sent.

**Fix:** added session-scoped autouse fixture in `tests/conftest.py`
that loads `data/help.json` once per test session.

**Tests affected:** 4 tests in `test_account_auth.py` now pass.

---

## TELNET-002 - `test_ansi_preference_persists_between_sessions` has a too-strict byte assertion

**Status:** [FIXED] in commit 2813df66

The test reads bytes between the ANSI preference prompt and the `Name: `
prompt, then asserts `b"\x1b[" not in greeting_off`. But the ANSI
prompt itself ends with `\x1b[0m\xff\xf9` (the `reset` colour and the
IAC GA byte), and `readuntil(b"Name: ")` consumes those trailing bytes
into the returned `greeting` variable. The assertion therefore fires
even though the production code is correct.

**Fix:** scope the assertions to the actual greeting body
(`greeting_off[banner_start:greeting_off.rfind(b"Name: ")]`) so the
test still asserts the user-disabled ANSI mode is honoured, but
doesn't false-positive on the ANSI prompt's own colour tail.

---

## AUTH-001 - Character room not persisted on save/load

**Status:** [OPEN]

`test_new_character_persists_true_sex` saves a character, then
`load_player_character("Pelvex")` returns a character with `room =
None`. The test asserts `reloaded.room is not None` and fails.

**Repro:**
```python
char.room = Room(vnum=ROOM_VNUM_LIMBO, name="Limbo", description="")
char.was_in_room = Room(vnum=ROOM_VNUM_SCHOOL, name="The School", description="")
save_player_character(char)
reloaded = load_player_character("Pelvex")
assert reloaded.room is not None  # FAILS - room is None
```

The hybrid save/load pfile is not writing/reading the room. Likely the
JSON pfile schema is missing a `room` field, or the save/load path is
serializing `was_in_room` instead of `room`.

**Files to investigate:** `mud/account/account_service.py`,
`mud/save/`, `mud/loaders/pfile_loader.py`.

---

## AUTH-002 - Ban list not reloaded when telnet server starts

**Status:** [OPEN]

`test_permanent_ban_survives_restart` adds a ban host, saves the ban
file, clears in-memory bans, starts a new telnet server (which should
re-load bans via `bootstrap_server`), then asserts
`bans.is_host_banned("203.0.113.9")` - which returns `False`.

**Repro:** already exercised by the test; the production code's ban
reload on server start is missing or runs before the file is written.

**Files to investigate:** `mud/server_bootstrap.py`,
`mud/security/bans.py`, `mud/net/telnet_server.py`.

---

## How to run the test suite locally

```bash
make install
make test                # serial, default
make test-parallel       # opt-in 5-worker parallel
```

The full suite is ~4,720 items. On a modern box it takes ~5-15 minutes
serially; parallel can crash on WSL.

---

## ASYNC-001 - Some asyncio-based tests hang in serial runs

**Status:** [OPEN]

`test_ansi_preference_persists_between_sessions` (account auth) and
`test_telnet_server_handles_look_command` (telnet server) hang past
the per-test timeout when run as part of the full suite. They pass when
run individually.

The likely cause: these tests use `asyncio.run()` at module scope, which
creates a new event loop and tears it down. The teardown may not be
cleaning up TCP listeners, sockets, or other resources, which then leaks
into the next test and eventually wedges the suite.

**Workaround:** run with `--timeout=15` and `--deselect` of the
offending tests, or skip the affected files.

**Files to investigate:**
- `tests/test_account_auth.py::test_ansi_preference_persists_between_sessions`
- `tests/test_telnet_server.py::test_telnet_server_handles_look_command`

**Suggested fix:** make these tests use a pytest-asyncio fixture
(`async def test_...`) instead of `asyncio.run()` inside the test body,
so that pytest-asyncio owns the loop lifecycle and teardown is clean.

