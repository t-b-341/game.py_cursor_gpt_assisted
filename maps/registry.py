"""Tile and theme registry for the map system."""
from typing import Optional

from .tile import Tile


# Global tile registry
_tiles: dict[str, Tile] = {}

# Theme mappings (theme_name -> list of tile_ids)
_themes: dict[str, list[str]] = {}


def register_tile(tile: Tile) -> None:
    """Register a tile type in the global registry.
    
    Args:
        tile: Tile instance to register
        
    Raises:
        ValueError: If a tile with this ID is already registered
    """
    if tile.id in _tiles:
        raise ValueError(f"Tile '{tile.id}' is already registered")
    _tiles[tile.id] = tile


def get_tile(tile_id: str) -> Optional[Tile]:
    """Get a tile by ID.
    
    Args:
        tile_id: The tile's unique identifier
        
    Returns:
        The Tile instance, or None if not found
    """
    return _tiles.get(tile_id)


def list_tiles() -> list[Tile]:
    """List all registered tiles.
    
    Returns:
        List of all registered Tile instances
    """
    return list(_tiles.values())


def register_theme(theme_name: str, tile_ids: list[str]) -> None:
    """Register a theme with its associated tile IDs.
    
    Args:
        theme_name: Name of the theme (e.g., "ocean", "lava", "desert")
        tile_ids: List of tile IDs that belong to this theme
    """
    _themes[theme_name] = tile_ids


def get_theme_tiles(theme_name: str) -> list[Tile]:
    """Get all tiles for a theme.
    
    Args:
        theme_name: Name of the theme
        
    Returns:
        List of Tile instances for this theme, or empty list if theme not found
    """
    tile_ids = _themes.get(theme_name, [])
    return [_tiles[tid] for tid in tile_ids if tid in _tiles]


def list_themes() -> list[str]:
    """List all registered theme names.
    
    Returns:
        List of theme names
    """
    return list(_themes.keys())


def clear_registry() -> None:
    """Clear all tiles and themes (useful for testing)."""
    _tiles.clear()
    _themes.clear()


# =============================================================================
# DEFAULT TILES REGISTRATION
# =============================================================================

def _register_default_tiles() -> None:
    """Register the default set of tiles."""
    # Basic tiles
    register_tile(Tile(
        id="floor",
        name="Floor",
        walkable=True,
        color=(60, 60, 60),
    ))
    register_tile(Tile(
        id="wall",
        name="Wall",
        walkable=False,
        color=(40, 40, 45),
    ))
    
    # Ocean theme
    register_tile(Tile(
        id="ocean_water",
        name="Ocean Water",
        walkable=True,  # Walkable but could slow/damage
        color=(30, 100, 180),
        shader_flags={"water_effect": True},
    ))
    register_tile(Tile(
        id="ocean_rock",
        name="Ocean Rock",
        walkable=False,
        color=(80, 90, 100),
    ))
    
    # Lava theme
    register_tile(Tile(
        id="lava_floor",
        name="Lava Floor",
        walkable=True,
        color=(60, 30, 20),
    ))
    register_tile(Tile(
        id="lava_rock",
        name="Lava Rock",
        walkable=False,
        color=(50, 25, 25),
    ))
    register_tile(Tile(
        id="lava_pool",
        name="Lava Pool",
        walkable=True,  # Walkable but damages
        color=(255, 100, 20),
        shader_flags={"lava_glow": True, "damage": 10},
    ))
    
    # Desert theme
    register_tile(Tile(
        id="desert_sand",
        name="Desert Sand",
        walkable=True,
        color=(210, 180, 120),
    ))
    register_tile(Tile(
        id="desert_rock",
        name="Desert Rock",
        walkable=False,
        color=(150, 120, 80),
    ))
    
    # Register themes
    register_theme("default", ["floor", "wall"])
    register_theme("ocean", ["ocean_water", "ocean_rock", "floor", "wall"])
    register_theme("lava", ["lava_floor", "lava_rock", "lava_pool", "wall"])
    register_theme("desert", ["desert_sand", "desert_rock", "floor", "wall"])


# Auto-register default tiles on import
_register_default_tiles()
