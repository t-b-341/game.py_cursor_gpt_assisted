"""VictoryScene: displayed when the player beats all levels."""
from __future__ import annotations

import pygame

from constants import STATE_VICTORY, STATE_NAME_INPUT, STATE_TITLE, STATE_PLAYING
from rendering import RenderContext, draw_centered_text
from rendering.menu_helpers import render_menu_options, handle_menu_navigation
from scenes.transitions import SceneTransition


VICTORY_OPTIONS = ["Enter High Score", "Play Again", "Quit to Title"]


class VictoryScene:
    """Victory screen. Shows when the player beats all levels."""

    def __init__(self):
        self._option_rects: list[pygame.Rect] = []

    def state_id(self) -> str:
        return STATE_VICTORY

    def handle_input(self, events, game_state, ctx: dict) -> dict:
        out = {
            "screen": None,
            "quit": False,
            "restart": False,
            "restart_to_wave1": False,
            "replay": False,
            "pop": False,
        }
        
        # Use shared navigation handler
        new_idx, confirmed, clicked_idx = handle_menu_navigation(
            events, len(VICTORY_OPTIONS), 
            game_state.ui.victory_selected,
            self._option_rects
        )
        game_state.ui.victory_selected = new_idx
        
        # Handle confirmation (Enter or click)
        selected = clicked_idx if clicked_idx >= 0 else (game_state.ui.victory_selected if confirmed else -1)
        if selected >= 0:
            if selected == 0:  # Enter High Score
                out["screen"] = STATE_NAME_INPUT
            elif selected == 1:  # Play Again
                out["replay"] = True
                out["screen"] = STATE_PLAYING
            elif selected == 2:  # Quit to Title
                out["screen"] = STATE_TITLE
            return out
        
        # Handle escape
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                out["screen"] = STATE_TITLE
                return out
        
        return out

    def update(self, dt: float, game_state, ctx: dict) -> None:
        pass

    def handle_input_transition(self, events, game_state, ctx: dict) -> SceneTransition:
        """Handle input and return transition if needed."""
        result = self.handle_input(events, game_state, ctx)
        self._last_input_result = result
        
        if result.get("screen") is not None:
            screen = result["screen"]
            if screen == STATE_NAME_INPUT:
                return SceneTransition.push(STATE_NAME_INPUT)
            elif screen == STATE_TITLE:
                return SceneTransition.replace(STATE_TITLE)
            elif screen == STATE_PLAYING and result.get("replay"):
                # Let game.py handle the replay logic
                return SceneTransition.none()
        
        return SceneTransition.none()

    def update_transition(self, dt: float, game_state, ctx: dict) -> SceneTransition:
        """Stub: call existing logic; return NONE."""
        self.update(dt, game_state, ctx)
        return SceneTransition.none()

    def render(self, render_ctx: RenderContext, game_state, ctx: dict) -> None:
        screen = render_ctx.screen
        w, h = render_ctx.width, render_ctx.height
        font, big_font = render_ctx.font, render_ctx.big_font
        
        # Semi-transparent overlay
        overlay = pygame.Surface((w, h))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 40))  # Dark blue tint for victory
        screen.blit(overlay, (0, 0))
        
        # Title
        draw_centered_text(screen, font, big_font, w, "VICTORY!", h // 2 - 150, color=(80, 255, 80), use_big=True)
        
        # Congratulations message
        draw_centered_text(screen, font, big_font, w, "You have conquered all waves!", h // 2 - 80, color=(200, 255, 200))
        
        # Show final score
        score = getattr(game_state, "score", 0)
        draw_centered_text(screen, font, big_font, w, f"Final Score: {score}", h // 2 - 50, color=(255, 255, 100))
        
        # Show final stats
        wave_num = getattr(game_state, "wave_number", 1)
        enemies_killed = getattr(game_state, "enemies_killed", 0)
        draw_centered_text(screen, font, big_font, w, f"Waves Completed: {wave_num} | Enemies Defeated: {enemies_killed}", h // 2 - 20, color=(200, 200, 200))
        
        # Menu options using shared helper
        selected = game_state.ui.victory_selected
        y_start = h // 2 + 40
        self._option_rects = render_menu_options(
            screen, font, big_font, w, VICTORY_OPTIONS,
            selected, y_start, line_height=45
        )
        
        # Instructions
        draw_centered_text(screen, font, big_font, w, "UP/DOWN: Select | ENTER: Confirm | ESC: Quit", h - 60, (150, 150, 150))

    def on_enter(self, game_state, ctx: dict) -> None:
        # Reset selection when entering
        game_state.ui.victory_selected = 0

    def on_exit(self, game_state, ctx: dict) -> None:
        pass
