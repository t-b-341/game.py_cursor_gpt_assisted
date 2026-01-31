"""GameOverScene: game over screen with Try Again, Save, and Quit options."""
from __future__ import annotations

import pygame

from constants import STATE_GAME_OVER, STATE_SAVE_GAME, STATE_TITLE, STATE_PLAYING
from rendering import RenderContext, draw_centered_text
from rendering.menu_helpers import render_menu_options, handle_menu_navigation
from scenes.base import BaseScene
from scenes.transitions import SceneTransition


# Base options - first one is customized with wave number
_BASE_OPTIONS = ["Try Again (Wave {wave})", "Save Progress", "Quit to Title"]


class GameOverScene(BaseScene):
    """Game over screen. Shows options to retry current wave, save, or quit."""

    def __init__(self):
        super().__init__()
        self._option_rects: list[pygame.Rect] = []

    def state_id(self) -> str:
        return STATE_GAME_OVER

    def _get_options(self, game_state) -> list[str]:
        """Get options with wave number substituted."""
        wave_num = getattr(game_state, "game_over_wave", 1)
        return [opt.format(wave=wave_num) for opt in _BASE_OPTIONS]

    def handle_input(self, events, game_state, ctx: dict) -> dict:
        out = {
            "screen": None,
            "quit": False,
            "restart": False,
            "restart_to_wave1": False,
            "replay": False,
            "pop": False,
            "try_again": False,
            "save": False,
        }
        
        options = self._get_options(game_state)
        
        # Use shared navigation handler
        new_idx, confirmed, clicked_idx = handle_menu_navigation(
            events, len(options),
            game_state.ui.game_over_selected,
            self._option_rects
        )
        game_state.ui.game_over_selected = new_idx
        
        # Handle confirmation (Enter or click)
        selected = clicked_idx if clicked_idx >= 0 else (game_state.ui.game_over_selected if confirmed else -1)
        if selected >= 0:
            if selected == 0:  # Try Again
                out["try_again"] = True
                out["screen"] = STATE_PLAYING
            elif selected == 1:  # Save
                out["save"] = True
                out["screen"] = STATE_SAVE_GAME
            elif selected == 2:  # Quit to Title
                out["screen"] = STATE_TITLE
            return out
        
        # Handle escape
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                out["screen"] = STATE_TITLE
                return out
        
        return out

    def render(self, render_ctx: RenderContext, game_state, ctx: dict) -> None:
        screen = render_ctx.screen
        w, h = render_ctx.width, render_ctx.height
        font, big_font = render_ctx.font, render_ctx.big_font
        
        # Semi-transparent overlay
        overlay = pygame.Surface((w, h))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))
        
        # Title
        draw_centered_text(screen, font, big_font, w, "GAME OVER", h // 2 - 150, color=(255, 80, 80), use_big=True)
        
        # Show wave info
        wave_num = getattr(game_state, "game_over_wave", 1)
        draw_centered_text(screen, font, big_font, w, f"You died on Wave {wave_num}", h // 2 - 80, color=(200, 200, 200))
        
        # Show final score
        score = getattr(game_state, "score", 0)
        draw_centered_text(screen, font, big_font, w, f"Final Score: {score}", h // 2 - 50, color=(200, 200, 200))
        
        # Menu options using shared helper
        selected = game_state.ui.game_over_selected
        y_start = h // 2 + 20
        options = self._get_options(game_state)
        self._option_rects = render_menu_options(
            screen, font, big_font, w, options,
            selected, y_start, line_height=45
        )
        
        # Instructions
        draw_centered_text(screen, font, big_font, w, "UP/DOWN: Select | ENTER: Confirm | ESC: Quit", h - 60, (150, 150, 150))

    def on_enter(self, game_state, ctx: dict) -> None:
        game_state.ui.game_over_selected = 0
    
    def _get_screen_transition(self, screen: str, result: dict) -> SceneTransition:
        if screen == STATE_PLAYING and result.get("try_again"):
            # Try again - handled by game.py to restart at game_over_wave
            return SceneTransition.none()
        elif screen == STATE_SAVE_GAME:
            return SceneTransition.push(STATE_SAVE_GAME)
        return SceneTransition.replace(screen)
