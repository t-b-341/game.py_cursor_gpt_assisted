"""
Game initialization functions.

This module contains all initialization logic previously in game.py:
- Pygame and mixer initialization
- Window and clock creation
- AppContext and GameState building
- Resource setup (high scores, music, shaders)
- Scene stack creation
"""
from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pygame

from asset_manager import get_font
from config import GameConfig, apply_safe_mode, log_startup_config
from constants import (
    AIM_MOUSE,
    DIFFICULTY_NORMAL,
    PLAYER_CLASS_BALANCED,
    STATE_TITLE,
)
from context import AppContext
from controls_io import load_controls
from event_bus import EventBus
from game_utils import init_high_scores_db
from geometry_utils import set_screen_dimensions
from level_builder import build_level_geometry, place_teleporter_pads
from level_utils import filter_blocks_no_overlap
from physics_loader import resolve_physics
from rendering import draw_centered_text
from scenes import SceneStack, TitleScene
from simulation_systems import SIMULATION_SYSTEMS
from state import GameState
from systems.audio_system import init_mixer, sync_from_config, play_music
from telemetry.event_bus_handlers import register_telemetry_event_handlers


def init_pygame_and_mixer() -> None:
    """Initialize pygame and audio mixer."""
    pygame.init()
    init_mixer()
    print("welcome to my game! :D")
    
    # Verify sound files can be loaded
    from asset_manager import get_sound
    test_sounds = ["BASIC SHOT", "DODGE", "WAVE START"]
    for name in test_sounds:
        snd = get_sound(name)
        if snd:
            print(f"[audio] Sound loaded OK: {name}")
        else:
            print(f"[audio] WARNING: Could not load sound: {name}")


def create_window_and_clock() -> tuple[pygame.Surface, pygame.time.Clock, int, int]:
    """Create window, clock, and fonts. Returns (screen, clock, width, height)."""
    pygame.display.init()
    screen_info = pygame.display.Info()
    WIDTH, HEIGHT = screen_info.current_w, screen_info.current_h
    set_screen_dimensions(WIDTH, HEIGHT)
    # Use hardware acceleration, double buffering, and disable vsync for max FPS
    display_flags = pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF
    # vsync=0 disables vertical sync for uncapped frame rates
    screen = pygame.display.set_mode((WIDTH, HEIGHT), display_flags, vsync=0)
    pygame.display.set_caption("Mouse Aim Shooter + Telemetry (SQLite)")

    clock = pygame.time.Clock()
    # Pre-load fonts (used by AppContext)
    get_font("main", 28)
    get_font("main", 56)
    get_font("main", 20)
    
    return screen, clock, WIDTH, HEIGHT


def build_app_context(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    display_width: int,
    display_height: int,
    using_c_physics: bool
) -> AppContext:
    """Build AppContext with config, controls, and resources."""
    controls = load_controls()
    
    cfg = GameConfig(
        difficulty=DIFFICULTY_NORMAL,
        aim_mode=AIM_MOUSE,
        aiming_mechanic="mouse",
        player_class=PLAYER_CLASS_BALANCED,
        enable_telemetry=True,  # Enable telemetry by default for analytics
        show_metrics=True,
        show_hud=True,
        show_health_bars=True,
        show_player_health_bar=True,
        profile_enabled=False,
        testing_mode=True,
        invulnerability_mode=False,
        default_weapon_mode="giant",
        mod_enemy_spawn_multiplier=1.0,
        mod_custom_waves_enabled=False,
    )
    
    # Calculate world dimensions based on world_scale
    world_scale = cfg.world_scale
    world_width = int(display_width * world_scale)
    world_height = int(display_height * world_scale)
    
    # Create world surface for rendering (larger than display)
    world_surface = pygame.Surface((world_width, world_height)).convert()
    
    # Update screen dimensions used by physics/collision
    set_screen_dimensions(world_width, world_height)
    
    event_bus = EventBus()
    ctx = AppContext(
        screen=screen,
        clock=clock,
        font=get_font("main", 28),
        big_font=get_font("main", 56),
        small_font=get_font("main", 20),
        display_width=display_width,
        display_height=display_height,
        width=world_width,
        height=world_height,
        world_surface=world_surface,
        telemetry_client=None,
        run_started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        controls=controls,
        config=cfg,
        using_c_physics=using_c_physics,
        event_bus=event_bus,
    )
    sync_from_config(ctx.config)
    print(f"World scale: {world_scale}x | Display: {display_width}x{display_height} | World: {world_width}x{world_height}")
    
    # Initialize camera for viewport management
    from systems.camera import create_camera
    create_camera(
        display_width=display_width,
        display_height=display_height,
        world_width=world_width,
        world_height=world_height,
        smoothing=8.0,
    )
    print(f"Camera initialized: viewport {display_width}x{display_height}, world {world_width}x{world_height}")
    
    return ctx


def build_initial_game_state(ctx: AppContext) -> GameState:
    """Create and initialize GameState with level geometry and context."""
    game_state = GameState()
    game_state.player_rect = pygame.Rect((ctx.width - 28) // 2, (ctx.height - 28) // 2, 28, 28)
    game_state.current_screen = STATE_TITLE
    game_state.run_started_at = ctx.run_started_at

    # Initialize pygame mouse visibility
    pygame.mouse.set_visible(True)

    # Build level geometry and store in game_state.level
    level = build_level_geometry(ctx.width, ctx.height)
    level.destructible_blocks = filter_blocks_no_overlap(
        level.destructible_blocks,
        [level.moveable_blocks, level.giant_blocks, level.super_giant_blocks, level.trapezoid_blocks, level.triangle_blocks],
        game_state.player_rect
    )
    level.moveable_blocks = filter_blocks_no_overlap(
        level.moveable_blocks,
        [level.destructible_blocks, level.giant_blocks, level.super_giant_blocks, level.trapezoid_blocks, level.triangle_blocks],
        game_state.player_rect
    )
    level.giant_blocks = filter_blocks_no_overlap(
        level.giant_blocks,
        [level.destructible_blocks, level.moveable_blocks, level.super_giant_blocks, level.trapezoid_blocks, level.triangle_blocks],
        game_state.player_rect
    )
    level.super_giant_blocks = filter_blocks_no_overlap(
        level.super_giant_blocks,
        [level.destructible_blocks, level.moveable_blocks, level.giant_blocks, level.trapezoid_blocks, level.triangle_blocks],
        game_state.player_rect
    )
    game_state.level = level
    game_state.teleporter_pads = place_teleporter_pads(level, ctx.width, ctx.height)
    
    # Level context for movement_system and collision_system
    from level_utils import make_level_context
    game_state.level_context = make_level_context(ctx, game_state)
    game_state.run_id = None  # Will be set when game starts
    return game_state


def setup_initial_resources() -> None:
    """Initialize high scores database, copy music file if needed, and play initial music."""
    init_high_scores_db()
    
    # Ensure in-game.ogg is available
    _project_root = Path(__file__).resolve().parent
    _music_dir = _project_root / "assets" / "music"
    _in_game_dst = _music_dir / "in-game.ogg"
    _in_game_src = _project_root / "in-game.ogg"
    if not _in_game_dst.exists() and _in_game_src.exists():
        try:
            _music_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(_in_game_src, _in_game_dst)
        except OSError:
            pass
    
    # Load and apply shader settings from config/shaders.json if available
    try:
        from rendering_shaders import apply_shader_settings_to_pipeline
        apply_shader_settings_to_pipeline()
    except Exception as e:
        print(f"[Game] Failed to load shader settings on startup: {e}")
    
    # Main menu uses ambient2 music
    play_music("ambient2", loop=True)


def prompt_shader_mode(ctx: AppContext, show_prompt: bool = False) -> None:
    """Initialize shader mode settings.
    
    Args:
        ctx: Application context
        show_prompt: If True, show the interactive Y/N prompt. If False, use defaults.
    """
    try:
        import moderngl  # noqa: F401
        moderngl_available = True
    except ImportError:
        print("moderngl not available; disabling shader mode.")
        ctx.config.use_shaders = False
        moderngl_available = False
    
    if moderngl_available and show_prompt:
        # Interactive prompt (disabled by default)
        prompt_done = False
        prompt_clock = pygame.time.Clock()
        display_w = getattr(ctx, 'display_width', ctx.width)
        display_h = getattr(ctx, 'display_height', ctx.height)
        while not prompt_done:
            prompt_clock.tick(60)
            ctx.screen.fill((30, 30, 40))
            draw_centered_text(ctx.screen, ctx.font, ctx.big_font, display_w,
                               "Enable GPU shaders?", display_h // 2 - 50, color=(220, 220, 220), use_big=True)
            draw_centered_text(ctx.screen, ctx.font, ctx.big_font, display_w,
                               "(Y)es  /  (N)o", display_h // 2 + 20, (180, 180, 180))
            pygame.display.flip()
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    prompt_done = True
                    ctx.config.use_shaders = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_y:
                        ctx.config.use_shaders = True
                        ctx.config.use_gpu_shader_pipeline = True
                        ctx.config.enable_gameplay_shaders = False
                        ctx.config.enable_pause_shaders = True
                        ctx.config.pause_shader_profile = "pause_dim_vignette"
                        prompt_done = True
                    elif e.key == pygame.K_n:
                        ctx.config.use_shaders = False
                        ctx.config.use_gpu_shader_pipeline = False
                        ctx.config.enable_gameplay_shaders = False
                        ctx.config.enable_pause_shaders = False
                        prompt_done = True
    elif moderngl_available:
        # Default: shaders disabled at startup
        ctx.config.use_shaders = False
        ctx.config.use_gpu_shader_pipeline = False
        ctx.config.enable_gameplay_shaders = False
        ctx.config.enable_pause_shaders = False
    
    # Log shader configuration
    if ctx.config.use_shaders:
        print("Shader mode: ON")
    if ctx.config.use_gpu_shader_pipeline:
        print("GPU particle effects: ENABLED (shot/rocket/bomb bursts)")
    if ctx.config.enable_pause_shaders:
        print(f"Pause effects: ENABLED (profile: {ctx.config.pause_shader_profile})")
    if ctx.config.enable_gameplay_shaders:
        print(f"CPU gameplay effects: ENABLED (profile: {ctx.config.gameplay_shader_profile})")


def build_scene_stack() -> SceneStack:
    """Create and initialize scene stack with TitleScene."""
    scene_stack = SceneStack()
    scene_stack.push(TitleScene())
    return scene_stack


def build_loop_params(target_fps: int = 144) -> tuple[int, float, int]:
    """Return (FPS, FIXED_DT, MAX_SIMULATION_STEPS).
    
    Args:
        target_fps: Target frame rate. 0 means uncapped.
    """
    FPS = target_fps if target_fps > 0 else 0
    FIXED_DT = 1.0 / 60.0  # Physics runs at fixed 60Hz
    MAX_SIMULATION_STEPS = 8
    return FPS, FIXED_DT, MAX_SIMULATION_STEPS


class AppResult:
    """Container for app initialization results."""
    def __init__(self):
        self.ctx = None
        self.game_state = None
        self.scene_stack = None
        self.fps = 0
        self.fixed_dt = 0.0
        self.max_sim_steps = 0
        self.update_simulation = None
        self.simulation_accumulator = 0.0


def create_app() -> AppResult:
    """Build ctx, game_state, scene_stack and loop invariants. Used by GameApp."""
    # Check for --safe-mode CLI flag or environment variable
    safe_mode = "--safe-mode" in sys.argv or os.environ.get("GAME_SAFE_MODE", "").strip() == "1"
    
    # Resolve physics backend
    force_python = "--python-physics" in sys.argv or os.environ.get("USE_PYTHON_PHYSICS", "").strip() == "1"
    _physics_impl, using_c_physics = resolve_physics(force_python=force_python)

    init_pygame_and_mixer()
    screen, clock, width, height = create_window_and_clock()
    ctx = build_app_context(screen, clock, width, height, using_c_physics)
    
    # Apply safe mode if requested
    if safe_mode:
        ctx.config.safe_mode = True
        apply_safe_mode(ctx.config)
    
    # Log startup configuration summary
    log_startup_config(ctx.config)
    
    game_state = build_initial_game_state(ctx)
    setup_initial_resources()
    prompt_shader_mode(ctx)

    # Hook telemetry handlers into EventBus
    register_telemetry_event_handlers(ctx.event_bus, ctx, game_state)

    # Get target FPS from config
    target_fps = getattr(ctx.config, 'target_fps', 144)
    FPS, FIXED_DT, MAX_SIMULATION_STEPS = build_loop_params(target_fps)
    
    def _update_simulation(sim_dt: float, gs: GameState, app_ctx: AppContext) -> None:
        """Run one fixed timestep of gameplay."""
        for system in SIMULATION_SYSTEMS:
            system(gs, sim_dt, app_ctx)

    scene_stack = build_scene_stack()
    
    r = AppResult()
    r.ctx = ctx
    r.game_state = game_state
    r.scene_stack = scene_stack
    r.fps = FPS
    r.fixed_dt = FIXED_DT
    r.max_sim_steps = MAX_SIMULATION_STEPS
    r.update_simulation = _update_simulation
    r.simulation_accumulator = 0.0
    return r
