"""A* pathfinding for tile-based maps.

Provides efficient pathfinding for AI enemies navigating around obstacles.
Supports multiprocessing for batch pathfinding of many entities.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional
from concurrent.futures import ThreadPoolExecutor, Future
import threading

if TYPE_CHECKING:
    from .map_grid import MapGrid

# Module-level thread pool for async pathfinding
_pathfinding_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()


def get_pathfinding_executor() -> ThreadPoolExecutor:
    """Get or create the shared pathfinding thread pool."""
    global _pathfinding_executor
    with _executor_lock:
        if _pathfinding_executor is None:
            # Use 2-4 threads for pathfinding (I/O bound operations)
            _pathfinding_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pathfind")
        return _pathfinding_executor


def shutdown_pathfinding_executor() -> None:
    """Shutdown the pathfinding thread pool."""
    global _pathfinding_executor
    with _executor_lock:
        if _pathfinding_executor is not None:
            _pathfinding_executor.shutdown(wait=False)
            _pathfinding_executor = None


@dataclass
class PathNode:
    """Node in the A* search graph."""
    x: int
    y: int
    g: float = 0.0  # Cost from start
    h: float = 0.0  # Heuristic cost to goal
    parent: Optional["PathNode"] = field(default=None, repr=False)
    
    @property
    def f(self) -> float:
        """Total estimated cost."""
        return self.g + self.h
    
    def __lt__(self, other: "PathNode") -> bool:
        return self.f < other.f
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PathNode):
            return False
        return self.x == other.x and self.y == other.y
    
    def __hash__(self) -> int:
        return hash((self.x, self.y))


@dataclass
class PathResult:
    """Result of a pathfinding operation."""
    path: list[tuple[int, int]]  # List of (x, y) tile coordinates
    found: bool  # Whether a path was found
    cost: float  # Total path cost
    nodes_explored: int  # Number of nodes explored (for debugging)
    
    @property
    def length(self) -> int:
        """Number of steps in the path."""
        return len(self.path)
    
    def get_next_step(self) -> Optional[tuple[int, int]]:
        """Get the next tile to move to (first step after start)."""
        if len(self.path) > 1:
            return self.path[1]
        return None
    
    def get_direction(self) -> Optional[tuple[int, int]]:
        """Get direction vector to next tile."""
        if len(self.path) > 1:
            dx = self.path[1][0] - self.path[0][0]
            dy = self.path[1][1] - self.path[0][1]
            return (dx, dy)
        return None


def heuristic(x1: int, y1: int, x2: int, y2: int) -> float:
    """Manhattan distance heuristic for A*."""
    return abs(x1 - x2) + abs(y1 - y2)


def heuristic_diagonal(x1: int, y1: int, x2: int, y2: int) -> float:
    """Chebyshev distance heuristic (allows diagonal movement)."""
    dx = abs(x1 - x2)
    dy = abs(y1 - y2)
    return max(dx, dy) + 0.41 * min(dx, dy)


def find_path(
    map_grid: "MapGrid",
    start_x: int,
    start_y: int,
    goal_x: int,
    goal_y: int,
    allow_diagonal: bool = False,
    max_iterations: int = 1000,
) -> PathResult:
    """Find a path from start to goal using A*.
    
    Args:
        map_grid: The map to pathfind on
        start_x, start_y: Starting tile coordinates
        goal_x, goal_y: Goal tile coordinates
        allow_diagonal: Whether diagonal movement is allowed
        max_iterations: Maximum nodes to explore before giving up
    
    Returns:
        PathResult with the path (or empty if not found)
    """
    from .registry import get_tile
    
    # Validate start and goal
    if not (0 <= start_x < map_grid.width and 0 <= start_y < map_grid.height):
        return PathResult(path=[], found=False, cost=0, nodes_explored=0)
    if not (0 <= goal_x < map_grid.width and 0 <= goal_y < map_grid.height):
        return PathResult(path=[], found=False, cost=0, nodes_explored=0)
    
    # Check if goal is walkable
    goal_tile_id = map_grid.get_tile_id(goal_x, goal_y)
    if goal_tile_id:
        goal_tile = get_tile(goal_tile_id)
        if goal_tile and not goal_tile.walkable:
            return PathResult(path=[], found=False, cost=0, nodes_explored=0)
    
    # Initialize
    h_func = heuristic_diagonal if allow_diagonal else heuristic
    start_node = PathNode(start_x, start_y, 0, h_func(start_x, start_y, goal_x, goal_y))
    
    open_set: list[PathNode] = [start_node]
    closed_set: set[tuple[int, int]] = set()
    open_dict: dict[tuple[int, int], PathNode] = {(start_x, start_y): start_node}
    
    # Direction vectors
    if allow_diagonal:
        directions = [
            (0, -1), (0, 1), (-1, 0), (1, 0),  # Cardinal
            (-1, -1), (-1, 1), (1, -1), (1, 1),  # Diagonal
        ]
        diagonal_cost = 1.41  # sqrt(2)
    else:
        directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
        diagonal_cost = 1.0
    
    iterations = 0
    
    while open_set and iterations < max_iterations:
        iterations += 1
        
        # Get node with lowest f score
        current = heapq.heappop(open_set)
        current_pos = (current.x, current.y)
        
        # Remove from open_dict
        if current_pos in open_dict:
            del open_dict[current_pos]
        
        # Goal check
        if current.x == goal_x and current.y == goal_y:
            # Reconstruct path
            path = []
            node: Optional[PathNode] = current
            while node is not None:
                path.append((node.x, node.y))
                node = node.parent
            path.reverse()
            return PathResult(
                path=path,
                found=True,
                cost=current.g,
                nodes_explored=iterations,
            )
        
        closed_set.add(current_pos)
        
        # Explore neighbors
        for dx, dy in directions:
            nx, ny = current.x + dx, current.y + dy
            neighbor_pos = (nx, ny)
            
            # Skip if out of bounds or already visited
            if not (0 <= nx < map_grid.width and 0 <= ny < map_grid.height):
                continue
            if neighbor_pos in closed_set:
                continue
            
            # Check if walkable
            tile_id = map_grid.get_tile_id(nx, ny)
            if tile_id:
                tile = get_tile(tile_id)
                if tile and not tile.walkable:
                    continue
            
            # Calculate cost
            move_cost = diagonal_cost if (dx != 0 and dy != 0) else 1.0
            new_g = current.g + move_cost
            
            # Check if we found a better path
            if neighbor_pos in open_dict:
                existing = open_dict[neighbor_pos]
                if new_g >= existing.g:
                    continue
                # Update existing node
                existing.g = new_g
                existing.parent = current
                heapq.heapify(open_set)
            else:
                # Add new node
                neighbor = PathNode(
                    nx, ny,
                    new_g,
                    h_func(nx, ny, goal_x, goal_y),
                    current,
                )
                heapq.heappush(open_set, neighbor)
                open_dict[neighbor_pos] = neighbor
    
    # No path found
    return PathResult(path=[], found=False, cost=0, nodes_explored=iterations)


def find_path_async(
    map_grid: "MapGrid",
    start_x: int,
    start_y: int,
    goal_x: int,
    goal_y: int,
    allow_diagonal: bool = False,
    max_iterations: int = 1000,
) -> Future[PathResult]:
    """Find a path asynchronously using thread pool.
    
    Returns a Future that will contain the PathResult.
    Use result.result() to get the PathResult (blocks until complete).
    Use result.done() to check if complete without blocking.
    """
    executor = get_pathfinding_executor()
    return executor.submit(
        find_path, map_grid, start_x, start_y, goal_x, goal_y,
        allow_diagonal, max_iterations
    )


def find_paths_batch(
    map_grid: "MapGrid",
    requests: list[tuple[int, int, int, int]],  # List of (start_x, start_y, goal_x, goal_y)
    allow_diagonal: bool = False,
    max_iterations: int = 1000,
) -> list[PathResult]:
    """Find multiple paths in parallel.
    
    Args:
        map_grid: The map to pathfind on
        requests: List of (start_x, start_y, goal_x, goal_y) tuples
        allow_diagonal: Whether diagonal movement is allowed
        max_iterations: Maximum nodes to explore per path
    
    Returns:
        List of PathResult objects in same order as requests
    """
    if not requests:
        return []
    
    executor = get_pathfinding_executor()
    futures = [
        executor.submit(
            find_path, map_grid, sx, sy, gx, gy, allow_diagonal, max_iterations
        )
        for sx, sy, gx, gy in requests
    ]
    
    return [f.result() for f in futures]


# Pathfinding cache for frequently used paths
class PathCache:
    """LRU cache for pathfinding results."""
    
    def __init__(self, max_size: int = 100):
        self._cache: dict[tuple, PathResult] = {}
        self._order: list[tuple] = []
        self._max_size = max_size
        self._lock = threading.Lock()
    
    def get(
        self,
        map_grid: "MapGrid",
        start: tuple[int, int],
        goal: tuple[int, int],
    ) -> Optional[PathResult]:
        """Get cached path if available."""
        key = (id(map_grid), start, goal)
        with self._lock:
            return self._cache.get(key)
    
    def put(
        self,
        map_grid: "MapGrid",
        start: tuple[int, int],
        goal: tuple[int, int],
        result: PathResult,
    ) -> None:
        """Cache a path result."""
        key = (id(map_grid), start, goal)
        with self._lock:
            if key in self._cache:
                self._order.remove(key)
            elif len(self._cache) >= self._max_size:
                # Evict oldest
                oldest = self._order.pop(0)
                del self._cache[oldest]
            
            self._cache[key] = result
            self._order.append(key)
    
    def clear(self) -> None:
        """Clear all cached paths."""
        with self._lock:
            self._cache.clear()
            self._order.clear()


# Global path cache
_path_cache = PathCache()


def find_path_cached(
    map_grid: "MapGrid",
    start_x: int,
    start_y: int,
    goal_x: int,
    goal_y: int,
    allow_diagonal: bool = False,
    max_iterations: int = 1000,
) -> PathResult:
    """Find path with caching for repeated queries."""
    start = (start_x, start_y)
    goal = (goal_x, goal_y)
    
    # Check cache
    cached = _path_cache.get(map_grid, start, goal)
    if cached is not None:
        return cached
    
    # Compute and cache
    result = find_path(map_grid, start_x, start_y, goal_x, goal_y, allow_diagonal, max_iterations)
    _path_cache.put(map_grid, start, goal, result)
    return result


def clear_path_cache() -> None:
    """Clear the global path cache (call when map changes)."""
    _path_cache.clear()
