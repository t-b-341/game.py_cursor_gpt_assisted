"""Editor rendering methods."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from .constants import TILE_SIZE, PALETTE_WIDTH, PALETTE_TILE_SIZE, PALETTE_PADDING
from ..registry import get_tile

if TYPE_CHECKING:
    from .core import MapEditor


class RenderingMixin:
    """Mixin providing editor rendering methods."""
    
    def render(self: "MapEditor", screen: pygame.Surface) -> None:
        """Render the editor."""
        screen.fill((30, 30, 35))
        
        self._render_map(screen)
        self._render_spawn_points(screen)
        
        if self.show_grid:
            self._render_grid(screen)
        
        self._render_brush_preview(screen)
        
        if self._spawn_mode:
            self._render_spawn_palette(screen)
        else:
            self._render_palette(screen)
        
        self._render_status(screen)
        
        if self.show_help:
            self._render_help(screen)
        
        if self._naming_mode:
            self._render_naming_overlay(screen)
        
        if self._resize_mode:
            self._render_resize_overlay(screen)
        
        if self._spawn_edit_mode:
            self._render_spawn_edit_overlay(screen)
    
    def _render_map(self: "MapEditor", screen: pygame.Surface) -> None:
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
        
        # Draw map boundary indicator
        self._render_map_boundary(screen, map_area_width)
    
    def _render_map_boundary(self: "MapEditor", screen: pygame.Surface, map_area_width: int) -> None:
        """Render a visible boundary around the map edges."""
        # Calculate map bounds in screen coordinates
        map_pixel_width = self.map_grid.width * TILE_SIZE
        map_pixel_height = self.map_grid.height * TILE_SIZE
        
        # Map boundary rectangle in screen space
        left = int(-self.camera_x)
        top = int(-self.camera_y)
        right = int(map_pixel_width - self.camera_x)
        bottom = int(map_pixel_height - self.camera_y)
        
        # Clamp to visible area
        visible_left = max(0, left)
        visible_top = max(0, top)
        visible_right = min(map_area_width, right)
        visible_bottom = min(self.screen_height, bottom)
        
        # Draw dashed boundary lines in yellow/orange
        boundary_color = (255, 180, 50)
        line_width = 3
        
        # Draw right edge of map (if visible)
        if 0 < right <= map_area_width:
            pygame.draw.line(screen, boundary_color, (right, visible_top), (right, visible_bottom), line_width)
        
        # Draw bottom edge of map (if visible)  
        if 0 < bottom <= self.screen_height:
            pygame.draw.line(screen, boundary_color, (visible_left, bottom), (visible_right, bottom), line_width)
        
        # Draw left edge (if camera is past left boundary)
        if left > 0:
            pygame.draw.line(screen, boundary_color, (left, visible_top), (left, visible_bottom), line_width)
        
        # Draw top edge (if camera is past top boundary)
        if top > 0:
            pygame.draw.line(screen, boundary_color, (visible_left, top), (visible_right, top), line_width)
    
    def _render_grid(self: "MapEditor", screen: pygame.Surface) -> None:
        """Render grid lines."""
        map_area_width = self.screen_width - PALETTE_WIDTH
        grid_color = (50, 50, 55)
        
        offset_x = int(self.camera_x % TILE_SIZE)
        for x in range(-offset_x, map_area_width, TILE_SIZE):
            pygame.draw.line(screen, grid_color, (x, 0), (x, self.screen_height))
        
        offset_y = int(self.camera_y % TILE_SIZE)
        for y in range(-offset_y, self.screen_height, TILE_SIZE):
            pygame.draw.line(screen, grid_color, (0, y), (map_area_width, y))
    
    def _render_palette(self: "MapEditor", screen: pygame.Surface) -> None:
        """Render the tile palette."""
        palette_x = self.screen_width - PALETTE_WIDTH
        
        pygame.draw.rect(screen, (40, 40, 45), (palette_x, 0, PALETTE_WIDTH, self.screen_height))
        
        font = pygame.font.Font(None, 24)
        title = font.render(f"Tiles ({self.map_grid.theme})", True, (200, 200, 200))
        screen.blit(title, (palette_x + 10, 10))
        
        y = 40
        for i, tile in enumerate(self.palette_tiles):
            tile_rect = pygame.Rect(palette_x + PALETTE_PADDING, y, PALETTE_TILE_SIZE, PALETTE_TILE_SIZE)
            pygame.draw.rect(screen, tile.color, tile_rect)
            
            if tile.id == self.selected_tile_id:
                pygame.draw.rect(screen, (255, 255, 0), tile_rect, 3)
            
            label = font.render(f"{i+1}: {tile.name}", True, (180, 180, 180))
            screen.blit(label, (palette_x + PALETTE_TILE_SIZE + PALETTE_PADDING * 2, y + 15))
            
            y += PALETTE_TILE_SIZE + PALETTE_PADDING
    
    def _render_status(self: "MapEditor", screen: pygame.Surface) -> None:
        """Render the status bar."""
        font = pygame.font.Font(None, 24)
        
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
    
    def _render_brush_preview(self: "MapEditor", screen: pygame.Surface) -> None:
        """Render brush size preview at cursor position."""
        mx, my = pygame.mouse.get_pos()
        
        if mx >= self.screen_width - PALETTE_WIDTH:
            return
        
        world_x = mx + self.camera_x
        world_y = my + self.camera_y
        center_tx = int(world_x // TILE_SIZE)
        center_ty = int(world_y // TILE_SIZE)
        
        mods = pygame.key.get_mods()
        if mods & pygame.KMOD_ALT:
            screen_x = int(center_tx * TILE_SIZE - self.camera_x)
            screen_y = int(center_ty * TILE_SIZE - self.camera_y)
            rect = pygame.Rect(screen_x, screen_y, TILE_SIZE, TILE_SIZE)
            pygame.draw.rect(screen, (0, 255, 255), rect, 2)
            return
        
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
    
    def _render_naming_overlay(self: "MapEditor", screen: pygame.Surface) -> None:
        """Render the map naming input overlay."""
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))
        
        font_large = pygame.font.Font(None, 36)
        font = pygame.font.Font(None, 28)
        
        title = font_large.render("Enter Map Name", True, (255, 255, 255))
        title_rect = title.get_rect(center=(self.screen_width // 2, self.screen_height // 2 - 60))
        screen.blit(title, title_rect)
        
        cursor = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        input_text = font.render(f"[ {self._name_input}{cursor} ]", True, (255, 255, 100))
        input_rect = input_text.get_rect(center=(self.screen_width // 2, self.screen_height // 2))
        screen.blit(input_text, input_rect)
        
        hint = font.render("ENTER: Confirm | ESC: Cancel", True, (150, 150, 150))
        hint_rect = hint.get_rect(center=(self.screen_width // 2, self.screen_height // 2 + 50))
        screen.blit(hint, hint_rect)
    
    def _render_resize_overlay(self: "MapEditor", screen: pygame.Surface) -> None:
        """Render the map resize input overlay."""
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))
        
        font_large = pygame.font.Font(None, 36)
        font = pygame.font.Font(None, 28)
        
        center_x = self.screen_width // 2
        center_y = self.screen_height // 2
        
        title = font_large.render("Resize Map", True, (255, 255, 255))
        title_rect = title.get_rect(center=(center_x, center_y - 100))
        screen.blit(title, title_rect)
        
        current = font.render(f"Current: {self.map_grid.width} x {self.map_grid.height}", True, (150, 150, 150))
        current_rect = current.get_rect(center=(center_x, center_y - 65))
        screen.blit(current, current_rect)
        
        cursor = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        
        width_color = (255, 255, 100) if self._resize_field == 0 else (180, 180, 180)
        width_cursor = cursor if self._resize_field == 0 else ""
        width_text = font.render(f"Width:  [ {self._resize_width}{width_cursor} ]", True, width_color)
        width_rect = width_text.get_rect(center=(center_x, center_y - 20))
        screen.blit(width_text, width_rect)
        
        height_color = (255, 255, 100) if self._resize_field == 1 else (180, 180, 180)
        height_cursor = cursor if self._resize_field == 1 else ""
        height_text = font.render(f"Height: [ {self._resize_height}{height_cursor} ]", True, height_color)
        height_rect = height_text.get_rect(center=(center_x, center_y + 20))
        screen.blit(height_text, height_rect)
        
        anchor_color = (255, 255, 100) if self._resize_field == 2 else (180, 180, 180)
        anchor_name = self._resize_anchors[self._resize_anchor_idx].replace("_", " ").title()
        anchor_text = font.render(f"Anchor: < {anchor_name} >", True, anchor_color)
        anchor_rect = anchor_text.get_rect(center=(center_x, center_y + 60))
        screen.blit(anchor_text, anchor_rect)
        
        hint = font.render("TAB: Switch field | Arrows: Change anchor | ENTER: Confirm | ESC: Cancel", True, (120, 120, 120))
        hint_rect = hint.get_rect(center=(center_x, center_y + 110))
        screen.blit(hint, hint_rect)
    
    def _render_help(self: "MapEditor", screen: pygame.Surface) -> None:
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
                "S: Quick save",
                "Ctrl+S: Save As...",
                "ESC: Exit spawn mode",
            ]
        else:
            help_lines = [
                "H: Toggle help",
                "1-9: Select tile",
                "T: Cycle theme",
                "G: Toggle grid",
                "S: Quick save",
                "Ctrl+S: Save As...",
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
                "F11: Fullscreen",
                "Left click: Paint",
                "Right click: Erase",
                "ESC: Quit",
            ]
        
        y = 50
        for line in help_lines:
            text = font.render(line, True, (120, 120, 120))
            screen.blit(text, (10, y))
            y += 18
    
    def _render_spawn_points(self: "MapEditor", screen: pygame.Surface) -> None:
        """Render spawn point markers on the map."""
        map_area_width = self.screen_width - PALETTE_WIDTH
        font = pygame.font.Font(None, 16)
        
        for spawn in self.map_grid.spawn_points:
            screen_x = int(spawn.x * TILE_SIZE - self.camera_x)
            screen_y = int(spawn.y * TILE_SIZE - self.camera_y)
            
            if screen_x + TILE_SIZE < 0 or screen_x > map_area_width:
                continue
            if screen_y + TILE_SIZE < 0 or screen_y > self.screen_height:
                continue
            
            rect = pygame.Rect(screen_x + 4, screen_y + 4, TILE_SIZE - 8, TILE_SIZE - 8)
            
            if spawn.is_boss_spawn:
                color = (255, 50, 50)
            else:
                color = (255, 165, 0)
            
            if spawn is self._selected_spawn:
                pygame.draw.rect(screen, (255, 255, 0), rect.inflate(4, 4), 3)
            
            pygame.draw.line(screen, color, rect.topleft, rect.bottomright, 3)
            pygame.draw.line(screen, color, rect.topright, rect.bottomleft, 3)
            
            if len(spawn.enemy_pool) > 0:
                count_text = font.render(str(len(spawn.enemy_pool)), True, (255, 255, 255))
                screen.blit(count_text, (screen_x + TILE_SIZE - 12, screen_y + 2))
        
        if self.map_grid.player_spawn:
            px, py = self.map_grid.player_spawn
            screen_x = int(px * TILE_SIZE - self.camera_x)
            screen_y = int(py * TILE_SIZE - self.camera_y)
            
            if 0 <= screen_x < map_area_width and 0 <= screen_y < self.screen_height:
                center = (screen_x + TILE_SIZE // 2, screen_y + TILE_SIZE // 2)
                pygame.draw.circle(screen, (0, 255, 100), center, TILE_SIZE // 3, 3)
                pygame.draw.circle(screen, (0, 255, 100), center, 5)
    
    def _render_spawn_palette(self: "MapEditor", screen: pygame.Surface) -> None:
        """Render the spawn mode palette panel."""
        palette_x = self.screen_width - PALETTE_WIDTH
        
        pygame.draw.rect(screen, (50, 40, 40), (palette_x, 0, PALETTE_WIDTH, self.screen_height))
        
        font_large = pygame.font.Font(None, 24)
        font = pygame.font.Font(None, 20)
        
        title = font_large.render("SPAWN MODE", True, (255, 150, 100))
        screen.blit(title, (palette_x + 10, 10))
        
        y = 40
        
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
            
            for enemy_type in self._selected_spawn.enemy_pool[:6]:
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
    
    def _render_spawn_edit_overlay(self: "MapEditor", screen: pygame.Surface) -> None:
        """Render the spawn pool edit overlay."""
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))
        
        font_large = pygame.font.Font(None, 36)
        font = pygame.font.Font(None, 24)
        font_small = pygame.font.Font(None, 20)
        
        center_x = self.screen_width // 2
        center_y = self.screen_height // 2
        
        title = font_large.render("Edit Spawn Pool", True, (255, 255, 255))
        title_rect = title.get_rect(center=(center_x, center_y - 120))
        screen.blit(title, title_rect)
        
        hint = font_small.render(f"Available: {', '.join(self._available_enemies[:8])}...", True, (150, 150, 150))
        hint_rect = hint.get_rect(center=(center_x, center_y - 85))
        screen.blit(hint, hint_rect)
        
        presets = font_small.render("Presets: basic, mixed, heavy, suicide, spawners, all", True, (150, 150, 150))
        presets_rect = presets.get_rect(center=(center_x, center_y - 65))
        screen.blit(presets, presets_rect)
        
        cursor = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        input_text = font.render(f"[ {self._spawn_pool_input}{cursor} ]", True, (255, 255, 100))
        input_rect = input_text.get_rect(center=(center_x, center_y))
        screen.blit(input_text, input_rect)
        
        inst = font.render("Enter enemy types separated by commas", True, (180, 180, 180))
        inst_rect = inst.get_rect(center=(center_x, center_y + 40))
        screen.blit(inst, inst_rect)
        
        inst2 = font.render("ENTER: Confirm | ESC: Cancel", True, (120, 120, 120))
        inst2_rect = inst2.get_rect(center=(center_x, center_y + 70))
        screen.blit(inst2, inst2_rect)
