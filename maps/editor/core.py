"""MapEditor core class - combines all mixins."""
from __future__ import annotations

from typing import Optional

import pygame

from .constants import (
    TileAction, ActionGroup, TILE_SIZE, PALETTE_WIDTH,
    AUTOSAVE_INTERVAL
)
from .input import InputMixin
from .tools import ToolsMixin
from .modes import ModesMixin
from .rendering import RenderingMixin

from ..map_grid import MapGrid
from ..registry import get_tile, list_tiles, list_themes, get_theme_tiles
from ..spawn_point import SpawnPoint


class MapEditor(InputMixin, ToolsMixin, ModesMixin, RenderingMixin):
    """Interactive map editor.
    
    Handles tile placement, palette selection, and map saving.
    Uses mixins for organization:
    - InputMixin: handle_event, keyboard/mouse handling
    - ToolsMixin: undo/redo, paint, fill, eyedropper, save
    - ModesMixin: naming, resize, spawn point modes
    - RenderingMixin: all render methods
    """
    
    def __init__(
        self,
        screen_width: int = 1280,
        screen_height: int = 720,
        map_width: int = 40,
        map_height: int = 22,
    ):
        """Initialize the map editor."""
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        # Create blank map
        self.map_grid = MapGrid(
            name="new_map",
            width=map_width,
            height=map_height,
            theme="default",
        )
        
        # Editor state
        self.selected_tile_id: str = "floor"
        self.camera_x: float = 0.0
        self.camera_y: float = 0.0
        self.current_theme_idx: int = 0
        self.themes = list_themes()
        
        # UI state
        self.show_grid: bool = True
        self.show_help: bool = True
        self.status_message: str = "Map Editor - Press H for help"
        self.status_timer: float = 0.0
        
        # Undo/redo stacks
        self._undo_stack: list[ActionGroup] = []
        self._redo_stack: list[ActionGroup] = []
        self._current_stroke: list[TileAction] = []
        self._is_painting: bool = False
        
        # Brush settings
        self.brush_size: int = 1
        self.max_brush_size: int = 5
        
        # Name input mode
        self._naming_mode: bool = False
        self._name_input: str = ""
        self._save_after_naming: bool = False  # True when in "Save As" mode
        
        # Autosave state
        self._autosave_timer: float = AUTOSAVE_INTERVAL
        self._has_unsaved_changes: bool = False
        self._last_autosave_action_count: int = 0
        
        # Resize mode
        self._resize_mode: bool = False
        self._resize_field: int = 0
        self._resize_width: str = ""
        self._resize_height: str = ""
        self._resize_anchor_idx: int = 0
        self._resize_anchors = ["top_left", "center", "top_right", "bottom_left", "bottom_right"]
        
        # Spawn editing mode
        self._spawn_mode: bool = False
        self._spawn_edit_mode: bool = False
        self._selected_spawn: Optional[SpawnPoint] = None
        self._spawn_pool_input: str = ""
        self._available_enemies: list[str] = []
        self._load_enemy_types()
        
        # Get available tiles for current theme
        self.palette_tiles: list = []
        self._update_palette()
    
    def _load_enemy_types(self) -> None:
        """Load available enemy types for spawn pools."""
        from ..spawn_point import get_available_enemy_types
        self._available_enemies = get_available_enemy_types()
    
    def _update_palette(self) -> None:
        """Update the tile palette based on current theme."""
        if self.themes:
            theme = self.themes[self.current_theme_idx]
            self.palette_tiles = get_theme_tiles(theme)
            self.map_grid.theme = theme
        else:
            self.palette_tiles = list_tiles()
        
        if self.palette_tiles and self.selected_tile_id not in [t.id for t in self.palette_tiles]:
            self.selected_tile_id = self.palette_tiles[0].id
    
    def _cycle_theme(self) -> None:
        """Cycle to the next theme."""
        if not self.themes:
            return
        
        self.current_theme_idx = (self.current_theme_idx + 1) % len(self.themes)
        self._update_palette()
        theme = self.themes[self.current_theme_idx]
        self._set_status(f"Theme: {theme}")
    
    def _set_status(self, message: str) -> None:
        """Set a status message."""
        self.status_message = message
        self.status_timer = 3.0
    
    def update(self, dt: float) -> None:
        """Update editor state."""
        # Don't paint during special modes
        if self._naming_mode or self._resize_mode or self._spawn_edit_mode or self._spawn_mode:
            if self.status_timer > 0:
                self.status_timer -= dt
            return
        
        # Handle held mouse buttons for continuous painting
        buttons = pygame.mouse.get_pressed()
        mods = pygame.key.get_mods()
        
        if mods & pygame.KMOD_ALT:
            if self._is_painting:
                self._end_stroke()
        elif buttons[0] or buttons[2]:
            mx, my = pygame.mouse.get_pos()
            if mx < self.screen_width - PALETTE_WIDTH:
                world_x = mx + self.camera_x
                world_y = my + self.camera_y
                tx = int(world_x // TILE_SIZE)
                ty = int(world_y // TILE_SIZE)
                
                if not self._is_painting:
                    self._begin_stroke()
                
                if buttons[0]:
                    self._paint_with_brush(tx, ty, self.selected_tile_id)
                elif buttons[2]:
                    self._paint_with_brush(tx, ty, "floor")
        else:
            if self._is_painting:
                self._end_stroke()
        
        if self.status_timer > 0:
            self.status_timer -= dt
        
        self._update_autosave(dt)
