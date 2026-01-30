"""Spatial grid for fast collision detection.

Divides the game world into cells. Objects are inserted into cells based on their position.
Collision queries only check objects in nearby cells, reducing O(n*m) to O(n) average case.
Uses C-accelerated cell index calculations when available.
"""
from __future__ import annotations

from typing import Any, Iterator
import pygame

from physics_loader import (
    get_grid_cell_indices_for_rect as c_get_cell_indices_for_rect,
    is_using_c,
)


class SpatialGrid:
    """Grid-based spatial partitioning for efficient collision queries."""
    
    __slots__ = ('cell_size', 'width', 'height', 'cols', 'rows', 'cells', '_obj_cells')
    
    def __init__(self, width: int, height: int, cell_size: int = 128):
        """
        Initialize spatial grid.
        
        Args:
            width: World width in pixels
            height: World height in pixels  
            cell_size: Size of each grid cell (larger = fewer cells but more objects per cell)
        """
        self.cell_size = cell_size
        self.width = width
        self.height = height
        self.cols = max(1, (width + cell_size - 1) // cell_size)
        self.rows = max(1, (height + cell_size - 1) // cell_size)
        self.cells: list[list[Any]] = [[] for _ in range(self.cols * self.rows)]
        self._obj_cells: dict[int, list[int]] = {}  # Track which cells each object is in
    
    def clear(self) -> None:
        """Clear all objects from the grid."""
        for cell in self.cells:
            cell.clear()
        self._obj_cells.clear()
    
    def _get_cell_index(self, x: int, y: int) -> int:
        """Get cell index for a position."""
        col = max(0, min(self.cols - 1, x // self.cell_size))
        row = max(0, min(self.rows - 1, y // self.cell_size))
        return row * self.cols + col
    
    def _get_cell_indices_for_rect(self, rect: pygame.Rect) -> list[int]:
        """Get all cell indices that a rect overlaps. Uses C-accelerated version if available."""
        # Use C-accelerated function for grid cell calculations
        return c_get_cell_indices_for_rect(
            rect.left, rect.top, rect.width, rect.height,
            self.cell_size, self.cols, self.rows
        )
    
    def insert(self, obj: Any, rect: pygame.Rect) -> None:
        """Insert an object into the grid based on its rect."""
        obj_id = id(obj)
        indices = self._get_cell_indices_for_rect(rect)
        self._obj_cells[obj_id] = indices
        for idx in indices:
            self.cells[idx].append(obj)
    
    def insert_all(self, objects: list[Any], get_rect: callable = None) -> None:
        """Insert multiple objects efficiently.
        
        Args:
            objects: List of objects to insert
            get_rect: Optional function to get rect from object. 
                     If None, assumes obj["rect"] or obj.rect
        """
        for obj in objects:
            if get_rect:
                rect = get_rect(obj)
            elif isinstance(obj, dict):
                rect = obj.get("rect")
            else:
                rect = getattr(obj, "rect", None)
            
            if rect:
                self.insert(obj, rect)
    
    def query_rect(self, rect: pygame.Rect) -> Iterator[Any]:
        """Yield all objects that might collide with the given rect.
        
        Note: This yields candidates - caller must still do precise collision check.
        Objects may be yielded multiple times if they span multiple cells.
        """
        seen = set()
        indices = self._get_cell_indices_for_rect(rect)
        for idx in indices:
            for obj in self.cells[idx]:
                obj_id = id(obj)
                if obj_id not in seen:
                    seen.add(obj_id)
                    yield obj
    
    def query_point(self, x: int, y: int) -> Iterator[Any]:
        """Yield all objects in the cell containing the given point."""
        idx = self._get_cell_index(x, y)
        yield from self.cells[idx]
    
    def query_radius(self, cx: int, cy: int, radius: int) -> Iterator[Any]:
        """Yield all objects that might be within radius of a point."""
        # Create a bounding rect for the circle
        rect = pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2)
        yield from self.query_rect(rect)


# Module-level grid instances for reuse (avoid allocation each frame)
_projectile_grid: SpatialGrid | None = None
_enemy_grid: SpatialGrid | None = None
_block_grid: SpatialGrid | None = None

# Frame-based caching: only rebuild grids once per frame
_last_frame_id: int = -1
_grids_built_this_frame: set[str] = set()


def _check_frame_cache(grid_name: str, frame_id: int) -> bool:
    """Check if this grid was already built this frame. Returns True if cached."""
    global _last_frame_id, _grids_built_this_frame
    if frame_id != _last_frame_id:
        _last_frame_id = frame_id
        _grids_built_this_frame.clear()
    
    if grid_name in _grids_built_this_frame:
        return True
    _grids_built_this_frame.add(grid_name)
    return False


def get_projectile_grid(width: int, height: int, cell_size: int = 128, frame_id: int = -1) -> SpatialGrid:
    """Get or create the projectile spatial grid.
    
    Args:
        frame_id: If provided, enables frame-based caching (grid only rebuilt once per frame).
    """
    global _projectile_grid
    
    # Check if we should reuse cached grid
    if frame_id >= 0 and _check_frame_cache("projectile", frame_id) and _projectile_grid is not None:
        return _projectile_grid
    
    if _projectile_grid is None or _projectile_grid.width != width or _projectile_grid.height != height:
        _projectile_grid = SpatialGrid(width, height, cell_size)
    else:
        _projectile_grid.clear()
    return _projectile_grid


def get_enemy_grid(width: int, height: int, cell_size: int = 128, frame_id: int = -1) -> SpatialGrid:
    """Get or create the enemy spatial grid.
    
    Args:
        frame_id: If provided, enables frame-based caching (grid only rebuilt once per frame).
    """
    global _enemy_grid
    
    # Check if we should reuse cached grid
    if frame_id >= 0 and _check_frame_cache("enemy", frame_id) and _enemy_grid is not None:
        return _enemy_grid
    
    if _enemy_grid is None or _enemy_grid.width != width or _enemy_grid.height != height:
        _enemy_grid = SpatialGrid(width, height, cell_size)
    else:
        _enemy_grid.clear()
    return _enemy_grid


def get_block_grid(width: int, height: int, cell_size: int = 128, frame_id: int = -1) -> SpatialGrid:
    """Get or create the block spatial grid.
    
    Args:
        frame_id: If provided, enables frame-based caching (grid only rebuilt once per frame).
    """
    global _block_grid
    
    # Check if we should reuse cached grid
    if frame_id >= 0 and _check_frame_cache("block", frame_id) and _block_grid is not None:
        return _block_grid
    
    if _block_grid is None or _block_grid.width != width or _block_grid.height != height:
        _block_grid = SpatialGrid(width, height, cell_size)
    else:
        _block_grid.clear()
    return _block_grid


def reset_frame_cache() -> None:
    """Force grids to rebuild on next access. Call at start of frame if needed."""
    global _last_frame_id
    _last_frame_id = -1
