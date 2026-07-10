"""PASSWORD-002 — do_password syntax + wrong-password strings must match ROM byte-for-byte.

Two literal-fidelity divergences in `mud/commands/character.py:do_password`:

- Syntax line (ROM src/act_info.c:2889): `"Syntax: password <old> <new>.\n\r"` —
  the port dropped the trailing period.
- Wrong-password line (ROM src/act_info.c:2896): `"Wrong password.  Wait 10
  seconds.\n\r"` — ROM has TWO spaces after "password."; the port had one.

Assertions use exact `==` (not `in`/`strip`) so a whitespace-normalizing test
can't pass on a wrong byte.
"""

from __future__ import annotations

from mud.world import create_test_character


def _pc(room_vnum: int = 3001):
    ch = create_test_character("Secretkeeper", room_vnum=room_vnum)
    ch.is_npc = False
    ch.pcdata.pwd = "irrelevant-hash"
    return ch


def test_password_syntax_message_has_trailing_period():
    """ROM src/act_info.c:2889 — 'Syntax: password <old> <new>.' (trailing period)."""
    ch = _pc()
    # Missing second arg → syntax message (verify step not reached).
    assert do_password_call(ch, "onlyold") == "Syntax: password <old> <new>."


def test_password_wrong_password_message_has_two_spaces(monkeypatch):
    """ROM src/act_info.c:2896 — 'Wrong password.  Wait 10 seconds.' (two spaces)."""
    from mud.commands import character as character_mod

    monkeypatch.setattr(character_mod, "verify_password", lambda *a, **k: False)
    ch = _pc()
    assert character_mod.do_password(ch, "wrongpass newpass") == "Wrong password.  Wait 10 seconds."


def do_password_call(ch, args: str) -> str:
    from mud.commands import character as character_mod

    return character_mod.do_password(ch, args)
