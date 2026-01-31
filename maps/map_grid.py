"""MapGrid - 2D tile-based map structure."""
from __future__ import annotations

from typing import Any


class MapGrid:
    """2D grid-based map structure.
    
    Stores a grid of tile IDs that can be rendered and used for collision.
    
    Attributes:
        name: Map name/identifier
        width: Grid width in tiles
        height: Grid height in tiles
        theme: Theme name for this map (affects available tiles)
        tiles: 2D list of tile IDs [y][x]
    """
    
    def __init__(
        self,
        name: str = "untitled",
        width: int = 40,
        height: int = 22,
        theme: str = "default",
        default_tile: str = "floor",
    ):
        """Create a new map grid.
        
        Args:
            name: Map name
            width: Grid width in tiles
            height: Grid height in tiles
            theme: Theme name
            default_tile: Tile ID to fill the grid with initially
        """
        self.name = name
        self.width = width
        self.height = height
        self.theme = theme
        # Initialize with default tile
        self.tiles: list[list[str]] = [
            [default_tile for _ in range(width)]
            for _ in range(height)
        ]
    
    def get_tile_id(self, x: int, y: int) -> str | None:
        """Get the tile ID at grid coordinates.
        
        Args:
            x: Grid X coordinate (0 to width-1)
            y: Grid Y coordinate (0 to height-1)
            
        Returns:
            Tile ID at that position, or None if out of bounds
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[y][x]
        return None
    
    def set_tile_id(self, x: int, y: int, tile_id: str) -> bool:
        """Set the tile ID at grid coordinates.
        
        Args:
            x: Grid X coordinate
            y: Grid Y coordinate
            tile_id: New tile ID to set
            
        Returns:
            True if successful, False if out of bounds
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            self.tiles[y][x] = tile_id
            return True
        return False
    
    def fill(self, tile_id: str) -> None:
        """Fill the entire map with a single tile type.
        
        Args:
            tile_id: Tile ID to fill with
        """
        for y in range(self.height):
            for x in range(self.width):
                self.tiles[y][x] = tile_id
    
    def fill_rect(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        tile_id: str,
    ) -> None:
        """Fill a rectangular region with a tile type.
        
        Args:
            x1, y1: Top-left corner (inclusive)
            x2, y2: Bottom-right corner (inclusive)
            tile_id: Tile ID to fill with
        """
        for y in range(max(0, y1), min(self.height, y2 + 1)):
            for x in range(max(0, x1), min(self.width, x2 + 1)):
                self.tiles[y][x] = tile_id
    
    def to_dict(self) -> dict[str, Any]:
        """Convert map to a dictionary for serialization.
        
        Returns:
            Dict representation of the map
        """
        return {
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "theme": self.theme,
            "tiles": self.tiles,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MapGrid:
        """Create a MapGrid from a dictionary.
        
        Args:
            data: Dict containing map data
            
        Returns:
            New MapGrid instance
        """
        grid = cls(
            name=data.get("name", "untitled"),
            width=data.get("width", 40),
            height=data.get("height", 22),
            theme=data.get("theme", "default"),
            default_tile="floor",
        )
        # Load tiles if present
        if "tiles" in data:
            grid.tiles = data["tiles"]
        return grid
    
    def __repr__(self) -> str:
        return f"MapGrid(name={self.name!r}, width={self.width}, height={self.height}, theme={self.theme!r})"
