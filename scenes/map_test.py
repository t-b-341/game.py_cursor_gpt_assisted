"""MapTestScene: Select and test custom maps in-game."""
from __future__ import annotations

import pygame

from constants import STATE_MAP_TEST, STATE_PLAYING
from rendering import RenderContext, draw_centered_text
from scenes.transitions import SceneTransition


class MapTestScene:
    """Scene for selecting a custom map to test in gameplay.
    
    Lists all available maps and allows launching gameplay with a selected map.
    """

    def __init__(self):
        self._selected_idx = 0
        self._maps: list[str] = []
        self._scroll_offset = 0
        self._max_visible = 10
        self._status_message = ""
        self._status_timer = 0.0
        # Load maps on init as fallback (on_enter may not always be called)
        self._load_map_list()

    def state_id(self) -> str:
        return STATE_MAP_TEST

    def on_enter(self, game_state, ctx: dict) -> None:
        """Load available maps when entering the scene."""
        self._load_map_list()
        self._selected_idx = 0
        self._scroll_offset = 0
        self._status_message = ""
    
    def _load_map_list(self) -> None:
        """Load list of available maps from maps/data directory."""
        try:
            from maps.map_loader import get_maps_data_dir
            import os
            
            maps_dir = get_maps_data_dir()
            self._maps = []
            
            if os.path.exists(maps_dir):
                for filename in os.listdir(maps_dir):
                    if filename.endswith(".json"):
                        self._maps.append(filename[:-5])  # Remove .json extension
            
            self._maps.sort()
            
            if not self._maps:
                self._status_message = "No maps found in maps/data/"
        except Exception as e:
            self._status_message = f"Error loading maps: {e}"
            self._maps = []

    def handle_input(self, events, game_state, ctx: dict) -> dict:
        out = {"screen": None, "quit": False, "pop": False, "selected_map": None}
        
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    out["pop"] = True
                    return out
                
                if event.key == pygame.K_UP:
                    if self._maps:
                        self._selected_idx = (self._selected_idx - 1) % len(self._maps)
                        self._update_scroll()
                
                if event.key == pygame.K_DOWN:
                    if self._maps:
                        self._selected_idx = (self._selected_idx + 1) % len(self._maps)
                        self._update_scroll()
                
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    if self._maps:
                        out["selected_map"] = self._maps[self._selected_idx]
                        out["screen"] = STATE_PLAYING
                        return out
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Handle click on map list
                clicked_idx = self._get_clicked_map_index(event.pos, ctx)
                if clicked_idx is not None:
                    if clicked_idx == self._selected_idx:
                        # Double-click effect: select and play
                        out["selected_map"] = self._maps[self._selected_idx]
                        out["screen"] = STATE_PLAYING
                        return out
                    else:
                        self._selected_idx = clicked_idx
        
        return out

    def _update_scroll(self) -> None:
        """Update scroll offset to keep selected item visible."""
        if self._selected_idx < self._scroll_offset:
            self._scroll_offset = self._selected_idx
        elif self._selected_idx >= self._scroll_offset + self._max_visible:
            self._scroll_offset = self._selected_idx - self._max_visible + 1

    def _get_clicked_map_index(self, pos: tuple[int, int], ctx: dict) -> int | None:
        """Get the map index that was clicked, or None if outside list."""
        mx, my = pos
        width = ctx.get("width", 1920)
        height = ctx.get("height", 1080)
        
        list_start_y = height // 4
        item_height = 40
        list_x = width // 4
        list_width = width // 2
        
        if list_x <= mx <= list_x + list_width:
            relative_y = my - list_start_y
            if relative_y >= 0:
                clicked_item = relative_y // item_height
                actual_idx = clicked_item + self._scroll_offset
                if 0 <= actual_idx < len(self._maps) and clicked_item < self._max_visible:
                    return actual_idx
        
        return None

    def update(self, dt: float, game_state, ctx: dict) -> None:
        if self._status_timer > 0:
            self._status_timer -= dt

    def handle_input_transition(self, events, game_state, ctx: dict) -> SceneTransition:
        result = self.handle_input(events, game_state, ctx)
        
        if result.get("pop"):
            return SceneTransition.pop()
        
        if result.get("screen") == STATE_PLAYING and result.get("selected_map"):
            # Store selected map in game state for gameplay to load
            game_state.test_map_name = result["selected_map"]
            return SceneTransition.replace(STATE_PLAYING)
        
        return SceneTransition.none()

    def update_transition(self, dt: float, game_state, ctx: dict) -> SceneTransition:
        self.update(dt, game_state, ctx)
        return SceneTransition.none()

    def render(self, render_ctx: RenderContext, game_state, ctx: dict) -> None:
        screen = render_ctx.screen
        w, h = render_ctx.width, render_ctx.height
        font, big_font = render_ctx.font, render_ctx.big_font
        
        # Background
        screen.fill((20, 25, 35))
        
        # Title
        draw_centered_text(screen, font, big_font, w, "TEST MAP", 60, color=(255, 200, 100), use_big=True)
        draw_centered_text(screen, font, big_font, w, "Select a map to play", 120, color=(180, 180, 180))
        
        # Map list
        list_start_y = h // 4
        item_height = 40
        list_x = w // 4
        list_width = w // 2
        
        if not self._maps:
            draw_centered_text(screen, font, big_font, w, "No maps available", h // 2, color=(150, 150, 150))
            draw_centered_text(screen, font, big_font, w, "Create maps with: python run_editor.py", h // 2 + 40, color=(120, 120, 120))
        else:
            # Draw visible maps
            for i in range(self._max_visible):
                map_idx = i + self._scroll_offset
                if map_idx >= len(self._maps):
                    break
                
                map_name = self._maps[map_idx]
                y = list_start_y + i * item_height
                
                # Highlight selected
                if map_idx == self._selected_idx:
                    pygame.draw.rect(screen, (60, 80, 100), (list_x - 10, y - 5, list_width + 20, item_height - 5))
                    color = (255, 255, 100)
                else:
                    color = (200, 200, 200)
                
                # Draw map name
                text = font.render(f"  {map_name}", True, color)
                screen.blit(text, (list_x, y))
                
                # Draw spawn point count if available
                try:
                    from maps import load_map
                    map_grid = load_map(map_name)
                    if map_grid:
                        spawn_count = len(map_grid.spawn_points)
                        info = f"({spawn_count} spawns)"
                        info_text = font.render(info, True, (120, 120, 120))
                        screen.blit(info_text, (list_x + list_width - 100, y))
                except Exception:
                    pass
            
            # Scroll indicators
            if self._scroll_offset > 0:
                draw_centered_text(screen, font, big_font, w, "▲ More above", list_start_y - 30, color=(100, 100, 100))
            if self._scroll_offset + self._max_visible < len(self._maps):
                draw_centered_text(screen, font, big_font, w, "▼ More below", list_start_y + self._max_visible * item_height + 10, color=(100, 100, 100))
        
        # Instructions
        draw_centered_text(screen, font, big_font, w, "UP/DOWN: Navigate | ENTER: Play | ESC: Back", h - 60, color=(120, 120, 120))
        
        # Status message
        if self._status_message:
            draw_centered_text(screen, font, big_font, w, self._status_message, h - 100, color=(255, 100, 100))

    def on_exit(self, game_state, ctx: dict) -> None:
        pass
