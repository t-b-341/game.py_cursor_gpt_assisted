"""OptionsScene: pre-game menu (difficulty, profile, class, HUD, telemetry, weapon, start).

Refactored to use a dispatcher pattern for cleaner section handling.
Each menu section has its own input handler and render method.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import pygame

from constants import (
    STATE_PLAYING,
    STATE_TITLE,
    STATE_MENU,
    difficulty_options,
    character_profile_options,
    custom_profile_stats_keys,
    custom_profile_stats_list,
    player_class_options,
    weapon_selection_options,
)
from rendering import RenderContext, draw_centered_text
from scenes.transitions import SceneTransition
from profile_system import load_profiles, save_profile, delete_profile, get_profile_display_text

if TYPE_CHECKING:
    from state import GameState
    from context import AppContext


def _get_menu_option_rects(width: int, height: int, y_start: int, num_options: int, line_height: int = 40) -> list[pygame.Rect]:
    """Calculate clickable rectangles for centered menu options."""
    rects = []
    option_width = 400  # Approximate clickable width
    for i in range(num_options):
        y = y_start + i * line_height
        rect = pygame.Rect((width - option_width) // 2, y - 15, option_width, line_height)
        rects.append(rect)
    return rects


# -----------------------------------------------------------------------------
# Navigation key helpers
# -----------------------------------------------------------------------------
_NAV_UP = (pygame.K_UP, pygame.K_w)
_NAV_DOWN = (pygame.K_DOWN, pygame.K_s)
_NAV_LEFT = (pygame.K_LEFT, pygame.K_a)
_NAV_RIGHT = (pygame.K_RIGHT, pygame.K_d)
_NAV_CONFIRM = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
_NAV_CONFIRM_RIGHT = _NAV_RIGHT + _NAV_CONFIRM


def _cycle_selection(current: int, delta: int, num_options: int) -> int:
    """Cycle selection index with wraparound."""
    return (current + delta) % num_options


class OptionsScene:
    """Options / main menu. All menu_section navigation and start-game intent via return value."""

    def state_id(self) -> str:
        return STATE_MENU

    def __init__(self):
        self._last_input_result = None
        self._option_rects: list[pygame.Rect] = []

    # -------------------------------------------------------------------------
    # Section Input Handlers
    # -------------------------------------------------------------------------
    def _handle_section_0_difficulty(self, event: pygame.event.Event, game_state, cfg, out: dict) -> dict | None:
        """Section 0: Difficulty selection."""
        if event.key in _NAV_UP:
            game_state.ui.difficulty_selected = _cycle_selection(game_state.ui.difficulty_selected, -1, len(difficulty_options))
        elif event.key in _NAV_DOWN:
            game_state.ui.difficulty_selected = _cycle_selection(game_state.ui.difficulty_selected, 1, len(difficulty_options))
        elif event.key in _NAV_LEFT:
            out["screen"] = STATE_TITLE
            game_state.ui.menu_confirm_quit = False
            return out
        elif event.key in _NAV_CONFIRM_RIGHT:
            cfg.difficulty = difficulty_options[game_state.ui.difficulty_selected]
            game_state.ui.menu_section = 1.5
        return None

    def _handle_section_1_5_use_profile(self, event: pygame.event.Event, game_state, cfg, out: dict) -> dict | None:
        """Section 1.5: Use character profile?"""
        if event.key in _NAV_UP:
            game_state.ui.use_character_profile_selected = _cycle_selection(game_state.ui.use_character_profile_selected, -1, 2)
        elif event.key in _NAV_DOWN:
            game_state.ui.use_character_profile_selected = _cycle_selection(game_state.ui.use_character_profile_selected, 1, 2)
        elif event.key in _NAV_LEFT:
            game_state.ui.menu_section = 0
        elif event.key in _NAV_CONFIRM_RIGHT:
            cfg.profile_enabled = game_state.ui.use_character_profile_selected == 1
            game_state.ui.menu_section = 2 if cfg.profile_enabled else 3
        return None

    def _handle_section_2_profile_type(self, event: pygame.event.Event, game_state, cfg, out: dict) -> dict | None:
        """Section 2: Character profile type."""
        if event.key in _NAV_UP:
            game_state.ui.character_profile_selected = _cycle_selection(game_state.ui.character_profile_selected, -1, len(character_profile_options))
        elif event.key in _NAV_DOWN:
            game_state.ui.character_profile_selected = _cycle_selection(game_state.ui.character_profile_selected, 1, len(character_profile_options))
        elif event.key in _NAV_LEFT:
            game_state.ui.menu_section = 1.5
        elif event.key in _NAV_CONFIRM_RIGHT:
            if game_state.ui.character_profile_selected == 0:
                game_state.ui.menu_section = 7  # Premade profiles -> class selection
            elif game_state.ui.character_profile_selected == 1:
                game_state.ui.custom_profile_stat_selected = 0
                game_state.ui.menu_section = 6  # Custom profile creator
            else:
                game_state.ui.saved_profile_selected = 0
                game_state.ui.menu_section = 8  # Load saved profile list
        return None

    def _handle_section_3_hud(self, event: pygame.event.Event, game_state, cfg, out: dict) -> dict | None:
        """Section 3: HUD options."""
        if event.key in _NAV_UP:
            game_state.ui.ui_show_metrics_selected = _cycle_selection(game_state.ui.ui_show_metrics_selected, -1, 2)
        elif event.key in _NAV_DOWN:
            game_state.ui.ui_show_metrics_selected = _cycle_selection(game_state.ui.ui_show_metrics_selected, 1, 2)
        elif event.key in _NAV_LEFT:
            # Go back based on profile type
            if not cfg.profile_enabled:
                game_state.ui.menu_section = 1.5
            elif game_state.ui.character_profile_selected == 0:
                game_state.ui.menu_section = 7  # Premade class selection
            elif game_state.ui.character_profile_selected == 1:
                game_state.ui.menu_section = 6  # Custom profile creator
            else:
                game_state.ui.menu_section = 8  # Saved profile list
        elif event.key in _NAV_CONFIRM_RIGHT:
            cfg.show_metrics = game_state.ui.ui_show_metrics_selected == 0
            cfg.show_hud = cfg.show_metrics
            game_state.ui.menu_section = 3.25  # Go to FPS toggle
        return None

    def _handle_section_3_25_fps(self, event: pygame.event.Event, game_state, cfg, out: dict) -> dict | None:
        """Section 3.25: FPS Graph toggle."""
        if event.key in _NAV_UP:
            game_state.ui.ui_show_fps_selected = _cycle_selection(game_state.ui.ui_show_fps_selected, -1, 2)
        elif event.key in _NAV_DOWN:
            game_state.ui.ui_show_fps_selected = _cycle_selection(game_state.ui.ui_show_fps_selected, 1, 2)
        elif event.key in _NAV_LEFT:
            game_state.ui.menu_section = 3
        elif event.key in _NAV_CONFIRM_RIGHT:
            cfg.show_fps = game_state.ui.ui_show_fps_selected == 0
            game_state.ui.menu_section = 3.5
        return None

    def _handle_section_3_5_telemetry(self, event: pygame.event.Event, game_state, cfg, out: dict) -> dict | None:
        """Section 3.5: Telemetry toggle."""
        if event.key in _NAV_UP:
            game_state.ui.ui_telemetry_enabled_selected = _cycle_selection(game_state.ui.ui_telemetry_enabled_selected, -1, 2)
        elif event.key in _NAV_DOWN:
            game_state.ui.ui_telemetry_enabled_selected = _cycle_selection(game_state.ui.ui_telemetry_enabled_selected, 1, 2)
        elif event.key in _NAV_LEFT:
            game_state.ui.menu_section = 3
        elif event.key in _NAV_CONFIRM_RIGHT:
            cfg.enable_telemetry = game_state.ui.ui_telemetry_enabled_selected == 0
            game_state.ui.menu_section = 4 if cfg.testing_mode else 5
        return None

    def _handle_section_4_weapon(self, event: pygame.event.Event, game_state, cfg, out: dict) -> dict | None:
        """Section 4: Weapon selection (testing mode)."""
        if event.key in _NAV_UP:
            game_state.ui.beam_selection_selected = _cycle_selection(game_state.ui.beam_selection_selected, -1, len(weapon_selection_options))
        elif event.key in _NAV_DOWN:
            game_state.ui.beam_selection_selected = _cycle_selection(game_state.ui.beam_selection_selected, 1, len(weapon_selection_options))
        elif event.key in _NAV_LEFT:
            game_state.ui.menu_section = 3.5
        elif event.key in _NAV_CONFIRM_RIGHT:
            sel = weapon_selection_options[game_state.ui.beam_selection_selected]
            game_state.unlocked_weapons.add(sel)
            if game_state.current_weapon_mode == "laser" and sel != "laser":
                game_state.laser_beams.clear()
            game_state.current_weapon_mode = sel
            game_state.beam_selection_pattern = sel
            game_state.ui.menu_section = 4.5 if cfg.testing_mode else 5
        return None

    def _handle_section_4_5_invuln(self, event: pygame.event.Event, game_state, cfg, out: dict) -> dict | None:
        """Section 4.5: Invulnerability toggle (testing mode)."""
        if event.key in (_NAV_UP + _NAV_DOWN):
            cfg.invulnerability_mode = not cfg.invulnerability_mode
        elif event.key in _NAV_LEFT:
            game_state.ui.menu_section = 4
        elif event.key in _NAV_CONFIRM_RIGHT:
            game_state.ui.menu_section = 5
        return None

    def _handle_section_5_ready(self, event: pygame.event.Event, game_state, cfg, out: dict) -> dict | None:
        """Section 5: Ready to start."""
        if event.key in _NAV_LEFT:
            game_state.ui.menu_section = 3.5
        elif event.key in _NAV_CONFIRM:
            out["screen"] = STATE_PLAYING
            out["start_game"] = True
            return out
        return None

    def _handle_section_6_custom_profile(self, event: pygame.event.Event, game_state, cfg, out: dict) -> dict | None:
        """Section 6: Custom profile creator."""
        num_stats = len(custom_profile_stats_list)
        num_options = num_stats + 3  # stats + Done + Save Profile + Back

        if event.key in _NAV_UP:
            game_state.ui.custom_profile_stat_selected = _cycle_selection(game_state.ui.custom_profile_stat_selected, -1, num_options)
        elif event.key in _NAV_DOWN:
            game_state.ui.custom_profile_stat_selected = _cycle_selection(game_state.ui.custom_profile_stat_selected, 1, num_options)
        elif event.key in _NAV_LEFT:
            if game_state.ui.custom_profile_stat_selected < num_stats:
                sk = custom_profile_stats_keys[game_state.ui.custom_profile_stat_selected]
                game_state.custom_profile_stats[sk] = max(0.5, round(game_state.custom_profile_stats[sk] - 0.1, 1))
        elif event.key in _NAV_RIGHT:
            if game_state.ui.custom_profile_stat_selected < num_stats:
                sk = custom_profile_stats_keys[game_state.ui.custom_profile_stat_selected]
                game_state.custom_profile_stats[sk] = min(3.0, round(game_state.custom_profile_stats[sk] + 0.1, 1))
        elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
            if game_state.ui.custom_profile_stat_selected < num_stats:
                sk = custom_profile_stats_keys[game_state.ui.custom_profile_stat_selected]
                game_state.custom_profile_stats[sk] = min(3.0, round(game_state.custom_profile_stats[sk] + 0.1, 1))
        elif event.key == pygame.K_MINUS:
            if game_state.ui.custom_profile_stat_selected < num_stats:
                sk = custom_profile_stats_keys[game_state.ui.custom_profile_stat_selected]
                game_state.custom_profile_stats[sk] = max(0.5, round(game_state.custom_profile_stats[sk] - 0.1, 1))
        elif event.key in _NAV_CONFIRM:
            if game_state.ui.custom_profile_stat_selected == num_stats:
                game_state.ui.menu_section = 3  # Done
            elif game_state.ui.custom_profile_stat_selected == num_stats + 1:
                game_state.ui.profile_name_input = ""
                game_state.ui.profile_name_active = True
                game_state.ui.menu_section = 9  # Save Profile
            elif game_state.ui.custom_profile_stat_selected == num_stats + 2:
                game_state.ui.menu_section = 2  # Back
        return None

    def _handle_section_7_class(self, event: pygame.event.Event, game_state, cfg, out: dict) -> dict | None:
        """Section 7: Class selection."""
        if event.key in _NAV_UP:
            game_state.ui.player_class_selected = _cycle_selection(game_state.ui.player_class_selected, -1, len(player_class_options))
        elif event.key in _NAV_DOWN:
            game_state.ui.player_class_selected = _cycle_selection(game_state.ui.player_class_selected, 1, len(player_class_options))
        elif event.key in _NAV_LEFT:
            game_state.ui.menu_section = 2
        elif event.key in _NAV_CONFIRM_RIGHT:
            cfg.player_class = player_class_options[game_state.ui.player_class_selected]
            game_state.ui.menu_section = 3
        return None

    def _handle_section_8_load_profile(self, event: pygame.event.Event, game_state, cfg, out: dict) -> dict | None:
        """Section 8: Load saved profile list."""
        profiles = load_profiles()
        num_profiles = len(profiles)
        total_options = num_profiles + 2  # profiles + Create New + Back

        if event.key in _NAV_UP:
            game_state.ui.saved_profile_selected = _cycle_selection(game_state.ui.saved_profile_selected, -1, total_options)
        elif event.key in _NAV_DOWN:
            game_state.ui.saved_profile_selected = _cycle_selection(game_state.ui.saved_profile_selected, 1, total_options)
        elif event.key == pygame.K_DELETE:
            if game_state.ui.saved_profile_selected < num_profiles and num_profiles > 0:
                profile_to_delete = profiles[game_state.ui.saved_profile_selected]
                delete_profile(profile_to_delete.profile_id)
                new_profiles = load_profiles()
                if game_state.ui.saved_profile_selected >= len(new_profiles):
                    game_state.ui.saved_profile_selected = max(0, len(new_profiles) - 1)
        elif event.key in _NAV_CONFIRM:
            if game_state.ui.saved_profile_selected < num_profiles and num_profiles > 0:
                selected_profile = profiles[game_state.ui.saved_profile_selected]
                game_state.custom_profile_stats["hp_mult"] = selected_profile.hp_mult
                game_state.custom_profile_stats["speed_mult"] = selected_profile.speed_mult
                game_state.custom_profile_stats["damage_mult"] = selected_profile.damage_mult
                game_state.custom_profile_stats["firerate_mult"] = selected_profile.firerate_mult
                game_state.ui.menu_section = 3
            elif game_state.ui.saved_profile_selected == num_profiles:
                game_state.ui.custom_profile_stat_selected = 0
                game_state.ui.menu_section = 6  # Create New
            else:
                game_state.ui.menu_section = 2  # Back
        return None

    def _handle_section_9_save_name(self, event: pygame.event.Event, game_state, cfg, out: dict) -> dict | None:
        """Section 9: Save profile name input."""
        if not game_state.ui.profile_name_active:
            return None

        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            name = game_state.ui.profile_name_input.strip() or "Custom Profile"
            save_profile(
                name=name,
                hp_mult=game_state.custom_profile_stats["hp_mult"],
                speed_mult=game_state.custom_profile_stats["speed_mult"],
                damage_mult=game_state.custom_profile_stats["damage_mult"],
                firerate_mult=game_state.custom_profile_stats["firerate_mult"],
            )
            game_state.ui.profile_name_active = False
            game_state.ui.profile_name_input = ""
            game_state.ui.menu_section = 6
        elif event.key == pygame.K_BACKSPACE:
            game_state.ui.profile_name_input = game_state.ui.profile_name_input[:-1]
        elif event.unicode and len(game_state.ui.profile_name_input) < 20:
            if event.unicode.isprintable():
                game_state.ui.profile_name_input += event.unicode
        return None

    def _handle_escape_navigation(self, game_state, cfg) -> str | None:
        """Handle ESC key to navigate back through menu sections. Returns STATE_TITLE if should exit."""
        ms = game_state.ui.menu_section
        
        back_map = {
            0: "exit",  # At root - go to title
            1.5: 0,
            2: 1.5,
            3: None,  # Special handling below
            3.25: 3,
            3.5: 3.25,
            4: 3.5,
            4.5: 4,
            5: 3.5,
            6: 2,  # Also clear profile_name_active
            7: 2,
            8: 2,
            9: 6,  # Also clear profile_name_active
        }
        
        if ms in (6, 9):
            game_state.ui.profile_name_active = False
        
        if ms == 0:
            return STATE_TITLE
        elif ms == 3:
            # HUD options - go back based on profile settings
            if cfg.profile_enabled:
                if game_state.ui.character_profile_selected == 0:
                    game_state.ui.menu_section = 7
                elif game_state.ui.character_profile_selected == 1:
                    game_state.ui.menu_section = 6
                else:
                    game_state.ui.menu_section = 8
            else:
                game_state.ui.menu_section = 1.5
        elif ms in back_map:
            target = back_map[ms]
            if target == "exit":
                return STATE_TITLE
            elif target is not None:
                game_state.ui.menu_section = target
        else:
            game_state.ui.menu_confirm_quit = True
        
        return None

    # -------------------------------------------------------------------------
    # Mouse Click Handlers
    # -------------------------------------------------------------------------
    def _handle_mouse_click(self, mouse_pos: tuple[int, int], game_state, cfg, width: int, height: int, out: dict) -> dict | None:
        """Handle mouse clicks for menu navigation."""
        ms = game_state.ui.menu_section
        y = height // 2

        click_handlers = {
            0: lambda: self._click_difficulty(mouse_pos, game_state, cfg, width, height, y),
            1.5: lambda: self._click_use_profile(mouse_pos, game_state, cfg, width, height, y),
            2: lambda: self._click_profile_type(mouse_pos, game_state, cfg, width, height, y),
            3: lambda: self._click_hud(mouse_pos, game_state, cfg, width, height, y),
            3.25: lambda: self._click_fps(mouse_pos, game_state, cfg, width, height, y),
            3.5: lambda: self._click_telemetry(mouse_pos, game_state, cfg, width, height, y),
            5: lambda: self._click_start(mouse_pos, width, height, y, out),
            7: lambda: self._click_class(mouse_pos, game_state, cfg, width, height, y),
        }

        if ms in click_handlers:
            return click_handlers[ms]()
        return None

    def _click_difficulty(self, mouse_pos, game_state, cfg, width, height, y):
        rects = _get_menu_option_rects(width, height, y, len(difficulty_options))
        for i, rect in enumerate(rects):
            if rect.collidepoint(mouse_pos):
                game_state.ui.difficulty_selected = i
                cfg.difficulty = difficulty_options[i]
                game_state.ui.menu_section = 1.5
                break
        return None

    def _click_use_profile(self, mouse_pos, game_state, cfg, width, height, y):
        rects = _get_menu_option_rects(width, height, y, 2)
        for i, rect in enumerate(rects):
            if rect.collidepoint(mouse_pos):
                game_state.ui.use_character_profile_selected = i
                cfg.profile_enabled = i == 1
                game_state.ui.menu_section = 2 if cfg.profile_enabled else 3
                break
        return None

    def _click_profile_type(self, mouse_pos, game_state, cfg, width, height, y):
        rects = _get_menu_option_rects(width, height, y, len(character_profile_options))
        for i, rect in enumerate(rects):
            if rect.collidepoint(mouse_pos):
                game_state.ui.character_profile_selected = i
                if i == 0:
                    game_state.ui.menu_section = 7
                elif i == 1:
                    game_state.ui.custom_profile_stat_selected = 0
                    game_state.ui.menu_section = 6
                else:
                    game_state.ui.saved_profile_selected = 0
                    game_state.ui.menu_section = 8
                break
        return None

    def _click_hud(self, mouse_pos, game_state, cfg, width, height, y):
        rects = _get_menu_option_rects(width, height, y, 2)
        for i, rect in enumerate(rects):
            if rect.collidepoint(mouse_pos):
                game_state.ui.ui_show_metrics_selected = i
                cfg.show_metrics = i == 0
                cfg.show_hud = cfg.show_metrics
                game_state.ui.menu_section = 3.25
                break
        return None

    def _click_fps(self, mouse_pos, game_state, cfg, width, height, y):
        rects = _get_menu_option_rects(width, height, y, 2)
        for i, rect in enumerate(rects):
            if rect.collidepoint(mouse_pos):
                game_state.ui.ui_show_fps_selected = i
                cfg.show_fps = i == 0
                game_state.ui.menu_section = 3.5
                break
        return None

    def _click_telemetry(self, mouse_pos, game_state, cfg, width, height, y):
        rects = _get_menu_option_rects(width, height, y, 2)
        for i, rect in enumerate(rects):
            if rect.collidepoint(mouse_pos):
                game_state.ui.ui_telemetry_enabled_selected = i
                cfg.enable_telemetry = i == 0
                game_state.ui.menu_section = 4 if cfg.testing_mode else 5
                break
        return None

    def _click_class(self, mouse_pos, game_state, cfg, width, height, y):
        rects = _get_menu_option_rects(width, height, y, len(player_class_options))
        for i, rect in enumerate(rects):
            if rect.collidepoint(mouse_pos):
                game_state.ui.player_class_selected = i
                cfg.player_class = player_class_options[i]
                game_state.ui.menu_section = 3
                break
        return None

    def _click_start(self, mouse_pos, width, height, y, out):
        start_rect = pygame.Rect((width - 400) // 2, y - 20, 400, 80)
        if start_rect.collidepoint(mouse_pos):
            out["screen"] = STATE_PLAYING
            out["start_game"] = True
            return out
        return None

    # -------------------------------------------------------------------------
    # Main Input Handler (Dispatcher)
    # -------------------------------------------------------------------------
    def handle_input(self, events, game_state, ctx: dict) -> dict:
        out = {
            "screen": None, "quit": False, "restart": False,
            "restart_to_wave1": False, "replay": False, "pop": False, "start_game": False
        }
        app_ctx = ctx.get("app_ctx")
        if app_ctx is None:
            return out

        cfg = app_ctx.config
        width = ctx.get("width", 1920)
        height = ctx.get("height", 1080)

        # Section -> handler mapping
        section_handlers = {
            0: self._handle_section_0_difficulty,
            1.5: self._handle_section_1_5_use_profile,
            2: self._handle_section_2_profile_type,
            3: self._handle_section_3_hud,
            3.25: self._handle_section_3_25_fps,
            3.5: self._handle_section_3_5_telemetry,
            4: self._handle_section_4_weapon,
            4.5: self._handle_section_4_5_invuln,
            5: self._handle_section_5_ready,
            6: self._handle_section_6_custom_profile,
            7: self._handle_section_7_class,
            8: self._handle_section_8_load_profile,
            9: self._handle_section_9_save_name,
        }

        for event in events:
            # Handle mouse clicks
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if game_state.ui.menu_confirm_quit:
                    game_state.ui.menu_confirm_quit = False
                    continue
                result = self._handle_mouse_click(event.pos, game_state, cfg, width, height, out)
                if result is not None:
                    return result
                continue

            if event.type != pygame.KEYDOWN:
                continue

            # Handle quit confirmation
            if game_state.ui.menu_confirm_quit:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_y):
                    out["quit"] = True
                    return out
                if event.key in (pygame.K_n, pygame.K_ESCAPE):
                    game_state.ui.menu_confirm_quit = False
                continue

            # Handle ESC navigation
            if event.key == pygame.K_ESCAPE:
                result = self._handle_escape_navigation(game_state, cfg)
                if result == STATE_TITLE:
                    out["screen"] = STATE_TITLE
                    game_state.ui.menu_confirm_quit = False
                    return out
                continue

            # Dispatch to section handler
            ms = game_state.ui.menu_section
            if ms in section_handlers:
                result = section_handlers[ms](event, game_state, cfg, out)
                if result is not None:
                    return result

        return out

    def update(self, dt: float, game_state, ctx: dict) -> None:
        pass

    def handle_input_transition(self, events, game_state, ctx: dict) -> SceneTransition:
        """Call existing handle_input logic and process the result."""
        result = self.handle_input(events, game_state, ctx)
        self._last_input_result = result

        if result.get("quit"):
            return SceneTransition.quit_game()
        if result.get("screen") is not None:
            screen = result["screen"]
            if screen == STATE_TITLE:
                return SceneTransition.replace(STATE_TITLE)
            elif screen == STATE_MENU:
                return SceneTransition.replace(STATE_MENU)
        return SceneTransition.none()

    def update_transition(self, dt: float, game_state, ctx: dict) -> SceneTransition:
        self.update(dt, game_state, ctx)
        return SceneTransition.none()

    # -------------------------------------------------------------------------
    # Section Render Methods
    # -------------------------------------------------------------------------
    def _render_quit_confirm(self, screen, font, big_font, w, h):
        draw_centered_text(screen, font, big_font, w, "Are you sure you want to exit?", h // 2 - 40, color=(220, 220, 220))
        draw_centered_text(screen, font, big_font, w, "ENTER or Y to quit", h // 2 + 20, (180, 180, 180))
        draw_centered_text(screen, font, big_font, w, "ESC or N to stay", h // 2 + 60, (180, 180, 180))

    def _render_selection_list(self, screen, font, big_font, w, y, title, options, selected_idx, hint="UP/DOWN: Select | ENTER: Continue | ESC: Back"):
        draw_centered_text(screen, font, big_font, w, title, y - 60)
        for i, opt in enumerate(options):
            c = (255, 255, 0) if i == selected_idx else (200, 200, 200)
            prefix = "->" if i == selected_idx else "  "
            draw_centered_text(screen, font, big_font, w, f"{prefix} {opt}", y + i * 40, c)
        return hint

    def _render_section_0(self, screen, font, big_font, w, h, game_state):
        y = h // 2
        hint = self._render_selection_list(screen, font, big_font, w, y,
            "Options — Select Difficulty:", difficulty_options, game_state.ui.difficulty_selected)
        draw_centered_text(screen, font, big_font, w, hint, h - 100, (150, 150, 150))

    def _render_section_1_5(self, screen, font, big_font, w, h, game_state):
        y = h // 2
        hint = self._render_selection_list(screen, font, big_font, w, y,
            "Use Character Profile?", ["No", "Yes"], game_state.ui.use_character_profile_selected)
        draw_centered_text(screen, font, big_font, w, hint, h - 100, (150, 150, 150))

    def _render_section_2(self, screen, font, big_font, w, h, game_state):
        y = h // 2
        hint = self._render_selection_list(screen, font, big_font, w, y,
            "Character Profile:", character_profile_options, game_state.ui.character_profile_selected)
        draw_centered_text(screen, font, big_font, w, hint, h - 100, (150, 150, 150))

    def _render_section_3(self, screen, font, big_font, w, h, game_state):
        y = h // 2
        hint = self._render_selection_list(screen, font, big_font, w, y,
            "HUD Options:", ["Show Metrics", "Hide Metrics"], game_state.ui.ui_show_metrics_selected)
        draw_centered_text(screen, font, big_font, w, hint, h - 100, (150, 150, 150))

    def _render_section_3_25(self, screen, font, big_font, w, h, game_state):
        y = h // 2
        hint = self._render_selection_list(screen, font, big_font, w, y,
            "FPS Counter:", ["Show FPS Graph", "Hide FPS Graph"], game_state.ui.ui_show_fps_selected)
        draw_centered_text(screen, font, big_font, w, hint, h - 100, (150, 150, 150))

    def _render_section_3_5(self, screen, font, big_font, w, h, game_state):
        y = h // 2
        hint = self._render_selection_list(screen, font, big_font, w, y,
            "Telemetry:", ["Enabled", "Disabled"], game_state.ui.ui_telemetry_enabled_selected)
        draw_centered_text(screen, font, big_font, w, hint, h - 100, (150, 150, 150))

    def _render_section_4(self, screen, font, big_font, w, h, game_state, cfg):
        if not cfg.testing_mode:
            return
        y = h // 2
        draw_centered_text(screen, font, big_font, w, "Select Weapon:", y - 60)
        for i, wep in enumerate(weapon_selection_options):
            c = (255, 255, 0) if i == game_state.ui.beam_selection_selected else (200, 200, 200)
            prefix = "->" if i == game_state.ui.beam_selection_selected else "  "
            draw_centered_text(screen, font, big_font, w, f"{prefix} {wep}", y + i * 30, c)
        draw_centered_text(screen, font, big_font, w, "UP/DOWN: Select | ENTER: Continue | ESC: Back", h - 100, (150, 150, 150))

    def _render_section_4_5(self, screen, font, big_font, w, h, cfg):
        y = h // 2
        draw_centered_text(screen, font, big_font, w, "Testing Options:", y - 60)
        ic = (255, 255, 0) if cfg.invulnerability_mode else (200, 200, 200)
        prefix = "->" if cfg.invulnerability_mode else "  "
        draw_centered_text(screen, font, big_font, w, f"{prefix} Invulnerability: {'ON' if cfg.invulnerability_mode else 'OFF'}", y, ic)
        draw_centered_text(screen, font, big_font, w, "UP/DOWN: Toggle | ENTER: Start | ESC: Back", h - 100, (150, 150, 150))

    def _render_section_5(self, screen, font, big_font, w, h):
        y = h // 2
        draw_centered_text(screen, font, big_font, w, "Ready to Start!", y)
        draw_centered_text(screen, font, big_font, w, "Press ENTER or SPACE to begin", y + 60, (150, 150, 150))
        draw_centered_text(screen, font, big_font, w, "Press ESC to go back", y + 100, (150, 150, 150))

    def _render_section_6(self, screen, font, big_font, w, h, game_state):
        y = h // 2
        draw_centered_text(screen, font, big_font, w, "Custom Profile Creator:", y - 100)
        num_stats = len(custom_profile_stats_list)

        for i, name in enumerate(custom_profile_stats_list):
            k = custom_profile_stats_keys[i]
            v = game_state.custom_profile_stats[k]
            selected = i == game_state.ui.custom_profile_stat_selected
            c = (255, 255, 0) if selected else (200, 200, 200)
            prefix = "->" if selected else "  "
            draw_centered_text(screen, font, big_font, w, f"{prefix} {name}: {v:.1f}x", y - 40 + i * 35, c)

        action_y = y - 40 + num_stats * 35 + 20
        actions = [("[Done - Continue]", num_stats), ("[Save Profile]", num_stats + 1), ("[Back]", num_stats + 2)]
        colors = [(200, 200, 200), (100, 200, 100), (200, 200, 200)]

        for idx, (label, action_idx) in enumerate(actions):
            selected = game_state.ui.custom_profile_stat_selected == action_idx
            c = (255, 255, 0) if selected else colors[idx]
            prefix = "->" if selected else "  "
            draw_centered_text(screen, font, big_font, w, f"{prefix} {label}", action_y + idx * 30, c)

        draw_centered_text(screen, font, big_font, w, "UP/DOWN: Select | LEFT/RIGHT: Adjust | ENTER: Confirm | ESC: Back", h - 100, (150, 150, 150))

    def _render_section_7(self, screen, font, big_font, w, h, game_state):
        y = h // 2
        hint = self._render_selection_list(screen, font, big_font, w, y,
            "Select Class:", player_class_options, game_state.ui.player_class_selected)
        draw_centered_text(screen, font, big_font, w, hint, h - 100, (150, 150, 150))

    def _render_section_8(self, screen, font, big_font, w, h, game_state):
        y = h // 2
        draw_centered_text(screen, font, big_font, w, "Saved Profiles:", y - 120)
        profiles = load_profiles()
        num_profiles = len(profiles)

        if num_profiles == 0:
            draw_centered_text(screen, font, big_font, w, "(No saved profiles)", y - 60, (150, 150, 150))
        else:
            start_idx = max(0, game_state.ui.saved_profile_selected - 3)
            visible_profiles = profiles[start_idx:start_idx + 6]
            for i, profile in enumerate(visible_profiles):
                actual_idx = start_idx + i
                selected = actual_idx == game_state.ui.saved_profile_selected
                c = (255, 255, 0) if selected else (200, 200, 200)
                prefix = "->" if selected else "  "
                display = get_profile_display_text(profile)
                draw_centered_text(screen, font, big_font, w, f"{prefix} {display}", y - 60 + i * 30, c)

        action_y = y + 100
        create_selected = game_state.ui.saved_profile_selected == num_profiles
        back_selected = game_state.ui.saved_profile_selected == num_profiles + 1

        create_color = (255, 255, 0) if create_selected else (100, 200, 100)
        create_prefix = "->" if create_selected else "  "
        draw_centered_text(screen, font, big_font, w, f"{create_prefix} [Create New Profile]", action_y, create_color)

        back_color = (255, 255, 0) if back_selected else (200, 200, 200)
        back_prefix = "->" if back_selected else "  "
        draw_centered_text(screen, font, big_font, w, f"{back_prefix} [Back]", action_y + 35, back_color)

        draw_centered_text(screen, font, big_font, w, "UP/DOWN: Select | ENTER: Load/Action | DEL: Delete | ESC: Back", h - 100, (150, 150, 150))

    def _render_section_9(self, screen, font, big_font, w, h, game_state):
        y = h // 2
        draw_centered_text(screen, font, big_font, w, "Save Profile", y - 60)
        draw_centered_text(screen, font, big_font, w, "Enter a name for your profile:", y)

        input_text = game_state.ui.profile_name_input + ("_" if game_state.ui.profile_name_active else "")
        draw_centered_text(screen, font, big_font, w, f"[ {input_text} ]", y + 50, (255, 255, 255))

        stats = game_state.custom_profile_stats
        stats_text = f"HP:{stats['hp_mult']:.1f}x Spd:{stats['speed_mult']:.1f}x Dmg:{stats['damage_mult']:.1f}x FR:{stats['firerate_mult']:.1f}x"
        draw_centered_text(screen, font, big_font, w, stats_text, y + 100, (150, 150, 150))

        draw_centered_text(screen, font, big_font, w, "Type name and press ENTER to save | ESC: Cancel", h - 100, (150, 150, 150))

    # -------------------------------------------------------------------------
    # Main Render (Dispatcher)
    # -------------------------------------------------------------------------
    def render(self, render_ctx: RenderContext, game_state, ctx: dict) -> None:
        app_ctx = ctx.get("app_ctx")
        if app_ctx is None:
            return

        screen = render_ctx.screen
        w, h = render_ctx.width, render_ctx.height
        font, big_font = render_ctx.font, render_ctx.big_font
        cfg = app_ctx.config
        ms = game_state.ui.menu_section

        if game_state.ui.menu_confirm_quit:
            self._render_quit_confirm(screen, font, big_font, w, h)
            return

        draw_centered_text(screen, font, big_font, w, "MOUSE AIM SHOOTER", h // 4, use_big=True)

        render_handlers = {
            0: lambda: self._render_section_0(screen, font, big_font, w, h, game_state),
            1.5: lambda: self._render_section_1_5(screen, font, big_font, w, h, game_state),
            2: lambda: self._render_section_2(screen, font, big_font, w, h, game_state),
            3: lambda: self._render_section_3(screen, font, big_font, w, h, game_state),
            3.25: lambda: self._render_section_3_25(screen, font, big_font, w, h, game_state),
            3.5: lambda: self._render_section_3_5(screen, font, big_font, w, h, game_state),
            4: lambda: self._render_section_4(screen, font, big_font, w, h, game_state, cfg),
            4.5: lambda: self._render_section_4_5(screen, font, big_font, w, h, cfg),
            5: lambda: self._render_section_5(screen, font, big_font, w, h),
            6: lambda: self._render_section_6(screen, font, big_font, w, h, game_state),
            7: lambda: self._render_section_7(screen, font, big_font, w, h, game_state),
            8: lambda: self._render_section_8(screen, font, big_font, w, h, game_state),
            9: lambda: self._render_section_9(screen, font, big_font, w, h, game_state),
        }

        if ms in render_handlers:
            render_handlers[ms]()

    def on_enter(self, game_state, ctx: dict) -> None:
        pass

    def on_exit(self, game_state, ctx: dict) -> None:
        pass
