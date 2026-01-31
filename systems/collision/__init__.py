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
- hazards: Hazard and laser beam collisions
- player_bullets: Player bullet collisions
- enemy_projectiles: Enemy projectile collisions
- friendly_projectiles: Friendly AI projectile collisions
- explosions: Grenades and missiles
"""

# Re-export helpers for direct access
from .helpers import (
    create_damage_number,
    bulk_remove,
    build_enemy_grid,
    build_block_grid,
)

# Re-export from split modules
from .hazards import (
    handle_hazard_enemy_collisions,
    handle_laser_beam_collisions,
)

from .player_bullets import (
    handle_dead_enemies,
    handle_player_bullet_offscreen,
    handle_player_bullet_enemy_collisions,
    handle_player_bullet_block_collisions,
)

from .enemy_projectiles import (
    handle_enemy_projectile_lifetime_offscreen,
    handle_enemy_projectile_block_collisions,
    handle_enemy_projectile_friendly_collisions,
    handle_enemy_projectile_decoy_collisions,
)

from .friendly_projectiles import (
    handle_friendly_projectile_offscreen_blocks_enemies,
)

from .explosions import (
    handle_grenade_explosion_damage,
    handle_missile_collisions,
)

# Re-export build_block_grid_cached from original module for backward compatibility
from ..collision_projectiles import build_block_grid_cached

__all__ = [
    # Helpers
    "create_damage_number",
    "bulk_remove",
    "build_enemy_grid",
    "build_block_grid",
    # Hazards
    "handle_hazard_enemy_collisions",
    "handle_laser_beam_collisions",
    # Player bullets
    "handle_dead_enemies",
    "handle_player_bullet_offscreen",
    "handle_player_bullet_enemy_collisions",
    "handle_player_bullet_block_collisions",
    # Enemy projectiles
    "handle_enemy_projectile_lifetime_offscreen",
    "handle_enemy_projectile_block_collisions",
    "handle_enemy_projectile_friendly_collisions",
    "handle_enemy_projectile_decoy_collisions",
    # Friendly projectiles
    "handle_friendly_projectile_offscreen_blocks_enemies",
    # Explosions
    "handle_grenade_explosion_damage",
    "handle_missile_collisions",
    # Backward compatibility
    "build_block_grid_cached",
]
