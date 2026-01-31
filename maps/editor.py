"""Map editor - backwards compatibility import.

The editor has been split into the maps/editor/ package for better organization.
This file provides backward compatibility for existing imports.
"""
# Re-export from the new package location
from .editor import (
    MapEditor,
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
