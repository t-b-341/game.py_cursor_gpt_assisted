"""OptionsScene: pre-game menu (difficulty, profile, class, HUD, telemetry, weapon, start)."""
from __future__ import annotations

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


class OptionsScene:
    """Options / main menu. All menu_section navigation and start-game intent via return value."""

    def state_id(self) -> str:
        return STATE_MENU

    def handle_input(self, events, game_state, ctx: dict) -> dict:
        out = {"screen": None, "quit": False, "restart": False, "restart_to_wave1": False, "replay": False, "pop": False, "start_game": False}
        app_ctx = ctx.get("app_ctx")
        if app_ctx is None:
            return out
        cfg = app_ctx.config
        # Always use game_state.ui.menu_section directly, not a local copy
        # This ensures changes to menu_section are immediately reflected in the same event processing loop

        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if game_state.ui.menu_confirm_quit:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_y):
                    out["quit"] = True
                    return out
                if event.key == pygame.K_n:
                    game_state.ui.menu_confirm_quit = False
                continue
            if event.key == pygame.K_ESCAPE:
                game_state.ui.menu_confirm_quit = True
                continue

            if game_state.ui.menu_section == 0:
                if event.key in (pygame.K_UP, pygame.K_w):
                    game_state.ui.difficulty_selected = (game_state.ui.difficulty_selected - 1) % len(difficulty_options)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    game_state.ui.difficulty_selected = (game_state.ui.difficulty_selected + 1) % len(difficulty_options)
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    out["screen"] = STATE_TITLE
                    game_state.ui.menu_confirm_quit = False
                    return out
                elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    cfg.difficulty = difficulty_options[game_state.ui.difficulty_selected]
                    game_state.ui.menu_section = 1.5
            elif game_state.ui.menu_section == 1.5:
                if event.key in (pygame.K_UP, pygame.K_w):
                    game_state.ui.use_character_profile_selected = (game_state.ui.use_character_profile_selected - 1) % 2
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    game_state.ui.use_character_profile_selected = (game_state.ui.use_character_profile_selected + 1) % 2
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    game_state.ui.menu_section = 0
                elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    cfg.profile_enabled = game_state.ui.use_character_profile_selected == 1
                    game_state.ui.menu_section = 2 if cfg.profile_enabled else 3
            elif game_state.ui.menu_section == 2:
                if event.key in (pygame.K_UP, pygame.K_w):
                    game_state.ui.character_profile_selected = (game_state.ui.character_profile_selected - 1) % len(character_profile_options)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    game_state.ui.character_profile_selected = (game_state.ui.character_profile_selected + 1) % len(character_profile_options)
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    game_state.ui.menu_section = 1.5
                elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    game_state.ui.menu_section = 7 if game_state.ui.character_profile_selected == 0 else 6
            elif game_state.ui.menu_section == 6:
                if event.key in (pygame.K_UP, pygame.K_w):
                    game_state.ui.custom_profile_stat_selected = (game_state.ui.custom_profile_stat_selected - 1) % len(custom_profile_stats_list)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    game_state.ui.custom_profile_stat_selected = (game_state.ui.custom_profile_stat_selected + 1) % len(custom_profile_stats_list)
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    sk = custom_profile_stats_keys[game_state.ui.custom_profile_stat_selected]
                    game_state.custom_profile_stats[sk] = max(0.5, game_state.custom_profile_stats[sk] - 0.1)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    game_state.ui.menu_section = 3
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                    sk = custom_profile_stats_keys[game_state.ui.custom_profile_stat_selected]
                    game_state.custom_profile_stats[sk] = min(3.0, game_state.custom_profile_stats[sk] + 0.1)
                elif event.key == pygame.K_MINUS:
                    sk = custom_profile_stats_keys[game_state.ui.custom_profile_stat_selected]
                    game_state.custom_profile_stats[sk] = max(0.5, game_state.custom_profile_stats[sk] - 0.1)
            elif game_state.ui.menu_section == 7:
                if event.key in (pygame.K_UP, pygame.K_w):
                    game_state.ui.player_class_selected = (game_state.ui.player_class_selected - 1) % len(player_class_options)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    game_state.ui.player_class_selected = (game_state.ui.player_class_selected + 1) % len(player_class_options)
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    game_state.ui.menu_section = 2
                elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    cfg.player_class = player_class_options[game_state.ui.player_class_selected]
                    game_state.ui.menu_section = 3
            elif game_state.ui.menu_section == 3:
                if event.key in (pygame.K_UP, pygame.K_w):
                    game_state.ui.ui_show_metrics_selected = (game_state.ui.ui_show_metrics_selected - 1) % 2
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    game_state.ui.ui_show_metrics_selected = (game_state.ui.ui_show_metrics_selected + 1) % 2
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    game_state.ui.menu_section = 7 if game_state.ui.character_profile_selected == 0 else 6 if cfg.profile_enabled else 1.5
                elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    cfg.show_metrics = game_state.ui.ui_show_metrics_selected == 0
                    cfg.show_hud = cfg.show_metrics
                    game_state.ui.menu_section = 3.5
            elif game_state.ui.menu_section == 3.5:
                if event.key in (pygame.K_UP, pygame.K_w):
                    game_state.ui.ui_telemetry_enabled_selected = (game_state.ui.ui_telemetry_enabled_selected - 1) % 2
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    game_state.ui.ui_telemetry_enabled_selected = (game_state.ui.ui_telemetry_enabled_selected + 1) % 2
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    game_state.ui.menu_section = 3
                elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    cfg.enable_telemetry = game_state.ui.ui_telemetry_enabled_selected == 0
                    game_state.ui.menu_section = 4 if cfg.testing_mode else 5
            elif game_state.ui.menu_section == 4:
                if event.key in (pygame.K_UP, pygame.K_w):
                    game_state.ui.beam_selection_selected = (game_state.ui.beam_selection_selected - 1) % len(weapon_selection_options)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    game_state.ui.beam_selection_selected = (game_state.ui.beam_selection_selected + 1) % len(weapon_selection_options)
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    game_state.ui.menu_section = 3.5
                elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    sel = weapon_selection_options[game_state.ui.beam_selection_selected]
                    game_state.unlocked_weapons.add(sel)
                    if game_state.current_weapon_mode == "laser" and sel != "laser":
                        game_state.laser_beams.clear()
                    game_state.current_weapon_mode = sel
                    game_state.beam_selection_pattern = sel
                    game_state.ui.menu_section = 4.5 if cfg.testing_mode else 5
            elif game_state.ui.menu_section == 4.5:
                if event.key in (pygame.K_UP, pygame.K_w):
                    cfg.invulnerability_mode = not cfg.invulnerability_mode
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    cfg.invulnerability_mode = not cfg.invulnerability_mode
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    game_state.ui.menu_section = 4
                elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    game_state.ui.menu_section = 5
            elif game_state.ui.menu_section == 5:
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    game_state.ui.menu_section = 3.5
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    out["screen"] = STATE_PLAYING
                    out["start_game"] = True
                    return out
        return out

    def update(self, dt: float, game_state, ctx: dict) -> None:
        pass

    def handle_input_transition(self, events, game_state, ctx: dict) -> SceneTransition:
        """Call existing handle_input logic and process the result. Return transition if needed."""
        result = self.handle_input(events, game_state, ctx)
        # Store result for retrieval by game.py (avoids calling handle_input twice)
        self._last_input_result = result
        # Process result to handle screen changes, quit, etc.
        # Note: Config changes (enable_menu_shaders, menu_shader_profile, etc.) are applied
        # directly in handle_input via cfg.enable_menu_shaders = ..., so they persist.
        if result.get("quit"):
            return SceneTransition.quit_game()
        if result.get("screen") is not None:
            # Map screen changes to transitions
            screen = result["screen"]
            if screen == STATE_TITLE:
                return SceneTransition.replace(STATE_TITLE)
            elif screen == STATE_MENU:
                return SceneTransition.replace(STATE_MENU)
            elif screen == STATE_PLAYING:
                # Start game - handled separately via start_game flag in result
                # Return NONE so the old path can handle start_game
                pass
        # Return NONE - config changes were already applied in handle_input
        return SceneTransition.none()

    def update_transition(self, dt: float, game_state, ctx: dict) -> SceneTransition:
        """Stub: call existing logic; return NONE. Used by future scene-driven loop."""
        self.update(dt, game_state, ctx)
        return SceneTransition.none()

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
            draw_centered_text(screen, font, big_font, w, "Are you sure you want to exit?", h // 2 - 40, color=(220, 220, 220))
            draw_centered_text(screen, font, big_font, w, "ENTER or Y to quit", h // 2 + 20, (180, 180, 180))
            draw_centered_text(screen, font, big_font, w, "ESC or N to stay", h // 2 + 60, (180, 180, 180))
            return
        draw_centered_text(screen, font, big_font, w, "MOUSE AIM SHOOTER", h // 4, use_big=True)
        y = h // 2
        if ms == 0:
            draw_centered_text(screen, font, big_font, w, "Options — Select Difficulty:", y - 60)
            for i, d in enumerate(difficulty_options):
                c = (255, 255, 0) if i == game_state.ui.difficulty_selected else (200, 200, 200)
                draw_centered_text(screen, font, big_font, w, f"{'->' if i == game_state.ui.difficulty_selected else '  '} {d}", y + i * 40, c)
            draw_centered_text(screen, font, big_font, w, "UP/DOWN to select, RIGHT/ENTER to continue, LEFT to return to main menu", h - 100, (150, 150, 150))
        elif ms == 1.5:
            draw_centered_text(screen, font, big_font, w, "Use Character Profile?", y - 60)
            for i, opt in enumerate(["No", "Yes"]):
                c = (255, 255, 0) if i == game_state.ui.use_character_profile_selected else (200, 200, 200)
                draw_centered_text(screen, font, big_font, w, f"{'->' if i == game_state.ui.use_character_profile_selected else '  '} {opt}", y + i * 40, c)
            draw_centered_text(screen, font, big_font, w, "Use UP/DOWN to select, LEFT to go back, RIGHT/ENTER to continue", h - 100, (150, 150, 150))
        elif ms == 2:
            draw_centered_text(screen, font, big_font, w, "Character Profile:", y - 60)
            for i, p in enumerate(character_profile_options):
                c = (255, 255, 0) if i == game_state.ui.character_profile_selected else (200, 200, 200)
                draw_centered_text(screen, font, big_font, w, f"{'->' if i == game_state.ui.character_profile_selected else '  '} {p}", y + i * 40, c)
            draw_centered_text(screen, font, big_font, w, "Use UP/DOWN to select, LEFT to go back, RIGHT/ENTER to continue", h - 100, (150, 150, 150))
        elif ms == 3:
            draw_centered_text(screen, font, big_font, w, "HUD Options:", y - 60)
            for i, opt in enumerate(["Show Metrics", "Hide Metrics"]):
                c = (255, 255, 0) if i == game_state.ui.ui_show_metrics_selected else (200, 200, 200)
                draw_centered_text(screen, font, big_font, w, f"{'->' if i == game_state.ui.ui_show_metrics_selected else '  '} {opt}", y + i * 40, c)
            draw_centered_text(screen, font, big_font, w, "Use UP/DOWN to select, LEFT to go back, RIGHT/ENTER to continue", h - 100, (150, 150, 150))
        elif ms == 3.5:
            draw_centered_text(screen, font, big_font, w, "Telemetry:", y - 60)
            for i, opt in enumerate(["Enabled", "Disabled"]):
                c = (255, 255, 0) if i == game_state.ui.ui_telemetry_enabled_selected else (200, 200, 200)
                draw_centered_text(screen, font, big_font, w, f"{'->' if i == game_state.ui.ui_telemetry_enabled_selected else '  '} {opt}", y + i * 40, c)
            draw_centered_text(screen, font, big_font, w, "Use UP/DOWN to select, LEFT to go back, RIGHT/ENTER to continue", h - 100, (150, 150, 150))
        elif ms == 4:
            if cfg.testing_mode:
                draw_centered_text(screen, font, big_font, w, "Select Weapon:", y - 60)
                for i, wep in enumerate(weapon_selection_options):
                    c = (255, 255, 0) if i == game_state.ui.beam_selection_selected else (200, 200, 200)
                    draw_centered_text(screen, font, big_font, w, f"{'->' if i == game_state.ui.beam_selection_selected else '  '} {wep}", y + i * 30, c)
                draw_centered_text(screen, font, big_font, w, "Use UP/DOWN to select, LEFT to go back, RIGHT/ENTER to continue", h - 100, (150, 150, 150))
        elif ms == 4.5:
            draw_centered_text(screen, font, big_font, w, "Testing Options:", y - 60)
            ic = (255, 255, 0) if cfg.invulnerability_mode else (200, 200, 200)
            draw_centered_text(screen, font, big_font, w, f"{'->' if cfg.invulnerability_mode else '  '} Invulnerability: {'ON' if cfg.invulnerability_mode else 'OFF'}", y, ic)
            draw_centered_text(screen, font, big_font, w, "Use UP/DOWN to toggle, LEFT to go back, RIGHT/ENTER to start", h - 100, (150, 150, 150))
        elif ms == 5:
            draw_centered_text(screen, font, big_font, w, "Ready to Start!", y)
            draw_centered_text(screen, font, big_font, w, "Press ENTER or SPACE to begin", y + 60, (150, 150, 150))
            draw_centered_text(screen, font, big_font, w, "Press LEFT to go back", y + 100, (150, 150, 150))
        elif ms == 6:
            draw_centered_text(screen, font, big_font, w, "Custom Profile Creator:", y - 100)
            for i, name in enumerate(custom_profile_stats_list):
                k = custom_profile_stats_keys[i]
                v = game_state.custom_profile_stats[k]
                c = (255, 255, 0) if i == game_state.ui.custom_profile_stat_selected else (200, 200, 200)
                draw_centered_text(screen, font, big_font, w, f"{'->' if i == game_state.ui.custom_profile_stat_selected else '  '} {name}: {v:.1f}x", y + i * 35, c)
            draw_centered_text(screen, font, big_font, w, "Use UP/DOWN to select stat, LEFT/RIGHT to adjust, ENTER to continue", h - 100, (150, 150, 150))
        elif ms == 7:
            draw_centered_text(screen, font, big_font, w, "Select Class:", y - 60)
            for i, cls in enumerate(player_class_options):
                c = (255, 255, 0) if i == game_state.ui.player_class_selected else (200, 200, 200)
                draw_centered_text(screen, font, big_font, w, f"{'->' if i == game_state.ui.player_class_selected else '  '} {cls}", y + i * 40, c)
            draw_centered_text(screen, font, big_font, w, "Use UP/DOWN to select, LEFT to go back, RIGHT/ENTER to continue", h - 100, (150, 150, 150))

    def on_enter(self, game_state, ctx: dict) -> None:
        pass

    def on_exit(self, game_state, ctx: dict) -> None:
        pass
