"""Faithful port of ROM ``get_skill`` (src/handler.c:346-448).

ROM computes a character's effective percentage in a skill/spell, combining:

* PCs — the learned percent, gated to 0 while ``level < skill_table[sn].skill_level[class]``.
* NPCs — a per-skill formula default (mobs have no learned table), keyed off the
  mob's ACT/OFF flags for the offensive/defensive skills.
* Both — a daze reduction (``skill/2`` for spells, ``2*skill/3`` for skills) and,
  for PCs, a drunkenness reduction (``9*skill/10`` when ``COND_DRUNK > 10``).
* A final ``URANGE(0, skill, 100)`` clamp.

The Python engine had no unified equivalent; skill percents were fetched ad-hoc
from the ``skills`` dict (0 for mobs), so every NPC offensive/defensive skill
under-reported and the daze/drunk modifiers were absent everywhere. HANDLER-008.

Integer math: the NPC "third attack" branch is ``4*level - 40`` — negative below
level 10 — so the daze/drunk divisions use ``c_div`` (C truncation toward zero),
matching ROM before the ``URANGE`` clamp folds negatives to 0.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mud.math.c_compat import c_div
from mud.models.constants import ActFlag, OffFlag

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mud.models.character import Character

# COND_DRUNK index into Character.condition ([drunk, full, thirst, hunger]).
_COND_DRUNK = 0

# ROM weapon skills (src/handler.c:432-438) — get_skill's NPC weapon-skill branch.
_WEAPON_SKILLS = frozenset({"sword", "dagger", "spear", "mace", "axe", "flail", "whip", "polearm"})


def _learned_percent(ch: Character, name: str) -> int:
    skills = getattr(ch, "skills", {}) or {}
    if not isinstance(skills, dict):
        return 0
    try:
        return int(skills.get(name, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _pc_skill(ch: Character, skill, name: str, level: int) -> int:
    """PC path: ``level < skill_level[class] → 0`` else ``learned[sn]``."""
    if skill is not None:
        levels = getattr(skill, "levels", None)
        ch_class = int(getattr(ch, "ch_class", 0) or 0)
        if isinstance(levels, list | tuple) and 0 <= ch_class < len(levels):
            if level < int(levels[ch_class]):
                return 0
    return _learned_percent(ch, name)


def _npc_skill(ch: Character, name: str, level: int, is_spell: bool) -> int:
    """NPC path: the ROM formula dispatch (src/handler.c:373-432)."""
    act = int(getattr(ch, "act", 0) or 0)
    off = int(getattr(ch, "off_flags", 0) or 0)

    if is_spell:
        return 40 + 2 * level
    if name in ("sneak", "hide"):
        return level * 2 + 20
    if (name == "dodge" and off & int(OffFlag.DODGE)) or (name == "parry" and off & int(OffFlag.PARRY)):
        return level * 2
    if name == "shield block":
        return 10 + 2 * level
    if name == "second attack" and (act & int(ActFlag.WARRIOR) or act & int(ActFlag.THIEF)):
        return 10 + 3 * level
    if name == "third attack" and act & int(ActFlag.WARRIOR):
        return 4 * level - 40
    if name == "hand to hand":
        return 40 + 2 * level
    if name == "trip" and off & int(OffFlag.TRIP):
        return 10 + 3 * level
    if name == "bash" and off & int(OffFlag.BASH):
        return 10 + 3 * level
    if name == "disarm" and (off & int(OffFlag.DISARM) or act & int(ActFlag.WARRIOR) or act & int(ActFlag.THIEF)):
        return 20 + 3 * level
    if name == "berserk" and off & int(OffFlag.BERSERK):
        return 3 * level
    if name == "kick":
        return 10 + 3 * level
    if name == "backstab" and act & int(ActFlag.THIEF):
        return 20 + 2 * level
    if name in ("rescue", "recall"):
        return 40 + level
    if name in _WEAPON_SKILLS:
        return 40 + c_div(5 * level, 2)
    return 0


def get_skill(ch: Character, name: str) -> int:
    """Return ``ch``'s effective percent in skill/spell ``name`` (ROM get_skill).

    ``name`` is the skill's canonical name (ROM keys by ``gsn``; the Python
    registry keys by name). Unknown names resolve to 0, matching ROM's ``else``
    fall-through. The ``sn == -1`` level-based shorthand is not modelled — no
    Python caller needs it.
    """
    # Local import avoids a module-load cycle (registry imports handlers, which
    # imports this module).
    from mud.skills.registry import skill_registry

    key = name.lower() if isinstance(name, str) else name
    skill = None
    if isinstance(key, str):
        try:
            skill = skill_registry.get(key)
        except KeyError:
            skill = None
    is_spell = bool(skill is not None and getattr(skill, "type", "") == "spell")

    level = int(getattr(ch, "level", 0) or 0)
    is_npc = bool(getattr(ch, "is_npc", False))

    if is_npc:
        value = _npc_skill(ch, key, level, is_spell)
    else:
        value = _pc_skill(ch, skill, key, level)

    # ROM src/handler.c:434-439 — daze reduction (both PC and NPC).
    if int(getattr(ch, "daze", 0) or 0) > 0:
        if is_spell:
            value = c_div(value, 2)
        else:
            value = c_div(2 * value, 3)

    # ROM src/handler.c:441-442 — drunkenness reduction (PCs only). The condition
    # array lives on pcdata (ch->pcdata->condition[COND_DRUNK]).
    if not is_npc:
        pcdata = getattr(ch, "pcdata", None)
        condition = getattr(pcdata, "condition", None)
        drunk = 0
        if isinstance(condition, list | tuple) and len(condition) > _COND_DRUNK:
            try:
                drunk = int(condition[_COND_DRUNK])
            except (TypeError, ValueError):
                drunk = 0
        if drunk > 10:
            value = c_div(9 * value, 10)

    # ROM src/handler.c:444 — URANGE(0, skill, 100).
    return max(0, min(100, value))
