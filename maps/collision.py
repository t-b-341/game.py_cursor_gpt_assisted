"""Tile-based collision helpers for the map system.

These functions are opt-in and do not interfere with existing collision systems.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from .registry import get_tile

if TYPE_CHECKING:
    from .map_grid import MapGrid


def world_to_tile(x: float, y: float, tile_size: int = 64) -> tuple[int, int]:
    """Convert world coordinates to tile grid coordinates.
    
    Args:
        x: World X coordinate
        y: World Y coordinate
        tile_size: Size of tiles in pixels
        
    Returns:
        Tuple of (tile_x, tile_y)
    """
    return int(x // tile_size), int(y // tile_size)


def is_tile_blocking(
    map_grid: MapGrid,
    x: float,
    y: float,
    tile_size: int = 64,
) -> bool:
    """Check if a world position is on a blocking tile.
    
    Args:
        map_grid: The map to check
        x: World X coordinate
        y: World Y coordinate
        tile_size: Size of tiles in pixels
        
    Returns:
        True if the tile at this position is not walkable
    """
    tx, ty = world_to_tile(x, y, tile_size)
    tile_id = map_grid.get_tile_id(tx, ty)
    
    if tile_id is None:
        # Out of bounds = blocking
        return True
    
    tile = get_tile(tile_id)
    if tile is None:
        return False
    
    return not tile.walkable


def is_rect_blocking(
    map_grid: MapGrid,
    rect: pygame.Rect,
    tile_size: int = 64,
) -> bool:
    """Check if any corner of a rect is on a blocking tile.
    
    Args:
        map_grid: The map to check
        rect: Rectangle to check
        tile_size: Size of tiles in pixels
        
    Returns:
        True if any corner is on a blocking tile
    """
    # Check all four corners
    corners = [
        (rect.left, rect.top),
        (rect.right - 1, rect.top),
        (rect.left, rect.bottom - 1),
        (rect.right - 1, rect.bottom - 1),
    ]
    
    for x, y in corners:
        if is_tile_blocking(map_grid, x, y, tile_size):
            return True
    
    return False


def resolve_entity_map_collision(
    entity_rect: pygame.Rect,
    velocity: tuple[float, float],
    map_grid: MapGrid,
    tile_size: int = 64,
) -> tuple[pygame.Rect, tuple[float, float]]:
    """Resolve entity collision with map tiles.
    
    Moves entity and stops at blocking tiles. Returns adjusted rect and velocity.
    
    Args:
        entity_rect: Entity's current rect (will be copied)
        velocity: (vx, vy) velocity tuple
        map_grid: The map to check collisions against
        tile_size: Size of tiles in pixels
        
    Returns:
        Tuple of (new_rect, new_velocity)
    """
    new_rect = entity_rect.copy()
    vx, vy = velocity
    
    # Move X first
    new_rect.x += int(vx)
    if is_rect_blocking(map_grid, new_rect, tile_size):
        new_rect.x = entity_rect.x  # Revert
        vx = 0
    
    # Then move Y
    new_rect.y += int(vy)
    if is_rect_blocking(map_grid, new_rect, tile_size):
        new_rect.y = entity_rect.y  # Revert
        vy = 0
    
    return new_rect, (vx, vy)


def get_blocking_tiles_in_rect(
    map_grid: MapGrid,
    rect: pygame.Rect,
    tile_size: int = 64,
) -> list[tuple[int, int]]:
    """Get all blocking tile positions that overlap a rect.
    
    Args:
        map_grid: The map to check
        rect: Rectangle to check
        tile_size: Size of tiles in pixels
        
    Returns:
        List of (tile_x, tile_y) positions that are blocking
    """
    blocking = []
    
    start_tx, start_ty = world_to_tile(rect.left, rect.top, tile_size)
    end_tx, end_ty = world_to_tile(rect.right, rect.bottom, tile_size)
    
    for ty in range(start_ty, end_ty + 1):
        for tx in range(start_tx, end_tx + 1):
            tile_id = map_grid.get_tile_id(tx, ty)
            if tile_id is None:
                blocking.append((tx, ty))
                continue
            
            tile = get_tile(tile_id)
            if tile and not tile.walkable:
                blocking.append((tx, ty))
    
    return blocking
