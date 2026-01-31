"""Editor constants and data classes."""
from __future__ import annotations

from dataclasses import dataclass


# Editor display constants
TILE_SIZE = 64
PALETTE_WIDTH = 200
PALETTE_TILE_SIZE = 48
PALETTE_PADDING = 8

# Editor limits
MAX_UNDO_HISTORY = 100
AUTOSAVE_INTERVAL = 60.0  # seconds
MAX_FLOOD_FILL = 10000
MAX_MAP_SIZE = 200
MAX_NAME_LENGTH = 30
MAX_POOL_INPUT_LENGTH = 100


@dataclass
class TileAction:
    """Represents a single tile change for undo/redo."""
    x: int
    y: int
    old_tile_id: str
    new_tile_id: str


@dataclass
class ActionGroup:
    """A group of tile actions (e.g., from a single brush stroke)."""
    actions: list[TileAction]
    
    def is_empty(self) -> bool:
        return len(self.actions) == 0
