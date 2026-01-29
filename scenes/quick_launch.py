"""QuickLaunchScene: streamlined game start with only difficulty selection."""
from __future__ import annotations

import pygame

from constants import STATE_PLAYING, STATE_TITLE, STATE_QUICK_LAUNCH, difficulty_options
from rendering import RenderContext, draw_centered_text
from scenes.transitions import SceneTransition


class QuickLaunchScene:
    """Quick launch screen. Select difficulty and immediately start the game."""

    def __init__(self):
        self._difficulty_selected = 1  # Default to NORMAL (index 1)

    def state_id(self) -> str:
        return STATE_QUICK_LAUNCH

    def handle_input(self, events, game_state, ctx: dict) -> dict:
        out = {
            "screen": None,
            "quit": False,
            "restart": False,
            "restart_to_wave1": False,
            "replay": False,
            "pop": False,
            "start_game": False,
        }
        app_ctx = ctx.get("app_ctx")
        if app_ctx is None:
            return out
        cfg = app_ctx.config

        for event in events:
            if event.type != pygame.KEYDOWN:
                continue

            if event.key == pygame.K_ESCAPE:
                # Go back to title screen
                out["screen"] = STATE_TITLE
                return out

            if event.key in (pygame.K_UP, pygame.K_w):
                self._difficulty_selected = (self._difficulty_selected - 1) % len(difficulty_options)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._difficulty_selected = (self._difficulty_selected + 1) % len(difficulty_options)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                # Set difficulty
                cfg.difficulty = difficulty_options[self._difficulty_selected]
                
                # Set sensible defaults for quick launch
                cfg.profile_enabled = False
                cfg.show_metrics = True
                cfg.show_hud = True
                cfg.enable_telemetry = False
                
                # Reset menu section in case they later go to full options
                game_state.ui.menu_section = 0
                game_state.ui.endurance_mode_selected = 0  # Normal mode, not endurance
                
                # Signal game start
                out["screen"] = STATE_PLAYING
                out["start_game"] = True
                return out

        return out

    def update(self, dt: float, game_state, ctx: dict) -> None:
        pass

    def handle_input_transition(self, events, game_state, ctx: dict) -> SceneTransition:
        """Call existing handle_input logic and process the result."""
        result = self.handle_input(events, game_state, ctx)
        # Store result for retrieval by game.py (avoids calling handle_input twice)
        self._last_input_result = result
        if result.get("screen") == STATE_TITLE:
            return SceneTransition.replace(STATE_TITLE)
        # start_game is handled by the main loop, return NONE
        return SceneTransition.none()

    def update_transition(self, dt: float, game_state, ctx: dict) -> SceneTransition:
        """Stub: call existing logic; return NONE."""
        self.update(dt, game_state, ctx)
        return SceneTransition.none()

    def render(self, render_ctx: RenderContext, game_state, ctx: dict) -> None:
        screen = render_ctx.screen
        w, h = render_ctx.width, render_ctx.height
        font, big_font = render_ctx.font, render_ctx.big_font

        # Title
        draw_centered_text(screen, font, big_font, w, "QUICK LAUNCH", h // 4, use_big=True)

        # Difficulty selection
        y = h // 2 - 40
        draw_centered_text(screen, font, big_font, w, "Select Difficulty:", y - 60)
        
        for i, difficulty in enumerate(difficulty_options):
            if i == self._difficulty_selected:
                color = (255, 255, 0)
                prefix = "-> "
            else:
                color = (200, 200, 200)
                prefix = "   "
            draw_centered_text(screen, font, big_font, w, f"{prefix}{difficulty}", y + i * 45, color)

        # Instructions
        draw_centered_text(
            screen, font, big_font, w,
            "UP/DOWN: Select | ENTER: Start Game | ESC: Back",
            h - 60, (150, 150, 150)
        )

    def on_enter(self, game_state, ctx: dict) -> None:
        self._difficulty_selected = 1  # Reset to NORMAL on enter

    def on_exit(self, game_state, ctx: dict) -> None:
        pass
