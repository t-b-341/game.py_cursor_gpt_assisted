"""
Collision and push movement systems for player and enemies.

This module handles solid collision detection and block pushing mechanics,
separated from higher-level movement logic.

Optimizations:
- Spatial grid for enemy-block collision (O(1) average instead of O(n))
- Frame-based caching to avoid rebuilding grids
"""
from __future__ import annotations
from typing import TYPE_CHECKING

import pygame

from geometry_utils import can_move_rect, clamp_rect_to_screen
from hazards import check_point_in_hazard
from .spatial_grid import SpatialGrid

if TYPE_CHECKING:
    from state import GameState
    from level_state import LevelState


# Module-level spatial grid for enemy-block collisions
_enemy_block_grid: SpatialGrid | None = None
_enemy_block_grid_frame: int = -1  # Frame ID when grid was built
_enemy_block_grid_level_id: int = -1  # Level ID to detect level changes


def _get_enemy_block_grid(level: "LevelState", state: "GameState") -> SpatialGrid:
    """Get or rebuild the spatial grid for enemy-block collisions.
    
    Grid is rebuilt once per frame or when level changes.
    """
    global _enemy_block_grid, _enemy_block_grid_frame, _enemy_block_grid_level_id
    
    frame_id = getattr(state, "_collision_frame_id", 0)
    level_id = id(level)
    
    # Check if we can reuse the cached grid
    if (_enemy_block_grid is not None and 
        _enemy_block_grid_frame == frame_id and 
        _enemy_block_grid_level_id == level_id):
        return _enemy_block_grid
    
    # Rebuild grid
    width = getattr(level, "width", 1920)
    height = getattr(level, "height", 1080)
    
    if _enemy_block_grid is None:
        _enemy_block_grid = SpatialGrid(width, height, cell_size=128)
    else:
        _enemy_block_grid.clear()
    
    # Insert all collidable blocks
    for b in level.static_blocks:
        if b.get("rect"):
            _enemy_block_grid.insert(b, b["rect"])
    
    for b in level.destructible_blocks:
        if b.get("rect"):
            _enemy_block_grid.insert(b, b["rect"])
    
    for b in level.moveable_blocks:
        if b.get("rect"):
            _enemy_block_grid.insert(b, b["rect"])
    
    for gb in level.giant_blocks:
        if gb.get("rect"):
            _enemy_block_grid.insert(gb, gb["rect"])
    
    for sgb in level.super_giant_blocks:
        if sgb.get("rect"):
            _enemy_block_grid.insert(sgb, sgb["rect"])
    
    for tb in level.trapezoid_blocks:
        br = tb.get("bounding_rect", tb.get("rect"))
        if br:
            _enemy_block_grid.insert(tb, br)
    
    for tr in level.triangle_blocks:
        br = tr.get("bounding_rect", tr.get("rect"))
        if br:
            _enemy_block_grid.insert(tr, br)
    
    # Insert pickups (enemies avoid these)
    for pickup in state.pickups:
        if pickup.get("rect"):
            _enemy_block_grid.insert(pickup, pickup["rect"])
    
    # Insert health zone if present
    if level.moving_health_zone and level.moving_health_zone.get("rect"):
        _enemy_block_grid.insert(level.moving_health_zone, level.moving_health_zone["rect"])
    
    _enemy_block_grid_frame = frame_id
    _enemy_block_grid_level_id = level_id
    
    return _enemy_block_grid


def _check_player_collision_with_block(
    player_rect: pygame.Rect,
    level: "LevelState",
) -> tuple[dict | None, bool]:
    """
    Check if player collides with any block in the level.
    
    Returns:
        (hit_block, is_unpushable): The block that was hit (or None), and whether it's unpushable
    """
    # Check static blocks
    for b in level.static_blocks:
        if player_rect.colliderect(b["rect"]):
            return b, False
    
    # Check destructible blocks
    for b in level.destructible_blocks:
        if player_rect.colliderect(b["rect"]):
            return b, False
    
    # Check moveable blocks
    for b in level.moveable_blocks:
        if player_rect.colliderect(b["rect"]):
            return b, False
    
    # Check trapezoid blocks (with point-in-polygon for accuracy)
    for tb in level.trapezoid_blocks:
        if player_rect.colliderect(tb.get("bounding_rect", tb.get("rect"))):
            player_center = pygame.Vector2(player_rect.center)
            if "points" in tb and len(tb["points"]) >= 3:
                trap_points = [
                    pygame.Vector2(p[0], p[1]) if isinstance(p, (tuple, list)) and len(p) >= 2
                    else pygame.Vector2(p.x, p.y) if hasattr(p, 'x')
                    else p
                    for p in tb["points"]
                ]
                if check_point_in_hazard(player_center, trap_points, tb.get("bounding_rect", tb.get("rect"))):
                    return tb, False
            else:
                if player_rect.colliderect(tb["rect"]):
                    return tb, False
    
    # Check triangle blocks
    for tr in level.triangle_blocks:
        if player_rect.colliderect(tr["rect"]):
            return tr, False
    
    # Check hazard obstacles (unpushable)
    for hazard in level.hazard_obstacles:
        if hazard.get("points") and len(hazard["points"]) > 2:
            player_center = pygame.Vector2(player_rect.center)
            if check_point_in_hazard(player_center, hazard["points"], hazard["bounding_rect"]):
                return hazard, True  # Hazards are unmovable
    
    # Check giant blocks (unpushable)
    for gb in level.giant_blocks:
        if player_rect.colliderect(gb["rect"]):
            return gb, True
    
    # Check super giant blocks (unpushable)
    for sgb in level.super_giant_blocks:
        if player_rect.colliderect(sgb["rect"]):
            return sgb, True
    
    return None, False


def _check_enemy_collision(
    enemy_rect: pygame.Rect,
    level: "LevelState",
    state: "GameState",
) -> bool:
    """
    Check if enemy collides with any solid object.
    
    Uses spatial grid for O(1) average case instead of O(n) linear scan.
    
    Returns:
        True if collision detected, False otherwise
    """
    # Use spatial grid for fast collision checking
    grid = _get_enemy_block_grid(level, state)
    
    # Query only objects in nearby cells
    for obj in grid.query_rect(enemy_rect):
        rect = obj.get("rect") if isinstance(obj, dict) else getattr(obj, "rect", None)
        if rect is None:
            # Trapezoid/triangle blocks may have bounding_rect
            rect = obj.get("bounding_rect") if isinstance(obj, dict) else getattr(obj, "bounding_rect", None)
        if rect and enemy_rect.colliderect(rect):
            return True
    
    # Check player
    if state.player_rect is not None and enemy_rect.colliderect(state.player_rect):
        return True
    
    # Check teleporter pads (usually small list, no grid needed)
    for pad in state.teleporter_pads:
        if enemy_rect.colliderect(pad["rect"]):
            return True
    
    # Check friendly AI (skip self) - usually small list
    for f in state.friendly_ai:
        if f["rect"] is enemy_rect:
            continue
        if f.get("hp", 1) > 0 and enemy_rect.colliderect(f["rect"]):
            return True
    
    # Check other enemies (prevent stacking)
    # This is O(n) per enemy = O(n^2) total, but enemies are already in a list
    # For large enemy counts, could use enemy grid, but typically < 50 enemies
    for other_e in state.enemies:
        if other_e["rect"] is not enemy_rect and enemy_rect.colliderect(other_e["rect"]):
            return True
    
    return False


def _try_push_block(
    hit_block: dict,
    axis_dx: int,
    axis_dy: int,
    all_collision_rects: list[pygame.Rect],
) -> bool:
    """
    Try to push a block in the given direction.
    
    Returns:
        True if block was pushed, False if it couldn't move
    """
    hit_rect = hit_block["rect"]
    other_rects = [r for r in all_collision_rects if r is not hit_rect]
    
    if can_move_rect(hit_rect, axis_dx, axis_dy, other_rects):
        hit_rect.x += axis_dx
        hit_rect.y += axis_dy
        # Update bounding_rect for trapezoid/triangle blocks
        if "bounding_rect" in hit_block:
            hit_block["bounding_rect"].x = hit_rect.x
            hit_block["bounding_rect"].y = hit_rect.y
        return True
    return False


def _apply_player_axis_movement(
    player_rect: pygame.Rect,
    axis_dx: int,
    axis_dy: int,
    level: "LevelState",
) -> bool:
    """
    Apply movement along one axis for the player, handling collisions and pushing.
    
    Returns:
        True if movement was successful, False if blocked
    """
    if axis_dx == 0 and axis_dy == 0:
        return True
    
    # Move player
    player_rect.x += axis_dx
    player_rect.y += axis_dy
    
    # Check for collision
    hit_block, is_unpushable = _check_player_collision_with_block(player_rect, level)
    
    if hit_block is None:
        return True  # No collision, movement successful
    
    # If unpushable, revert movement
    if is_unpushable:
        player_rect.x -= axis_dx
        player_rect.y -= axis_dy
        return False
    
    # Try to push the block
    block_list = level.static_blocks
    block_rects = [b["rect"] for b in block_list]
    destructible_rects = [b["rect"] for b in level.destructible_blocks]
    moveable_destructible_rects = [b["rect"] for b in level.moveable_blocks]
    trapezoid_rects = [tb["rect"] for tb in level.trapezoid_blocks]
    triangle_rects = [tr["rect"] for tr in level.triangle_blocks]
    giant_block_rects = [gb["rect"] for gb in level.giant_blocks]
    super_giant_block_rects = [sgb["rect"] for sgb in level.super_giant_blocks]
    all_collision_rects = (
        block_rects + destructible_rects + moveable_destructible_rects +
        trapezoid_rects + triangle_rects + giant_block_rects + super_giant_block_rects
    )
    
    if _try_push_block(hit_block, axis_dx, axis_dy, all_collision_rects):
        return True  # Block was pushed, movement successful
    else:
        # Block couldn't be pushed, revert player movement
        player_rect.x -= axis_dx
        player_rect.y -= axis_dy
        return False


def _apply_enemy_axis_movement(
    enemy_rect: pygame.Rect,
    axis_dx: int,
    axis_dy: int,
    level: "LevelState",
    state: "GameState",
) -> bool:
    """
    Apply movement along one axis for an enemy, handling collisions.
    
    Returns:
        True if movement was successful, False if blocked
    """
    if axis_dx == 0 and axis_dy == 0:
        return True
    
    # Move enemy
    enemy_rect.x += axis_dx
    enemy_rect.y += axis_dy
    
    # Check for collision
    if _check_enemy_collision(enemy_rect, level, state):
        # Collision detected, revert movement
        enemy_rect.x -= axis_dx
        enemy_rect.y -= axis_dy
        return False
    
    return True  # No collision, movement successful


def _try_enemy_slide(
    enemy_rect: pygame.Rect,
    move_x: int,
    move_y: int,
    start_x: int,
    start_y: int,
    level: "LevelState",
    state: "GameState",
) -> None:
    """
    Try sliding along walls when enemy is stuck (both axes blocked).
    """
    if enemy_rect.x == start_x and enemy_rect.y == start_y and (move_x != 0 or move_y != 0):
        step = max(1, (abs(move_x) + abs(move_y)) // 2)
        for slide_dx, slide_dy in [(move_y, move_x), (-move_y, -move_x), (move_y, -move_x), (-move_y, move_x)]:
            if slide_dx == 0 and slide_dy == 0:
                continue
            # Scale to same magnitude as step
            try:
                scale = step / (slide_dx * slide_dx + slide_dy * slide_dy) ** 0.5
            except ZeroDivisionError:
                continue
            sx = int(slide_dx * scale) if slide_dx else 0
            sy = int(slide_dy * scale) if slide_dy else 0
            if sx == 0 and sy == 0:
                continue
            enemy_rect.x += sx
            enemy_rect.y += sy
            if not _check_enemy_collision(enemy_rect, level, state):
                break  # Slide successful
            enemy_rect.x -= sx
            enemy_rect.y -= sy


def move_player_with_push(
    player_rect: pygame.Rect,
    move_x: int,
    move_y: int,
    level: "LevelState",
    width: int,
    height: int,
) -> None:
    """
    Move player with solid collision and block pushing.
    
    Single block push; no chain pushing. Movement is applied axis-by-axis
    (horizontal first, then vertical) to allow smooth diagonal movement.
    """
    # Apply movement axis by axis
    for axis_dx, axis_dy in [(move_x, 0), (0, move_y)]:
        _apply_player_axis_movement(player_rect, axis_dx, axis_dy, level)
    
    # Clamp to screen bounds
    clamp_rect_to_screen(player_rect, width, height)


def move_enemy_with_push(
    enemy_rect: pygame.Rect,
    move_x: int,
    move_y: int,
    level: "LevelState",
    state: "GameState",
    width: int,
    height: int,
) -> None:
    """
    Move enemy with solid collision detection.
    
    Enemies cannot go through objects and must navigate around them.
    When stuck (both axes blocked), tries sliding along walls to avoid getting stuck.
    """
    start_x, start_y = enemy_rect.x, enemy_rect.y
    
    # Apply movement axis by axis
    for axis_dx, axis_dy in [(move_x, 0), (0, move_y)]:
        _apply_enemy_axis_movement(enemy_rect, axis_dx, axis_dy, level, state)
    
    # If stuck, try sliding
    _try_enemy_slide(enemy_rect, move_x, move_y, start_x, start_y, level, state)
    
    # Clamp to screen bounds
    clamp_rect_to_screen(enemy_rect, width, height)
