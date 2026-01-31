"""Convert MapGrid to game level geometry (LevelState)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from game_logging import get_logger

_log = get_logger(__name__)

if TYPE_CHECKING:
    from .map_grid import MapGrid
    from level_state import LevelState


# Tile size in pixels (should match editor and game)
TILE_SIZE = 64


def map_to_level_state(map_grid: "MapGrid") -> "LevelState":
    """Convert a MapGrid to a LevelState for in-game use.
    
    Converts non-walkable tiles to static blocks that the collision
    system can use.
    
    Args:
        map_grid: The custom map to convert
        
    Returns:
        LevelState with static blocks from the map's non-walkable tiles
    """
    from level_state import LevelState
    from .registry import get_tile
    
    static_blocks: list = []
    
    # Convert each non-walkable tile to a static block
    for ty in range(map_grid.height):
        for tx in range(map_grid.width):
            tile_id = map_grid.get_tile_id(tx, ty)
            if tile_id is None:
                continue
            
            tile = get_tile(tile_id)
            if tile is None:
                continue
            
            # Non-walkable tiles become static blocks
            if not tile.walkable:
                block = {
                    "rect": pygame.Rect(
                        tx * TILE_SIZE,
                        ty * TILE_SIZE,
                        TILE_SIZE,
                        TILE_SIZE
                    ),
                    "color": tile.color,
                    "tile_id": tile_id,
                }
                static_blocks.append(block)
    
    _log.debug(f"Converted map '{map_grid.name}' to {len(static_blocks)} static blocks")
    
    # Create LevelState with only static blocks from the map
    # Other block types are left empty for custom maps
    return LevelState(
        static_blocks=static_blocks,
        trapezoid_blocks=[],
        triangle_blocks=[],
        destructible_blocks=[],
        moveable_blocks=[],
        giant_blocks=[],
        super_giant_blocks=[],
        hazard_obstacles=[],
        moving_health_zone=None,
    )


def get_player_spawn_position(map_grid: "MapGrid", default_x: int = 400, default_y: int = 300) -> tuple[int, int]:
    """Get the player spawn position from a map.
    
    Args:
        map_grid: The custom map
        default_x: Default X position if no spawn defined
        default_y: Default Y position if no spawn defined
        
    Returns:
        (x, y) world position for player spawn
    """
    if map_grid.player_spawn:
        tx, ty = map_grid.player_spawn
        # Convert tile coords to world coords (center of tile)
        return (
            tx * TILE_SIZE + TILE_SIZE // 2,
            ty * TILE_SIZE + TILE_SIZE // 2,
        )
    return (default_x, default_y)
