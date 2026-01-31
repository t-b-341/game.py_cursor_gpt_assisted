"""MapManager - runtime map handling and rendering."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import pygame

from .map_grid import MapGrid
from .map_loader import load_map
from .map_saver import list_saved_maps
from .registry import get_tile

if TYPE_CHECKING:
    from systems.camera import Camera

# Default tile size
TILE_SIZE = 64


class MapManager:
    """Manages map loading, switching, and rendering.
    
    Attributes:
        current_map: Currently active MapGrid
        loaded_maps: Cache of loaded maps by name
        tile_size: Size of each tile in pixels
    """
    
    def __init__(self, tile_size: int = TILE_SIZE):
        """Initialize the map manager.
        
        Args:
            tile_size: Size of tiles in pixels (default 64)
        """
        self.current_map: Optional[MapGrid] = None
        self.loaded_maps: dict[str, MapGrid] = {}
        self.tile_size = tile_size
        self._sprite_cache: dict[str, pygame.Surface] = {}
    
    def load_map_by_name(self, name: str) -> bool:
        """Load a map by name from the data directory.
        
        Args:
            name: Map name (filename without .json)
            
        Returns:
            True if map was loaded successfully
        """
        # Check cache first
        if name in self.loaded_maps:
            self.current_map = self.loaded_maps[name]
            return True
        
        # Load from file
        map_grid = load_map(name)
        if map_grid:
            self.loaded_maps[name] = map_grid
            self.current_map = map_grid
            return True
        return False
    
    def set_current_map(self, map_grid: MapGrid) -> None:
        """Set the current map directly.
        
        Args:
            map_grid: MapGrid to set as current
        """
        self.current_map = map_grid
        self.loaded_maps[map_grid.name] = map_grid
    
    def get_current_map(self) -> Optional[MapGrid]:
        """Get the currently active map.
        
        Returns:
            Current MapGrid or None
        """
        return self.current_map
    
    def list_available_maps(self) -> list[str]:
        """List all available map names.
        
        Returns:
            List of map names (from saved files)
        """
        return list_saved_maps()
    
    def cycle_map(self) -> Optional[str]:
        """Cycle to the next available map.
        
        Returns:
            Name of the new current map, or None if no maps available
        """
        available = self.list_available_maps()
        if not available:
            return None
        
        current_name = self.current_map.name if self.current_map else ""
        
        try:
            idx = available.index(current_name)
            next_idx = (idx + 1) % len(available)
        except ValueError:
            next_idx = 0
        
        next_name = available[next_idx]
        if self.load_map_by_name(next_name):
            return next_name
        return None
    
    def render(
        self,
        surface: pygame.Surface,
        camera: Optional[Camera] = None,
    ) -> None:
        """Render the current map to a surface.
        
        Args:
            surface: Pygame surface to render to
            camera: Optional camera for viewport offset
        """
        if not self.current_map:
            return
        
        # Get camera offset
        if camera:
            cam_x, cam_y = int(camera.x), int(camera.y)
            view_width = camera.display_width
            view_height = camera.display_height
        else:
            cam_x, cam_y = 0, 0
            view_width = surface.get_width()
            view_height = surface.get_height()
        
        ts = self.tile_size
        grid = self.current_map
        
        # Calculate visible tile range
        start_x = max(0, cam_x // ts)
        start_y = max(0, cam_y // ts)
        end_x = min(grid.width, (cam_x + view_width) // ts + 2)
        end_y = min(grid.height, (cam_y + view_height) // ts + 2)
        
        # Render visible tiles
        for ty in range(start_y, end_y):
            for tx in range(start_x, end_x):
                tile_id = grid.get_tile_id(tx, ty)
                if not tile_id:
                    continue
                
                # Get tile definition
                tile = get_tile(tile_id)
                if not tile:
                    continue
                
                # Calculate screen position
                screen_x = tx * ts - cam_x
                screen_y = ty * ts - cam_y
                
                # Draw tile (sprite or color fallback)
                tile_rect = pygame.Rect(screen_x, screen_y, ts, ts)
                
                # Check sprite cache
                if tile.sprite_path and tile.sprite_path in self._sprite_cache:
                    surface.blit(self._sprite_cache[tile.sprite_path], tile_rect)
                else:
                    # Color fallback
                    pygame.draw.rect(surface, tile.color, tile_rect)
    
    def load_tile_sprite(self, tile_id: str, sprite_path: str) -> bool:
        """Load and cache a sprite for a tile.
        
        Args:
            tile_id: Tile ID this sprite is for
            sprite_path: Path to sprite image
            
        Returns:
            True if sprite was loaded successfully
        """
        try:
            sprite = pygame.image.load(sprite_path).convert_alpha()
            sprite = pygame.transform.scale(sprite, (self.tile_size, self.tile_size))
            self._sprite_cache[sprite_path] = sprite
            return True
        except Exception as e:
            print(f"[maps] Error loading sprite {sprite_path}: {e}")
            return False
    
    def clear_cache(self) -> None:
        """Clear loaded maps and sprite cache."""
        self.loaded_maps.clear()
        self._sprite_cache.clear()
        self.current_map = None
