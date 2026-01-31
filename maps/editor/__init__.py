"""Map editor package - modular editor for tile-based maps.

This package provides the MapEditor class split into logical modules:
- core.py: Main MapEditor class with state and lifecycle
- input.py: Event handling (keyboard, mouse)
- tools.py: Undo/redo, paint, fill, eyedropper, save
- modes.py: Special modes (naming, resize, spawn)
- rendering.py: All rendering methods
- constants.py: Shared constants and data classes
"""

from .core import MapEditor
from .constants import (
    TILE_SIZE,
    PALETTE_WIDTH,
    PALETTE_TILE_SIZE,
    PALETTE_PADDING,
    MAX_UNDO_HISTORY,
    AUTOSAVE_INTERVAL,
    TileAction,
    ActionGroup,
)

__all__ = [
    "MapEditor",
    "TILE_SIZE",
    "PALETTE_WIDTH",
    "PALETTE_TILE_SIZE",
    "PALETTE_PADDING",
    "MAX_UNDO_HISTORY",
    "AUTOSAVE_INTERVAL",
    "TileAction",
    "ActionGroup",
]
