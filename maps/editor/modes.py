"""Editor modes: naming, resize, spawn point editing."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from .constants import TILE_SIZE, PALETTE_WIDTH, MAX_MAP_SIZE
from ..spawn_point import SpawnPoint, ENEMY_POOLS

if TYPE_CHECKING:
    from .core import MapEditor


class ModesMixin:
    """Mixin providing editor special modes: naming, resize, spawn."""
    
    # =========================================================================
    # MAP NAMING
    # =========================================================================
    
    def _start_naming_mode(self: "MapEditor") -> None:
        """Enter name input mode."""
        self._naming_mode = True
        self._name_input = self.map_grid.name
        self._set_status("Enter map name (ENTER to confirm, ESC to cancel)")
    
    def _handle_naming_input(self: "MapEditor", event: pygame.event.Event) -> bool:
        """Handle keyboard input during naming mode."""
        key = event.key
        
        if key == pygame.K_ESCAPE:
            self._naming_mode = False
            self._name_input = ""
            self._set_status("Rename cancelled")
            return False
        
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            new_name = self._name_input.strip()
            if new_name:
                self.map_grid.name = new_name
                self._set_status(f"Map renamed to: {new_name}")
            else:
                self._set_status("Name cannot be empty")
            self._naming_mode = False
            self._name_input = ""
            return False
        
        if key == pygame.K_BACKSPACE:
            self._name_input = self._name_input[:-1]
            return False
        
        if event.unicode and event.unicode.isprintable() and len(self._name_input) < 30:
            char = event.unicode
            if char not in r'\/:*?"<>|':
                self._name_input += char
        
        return False
    
    # =========================================================================
    # MAP RESIZE
    # =========================================================================
    
    def _start_resize_mode(self: "MapEditor") -> None:
        """Enter resize input mode."""
        self._resize_mode = True
        self._resize_field = 0
        self._resize_width = str(self.map_grid.width)
        self._resize_height = str(self.map_grid.height)
        self._resize_anchor_idx = 0
        self._set_status("Enter new size (TAB to switch fields, ENTER to confirm)")
    
    def _handle_resize_input(self: "MapEditor", event: pygame.event.Event) -> bool:
        """Handle keyboard input during resize mode."""
        key = event.key
        
        if key == pygame.K_ESCAPE:
            self._resize_mode = False
            self._set_status("Resize cancelled")
            return False
        
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._apply_resize()
            return False
        
        if key == pygame.K_TAB:
            self._resize_field = (self._resize_field + 1) % 3
            return False
        
        if key == pygame.K_BACKSPACE:
            if self._resize_field == 0:
                self._resize_width = self._resize_width[:-1]
            elif self._resize_field == 1:
                self._resize_height = self._resize_height[:-1]
            return False
        
        if self._resize_field == 2:
            if key in (pygame.K_LEFT, pygame.K_UP):
                self._resize_anchor_idx = (self._resize_anchor_idx - 1) % len(self._resize_anchors)
            elif key in (pygame.K_RIGHT, pygame.K_DOWN):
                self._resize_anchor_idx = (self._resize_anchor_idx + 1) % len(self._resize_anchors)
            return False
        
        if event.unicode and event.unicode.isdigit():
            if self._resize_field == 0 and len(self._resize_width) < 4:
                self._resize_width += event.unicode
            elif self._resize_field == 1 and len(self._resize_height) < 4:
                self._resize_height += event.unicode
        
        return False
    
    def _apply_resize(self: "MapEditor") -> None:
        """Apply the resize operation."""
        try:
            new_width = int(self._resize_width) if self._resize_width else self.map_grid.width
            new_height = int(self._resize_height) if self._resize_height else self.map_grid.height
        except ValueError:
            self._set_status("Invalid size values")
            self._resize_mode = False
            return
        
        if new_width < 1 or new_width > MAX_MAP_SIZE:
            self._set_status(f"Width must be 1-{MAX_MAP_SIZE}")
            self._resize_mode = False
            return
        if new_height < 1 or new_height > MAX_MAP_SIZE:
            self._set_status(f"Height must be 1-{MAX_MAP_SIZE}")
            self._resize_mode = False
            return
        
        if new_width == self.map_grid.width and new_height == self.map_grid.height:
            self._set_status("Size unchanged")
            self._resize_mode = False
            return
        
        old_size = f"{self.map_grid.width}x{self.map_grid.height}"
        anchor = self._resize_anchors[self._resize_anchor_idx]
        
        self.map_grid.resize(new_width, new_height, anchor=anchor, default_tile="floor")
        
        self._undo_stack.clear()
        self._redo_stack.clear()
        
        # Reset camera to origin to show resized map
        self.camera_x = 0.0
        self.camera_y = 0.0
        
        self._resize_mode = False
        self._set_status(f"Resized {old_size} -> {new_width}x{new_height} (anchor: {anchor})")
    
    # =========================================================================
    # SPAWN POINT EDITING
    # =========================================================================
    
    def _place_spawn_point(self: "MapEditor", tx: int, ty: int) -> None:
        """Place or select a spawn point at the given tile."""
        existing = self.map_grid.get_spawn_point_at(tx, ty)
        if existing:
            self._selected_spawn = existing
            self._start_spawn_edit()
        else:
            spawn = SpawnPoint(x=tx, y=ty, enemy_pool=["grunt"])
            self.map_grid.add_spawn_point(spawn)
            self._selected_spawn = spawn
            self._set_status(f"Spawn point added at ({tx}, {ty}) - click to edit pool")
    
    def _remove_spawn_point(self: "MapEditor", tx: int, ty: int) -> None:
        """Remove spawn point at the given tile."""
        if self.map_grid.remove_spawn_point_at(tx, ty):
            self._set_status(f"Spawn point removed at ({tx}, {ty})")
            if self._selected_spawn and self._selected_spawn.x == tx and self._selected_spawn.y == ty:
                self._selected_spawn = None
        else:
            self._set_status("No spawn point here")
    
    def _place_player_spawn_at_cursor(self: "MapEditor") -> None:
        """Set player spawn at cursor position."""
        mx, my = pygame.mouse.get_pos()
        if mx >= self.screen_width - PALETTE_WIDTH:
            self._set_status("Move cursor to map area")
            return
        
        world_x = mx + self.camera_x
        world_y = my + self.camera_y
        tx = int(world_x // TILE_SIZE)
        ty = int(world_y // TILE_SIZE)
        
        self.map_grid.player_spawn = (tx, ty)
        self._set_status(f"Player spawn set at ({tx}, {ty})")
    
    def _start_spawn_edit(self: "MapEditor") -> None:
        """Start editing the selected spawn point's enemy pool."""
        if not self._selected_spawn:
            return
        self._spawn_edit_mode = True
        self._spawn_pool_input = ",".join(self._selected_spawn.enemy_pool)
        self._set_status("Edit pool: type enemy names separated by commas")
    
    def _handle_spawn_edit_input(self: "MapEditor", event: pygame.event.Event) -> bool:
        """Handle keyboard input during spawn pool editing."""
        key = event.key
        
        if key == pygame.K_ESCAPE:
            self._spawn_edit_mode = False
            self._set_status("Spawn edit cancelled")
            return False
        
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._apply_spawn_pool_edit()
            return False
        
        if key == pygame.K_BACKSPACE:
            self._spawn_pool_input = self._spawn_pool_input[:-1]
            return False
        
        if event.unicode and event.unicode.isprintable() and len(self._spawn_pool_input) < 100:
            self._spawn_pool_input += event.unicode
        
        return False
    
    def _apply_spawn_pool_edit(self: "MapEditor") -> None:
        """Apply the edited enemy pool to the selected spawn point."""
        if not self._selected_spawn:
            self._spawn_edit_mode = False
            return
        
        pool = [t.strip() for t in self._spawn_pool_input.split(",") if t.strip()]
        
        valid_pool = []
        invalid = []
        for enemy_type in pool:
            if enemy_type in self._available_enemies:
                valid_pool.append(enemy_type)
            elif enemy_type in ENEMY_POOLS:
                valid_pool.extend(ENEMY_POOLS[enemy_type])
            else:
                invalid.append(enemy_type)
        
        if not valid_pool:
            self._set_status(f"No valid enemies. Available: {', '.join(self._available_enemies[:5])}...")
            self._spawn_edit_mode = False
            return
        
        self._selected_spawn.enemy_pool = list(set(valid_pool))
        self._spawn_edit_mode = False
        
        if invalid:
            self._set_status(f"Pool set (unknown: {', '.join(invalid)})")
        else:
            self._set_status(f"Pool set: {', '.join(self._selected_spawn.enemy_pool)}")
