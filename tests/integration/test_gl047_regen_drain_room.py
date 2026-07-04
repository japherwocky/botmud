"""GL-047 — regen in a negative-rate ("drain") room: UMIN allows drain + signed math.

ROM's `hit_gain`/`mana_gain`/`move_gain` (`src/update.c:149-370`) return
``UMIN (gain, ch->max_hit - ch->hit)`` — a plain ``min`` that can return a
**negative** value when the room's ``heal_rate``/``mana_rate`` is negative. A
drain room is fully representable: ``heal_rate``/``mana_rate`` are signed
``sh_int``, set via ``redit_heal``/``redit_mana`` (``atoi``, no lower bound) or
the signed ``fread_number`` area loader (``src/db.c:1180,1183``). The caller
``if (ch->hit < ch->max_hit) ch->hit += hit_gain(ch);`` (``:698``) then *drains*
HP by adding the negative return.

Two divergences the pre-fix port had:

1. **Clamp** — the port returned ``max(0, min(gain, deficit))``, clamping any
   drain to zero (no HP loss). ROM has no such ``max(0, …)``.
2. **Signed math** — once ``gain * heal_rate`` goes negative, every subsequent
   division (the ``/100`` rate multiply, the furniture ``/100``, the poison
   ``/4`` / plague ``/8`` / haste ``/2`` reductions) must truncate toward zero
   like C. The port used bare ``//`` (floor toward −∞), which is off-by-one on a
   negative dividend. Per AGENTS.md these are ``c_div`` sites.

Char-side regen twin of the GL-045/GL-046 update.c RNG/math sweep.
"""

from __future__ import annotations

from mud.game_loop import hit_gain, mana_gain, move_gain
from mud.models.character import AffectData, Character
from mud.models.constants import AffectFlag, Position, Sex
from mud.models.room import Room


def _drain_room(*, heal_rate: int = -100, mana_rate: int = -100) -> Room:
    room = Room(vnum=9595, name="Draining Vault", description="")
    room.people = []
    room.heal_rate = heal_rate
    room.mana_rate = mana_rate
    return room


def _npc(room: Room, *, level: int = 10, poison: bool = False) -> Character:
    ch = Character(
        name="drudge",
        is_npc=True,
        level=level,
        room=room,
        sex=int(Sex.NONE),
        position=int(Position.STANDING),
        default_pos=int(Position.STANDING),
    )
    ch.max_hit = ch.max_mana = ch.max_move = 100
    ch.hit = ch.mana = ch.move = 50
    if poison:
        ch.affected_by = int(AffectFlag.POISON)
        ch.affected = [
            AffectData(type="poison", level=10, duration=5, location=0, modifier=0, bitvector=int(AffectFlag.POISON))
        ]
    room.people.append(ch)
    return ch


def test_hit_gain_drains_in_negative_rate_room() -> None:
    """ROM :229 UMIN can return negative; the port must not clamp the drain to 0."""
    room = _drain_room(heal_rate=-100)
    mob = _npc(room)  # NPC lvl10 standing: gain 15 -> //2 = 7; *-100/100 = -7
    assert hit_gain(mob) == -7


def test_hit_gain_rate_multiply_truncates_toward_zero() -> None:
    """ROM :215 `gain * heal_rate / 100` truncates toward 0 (c_div), not floor (`//`)."""
    room = _drain_room(heal_rate=-55)
    mob = _npc(room)  # gain 7; 7*-55 = -385; c_div(-385,100) = -3 (floor // would give -4)
    assert hit_gain(mob) == -3


def test_hit_gain_post_rate_division_truncates_toward_zero() -> None:
    """ROM :221 poison `gain /= 4` truncates toward 0 on the negative drained gain."""
    room = _drain_room(heal_rate=-100)
    mob = _npc(room, poison=True)  # gain -7; poison c_div(-7,4) = -1 (floor // would give -2)
    assert hit_gain(mob) == -1


def test_mana_and_move_gain_drain_in_negative_rate_room() -> None:
    """mana_gain / move_gain share the same UMIN + signed-math contract."""
    room = _drain_room(heal_rate=-100, mana_rate=-100)
    mob = _npc(room)  # NPC standing: mana 15->//2=7 -> -7 ; move = level 10 -> -10
    assert mana_gain(mob) == -7
    assert move_gain(mob) == -10
