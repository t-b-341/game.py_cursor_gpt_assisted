"""
Data-driven enemy definitions. Unified lookup by type_id with caching.

Canonical source: config.enemy_data. This module re-exports templates and constants
and provides get_enemy_def() / clear_enemy_def_cache(). Each definition is the same
dict shape as ENEMY_TEMPLATES / BOSS_TEMPLATE for make_enemy_from_template.
Normalized fields used by callers: type_id, base_health, move_speed, sprite_id,
score_value, behavior_flags (frozenset).
"""
from __future__ import annotations

from typing import Any, Optional

from config.enemy_data import (
    ALLY_COLOR,
    ALLY_PROJECTILE_COLOR,
    BOSS_TEMPLATE,
    BASE_ENEMIES_PER_WAVE,
    ENEMY_FIRE_RATE_MULTIPLIER,
    ENEMY_HP_CAP,
    ENEMY_HP_SCALE_MULTIPLIER,
    ENEMY_SPAWN_MULTIPLIER,
    ENEMY_SPEED_SCALE_MULTIPLIER,
    ENEMY_TEMPLATES,
    FRIENDLY_AI_TEMPLATES,
    MAX_ENEMIES_PER_WAVE,
    QUEEN_FIXED_HP,
    QUEEN_SPEED_MULTIPLIER,
)

_ENEMY_DEF_CACHE: dict[str, Optional[dict[str, Any]]] = {}


def get_enemy_def(type_id: str) -> Optional[dict[str, Any]]:
    """Return the enemy definition for type_id, or None if unknown. Results are cached."""
    if type_id in _ENEMY_DEF_CACHE:
        return _ENEMY_DEF_CACHE[type_id]
    template = None
    if type_id == BOSS_TEMPLATE.get("type", "boss"):
        template = BOSS_TEMPLATE.copy()
    else:
        for t in ENEMY_TEMPLATES:
            if t.get("type") == type_id:
                template = t.copy()
                break
    if template is not None:
        # Normalized fields for data-driven use
        template.setdefault("type_id", template.get("type", type_id))
        template.setdefault("base_health", template.get("hp", template.get("max_hp", 0)))
        template.setdefault("move_speed", template.get("speed", 0))
        template.setdefault("sprite_id", type_id)
        template.setdefault("score_value", 0)
        flags = set()
        if template.get("is_suicide"):
            flags.add("suicider")
        if template.get("is_ambient"):
            flags.add("ambient")
        if template.get("is_boss"):
            flags.add("boss")
        if template.get("is_spawner"):
            flags.add("spawner")
        template["behavior_flags"] = frozenset(flags)
    _ENEMY_DEF_CACHE[type_id] = template
    return template


def clear_enemy_def_cache() -> None:
    """Clear the cache (e.g. for tests or hot-reload)."""
    _ENEMY_DEF_CACHE.clear()
