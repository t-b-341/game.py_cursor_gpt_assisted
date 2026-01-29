"""TitleScene: title screen with New Game, Quick Launch, and Load Game options. ESC toggles quit dialog."""
from __future__ import annotations

import random

import pygame

from constants import STATE_MENU, STATE_TITLE, STATE_LOAD_GAME, STATE_QUICK_LAUNCH
from rendering import RenderContext, draw_centered_text
from scenes.transitions import SceneTransition
from save_system import load_saves


TITLE_OPTIONS = ["New Game", "Quick Launch", "Load Game"]

# Ambient sound plays at random intervals between these values (seconds)
AMBIENT_SOUND_MIN_INTERVAL = 8.0
AMBIENT_SOUND_MAX_INTERVAL = 20.0


class TitleScene:
    """Title screen. Select New Game, Quick Launch, or Load Game; ESC -> quit confirm or stay."""

    def __init__(self):
        self._title_selected = 0  # 0=New Game, 1=Quick Launch, 2=Load Game
        self._ambient_timer = random.uniform(AMBIENT_SOUND_MIN_INTERVAL, AMBIENT_SOUND_MAX_INTERVAL)

    def state_id(self) -> str:
        return STATE_TITLE

    def handle_input(self, events, game_state, ctx: dict) -> dict:
        out = {"screen": None, "quit": False, "restart": False, "restart_to_wave1": False, "replay": False, "pop": False}
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key == pygame.K_ESCAPE:
                if game_state.ui.title_confirm_quit:
                    game_state.ui.title_confirm_quit = False
                else:
                    game_state.ui.title_confirm_quit = True
                continue
            if game_state.ui.title_confirm_quit:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_y):
                    out["quit"] = True
                    return out
                if event.key == pygame.K_n:
                    game_state.ui.title_confirm_quit = False
            else:
                if event.key in (pygame.K_UP, pygame.K_w):
                    self._title_selected = (self._title_selected - 1) % len(TITLE_OPTIONS)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self._title_selected = (self._title_selected + 1) % len(TITLE_OPTIONS)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    if self._title_selected == 0:
                        # New Game
                        out["screen"] = STATE_MENU
                    elif self._title_selected == 1:
                        # Quick Launch
                        out["screen"] = STATE_QUICK_LAUNCH
                    else:
                        # Load Game
                        out["screen"] = STATE_LOAD_GAME
                    return out
        return out

    def update(self, dt: float, game_state, ctx: dict) -> None:
        # Play ambient sound at random intervals
        self._ambient_timer -= dt
        if self._ambient_timer <= 0:
            from systems.audio_system import play_sfx
            play_sfx("AMBIENT")
            self._ambient_timer = random.uniform(AMBIENT_SOUND_MIN_INTERVAL, AMBIENT_SOUND_MAX_INTERVAL)

    def handle_input_transition(self, events, game_state, ctx: dict) -> SceneTransition:
        """Call existing handle_input logic and process the result. Return transition if needed."""
        result = self.handle_input(events, game_state, ctx)
        # Process result to handle screen changes, quit, etc.
        if result.get("quit"):
            return SceneTransition.quit_game()
        if result.get("screen") is not None:
            # Map screen changes to transitions
            screen = result["screen"]
            if screen == STATE_MENU:
                return SceneTransition.replace(STATE_MENU)
            elif screen == STATE_QUICK_LAUNCH:
                return SceneTransition.replace(STATE_QUICK_LAUNCH)
            elif screen == STATE_LOAD_GAME:
                return SceneTransition.push(STATE_LOAD_GAME)
        return SceneTransition.none()

    def update_transition(self, dt: float, game_state, ctx: dict) -> SceneTransition:
        """Stub: call existing logic; return NONE. Used by future scene-driven loop."""
        self.update(dt, game_state, ctx)
        return SceneTransition.none()

    def render(self, render_ctx: RenderContext, game_state, ctx: dict) -> None:
        screen = render_ctx.screen
        w, h = render_ctx.width, render_ctx.height
        font, big_font = render_ctx.font, render_ctx.big_font
        
        if game_state.ui.title_confirm_quit:
            draw_centered_text(screen, font, big_font, w, "Are you sure you want to exit?", h // 2 - 40, color=(220, 220, 220))
            draw_centered_text(screen, font, big_font, w, "ENTER or Y to quit", h // 2 + 20, (180, 180, 180))
            draw_centered_text(screen, font, big_font, w, "ESC or N to stay", h // 2 + 60, (180, 180, 180))
        else:
            # Title
            draw_centered_text(screen, font, big_font, w, "GAME", h // 2 - 100, color=(220, 220, 220), use_big=True)
            
            # Check if any saves exist to show indicator
            saves = load_saves()
            has_saves = any(saves.get(i) is not None for i in range(3))
            
            # Menu options
            y_start = h // 2 - 10
            for i, option in enumerate(TITLE_OPTIONS):
                if i == self._title_selected:
                    color = (255, 255, 0)
                    prefix = "-> "
                else:
                    color = (200, 200, 200)
                    prefix = "   "
                
                # Add indicator for Load Game if saves exist (now at index 2)
                suffix = ""
                if i == 2 and has_saves:
                    suffix = " *"
                
                draw_centered_text(screen, font, big_font, w, f"{prefix}{option}{suffix}", y_start + i * 45, color)
            
            # Instructions
            draw_centered_text(screen, font, big_font, w, "UP/DOWN: Select | ENTER: Confirm | ESC: Quit", h - 60, (150, 150, 150))

    def on_enter(self, game_state, ctx: dict) -> None:
        self._title_selected = 0
        game_state.ui.title_confirm_quit = False
        # Reset ambient timer
        self._ambient_timer = random.uniform(AMBIENT_SOUND_MIN_INTERVAL, AMBIENT_SOUND_MAX_INTERVAL)

    def on_exit(self, game_state, ctx: dict) -> None:
        pass
