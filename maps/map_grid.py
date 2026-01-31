"""MapGrid - 2D tile-based map structure."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .spawn_point import SpawnPoint


class MapGrid:
    """2D grid-based map structure.
    
    Stores a grid of tile IDs that can be rendered and used for collision.
    
    Attributes:
        name: Map name/identifier
        width: Grid width in tiles
        height: Grid height in tiles
        theme: Theme name for this map (affects available tiles)
        tiles: 2D list of tile IDs [y][x]
        spawn_points: List of SpawnPoint objects for enemy spawning
        player_spawn: Optional (x, y) tuple for player start position
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
        # Spawn points for enemies
        self.spawn_points: list[SpawnPoint] = []
        # Player start position (tile coordinates)
        self.player_spawn: tuple[int, int] | None = None
    
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
    
    def resize(
        self,
        new_width: int,
        new_height: int,
        anchor: str = "top_left",
        default_tile: str = "floor",
    ) -> None:
        """Resize the map grid, preserving existing tiles where possible.
        
        Args:
            new_width: New grid width in tiles
            new_height: New grid height in tiles
            anchor: Where to anchor existing content. Options:
                    "top_left", "top_right", "bottom_left", "bottom_right", "center"
            default_tile: Tile ID to use for new areas
        """
        if new_width < 1 or new_height < 1:
            return
        
        # Calculate offset based on anchor
        if anchor == "top_left":
            offset_x, offset_y = 0, 0
        elif anchor == "top_right":
            offset_x, offset_y = new_width - self.width, 0
        elif anchor == "bottom_left":
            offset_x, offset_y = 0, new_height - self.height
        elif anchor == "bottom_right":
            offset_x, offset_y = new_width - self.width, new_height - self.height
        elif anchor == "center":
            offset_x = (new_width - self.width) // 2
            offset_y = (new_height - self.height) // 2
        else:
            offset_x, offset_y = 0, 0
        
        # Create new tile grid
        new_tiles: list[list[str]] = [
            [default_tile for _ in range(new_width)]
            for _ in range(new_height)
        ]
        
        # Copy existing tiles to new grid
        for old_y in range(self.height):
            for old_x in range(self.width):
                new_x = old_x + offset_x
                new_y = old_y + offset_y
                if 0 <= new_x < new_width and 0 <= new_y < new_height:
                    new_tiles[new_y][new_x] = self.tiles[old_y][old_x]
        
        # Update grid
        self.width = new_width
        self.height = new_height
        self.tiles = new_tiles
    
    def to_dict(self) -> dict[str, Any]:
        """Convert map to a dictionary for serialization.
        
        Returns:
            Dict representation of the map
        """
        result = {
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "theme": self.theme,
            "tiles": self.tiles,
        }
        # Only include spawn data if present
        if self.spawn_points:
            result["spawn_points"] = [sp.to_dict() for sp in self.spawn_points]
        if self.player_spawn is not None:
            result["player_spawn"] = list(self.player_spawn)
        return result
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MapGrid:
        """Create a MapGrid from a dictionary.
        
        Args:
            data: Dict containing map data
            
        Returns:
            New MapGrid instance
        """
        from .spawn_point import SpawnPoint
        
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
        # Load spawn points if present
        if "spawn_points" in data:
            grid.spawn_points = [SpawnPoint.from_dict(sp) for sp in data["spawn_points"]]
        # Load player spawn if present
        if "player_spawn" in data:
            ps = data["player_spawn"]
            grid.player_spawn = (ps[0], ps[1]) if ps else None
        return grid
    
    def add_spawn_point(self, spawn_point: "SpawnPoint") -> None:
        """Add a spawn point to the map."""
        self.spawn_points.append(spawn_point)
    
    def remove_spawn_point_at(self, x: int, y: int) -> bool:
        """Remove spawn point at given tile coordinates. Returns True if removed."""
        for i, sp in enumerate(self.spawn_points):
            if sp.x == x and sp.y == y:
                self.spawn_points.pop(i)
                return True
        return False
    
    def get_spawn_point_at(self, x: int, y: int) -> "SpawnPoint | None":
        """Get spawn point at given tile coordinates."""
        for sp in self.spawn_points:
            if sp.x == x and sp.y == y:
                return sp
        return None
    
    def get_spawn_points_for_wave(self, wave: int) -> list["SpawnPoint"]:
        """Get all spawn points active for the given wave number."""
        return [sp for sp in self.spawn_points if sp.can_spawn_on_wave(wave)]
    
    def __repr__(self) -> str:
        return f"MapGrid(name={self.name!r}, width={self.width}, height={self.height}, theme={self.theme!r})"
