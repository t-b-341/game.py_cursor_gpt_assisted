"""Tile definition for map system."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Tile:
    """Represents a single tile type in the map system.
    
    Attributes:
        id: Unique identifier for this tile type (e.g., "floor", "wall")
        name: Human-readable display name
        walkable: Whether entities can walk through this tile
        sprite_path: Optional path to sprite image (None = use color fallback)
        color: Fallback color when no sprite is available (R, G, B)
        shader_flags: Optional dict of shader-related flags/parameters
    """
    id: str
    name: str
    walkable: bool = True
    sprite_path: Optional[str] = None
    color: tuple[int, int, int] = (128, 128, 128)
    shader_flags: Optional[dict] = field(default_factory=dict)
    
    def __hash__(self) -> int:
        return hash(self.id)
    
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Tile):
            return self.id == other.id
        return False
