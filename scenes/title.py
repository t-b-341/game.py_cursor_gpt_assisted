"""TitleScene: title screen with background image and Start Game button."""
from __future__ import annotations

import random
from pathlib import Path

import pygame

from constants import STATE_MENU, STATE_TITLE, STATE_LOAD_GAME, STATE_QUICK_LAUNCH
from rendering import RenderContext, draw_centered_text
from scenes.transitions import SceneTransition
from save_system import load_saves
from resource_paths import get_resource_path


# Ambient sound plays at random intervals between these values (seconds)
AMBIENT_SOUND_MIN_INTERVAL = 8.0
AMBIENT_SOUND_MAX_INTERVAL = 20.0

# Cached background image
_title_bg_image: pygame.Surface | None = None
_title_bg_size: tuple[int, int] | None = None


def _load_title_background(width: int, height: int) -> pygame.Surface | None:
    """Load and cache the title background image, scaled to screen size."""
    global _title_bg_image, _title_bg_size
    
    if _title_bg_image is not None and _title_bg_size == (width, height):
        return _title_bg_image
    
    try:
        img_path = Path(get_resource_path("assets/images/title_screen.png"))
        if img_path.exists():
            img = pygame.image.load(str(img_path)).convert()
            _title_bg_image = pygame.transform.smoothscale(img, (width, height))
            _title_bg_size = (width, height)
            return _title_bg_image
    except Exception as e:
        print(f"[Title] Failed to load background: {e}")
    
    return None


class TitleScene:
    """Title screen with background image. Click Start Game or press Enter/Space to begin."""

    def __init__(self):
        self._ambient_timer = random.uniform(AMBIENT_SOUND_MIN_INTERVAL, AMBIENT_SOUND_MAX_INTERVAL)
        # Start Game button area (will be calculated based on screen size)
        self._start_button_rect: pygame.Rect | None = None

    def state_id(self) -> str:
        return STATE_TITLE

    def _get_start_button_rect(self, width: int, height: int) -> pygame.Rect:
        """Calculate the clickable area for the Start Game button.
        
        Based on the title_screen.png image, the green "Start Game" button
        is roughly centered horizontally and positioned about 55-65% down the screen.
        """
        # Button is approximately centered, about 55-65% down the screen
        # Button is roughly 200-250 pixels wide and 50-60 pixels tall (relative to 1920x1080)
        scale_x = width / 1920
        scale_y = height / 1080
        
        btn_width = int(280 * scale_x)
        btn_height = int(60 * scale_y)
        btn_x = (width - btn_width) // 2
        btn_y = int(height * 0.56)  # About 56% down the screen
        
        return pygame.Rect(btn_x, btn_y, btn_width, btn_height)

    def handle_input(self, events, game_state, ctx: dict) -> dict:
        out = {"screen": None, "quit": False, "restart": False, "restart_to_wave1": False, "replay": False, "pop": False}
        
        width = ctx.get("width", 1920)
        height = ctx.get("height", 1080)
        self._start_button_rect = self._get_start_button_rect(width, height)
        
        for event in events:
            # Handle quit confirmation dialog
            if game_state.ui.title_confirm_quit:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_y):
                        out["quit"] = True
                        return out
                    if event.key in (pygame.K_n, pygame.K_ESCAPE):
                        game_state.ui.title_confirm_quit = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # Click anywhere to dismiss quit dialog
                    game_state.ui.title_confirm_quit = False
                continue
            
            # ESC to show quit confirmation
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                game_state.ui.title_confirm_quit = True
                continue
            
            # Enter, Space, or click anywhere -> go to next menu
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    out["screen"] = STATE_MENU
                    return out
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Click anywhere to start
                out["screen"] = STATE_MENU
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
        
        # Draw background image
        bg = _load_title_background(w, h)
        if bg:
            screen.blit(bg, (0, 0))
        else:
            # Fallback: dark background
            screen.fill((20, 20, 40))
            draw_centered_text(screen, font, big_font, w, "GAME", h // 2 - 100, color=(220, 220, 220), use_big=True)
        
        if game_state.ui.title_confirm_quit:
            # Draw semi-transparent overlay
            overlay = pygame.Surface((w, h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0, 0))
            
            draw_centered_text(screen, font, big_font, w, "Are you sure you want to exit?", h // 2 - 40, color=(220, 220, 220))
            draw_centered_text(screen, font, big_font, w, "ENTER or Y to quit", h // 2 + 20, (180, 180, 180))
            draw_centered_text(screen, font, big_font, w, "ESC or N to stay", h // 2 + 60, (180, 180, 180))
        else:
            # Draw subtle instruction text at bottom
            draw_centered_text(screen, font, big_font, w, "Press ENTER or Click START GAME", h - 40, (200, 200, 200))

    def on_enter(self, game_state, ctx: dict) -> None:
        game_state.ui.title_confirm_quit = False
        # Reset ambient timer
        self._ambient_timer = random.uniform(AMBIENT_SOUND_MIN_INTERVAL, AMBIENT_SOUND_MAX_INTERVAL)

    def on_exit(self, game_state, ctx: dict) -> None:
        pass
