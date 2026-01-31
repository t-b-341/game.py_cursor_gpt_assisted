"""
Data-driven projectile and weapon definitions. Unified lookup by type_id with caching.

Canonical source for WEAPON_CONFIGS, WEAPON_NAMES, WEAPON_DISPLAY_COLORS, WEAPON_UNLOCK_ORDER.
Each projectile definition provides: type_id, speed, damage, lifetime, sprite_id (optional),
flags. Player defs carry weapon-style fields so spawn logic uses one canonical source.
"""
from __future__ import annotations

from typing import Any, Optional

# ----------------------------
# Weapon config (canonical; config_weapons.py is a compatibility shim)
# ----------------------------
WEAPON_CONFIGS: dict[str, dict[str, Any]] = {
    "basic": {
        "damage_multiplier": 1.0,
        "size_multiplier": 1.0,
        "speed_multiplier": 1.0,
        "cooldown_multiplier": 1.0,
        "spread_angle_deg": 30.0,
        "num_projectiles": 3,
        "color": (10, 200, 200),
        "explosion_radius": 0.0,
        "max_bounces": 0,
        "is_rocket": False,
    },
    "triple": {
        "damage_multiplier": 1.0,
        "size_multiplier": 3.0,
        "speed_multiplier": 1.0,
        "cooldown_multiplier": 1.0,
        "spread_angle_deg": 30.0,
        "num_projectiles": 3,
        "color": (255, 105, 180),
        "explosion_radius": 0.0,
        "max_bounces": 0,
        "is_rocket": False,
    },
    "giant": {
        "damage_multiplier": 1.0,
        "size_multiplier": 10.0,
        "speed_multiplier": 1.0,
        "cooldown_multiplier": 1.0,
        "spread_angle_deg": 0.0,
        "num_projectiles": 1,
        "color": (10, 200, 200),
        "explosion_radius": 0.0,
        "max_bounces": 0,
        "is_rocket": False,
    },
    "laser": {
        "damage_multiplier": 1.0,
        "size_multiplier": 1.0,
        "speed_multiplier": 1.0,
        "cooldown_multiplier": 1.0,
        "spread_angle_deg": 0.0,
        "num_projectiles": 0,
        "color": (255, 50, 50),
        "explosion_radius": 0.0,
        "max_bounces": 0,
        "is_rocket": False,
    },
}

WEAPON_NAMES: dict[str, str] = {
    "giant": "GIANT BULLETS",
    "triple": "TRIPLE SHOT",
    "laser": "LASER BEAM",
    "basic": "BASIC FIRE",
}

WEAPON_DISPLAY_COLORS: dict[str, tuple[int, int, int]] = {
    "giant": (255, 200, 0),
    "triple": (255, 105, 180),
    "laser": (255, 50, 50),
    "basic": (200, 200, 200),
}

WEAPON_UNLOCK_ORDER: dict[int, str] = {
    1: "giant",
    2: "giant",
}

_PROJECTILE_DEF_CACHE: dict[str, Optional[dict[str, Any]]] = {}


def get_projectile_def(type_id: str) -> Optional[dict[str, Any]]:
    """Return the projectile definition for type_id, or None if unknown. Results are cached."""
    if type_id in _PROJECTILE_DEF_CACHE:
        return _PROJECTILE_DEF_CACHE[type_id]

    build = _BUILDERS.get(type_id)
    if build is None:
        _PROJECTILE_DEF_CACHE[type_id] = None
        return None

    out = build()
    _PROJECTILE_DEF_CACHE[type_id] = out
    return out


def _build_player_def(weapon_key: str) -> dict[str, Any]:
    from config.balance import (
        player_bullet_damage,
        player_bullet_size,
        player_bullet_speed,
        player_bullets_color,
    )

    cfg = WEAPON_CONFIGS.get(weapon_key, WEAPON_CONFIGS["basic"])
    return {
        "type_id": f"player_{weapon_key}",
        "speed": player_bullet_speed * cfg["speed_multiplier"],
        "damage": int(player_bullet_damage * cfg["damage_multiplier"]),
        "lifetime": None,
        "sprite_id": None,
        "flags": frozenset(),
        "size": tuple(player_bullet_size),
        "color": cfg.get("color", player_bullets_color),
        "damage_multiplier": cfg["damage_multiplier"],
        "size_multiplier": cfg["size_multiplier"],
        "speed_multiplier": cfg["speed_multiplier"],
        "num_projectiles": cfg["num_projectiles"],
        "spread_angle_deg": cfg["spread_angle_deg"],
        "explosion_radius": cfg["explosion_radius"],
        "max_bounces": cfg["max_bounces"],
        "is_rocket": cfg["is_rocket"],
    }


def _build_enemy_default() -> dict[str, Any]:
    from config.balance import (
        ENEMY_PROJECTILE_DAMAGE,
        ENEMY_PROJECTILES_COLOR,
        ENEMY_PROJECTILE_SIZE,
    )

    return {
        "type_id": "enemy_default",
        "speed": 0,  # Per-enemy; this is fallback only
        "damage": ENEMY_PROJECTILE_DAMAGE,
        "lifetime": None,
        "sprite_id": None,
        "flags": frozenset(),
        "size": tuple(ENEMY_PROJECTILE_SIZE),
        "color": ENEMY_PROJECTILES_COLOR,
    }


_BUILDERS: dict[str, Any] = {
    "player_basic": lambda: _build_player_def("basic"),
    "player_triple": lambda: _build_player_def("triple"),
    "player_giant": lambda: _build_player_def("giant"),
    "enemy_default": _build_enemy_default,
}


def clear_projectile_def_cache() -> None:
    """Clear the cache (e.g. for tests or hot-reload)."""
    _PROJECTILE_DEF_CACHE.clear()
