"""Hazard and laser beam collision handling.

Handles:
- Hazard damage to enemies (environmental damage)
- Player laser beam damage to enemies
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from ..collision_common import set_enemy_damage_flash
from ..spatial_grid import get_enemy_grid, SpatialGrid

if TYPE_CHECKING:
    from state import GameState


def _build_enemy_grid(state: "GameState", ctx: dict) -> SpatialGrid:
    """Build spatial grid containing all enemies."""
    width: int = ctx.get("width", 1920)
    height: int = ctx.get("height", 1080)
    frame_id: int = ctx.get("frame_id", -1)
    grid = get_enemy_grid(width, height, frame_id=frame_id)
    if len(grid._obj_cells) == 0 and state.enemies:
        grid.insert_all(state.enemies)
    return grid


def handle_hazard_enemy_collisions(state: "GameState", dt: float, ctx: dict) -> None:
    """Apply hazard damage to enemies that touch hazard zones."""
    lev = getattr(state, "level", None)
    hazards = lev.hazard_obstacles if lev else []
    for hazard in hazards:
        if not hazard.get("points") or len(hazard["points"]) < 3:
            continue
        hazard_damage = hazard.get("damage", 10)
        check = ctx.get("check_point_in_hazard")
        kill = ctx.get("kill_enemy")
        if not check or not kill:
            continue
        for enemy in state.enemies[:]:
            center = pygame.Vector2(enemy["rect"].center)
            if check(center, hazard["points"], hazard["bounding_rect"]):
                enemy["hp"] -= hazard_damage * dt
                set_enemy_damage_flash(enemy, ctx)
                if enemy["hp"] <= 0:
                    kill(enemy, state)


def handle_laser_beam_collisions(state: "GameState", dt: float, ctx: dict) -> None:
    """Handle laser beam collisions using spatial grid for O(n) performance."""
    line_rect = ctx.get("line_rect_intersection")
    kill = ctx.get("kill_enemy")
    if not line_rect or not kill:
        return
    
    if not state.laser_beams:
        return
    
    # Build enemy grid for spatial queries
    enemy_grid = _build_enemy_grid(state, ctx)
    
    beams_to_remove = []
    for beam in state.laser_beams:
        beam["timer"] = beam.get("timer", 0.1) - dt
        if beam["timer"] <= 0:
            beams_to_remove.append(beam)
            continue
        
        damage = beam.get("damage", 50) * dt * 60
        
        # Calculate beam bounding rect for spatial query
        start = beam["start"]
        end = beam["end"]
        min_x = min(start[0], end[0])
        max_x = max(start[0], end[0])
        min_y = min(start[1], end[1])
        max_y = max(start[1], end[1])
        # Add padding for enemy sizes
        beam_rect = pygame.Rect(min_x - 50, min_y - 50, max_x - min_x + 100, max_y - min_y + 100)
        
        # Query only nearby enemies using spatial grid
        nearby_enemies = enemy_grid.query(beam_rect)
        
        for enemy in nearby_enemies:
            if line_rect(start, end, enemy["rect"]):
                enemy["hp"] -= damage
                set_enemy_damage_flash(enemy, ctx)
                if enemy["hp"] <= 0:
                    kill(enemy, state)
    
    # Remove expired beams
    for beam in beams_to_remove:
        if beam in state.laser_beams:
            state.laser_beams.remove(beam)
