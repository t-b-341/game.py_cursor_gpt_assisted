"""Hazard and laser-beam collisions against enemies.

Moved verbatim from systems/collision_projectiles.py - this is the implementation
that has actually been running. See AGENTS.md §10.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from ..collision_common import record_enemy_hit, set_enemy_damage_flash
from .helpers import (
    build_enemy_grid as _build_enemy_grid,
)

if TYPE_CHECKING:
    from state import GameState



def handle_hazard_enemy_collisions(state, dt: float, ctx: dict) -> None:
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


def handle_laser_beam_collisions(state, dt: float, ctx: dict) -> None:
    """Handle laser beam collisions using spatial grid for O(n) performance.
    
    Fair gameplay: Player laser beams cannot hit off-screen enemies (player can't see them).
    """
    line_rect = ctx.get("line_rect_intersection")
    kill = ctx.get("kill_enemy")
    if not line_rect or not kill:
        return
    
    if not state.laser_beams:
        return
    
    # Get camera for visibility check (fair gameplay)
    from ..camera import get_camera
    camera = get_camera()
    
    # Build enemy grid for spatial queries
    enemy_grid = _build_enemy_grid(state, ctx)
    
    beams_to_remove = set()
    for beam in state.laser_beams:
        beam["timer"] = beam.get("timer", 0.1) - dt
        if beam["timer"] <= 0:
            beams_to_remove.add(id(beam))
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
        nearby_enemies = enemy_grid.query_rect(beam_rect)
        
        for enemy in nearby_enemies:
            # Fair gameplay: Skip off-screen enemies (player can't see them)
            if camera and not camera.is_visible(enemy["rect"]):
                continue
            if line_rect(start, end, enemy["rect"]):
                enemy["hp"] -= damage
                record_enemy_hit(state, ctx, enemy, int(damage), enemy["hp"], enemy["hp"] <= 0)
                set_enemy_damage_flash(enemy, ctx)
                if enemy["hp"] <= 0:
                    kill(enemy, state)
    
    # O(n) bulk removal instead of O(n²) .remove() in loop
    if beams_to_remove:
        state.laser_beams[:] = [b for b in state.laser_beams if id(b) not in beams_to_remove]
