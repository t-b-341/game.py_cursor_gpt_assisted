"""Collision detection and damage: player bullets, enemy projectiles, pickups, hazards, beams, explosives.

Delegates to collision_player, collision_projectiles, and collision_pickups.
Uses LevelState from state.level; geometry and callables come from state.level_context.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from . import collision_pickups
from . import collision_player
from . import collision_projectiles
from .perf_timing import perf_timer

if TYPE_CHECKING:
    from state import GameState


def update(state: "GameState", dt: float) -> None:
    """Process all collisions and apply damage. Called from gameplay."""
    with perf_timer("collision_system"):
        ctx = getattr(state, "level_context", None)
        if ctx is None:
            return
        if state.player_rect is None:
            return
        
        # Increment frame counter for spatial grid caching
        # This ensures grids are only rebuilt once per collision update phase
        frame_id = getattr(state, "_collision_frame_id", 0) + 1
        state._collision_frame_id = frame_id
        ctx["frame_id"] = frame_id
        
        # Pre-build block grid once for all collision checks this frame
        # This avoids repeated _build_block_grid calls (was 3x per frame)
        block_grid = collision_projectiles.build_block_grid_cached(state, ctx)
        ctx["_block_grid"] = block_grid

        collision_projectiles.handle_hazard_enemy_collisions(state, dt, ctx)
        collision_projectiles.handle_laser_beam_collisions(state, dt, ctx)
        collision_player.handle_enemy_laser_beam_collisions(state, dt, ctx)
        collision_projectiles.handle_dead_enemies(state, ctx)
        collision_projectiles.handle_player_bullet_offscreen(state, ctx)
        collision_projectiles.handle_player_bullet_enemy_collisions(state, ctx)
        collision_projectiles.handle_player_bullet_block_collisions(state, dt, ctx)
        collision_projectiles.handle_enemy_projectile_lifetime_offscreen(state, ctx)
        collision_projectiles.handle_enemy_projectile_block_collisions(state, ctx)
        collision_player.handle_enemy_projectile_player_collisions(state, ctx)
        collision_projectiles.handle_enemy_projectile_friendly_collisions(state, ctx)
        collision_projectiles.handle_enemy_projectile_decoy_collisions(state, ctx)
        collision_player.handle_teleporter_player(state, ctx)
        collision_pickups.handle_pickup_player_collisions(state, ctx)
        collision_player.handle_health_zone_player_dt(state, dt, ctx)
        collision_projectiles.handle_friendly_projectile_offscreen_blocks_enemies(state, ctx)
        collision_projectiles.handle_grenade_explosion_damage(state, dt, ctx)
        collision_projectiles.handle_missile_collisions(state, ctx)
