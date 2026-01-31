"""World rendering - backward compatibility re-exports.

This module has been refactored into the rendering.world package:
- rendering/world/textures.py - Wall texture functions
- rendering/world/projectiles.py - Projectile/effect/beam rendering
- rendering/world/terrain.py - Terrain blocks, hazards, health zones
- rendering/world/entities.py - Pickups, allies, enemies, player
- rendering/world/__init__.py - Main entry points

All original exports remain available for backward compatibility.
"""
from __future__ import annotations

# Re-export everything from the world package
from .world import (
    # Main render functions
    render_background,
    render_entities,
    render_projectiles,
    render_gameplay,
    # Texture functions
    draw_silver_wall_texture,
    draw_cracked_brick_wall_texture,
    # Projectile functions
    draw_projectile,
    _get_cached_projectile_surface,
    # Cache clearing
    clear_all_caches,
    clear_texture_cache,
    clear_projectile_cache,
    clear_terrain_cache,
)

# Legacy internal function names (with underscores)
from .world.terrain import draw_terrain as _draw_terrain
from .world.entities import (
    draw_pickups as _draw_pickups,
    draw_allies_and_enemies as _draw_allies_and_enemies,
    draw_player as _draw_player,
)
from .world.projectiles import (
    draw_projectiles as _draw_projectiles,
    draw_effects as _draw_effects,
    draw_beams as _draw_beams,
)

__all__ = [
    # Main render functions
    "render_background",
    "render_entities",
    "render_projectiles",
    "render_gameplay",
    # Texture functions
    "draw_silver_wall_texture",
    "draw_cracked_brick_wall_texture",
    # Projectile functions
    "draw_projectile",
    "_get_cached_projectile_surface",
    # Cache clearing
    "clear_all_caches",
    "clear_texture_cache",
    "clear_projectile_cache",
    "clear_terrain_cache",
    # Legacy internal functions
    "_draw_terrain",
    "_draw_pickups",
    "_draw_allies_and_enemies",
    "_draw_player",
    "_draw_projectiles",
    "_draw_effects",
    "_draw_beams",
]
