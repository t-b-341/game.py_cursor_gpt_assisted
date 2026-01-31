"""SaveGameScene: screen for saving game progress to one of 3 slots."""
from __future__ import annotations

import pygame

from constants import STATE_SAVE_GAME, STATE_GAME_OVER, STATE_TITLE
from rendering import RenderContext, draw_centered_text
from rendering.menu_helpers import handle_menu_navigation
from scenes.transitions import SceneTransition
from save_system import load_saves, save_game, get_save_display_text, MAX_SAVE_SLOTS


class SaveGameScene:
    """Save game screen. Select a slot, enter a name, and save."""

    def __init__(self):
        self._option_rects: list[pygame.Rect] = []

    def state_id(self) -> str:
        return STATE_SAVE_GAME

    def handle_input(self, events, game_state, ctx: dict) -> dict:
        out = {
            "screen": None,
            "quit": False,
            "restart": False,
            "pop": False,
            "saved": False,
        }
        
        app_ctx = ctx.get("app_ctx")
        cfg = getattr(app_ctx, "config", None) if app_ctx else None
        
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            
            # Handle name input mode
            if game_state.ui.save_name_active:
                if event.key == pygame.K_ESCAPE:
                    # Cancel name input
                    game_state.ui.save_name_active = False
                    game_state.ui.save_name_input = ""
                elif event.key == pygame.K_BACKSPACE:
                    game_state.ui.save_name_input = game_state.ui.save_name_input[:-1]
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    # Save the game
                    slot_id = game_state.ui.save_slot_selected
                    name = game_state.ui.save_name_input.strip()
                    if not name:
                        name = f"Save {slot_id + 1}"
                    
                    # Get config values
                    difficulty = getattr(cfg, "difficulty", "NORMAL") if cfg else "NORMAL"
                    player_class = getattr(cfg, "player_class", "BALANCED") if cfg else "BALANCED"
                    
                    # Determine wave to save:
                    # - From pause menu (save_and_quit): use current wave_number
                    # - From game over: use game_over_wave
                    if game_state.ui.save_and_quit:
                        wave_to_save = max(1, game_state.wave_number)
                    else:
                        wave_to_save = max(1, getattr(game_state, "game_over_wave", game_state.wave_number))
                    
                    success = save_game(
                        slot_id=slot_id,
                        name=name,
                        wave_number=wave_to_save,
                        difficulty=difficulty,
                        player_class=player_class,
                        score=game_state.score,
                    )
                    
                    if success:
                        out["saved"] = True
                        game_state.ui.save_name_active = False
                        game_state.ui.save_name_input = ""
                        
                        # If save_and_quit, go to title; otherwise pop back
                        if game_state.ui.save_and_quit:
                            game_state.ui.save_and_quit = False  # Reset flag
                            out["screen"] = STATE_TITLE
                        else:
                            out["pop"] = True  # Go back to game over screen
                        return out
                elif event.unicode and len(game_state.ui.save_name_input) < 20:
                    # Only allow printable characters
                    if event.unicode.isprintable():
                        game_state.ui.save_name_input += event.unicode
                continue
            
        # Normal navigation (when not in name input mode)
        new_idx, confirmed, clicked_idx = handle_menu_navigation(
            events, MAX_SAVE_SLOTS,
            game_state.ui.save_slot_selected,
            self._option_rects
        )
        game_state.ui.save_slot_selected = new_idx
        
        # Handle confirmation - activate name input
        if confirmed or clicked_idx >= 0:
            game_state.ui.save_name_active = True
            game_state.ui.save_name_input = ""
        
        # Handle escape
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                out["pop"] = True
                return out
        
        return out

    def update(self, dt: float, game_state, ctx: dict) -> None:
        pass

    def handle_input_transition(self, events, game_state, ctx: dict) -> SceneTransition:
        """Handle input and return transition if needed."""
        result = self.handle_input(events, game_state, ctx)
        # Store result for retrieval by game.py (avoids calling handle_input twice)
        self._last_input_result = result
        
        if result.get("screen") == STATE_TITLE:
            return SceneTransition.replace(STATE_TITLE)
        
        if result.get("pop"):
            return SceneTransition.pop()
        
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
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))
        
        # Title
        draw_centered_text(screen, font, big_font, w, "SAVE GAME", h // 2 - 180, color=(100, 200, 255), use_big=True)
        
        # Instructions - show correct wave based on context
        if game_state.ui.save_and_quit:
            wave_num = game_state.wave_number
        else:
            wave_num = getattr(game_state, "game_over_wave", game_state.wave_number)
        draw_centered_text(screen, font, big_font, w, f"Saving progress at Wave {wave_num}", h // 2 - 120, color=(180, 180, 180))
        
        # Load current saves
        saves = load_saves()
        selected = game_state.ui.save_slot_selected
        
        # Render slots and calculate clickable rects
        y_start = h // 2 - 60
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
                color = (200, 200, 200)
                prefix = "   "
            
            # Show slot number
            y = y_start + i * line_height
            slot_label = f"Slot {i + 1}: "
            draw_centered_text(screen, font, big_font, w, f"{prefix}{slot_label}{display_text}", y, color)
            
            # Store clickable rect
            click_rect = pygame.Rect((w - option_width) // 2, y - line_height // 2, option_width, line_height)
            self._option_rects.append(click_rect)
        
        # Name input overlay
        if game_state.ui.save_name_active:
            # Draw input box
            input_y = h // 2 + 100
            draw_centered_text(screen, font, big_font, w, "Enter save name:", input_y, color=(255, 255, 255))
            
            # Input field with cursor
            name = game_state.ui.save_name_input
            cursor = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
            draw_centered_text(screen, font, big_font, w, f"[ {name}{cursor} ]", input_y + 40, color=(255, 255, 0))
            
            draw_centered_text(screen, font, big_font, w, "ENTER: Confirm | ESC: Cancel", input_y + 90, (150, 150, 150))
        else:
            # Normal instructions
            draw_centered_text(screen, font, big_font, w, "UP/DOWN: Select Slot | ENTER: Save to Slot | ESC: Back", h - 60, (150, 150, 150))

    def on_enter(self, game_state, ctx: dict) -> None:
        # Reset state when entering
        game_state.ui.save_slot_selected = 0
        game_state.ui.save_name_active = False
        game_state.ui.save_name_input = ""

    def on_exit(self, game_state, ctx: dict) -> None:
        game_state.ui.save_name_active = False
        game_state.ui.save_name_input = ""
        # Reset save_and_quit flag if user cancelled without saving
        game_state.ui.save_and_quit = False
