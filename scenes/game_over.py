"""GameOverScene: game over screen with Try Again, Save, and Quit options."""
from __future__ import annotations

import pygame

from constants import STATE_GAME_OVER, STATE_SAVE_GAME, STATE_TITLE, STATE_PLAYING
from rendering import RenderContext, draw_centered_text
from scenes.transitions import SceneTransition


GAME_OVER_OPTIONS = ["Try Again (Current Wave)", "Save Progress", "Quit to Title"]


class GameOverScene:
    """Game over screen. Shows options to retry current wave, save, or quit."""

    def state_id(self) -> str:
        return STATE_GAME_OVER

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
        
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            
            if event.key in (pygame.K_UP, pygame.K_w):
                game_state.ui.game_over_selected = (game_state.ui.game_over_selected - 1) % len(GAME_OVER_OPTIONS)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                game_state.ui.game_over_selected = (game_state.ui.game_over_selected + 1) % len(GAME_OVER_OPTIONS)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                selected = game_state.ui.game_over_selected
                if selected == 0:  # Try Again
                    out["try_again"] = True
                    out["screen"] = STATE_PLAYING
                    return out
                elif selected == 1:  # Save
                    out["save"] = True
                    out["screen"] = STATE_SAVE_GAME
                    return out
                elif selected == 2:  # Quit to Title
                    out["screen"] = STATE_TITLE
                    return out
            elif event.key == pygame.K_ESCAPE:
                # ESC goes back to title
                out["screen"] = STATE_TITLE
                return out
        
        return out

    def update(self, dt: float, game_state, ctx: dict) -> None:
        pass

    def handle_input_transition(self, events, game_state, ctx: dict) -> SceneTransition:
        """Handle input and return transition if needed."""
        result = self.handle_input(events, game_state, ctx)
        # Store result for retrieval by game.py (avoids calling handle_input twice)
        self._last_input_result = result
        
        if result.get("screen") is not None:
            screen = result["screen"]
            if screen == STATE_PLAYING and result.get("try_again"):
                # Try again - handled by game.py to restart at game_over_wave
                return SceneTransition.none()  # Let game.py handle the restart
            elif screen == STATE_SAVE_GAME:
                return SceneTransition.push(STATE_SAVE_GAME)
            elif screen == STATE_TITLE:
                return SceneTransition.replace(STATE_TITLE)
        
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
        
        # Menu options
        selected = game_state.ui.game_over_selected
        y_start = h // 2 + 20
        
        for i, option in enumerate(GAME_OVER_OPTIONS):
            # Customize display for Try Again option
            if i == 0:
                display_text = f"Try Again (Wave {wave_num})"
            else:
                display_text = option
            
            if i == selected:
                color = (255, 255, 0)
                prefix = "-> "
            else:
                color = (200, 200, 200)
                prefix = "   "
            
            draw_centered_text(screen, font, big_font, w, f"{prefix}{display_text}", y_start + i * 45, color)
        
        # Instructions
        draw_centered_text(screen, font, big_font, w, "UP/DOWN: Select | ENTER: Confirm | ESC: Quit", h - 60, (150, 150, 150))

    def on_enter(self, game_state, ctx: dict) -> None:
        # Reset selection when entering
        game_state.ui.game_over_selected = 0

    def on_exit(self, game_state, ctx: dict) -> None:
        pass
