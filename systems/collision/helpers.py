"""Common collision helpers used across collision modules."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..spatial_grid import get_enemy_grid, get_block_grid, SpatialGrid

if TYPE_CHECKING:
    from state import GameState


def create_damage_number(
    x: int | float,
    y: int | float,
    damage: int | float,
    color: tuple[int, int, int] = (255, 255, 100),
    timer: float = 2.0,
) -> dict:
    """Create a damage number dict for display.
    
    Args:
        x: X position (usually entity centerx)
        y: Y position (usually entity top - 20)
        damage: Damage amount to display
        color: RGB color tuple (default yellow)
        timer: Display duration in seconds
        
    Returns:
        Dict ready to append to state.damage_numbers
    """
    return {
        "x": x,
        "y": y,
        "damage": int(damage),
        "timer": timer,
        "color": color,
    }


def bulk_remove(items: list, ids_to_remove: set) -> None:
    """Remove items from list by id set (O(n) instead of O(n²) with .remove()).
    
    Modifies list in-place using slice assignment.
    
    Args:
        items: List to filter
        ids_to_remove: Set of id(item) values to remove
    """
    if ids_to_remove:
        items[:] = [item for item in items if id(item) not in ids_to_remove]


def build_enemy_grid(state: "GameState", ctx: dict) -> SpatialGrid:
    """Build spatial grid containing all enemies. Uses frame caching.
    
    Args:
        state: Game state containing enemies list
        ctx: Context dict with width, height, and frame_id
        
    Returns:
        SpatialGrid populated with enemies
    """
    width: int = ctx.get("width", 1920)
    height: int = ctx.get("height", 1080)
    frame_id: int = ctx.get("frame_id", -1)
    grid = get_enemy_grid(width, height, frame_id=frame_id)
    if len(grid._obj_cells) == 0 and state.enemies:
        grid.insert_all(state.enemies)
    return grid


def build_block_grid(state: "GameState", ctx: dict) -> SpatialGrid:
    """Build spatial grid containing all collidable blocks.
    
    Called once per collision update frame. Uses frame caching.
    """
    # Check if pre-built grid is available in context
    cached = ctx.get("_block_grid")
    if cached is not None:
        return cached
    
    width = ctx.get("width", 1920)
    height = ctx.get("height", 1080)
    frame_id = ctx.get("frame_id", -1)
    
    lev = getattr(state, "level", None)
    if lev is None:
        return get_block_grid(width, height, frame_id=frame_id)
    
    grid = get_block_grid(width, height, frame_id=frame_id)
    
    # Only insert if grid was just cleared (not cached this frame)
    if len(grid._obj_cells) > 0:
        return grid
    
    # Insert all block types
    for block in lev.destructible_blocks:
        if block.get("rect"):
            grid.insert(block, block["rect"])
    for block in lev.moveable_blocks:
        if block.get("rect"):
            grid.insert(block, block["rect"])
    for block in lev.giant_blocks + lev.super_giant_blocks:
        if block.get("rect"):
            grid.insert(block, block["rect"])
    for tb in lev.trapezoid_blocks:
        br = tb.get("bounding_rect", tb.get("rect"))
        if br:
            grid.insert(tb, br)
    for tr in lev.triangle_blocks:
        br = tr.get("bounding_rect", tr.get("rect"))
        if br:
            grid.insert(tr, br)
    
    return grid


# Alias for backward compatibility with code that used the cached version name
build_block_grid_cached = build_block_grid
