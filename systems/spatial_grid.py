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
        """Clear all objects from the grid.
        
        Optimized: only clears cells that have objects (tracked via _obj_cells).
        """
        # Only clear cells that actually have objects (avoid O(n) iteration)
        if self._obj_cells:
            # Get unique cell indices that have objects
            cells_to_clear = set()
            for indices in self._obj_cells.values():
                cells_to_clear.update(indices)
            
            for idx in cells_to_clear:
                if idx < len(self.cells):
                    self.cells[idx].clear()
            
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
        # Compute cell indices directly (avoid creating pygame.Rect)
        left = cx - radius
        top = cy - radius
        size = radius * 2
        indices = c_get_cell_indices_for_rect(left, top, size, size, self.cell_size, self.cols, self.rows)
        seen = set()
        for idx in indices:
            for obj in self.cells[idx]:
                obj_id = id(obj)
                if obj_id not in seen:
                    seen.add(obj_id)
                    yield obj


# Module-level grid instances for reuse (avoid allocation each frame)
_projectile_grid: SpatialGrid | None = None
_enemy_grid: SpatialGrid | None = None
_block_grid: SpatialGrid | None = None

# Frame-based caching: only rebuild grids once per frame
_last_frame_id: int = -1
_grids_built_this_frame: set[str] = set()

# Block grid invalidation: only rebuild when blocks change
_block_grid_version: int = 0
_block_grid_last_version: int = -1


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
    
    Note: Block grid uses version-based invalidation in addition to frame caching.
          Call invalidate_block_grid() when blocks are destroyed or level changes.
    """
    global _block_grid, _block_grid_last_version
    
    # Check if we should reuse cached grid (version-based)
    if (_block_grid is not None and 
        _block_grid_last_version == _block_grid_version and
        _block_grid.width == width and 
        _block_grid.height == height and
        len(_block_grid._obj_cells) > 0):
        # Grid is still valid, return cached
        return _block_grid
    
    # Check frame cache
    if frame_id >= 0 and _check_frame_cache("block", frame_id) and _block_grid is not None:
        if _block_grid_last_version == _block_grid_version and len(_block_grid._obj_cells) > 0:
            return _block_grid
    
    if _block_grid is None or _block_grid.width != width or _block_grid.height != height:
        _block_grid = SpatialGrid(width, height, cell_size)
    else:
        _block_grid.clear()
    
    _block_grid_last_version = _block_grid_version
    return _block_grid


def invalidate_block_grid() -> None:
    """Invalidate the block grid cache.
    
    Call this when:
    - A destructible block is destroyed
    - A new level is loaded
    - Blocks are added/removed
    
    The grid will be rebuilt on next access.
    """
    global _block_grid_version
    _block_grid_version += 1


def reset_frame_cache() -> None:
    """Force grids to rebuild on next access. Call at start of frame if needed."""
    global _last_frame_id
    _last_frame_id = -1


def reset_all_grids() -> None:
    """Reset all grids. Call when loading a new level."""
    global _projectile_grid, _enemy_grid, _block_grid
    global _last_frame_id, _grids_built_this_frame
    global _block_grid_version, _block_grid_last_version
    
    _projectile_grid = None
    _enemy_grid = None
    _block_grid = None
    _last_frame_id = -1
    _grids_built_this_frame.clear()
    _block_grid_version += 1
    _block_grid_last_version = -1
