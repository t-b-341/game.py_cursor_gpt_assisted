"""Map editor logic - handles editor state and rendering."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pygame

from .map_grid import MapGrid
from .map_saver import save_map
from .registry import get_tile, list_tiles, list_themes, get_theme_tiles


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
        
        # Get available tiles for current theme
        self._update_palette()
    
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
        
        # Quit
        if key == pygame.K_ESCAPE:
            return True
        
        # Save
        if key == pygame.K_s:
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
        
        # Number keys for palette selection
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
        
        # Begin brush stroke
        self._begin_stroke()
        
        if event.button == 1:  # Left click - place tile
            self._place_tile_with_undo(tx, ty, self.selected_tile_id)
        elif event.button == 3:  # Right click - erase (place floor)
            self._place_tile_with_undo(tx, ty, "floor")
    
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
    
    def update(self, dt: float) -> None:
        """Update editor state.
        
        Args:
            dt: Delta time in seconds
        """
        # Handle held mouse buttons for continuous painting
        buttons = pygame.mouse.get_pressed()
        if buttons[0] or buttons[2]:  # Left or right held
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
                    self._place_tile_with_undo(tx, ty, self.selected_tile_id)
                elif buttons[2]:  # Right - erase
                    self._place_tile_with_undo(tx, ty, "floor")
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
        
        # Render grid overlay
        if self.show_grid:
            self._render_grid(screen)
        
        # Render palette
        self._render_palette(screen)
        
        # Render status bar
        self._render_status(screen)
        
        # Render help overlay
        if self.show_help:
            self._render_help(screen)
    
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
            pos_text = f"Map: {self.map_grid.name} | Size: {self.map_grid.width}x{self.map_grid.height} | Undo: {undo_count} | Redo: {redo_count}"
            text = font.render(pos_text, True, (150, 150, 150))
        
        screen.blit(text, (10, self.screen_height - 30))
    
    def _render_help(self, screen: pygame.Surface) -> None:
        """Render the help overlay."""
        font = pygame.font.Font(None, 20)
        help_lines = [
            "H: Toggle help",
            "1-9: Select tile",
            "T: Cycle theme",
            "G: Toggle grid",
            "S: Save map",
            "Ctrl+Z: Undo",
            "Ctrl+Y: Redo",
            "Arrows: Pan camera",
            "Ctrl+F: Fill map",
            "Left click: Place tile",
            "Right click: Erase",
            "ESC: Quit",
        ]
        
        y = 50
        for line in help_lines:
            text = font.render(line, True, (120, 120, 120))
            screen.blit(text, (10, y))
            y += 18
