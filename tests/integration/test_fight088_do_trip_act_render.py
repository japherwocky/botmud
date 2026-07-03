"""FIGHT-088 — do_trip emits ROM's three act() lines and the failure damage(0) call.

ROM do_trip (src/fight.c:2733-2751):

    if (number_percent () < chance) {
        act ("{5$n trips you and you go down!{x", ch, NULL, victim, TO_VICT);
        act ("{5You trip $N and $N goes down!{x", ch, NULL, victim, TO_CHAR);
        act ("{5$n trips $N, sending $M to the ground.{x", ch, NULL, victim, TO_NOTVICT);
        ...
        damage (ch, victim, number_range (...), gsn_trip, DAM_BASH, TRUE);
    } else {
        damage (ch, victim, 0, gsn_trip, DAM_BASH, TRUE);   // <-- miss still hits combat
        WAIT_STATE (ch, skill_table[gsn_trip].beats * 2 / 3);
    }

The port returned a single baked ``f"You trip {name} and they go down!"`` (no
$N/$M PERS render, no room broadcast) and, on a miss, only set the wait — it
never called ``damage(0)``, so a cold trip miss didn't start the fight or emit
the miss combat message. This test locks the TO_NOTVICT $M render and the
failure fight-start via state, not message wording.
"""

from __future__ import annotations

import pytest

from mud.commands.combat import do_trip
from mud.models.constants import Position, Sex
from mud.utils import rng_mm
from mud.world import create_test_character, initialize_world

_ROOM = 3001


@pytest.fixture(autouse=True)
def _world():
    initialize_world("area/area.lst")


def _setup():
    char = create_test_character("Tripper", _ROOM)
    victim = create_test_character("Victim", _ROOM)
    char.is_npc = False
    char.skills["trip"] = 100
    victim.is_npc = True
    victim.sex = Sex.FEMALE
    victim.position = Position.STANDING
    victim.hit = 200
    victim.max_hit = 200
    char.fighting = victim  # target via char.fighting (no arg needed)
    victim.fighting = None
    return char, victim


def test_cold_trip_miss_starts_the_fight(monkeypatch: pytest.MonkeyPatch) -> None:
    # ROM src/fight.c:2749 — the failure branch calls damage(ch, victim, 0, ...),
    # which runs set_fighting. The pre-fix branch only set the wait, so the victim
    # never entered combat with the tripper.
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 100)  # guaranteed miss
    char, victim = _setup()
    do_trip(char, "")
    assert victim.fighting is char, "a cold trip miss must start the fight (ROM damage(0))"


def test_success_broadcasts_tonotvict_with_gendered_pronoun(monkeypatch: pytest.MonkeyPatch) -> None:
    # ROM TO_NOTVICT: "{5$n trips $N, sending $M to the ground.{x" — $M is the
    # victim's objective pronoun (him/her/it). A bystander in the room must receive
    # it with "her" rendered, not a literal "$M" or a baked "them".
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 0)  # guaranteed success
    char, victim = _setup()
    bystander = create_test_character("Onlooker", _ROOM)
    bystander.messages = []
    do_trip(char, "")
    assert any("sending her to the ground" in m for m in bystander.messages), bystander.messages
