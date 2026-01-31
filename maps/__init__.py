"""
Maps package - tile-based map system with editor support.

This package provides:
- Tile definitions and registry
- MapGrid for 2D tile-based levels
- Map saving/loading (JSON format)
- MapManager for runtime map handling
- Collision helpers for tile-based collision
- Standalone map editor

Usage:
    from maps import MapManager, load_map, MapGrid
    
    manager = MapManager()
    manager.load_map("my_map")
    manager.render(screen, camera)
"""

from .tile import Tile
from .registry import (
    register_tile,
    get_tile,
    list_tiles,
    register_theme,
    get_theme_tiles,
)
from .map_grid import MapGrid
from .map_saver import save_map
from .map_loader import load_map
from .map_manager import MapManager
from .collision import world_to_tile, is_tile_blocking, resolve_entity_map_collision
from .spawn_point import SpawnPoint, ENEMY_POOLS, get_available_enemy_types
from .pathfinding import (
    find_path,
    find_path_async,
    find_path_cached,
    find_paths_batch,
    clear_path_cache,
    PathResult,
)
from .level_converter import map_to_level_state, get_player_spawn_position

__all__ = [
    "Tile",
    "register_tile",
    "get_tile",
    "list_tiles",
    "register_theme",
    "get_theme_tiles",
    "MapGrid",
    "save_map",
    "load_map",
    "MapManager",
    "world_to_tile",
    "is_tile_blocking",
    "resolve_entity_map_collision",
    "SpawnPoint",
    "ENEMY_POOLS",
    "get_available_enemy_types",
    # Pathfinding
    "find_path",
    "find_path_async",
    "find_path_cached",
    "find_paths_batch",
    "clear_path_cache",
    "PathResult",
    # Level conversion
    "map_to_level_state",
    "get_player_spawn_position",
]

# Default tile size (64x64 pixels)
TILE_SIZE = 64
