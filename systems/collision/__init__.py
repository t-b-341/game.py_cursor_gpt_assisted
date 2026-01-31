"""Collision detection package for projectiles, beams, hazards, and explosives.

This package handles all projectile-based collision detection:
- Player bullets vs enemies, blocks
- Enemy projectiles vs player, friendlies, blocks
- Friendly projectiles vs enemies, blocks
- Grenades, missiles, explosions
- Hazards and laser beams

Performance optimizations:
- Spatial grid partitioning for O(n) collision checks
- Filter-based list updates avoid O(n²) removal
- Bulk processing where possible
- Frame-cached grids to avoid rebuilding

Modules:
- helpers: Common helper functions (damage numbers, bulk remove, grid builders)
- projectiles: Main collision handling (re-exports from collision_projectiles)
"""

# Re-export helpers for direct access
from .helpers import (
    create_damage_number,
    bulk_remove,
    build_enemy_grid,
    build_block_grid,
)

# Re-export all collision functions from the main module
from ..collision_projectiles import (
    handle_hazard_enemy_collisions,
    handle_laser_beam_collisions,
    handle_dead_enemies,
    handle_player_bullet_offscreen,
    handle_player_bullet_enemy_collisions,
    handle_player_bullet_block_collisions,
    handle_enemy_projectile_lifetime_offscreen,
    handle_enemy_projectile_block_collisions,
    handle_enemy_projectile_friendly_collisions,
    handle_friendly_projectile_offscreen_blocks_enemies,
    handle_grenade_explosion_damage,
    handle_missile_collisions,
    build_block_grid_cached,
)

__all__ = [
    # Helpers
    "create_damage_number",
    "bulk_remove",
    "build_enemy_grid",
    "build_block_grid",
    # Collision handlers
    "handle_hazard_enemy_collisions",
    "handle_laser_beam_collisions",
    "handle_dead_enemies",
    "handle_player_bullet_offscreen",
    "handle_player_bullet_enemy_collisions",
    "handle_player_bullet_block_collisions",
    "handle_enemy_projectile_lifetime_offscreen",
    "handle_enemy_projectile_block_collisions",
    "handle_enemy_projectile_friendly_collisions",
    "handle_friendly_projectile_offscreen_blocks_enemies",
    "handle_grenade_explosion_damage",
    "handle_missile_collisions",
    "build_block_grid_cached",
]
