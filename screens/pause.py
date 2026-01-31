"""Pause screen: handle_events and render. Uses RenderContext for display/fonts.

Refactored to use separate handlers for each submenu.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
from constants import STATE_PLAYING, STATE_ENDURANCE, STATE_MENU, STATE_SAVE_GAME, STATE_TELEMETRY_VIEWER, STATE_MAP_TEST, pause_options, fps_cap_options
from rendering import RenderContext, draw_centered_text
from systems.audio_system import (
    get_sfx_volume, get_music_volume, set_sfx_volume, set_music_volume,
    is_muted_sfx, is_muted_music, set_muted, play_sfx
)
from systems.idle_enemy_animation import (
    update_idle_enemies,
    render_idle_enemies,
    reset_idle_enemies,
)

if TYPE_CHECKING:
    from state import GameState


# -----------------------------------------------------------------------------
# Navigation key constants (shared with options.py pattern)
# -----------------------------------------------------------------------------
_NAV_UP = (pygame.K_UP, pygame.K_w)
_NAV_DOWN = (pygame.K_DOWN, pygame.K_s)
_NAV_LEFT = (pygame.K_LEFT, pygame.K_a)
_NAV_RIGHT = (pygame.K_RIGHT, pygame.K_d)
_NAV_CONFIRM = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)


# Cached overlay surface to avoid per-frame allocation
_overlay_cache: pygame.Surface | None = None
_overlay_size: tuple[int, int] = (0, 0)


# ============================================================================
# Submenu Handlers
# ============================================================================

def _handle_audio_submenu(event: pygame.event.Event, game_state: "GameState", cfg) -> dict | None:
    """Handle input for the audio options submenu."""
    if not hasattr(game_state.ui, 'pause_audio_options_row'):
        game_state.ui.pause_audio_options_row = 0
    row = game_state.ui.pause_audio_options_row

    if event.key == pygame.K_ESCAPE:
        game_state.ui.pause_submenu = None
        return {"handled": True}
    elif event.key in _NAV_UP:
        game_state.ui.pause_audio_options_row = (row - 1) % 4
    elif event.key in _NAV_DOWN:
        game_state.ui.pause_audio_options_row = (row + 1) % 4
    elif event.key in _NAV_LEFT:
        _adjust_audio_setting(row, -0.1, cfg)
    elif event.key in _NAV_RIGHT:
        _adjust_audio_setting(row, 0.1, cfg)
        if row == 0:  # Play test sound when increasing SFX
            play_sfx("BASIC SHOT")
    return None


def _adjust_audio_setting(row: int, delta: float, cfg) -> None:
    """Adjust audio setting based on row index."""
    if row == 0:  # SFX Volume
        new_vol = max(0.0, min(1.0, get_sfx_volume() + delta))
        set_sfx_volume(new_vol)
        if cfg:
            cfg.sfx_volume = new_vol
    elif row == 1:  # Music Volume
        new_vol = max(0.0, min(1.0, get_music_volume() + delta))
        set_music_volume(new_vol)
        if cfg:
            cfg.music_volume = new_vol
    elif row == 2:  # Mute SFX
        set_muted(sfx=not is_muted_sfx())
        if cfg:
            cfg.mute_sfx = is_muted_sfx()
    elif row == 3:  # Mute Music
        set_muted(music=not is_muted_music())
        if cfg:
            cfg.mute_music = is_muted_music()


def _handle_shader_submenu(event: pygame.event.Event, game_state: "GameState", cfg, out: dict) -> dict | None:
    """Handle input for the shader/settings submenu."""
    if not hasattr(game_state.ui, 'pause_shader_options_row'):
        game_state.ui.pause_shader_options_row = 0
    row = game_state.ui.pause_shader_options_row

    _pp = ["none", "pause_dim_vignette"]
    _gp = ["none", "gameplay_subtle_vignette", "gameplay_retro"]
    _ts = [0.5, 0.75, 1.0, 1.25, 1.5]  # Timescale options

    if event.key == pygame.K_ESCAPE:
        game_state.ui.pause_submenu = None
        return {"handled": True}
    elif event.key in _NAV_UP:
        game_state.ui.pause_shader_options_row = (row - 1) % 6
    elif event.key in _NAV_DOWN:
        game_state.ui.pause_shader_options_row = (row + 1) % 6
    elif event.key in _NAV_LEFT and cfg is not None:
        _adjust_shader_setting(row, -1, cfg, _gp, _pp, _ts)
    elif event.key in _NAV_RIGHT and cfg is not None:
        _adjust_shader_setting(row, 1, cfg, _gp, _pp, _ts)
    elif event.key in _NAV_CONFIRM:
        row = game_state.ui.pause_shader_options_row
        if row == 5:  # "Full Settings" option
            out["screen"] = "SHADER_SETTINGS"
            return out
    return None


def _adjust_shader_setting(row: int, direction: int, cfg, gameplay_profiles: list, pause_profiles: list, timescales: list = None) -> None:
    """Adjust shader/game setting based on row index and direction."""
    if timescales is None:
        timescales = [0.5, 0.75, 1.0, 1.25, 1.5]
    
    if row == 0:
        cfg.enable_gameplay_shaders = not cfg.enable_gameplay_shaders
    elif row == 1:
        cfg.enable_pause_shaders = not cfg.enable_pause_shaders
    elif row == 2:
        cur = getattr(cfg, "gameplay_shader_profile", "none")
        i = (gameplay_profiles.index(cur) if cur in gameplay_profiles else 0) + direction
        cfg.gameplay_shader_profile = gameplay_profiles[i % len(gameplay_profiles)]
    elif row == 3:
        cur = getattr(cfg, "pause_shader_profile", "none")
        i = (pause_profiles.index(cur) if cur in pause_profiles else 0) + direction
        cfg.pause_shader_profile = pause_profiles[i % len(pause_profiles)]
    elif row == 4:
        # Game Speed (timescale)
        cur = getattr(cfg, "timescale", 1.0)
        # Find closest matching timescale
        try:
            i = timescales.index(cur)
        except ValueError:
            i = timescales.index(1.0) if 1.0 in timescales else 0
        cfg.timescale = timescales[(i + direction) % len(timescales)]


def _handle_main_menu(event: pygame.event.Event, game_state: "GameState", cfg, out: dict) -> dict | None:
    """Handle input for the main pause menu."""
    if event.key == pygame.K_ESCAPE:
        return _get_resume_target(game_state, out)

    if event.key in _NAV_UP:
        current = game_state.ui.pause_selected
        game_state.ui.pause_selected = (current - 1) % len(pause_options)
    elif event.key in _NAV_DOWN:
        current = game_state.ui.pause_selected
        game_state.ui.pause_selected = (current + 1) % len(pause_options)
    elif event.key in _NAV_CONFIRM:
        return _handle_menu_selection(game_state, cfg, out)
    return None


def _get_resume_target(game_state: "GameState", out: dict) -> dict:
    """Get the target screen when resuming from pause."""
    target = game_state.previous_screen or STATE_PLAYING
    if target not in (STATE_PLAYING, STATE_ENDURANCE):
        target = STATE_PLAYING
    out["screen"] = target
    return out


def _handle_menu_selection(game_state: "GameState", cfg, out: dict) -> dict | None:
    """Handle selection of a pause menu option."""
    choice = pause_options[game_state.ui.pause_selected]

    if choice == "Continue":
        return _get_resume_target(game_state, out)
    elif choice == "Restart (Wave 1)":
        out["restart_to_wave1"] = True
        out["screen"] = STATE_PLAYING
        return out
    elif choice == "Test Map":
        out["screen"] = STATE_MAP_TEST
        return out
    elif choice == "Audio options":
        game_state.ui.pause_submenu = "audio"
        game_state.ui.pause_audio_options_row = 0
    elif choice == "Shader options":
        game_state.ui.pause_submenu = "shaders"
        game_state.ui.pause_shader_options_row = 0
    elif choice == "Telemetry Graphs":
        out["screen"] = STATE_TELEMETRY_VIEWER
        return out
    elif choice == "Toggle FPS":
        if cfg is not None:
            cfg.show_fps = not cfg.show_fps
    elif choice == "FPS Cap":
        if cfg is not None:
            current_fps = getattr(cfg, 'target_fps', 144)
            try:
                current_idx = fps_cap_options.index(current_fps)
            except ValueError:
                current_idx = 0
            cfg.target_fps = fps_cap_options[(current_idx + 1) % len(fps_cap_options)]
    elif choice == "Perf Overlay":
        if cfg is not None:
            cfg.show_perf_overlay = not getattr(cfg, 'show_perf_overlay', False)
    elif choice == "Save & Quit":
        game_state.ui.save_and_quit = True
        out["screen"] = STATE_SAVE_GAME
        out["save_and_quit"] = True
        return out
    elif choice == "Exit to main menu":
        out["screen"] = STATE_MENU
        return out
    elif choice == "Quit":
        out["quit"] = True
        return out
    return None


# ============================================================================
# Mouse Click Support
# ============================================================================

def _get_option_rects(width: int, height: int, y_start: int, num_options: int, line_height: int = 40, option_width: int = 400) -> list[pygame.Rect]:
    """Calculate clickable rectangles for menu options."""
    rects = []
    x = (width - option_width) // 2
    for i in range(num_options):
        y = y_start + i * line_height - 15  # Offset up a bit for centering
        rects.append(pygame.Rect(x, y, option_width, line_height))
    return rects


def _handle_main_menu_click(mouse_pos: tuple[int, int], game_state, cfg, width: int, height: int, out: dict) -> dict | None:
    """Handle mouse click on main pause menu."""
    y_offset = height // 2 - 60
    rects = _get_option_rects(width, height, y_offset, len(pause_options), line_height=40)
    
    for i, rect in enumerate(rects):
        if rect.collidepoint(mouse_pos):
            game_state.ui.pause_selected = i
            # Trigger selection
            return _handle_menu_selection(game_state, cfg, out)
    return None


def _handle_audio_submenu_click(mouse_pos: tuple[int, int], game_state, cfg, width: int, height: int) -> dict | None:
    """Handle mouse click on audio submenu."""
    y_start = height // 2 - 80
    rects = _get_option_rects(width, height, y_start, 4, line_height=35, option_width=350)
    
    for i, rect in enumerate(rects):
        if rect.collidepoint(mouse_pos):
            game_state.ui.pause_audio_options_row = i
            return {"handled": True}
    return None


def _handle_shader_submenu_click(mouse_pos: tuple[int, int], game_state, cfg, width: int, height: int, out: dict) -> dict | None:
    """Handle mouse click on shader/settings submenu."""
    y_start = height // 2 - 100
    rects = _get_option_rects(width, height, y_start, 6, line_height=32, option_width=400)
    
    for i, rect in enumerate(rects):
        if rect.collidepoint(mouse_pos):
            game_state.ui.pause_shader_options_row = i
            # If clicking "Open Full Settings" (row 5), open it
            if i == 5:
                out["screen"] = "SHADER_SETTINGS"
                return out
            return {"handled": True}
    return None


# ============================================================================
# Main Event Handler (Dispatcher)
# ============================================================================

def handle_events(events, game_state, ctx) -> dict:
    """
    Process pause-screen events. Mutates game_state.ui.pause_selected.
    Returns dict: {"screen": str|None, "quit": bool, "restart": bool, "restart_to_wave1": bool}.
    Supports both keyboard navigation and mouse clicks.
    """
    out = {"screen": None, "quit": False, "restart": False, "restart_to_wave1": False}
    app_ctx = ctx.get("app_ctx") if isinstance(ctx, dict) else None
    cfg = getattr(app_ctx, "config", None) if app_ctx else None
    
    # Get screen dimensions for mouse hit testing
    width = ctx.get("width", 1920) if isinstance(ctx, dict) else 1920
    height = ctx.get("height", 1080) if isinstance(ctx, dict) else 1080

    if game_state is None:
        return out

    submenu = game_state.ui.pause_submenu

    for event in events:
        if not hasattr(event, "type"):
            continue
        
        # Handle mouse clicks
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if submenu == "audio":
                result = _handle_audio_submenu_click(event.pos, game_state, cfg, width, height)
                if result and result.get("handled"):
                    continue
            elif submenu == "shaders":
                result = _handle_shader_submenu_click(event.pos, game_state, cfg, width, height, out)
                if result is not None:
                    if result.get("screen"):
                        return result
                    if result.get("handled"):
                        continue
            else:
                result = _handle_main_menu_click(event.pos, game_state, cfg, width, height, out)
                if result is not None:
                    return result
            continue
        
        # Handle keyboard input
        if event.type != pygame.KEYDOWN:
            continue

        # Dispatch to submenu handler or main menu
        if submenu == "audio":
            result = _handle_audio_submenu(event, game_state, cfg)
            if result and result.get("handled"):
                break
        elif submenu == "shaders":
            result = _handle_shader_submenu(event, game_state, cfg, out)
            if result is not None:
                if result.get("screen"):
                    return result
                if result.get("handled"):
                    break
        else:
            result = _handle_main_menu(event, game_state, cfg, out)
            if result is not None:
                return result

    return out


# ============================================================================
# Render Functions
# ============================================================================

def _render_audio_submenu(screen, font, big_font, WIDTH, HEIGHT, game_state) -> None:
    """Render the audio options submenu."""
    row = getattr(game_state.ui, 'pause_audio_options_row', 0)
    row = max(0, min(3, row))

    sfx_vol = int(get_sfx_volume() * 100)
    music_vol = int(get_music_volume() * 100)
    sfx_muted = is_muted_sfx()
    music_muted = is_muted_music()

    lines = [
        f"SFX Volume: {sfx_vol}%",
        f"Music Volume: {music_vol}%",
        f"Mute SFX: {'Yes' if sfx_muted else 'No'}",
        f"Mute Music: {'Yes' if music_muted else 'No'}",
    ]

    draw_centered_text(screen, font, big_font, WIDTH, "Audio Options", HEIGHT // 2 - 140, use_big=True)
    for i, line in enumerate(lines):
        color = (255, 255, 0) if i == row else (200, 200, 200)
        prefix = "->" if i == row else "  "
        draw_centered_text(screen, font, big_font, WIDTH, f"{prefix} {line}", HEIGHT // 2 - 80 + i * 40, color)
    draw_centered_text(screen, font, big_font, WIDTH, "UP/DOWN: Select | LEFT/RIGHT: Adjust | ESC: Back", HEIGHT - 80, (150, 150, 150))


def _render_shader_submenu(screen, font, big_font, WIDTH, HEIGHT, game_state, cfg) -> None:
    """Render the shader/settings submenu."""
    row = getattr(game_state.ui, 'pause_shader_options_row', 0)
    row = max(0, min(5, row))

    if cfg is not None:
        timescale = getattr(cfg, 'timescale', 1.0)
        speed_text = f"{int(timescale * 100)}%" if timescale != 1.0 else "Normal"
        lines = [
            f"Gameplay Shaders: {'On' if getattr(cfg, 'enable_gameplay_shaders', False) else 'Off'}",
            f"Pause Shaders: {'On' if getattr(cfg, 'enable_pause_shaders', False) else 'Off'}",
            f"Gameplay Profile: {getattr(cfg, 'gameplay_shader_profile', 'none')}",
            f"Pause Profile: {getattr(cfg, 'pause_shader_profile', 'none')}",
            f"Game Speed: {speed_text}",
            "Open Full Settings",
        ]
    else:
        lines = ["Gameplay Shaders", "Pause Shaders", "Gameplay Profile", "Pause Profile", "Game Speed", "Open Full Settings"]

    draw_centered_text(screen, font, big_font, WIDTH, "Settings", HEIGHT // 2 - 160, use_big=True)
    for i, line in enumerate(lines):
        color = (255, 255, 0) if i == row else (200, 200, 200)
        prefix = "->" if i == row else "  "
        draw_centered_text(screen, font, big_font, WIDTH, f"{prefix} {line}", HEIGHT // 2 - 100 + i * 32, color)
    draw_centered_text(screen, font, big_font, WIDTH, "UP/DOWN: Select | LEFT/RIGHT: Change | ENTER: Confirm | ESC: Back", HEIGHT - 80, (150, 150, 150))


def _render_main_menu(screen, font, big_font, WIDTH, HEIGHT, game_state, cfg) -> None:
    """Render the main pause menu."""
    draw_centered_text(screen, font, big_font, WIDTH, "PAUSED", HEIGHT // 2 - 140, use_big=True)
    y_offset = HEIGHT // 2 - 60
    pause_selected = game_state.ui.pause_selected

    for i, option in enumerate(pause_options):
        display_option = _get_option_display_text(option, cfg)
        color = (255, 255, 0) if i == pause_selected else (200, 200, 200)
        prefix = "->" if i == pause_selected else "  "
        draw_centered_text(screen, font, big_font, WIDTH, f"{prefix} {display_option}", y_offset + i * 40, color)
    draw_centered_text(screen, font, big_font, WIDTH, "Press ENTER to select, ESC to unpause", HEIGHT - 80, (150, 150, 150))


def _get_option_display_text(option: str, cfg) -> str:
    """Get display text for a pause menu option (with current state)."""
    if option == "Toggle FPS" and cfg is not None:
        return f"Toggle FPS ({'On' if cfg.show_fps else 'Off'})"
    elif option == "FPS Cap" and cfg is not None:
        target_fps = getattr(cfg, 'target_fps', 144)
        fps_cap_text = "Uncapped" if target_fps == 0 else str(target_fps)
        return f"FPS Cap: {fps_cap_text}"
    elif option == "Perf Overlay" and cfg is not None:
        return f"Perf Overlay ({'On' if getattr(cfg, 'show_perf_overlay', False) else 'Off'})"
    return option


def render(render_ctx: RenderContext, game_state, screen_ctx) -> None:
    """Draw pause overlay and menu. render_ctx: screen, fonts, width, height."""
    global _overlay_cache, _overlay_size

    screen = render_ctx.screen
    WIDTH, HEIGHT = render_ctx.width, render_ctx.height
    font, big_font = render_ctx.font, render_ctx.big_font

    # Reuse cached overlay surface
    if _overlay_cache is None or _overlay_size != (WIDTH, HEIGHT):
        _overlay_cache = pygame.Surface((WIDTH, HEIGHT))
        _overlay_cache.set_alpha(128)
        _overlay_cache.fill((0, 0, 0))
        _overlay_size = (WIDTH, HEIGHT)

    screen.blit(_overlay_cache, (0, 0))

    # Render idle enemy animations
    run_time = getattr(game_state, "run_time", 0.0) if game_state else 0.0
    render_idle_enemies(screen, run_time)

    if game_state is None:
        return

    submenu = game_state.ui.pause_submenu
    app_ctx = screen_ctx.get("app_ctx") if isinstance(screen_ctx, dict) else None
    cfg = getattr(app_ctx, "config", None) if app_ctx else None

    if submenu == "audio":
        _render_audio_submenu(screen, font, big_font, WIDTH, HEIGHT, game_state)
    elif submenu == "shaders":
        _render_shader_submenu(screen, font, big_font, WIDTH, HEIGHT, game_state, cfg)
    else:
        _render_main_menu(screen, font, big_font, WIDTH, HEIGHT, game_state, cfg)
