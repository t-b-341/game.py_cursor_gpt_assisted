"""Map editor logic - handles editor state and rendering."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pygame

from .map_grid import MapGrid
from .map_saver import save_map
from .registry import get_tile, list_tiles, list_themes, get_theme_tiles
from .spawn_point import SpawnPoint, ENEMY_POOLS


# Editor constants
TILE_SIZE = 64
PALETTE_WIDTH = 200
PALETTE_TILE_SIZE = 48
PALETTE_PADDING = 8
MAX_UNDO_HISTORY = 100  # Maximum number of undo steps


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


class MapEditor:
    """Interactive map editor.
    
    Handles tile placement, palette selection, and map saving.
    """
    
    def __init__(
        self,
        screen_width: int = 1280,
        screen_height: int = 720,
        map_width: int = 40,
        map_height: int = 22,
    ):
        """Initialize the map editor.
        
        Args:
            screen_width: Editor window width
            screen_height: Editor window height
            map_width: Map grid width in tiles
            map_height: Map grid height in tiles
        """
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
        self._current_stroke: list[TileAction] = []  # Actions in current brush stroke
        self._is_painting: bool = False  # Track if we're in a brush stroke
        
        # Brush settings
        self.brush_size: int = 1  # Brush size in tiles (1 = single tile)
        self.max_brush_size: int = 5
        
        # Name input mode
        self._naming_mode: bool = False
        self._name_input: str = ""
        
        # Resize mode
        self._resize_mode: bool = False
        self._resize_field: int = 0  # 0 = width, 1 = height, 2 = anchor
        self._resize_width: str = ""
        self._resize_height: str = ""
        self._resize_anchor_idx: int = 0
        self._resize_anchors = ["top_left", "center", "top_right", "bottom_left", "bottom_right"]
        
        # Spawn editing mode
        self._spawn_mode: bool = False  # Toggle with M key
        self._spawn_edit_mode: bool = False  # Editing a spawn point's pool
        self._selected_spawn: "SpawnPoint | None" = None
        self._spawn_pool_input: str = ""
        self._available_enemies: list[str] = []
        self._load_enemy_types()
        
        # Get available tiles for current theme
        self._update_palette()
    
    def _load_enemy_types(self) -> None:
        """Load available enemy types for spawn pools."""
        from .spawn_point import get_available_enemy_types
        self._available_enemies = get_available_enemy_types()
    
    def _update_palette(self) -> None:
        """Update the tile palette based on current theme."""
        if self.themes:
            theme = self.themes[self.current_theme_idx]
            self.palette_tiles = get_theme_tiles(theme)
            self.map_grid.theme = theme
        else:
            self.palette_tiles = list_tiles()
        
        # Ensure selected tile is valid
        if self.palette_tiles and self.selected_tile_id not in [t.id for t in self.palette_tiles]:
            self.selected_tile_id = self.palette_tiles[0].id
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle a pygame event.
        
        Args:
            event: Pygame event to handle
            
        Returns:
            True if editor should quit
        """
        if event.type == pygame.QUIT:
            return True
        
        if event.type == pygame.KEYDOWN:
            return self._handle_keydown(event)
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_mouse_click(event)
        
        return False
    
    def _handle_keydown(self, event: pygame.event.Event) -> bool:
        """Handle keyboard input."""
        key = event.key
        
        # Handle name input mode separately
        if self._naming_mode:
            return self._handle_naming_input(event)
        
        # Handle resize mode separately
        if self._resize_mode:
            return self._handle_resize_input(event)
        
        # Handle spawn edit mode separately
        if self._spawn_edit_mode:
            return self._handle_spawn_edit_input(event)
        
        # Quit (or exit spawn mode)
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
        
        # Rename map (N key)
        if key == pygame.K_n:
            self._start_naming_mode()
        
        # Toggle spawn mode (M key)
        if key == pygame.K_m:
            self._spawn_mode = not self._spawn_mode
            self._selected_spawn = None
            mode_str = "ON (click to place, right-click to remove)" if self._spawn_mode else "OFF"
            self._set_status(f"Spawn mode: {mode_str}")
        
        # Set player spawn (P key in spawn mode)
        if key == pygame.K_p and self._spawn_mode:
            self._place_player_spawn_at_cursor()
        
        # Number keys for palette selection (only when not in spawn mode)
        if pygame.K_1 <= key <= pygame.K_9:
            idx = key - pygame.K_1
            if idx < len(self.palette_tiles):
                self.selected_tile_id = self.palette_tiles[idx].id
                self._set_status(f"Selected: {self.selected_tile_id}")
        
        # Camera movement (arrow keys)
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
        if key == pygame.K_LEFTBRACKET:  # [ key - decrease brush
            self.brush_size = max(1, self.brush_size - 1)
            self._set_status(f"Brush size: {self.brush_size}")
        if key == pygame.K_RIGHTBRACKET:  # ] key - increase brush
            self.brush_size = min(self.max_brush_size, self.brush_size + 1)
            self._set_status(f"Brush size: {self.brush_size}")
        
        # Flood fill (F key without Ctrl)
        if key == pygame.K_f and not (pygame.key.get_mods() & pygame.KMOD_CTRL):
            self._flood_fill_at_cursor()
        
        # Fill map with selected tile (Ctrl+F)
        if key == pygame.K_f and pygame.key.get_mods() & pygame.KMOD_CTRL:
            self._fill_map_with_undo(self.selected_tile_id)
            self._set_status(f"Filled map with {self.selected_tile_id}")
        
        # Undo (Ctrl+Z)
        if key == pygame.K_z and pygame.key.get_mods() & pygame.KMOD_CTRL:
            if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                # Ctrl+Shift+Z = Redo
                self._redo()
            else:
                self._undo()
        
        # Redo (Ctrl+Y)
        if key == pygame.K_y and pygame.key.get_mods() & pygame.KMOD_CTRL:
            self._redo()
        
        # Resize map (Ctrl+R)
        if key == pygame.K_r and pygame.key.get_mods() & pygame.KMOD_CTRL:
            self._start_resize_mode()
        
        return False
    
    def _fill_map_with_undo(self, tile_id: str) -> None:
        """Fill the entire map with a tile, recording for undo."""
        self._begin_stroke()
        for y in range(self.map_grid.height):
            for x in range(self.map_grid.width):
                self._place_tile_with_undo(x, y, tile_id)
        self._end_stroke()
    
    def _handle_mouse_click(self, event: pygame.event.Event) -> None:
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
        
        # Check for eyedropper (Alt+click or middle click)
        mods = pygame.key.get_mods()
        if mods & pygame.KMOD_ALT or event.button == 2:
            self._eyedropper(tx, ty)
            return
        
        # Handle spawn mode clicks
        if self._spawn_mode:
            if event.button == 1:  # Left click - place/select spawn
                self._place_spawn_point(tx, ty)
            elif event.button == 3:  # Right click - remove spawn
                self._remove_spawn_point(tx, ty)
            return
        
        # Begin brush stroke
        self._begin_stroke()
        
        if event.button == 1:  # Left click - place tile
            self._paint_with_brush(tx, ty, self.selected_tile_id)
        elif event.button == 3:  # Right click - erase (place floor)
            self._paint_with_brush(tx, ty, "floor")
    
    def _handle_palette_click(self, mx: int, my: int) -> None:
        """Handle click in the palette area."""
        palette_x = mx - (self.screen_width - PALETTE_WIDTH)
        
        # Calculate which tile was clicked
        tile_idx = my // (PALETTE_TILE_SIZE + PALETTE_PADDING)
        
        if 0 <= tile_idx < len(self.palette_tiles):
            self.selected_tile_id = self.palette_tiles[tile_idx].id
            self._set_status(f"Selected: {self.selected_tile_id}")
    
    def _cycle_theme(self) -> None:
        """Cycle to the next theme."""
        if not self.themes:
            return
        
        self.current_theme_idx = (self.current_theme_idx + 1) % len(self.themes)
        self._update_palette()
        theme = self.themes[self.current_theme_idx]
        self._set_status(f"Theme: {theme}")
    
    def _save_map(self) -> None:
        """Save the current map."""
        filename = self.map_grid.name
        if save_map(self.map_grid, filename):
            self._set_status(f"Saved: {filename}.json")
        else:
            self._set_status("Error saving map!")
    
    def _set_status(self, message: str) -> None:
        """Set a status message."""
        self.status_message = message
        self.status_timer = 3.0
    
    # =========================================================================
    # UNDO/REDO SYSTEM
    # =========================================================================
    
    def _place_tile_with_undo(self, tx: int, ty: int, new_tile_id: str) -> bool:
        """Place a tile and record the action for undo.
        
        Returns True if the tile was changed, False if it was already that tile.
        """
        old_tile_id = self.map_grid.get_tile_id(tx, ty)
        if old_tile_id is None or old_tile_id == new_tile_id:
            return False  # No change needed
        
        # Record the action
        action = TileAction(x=tx, y=ty, old_tile_id=old_tile_id, new_tile_id=new_tile_id)
        self._current_stroke.append(action)
        
        # Apply the change
        self.map_grid.set_tile_id(tx, ty, new_tile_id)
        return True
    
    def _begin_stroke(self) -> None:
        """Begin a new brush stroke (for grouping undo actions)."""
        if not self._is_painting:
            self._is_painting = True
            self._current_stroke = []
    
    def _end_stroke(self) -> None:
        """End the current brush stroke and commit to undo stack."""
        if self._is_painting and self._current_stroke:
            # Create action group and add to undo stack
            group = ActionGroup(actions=self._current_stroke.copy())
            self._undo_stack.append(group)
            
            # Limit undo history size
            while len(self._undo_stack) > MAX_UNDO_HISTORY:
                self._undo_stack.pop(0)
            
            # Clear redo stack (new action invalidates redo history)
            self._redo_stack.clear()
        
        self._current_stroke = []
        self._is_painting = False
    
    def _undo(self) -> None:
        """Undo the last action group."""
        if not self._undo_stack:
            self._set_status("Nothing to undo")
            return
        
        group = self._undo_stack.pop()
        
        # Apply actions in reverse order
        for action in reversed(group.actions):
            self.map_grid.set_tile_id(action.x, action.y, action.old_tile_id)
        
        # Add to redo stack
        self._redo_stack.append(group)
        
        self._set_status(f"Undo ({len(group.actions)} tiles)")
    
    def _redo(self) -> None:
        """Redo the last undone action group."""
        if not self._redo_stack:
            self._set_status("Nothing to redo")
            return
        
        group = self._redo_stack.pop()
        
        # Apply actions in forward order
        for action in group.actions:
            self.map_grid.set_tile_id(action.x, action.y, action.new_tile_id)
        
        # Add back to undo stack
        self._undo_stack.append(group)
        
        self._set_status(f"Redo ({len(group.actions)} tiles)")
    
    # =========================================================================
    # EYEDROPPER TOOL
    # =========================================================================
    
    def _eyedropper(self, tx: int, ty: int) -> bool:
        """Pick the tile at the given coordinates.
        
        Returns True if a tile was picked.
        """
        tile_id = self.map_grid.get_tile_id(tx, ty)
        if tile_id:
            self.selected_tile_id = tile_id
            self._set_status(f"Picked: {tile_id}")
            return True
        return False
    
    # =========================================================================
    # MAP NAMING
    # =========================================================================
    
    def _start_naming_mode(self) -> None:
        """Enter name input mode."""
        self._naming_mode = True
        self._name_input = self.map_grid.name
        self._set_status("Enter map name (ENTER to confirm, ESC to cancel)")
    
    def _handle_naming_input(self, event: pygame.event.Event) -> bool:
        """Handle keyboard input during naming mode."""
        key = event.key
        
        if key == pygame.K_ESCAPE:
            # Cancel naming
            self._naming_mode = False
            self._name_input = ""
            self._set_status("Rename cancelled")
            return False
        
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            # Confirm name
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
        
        # Add printable characters
        if event.unicode and event.unicode.isprintable() and len(self._name_input) < 30:
            # Filter out characters that are problematic for filenames
            char = event.unicode
            if char not in r'\/:*?"<>|':
                self._name_input += char
        
        return False
    
    # =========================================================================
    # MAP RESIZE
    # =========================================================================
    
    def _start_resize_mode(self) -> None:
        """Enter resize input mode."""
        self._resize_mode = True
        self._resize_field = 0  # Start at width field
        self._resize_width = str(self.map_grid.width)
        self._resize_height = str(self.map_grid.height)
        self._resize_anchor_idx = 0
        self._set_status("Enter new size (TAB to switch fields, ENTER to confirm)")
    
    def _handle_resize_input(self, event: pygame.event.Event) -> bool:
        """Handle keyboard input during resize mode."""
        key = event.key
        
        if key == pygame.K_ESCAPE:
            # Cancel resize
            self._resize_mode = False
            self._set_status("Resize cancelled")
            return False
        
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            # Confirm resize
            self._apply_resize()
            return False
        
        if key == pygame.K_TAB:
            # Cycle through fields (width -> height -> anchor -> width)
            self._resize_field = (self._resize_field + 1) % 3
            return False
        
        if key == pygame.K_BACKSPACE:
            if self._resize_field == 0:
                self._resize_width = self._resize_width[:-1]
            elif self._resize_field == 1:
                self._resize_height = self._resize_height[:-1]
            return False
        
        # Handle anchor selection with arrow keys
        if self._resize_field == 2:
            if key in (pygame.K_LEFT, pygame.K_UP):
                self._resize_anchor_idx = (self._resize_anchor_idx - 1) % len(self._resize_anchors)
            elif key in (pygame.K_RIGHT, pygame.K_DOWN):
                self._resize_anchor_idx = (self._resize_anchor_idx + 1) % len(self._resize_anchors)
            return False
        
        # Add digit characters to width/height
        if event.unicode and event.unicode.isdigit():
            if self._resize_field == 0 and len(self._resize_width) < 4:
                self._resize_width += event.unicode
            elif self._resize_field == 1 and len(self._resize_height) < 4:
                self._resize_height += event.unicode
        
        return False
    
    def _apply_resize(self) -> None:
        """Apply the resize operation."""
        try:
            new_width = int(self._resize_width) if self._resize_width else self.map_grid.width
            new_height = int(self._resize_height) if self._resize_height else self.map_grid.height
        except ValueError:
            self._set_status("Invalid size values")
            self._resize_mode = False
            return
        
        # Validate bounds
        if new_width < 1 or new_width > 200:
            self._set_status("Width must be 1-200")
            self._resize_mode = False
            return
        if new_height < 1 or new_height > 200:
            self._set_status("Height must be 1-200")
            self._resize_mode = False
            return
        
        # Check if size actually changed
        if new_width == self.map_grid.width and new_height == self.map_grid.height:
            self._set_status("Size unchanged")
            self._resize_mode = False
            return
        
        # Store old state for info message
        old_size = f"{self.map_grid.width}x{self.map_grid.height}"
        anchor = self._resize_anchors[self._resize_anchor_idx]
        
        # Apply resize
        self.map_grid.resize(new_width, new_height, anchor=anchor, default_tile="floor")
        
        # Clear undo/redo (resize is not undoable for simplicity)
        self._undo_stack.clear()
        self._redo_stack.clear()
        
        self._resize_mode = False
        self._set_status(f"Resized {old_size} -> {new_width}x{new_height} (anchor: {anchor})")
    
    # =========================================================================
    # FLOOD FILL
    # =========================================================================
    
    def _flood_fill_at_cursor(self) -> None:
        """Flood fill at the current mouse position."""
        mx, my = pygame.mouse.get_pos()
        
        # Check if mouse is in map area
        if mx >= self.screen_width - PALETTE_WIDTH:
            self._set_status("Move cursor to map area to fill")
            return
        
        # Convert to tile coordinates
        world_x = mx + self.camera_x
        world_y = my + self.camera_y
        tx = int(world_x // TILE_SIZE)
        ty = int(world_y // TILE_SIZE)
        
        self._flood_fill(tx, ty, self.selected_tile_id)
    
    def _flood_fill(self, start_x: int, start_y: int, fill_tile_id: str) -> None:
        """Flood fill starting from a position.
        
        Uses breadth-first search to fill connected tiles of the same type.
        """
        target_tile_id = self.map_grid.get_tile_id(start_x, start_y)
        
        if target_tile_id is None:
            return
        
        if target_tile_id == fill_tile_id:
            self._set_status("Already filled with this tile")
            return
        
        # BFS flood fill
        self._begin_stroke()
        
        visited = set()
        queue = [(start_x, start_y)]
        filled_count = 0
        max_fill = 10000  # Safety limit
        
        while queue and filled_count < max_fill:
            x, y = queue.pop(0)
            
            if (x, y) in visited:
                continue
            
            if x < 0 or x >= self.map_grid.width or y < 0 or y >= self.map_grid.height:
                continue
            
            current_tile = self.map_grid.get_tile_id(x, y)
            if current_tile != target_tile_id:
                continue
            
            visited.add((x, y))
            
            if self._place_tile_with_undo(x, y, fill_tile_id):
                filled_count += 1
            
            # Add neighbors (4-directional)
            queue.append((x + 1, y))
            queue.append((x - 1, y))
            queue.append((x, y + 1))
            queue.append((x, y - 1))
        
        self._end_stroke()
        
        if filled_count > 0:
            self._set_status(f"Filled {filled_count} tiles")
        else:
            self._set_status("Nothing to fill")
    
    # =========================================================================
    # BRUSH SIZE
    # =========================================================================
    
    def _paint_with_brush(self, center_tx: int, center_ty: int, tile_id: str) -> None:
        """Paint tiles using the current brush size.
        
        Brush is centered on the given tile coordinates.
        """
        if self.brush_size == 1:
            self._place_tile_with_undo(center_tx, center_ty, tile_id)
            return
        
        # Calculate brush bounds (centered)
        half = self.brush_size // 2
        for dy in range(-half, half + 1):
            for dx in range(-half, half + 1):
                # For odd sizes, include center; for even, offset slightly
                tx = center_tx + dx
                ty = center_ty + dy
                self._place_tile_with_undo(tx, ty, tile_id)
    
    # =========================================================================
    # SPAWN POINT EDITING
    # =========================================================================
    
    def _place_spawn_point(self, tx: int, ty: int) -> None:
        """Place or select a spawn point at the given tile."""
        existing = self.map_grid.get_spawn_point_at(tx, ty)
        if existing:
            # Select existing spawn point for editing
            self._selected_spawn = existing
            self._start_spawn_edit()
        else:
            # Create new spawn point
            spawn = SpawnPoint(x=tx, y=ty, enemy_pool=["grunt"])
            self.map_grid.add_spawn_point(spawn)
            self._selected_spawn = spawn
            self._set_status(f"Spawn point added at ({tx}, {ty}) - click to edit pool")
    
    def _remove_spawn_point(self, tx: int, ty: int) -> None:
        """Remove spawn point at the given tile."""
        if self.map_grid.remove_spawn_point_at(tx, ty):
            self._set_status(f"Spawn point removed at ({tx}, {ty})")
            if self._selected_spawn and self._selected_spawn.x == tx and self._selected_spawn.y == ty:
                self._selected_spawn = None
        else:
            self._set_status("No spawn point here")
    
    def _place_player_spawn_at_cursor(self) -> None:
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
    
    def _start_spawn_edit(self) -> None:
        """Start editing the selected spawn point's enemy pool."""
        if not self._selected_spawn:
            return
        self._spawn_edit_mode = True
        self._spawn_pool_input = ",".join(self._selected_spawn.enemy_pool)
        self._set_status("Edit pool: type enemy names separated by commas")
    
    def _handle_spawn_edit_input(self, event: pygame.event.Event) -> bool:
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
        
        # Add printable characters
        if event.unicode and event.unicode.isprintable() and len(self._spawn_pool_input) < 100:
            self._spawn_pool_input += event.unicode
        
        return False
    
    def _apply_spawn_pool_edit(self) -> None:
        """Apply the edited enemy pool to the selected spawn point."""
        if not self._selected_spawn:
            self._spawn_edit_mode = False
            return
        
        # Parse comma-separated enemy types
        pool = [t.strip() for t in self._spawn_pool_input.split(",") if t.strip()]
        
        # Validate enemy types
        valid_pool = []
        invalid = []
        for enemy_type in pool:
            if enemy_type in self._available_enemies:
                valid_pool.append(enemy_type)
            elif enemy_type in ENEMY_POOLS:
                # Expand pool preset
                valid_pool.extend(ENEMY_POOLS[enemy_type])
            else:
                invalid.append(enemy_type)
        
        if not valid_pool:
            self._set_status(f"No valid enemies. Available: {', '.join(self._available_enemies[:5])}...")
            self._spawn_edit_mode = False
            return
        
        self._selected_spawn.enemy_pool = list(set(valid_pool))  # Remove duplicates
        self._spawn_edit_mode = False
        
        if invalid:
            self._set_status(f"Pool set (unknown: {', '.join(invalid)})")
        else:
            self._set_status(f"Pool set: {', '.join(self._selected_spawn.enemy_pool)}")
    
    def update(self, dt: float) -> None:
        """Update editor state.
        
        Args:
            dt: Delta time in seconds
        """
        # Don't paint during special modes
        if self._naming_mode or self._resize_mode or self._spawn_edit_mode or self._spawn_mode:
            if self.status_timer > 0:
                self.status_timer -= dt
            return
        
        # Handle held mouse buttons for continuous painting
        buttons = pygame.mouse.get_pressed()
        mods = pygame.key.get_mods()
        
        # Don't paint if Alt is held (eyedropper mode)
        if mods & pygame.KMOD_ALT:
            if self._is_painting:
                self._end_stroke()
        elif buttons[0] or buttons[2]:  # Left or right held
            mx, my = pygame.mouse.get_pos()
            if mx < self.screen_width - PALETTE_WIDTH:
                world_x = mx + self.camera_x
                world_y = my + self.camera_y
                tx = int(world_x // TILE_SIZE)
                ty = int(world_y // TILE_SIZE)
                
                # Ensure we're in a stroke
                if not self._is_painting:
                    self._begin_stroke()
                
                if buttons[0]:  # Left - place
                    self._paint_with_brush(tx, ty, self.selected_tile_id)
                elif buttons[2]:  # Right - erase
                    self._paint_with_brush(tx, ty, "floor")
        else:
            # Mouse released - end stroke
            if self._is_painting:
                self._end_stroke()
        
        # Update status timer
        if self.status_timer > 0:
            self.status_timer -= dt
    
    def render(self, screen: pygame.Surface) -> None:
        """Render the editor.
        
        Args:
            screen: Pygame surface to render to
        """
        # Clear screen
        screen.fill((30, 30, 35))
        
        # Render map
        self._render_map(screen)
        
        # Render spawn points (always, but highlighted in spawn mode)
        self._render_spawn_points(screen)
        
        # Render grid overlay
        if self.show_grid:
            self._render_grid(screen)
        
        # Render brush preview
        self._render_brush_preview(screen)
        
        # Render palette (or spawn palette in spawn mode)
        if self._spawn_mode:
            self._render_spawn_palette(screen)
        else:
            self._render_palette(screen)
        
        # Render status bar
        self._render_status(screen)
        
        # Render help overlay
        if self.show_help:
            self._render_help(screen)
        
        # Render naming overlay
        if self._naming_mode:
            self._render_naming_overlay(screen)
        
        # Render resize overlay
        if self._resize_mode:
            self._render_resize_overlay(screen)
        
        # Render spawn edit overlay
        if self._spawn_edit_mode:
            self._render_spawn_edit_overlay(screen)
    
    def _render_map(self, screen: pygame.Surface) -> None:
        """Render the map tiles."""
        map_area_width = self.screen_width - PALETTE_WIDTH
        
        start_tx = int(self.camera_x // TILE_SIZE)
        start_ty = int(self.camera_y // TILE_SIZE)
        end_tx = min(self.map_grid.width, start_tx + map_area_width // TILE_SIZE + 2)
        end_ty = min(self.map_grid.height, start_ty + self.screen_height // TILE_SIZE + 2)
        
        for ty in range(start_ty, end_ty):
            for tx in range(start_tx, end_tx):
                tile_id = self.map_grid.get_tile_id(tx, ty)
                if not tile_id:
                    continue
                
                tile = get_tile(tile_id)
                if not tile:
                    continue
                
                screen_x = int(tx * TILE_SIZE - self.camera_x)
                screen_y = int(ty * TILE_SIZE - self.camera_y)
                
                if screen_x + TILE_SIZE < 0 or screen_x > map_area_width:
                    continue
                if screen_y + TILE_SIZE < 0 or screen_y > self.screen_height:
                    continue
                
                rect = pygame.Rect(screen_x, screen_y, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(screen, tile.color, rect)
    
    def _render_grid(self, screen: pygame.Surface) -> None:
        """Render grid lines."""
        map_area_width = self.screen_width - PALETTE_WIDTH
        grid_color = (50, 50, 55)
        
        # Vertical lines
        offset_x = int(self.camera_x % TILE_SIZE)
        for x in range(-offset_x, map_area_width, TILE_SIZE):
            pygame.draw.line(screen, grid_color, (x, 0), (x, self.screen_height))
        
        # Horizontal lines
        offset_y = int(self.camera_y % TILE_SIZE)
        for y in range(-offset_y, self.screen_height, TILE_SIZE):
            pygame.draw.line(screen, grid_color, (0, y), (map_area_width, y))
    
    def _render_palette(self, screen: pygame.Surface) -> None:
        """Render the tile palette."""
        palette_x = self.screen_width - PALETTE_WIDTH
        
        # Background
        pygame.draw.rect(
            screen,
            (40, 40, 45),
            (palette_x, 0, PALETTE_WIDTH, self.screen_height),
        )
        
        # Title
        font = pygame.font.Font(None, 24)
        title = font.render(f"Tiles ({self.map_grid.theme})", True, (200, 200, 200))
        screen.blit(title, (palette_x + 10, 10))
        
        # Tiles
        y = 40
        for i, tile in enumerate(self.palette_tiles):
            # Tile preview
            tile_rect = pygame.Rect(
                palette_x + PALETTE_PADDING,
                y,
                PALETTE_TILE_SIZE,
                PALETTE_TILE_SIZE,
            )
            pygame.draw.rect(screen, tile.color, tile_rect)
            
            # Selection highlight
            if tile.id == self.selected_tile_id:
                pygame.draw.rect(screen, (255, 255, 0), tile_rect, 3)
            
            # Label
            label = font.render(f"{i+1}: {tile.name}", True, (180, 180, 180))
            screen.blit(label, (palette_x + PALETTE_TILE_SIZE + PALETTE_PADDING * 2, y + 15))
            
            y += PALETTE_TILE_SIZE + PALETTE_PADDING
    
    def _render_status(self, screen: pygame.Surface) -> None:
        """Render the status bar."""
        font = pygame.font.Font(None, 24)
        
        # Status message
        if self.status_timer > 0:
            text = font.render(self.status_message, True, (255, 255, 100))
        else:
            undo_count = len(self._undo_stack)
            redo_count = len(self._redo_stack)
            brush_str = f"Brush: {self.brush_size}" if self.brush_size > 1 else ""
            pos_text = f"Map: {self.map_grid.name} | {self.map_grid.width}x{self.map_grid.height} | Undo: {undo_count} | Redo: {redo_count}"
            if brush_str:
                pos_text += f" | {brush_str}"
            text = font.render(pos_text, True, (150, 150, 150))
        
        screen.blit(text, (10, self.screen_height - 30))
    
    def _render_brush_preview(self, screen: pygame.Surface) -> None:
        """Render brush size preview at cursor position."""
        mx, my = pygame.mouse.get_pos()
        
        # Only show in map area
        if mx >= self.screen_width - PALETTE_WIDTH:
            return
        
        # Convert to tile coordinates
        world_x = mx + self.camera_x
        world_y = my + self.camera_y
        center_tx = int(world_x // TILE_SIZE)
        center_ty = int(world_y // TILE_SIZE)
        
        # Check for eyedropper mode
        mods = pygame.key.get_mods()
        if mods & pygame.KMOD_ALT:
            # Show eyedropper cursor
            screen_x = int(center_tx * TILE_SIZE - self.camera_x)
            screen_y = int(center_ty * TILE_SIZE - self.camera_y)
            rect = pygame.Rect(screen_x, screen_y, TILE_SIZE, TILE_SIZE)
            pygame.draw.rect(screen, (0, 255, 255), rect, 2)
            return
        
        # Draw brush preview
        half = self.brush_size // 2
        for dy in range(-half, half + 1):
            for dx in range(-half, half + 1):
                tx = center_tx + dx
                ty = center_ty + dy
                
                if 0 <= tx < self.map_grid.width and 0 <= ty < self.map_grid.height:
                    screen_x = int(tx * TILE_SIZE - self.camera_x)
                    screen_y = int(ty * TILE_SIZE - self.camera_y)
                    rect = pygame.Rect(screen_x, screen_y, TILE_SIZE, TILE_SIZE)
                    pygame.draw.rect(screen, (255, 255, 0), rect, 2)
    
    def _render_naming_overlay(self, screen: pygame.Surface) -> None:
        """Render the map naming input overlay."""
        # Semi-transparent background
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))
        
        # Input box
        font_large = pygame.font.Font(None, 36)
        font = pygame.font.Font(None, 28)
        
        # Title
        title = font_large.render("Enter Map Name", True, (255, 255, 255))
        title_rect = title.get_rect(center=(self.screen_width // 2, self.screen_height // 2 - 60))
        screen.blit(title, title_rect)
        
        # Input field with cursor
        cursor = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        input_text = font.render(f"[ {self._name_input}{cursor} ]", True, (255, 255, 100))
        input_rect = input_text.get_rect(center=(self.screen_width // 2, self.screen_height // 2))
        screen.blit(input_text, input_rect)
        
        # Instructions
        hint = font.render("ENTER: Confirm | ESC: Cancel", True, (150, 150, 150))
        hint_rect = hint.get_rect(center=(self.screen_width // 2, self.screen_height // 2 + 50))
        screen.blit(hint, hint_rect)
    
    def _render_resize_overlay(self, screen: pygame.Surface) -> None:
        """Render the map resize input overlay."""
        # Semi-transparent background
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))
        
        font_large = pygame.font.Font(None, 36)
        font = pygame.font.Font(None, 28)
        
        center_x = self.screen_width // 2
        center_y = self.screen_height // 2
        
        # Title
        title = font_large.render("Resize Map", True, (255, 255, 255))
        title_rect = title.get_rect(center=(center_x, center_y - 100))
        screen.blit(title, title_rect)
        
        # Current size info
        current = font.render(f"Current: {self.map_grid.width} x {self.map_grid.height}", True, (150, 150, 150))
        current_rect = current.get_rect(center=(center_x, center_y - 65))
        screen.blit(current, current_rect)
        
        # Blinking cursor
        cursor = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        
        # Width field
        width_color = (255, 255, 100) if self._resize_field == 0 else (180, 180, 180)
        width_cursor = cursor if self._resize_field == 0 else ""
        width_text = font.render(f"Width:  [ {self._resize_width}{width_cursor} ]", True, width_color)
        width_rect = width_text.get_rect(center=(center_x, center_y - 20))
        screen.blit(width_text, width_rect)
        
        # Height field
        height_color = (255, 255, 100) if self._resize_field == 1 else (180, 180, 180)
        height_cursor = cursor if self._resize_field == 1 else ""
        height_text = font.render(f"Height: [ {self._resize_height}{height_cursor} ]", True, height_color)
        height_rect = height_text.get_rect(center=(center_x, center_y + 20))
        screen.blit(height_text, height_rect)
        
        # Anchor selection
        anchor_color = (255, 255, 100) if self._resize_field == 2 else (180, 180, 180)
        anchor_name = self._resize_anchors[self._resize_anchor_idx].replace("_", " ").title()
        anchor_text = font.render(f"Anchor: < {anchor_name} >", True, anchor_color)
        anchor_rect = anchor_text.get_rect(center=(center_x, center_y + 60))
        screen.blit(anchor_text, anchor_rect)
        
        # Instructions
        hint = font.render("TAB: Switch field | Arrows: Change anchor | ENTER: Confirm | ESC: Cancel", True, (120, 120, 120))
        hint_rect = hint.get_rect(center=(center_x, center_y + 110))
        screen.blit(hint, hint_rect)
    
    def _render_help(self, screen: pygame.Surface) -> None:
        """Render the help overlay."""
        font = pygame.font.Font(None, 20)
        
        if self._spawn_mode:
            help_lines = [
                "=== SPAWN MODE ===",
                "M: Exit spawn mode",
                "Left click: Add/edit spawn",
                "Right click: Remove spawn",
                "P: Set player spawn",
                "Arrows: Pan camera",
                "S: Save map",
                "ESC: Exit spawn mode",
            ]
        else:
            help_lines = [
                "H: Toggle help",
                "1-9: Select tile",
                "T: Cycle theme",
                "G: Toggle grid",
                "S: Save map",
                "N: Rename map",
                "M: Spawn mode",
                "Ctrl+R: Resize map",
                "F: Flood fill",
                "[/]: Brush size",
                "Alt+Click: Eyedropper",
                "Ctrl+Z: Undo",
                "Ctrl+Y: Redo",
                "Arrows: Pan camera",
                "Ctrl+F: Fill all",
                "Left click: Paint",
                "Right click: Erase",
                "ESC: Quit",
            ]
        
        y = 50
        for line in help_lines:
            text = font.render(line, True, (120, 120, 120))
            screen.blit(text, (10, y))
            y += 18
    
    def _render_spawn_points(self, screen: pygame.Surface) -> None:
        """Render spawn point markers on the map."""
        map_area_width = self.screen_width - PALETTE_WIDTH
        font = pygame.font.Font(None, 16)
        
        for spawn in self.map_grid.spawn_points:
            screen_x = int(spawn.x * TILE_SIZE - self.camera_x)
            screen_y = int(spawn.y * TILE_SIZE - self.camera_y)
            
            # Skip if off screen
            if screen_x + TILE_SIZE < 0 or screen_x > map_area_width:
                continue
            if screen_y + TILE_SIZE < 0 or screen_y > self.screen_height:
                continue
            
            # Draw spawn marker
            rect = pygame.Rect(screen_x + 4, screen_y + 4, TILE_SIZE - 8, TILE_SIZE - 8)
            
            # Color based on type
            if spawn.is_boss_spawn:
                color = (255, 50, 50)  # Red for boss
            else:
                color = (255, 165, 0)  # Orange for regular
            
            # Highlight selected spawn
            if spawn is self._selected_spawn:
                pygame.draw.rect(screen, (255, 255, 0), rect.inflate(4, 4), 3)
            
            # Draw X marker
            pygame.draw.line(screen, color, rect.topleft, rect.bottomright, 3)
            pygame.draw.line(screen, color, rect.topright, rect.bottomleft, 3)
            
            # Draw pool count
            if len(spawn.enemy_pool) > 0:
                count_text = font.render(str(len(spawn.enemy_pool)), True, (255, 255, 255))
                screen.blit(count_text, (screen_x + TILE_SIZE - 12, screen_y + 2))
        
        # Draw player spawn
        if self.map_grid.player_spawn:
            px, py = self.map_grid.player_spawn
            screen_x = int(px * TILE_SIZE - self.camera_x)
            screen_y = int(py * TILE_SIZE - self.camera_y)
            
            if 0 <= screen_x < map_area_width and 0 <= screen_y < self.screen_height:
                # Draw green circle for player spawn
                center = (screen_x + TILE_SIZE // 2, screen_y + TILE_SIZE // 2)
                pygame.draw.circle(screen, (0, 255, 100), center, TILE_SIZE // 3, 3)
                pygame.draw.circle(screen, (0, 255, 100), center, 5)
    
    def _render_spawn_palette(self, screen: pygame.Surface) -> None:
        """Render the spawn mode palette panel."""
        palette_x = self.screen_width - PALETTE_WIDTH
        
        # Background
        pygame.draw.rect(
            screen,
            (50, 40, 40),  # Darker red tint for spawn mode
            (palette_x, 0, PALETTE_WIDTH, self.screen_height),
        )
        
        font_large = pygame.font.Font(None, 24)
        font = pygame.font.Font(None, 20)
        
        # Title
        title = font_large.render("SPAWN MODE", True, (255, 150, 100))
        screen.blit(title, (palette_x + 10, 10))
        
        y = 40
        
        # Instructions
        instructions = [
            "Click map to place spawn",
            "Right-click to remove",
            "Click spawn to edit pool",
            "P: Set player spawn",
            "",
            f"Spawns: {len(self.map_grid.spawn_points)}",
        ]
        for line in instructions:
            text = font.render(line, True, (180, 180, 180))
            screen.blit(text, (palette_x + 10, y))
            y += 20
        
        # Selected spawn info
        if self._selected_spawn:
            y += 10
            pygame.draw.line(screen, (100, 100, 100), (palette_x + 10, y), (palette_x + PALETTE_WIDTH - 10, y))
            y += 10
            
            header = font_large.render("Selected Spawn", True, (255, 200, 100))
            screen.blit(header, (palette_x + 10, y))
            y += 25
            
            pos_text = font.render(f"Position: ({self._selected_spawn.x}, {self._selected_spawn.y})", True, (200, 200, 200))
            screen.blit(pos_text, (palette_x + 10, y))
            y += 20
            
            pool_text = font.render("Pool:", True, (200, 200, 200))
            screen.blit(pool_text, (palette_x + 10, y))
            y += 18
            
            for enemy_type in self._selected_spawn.enemy_pool[:6]:  # Show max 6
                e_text = font.render(f"  - {enemy_type}", True, (180, 180, 180))
                screen.blit(e_text, (palette_x + 10, y))
                y += 16
            
            if len(self._selected_spawn.enemy_pool) > 6:
                more_text = font.render(f"  ...+{len(self._selected_spawn.enemy_pool) - 6} more", True, (150, 150, 150))
                screen.blit(more_text, (palette_x + 10, y))
                y += 16
            
            y += 10
            click_text = font.render("Click to edit pool", True, (255, 255, 100))
            screen.blit(click_text, (palette_x + 10, y))
    
    def _render_spawn_edit_overlay(self, screen: pygame.Surface) -> None:
        """Render the spawn pool edit overlay."""
        # Semi-transparent background
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))
        
        font_large = pygame.font.Font(None, 36)
        font = pygame.font.Font(None, 24)
        font_small = pygame.font.Font(None, 20)
        
        center_x = self.screen_width // 2
        center_y = self.screen_height // 2
        
        # Title
        title = font_large.render("Edit Spawn Pool", True, (255, 255, 255))
        title_rect = title.get_rect(center=(center_x, center_y - 120))
        screen.blit(title, title_rect)
        
        # Available enemies hint
        hint = font_small.render(f"Available: {', '.join(self._available_enemies[:8])}...", True, (150, 150, 150))
        hint_rect = hint.get_rect(center=(center_x, center_y - 85))
        screen.blit(hint, hint_rect)
        
        # Presets hint
        presets = font_small.render("Presets: basic, mixed, heavy, suicide, spawners, all", True, (150, 150, 150))
        presets_rect = presets.get_rect(center=(center_x, center_y - 65))
        screen.blit(presets, presets_rect)
        
        # Input field
        cursor = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        input_text = font.render(f"[ {self._spawn_pool_input}{cursor} ]", True, (255, 255, 100))
        input_rect = input_text.get_rect(center=(center_x, center_y))
        screen.blit(input_text, input_rect)
        
        # Instructions
        inst = font.render("Enter enemy types separated by commas", True, (180, 180, 180))
        inst_rect = inst.get_rect(center=(center_x, center_y + 40))
        screen.blit(inst, inst_rect)
        
        inst2 = font.render("ENTER: Confirm | ESC: Cancel", True, (120, 120, 120))
        inst2_rect = inst2.get_rect(center=(center_x, center_y + 70))
        screen.blit(inst2, inst2_rect)
