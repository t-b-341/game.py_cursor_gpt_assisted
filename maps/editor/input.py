"""Editor input handling."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from .constants import TILE_SIZE, PALETTE_WIDTH

if TYPE_CHECKING:
    from .core import MapEditor


class InputMixin:
    """Mixin providing editor input handling."""
    
    def handle_event(self: "MapEditor", event: pygame.event.Event) -> bool:
        """Handle a pygame event. Returns True if editor should quit."""
        if event.type == pygame.QUIT:
            return True
        
        if event.type == pygame.KEYDOWN:
            return self._handle_keydown(event)
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_mouse_click(event)
        
        return False
    
    def _handle_keydown(self: "MapEditor", event: pygame.event.Event) -> bool:
        """Handle keyboard input."""
        key = event.key
        
        # Handle special modes
        if self._naming_mode:
            return self._handle_naming_input(event)
        
        if self._resize_mode:
            return self._handle_resize_input(event)
        
        if self._spawn_edit_mode:
            return self._handle_spawn_edit_input(event)
        
        # Quit or exit spawn mode
        if key == pygame.K_ESCAPE:
            if self._spawn_mode:
                self._spawn_mode = False
                self._selected_spawn = None
                self._set_status("Spawn mode OFF")
                return False
            return True
        
        # Save
        if key == pygame.K_s and not (pygame.key.get_mods() & pygame.KMOD_CTRL):
            self._save_map()
        
        # Toggle grid
        if key == pygame.K_g:
            self.show_grid = not self.show_grid
            self._set_status("Grid: " + ("ON" if self.show_grid else "OFF"))
        
        # Toggle help
        if key == pygame.K_h:
            self.show_help = not self.show_help
        
        # Cycle theme
        if key == pygame.K_t:
            self._cycle_theme()
        
        # Rename map
        if key == pygame.K_n:
            self._start_naming_mode()
        
        # Toggle spawn mode
        if key == pygame.K_m:
            self._spawn_mode = not self._spawn_mode
            self._selected_spawn = None
            mode_str = "ON (click to place, right-click to remove)" if self._spawn_mode else "OFF"
            self._set_status(f"Spawn mode: {mode_str}")
        
        # Set player spawn in spawn mode
        if key == pygame.K_p and self._spawn_mode:
            self._place_player_spawn_at_cursor()
        
        # Number keys for palette selection
        if pygame.K_1 <= key <= pygame.K_9:
            idx = key - pygame.K_1
            if idx < len(self.palette_tiles):
                self.selected_tile_id = self.palette_tiles[idx].id
                self._set_status(f"Selected: {self.selected_tile_id}")
        
        # Camera movement
        cam_speed = 64
        if key == pygame.K_LEFT:
            self.camera_x = max(0, self.camera_x - cam_speed)
        if key == pygame.K_RIGHT:
            self.camera_x += cam_speed
        if key == pygame.K_UP:
            self.camera_y = max(0, self.camera_y - cam_speed)
        if key == pygame.K_DOWN:
            self.camera_y += cam_speed
        
        # Brush size controls
        if key == pygame.K_LEFTBRACKET:
            self.brush_size = max(1, self.brush_size - 1)
            self._set_status(f"Brush size: {self.brush_size}")
        if key == pygame.K_RIGHTBRACKET:
            self.brush_size = min(self.max_brush_size, self.brush_size + 1)
            self._set_status(f"Brush size: {self.brush_size}")
        
        # Flood fill
        if key == pygame.K_f and not (pygame.key.get_mods() & pygame.KMOD_CTRL):
            self._flood_fill_at_cursor()
        
        # Fill map with selected tile
        if key == pygame.K_f and pygame.key.get_mods() & pygame.KMOD_CTRL:
            self._fill_map_with_undo(self.selected_tile_id)
            self._set_status(f"Filled map with {self.selected_tile_id}")
        
        # Undo
        if key == pygame.K_z and pygame.key.get_mods() & pygame.KMOD_CTRL:
            if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                self._redo()
            else:
                self._undo()
        
        # Redo
        if key == pygame.K_y and pygame.key.get_mods() & pygame.KMOD_CTRL:
            self._redo()
        
        # Resize map
        if key == pygame.K_r and pygame.key.get_mods() & pygame.KMOD_CTRL:
            self._start_resize_mode()
        
        return False
    
    def _handle_mouse_click(self: "MapEditor", event: pygame.event.Event) -> None:
        """Handle mouse click for tile placement."""
        mx, my = event.pos
        
        # Check if click is in palette area
        if mx > self.screen_width - PALETTE_WIDTH:
            self._handle_palette_click(mx, my)
            return
        
        # Convert to tile coordinates
        world_x = mx + self.camera_x
        world_y = my + self.camera_y
        tx = int(world_x // TILE_SIZE)
        ty = int(world_y // TILE_SIZE)
        
        # Check for eyedropper
        mods = pygame.key.get_mods()
        if mods & pygame.KMOD_ALT or event.button == 2:
            self._eyedropper(tx, ty)
            return
        
        # Handle spawn mode clicks
        if self._spawn_mode:
            if event.button == 1:
                self._place_spawn_point(tx, ty)
            elif event.button == 3:
                self._remove_spawn_point(tx, ty)
            return
        
        # Begin brush stroke
        self._begin_stroke()
        
        if event.button == 1:
            self._paint_with_brush(tx, ty, self.selected_tile_id)
        elif event.button == 3:
            self._paint_with_brush(tx, ty, "floor")
    
    def _handle_palette_click(self: "MapEditor", mx: int, my: int) -> None:
        """Handle click in the palette area."""
        from .constants import PALETTE_TILE_SIZE, PALETTE_PADDING
        
        tile_idx = my // (PALETTE_TILE_SIZE + PALETTE_PADDING)
        
        if 0 <= tile_idx < len(self.palette_tiles):
            self.selected_tile_id = self.palette_tiles[tile_idx].id
            self._set_status(f"Selected: {self.selected_tile_id}")
