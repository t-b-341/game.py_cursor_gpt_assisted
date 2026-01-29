"""Pause screen: handle_events and render. Uses RenderContext for display/fonts."""
from __future__ import annotations

import pygame
from constants import STATE_PLAYING, STATE_ENDURANCE, STATE_MENU, STATE_SAVE_GAME, pause_options
from rendering import RenderContext, draw_centered_text
from systems.audio_system import (
    get_sfx_volume, get_music_volume, set_sfx_volume, set_music_volume,
    is_muted_sfx, is_muted_music, set_muted, play_sfx
)


def handle_events(events, game_state, ctx):
    """
    Process pause-screen events. Mutates game_state.ui.pause_selected.
    Returns dict: {"screen": str|None, "quit": bool, "restart": bool, "restart_to_wave1": bool}.
    """
    out = {"screen": None, "quit": False, "restart": False, "restart_to_wave1": False}
    app_ctx = ctx.get("app_ctx") if isinstance(ctx, dict) else None
    cfg = getattr(app_ctx, "config", None) if app_ctx else None
    if game_state is None:
        return out
    submenu = game_state.ui.pause_submenu

    for event in events:
        if not hasattr(event, "type") or event.type != pygame.KEYDOWN:
            continue
        
        # Audio submenu handling
        if submenu == "audio":
            if not hasattr(game_state.ui, 'pause_audio_options_row'):
                game_state.ui.pause_audio_options_row = 0
            row = game_state.ui.pause_audio_options_row
            
            if event.key == pygame.K_ESCAPE:
                game_state.ui.pause_submenu = None
                break
            elif event.key in (pygame.K_UP, pygame.K_w):
                game_state.ui.pause_audio_options_row = (row - 1) % 4  # 4 options
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                game_state.ui.pause_audio_options_row = (row + 1) % 4  # 4 options
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                if row == 0:  # SFX Volume
                    new_vol = max(0.0, get_sfx_volume() - 0.1)
                    set_sfx_volume(new_vol)
                    if cfg:
                        cfg.sfx_volume = new_vol
                elif row == 1:  # Music Volume
                    new_vol = max(0.0, get_music_volume() - 0.1)
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
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                if row == 0:  # SFX Volume
                    new_vol = min(1.0, get_sfx_volume() + 0.1)
                    set_sfx_volume(new_vol)
                    if cfg:
                        cfg.sfx_volume = new_vol
                    # Play test sound when adjusting SFX volume
                    play_sfx("BASIC SHOT")
                elif row == 1:  # Music Volume
                    new_vol = min(1.0, get_music_volume() + 0.1)
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
            continue
        
        if submenu == "shaders":
            # Ensure row is initialized
            if game_state is not None:
                if not hasattr(game_state.ui, 'pause_shader_options_row'):
                    game_state.ui.pause_shader_options_row = 0
                row = game_state.ui.pause_shader_options_row
            else:
                row = 0
            
            _pp = ["none", "pause_dim_vignette"]
            _gp = ["none", "gameplay_subtle_vignette", "gameplay_retro"]
            
            if event.key == pygame.K_ESCAPE:
                if game_state is not None:
                    game_state.ui.pause_submenu = None
                break
            elif event.key in (pygame.K_UP, pygame.K_w):
                if game_state is not None:
                    # Ensure row is initialized
                    if not hasattr(game_state.ui, 'pause_shader_options_row'):
                        game_state.ui.pause_shader_options_row = 0
                    current = game_state.ui.pause_shader_options_row
                    new = (current - 1) % 5  # 5 options now (4 settings + Full Settings)
                    game_state.ui.pause_shader_options_row = new
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                if game_state is not None:
                    # Ensure row is initialized
                    if not hasattr(game_state.ui, 'pause_shader_options_row'):
                        game_state.ui.pause_shader_options_row = 0
                    current = game_state.ui.pause_shader_options_row
                    new = (current + 1) % 5  # 5 options now (4 settings + Full Settings)
                    game_state.ui.pause_shader_options_row = new
            elif event.key in (pygame.K_LEFT, pygame.K_a) and cfg is not None:
                # Refresh row value in case it was just updated
                row = game_state.ui.pause_shader_options_row if game_state is not None else 0
                if row == 0:
                    cfg.enable_gameplay_shaders = not cfg.enable_gameplay_shaders
                elif row == 1:
                    cfg.enable_pause_shaders = not cfg.enable_pause_shaders
                elif row == 2:
                    cur = getattr(cfg, "gameplay_shader_profile", "none")
                    i = (_gp.index(cur) if cur in _gp else 0) - 1
                    cfg.gameplay_shader_profile = _gp[i % len(_gp)]
                elif row == 3:
                    cur = getattr(cfg, "pause_shader_profile", "none")
                    i = (_pp.index(cur) if cur in _pp else 0) - 1
                    cfg.pause_shader_profile = _pp[i % len(_pp)]
            elif event.key in (pygame.K_RIGHT, pygame.K_d) and cfg is not None:
                # Refresh row value in case it was just updated
                row = game_state.ui.pause_shader_options_row if game_state is not None else 0
                if row == 0:
                    cfg.enable_gameplay_shaders = not cfg.enable_gameplay_shaders
                elif row == 1:
                    cfg.enable_pause_shaders = not cfg.enable_pause_shaders
                elif row == 2:
                    cur = getattr(cfg, "gameplay_shader_profile", "none")
                    i = (_gp.index(cur) if cur in _gp else 0) + 1
                    cfg.gameplay_shader_profile = _gp[i % len(_gp)]
                elif row == 3:
                    cur = getattr(cfg, "pause_shader_profile", "none")
                    i = (_pp.index(cur) if cur in _pp else 0) + 1
                    cfg.pause_shader_profile = _pp[i % len(_pp)]
                # Row 4 is "Full Settings" - handled by Enter key
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                row = game_state.ui.pause_shader_options_row if game_state is not None else 0
                if row == 4:  # "Full Settings" option
                    # Open full shader settings screen
                    out["screen"] = "SHADER_SETTINGS"
                    return out  # Return immediately to ensure transition is processed
                # For other rows, Enter does nothing (values changed with LEFT/RIGHT)
            continue
        
        # Handle ESCAPE key
        if event.key == pygame.K_ESCAPE:
            if game_state is not None:
                target = game_state.previous_screen or STATE_PLAYING
            else:
                target = STATE_PLAYING
            if target not in (STATE_PLAYING, STATE_ENDURANCE):
                target = STATE_PLAYING
            out["screen"] = target
            break
        
        # Handle navigation keys (only if not in submenu)
        if event.key == pygame.K_UP or event.key == pygame.K_w:
            if game_state is not None:
                current = game_state.ui.pause_selected
                new = (current - 1) % len(pause_options)
                game_state.ui.pause_selected = new
                # Debug: verify update
                if game_state.ui.pause_selected != new:
                    print(f"[Pause] Warning: pause_selected not updated correctly: expected {new}, got {game_state.ui.pause_selected}")
        elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
            if game_state is not None:
                current = game_state.ui.pause_selected
                new = (current + 1) % len(pause_options)
                game_state.ui.pause_selected = new
                # Debug: verify update
                if game_state.ui.pause_selected != new:
                    print(f"[Pause] Warning: pause_selected not updated correctly: expected {new}, got {game_state.ui.pause_selected}")
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            if game_state is None:
                continue
            choice = pause_options[game_state.ui.pause_selected]
            if choice == "Continue":
                if game_state is not None:
                    target = game_state.previous_screen or STATE_PLAYING
                else:
                    target = STATE_PLAYING
                if target not in (STATE_PLAYING, STATE_ENDURANCE):
                    target = STATE_PLAYING
                out["screen"] = target
            elif choice == "Restart (Wave 1)":
                out["restart_to_wave1"] = True
                out["screen"] = STATE_PLAYING
            elif choice == "Audio options":
                if game_state is not None:
                    game_state.ui.pause_submenu = "audio"
                    if not hasattr(game_state.ui, 'pause_audio_options_row'):
                        game_state.ui.pause_audio_options_row = 0
                    else:
                        game_state.ui.pause_audio_options_row = 0  # Reset to first option
            elif choice == "Shader options":
                if game_state is not None:
                    game_state.ui.pause_submenu = "shaders"
                    # Initialize shader options row when entering submenu
                    if not hasattr(game_state.ui, 'pause_shader_options_row'):
                        game_state.ui.pause_shader_options_row = 0
                    else:
                        game_state.ui.pause_shader_options_row = 0  # Reset to first option
            elif choice == "Save & Quit":
                if game_state is not None:
                    game_state.ui.save_and_quit = True  # Flag to go to title after saving
                    out["screen"] = STATE_SAVE_GAME
                    out["save_and_quit"] = True
            elif choice == "Exit to main menu":
                out["screen"] = STATE_MENU
            elif choice == "Quit":
                out["quit"] = True
    return out


def render(render_ctx: RenderContext, game_state, screen_ctx) -> None:
    """Draw pause overlay and menu. render_ctx: screen, fonts, width, height."""
    screen = render_ctx.screen
    WIDTH = render_ctx.width
    HEIGHT = render_ctx.height
    font = render_ctx.font
    big_font = render_ctx.big_font
    overlay = pygame.Surface((WIDTH, HEIGHT))
    overlay.set_alpha(128)
    overlay.fill((0, 0, 0))
    screen.blit(overlay, (0, 0))

    if game_state is None:
        return
    submenu = game_state.ui.pause_submenu
    
    # Audio submenu render
    if submenu == "audio":
        row = getattr(game_state.ui, 'pause_audio_options_row', 0)
        row = max(0, min(3, row))  # 4 options
        
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
            draw_centered_text(screen, font, big_font, WIDTH, f"{'->' if i == row else '  '} {line}", HEIGHT // 2 - 80 + i * 40, color)
        draw_centered_text(screen, font, big_font, WIDTH, "UP/DOWN: Select | LEFT/RIGHT: Adjust | ESC: Back", HEIGHT - 80, (150, 150, 150))
        return
    
    if submenu == "shaders":
        app_ctx = screen_ctx.get("app_ctx") if isinstance(screen_ctx, dict) else None
        cfg = getattr(app_ctx, "config", None) if app_ctx else None
        # Read row value directly from game_state to ensure we get the latest value
        row = getattr(game_state.ui, 'pause_shader_options_row', 0)
        # Clamp row to valid range [0, 4] to prevent out-of-bounds (5 options now)
        row = max(0, min(4, row))
        if cfg is not None:
            lines = [
                f"Gameplay Shaders: {'On' if getattr(cfg, 'enable_gameplay_shaders', False) else 'Off'}",
                f"Pause Shaders: {'On' if getattr(cfg, 'enable_pause_shaders', False) else 'Off'}",
                f"Gameplay Profile: {getattr(cfg, 'gameplay_shader_profile', 'none')}",
                f"Pause Profile: {getattr(cfg, 'pause_shader_profile', 'none')}",
                "Open Full Settings",
            ]
        else:
            lines = ["Gameplay Shaders", "Pause Shaders", "Gameplay Profile", "Pause Profile", "Open Full Settings"]
        draw_centered_text(screen, font, big_font, WIDTH, "Shader options", HEIGHT // 2 - 140, use_big=True)
        for i, line in enumerate(lines):
            color = (255, 255, 0) if i == row else (200, 200, 200)
            draw_centered_text(screen, font, big_font, WIDTH, f"{'->' if i == row else '  '} {line}", HEIGHT // 2 - 80 + i * 35, color)
        draw_centered_text(screen, font, big_font, WIDTH, "UP/DOWN: Select | LEFT/RIGHT: Change value | ENTER: Open Full/Continue | ESC: Back", HEIGHT - 80, (150, 150, 150))
        return

    draw_centered_text(screen, font, big_font, WIDTH, "PAUSED", HEIGHT // 2 - 140, use_big=True)
    y_offset = HEIGHT // 2 - 60
    pause_selected = game_state.ui.pause_selected if game_state is not None else 0
    for i, option in enumerate(pause_options):
        color = (255, 255, 0) if i == pause_selected else (200, 200, 200)
        draw_centered_text(screen, font, big_font, WIDTH, f"{'->' if i == pause_selected else '  '} {option}", y_offset + i * 40, color)
    draw_centered_text(screen, font, big_font, WIDTH, "Press ENTER to select, ESC to unpause", HEIGHT - 80, (150, 150, 150))
