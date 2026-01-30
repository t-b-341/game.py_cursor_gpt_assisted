"""QuickLaunchScene: streamlined game start with difficulty selection and load game."""
from __future__ import annotations

import pygame

from constants import STATE_PLAYING, STATE_TITLE, STATE_QUICK_LAUNCH, STATE_LOAD_GAME, difficulty_options
from rendering import RenderContext, draw_centered_text
from scenes.transitions import SceneTransition
from save_system import load_saves


# Menu options: difficulties + Load Game
_LOAD_GAME_OPTION = "Load Saved Game"


class QuickLaunchScene:
    """Quick launch screen. Select difficulty to start new game, or load a saved game."""

    def __init__(self):
        self._selected = 1  # Default to NORMAL (index 1)
        self._has_saves = False  # Cache whether saves exist

    def state_id(self) -> str:
        return STATE_QUICK_LAUNCH

    def _get_menu_options(self) -> list[str]:
        """Get menu options including Load Game if saves exist."""
        options = list(difficulty_options)
        if self._has_saves:
            options.append(_LOAD_GAME_OPTION)
        return options

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
        
        menu_options = self._get_menu_options()
        num_options = len(menu_options)

        for event in events:
            if event.type != pygame.KEYDOWN:
                continue

            if event.key == pygame.K_ESCAPE:
                # Go back to title screen
                out["screen"] = STATE_TITLE
                return out
            
            # Quick key: L for Load Game
            if event.key == pygame.K_l and self._has_saves:
                out["screen"] = STATE_LOAD_GAME
                return out

            if event.key in (pygame.K_UP, pygame.K_w):
                self._selected = (self._selected - 1) % num_options
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._selected = (self._selected + 1) % num_options
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                selected_option = menu_options[self._selected]
                
                # Check if Load Game was selected
                if selected_option == _LOAD_GAME_OPTION:
                    out["screen"] = STATE_LOAD_GAME
                    return out
                
                # Otherwise, it's a difficulty - start new game
                cfg.difficulty = selected_option
                
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
        if result.get("screen") == STATE_LOAD_GAME:
            return SceneTransition.push(STATE_LOAD_GAME)
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

        # Menu options
        menu_options = self._get_menu_options()
        y = h // 2 - 40
        draw_centered_text(screen, font, big_font, w, "Select Difficulty or Load Game:", y - 60)
        
        for i, option in enumerate(menu_options):
            if i == self._selected:
                color = (255, 255, 0)
                prefix = "-> "
            else:
                color = (200, 200, 200)
                prefix = "   "
            draw_centered_text(screen, font, big_font, w, f"{prefix}{option}", y + i * 45, color)

        # Instructions
        hint = "UP/DOWN: Select | ENTER: Confirm | ESC: Back"
        if self._has_saves:
            hint += " | L: Load Game"
        draw_centered_text(
            screen, font, big_font, w,
            hint,
            h - 60, (150, 150, 150)
        )

    def on_enter(self, game_state, ctx: dict) -> None:
        self._selected = 1  # Reset to NORMAL on enter
        # Check if any saves exist
        saves = load_saves()
        self._has_saves = any(slot is not None for slot in saves.values())

    def on_exit(self, game_state, ctx: dict) -> None:
        pass
