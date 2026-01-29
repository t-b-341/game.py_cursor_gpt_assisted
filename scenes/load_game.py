"""LoadGameScene: screen for loading saved games from the main menu."""
from __future__ import annotations

import pygame

from constants import STATE_LOAD_GAME, STATE_MENU, STATE_PLAYING
from rendering import RenderContext, draw_centered_text
from scenes.transitions import SceneTransition
from save_system import load_saves, get_save_display_text, delete_save, MAX_SAVE_SLOTS


class LoadGameScene:
    """Load game screen. Select a save slot to load or delete."""

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
        
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            
            if event.key in (pygame.K_UP, pygame.K_w):
                game_state.ui.load_slot_selected = (game_state.ui.load_slot_selected - 1) % MAX_SAVE_SLOTS
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                game_state.ui.load_slot_selected = (game_state.ui.load_slot_selected + 1) % MAX_SAVE_SLOTS
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                # Load selected save
                saves = load_saves()
                slot = saves.get(game_state.ui.load_slot_selected)
                if slot is not None:
                    out["load_game"] = True
                    out["load_slot"] = slot
                    out["screen"] = STATE_PLAYING
                    return out
            elif event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
                # Delete selected save
                saves = load_saves()
                slot = saves.get(game_state.ui.load_slot_selected)
                if slot is not None:
                    delete_save(game_state.ui.load_slot_selected)
            elif event.key == pygame.K_ESCAPE:
                # Go back to menu
                out["pop"] = True
                return out
        
        return out

    def update(self, dt: float, game_state, ctx: dict) -> None:
        pass

    def handle_input_transition(self, events, game_state, ctx: dict) -> SceneTransition:
        """Handle input and return transition if needed."""
        result = self.handle_input(events, game_state, ctx)
        
        if result.get("pop"):
            return SceneTransition.pop()
        
        # Load game is handled by game.py via the result dict
        return SceneTransition.none()

    def update_transition(self, dt: float, game_state, ctx: dict) -> SceneTransition:
        """Stub: call existing logic; return NONE."""
        self.update(dt, game_state, ctx)
        return SceneTransition.none()

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
        
        # Render slots
        y_start = h // 2 - 40
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
            slot_label = f"Slot {i + 1}: "
            draw_centered_text(screen, font, big_font, w, f"{prefix}{slot_label}{display_text}", y_start + i * 50, color)
        
        # Instructions
        if has_saves:
            draw_centered_text(screen, font, big_font, w, "UP/DOWN: Select | ENTER: Load | DELETE: Remove Save | ESC: Back", h - 60, (150, 150, 150))
        else:
            draw_centered_text(screen, font, big_font, w, "No saves found. Press ESC to go back.", h - 60, (150, 150, 150))

    def on_enter(self, game_state, ctx: dict) -> None:
        # Reset selection when entering
        game_state.ui.load_slot_selected = 0

    def on_exit(self, game_state, ctx: dict) -> None:
        pass
