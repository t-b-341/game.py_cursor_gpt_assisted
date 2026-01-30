"""Pause screen: handle_events and render. Uses RenderContext for display/fonts."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import pygame
from constants import STATE_PLAYING, STATE_ENDURANCE, STATE_MENU, STATE_SAVE_GAME, pause_options, fps_cap_options
from rendering import RenderContext, draw_centered_text
from systems.audio_system import (
    get_sfx_volume, get_music_volume, set_sfx_volume, set_music_volume,
    is_muted_sfx, is_muted_music, set_muted, play_sfx
)


# Cached overlay surface to avoid per-frame allocation
_overlay_cache: pygame.Surface | None = None
_overlay_size: tuple[int, int] = (0, 0)


# ============================================================================
# Idle enemy animation system for pause screen
# ============================================================================

@dataclass
class IdleEnemy:
    """An animated enemy that floats around the pause screen."""
    x: float
    y: float
    vx: float
    vy: float
    size: int
    color: tuple[int, int, int]
    shape: str  # "circle", "square", "triangle"
    bob_offset: float = 0.0  # For bobbing animation
    bob_speed: float = 2.0
    time_to_exit: float = 0.0  # Timer for when to fly off screen
    exiting: bool = False  # True when flying off screen
    exit_target_x: float = 0.0
    exit_target_y: float = 0.0
    returning: bool = False  # True when returning to screen


# Enemy colors based on actual game enemies
ENEMY_COLORS = [
    (255, 100, 100),  # Red - basic
    (100, 100, 255),  # Blue - ranged
    (255, 200, 100),  # Orange - fast
    (150, 80, 200),   # Purple - ambient
    (100, 255, 100),  # Green - healer
    (255, 255, 100),  # Yellow - suicide
]

ENEMY_SHAPES = ["circle", "square", "triangle"]

# Module-level state for idle enemies
_idle_enemies: list[IdleEnemy] = []
_idle_enemies_initialized: bool = False
_screen_size: tuple[int, int] = (0, 0)


def _init_idle_enemies(width: int, height: int, count: int = 8) -> None:
    """Initialize idle enemies for the pause screen."""
    global _idle_enemies, _idle_enemies_initialized, _screen_size
    
    _idle_enemies = []
    _screen_size = (width, height)
    
    for _ in range(count):
        enemy = _create_idle_enemy(width, height, spawn_onscreen=True)
        _idle_enemies.append(enemy)
    
    _idle_enemies_initialized = True


def _create_idle_enemy(width: int, height: int, spawn_onscreen: bool = True) -> IdleEnemy:
    """Create a new idle enemy with random properties."""
    size = random.randint(20, 45)
    color = random.choice(ENEMY_COLORS)
    shape = random.choice(ENEMY_SHAPES)
    
    if spawn_onscreen:
        # Spawn within screen bounds (with margin)
        margin = 100
        x = random.uniform(margin, width - margin)
        y = random.uniform(margin, height - margin)
    else:
        # Spawn off screen
        side = random.randint(0, 3)
        if side == 0:  # Top
            x = random.uniform(0, width)
            y = -size - 20
        elif side == 1:  # Right
            x = width + size + 20
            y = random.uniform(0, height)
        elif side == 2:  # Bottom
            x = random.uniform(0, width)
            y = height + size + 20
        else:  # Left
            x = -size - 20
            y = random.uniform(0, height)
    
    # Random velocity (slow, drifting motion)
    speed = random.uniform(20, 60)
    angle = random.uniform(0, 2 * math.pi)
    vx = math.cos(angle) * speed
    vy = math.sin(angle) * speed
    
    # Time until this enemy decides to fly off screen
    time_to_exit = random.uniform(5.0, 15.0)
    
    return IdleEnemy(
        x=x, y=y, vx=vx, vy=vy,
        size=size, color=color, shape=shape,
        bob_offset=random.uniform(0, 2 * math.pi),
        bob_speed=random.uniform(1.5, 3.0),
        time_to_exit=time_to_exit,
    )


def update_idle_enemies(dt: float, width: int, height: int) -> None:
    """Update all idle enemies (called each frame while paused)."""
    global _idle_enemies, _idle_enemies_initialized, _screen_size
    
    # Reinitialize if screen size changed
    if not _idle_enemies_initialized or _screen_size != (width, height):
        _init_idle_enemies(width, height)
        return
    
    margin = 150  # How far off screen before considered "exited"
    
    for enemy in _idle_enemies:
        # Update bob animation
        enemy.bob_offset += enemy.bob_speed * dt
        
        if enemy.exiting:
            # Move towards exit target
            dx = enemy.exit_target_x - enemy.x
            dy = enemy.exit_target_y - enemy.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 1:
                speed = 200  # Faster when exiting
                enemy.x += (dx / dist) * speed * dt
                enemy.y += (dy / dist) * speed * dt
            
            # Check if fully off screen
            if (enemy.x < -margin or enemy.x > width + margin or
                enemy.y < -margin or enemy.y > height + margin):
                # Reset as returning enemy
                enemy.exiting = False
                enemy.returning = True
                
                # Pick a new entry point (opposite side)
                side = random.randint(0, 3)
                if side == 0:
                    enemy.x = random.uniform(0, width)
                    enemy.y = -enemy.size - 20
                elif side == 1:
                    enemy.x = width + enemy.size + 20
                    enemy.y = random.uniform(0, height)
                elif side == 2:
                    enemy.x = random.uniform(0, width)
                    enemy.y = height + enemy.size + 20
                else:
                    enemy.x = -enemy.size - 20
                    enemy.y = random.uniform(0, height)
                
                # Set velocity towards center area
                target_x = width // 2 + random.uniform(-200, 200)
                target_y = height // 2 + random.uniform(-200, 200)
                dx = target_x - enemy.x
                dy = target_y - enemy.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 1:
                    speed = random.uniform(40, 80)
                    enemy.vx = (dx / dist) * speed
                    enemy.vy = (dy / dist) * speed
                
                enemy.time_to_exit = random.uniform(5.0, 15.0)
        
        elif enemy.returning:
            # Move with velocity until on screen
            enemy.x += enemy.vx * dt
            enemy.y += enemy.vy * dt
            
            # Check if back on screen
            if 50 < enemy.x < width - 50 and 50 < enemy.y < height - 50:
                enemy.returning = False
        
        else:
            # Normal floating behavior
            enemy.x += enemy.vx * dt
            enemy.y += enemy.vy * dt
            
            # Bounce off screen edges (with some randomness)
            if enemy.x < 50:
                enemy.vx = abs(enemy.vx) + random.uniform(-10, 10)
                enemy.x = 50
            elif enemy.x > width - 50:
                enemy.vx = -abs(enemy.vx) + random.uniform(-10, 10)
                enemy.x = width - 50
            
            if enemy.y < 100:  # Keep above pause menu
                enemy.vy = abs(enemy.vy) + random.uniform(-10, 10)
                enemy.y = 100
            elif enemy.y > height - 150:  # Keep above bottom text
                enemy.vy = -abs(enemy.vy) + random.uniform(-10, 10)
                enemy.y = height - 150
            
            # Occasionally change direction slightly
            if random.random() < 0.01:  # 1% chance per frame
                enemy.vx += random.uniform(-20, 20)
                enemy.vy += random.uniform(-20, 20)
                # Clamp speed
                speed = math.sqrt(enemy.vx ** 2 + enemy.vy ** 2)
                if speed > 80:
                    enemy.vx = (enemy.vx / speed) * 80
                    enemy.vy = (enemy.vy / speed) * 80
            
            # Check if it's time to exit
            enemy.time_to_exit -= dt
            if enemy.time_to_exit <= 0:
                enemy.exiting = True
                # Pick an exit point off screen
                side = random.randint(0, 3)
                if side == 0:
                    enemy.exit_target_x = random.uniform(0, width)
                    enemy.exit_target_y = -100
                elif side == 1:
                    enemy.exit_target_x = width + 100
                    enemy.exit_target_y = random.uniform(0, height)
                elif side == 2:
                    enemy.exit_target_x = random.uniform(0, width)
                    enemy.exit_target_y = height + 100
                else:
                    enemy.exit_target_x = -100
                    enemy.exit_target_y = random.uniform(0, height)


def render_idle_enemies(screen: pygame.Surface, run_time: float) -> None:
    """Render all idle enemies on the pause screen."""
    for enemy in _idle_enemies:
        # Apply bobbing animation
        bob_y = math.sin(enemy.bob_offset) * 5
        
        x = int(enemy.x)
        y = int(enemy.y + bob_y)
        size = enemy.size
        color = enemy.color
        
        # Draw based on shape
        if enemy.shape == "circle":
            pygame.draw.circle(screen, color, (x, y), size // 2)
            # Darker border
            border_color = (max(0, color[0] - 60), max(0, color[1] - 60), max(0, color[2] - 60))
            pygame.draw.circle(screen, border_color, (x, y), size // 2, 3)
        
        elif enemy.shape == "square":
            rect = pygame.Rect(x - size // 2, y - size // 2, size, size)
            pygame.draw.rect(screen, color, rect)
            border_color = (max(0, color[0] - 60), max(0, color[1] - 60), max(0, color[2] - 60))
            pygame.draw.rect(screen, border_color, rect, 3)
        
        elif enemy.shape == "triangle":
            half = size // 2
            points = [
                (x, y - half),  # Top
                (x - half, y + half),  # Bottom left
                (x + half, y + half),  # Bottom right
            ]
            pygame.draw.polygon(screen, color, points)
            border_color = (max(0, color[0] - 60), max(0, color[1] - 60), max(0, color[2] - 60))
            pygame.draw.polygon(screen, border_color, points, 3)


def reset_idle_enemies() -> None:
    """Reset idle enemies (call when leaving pause screen)."""
    global _idle_enemies_initialized
    _idle_enemies_initialized = False


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
            elif choice == "Toggle FPS":
                # Toggle FPS graph display
                if cfg is not None:
                    cfg.show_fps = not cfg.show_fps
            elif choice == "FPS Cap":
                # Cycle through FPS cap options
                if cfg is not None:
                    current_fps = getattr(cfg, 'target_fps', 144)
                    try:
                        current_idx = fps_cap_options.index(current_fps)
                    except ValueError:
                        current_idx = 0
                    next_idx = (current_idx + 1) % len(fps_cap_options)
                    cfg.target_fps = fps_cap_options[next_idx]
            elif choice == "Perf Overlay":
                # Toggle performance overlay (shows entity counts)
                if cfg is not None:
                    cfg.show_perf_overlay = not getattr(cfg, 'show_perf_overlay', False)
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
    global _overlay_cache, _overlay_size
    
    screen = render_ctx.screen
    WIDTH = render_ctx.width
    HEIGHT = render_ctx.height
    font = render_ctx.font
    big_font = render_ctx.big_font
    
    # Reuse cached overlay surface (avoids per-frame allocation)
    if _overlay_cache is None or _overlay_size != (WIDTH, HEIGHT):
        _overlay_cache = pygame.Surface((WIDTH, HEIGHT))
        _overlay_cache.set_alpha(128)
        _overlay_cache.fill((0, 0, 0))
        _overlay_size = (WIDTH, HEIGHT)
    
    screen.blit(_overlay_cache, (0, 0))
    
    # Render idle enemy animations (behind menu text)
    run_time = getattr(game_state, "run_time", 0.0) if game_state else 0.0
    render_idle_enemies(screen, run_time)

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
    
    # Get config for dynamic option text
    app_ctx = screen_ctx.get("app_ctx") if isinstance(screen_ctx, dict) else None
    cfg = getattr(app_ctx, "config", None) if app_ctx else None
    
    for i, option in enumerate(pause_options):
        # Show current state in option text for toggle options
        display_option = option
        if option == "Toggle FPS" and cfg is not None:
            fps_state = "On" if cfg.show_fps else "Off"
            display_option = f"Toggle FPS ({fps_state})"
        elif option == "FPS Cap" and cfg is not None:
            target_fps = getattr(cfg, 'target_fps', 144)
            fps_cap_text = "Uncapped" if target_fps == 0 else str(target_fps)
            display_option = f"FPS Cap: {fps_cap_text}"
        elif option == "Perf Overlay" and cfg is not None:
            perf_state = "On" if getattr(cfg, 'show_perf_overlay', False) else "Off"
            display_option = f"Perf Overlay ({perf_state})"
        
        color = (255, 255, 0) if i == pause_selected else (200, 200, 200)
        draw_centered_text(screen, font, big_font, WIDTH, f"{'->' if i == pause_selected else '  '} {display_option}", y_offset + i * 40, color)
    draw_centered_text(screen, font, big_font, WIDTH, "Press ENTER to select, ESC to unpause", HEIGHT - 80, (150, 150, 150))
