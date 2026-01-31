"""LoadGameScene: screen for loading saved games from the main menu."""
from __future__ import annotations

import pygame

from constants import STATE_LOAD_GAME, STATE_MENU, STATE_PLAYING
from rendering import RenderContext, draw_centered_text
from rendering.menu_helpers import handle_menu_navigation
from scenes.base import BaseScene
from scenes.transitions import SceneTransition
from save_system import load_saves, get_save_display_text, delete_save, MAX_SAVE_SLOTS


class LoadGameScene(BaseScene):
    """Load game screen. Select a save slot to load or delete."""

    def __init__(self):
        super().__init__()
        self._option_rects: list[pygame.Rect] = []

    def state_id(self) -> str:
        return STATE_LOAD_GAME

    def handle_input(self, events, game_state, ctx: dict) -> dict:
        out = {
            "screen": None,
            "quit": False,
            "restart": False,
            "pop": False,
            "load_game": False,
            "load_slot": None,
        }
        
        # Use shared navigation handler
        new_idx, confirmed, clicked_idx = handle_menu_navigation(
            events, MAX_SAVE_SLOTS,
            game_state.ui.load_slot_selected,
            self._option_rects
        )
        game_state.ui.load_slot_selected = new_idx
        
        # Handle confirmation (Enter or click)
        if confirmed or clicked_idx >= 0:
            selected_idx = clicked_idx if clicked_idx >= 0 else game_state.ui.load_slot_selected
            saves = load_saves()
            slot = saves.get(selected_idx)
            if slot is not None:
                out["load_game"] = True
                out["load_slot"] = slot
                out["screen"] = STATE_PLAYING
                return out
        
        # Handle special keys (delete, escape)
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
                saves = load_saves()
                slot = saves.get(game_state.ui.load_slot_selected)
                if slot is not None:
                    delete_save(game_state.ui.load_slot_selected)
            elif event.key == pygame.K_ESCAPE:
                out["pop"] = True
                return out
        
        return out

    def render(self, render_ctx: RenderContext, game_state, ctx: dict) -> None:
        screen = render_ctx.screen
        w, h = render_ctx.width, render_ctx.height
        font, big_font = render_ctx.font, render_ctx.big_font
        
        # Background
        screen.fill((20, 20, 40))
        
        # Title
        draw_centered_text(screen, font, big_font, w, "LOAD GAME", h // 2 - 180, color=(100, 200, 255), use_big=True)
        
        # Instructions
        draw_centered_text(screen, font, big_font, w, "Select a save to continue your adventure", h // 2 - 120, color=(180, 180, 180))
        
        # Load current saves
        saves = load_saves()
        selected = game_state.ui.load_slot_selected
        
        # Check if any saves exist
        has_saves = any(saves.get(i) is not None for i in range(MAX_SAVE_SLOTS))
        
        # Render slots and calculate clickable rects
        y_start = h // 2 - 40
        line_height = 50
        option_width = 600
        self._option_rects = []
        
        for i in range(MAX_SAVE_SLOTS):
            slot = saves.get(i)
            display_text = get_save_display_text(slot)
            
            if i == selected:
                color = (255, 255, 0)
                prefix = "-> "
            else:
                color = (200, 200, 200) if slot else (100, 100, 100)
                prefix = "   "
            
            # Show slot number
            y = y_start + i * line_height
            slot_label = f"Slot {i + 1}: "
            draw_centered_text(screen, font, big_font, w, f"{prefix}{slot_label}{display_text}", y, color)
            
            # Store clickable rect
            click_rect = pygame.Rect((w - option_width) // 2, y - line_height // 2, option_width, line_height)
            self._option_rects.append(click_rect)
        
        # Instructions
        if has_saves:
            draw_centered_text(screen, font, big_font, w, "UP/DOWN: Select | ENTER: Load | DELETE: Remove Save | ESC: Back", h - 60, (150, 150, 150))
        else:
            draw_centered_text(screen, font, big_font, w, "No saves found. Press ESC to go back.", h - 60, (150, 150, 150))

    def on_enter(self, game_state, ctx: dict) -> None:
        game_state.ui.load_slot_selected = 0
    
    def handle_input_transition(self, events, game_state, ctx: dict) -> SceneTransition:
        """Override to handle load_game result which game.py needs to process."""
        result = self.handle_input(events, game_state, ctx)
        self._last_input_result = result
        
        if result.get("pop"):
            return SceneTransition.pop()
        
        # Load game is handled by game.py via the result dict
        return SceneTransition.none()
