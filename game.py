"""
Main game entry point. Runs the game loop, handles menus, gameplay, and screen transitions.
All mutable game state lives in GameState; app-level resources and config in AppContext.
Level geometry in state.level (LevelState). Gameplay input via handle_gameplay_input;
per-frame logic in _update_simulation (movement/collision/spawn/ai). Overlay screens use
scenes from scenes/ and RenderContext.from_app_ctx(ctx).

# -----------------------------------------------------------------------------
# Screen/state mapping
# -----------------------------------------------------------------------------
# All game states are represented as Scene classes in scenes/:
# - TitleScene (STATE_TITLE): Title screen
# - OptionsScene (STATE_MENU): Options/settings menu
# - GameplayScene (STATE_PLAYING, STATE_ENDURANCE): Main gameplay
# - PauseScene (STATE_PAUSED): Pause overlay
# - NameInputScene (STATE_NAME_INPUT): High score name entry
# - HighScoreScene (STATE_HIGH_SCORES): High scores list
# - GameOverScene (STATE_GAME_OVER): Game over screen
# - VictoryScene (STATE_VICTORY): Victory screen after beating all levels
# - SaveGameScene (STATE_SAVE_GAME): Save game menu
# - LoadGameScene (STATE_LOAD_GAME): Load game menu
# - QuickLaunchScene (STATE_QUICK_LAUNCH): Quick launch menu
# - ShaderTestScene ("SHADER_TEST"): Shader testing
# - ShaderSettingsScreen ("SHADER_SETTINGS"): Shader settings
#
# GameState.current_screen (str): canonical "what screen we are on"
# GameState.previous_screen (str|None): used for pause/unpause to restore PLAYING or ENDURANCE
#
# Input flows through scene_stack.current().handle_input_transition() which returns
# SceneTransition objects (push, pop, replace, quit_game, or none).
# -----------------------------------------------------------------------------
"""
import json
import logging
import math
import os
import random
import shutil
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pygame
import sqlite3

# Suppress pygame's pkg_resources deprecation warning (pygame internal, not our code)
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

# Optional GPU acceleration (numba/CUDA). Single capability flag; CPU fallback when disabled.
try:
    from gpu_physics import update_bullets_batch, check_collisions_batch, CUDA_AVAILABLE  # pyright: ignore[reportMissingImports]
    USE_GPU = CUDA_AVAILABLE
    if not USE_GPU:
        pass  # gpu_physics logs or stays quiet; game uses CPU path when USE_GPU is False
except Exception as e:
    USE_GPU = False
    update_bullets_batch = None
    check_collisions_batch = None
    logging.getLogger(__name__).debug("gpu_physics unavailable (%s), using CPU physics.", e)

from telemetry.event_bus_handlers import register_telemetry_event_handlers
from telemetry import (
    Telemetry,
    NoOpTelemetry,
    EnemySpawnEvent,
    PlayerPosEvent,
    ShotEvent,
    EnemyHitEvent,
    PlayerDamageEvent,
    PlayerDeathEvent,
    WaveEvent,
    WaveEnemyTypeEvent,
    EnemyPositionEvent,
    PlayerVelocityEvent,
    BulletMetadataEvent,
    PlayerActionEvent,
    ZoneVisitEvent,
    FriendlyAISpawnEvent,
    FriendlyAIPositionEvent,
    FriendlyAIShotEvent,
    FriendlyAIDeathEvent,
)

# -----------------------------------------------------------------------------
# Internal: constants and config
# -----------------------------------------------------------------------------
from constants import (
    AIM_ARROWS,
    AIM_MOUSE,
    DIFFICULTY_NORMAL,
    ENEMY_PROJECTILE_DAMAGE,
    ENEMY_PROJECTILE_SIZE,
    ENEMY_PROJECTILES_COLOR,
    HIGH_SCORES_DB,
    LIVES_START,
    PLAYER_CLASS_BALANCED,
    PICKUP_SPAWN_INTERVAL,
    SCORE_BASE_POINTS,
    SCORE_TIME_MULTIPLIER,
    SCORE_WAVE_MULTIPLIER,
    STATE_ENDURANCE,
    STATE_GAME_OVER,
    STATE_HIGH_SCORES,
    STATE_LOAD_GAME,
    STATE_MENU,
    STATE_NAME_INPUT,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_QUICK_LAUNCH,
    STATE_SAVE_GAME,
    STATE_TELEMETRY_VIEWER,
    STATE_TITLE,
    STATE_VICTORY,
    UNLOCKED_WEAPON_DAMAGE_MULT,
    ally_drop_cooldown,
    boost_drain_per_s,
    boost_meter_max,
    boost_regen_per_s,
    boost_speed_mult,
    character_profile_options,
    custom_profile_stats_keys,
    custom_profile_stats_list,
    difficulty_multipliers,
    difficulty_options,
    fire_rate_buff_duration,
    fire_rate_mult,
    grenade_cooldown,
    grenade_damage,
    jump_cooldown,
    laser_cooldown,
    laser_damage,
    laser_length,
    level_themes,
    missile_cooldown,
    missile_damage,
    overshield_max,
    overshield_recharge_cooldown,
    pause_options,
    player_bullet_shapes,
    player_bullet_size,
    player_bullet_speed,
    player_bullets_color,
    player_class_options,
    player_class_stats,
    shield_duration,
    shield_recharge_cooldown,
    slow_speed_mult,
    weapon_selection_options,
)

from config_enemies import (
    ENEMY_TEMPLATES,
    BOSS_TEMPLATE,
    BASE_ENEMIES_PER_WAVE,
    MAX_ENEMIES_PER_WAVE,
    ENEMY_SPAWN_MULTIPLIER,
    ENEMY_HP_SCALE_MULTIPLIER,
    ENEMY_SPEED_SCALE_MULTIPLIER,
    ENEMY_FIRE_RATE_MULTIPLIER,
    ENEMY_HP_CAP,
    QUEEN_FIXED_HP,
    QUEEN_SPEED_MULTIPLIER,
    FRIENDLY_AI_TEMPLATES,
)
from config_weapons import (
    WEAPON_CONFIGS,
    WEAPON_NAMES,
    WEAPON_DISPLAY_COLORS,
    WEAPON_UNLOCK_ORDER,
)
from rendering import RenderContext, draw_centered_text
from asset_manager import get_font
from enemies import (
    find_nearest_threat,
    make_enemy_from_template,
)
from allies import (
    find_nearest_enemy,
    make_friendly_from_template,
    spawn_friendly_ai,
    spawn_friendly_projectile,
    update_friendly_ai,
)
from state import GameState
from context import AppContext
from event_bus import EventBus, GameEvent
from config import GameConfig, apply_safe_mode, log_startup_config
from config.projectile_defs import get_projectile_def
# -----------------------------------------------------------------------------
# SCENE MIGRATION STATUS: COMPLETE
# -----------------------------------------------------------------------------
# INVARIANT: All game states must have a corresponding Scene on the stack.
# The scene stack is the authoritative source of truth for the current state.
# If a state lacks a scene, it is treated as a bug (assertion failure in debug).
#
# Input flows through the scene stack via handle_scene_events().
# States are synchronized: game_state.current_screen reflects scene_stack.current().state_id().
#
# The screens/ package still contains render/input logic, but it's wrapped
# by scene classes (e.g., PauseScene wraps screens.pause).
#
# Future cleanup opportunities:
# - Merge screens/*.py logic directly into scenes/*.py
# - Remove screen_ctx dict (replace with structured context objects)
# - Remove SCREEN_HANDLERS from screens/__init__.py (currently unused)
# -----------------------------------------------------------------------------
from screens.gameplay import render as gameplay_render
from rendering_shaders import render_gameplay_with_optional_shaders
from scenes import SceneStack, GameplayScene, PauseScene, HighScoreScene, NameInputScene, ShaderTestScene, TitleScene, OptionsScene, QuickLaunchScene
from scenes.game_over import GameOverScene
from scenes.victory import VictoryScene
from scenes.save_game import SaveGameScene
from scenes.load_game import LoadGameScene
from scenes.transitions import SceneTransition, KIND_NONE, KIND_PUSH, KIND_POP, KIND_REPLACE, KIND_QUIT_GAME, apply_scene_transition
# apply_menu_effects, apply_pause_effects now in engine/render_loop.py
from shader_effects import get_menu_shader_stack, get_pause_shader_stack, get_gameplay_shader_stack
from simulation_systems import SIMULATION_SYSTEMS
from systems.spawn_system import start_wave as spawn_system_start_wave
from engine.run_manager import (
    start_new_run,
    restart_current_wave,
    restart_from_wave_one,
    replay as run_replay,
    try_again as run_try_again,
    load_game as run_load_game,
)
from systems.input_system import handle_gameplay_input
from systems.telemetry_system import update_telemetry
from systems.audio_system import init_mixer, sync_from_config, play_sfx, play_music, stop_music
from systems.projectile_spawning import (
    spawn_player_bullet_and_log,
    spawn_enemy_projectile,
    spawn_enemy_projectile_predictive,
    spawn_boss_projectile,
    spawn_ally_missile,
)
from pickups import apply_pickup_effect
from systems.collision_movement import move_player_with_push, move_enemy_with_push
try:
    from telemetry.perf import record_frame as _perf_record_frame
except ImportError:
    _perf_record_frame = lambda _dt: None
from controls_io import _key_name_to_code, load_controls
from physics_loader import resolve_physics
from geometry_utils import (
    clamp_rect_to_screen,
    vec_toward,
    line_rect_intersection,
    can_move_rect,
    rect_offscreen,
    filter_blocks_too_close_to_player,
    set_screen_dimensions,
)
from level_utils import filter_blocks_no_overlap, clone_enemies_from_templates
from level_builder import (
    build_level_geometry,
    place_teleporter_pads,
    generate_wave_beam_points,
    check_wave_beam_collision,
)
from hazards import hazard_obstacles, check_point_in_hazard
from level_state import LevelState

# -----------------------------------------------------------------------------
# Default display dimensions - used for pygame initialization before detecting
# actual screen size. _init_pygame() updates these from pygame.display.Info().
# All runtime code should use ctx.width/ctx.height (world dimensions) or 
# ctx.display_width/ctx.display_height (screen dimensions).
# -----------------------------------------------------------------------------
WIDTH = 1920
HEIGHT = 1080

# ----------------------------
# Rendering cache for performance optimization
# ----------------------------
# Wall texture, HUD text, health bar, and trapezoid/triangle caches are in rendering.py


def _init_pygame_and_mixer() -> None:
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


def _create_window_and_clock() -> tuple[pygame.Surface, pygame.time.Clock, int, int]:
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
    font = get_font("main", 28)
    big_font = get_font("main", 56)
    small_font = get_font("main", 20)
    
    return screen, clock, WIDTH, HEIGHT


def _build_app_context(screen: pygame.Surface, clock: pygame.time.Clock, display_width: int, display_height: int, using_c_physics: bool) -> AppContext:
    """Build AppContext with config, controls, and resources."""
    # EventBus is imported at module level
    controls = load_controls()
    
    cfg = GameConfig(
        difficulty=DIFFICULTY_NORMAL,
        aim_mode=AIM_MOUSE,
        aiming_mechanic="mouse",
        player_class=PLAYER_CLASS_BALANCED,
        enable_telemetry=False,
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
    # World is larger than display, rendered then scaled down
    world_scale = cfg.world_scale
    world_width = int(display_width * world_scale)
    world_height = int(display_height * world_scale)
    
    # Create world surface for rendering (larger than display)
    # Use convert() for hardware-accelerated blitting
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
    camera = create_camera(
        display_width=display_width,
        display_height=display_height,
        world_width=world_width,
        world_height=world_height,
        smoothing=8.0,  # Smooth camera follow
    )
    print(f"Camera initialized: viewport {display_width}x{display_height}, world {world_width}x{world_height}")
    
    return ctx

def _build_initial_game_state(ctx: AppContext) -> GameState:
    """Create and initialize GameState with level geometry and context."""
    game_state = GameState()
    game_state.player_rect = pygame.Rect((ctx.width - 28) // 2, (ctx.height - 28) // 2, 28, 28)
    game_state.current_screen = STATE_TITLE
    game_state.run_started_at = ctx.run_started_at

    # Initialize pygame mouse visibility
    pygame.mouse.set_visible(True)

    # Build level geometry and store in game_state.level
    level = build_level_geometry(ctx.width, ctx.height)
    level.destructible_blocks = filter_blocks_no_overlap(level.destructible_blocks, [level.moveable_blocks, level.giant_blocks, level.super_giant_blocks, level.trapezoid_blocks, level.triangle_blocks], game_state.player_rect)
    level.moveable_blocks = filter_blocks_no_overlap(level.moveable_blocks, [level.destructible_blocks, level.giant_blocks, level.super_giant_blocks, level.trapezoid_blocks, level.triangle_blocks], game_state.player_rect)
    level.giant_blocks = filter_blocks_no_overlap(level.giant_blocks, [level.destructible_blocks, level.moveable_blocks, level.super_giant_blocks, level.trapezoid_blocks, level.triangle_blocks], game_state.player_rect)
    level.super_giant_blocks = filter_blocks_no_overlap(level.super_giant_blocks, [level.destructible_blocks, level.moveable_blocks, level.giant_blocks, level.trapezoid_blocks, level.triangle_blocks], game_state.player_rect)
    game_state.level = level
    game_state.teleporter_pads = place_teleporter_pads(level, ctx.width, ctx.height)
    
    # Level context for movement_system and collision_system (callables and data)
    from level_utils import make_level_context
    game_state.level_context = make_level_context(ctx, game_state)
    game_state.run_id = None  # Will be set when game starts
    return game_state


def _setup_initial_resources() -> None:
    """Initialize high scores database, copy music file if needed, and play initial music."""
    init_high_scores_db()
    
    # Ensure in-game.ogg is available: copy from project root to assets/music/ if missing
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
    
    # Main menu (title + pre-game options) uses ambient2 music
    play_music("ambient2", loop=True)


def _prompt_shader_mode(ctx: AppContext, show_prompt: bool = False) -> None:
    """Initialize shader mode settings.
    
    Args:
        ctx: Application context
        show_prompt: If True, show the interactive Y/N prompt. If False, use defaults.
                     The prompt can be re-enabled later if needed.
    """
    try:
        import moderngl  # noqa: F401  # type: ignore[import-untyped]
        moderngl_available = True
    except ImportError:
        print("moderngl not available; disabling shader mode.")
        ctx.config.use_shaders = False
        moderngl_available = False
    
    if moderngl_available and show_prompt:
        # Interactive prompt (disabled by default)
        prompt_done = False
        prompt_clock = pygame.time.Clock()
        # Use display dimensions for the prompt (not world dimensions)
        display_w = getattr(ctx, 'display_width', ctx.width)
        display_h = getattr(ctx, 'display_height', ctx.height)
        while not prompt_done:
            prompt_clock.tick(60)  # Limit to 60 FPS for the prompt
            ctx.screen.fill((30, 30, 40))
            draw_centered_text(ctx.screen, ctx.font, ctx.big_font, display_w, "Enable GPU shaders?", display_h // 2 - 50, color=(220, 220, 220), use_big=True)
            draw_centered_text(ctx.screen, ctx.font, ctx.big_font, display_w, "(Y)es  /  (N)o", display_h // 2 + 20, (180, 180, 180))
            pygame.display.flip()
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    prompt_done = True
                    ctx.config.use_shaders = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_y:
                        ctx.config.use_shaders = True
                        ctx.config.use_gpu_shader_pipeline = True  # Enable GPU particle effects
                        # CPU effects disabled by default for performance
                        # Enable via pause menu Shader Options if desired
                        ctx.config.enable_gameplay_shaders = False
                        ctx.config.enable_pause_shaders = True  # Pause effects are lightweight
                        ctx.config.pause_shader_profile = "pause_dim_vignette"
                        prompt_done = True
                    elif e.key == pygame.K_n:
                        ctx.config.use_shaders = False
                        ctx.config.use_gpu_shader_pipeline = False
                        ctx.config.enable_gameplay_shaders = False
                        ctx.config.enable_pause_shaders = False
                        prompt_done = True
    elif moderngl_available:
        # Default: shaders disabled at startup, can be enabled via pause menu Shader Options
        ctx.config.use_shaders = False
        ctx.config.use_gpu_shader_pipeline = False
        ctx.config.enable_gameplay_shaders = False
        ctx.config.enable_pause_shaders = False
    
    # Log shader configuration (only if enabled)
    if ctx.config.use_shaders:
        print("Shader mode: ON")
    if ctx.config.use_gpu_shader_pipeline:
        print("GPU particle effects: ENABLED (shot/rocket/bomb bursts)")
    if ctx.config.enable_pause_shaders:
        print(f"Pause effects: ENABLED (profile: {ctx.config.pause_shader_profile})")
    if ctx.config.enable_gameplay_shaders:
        print(f"CPU gameplay effects: ENABLED (profile: {ctx.config.gameplay_shader_profile})")


def _build_scene_stack() -> SceneStack:
    """Create and initialize scene stack with TitleScene."""
    scene_stack = SceneStack()
    scene_stack.push(TitleScene())
    return scene_stack


def _build_loop_params(target_fps: int = 144) -> tuple[int, float, int]:
    """Return (FPS, FIXED_DT, MAX_SIMULATION_STEPS).
    
    Args:
        target_fps: Target frame rate. 0 means uncapped.
    """
    FPS = target_fps if target_fps > 0 else 0  # 0 = uncapped
    FIXED_DT = 1.0 / 60.0  # Physics runs at fixed 60Hz regardless of display FPS
    MAX_SIMULATION_STEPS = 8  # Increased to handle higher frame rates
    return FPS, FIXED_DT, MAX_SIMULATION_STEPS


def _create_app():
    """Build ctx, game_state, scene_stack and loop invariants. Used by GameApp."""
    # Check for --safe-mode CLI flag or environment variable
    safe_mode = "--safe-mode" in sys.argv or os.environ.get("GAME_SAFE_MODE", "").strip() == "1"
    
    # Resolve physics backend before any geometry/physics use
    force_python = "--python-physics" in sys.argv or os.environ.get("USE_PYTHON_PHYSICS", "").strip() == "1"
    _physics_impl, using_c_physics = resolve_physics(force_python=force_python)

    _init_pygame_and_mixer()
    screen, clock, width, height = _create_window_and_clock()
    ctx = _build_app_context(screen, clock, width, height, using_c_physics)
    
    # Apply safe mode if requested (disables GPU, CUDA, telemetry)
    if safe_mode:
        ctx.config.safe_mode = True
        apply_safe_mode(ctx.config)
    
    # Log startup configuration summary
    log_startup_config(ctx.config)
    
    game_state = _build_initial_game_state(ctx)
    _setup_initial_resources()
    _prompt_shader_mode(ctx)

    # Hook telemetry handlers into EventBus
    register_telemetry_event_handlers(ctx.event_bus, ctx, game_state)

    # Get target FPS from config (default 144)
    target_fps = getattr(ctx.config, 'target_fps', 144)
    FPS, FIXED_DT, MAX_SIMULATION_STEPS = _build_loop_params(target_fps)
    
    def _update_simulation(sim_dt: float, gs: GameState, app_ctx: AppContext) -> None:
        """Run one fixed timestep of gameplay (timers, movement, collision, spawn, AI)."""
        for system in SIMULATION_SYSTEMS:
            system(gs, sim_dt, app_ctx)

    scene_stack = _build_scene_stack()
    
    class _AppRes:
        pass
    r = _AppRes()
    r.ctx = ctx
    r.game_state = game_state
    r.scene_stack = scene_stack
    r.fps = FPS
    r.fixed_dt = FIXED_DT
    r.max_sim_steps = MAX_SIMULATION_STEPS
    r.update_simulation = _update_simulation
    r.simulation_accumulator = 0.0
    return r


def _print_active_shader_profiles(config) -> None:
    """Debug-only: print currently active shader profile names and stack lengths. Does not change config."""
    if config is None:
        return
    try:
        menu = get_menu_shader_stack(config)
        pause = get_pause_shader_stack(config)
        gameplay = get_gameplay_shader_stack(config)
        mp = getattr(config, "menu_shader_profile", "none")
        pp = getattr(config, "pause_shader_profile", "none")
        gp = getattr(config, "gameplay_shader_profile", "none")
        print(f"[Shader profiles] menu={mp} (len={len(menu)}) pause={pp} (len={len(pause)}) gameplay={gp} (len={len(gameplay)})")
    except Exception as e:
        print(f"[Shader profiles] could not report: {e}")


def _get_current_scene(scene_stack: SceneStack):
    """Return the current scene from the stack, or None if empty."""
    return scene_stack.current()


# _get_current_state imported from engine.render_loop

# Scene transition logic is now in scenes/transitions.py (apply_scene_transition)


# -----------------------------------------------------------------------------
# EVENT POLLING AND INPUT DISPATCH (delegated to engine/input_loop)
# -----------------------------------------------------------------------------
from engine.input_loop import (
    poll_events as _engine_poll_events,
    handle_global_events as _engine_handle_global_events,
    handle_scene_events as _engine_handle_scene_events,
    handle_debug_keys as _engine_handle_debug_keys,
)
from engine.render_loop import (
    get_current_state as _get_current_state,
    render_current_scene as _render_current_scene,
)


def _poll_events() -> list:
    """Poll pygame events and return them. Delegates to engine.input_loop."""
    return _engine_poll_events()


def handle_global_events(events: list, ctx: AppContext, game_state: GameState, ui_state, scene_stack: SceneStack, screen_ctx: dict) -> bool:
    """Handle global events (QUIT). Delegates to engine.input_loop."""
    return _engine_handle_global_events(events)


def handle_scene_events(events: list, ctx: AppContext, game_state: GameState, ui_state, scene_stack: SceneStack, screen_ctx: dict, previous_game_state: str | None) -> SceneTransition | None:
    """Delegate events to the active scene. Delegates to engine.input_loop."""
    return _engine_handle_scene_events(events, game_state, scene_stack, screen_ctx)


def handle_debug_keys(events: list, ctx: AppContext) -> None:
    """Handle debug keys (F3). Delegates to engine.input_loop."""
    _engine_handle_debug_keys(events, ctx.config)


# -----------------------------------------------------------------------------
# EVENT HANDLING - _handle_events is the coordinator
# Core input logic is in engine/input_loop.py. This file provides thin wrappers
# and the coordinator function that processes transitions and updates game state.
# -----------------------------------------------------------------------------

def _handle_events(
    events: list,
    ctx: AppContext,
    game_state: GameState,
    scene_stack: SceneStack,
    screen_ctx: dict,
    previous_game_state: str | None,
    pause_selected: int,
    controls_selected: int,
    controls_rebinding: bool,
) -> tuple[bool, str | None, int, int, bool]:
    """
    Handle all input events. Returns (running, previous_game_state, pause_selected, controls_selected, controls_rebinding).
    
    This function is the COORDINATOR for input handling. It delegates to:
    1. handle_global_events: Handles truly global events (QUIT, etc.)
    2. handle_scene_events: Delegates to the scene system
    3. handle_debug_keys: Handles debug shortcuts (F3 for shader profiles)
    
    All screen states are now represented as scenes. Input flows through the scene stack.
    
    Future: Move the helper functions into a dedicated input routing module and keep this
    function as a thin coordinator in game.py.
    """
    # Step 1: Handle global events (QUIT, etc.)
    running = handle_global_events(events, ctx, game_state, game_state.ui, scene_stack, screen_ctx)
    if not running:
        return False, previous_game_state, pause_selected, controls_selected, controls_rebinding
    
    # Step 2: Try scene-driven input handling
    handled_by_screen = False
    scene_result = None
    current_scene = _get_current_scene(scene_stack)
    current_state = _get_current_state(scene_stack) or game_state.current_screen
    
    transition = handle_scene_events(events, ctx, game_state, game_state.ui, scene_stack, screen_ctx, previous_game_state)
    
    if transition is not None:
        # Get the result from handle_input to check for flags like start_game, try_again, load_game, restart_to_wave1
        # handle_input_transition calls handle_input internally and stores result in _last_input_result.
        # We retrieve that stored result to avoid calling handle_input twice (which would process events twice).
        if current_state in ("SHADER_SETTINGS", STATE_GAME_OVER, STATE_SAVE_GAME, STATE_LOAD_GAME, STATE_TELEMETRY_VIEWER, STATE_QUICK_LAUNCH, STATE_MENU, STATE_PAUSED):
            scene_result = getattr(current_scene, "_last_input_result", None) if current_scene else None
        
        if transition.kind != KIND_NONE:
            should_quit = apply_scene_transition(transition, scene_stack, game_state)
            if should_quit:
                return False, previous_game_state, pause_selected, controls_selected, controls_rebinding
            handled_by_screen = True
        else:
            # Transition is NONE, but handle_input was called (config changes applied)
            # For PAUSED and SHADER_SETTINGS, the input was handled, so mark as handled
            if current_state in (STATE_MENU, STATE_QUICK_LAUNCH):
                handled_by_screen = False  # Let fallback process start_game
            elif current_state == "SHADER_SETTINGS":
                # Check if start_game was requested from shader settings
                if scene_result and scene_result.get("start_game"):
                    handled_by_screen = False  # Let fallback process start_game
                else:
                    handled_by_screen = True  # Scene handled its own input
            elif current_state == STATE_PAUSED:
                # Check if restart was requested - needs fallback processing
                if scene_result and (scene_result.get("restart") or scene_result.get("restart_to_wave1")):
                    handled_by_screen = False  # Let fallback process restart
                else:
                    handled_by_screen = True  # Scene handled its own input
            elif current_state in (STATE_HIGH_SCORES, STATE_NAME_INPUT, "SHADER_TEST", STATE_TITLE, STATE_TELEMETRY_VIEWER):
                handled_by_screen = True  # Scene handled its own input
            elif current_state in (STATE_GAME_OVER, STATE_SAVE_GAME, STATE_LOAD_GAME):
                # These scenes return SceneTransition.none() for actions like "try_again" or "load_game"
                # that need to be processed by the fallback handler, so don't mark as handled
                handled_by_screen = False
    
    # Fallback to old input handling if scene path didn't handle it
    current_state = _get_current_state(scene_stack) or game_state.current_screen
    if not handled_by_screen and current_state in (STATE_PAUSED, STATE_HIGH_SCORES, STATE_NAME_INPUT, "SHADER_TEST", "SHADER_SETTINGS", STATE_TITLE, STATE_MENU, STATE_QUICK_LAUNCH, STATE_GAME_OVER, STATE_VICTORY, STATE_SAVE_GAME, STATE_LOAD_GAME, STATE_TELEMETRY_VIEWER):
        # Use scene_result if we already got it, otherwise get it now
        if scene_result is not None:
            result = scene_result
        elif current_scene:
            result = current_scene.handle_input(events, game_state, screen_ctx)
        else:
            # INVARIANT: All states must have a scene on the stack.
            # If we reach here, it's a bug - the scene stack should always have the appropriate scene.
            logging.getLogger(__name__).error(
                f"No scene on stack for state '{current_state}'. This is a bug - all states should have scenes."
            )
            assert False, f"Missing scene for state '{current_state}'. Scene migration is incomplete."
        
        if result.get("quit"):
            return False, previous_game_state, pause_selected, controls_selected, controls_rebinding
        if result.get("pop"):
            scene_stack.pop()
            current_state = _get_current_state(scene_stack) or STATE_PLAYING
            game_state.current_screen = current_state
        # Handle restart/replay/wave1 restart - delegate to RunManager
        if result.get("restart") or result.get("restart_to_wave1") or result.get("replay"):
            if result.get("restart"):
                restart_current_wave(ctx, game_state)
            elif result.get("restart_to_wave1"):
                restart_from_wave_one(ctx, game_state, scene_stack)
            elif result.get("replay"):
                run_replay(ctx, game_state, scene_stack)
        
        # Handle start_game from menu - delegate to RunManager
        if result.get("start_game") and result.get("screen") == STATE_PLAYING:
            endurance_mode = game_state.ui.endurance_mode_selected == 1
            start_new_run(ctx, game_state, scene_stack, endurance_mode=endurance_mode)
        
        current_state = _get_current_state(scene_stack) or game_state.current_screen
        # Sync pause_selected from game_state (handler may have updated it)
        if current_state == STATE_PAUSED:
            pause_selected = game_state.ui.pause_selected
        
        # Handle "try_again" from game over screen - delegate to RunManager
        if result.get("try_again"):
            run_try_again(ctx, game_state, scene_stack)
        # Handle "load_game" from load game screen - delegate to RunManager
        elif result.get("load_game") and result.get("load_slot"):
            run_load_game(ctx, game_state, scene_stack, result["load_slot"])
        elif result.get("screen") is not None and not result.get("start_game"):
            new_screen = result["screen"]
            game_state.current_screen = new_screen
            # Play ambient music for menu screens
            if new_screen in (STATE_MENU, STATE_QUICK_LAUNCH):
                play_music("ambient2", loop=True)
            # Determine if we should clear or just push
            clear_first = new_screen in (STATE_MENU, STATE_QUICK_LAUNCH, STATE_TITLE, STATE_GAME_OVER, STATE_VICTORY)
            pop_if_paused = new_screen in (STATE_PLAYING, STATE_ENDURANCE) and current_state == STATE_PAUSED
            if pop_if_paused:
                scene_stack.pop()
            else:
                if clear_first:
                    scene_stack.clear()
                from scenes.transitions import create_scene_for_state
                scene = create_scene_for_state(new_screen)
                if scene:
                    scene_stack.push(scene)
        handled_by_screen = True
    
    # Step 4: Handle debug keys (F3 for shader profile info)
    handle_debug_keys(events, ctx)
    
    return True, previous_game_state, pause_selected, controls_selected, controls_rebinding


def _step_simulation(
    simulation_accumulator: float,
    dt: float,
    FIXED_DT: float,
    MAX_SIMULATION_STEPS: int,
    _update_simulation,
    ctx: AppContext,
    game_state: GameState,
    scene_stack: SceneStack,
    screen_ctx: dict,
) -> tuple[float, bool]:
    """Run fixed-step simulation updates. Returns (new_accumulator, should_quit)."""
    simulation_accumulator += dt
    steps = 0
    should_quit = False
    while simulation_accumulator >= FIXED_DT and steps < MAX_SIMULATION_STEPS:
        # Try scene-driven update first
        current_scene = _get_current_scene(scene_stack)
        if current_scene is not None:
            try:
                transition = current_scene.update_transition(FIXED_DT, game_state, screen_ctx)
                if transition.kind != KIND_NONE:
                    should_quit = apply_scene_transition(transition, scene_stack, game_state)
                    if should_quit:
                        break
            except AttributeError:
                # Scene doesn't have update_transition, fall through to old path
                pass
        
        # Run simulation update (for gameplay scenes)
        _update_simulation(FIXED_DT, game_state, ctx)
        simulation_accumulator -= FIXED_DT
        steps += 1
    return simulation_accumulator, should_quit


# _render_current_scene imported from engine.render_loop


def _handle_exit(ctx: AppContext, game_state: GameState) -> None:
    """Handle cleanup and telemetry when exiting the game."""
    run_ended_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if ctx.config.enable_telemetry and ctx.telemetry_client:
        ctx.telemetry_client.end_run(
            ended_at_iso=run_ended_at,
            seconds_survived=game_state.run_time,
            player_hp_end=game_state.player_hp,
            shots_fired=game_state.shots_fired,
            hits=game_state.hits,
            damage_taken=game_state.damage_taken,
            damage_dealt=game_state.damage_dealt,
            enemies_spawned=game_state.enemies_spawned,
            enemies_killed=game_state.enemies_killed,
            deaths=game_state.deaths,
            max_wave=game_state.wave_number,
        )
        ctx.telemetry_client.close()
        print(f"Saved run_id={game_state.run_id} to game_telemetry.db")
    pygame.quit()


def _run_loop(app):
    """
    DEPRECATED: This function is now a thin wrapper around GameApp.run().
    The main loop logic has been moved into GameApp methods (process_events, update, render, run).
    This wrapper is kept for backward compatibility but will be removed in the future.
    """
    # GameApp.run() now contains the full loop logic
    app.run()


def main():
    """Thin entrypoint: create GameApp and run the main loop."""
    from game_app import GameApp
    GameApp().run()


# -----------------------------------------------------------------------------
# LEGACY MODULE-LEVEL STATE (MINIMAL)
# All game state is in GameState. These are kept only for external compatibility.
# New code should use state.xxx instead.
# -----------------------------------------------------------------------------
controls = {}  # Initialized in _create_app() after pygame.init()

# Weapon key mapping (uses pygame constants)
WEAPON_KEY_MAP = {
    pygame.K_1: "triple",
    pygame.K_2: "laser",
    pygame.K_3: "giant",
}

# Lowercase aliases for constants (external compatibility)
enemy_projectile_size = ENEMY_PROJECTILE_SIZE
enemy_projectile_damage = ENEMY_PROJECTILE_DAMAGE
enemy_projectiles_color = ENEMY_PROJECTILES_COLOR

# Template aliases (external compatibility)
enemy_templates = ENEMY_TEMPLATES
boss_template = BOSS_TEMPLATE
friendly_ai_templates = FRIENDLY_AI_TEMPLATES

# -----------------------------------------------------------------------------
# RE-EXPORTS (functions that other modules import from game.py)
# -----------------------------------------------------------------------------
from game_utils import init_high_scores_db, get_high_scores, save_high_score, is_high_score, calculate_kill_score
from systems.spawn_helpers import random_spawn_position, spawn_pickup, spawn_weapon_in_center, spawn_weapon_drop, create_pickup_collection_effect
from systems.enemy_death import kill_enemy, reset_after_death


if __name__ == "__main__":
    main()
