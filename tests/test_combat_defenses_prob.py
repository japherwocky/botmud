from mud.commands import process_command
from mud.models.constants import DamageType, OffFlag
from mud.world import create_test_character, initialize_world


def setup_function(_):
    initialize_world("area/area.lst")


def _setup_pair():
    attacker = create_test_character("Attacker", 3001)
    victim = create_test_character("Victim", 3001)
    victim.is_npc = True  # Ensure victim is NPC to avoid PK restrictions
    # HANDLER-008: get_skill ignores an NPC's skills dict and uses ROM's formula
    # (parry/dodge = level*2 gated by OFF_PARRY/OFF_DODGE; shield block = 10+2*level).
    # Give the mob a level so the formula yields positive chances; per-test OFF
    # flags below select which defenses can fire. Equalize attacker/victim level so
    # the check_* level-diff modifier (victim.level - attacker.level) is 0 — otherwise
    # a positive diff would grant parry a chance even with no OFF_PARRY (ROM adds the
    # diff after the skill term, src/fight.c), stealing the win from dodge.
    victim.level = 10
    attacker.level = 10
    attacker.hitroll = 100
    attacker.damroll = 3
    attacker.dam_type = int(DamageType.BASH)
    victim.armor = [0, 0, 0, 0]
    victim.hit = 50
    return attacker, victim


def deliver_kill(char, target: str) -> str:
    """Run `kill <target>` and return the attacker-facing combat line.

    INV-001/SINGLE-DELIVERY: do_kill returns "" (ROM's void do_kill); the
    defense line (e.g. "<v> parries your attack.") is pushed to the attacker by
    check_parry/dodge/shield_block via _push_message, landing in char.messages
    for a connection-less test character. Returns the first line pushed here.
    """
    before = len(char.messages)
    process_command(char, f"kill {target}")
    pushed = char.messages[before:]
    return pushed[0] if pushed else ""


def test_parry_triggers_before_dodge_and_shield_block(monkeypatch):
    from mud.utils import rng_mm

    attacker, victim = _setup_pair()
    # HANDLER-008: all three defenses enabled via ROM's NPC formula so the
    # priority order (parry checked before dodge before shield block) is what
    # selects the winner. At level 10: parry/dodge get_skill=20, shield=30.
    victim.off_flags = int(OffFlag.PARRY | OffFlag.DODGE)
    # Must have shield equipped for shield block to work
    victim.has_shield_equipped = True
    # Ensure percent roll always hits the threshold
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 1)
    out = deliver_kill(attacker, "victim")
    assert out == "Victim parries your attack."


def test_parry_triggers_when_no_shield(monkeypatch):
    from mud.utils import rng_mm

    attacker, victim = _setup_pair()
    # HANDLER-008: OFF_PARRY → get_skill=level*2=20 → chance = 20/2 + leveldiff.
    victim.off_flags = int(OffFlag.PARRY)
    victim.has_weapon_equipped = True
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 1)
    out = deliver_kill(attacker, "victim")
    assert out == "Victim parries your attack."


def test_dodge_triggers_when_no_shield_or_parry(monkeypatch):
    from mud.utils import rng_mm

    attacker, victim = _setup_pair()
    # HANDLER-008: OFF_DODGE only (no OFF_PARRY, no shield) so dodge is the sole
    # defense that can fire → get_skill=level*2=20 → chance = 20/2 + leveldiff.
    victim.off_flags = int(OffFlag.DODGE)
    monkeypatch.setattr(rng_mm, "number_percent", lambda: 1)
    out = deliver_kill(attacker, "victim")
    assert out == "Victim dodges your attack."
