"""
Main game entry point. Runs the game loop, handles menus, gameplay, and screen transitions.
All mutable game state lives in GameState; app-level resources and config in AppContext.
Level geometry in state.level (LevelState). Gameplay input via handle_gameplay_input;
per-frame logic in _update_simulation (movement/collision/spawn/ai). Overlay screens use
SCREEN_HANDLERS and RenderContext.from_app_ctx(ctx).

# -----------------------------------------------------------------------------
# Screen/state mapping (temporary documentation during refactor)
# -----------------------------------------------------------------------------
# - Global state constants (from constants.py): STATE_TITLE, STATE_MENU, STATE_PLAYING,
#   STATE_PAUSED, STATE_ENDURANCE, STATE_GAME_OVER, STATE_NAME_INPUT, STATE_HIGH_SCORES,
#   STATE_VICTORY, STATE_CONTINUE, STATE_CONTROLS, STATE_MODS, STATE_WAVE_BUILDER.
#   SHADER_TEST is not in constants; it is the string "SHADER_TEST" (see scenes/shader_test.SHADER_TEST_STATE_ID).
#
# - GameState.current_screen (str): canonical "what screen we are on". Initialized to STATE_TITLE
#   in _create_app(); the loop reads it at frame start and writes it back at frame end.
#   GameState.previous_screen (str|None): used for pause/unpause to restore PLAYING or ENDURANCE.
#
# - Module-level locals in _run_loop (not globals): each iteration sets
#   state = game_state.current_screen and previous_game_state = game_state.previous_screen,
#   then event/render logic may change state/previous_game_state; at end of frame they are
#   written back to game_state.current_screen and game_state.previous_screen. So the
#   in-loop "state" is the effective current screen for that frame.
#
# - SceneStack and scenes: scene_stack is built in _create_app() and stored on app.
#   SCENE_STATES = (STATE_PLAYING, STATE_ENDURANCE, STATE_PAUSED, STATE_HIGH_SCORES,
#   STATE_NAME_INPUT, STATE_TITLE, STATE_MENU). _sync_scene_stack(stk, s, gs) keeps the
#   stack in sync with gs.current_screen (s) when s in SCENE_STATES:
#     - STATE_TITLE: stack becomes [TitleScene]
#     - STATE_MENU: stack becomes [TitleScene, OptionsScene] or [OptionsScene] as needed
#     - STATE_PLAYING / STATE_ENDURANCE: stack top is GameplayScene(s); may clear and push
#     - STATE_PAUSED: ensures [..., GameplayScene(...), PauseScene]
#     - STATE_NAME_INPUT: ensures [..., GameplayScene(PLAYING), NameInputScene]
#     - STATE_HIGH_SCORES: ensures [..., GameplayScene(PLAYING), HighScoreScene]
#   SHADER_TEST is not in SCENE_STATES; _sync_scene_stack does nothing for it. ShaderTestScene
#   is never pushed by _sync_scene_stack in the main loop (only by tests or other entry points).
#
# - Scene classes (from scenes/): TitleScene (state_id STATE_TITLE), OptionsScene (STATE_MENU),
#   GameplayScene(state_id passed in: STATE_PLAYING or STATE_ENDURANCE), PauseScene (STATE_PAUSED),
#   NameInputScene (STATE_NAME_INPUT), HighScoreScene (STATE_HIGH_SCORES), ShaderTestScene
#   (state_id "SHADER_TEST"). Pushed/popped by _sync_scene_stack and by loop logic (e.g. pop on
#   result["pop"], push GameplayScene on start_game, scene_stack.clear() + push on restart/menu).
#
# - When state in (STATE_PAUSED, STATE_HIGH_SCORES, STATE_NAME_INPUT, "SHADER_TEST", STATE_TITLE,
#   STATE_MENU), input is delegated to scene_stack.current().handle_input or, if no current scene,
#   to SCREEN_HANDLERS[state]["handle_events"]. SCREEN_HANDLERS (screens/) has PAUSED, HIGH_SCORES,
#   NAME_INPUT only; TITLE and MENU have no handler (scene path only). Render uses
#   current_scene.render() or SCREEN_HANDLERS[state]["render"] for those same states.
#
# - STATE_GAME_OVER, STATE_VICTORY, STATE_CONTROLS: no scene stack sync, no SCREEN_HANDLERS entry;
#   they are handled in keyboard/event logic and have placeholder or minimal render branches.
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
    MOUSE_BUTTON_RIGHT,
    PLAYER_CLASS_BALANCED,
    PICKUP_SPAWN_INTERVAL,
    SCORE_BASE_POINTS,
    SCORE_TIME_MULTIPLIER,
    SCORE_WAVE_MULTIPLIER,
    STATE_CONTINUE,
    STATE_CONTROLS,
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
    STATE_TITLE,
    STATE_VICTORY,
    UNLOCKED_WEAPON_DAMAGE_MULT,
    ally_drop_cooldown,
    boost_drain_per_s,
    boost_meter_max,
    boost_regen_per_s,
    boost_speed_mult,
    character_profile_options,
    controls_actions,
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
from config import GameConfig
from config.projectile_defs import get_projectile_def
# -----------------------------------------------------------------------------
# LEGACY SCREEN HANDLER MIGRATION PATH:
# -----------------------------------------------------------------------------
# TODO: Remove SCREEN_HANDLERS import once all screens are fully migrated to scenes.
# 
# Migration plan:
# 1. All game states should eventually have corresponding Scene classes in scenes/.
# 2. Once every state (PAUSED, HIGH_SCORES, NAME_INPUT, etc.) is fully represented 
#    as a scene with handle_input_transition() and render():
#    - Remove SCREEN_HANDLERS dictionary from screens/__init__.py
#    - Remove handle_legacy_state_events() from game.py
#    - Remove screen_ctx dict (replaced by AppContext/RenderContext)
# 3. _handle_events becomes a thin coordinator calling only handle_global_events 
#    and handle_scene_events.
#
# Current status: SCREEN_HANDLERS is no longer imported (scenes are primary).
# Legacy state handling still exists in handle_legacy_state_events for edge cases.
# from screens import SCREEN_HANDLERS  # Deprecated - use scenes instead
# -----------------------------------------------------------------------------
from screens.gameplay import render as gameplay_render
from rendering_shaders import render_gameplay_with_optional_shaders, render_gameplay_frame_to_surface
from scenes import SceneStack, GameplayScene, PauseScene, HighScoreScene, NameInputScene, ShaderTestScene, TitleScene, OptionsScene, QuickLaunchScene
from scenes.game_over import GameOverScene
from scenes.save_game import SaveGameScene
from scenes.load_game import LoadGameScene
from scenes.transitions import SceneTransition, KIND_NONE, KIND_PUSH, KIND_POP, KIND_REPLACE, KIND_QUIT_GAME
from visual_effects import apply_menu_effects, apply_pause_effects
from shader_effects import get_menu_shader_stack, get_pause_shader_stack, get_gameplay_shader_stack
from simulation_systems import SIMULATION_SYSTEMS
from systems.spawn_system import start_wave as spawn_system_start_wave
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
from controls_io import _key_name_to_code, load_controls, save_controls
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
# TODO: LEGACY PLACEHOLDER DIMENSIONS
# These module-level WIDTH/HEIGHT are placeholder values used only for initial
# geometry definitions (trapezoids, blocks, etc.) before AppContext is created.
# All runtime code should use ctx.width/ctx.height (world dimensions) or 
# ctx.display_width/ctx.display_height (screen dimensions).
# 
# Once build_level_geometry() is moved to level_builder.py and accepts 
# explicit width/height parameters, these placeholders can be removed.
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
    # Use hardware acceleration and double buffering for better performance
    display_flags = pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF
    screen = pygame.display.set_mode((WIDTH, HEIGHT), display_flags)
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
    world_surface = pygame.Surface((world_width, world_height))
    
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
    
    # Level context for movement_system and collision_system (callables and data; avoids circular imports)
    def _make_level_context():
        w, h = ctx.width, ctx.height
        lv = game_state.level

        def _log_player_death(t, px, py, lives_left, wave_num):
            if ctx.config.enable_telemetry and ctx.telemetry_client:
                ctx.telemetry_client.log_player_death(
                    PlayerDeathEvent(t=t, player_x=px, player_y=py, lives_left=lives_left, wave_number=wave_num)
                )

        return {
            "move_player": lambda p, dx, dy: move_player_with_push(p, dx, dy, lv, w, h),
            "move_enemy": lambda s, rect, mx, my: move_enemy_with_push(rect, mx, my, lv, s, w, h),
            "clamp": lambda r: clamp_rect_to_screen(r, w, h),
            "blocks": lv.static_blocks,
            "width": w,
            "height": h,
            "main_area_rect": pygame.Rect(int(w * 0.25), int(h * 0.25), int(w * 0.5), int(h * 0.5)),
            "rect_offscreen": lambda r: r.right < 0 or r.left > w or r.bottom < 0 or r.top > h,
            "vec_toward": vec_toward,
            "update_friendly_ai": lambda s, dt: update_friendly_ai(
                s.friendly_ai, s.enemies, lv.static_blocks, dt,
                find_nearest_enemy, vec_toward,
                lambda rect, mx, my, bl: move_enemy_with_push(rect, mx, my, lv, s, w, h),
                lambda f, t: spawn_friendly_projectile(f, t, s.friendly_projectiles, vec_toward, ctx.telemetry_client, s.run_time),
                state=s,
                player_rect=getattr(s, "player_rect", None),
                spawn_ally_missile_func=lambda f, t, st: spawn_ally_missile(f, t, st),
            ),
            "kill_enemy": lambda e, s: kill_enemy(e, s, w, h, getattr(ctx, "event_bus", None)),
            "destructible_blocks": lv.destructible_blocks,
            "moveable_destructible_blocks": lv.moveable_blocks,
            "giant_blocks": lv.giant_blocks,
            "super_giant_blocks": lv.super_giant_blocks,
            "trapezoid_blocks": lv.trapezoid_blocks,
            "triangle_blocks": lv.triangle_blocks,
            "hazard_obstacles": lv.hazard_obstacles,
            "moving_health_zone": lv.moving_health_zone,
            "teleporter_pads": game_state.teleporter_pads,
            "check_point_in_hazard": check_point_in_hazard,
            "line_rect_intersection": line_rect_intersection,
            "testing_mode": ctx.config.testing_mode,
            "invulnerability_mode": ctx.config.invulnerability_mode,
            "reset_after_death": lambda s: reset_after_death(s, w, h),
            "create_pickup_collection_effect": create_pickup_collection_effect,
            "apply_pickup_effect": lambda pt, s: apply_pickup_effect(pt, s, ctx),
            "enemy_projectile_size": enemy_projectile_size,
            "enemy_projectiles_color": enemy_projectiles_color,
            "missile_damage": missile_damage,
            "find_nearest_threat": find_nearest_threat,
            "spawn_enemy_projectile": lambda e, s: spawn_enemy_projectile(e, s, ctx.telemetry_client, ctx.config.enable_telemetry),
            "spawn_enemy_projectile_predictive": spawn_enemy_projectile_predictive,
            "difficulty": ctx.config.difficulty,
            "random_spawn_position": random_spawn_position,
            "telemetry": ctx.telemetry_client,
            "telemetry_enabled": ctx.config.enable_telemetry,
            "overshield_recharge_cooldown": overshield_recharge_cooldown,
            "ally_drop_cooldown": ally_drop_cooldown,
            "play_sfx": play_sfx,
            "damage_flash_duration": getattr(ctx.config, "damage_flash_duration", 0.12),
            "screen_flash_duration": getattr(ctx.config, "screen_flash_duration", 0.25),
            "screen_flash_max_alpha": getattr(ctx.config, "screen_flash_max_alpha", 100),
            "enable_damage_flash": getattr(ctx.config, "enable_damage_flash", True),
            "enable_screen_flash": getattr(ctx.config, "enable_screen_flash", True),
            "enable_damage_wobble": getattr(ctx.config, "enable_damage_wobble", False),
            "enable_wave_banner": getattr(ctx.config, "enable_wave_banner", True),
            "wave_banner_duration": getattr(ctx.config, "wave_banner_duration", 1.5),
            "base_enemies_per_wave": getattr(ctx.config, "base_enemies_per_wave", 12),
            "enemy_spawn_multiplier": getattr(ctx.config, "enemy_spawn_multiplier", 3.5),
            "log_player_death": _log_player_death,
            "config": ctx.config,
        }
    game_state.level_context = _make_level_context()
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


def _prompt_shader_mode(ctx: AppContext) -> None:
    """Prompt user for GPU shader mode if moderngl is available."""
    try:
        import moderngl  # noqa: F401  # type: ignore[import-untyped]
        moderngl_available = True
    except ImportError:
        print("moderngl not available; disabling shader mode.")
        ctx.config.use_shaders = False
        moderngl_available = False
    
    if moderngl_available:
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
                        prompt_done = True
                    elif e.key == pygame.K_n:
                        ctx.config.use_shaders = False
                        prompt_done = True
    print("Shader mode: ON" if ctx.config.use_shaders else "Shader mode: OFF")


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
    # Resolve physics backend before any geometry/physics use
    force_python = "--python-physics" in sys.argv or os.environ.get("USE_PYTHON_PHYSICS", "").strip() == "1"
    _physics_impl, using_c_physics = resolve_physics(force_python=force_python)

    _init_pygame_and_mixer()
    screen, clock, width, height = _create_window_and_clock()
    ctx = _build_app_context(screen, clock, width, height, using_c_physics)
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


def _get_current_state(scene_stack: SceneStack) -> str | None:
    """Get the current state ID from the top scene in the stack, or None if empty."""
    scene = scene_stack.current()
    if scene is None:
        return None
    return scene.state_id()


def _apply_scene_transition(transition: SceneTransition, scene_stack: SceneStack, ctx, game_state) -> bool:
    """Apply a SceneTransition to the scene stack and game state.
    
    Returns True if the transition should cause the loop to exit (QUIT_GAME).
    For PUSH/REPLACE, scene_name should be a state constant like STATE_PAUSED, STATE_MENU, etc.
    Falls back to old state-machine logic where needed.
    """
    if transition.kind == KIND_NONE:
        return False
    
    if transition.kind == KIND_QUIT_GAME:
        return True  # Signal to exit loop
    
    if transition.kind == KIND_POP:
        scene_stack.pop()
        # Restore previous screen state
        state = game_state.previous_screen or STATE_PLAYING
        game_state.current_screen = state
        return False
    
    if transition.kind == KIND_PUSH:
        scene_name = transition.scene_name
        if scene_name == STATE_PAUSED:
            scene_stack.push(PauseScene())
        elif scene_name == STATE_MENU:
            scene_stack.push(OptionsScene())
        elif scene_name == STATE_QUICK_LAUNCH:
            scene_stack.push(QuickLaunchScene())
        elif scene_name == STATE_TITLE:
            scene_stack.push(TitleScene())
        elif scene_name == STATE_NAME_INPUT:
            scene_stack.push(NameInputScene())
        elif scene_name == STATE_HIGH_SCORES:
            scene_stack.push(HighScoreScene())
        elif scene_name == STATE_GAME_OVER:
            scene_stack.push(GameOverScene())
        elif scene_name == STATE_SAVE_GAME:
            scene_stack.push(SaveGameScene())
        elif scene_name == STATE_LOAD_GAME:
            scene_stack.push(LoadGameScene())
        elif scene_name in (STATE_PLAYING, STATE_ENDURANCE):
            scene_stack.push(GameplayScene(scene_name))
        elif scene_name == "SHADER_TEST":
            scene_stack.push(ShaderTestScene())
        elif scene_name == "SHADER_SETTINGS":
            from scenes.shader_settings import ShaderSettingsScreen
            scene_stack.push(ShaderSettingsScreen())
        # Update current_screen to match the pushed scene
        if scene_name:
            game_state.current_screen = scene_name
        return False
    
    if transition.kind == KIND_REPLACE:
        scene_name = transition.scene_name
        scene_stack.clear()
        if scene_name == STATE_PAUSED:
            scene_stack.push(PauseScene())
        elif scene_name == STATE_MENU:
            scene_stack.push(OptionsScene())
        elif scene_name == STATE_QUICK_LAUNCH:
            scene_stack.push(QuickLaunchScene())
        elif scene_name == STATE_TITLE:
            scene_stack.push(TitleScene())
        elif scene_name == STATE_NAME_INPUT:
            scene_stack.push(NameInputScene())
        elif scene_name == STATE_HIGH_SCORES:
            scene_stack.push(HighScoreScene())
        elif scene_name == STATE_GAME_OVER:
            scene_stack.push(GameOverScene())
        elif scene_name == STATE_SAVE_GAME:
            scene_stack.push(SaveGameScene())
        elif scene_name == STATE_LOAD_GAME:
            scene_stack.push(LoadGameScene())
        elif scene_name in (STATE_PLAYING, STATE_ENDURANCE):
            scene_stack.push(GameplayScene(scene_name))
        elif scene_name == "SHADER_TEST":
            scene_stack.push(ShaderTestScene())
        elif scene_name == "SHADER_SETTINGS":
            from scenes.shader_settings import ShaderSettingsScreen
            scene_stack.push(ShaderSettingsScreen())
        # Update current_screen to match the replaced scene
        if scene_name:
            game_state.current_screen = scene_name
        return False
    
    return False


def _poll_events() -> list:
    """Poll pygame events and return them."""
    return pygame.event.get()


def handle_global_events(events: list, ctx: AppContext, game_state: GameState, ui_state, scene_stack: SceneStack, screen_ctx: dict) -> bool:
    """
    Handle events that apply globally, regardless of which scene is active.
    
    Returns False if the game should stop running (e.g., QUIT event), True otherwise.
    This function is PURELY about "does the game keep running?" and truly global shortcuts.
    
    Future: Move this helper into a dedicated input routing module (e.g. input_handlers.py
    or systems/input_routing.py) and keep _handle_events as a thin coordinator.
    """
    for event in events:
        if event.type == pygame.QUIT:
            return False
    return True


def handle_scene_events(events: list, ctx: AppContext, game_state: GameState, ui_state, scene_stack: SceneStack, screen_ctx: dict, previous_game_state: str | None) -> SceneTransition | None:
    """
    Delegate events to the active scene / SceneStack in the modern system.
    
    Returns a SceneTransition object (or None) describing what should happen (push, pop, quit, replace, none).
    Does NOT handle legacy game_state.current_screen states - that's in handle_legacy_state_events.
    
    Future: Move this helper into a dedicated input routing module (e.g. input_handlers.py
    or systems/input_routing.py) and keep _handle_events as a thin coordinator.
    """
    current_scene = _get_current_scene(scene_stack)
    if current_scene is None:
        return None
    
    try:
        transition = current_scene.handle_input_transition(events, game_state, screen_ctx)
        return transition
    except AttributeError:
        # Scene doesn't have handle_input_transition, fall through to legacy handling
        return None
    except Exception as e:
        # Log other errors but don't crash
        import traceback
        print(f"[handle_scene_events] Error in scene handle_input_transition: {e}")
        traceback.print_exc()
        return None


def handle_legacy_state_events(events: list, ctx: AppContext, game_state: GameState, ui_state, screen_ctx: dict, scene_stack: SceneStack, handled_by_screen: bool, previous_game_state: str | None, pause_selected: int, controls_selected: int, controls_rebinding: bool) -> tuple[bool, str | None, int, int, bool, dict]:
    """
    TODO: This function contains legacy screen-based input handling. 
    Once all screens are migrated to scenes, this should be removed.
    
    Handles legacy input that still uses game_state.current_screen, STATE_* constants, etc.
    Returns (running, previous_game_state, pause_selected, controls_selected, controls_rebinding, result_dict).
    
    Future: Move this helper into a dedicated input routing module (e.g. input_handlers.py
    or systems/input_routing.py) and keep _handle_events as a thin coordinator.
    Once every state is fully represented as a scene, we can remove this function entirely.
    """
    running = True
    result = {"screen": None, "quit": False, "restart": False, "restart_to_wave1": False, "replay": False, "pop": False, "start_game": False}
    
    for event in events:
        if handled_by_screen:
            continue
        if event.type == pygame.QUIT:
            return False, previous_game_state, pause_selected, controls_selected, controls_rebinding, result
        
        current_state = _get_current_state(scene_stack) or game_state.current_screen
        
        if current_state == STATE_NAME_INPUT and event.type == pygame.TEXTINPUT:
            if len(game_state.player_name_input) < 20:
                game_state.player_name_input += event.text
        
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and current_state == STATE_CONTROLS and controls_rebinding:
            action = controls_actions[controls_selected]
            if action == "direct_allies":
                ctx.controls[action] = MOUSE_BUTTON_RIGHT
                save_controls(ctx.controls)
                controls_rebinding = False
        
        if event.type == pygame.KEYDOWN:
            if current_state == STATE_NAME_INPUT:
                if event.key == pygame.K_BACKSPACE:
                    game_state.player_name_input = game_state.player_name_input[:-1]
                elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    if game_state.player_name_input.strip():
                        save_high_score(
                            game_state.player_name_input.strip(),
                            game_state.final_score_for_high_score,
                            game_state.wave_number - 1,
                            game_state.survival_time,
                            game_state.enemies_killed,
                            ctx.config.difficulty
                        )
                    game_state.current_screen = STATE_HIGH_SCORES
                    game_state.name_input_active = False
                    scene_stack.pop()
                    scene_stack.push(HighScoreScene())
            
            if event.key == pygame.K_ESCAPE:
                if current_state == STATE_PLAYING or current_state == STATE_ENDURANCE:
                    previous_game_state = current_state
                    game_state.previous_screen = previous_game_state
                    game_state.ui.pause_selected = 0
                    # TODO: Remove current_screen assignment - scene stack handles state
                    game_state.current_screen = STATE_PAUSED
                    scene_stack.push(PauseScene())
                elif current_state == STATE_PAUSED:
                    scene_stack.pop()
                    new_state = _get_current_state(scene_stack) or previous_game_state or STATE_PLAYING
                    game_state.current_screen = new_state
                elif current_state == STATE_CONTINUE:
                    return False, previous_game_state, pause_selected, controls_selected, controls_rebinding, result
                elif current_state == STATE_CONTROLS:
                    game_state.ui.pause_selected = 0
                    # TODO: Remove current_screen assignment - scene stack handles state
                    game_state.current_screen = STATE_PAUSED
                    scene_stack.push(PauseScene())
                elif current_state == STATE_VICTORY or current_state == STATE_GAME_OVER or current_state == STATE_HIGH_SCORES:
                    return False, previous_game_state, pause_selected, controls_selected, controls_rebinding, result
                elif current_state == STATE_NAME_INPUT:
                    if game_state.player_name_input.strip():
                        save_high_score(
                            game_state.player_name_input.strip(),
                            game_state.final_score_for_high_score,
                            game_state.wave_number - 1,
                            game_state.survival_time,
                            game_state.enemies_killed,
                            ctx.config.difficulty
                        )
                    game_state.current_screen = STATE_HIGH_SCORES
                    game_state.name_input_active = False
                    scene_stack.pop()
                    scene_stack.push(HighScoreScene())
            
            if event.key == pygame.K_p:
                if current_state == STATE_PLAYING or current_state == STATE_ENDURANCE:
                    previous_game_state = current_state
                    game_state.previous_screen = previous_game_state
                    game_state.ui.pause_selected = 0
                    # TODO: Remove current_screen assignment - scene stack handles state
                    game_state.current_screen = STATE_PAUSED
                    scene_stack.push(PauseScene())
                elif current_state == STATE_PAUSED:
                    scene_stack.pop()
                    new_state = _get_current_state(scene_stack) or previous_game_state or STATE_PLAYING
                    game_state.current_screen = new_state
            
            if event.key == pygame.K_F3:
                _print_active_shader_profiles(ctx.config)
            
            if current_state == STATE_CONTROLS and controls_rebinding:
                if event.key != pygame.K_ESCAPE:
                    action = controls_actions[controls_selected]
                    ctx.controls[action] = event.key
                    save_controls(ctx.controls)
                    controls_rebinding = False
                else:
                    controls_rebinding = False
    
    return running, previous_game_state, pause_selected, controls_selected, controls_rebinding, result


# -----------------------------------------------------------------------------
# EVENT HANDLING - _handle_events is the coordinator
# Future: Move helper functions (handle_global_events, handle_scene_events, 
# handle_legacy_state_events) into a dedicated input routing module 
# (e.g. input_handlers.py or systems/input_routing.py) and keep _handle_events
# as a thin coordinator.
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
    
    This function is the COORDINATOR for input handling. It delegates to three helpers:
    1. handle_global_events: Handles truly global events (QUIT, etc.)
    2. handle_scene_events: Delegates to the modern scene system
    3. handle_legacy_state_events: Handles legacy screen-based input (TODO: remove once migration complete)
    
    Migration path: As screens are fully migrated to scenes, handle_legacy_state_events will be removed,
    and this function will become a thin coordinator of global and scene events only.
    
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
        if current_state in ("SHADER_SETTINGS", STATE_GAME_OVER, STATE_SAVE_GAME, STATE_LOAD_GAME, STATE_QUICK_LAUNCH, STATE_MENU, STATE_PAUSED):
            scene_result = getattr(current_scene, "_last_input_result", None) if current_scene else None
        
        if transition.kind != KIND_NONE:
            should_quit = _apply_scene_transition(transition, scene_stack, ctx, game_state)
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
            elif current_state in (STATE_HIGH_SCORES, STATE_NAME_INPUT, "SHADER_TEST", STATE_TITLE):
                handled_by_screen = True  # Scene handled its own input
            elif current_state in (STATE_GAME_OVER, STATE_SAVE_GAME, STATE_LOAD_GAME):
                # These scenes return SceneTransition.none() for actions like "try_again" or "load_game"
                # that need to be processed by the fallback handler, so don't mark as handled
                handled_by_screen = False
    
    # Fallback to old input handling if scene path didn't handle it
    current_state = _get_current_state(scene_stack) or game_state.current_screen
    if not handled_by_screen and current_state in (STATE_PAUSED, STATE_HIGH_SCORES, STATE_NAME_INPUT, "SHADER_TEST", "SHADER_SETTINGS", STATE_TITLE, STATE_MENU, STATE_QUICK_LAUNCH, STATE_GAME_OVER, STATE_SAVE_GAME, STATE_LOAD_GAME):
        # Use scene_result if we already got it, otherwise get it now
        if scene_result is not None:
            result = scene_result
        elif current_scene:
            result = current_scene.handle_input(events, game_state, screen_ctx)
        else:
            # No scene on stack - this shouldn't happen for these states, but provide empty result for safety
            # TODO: All states should have scenes on the stack. Remove this fallback once migration is complete.
            result = {"screen": None, "quit": False, "restart": False, "restart_to_wave1": False, "replay": False, "pop": False, "start_game": False}
        
        if result.get("quit"):
            return False, previous_game_state, pause_selected, controls_selected, controls_rebinding
        if result.get("pop"):
            scene_stack.pop()
            current_state = _get_current_state(scene_stack) or STATE_PLAYING
            game_state.current_screen = current_state
        if result.get("restart") or result.get("restart_to_wave1") or result.get("replay"):
            game_state.reset_run(ctx, center_player=bool(result.get("restart_to_wave1") or result.get("replay")))
            if result.get("restart"):
                game_state.ui.menu_section = 0
            if result.get("restart_to_wave1") or result.get("replay"):
                spawn_system_start_wave(1, game_state)
                scene_stack.clear()
                scene_stack.push(GameplayScene(STATE_PLAYING))
                game_state.current_screen = STATE_PLAYING
                play_music("in-game", loop=True)
        if result.get("start_game") and result.get("screen") == STATE_PLAYING:
            stop_music()
            play_music("in-game", loop=True)
            if ctx.config.enable_telemetry:
                ctx.telemetry_client = Telemetry(db_path="game_telemetry.db", flush_interval_s=0.5, max_buffer=700)
            else:
                ctx.telemetry_client = NoOpTelemetry()
            stats = player_class_stats[ctx.config.player_class]
            game_state.player_max_hp = int(1000 * stats["hp_mult"] * 0.75)
            game_state.player_hp = game_state.player_max_hp
            game_state.player_speed = int(ctx.config.player_base_speed * stats["speed_mult"])
            game_state.player_bullet_damage = int(ctx.config.player_base_damage * stats["damage_mult"])
            game_state.player_shoot_cooldown = ctx.config.player_base_shoot_cooldown / stats["firerate_mult"]
            if game_state.ui.endurance_mode_selected == 1:
                game_state.lives = 999
                game_state.current_screen = STATE_ENDURANCE
                game_state.previous_screen = STATE_ENDURANCE
                scene_stack.clear()
                scene_stack.push(GameplayScene(STATE_ENDURANCE))
            else:
                game_state.current_screen = STATE_PLAYING
                game_state.previous_screen = STATE_PLAYING
                scene_stack.clear()
                scene_stack.push(GameplayScene(STATE_PLAYING))
            if game_state.level_context:
                game_state.level_context["telemetry"] = ctx.telemetry_client
                game_state.level_context["telemetry_enabled"] = ctx.config.enable_telemetry
                game_state.level_context["difficulty"] = ctx.config.difficulty
                game_state.level_context["testing_mode"] = ctx.config.testing_mode
                game_state.level_context["invulnerability_mode"] = ctx.config.invulnerability_mode
            game_state.run_id = ctx.telemetry_client.start_run(game_state.run_started_at, game_state.player_max_hp) if ctx.config.enable_telemetry else None
            ctx.last_telemetry_sample_t = -1.0
            game_state.wave_reset_log.clear()
            game_state.wave_start_reason = "menu_start"
            spawn_system_start_wave(game_state.wave_number, game_state)
        current_state = _get_current_state(scene_stack) or game_state.current_screen
        # Sync pause_selected from game_state (handler may have updated it)
        if current_state == STATE_PAUSED:
            pause_selected = game_state.ui.pause_selected
        # Handle "try_again" from game over screen - restart at game_over_wave
        if result.get("try_again"):
            wave_to_restart = getattr(game_state, "game_over_wave", 1)
            game_state.reset_run(ctx)
            game_state.wave_start_reason = "try_again"
            spawn_system_start_wave(wave_to_restart, game_state)
            scene_stack.clear()
            scene_stack.push(GameplayScene(STATE_PLAYING))
            game_state.current_screen = STATE_PLAYING
            play_music("in-game", loop=True)
        # Handle "load_game" from load game screen
        elif result.get("load_game") and result.get("load_slot"):
            from constants import difficulty_options, player_class_options
            slot = result["load_slot"]
            # Apply saved config
            if hasattr(ctx, "config"):
                ctx.config.difficulty = slot.difficulty
                ctx.config.player_class = slot.player_class
            # Reset and start at saved wave
            game_state.reset_run(ctx)
            game_state.wave_start_reason = "load_game"
            spawn_system_start_wave(slot.wave_number, game_state)
            game_state.score = slot.score  # Restore score
            scene_stack.clear()
            scene_stack.push(GameplayScene(STATE_PLAYING))
            game_state.current_screen = STATE_PLAYING
            play_music("in-game", loop=True)
        elif result.get("screen") is not None and not result.get("start_game"):
            new_screen = result["screen"]
            game_state.current_screen = new_screen
            if new_screen == STATE_MENU:
                play_music("ambient2", loop=True)
                scene_stack.clear()
                scene_stack.push(OptionsScene())
            elif new_screen == STATE_QUICK_LAUNCH:
                play_music("ambient2", loop=True)
                scene_stack.clear()
                scene_stack.push(QuickLaunchScene())
            elif new_screen == STATE_TITLE:
                scene_stack.clear()
                scene_stack.push(TitleScene())
            elif new_screen == STATE_PAUSED:
                scene_stack.push(PauseScene())
            elif new_screen == STATE_NAME_INPUT:
                scene_stack.push(NameInputScene())
            elif new_screen == STATE_HIGH_SCORES:
                scene_stack.push(HighScoreScene())
            elif new_screen == STATE_GAME_OVER:
                scene_stack.clear()
                scene_stack.push(GameOverScene())
            elif new_screen == STATE_SAVE_GAME:
                scene_stack.push(SaveGameScene())
            elif new_screen == STATE_LOAD_GAME:
                scene_stack.push(LoadGameScene())
            elif new_screen in (STATE_PLAYING, STATE_ENDURANCE):
                if current_state == STATE_PAUSED:
                    scene_stack.pop()
                else:
                    scene_stack.clear()
                    scene_stack.push(GameplayScene(new_screen))
        handled_by_screen = True
    
    # Step 4: Handle legacy state events (TODO: remove once migration complete)
    running, previous_game_state, pause_selected, controls_selected, controls_rebinding, _ = handle_legacy_state_events(
        events, ctx, game_state, game_state.ui, screen_ctx, scene_stack, handled_by_screen, previous_game_state, pause_selected, controls_selected, controls_rebinding
    )
    if not running:
        return False, previous_game_state, pause_selected, controls_selected, controls_rebinding
    
    return running, previous_game_state, pause_selected, controls_selected, controls_rebinding


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
                    should_quit = _apply_scene_transition(transition, scene_stack, ctx, game_state)
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


def _render_current_scene(
    ctx: AppContext,
    game_state: GameState,
    scene_stack: SceneStack,
    screen_ctx: dict,
    pause_shaders_enabled: bool = False,
    menu_shaders_enabled: bool = False,
) -> None:
    """Render the current scene based on game state."""
    current_state = _get_current_state(scene_stack) or game_state.current_screen
    theme = level_themes.get(game_state.current_level, level_themes[1])
    if current_state not in (STATE_PLAYING, STATE_ENDURANCE):
        ctx.screen.fill(theme["bg_color"])

    if current_state == STATE_PLAYING or current_state == STATE_ENDURANCE:
        lv = game_state.level
        # Cache gameplay_ctx on game_state to avoid recreating dict every frame
        gameplay_ctx = getattr(game_state, "_cached_gameplay_ctx", None)
        if gameplay_ctx is None:
            gameplay_ctx = {
                "level_themes": level_themes,
                "trapezoid_blocks": lv.trapezoid_blocks if lv else [],
                "triangle_blocks": lv.triangle_blocks if lv else [],
                "destructible_blocks": lv.destructible_blocks if lv else [],
                "moveable_destructible_blocks": lv.moveable_blocks if lv else [],
                "giant_blocks": lv.giant_blocks if lv else [],
                "super_giant_blocks": lv.super_giant_blocks if lv else [],
                "hazard_obstacles": lv.hazard_obstacles if lv else [],
                "moving_health_zone": lv.moving_health_zone if lv else None,
                "teleporter_pads": game_state.teleporter_pads,
                "small_font": ctx.small_font,
                "weapon_names": WEAPON_NAMES,
                "WIDTH": ctx.width,
                "HEIGHT": ctx.height,
                "font": ctx.font,
                "big_font": ctx.big_font,
                "ui_show_hud": ctx.config.show_hud,
                "ui_show_metrics": ctx.config.show_metrics,
                "ui_show_health_bars": ctx.config.show_health_bars,
                "ui_show_fps": ctx.config.show_fps,
                "overshield_max": overshield_max,
                "grenade_cooldown": grenade_cooldown,
                "missile_cooldown": missile_cooldown,
                "ally_drop_cooldown": ally_drop_cooldown,
                "overshield_recharge_cooldown": overshield_recharge_cooldown,
                "shield_duration": shield_duration,
                "aiming_mode": ctx.config.aim_mode,
                "current_state": current_state,
                "enable_screen_flash": getattr(ctx.config, "enable_screen_flash", True),
                "screen_flash_duration": getattr(ctx.config, "screen_flash_duration", 0.25),
                "screen_flash_max_alpha": getattr(ctx.config, "screen_flash_max_alpha", 100),
                "enable_wave_banner": getattr(ctx.config, "enable_wave_banner", True),
            }
            game_state._cached_gameplay_ctx = gameplay_ctx
        else:
            # Update only values that can change (config toggles and current state)
            gameplay_ctx["ui_show_hud"] = ctx.config.show_hud
            gameplay_ctx["ui_show_metrics"] = ctx.config.show_metrics
            gameplay_ctx["ui_show_health_bars"] = ctx.config.show_health_bars
            gameplay_ctx["ui_show_fps"] = ctx.config.show_fps
            gameplay_ctx["current_state"] = current_state
            # Update level references if level changed
            if lv:
                gameplay_ctx["trapezoid_blocks"] = lv.trapezoid_blocks
                gameplay_ctx["triangle_blocks"] = lv.triangle_blocks
                gameplay_ctx["destructible_blocks"] = lv.destructible_blocks
                gameplay_ctx["moveable_destructible_blocks"] = lv.moveable_blocks
                gameplay_ctx["giant_blocks"] = lv.giant_blocks
                gameplay_ctx["super_giant_blocks"] = lv.super_giant_blocks
                gameplay_ctx["hazard_obstacles"] = lv.hazard_obstacles
                gameplay_ctx["moving_health_zone"] = lv.moving_health_zone
            gameplay_ctx["teleporter_pads"] = game_state.teleporter_pads
        render_ctx = RenderContext.from_app_ctx(ctx)
        render_gameplay_with_optional_shaders(render_ctx, game_state, {"app_ctx": ctx, "gameplay_ctx": gameplay_ctx})
        
        # Clean up expired UI tokens (state updates; timers decremented in update loop)
        for dmg_num in game_state.damage_numbers[:]:
            if dmg_num["timer"] <= 0:
                game_state.damage_numbers.remove(dmg_num)
        for msg in game_state.weapon_pickup_messages[:]:
            if msg["timer"] <= 0:
                game_state.weapon_pickup_messages.remove(msg)
    elif current_state in (STATE_TITLE, STATE_MENU, STATE_QUICK_LAUNCH, STATE_PAUSED, STATE_HIGH_SCORES, STATE_NAME_INPUT, STATE_GAME_OVER, STATE_SAVE_GAME, STATE_LOAD_GAME, "SHADER_TEST", "SHADER_SETTINGS"):
        # Use display render context for menus (not world surface)
        render_ctx = RenderContext.for_menu(ctx)
        # When paused + enable_pause_shaders: render gameplay frame, apply pause stack, then draw UI on top
        if current_state == STATE_PAUSED and pause_shaders_enabled:
            lv = game_state.level
            # Use display dimensions for pause overlay
            display_w = getattr(ctx, 'display_width', ctx.width)
            display_h = getattr(ctx, 'display_height', ctx.height)
            gameplay_ctx_pause = {
                "level_themes": level_themes,
                "trapezoid_blocks": lv.trapezoid_blocks if lv else [],
                "triangle_blocks": lv.triangle_blocks if lv else [],
                "destructible_blocks": lv.destructible_blocks if lv else [],
                "moveable_destructible_blocks": lv.moveable_blocks if lv else [],
                "giant_blocks": lv.giant_blocks if lv else [],
                "super_giant_blocks": lv.super_giant_blocks if lv else [],
                "hazard_obstacles": lv.hazard_obstacles if lv else [],
                "moving_health_zone": lv.moving_health_zone if lv else None,
                "teleporter_pads": game_state.teleporter_pads,
                "small_font": ctx.small_font,
                "weapon_names": WEAPON_NAMES,
                "WIDTH": display_w,
                "HEIGHT": display_h,
                "font": ctx.font,
                "big_font": ctx.big_font,
                "ui_show_hud": ctx.config.show_hud,
                "ui_show_metrics": ctx.config.show_metrics,
                "ui_show_health_bars": ctx.config.show_health_bars,
                "ui_show_fps": ctx.config.show_fps,
                "overshield_max": overshield_max,
                "grenade_cooldown": grenade_cooldown,
                "missile_cooldown": missile_cooldown,
                "ally_drop_cooldown": ally_drop_cooldown,
                "overshield_recharge_cooldown": overshield_recharge_cooldown,
                "shield_duration": shield_duration,
                "aiming_mode": ctx.config.aim_mode,
                "current_state": current_state,
                "enable_screen_flash": getattr(ctx.config, "enable_screen_flash", True),
                "screen_flash_duration": getattr(ctx.config, "screen_flash_duration", 0.25),
                "screen_flash_max_alpha": getattr(ctx.config, "screen_flash_max_alpha", 100),
                "enable_wave_banner": getattr(ctx.config, "enable_wave_banner", True),
            }
            offscreen = pygame.Surface((display_w, display_h)).convert_alpha()
            offscreen.fill((0, 0, 0, 255))
            render_gameplay_frame_to_surface(
                offscreen, display_w, display_h,
                ctx.font, ctx.big_font, ctx.small_font,
                game_state, {"app_ctx": ctx, "gameplay_ctx": gameplay_ctx_pause},
            )
            pause_stack = get_pause_shader_stack(ctx.config)
            surf = offscreen
            eff_ctx = {"time": time.perf_counter()}
            for eff in pause_stack:
                surf = eff.apply(surf, 0.016, eff_ctx)
            ctx.screen.blit(surf, (0, 0))
        current_scene = scene_stack.current()
        if current_scene:
            current_scene.render(render_ctx, game_state, screen_ctx)
        # Note: All states should have scenes on the stack. If no scene exists, we skip rendering.
        # This is a safety fallback - scenes should always be present for PAUSED, HIGH_SCORES, NAME_INPUT, etc.
        # Config-based shader stacks and legacy lightweight effects
        if current_state == STATE_PAUSED and not pause_shaders_enabled:
            apply_pause_effects(render_ctx.screen, ctx)
        elif current_state in (STATE_TITLE, STATE_MENU, STATE_QUICK_LAUNCH):
            apply_menu_effects(render_ctx.screen, ctx)
        # Apply config-based menu shader stack when enable_menu_shaders and menu_shader_profile != "none"
        if current_state in (STATE_TITLE, STATE_MENU, STATE_QUICK_LAUNCH) and menu_shaders_enabled:
            try:
                menu_stack = get_menu_shader_stack(ctx.config)
                if menu_stack:
                    display = render_ctx.screen
                    surf = display
                    eff_ctx = {"time": game_state.run_time}
                    for eff in menu_stack:
                        if surf is None:
                            break
                        surf = eff.apply(surf, 0.016, eff_ctx)
                    if surf is not None and surf is not display:
                        display.blit(surf, (0, 0))
            except Exception as e:
                # If shader application fails, log and continue without shaders
                print(f"[Menu shader] Error applying shader stack: {e}")
                import traceback
                traceback.print_exc()
    elif current_state == STATE_VICTORY:
        # Victory screen
        # (Victory rendering would go here)
        pass
    elif current_state == STATE_CONTROLS:
        # Controls menu
        # (Controls menu rendering would go here)
        pass


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


# Controls will be initialized in _create_app() after pygame.init()
# Using a placeholder dict to avoid calling pygame.key.key_code() before pygame.init()
controls = {}

# Telemetry and run_started_at are stored in AppContext (built in main()).

# Game state constants are now imported from constants.py
# UI state is now in GameState.ui (UiState) - see ui_state.py
# Character profile stats are now in GameState.custom_profile_stats

# Side quests and goal tracking are now in GameState.side_quests and GameState.wave_damage_taken
# Beam selection for testing (harder to access - requires testing mode)
# testing_mode and invulnerability_mode are now in AppContext.config
# beam_selection_selected is now in GameState.ui.beam_selection_selected
# beam_selection_pattern is now in GameState.beam_selection_pattern

# Level system - 3 levels, each with 3 waves (boss on wave 3)
# current_level, max_level, wave_in_level are now in GameState
# level_themes is now imported from constants.py

# Difficulty / aiming / class: applied values live in AppContext (ctx)
# Menu selection indices are now in GameState.ui (difficulty_selected, aiming_mode_selected, player_class_selected)

# Mod settings are now in GameConfig (mod_enemy_spawn_multiplier, mod_custom_waves_enabled, custom_waves)
# UI customization settings are now in GameState.ui (UiState)
# Alternative aiming mechanics are now in GameConfig.aiming_mechanic

# difficulty_multipliers and pause_options are now imported from constants.py
# pause_selected, continue_blink_t, controls_selected are now in GameState.ui
# controls_rebinding is now in GameState.controls_rebinding

# ----------------------------
# Player (initialized in main() after WIDTH/HEIGHT are set)
# ----------------------------
player = None  # Will be initialized in main() after WIDTH/HEIGHT are set
player_speed = 450  # px/s (base speed, modified by class) - 1.5x (300 * 1.5)
player_max_hp = 7500  # base HP (modified by class) - 10x (750 * 10)
player_hp = player_max_hp

# player_class_stats and overshield_max are now imported from constants.py
overshield = 0  # Current overshield amount
# overshield_recharge_cooldown is now imported from constants.py
overshield_recharge_timer = 0.0  # Time since last overshield activation
# shield_recharge_cooldown is now imported from constants.py
shield_recharge_timer = 0.0  # Time since shield was used
# pygame.mouse.set_visible(True)  # Moved to main() after pygame.init()

# LIVES_START is now imported from constants.py
lives = LIVES_START

# Track most recent movement keys so latest press wins on conflicts
last_horizontal_key = None  # keycode of current "latest" horizontal key
last_vertical_key = None  # keycode of current "latest" vertical key
last_move_velocity = pygame.Vector2(0, 0)

# Dash mechanic (space bar) - constants imported from constants.py
jump_cooldown_timer = 0.0
jump_velocity = pygame.Vector2(0, 0)  # Current jump velocity
jump_timer = 0.0
is_jumping = False

# Boost / slow
previous_boost_state = False  # Track for telemetry
previous_slow_state = False  # Track for telemetry

# Boost/slow constants imported from constants.py
boost_meter = boost_meter_max

# Fire-rate pickup buff
fire_rate_buff_t = 0.0
fire_rate_buff_duration = 10.0
fire_rate_mult = 0.55  # reduces cooldown while active

# Shield system (Left Alt key) - constants imported from constants.py
shield_active = False
shield_duration_remaining = 0.0
shield_cooldown = shield_recharge_cooldown  # From constants (5.0, half of original 10)
shield_cooldown_remaining = 0.0
shield_recharge_cooldown = shield_recharge_cooldown  # Imported from constants.py (default 10.0), will be set when shield is activated
shield_recharge_timer = 0.0

# Permanent player stat multipliers (from pickups)
player_stat_multipliers = {
    "speed": 1.0,
    "firerate": 1.0,  # permanent firerate boost (stacks with temporary buff)
    "bullet_size": 1.0,
    "bullet_speed": 1.0,
    "bullet_damage": 1.0,
    "bullet_knockback": 1.0,
    "bullet_penetration": 0,  # number of enemies bullet can pierce through
    "bullet_explosion_radius": 0.0,  # explosion radius in pixels (0 = no explosion)
}

# Random damage multiplier (from "random_damage" pickup)
# This multiplies the base damage, and changes randomly when pickup is collected
random_damage_multiplier = 1.0  # Starts at 1.0x

# Damage number display system (floating damage numbers over enemies)
damage_numbers: list[dict] = []  # List of {x, y, damage, timer, color}
weapon_pickup_messages: list[dict] = []  # List of {weapon_name, timer, color} for displaying weapon pickup notifications

# Weapon mode system (keys 1-6 to switch)
# "basic" = normal bullets, "triple" = triple shot, "giant" = giant bullets, "laser" = laser beam
current_weapon_mode = "giant"
previous_weapon_mode = "giant"  # Track for telemetry
unlocked_weapons: set[str] = {"basic", "giant", "triple", "laser"}  # Keys 1=triple, 2=laser, 3=giant

# Laser beam system - constants imported from constants.py
laser_beams: list[dict] = []  # List of active laser beams
laser_time_since_shot = 999.0

# Wave beam system (trigonometric wave patterns) - constants imported from constants.py
wave_beams: list[dict] = []  # List of active wave beams
wave_beam_time_since_shot = 999.0
wave_beam_pattern_index = 0  # Current wave pattern (cycles through patterns)

# hazard_obstacles imported from hazards.py
# Level geometry is built in build_level_geometry() and stored in game_state.level (LevelState).

# Teleporter pads: set in main() via place_teleporter_pads() from level_builder.py. Other modules may reference this.
# TELEPORTER_SIZE is defined in level_builder.py; used by place_teleporter_pads()
teleporter_pads: list = []

# Level geometry functions moved to level_builder.py:
# - build_level_geometry()
# - place_teleporter_pads()
# - generate_wave_beam_points()
# - check_wave_beam_collision()

# Track which zones player is currently in (for telemetry)
player_current_zones = set()  # Set of zone names player is in

# Player health regeneration rate (can be increased by pickups)
player_health_regen_rate = 0.0  # Base regeneration rate (0 = no regen)

# Bouncing destructor shapes (line 79)
destructor_shapes: list[dict] = []  # Large shapes that bounce around destroying things

# ----------------------------
# Player bullets - constants imported from constants.py
# ----------------------------
player_bullets: list[dict] = []
player_time_since_shot = 999.0
player_bullet_shape_index = 0

# Grenade system - constants imported from constants.py
grenade_explosions: list[dict] = []  # List of active explosions {x, y, radius, max_radius, timer, damage}
grenade_time_since_used = 999.0  # Time since last grenade

# Missile system (seeking missiles) - constants imported from constants.py
missiles: list[dict] = []  # List of active missiles {rect, vel, target_enemy, speed, damage, explosion_radius}
missile_time_since_used = 999.0  # Time since last missile
missile_explosion_radius = 100  # Explosion radius
missile_speed = 200  # Missile movement speed (reduced by 0.5x)

# ----------------------------
# Enemy templates are now imported from config_enemies.py
# ----------------------------
enemy_templates = ENEMY_TEMPLATES  # Alias for compatibility

# Boss enemy template is now imported from config_enemies.py
# Note: rect position will be set at runtime in spawn_boss()
# boss_template will be created from BOSS_TEMPLATE.copy() when needed in start_wave()
# We keep a reference here for compatibility, but it will be copied at runtime
boss_template = BOSS_TEMPLATE  # Reference (will be copied when spawning boss)

enemies: list[dict] = []

# ----------------------------
# Friendly AI
# ----------------------------
# Friendly AI templates are now imported from config_enemies.py
friendly_ai_templates = FRIENDLY_AI_TEMPLATES  # Alias for compatibility

friendly_ai: list[dict] = []

# Dropped ally system (distracts enemies)
dropped_ally: dict | None = None  # Single dropped ally that distracts enemies
ally_drop_cooldown = 3.0  # Cooldown between ally drops (seconds)
ally_drop_timer = 0.0  # Time since last ally drop
friendly_projectiles: list[dict] = []

# ----------------------------
# Enemy projectiles
# ----------------------------
enemy_projectiles: list[dict] = []
# Enemy projectile constants are now imported from constants.py
enemy_projectile_size = ENEMY_PROJECTILE_SIZE
enemy_projectile_damage = ENEMY_PROJECTILE_DAMAGE
enemy_projectiles_color = ENEMY_PROJECTILES_COLOR
enemy_projectile_shapes = ["circle", "square", "diamond"]

# ----------------------------
# Run counters (runs table) - initialized in main()
# ----------------------------
running = True  # Will be set in main()
run_time = 0.0

shots_fired = 0
hits = 0

damage_taken = 0
damage_dealt = 0

enemies_spawned = 0
enemies_killed = 0
deaths = 0
score = 0
survival_time = 0.0  # Total time survived in seconds

# High score system - HIGH_SCORES_DB imported from constants.py
player_name_input = ""  # Current name being typed
name_input_active = False  # Whether we're in name input mode
final_score_for_high_score = 0  # Score to save when name is entered

# POS_SAMPLE_INTERVAL imported from constants.py
pos_timer = 0.0

# Waves / progression
wave_number = 1
wave_in_level = 1  # Wave within current level (1, 2, or 3)
wave_respawn_delay = 2.5  # seconds between waves
time_to_next_wave = 0.0
wave_active = True
# Enemy spawn constants are now imported from config_enemies.py
base_enemies_per_wave = BASE_ENEMIES_PER_WAVE
max_enemies_per_wave = MAX_ENEMIES_PER_WAVE
boss_active = False

# Pickups - PICKUP_SPAWN_INTERVAL imported from constants.py
pickups: list[dict] = []
pickup_spawn_timer = 0.0

# Scoring constants imported from constants.py
# Weapon key mapping imported from constants.py
# Removed: enemy_spawn_boost_level - enemies no longer collect pickups

# Weapon key mapping (uses pygame constants, so must stay here)
WEAPON_KEY_MAP = {
    pygame.K_1: "triple",
    pygame.K_2: "laser",
    pygame.K_3: "giant",
}

# Visual effects for pickups
pickup_particles: list[dict] = []  # particles around pickups
collection_effects: list[dict] = []  # effects when pickups are collected


# ----------------------------
# Helpers (geometry/physics moved to geometry_utils)
# ----------------------------
# move_player_with_push is now imported from systems.collision_movement


# _enemy_collides and move_enemy_with_push are now imported from systems.collision_movement


def random_spawn_position(size: tuple[int, int], state: GameState, max_attempts: int = 25) -> pygame.Rect:
    """Find a spawn position not overlapping player or blocks. Player spawn takes priority."""
    w, h = size
    lev = getattr(state, "level", None)
    if state.player_rect is None:
        player_center = pygame.Vector2(WIDTH // 2, HEIGHT // 2)
        player_size = 28
    else:
        player_center = pygame.Vector2(state.player_rect.center)
        player_size = max(state.player_rect.w, state.player_rect.h)
    min_distance = player_size * 10
    
    for _ in range(max_attempts):
        x = random.randint(0, WIDTH - w)
        y = random.randint(0, HEIGHT - h)
        candidate = pygame.Rect(x, y, w, h)
        candidate_center = pygame.Vector2(candidate.center)
        if candidate_center.distance_to(player_center) < min_distance:
            continue
        if state.player_rect is not None and candidate.colliderect(state.player_rect):
            continue
        if lev is not None:
            if any(candidate.colliderect(b["rect"]) for b in lev.static_blocks):
                continue
            if any(candidate.colliderect(b["rect"]) for b in lev.moveable_blocks):
                continue
            if any(candidate.colliderect(b["rect"]) for b in lev.destructible_blocks):
                continue
            if any(candidate.colliderect(b["rect"]) for b in lev.giant_blocks):
                continue
            if any(candidate.colliderect(b["rect"]) for b in lev.super_giant_blocks):
                continue
            if any(candidate.colliderect(tb["bounding_rect"]) for tb in lev.trapezoid_blocks):
                continue
            if any(candidate.colliderect(tr["bounding_rect"]) for tr in lev.triangle_blocks):
                continue
            if lev.moving_health_zone and candidate.colliderect(lev.moving_health_zone["rect"]):
                continue
        if any(candidate.colliderect(p["rect"]) for p in state.pickups):
            continue
        if any(candidate.colliderect(pad["rect"]) for pad in state.teleporter_pads):
            continue
        return candidate
    return pygame.Rect(max(0, WIDTH // 2 - w), max(0, HEIGHT // 2 - h), w, h)


# Wave start and wave/boss/difficulty logic live in systems.spawn_system (start_wave, update)


def init_high_scores_db():
    """Initialize the high scores database."""
    conn = sqlite3.connect(HIGH_SCORES_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS high_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT NOT NULL,
            score INTEGER NOT NULL,
            waves_survived INTEGER NOT NULL,
            time_survived REAL NOT NULL,
            enemies_killed INTEGER NOT NULL,
            difficulty TEXT NOT NULL,
            date_achieved TEXT NOT NULL
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_score ON high_scores(score DESC);")
    conn.commit()
    conn.close()


def get_high_scores(limit: int = 10) -> list[dict]:
    """Get top high scores from database."""
    conn = sqlite3.connect(HIGH_SCORES_DB)
    cursor = conn.execute("""
        SELECT player_name, score, waves_survived, time_survived, enemies_killed, difficulty, date_achieved
        FROM high_scores
        ORDER BY score DESC
        LIMIT ?
    """, (limit,))
    scores = []
    for row in cursor.fetchall():
        scores.append({
            "name": row[0],
            "score": row[1],
            "waves": row[2],
            "time": row[3],
            "kills": row[4],
            "difficulty": row[5],
            "date": row[6]
        })
    conn.close()
    return scores


def save_high_score(name: str, score: int, waves: int, time_survived: float, enemies_killed: int, difficulty: str):
    """Save a high score to the database."""
    if not name or not name.strip():
        name = "Anonymous"
    conn = sqlite3.connect(HIGH_SCORES_DB)
    conn.execute("""
        INSERT INTO high_scores (player_name, score, waves_survived, time_survived, enemies_killed, difficulty, date_achieved)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name.strip()[:20], score, waves, time_survived, enemies_killed, difficulty, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()


def is_high_score(score: int) -> bool:
    """Check if a score qualifies for the high score board (top 10)."""
    scores = get_high_scores(10)
    if len(scores) < 10:
        return True
    return score > scores[-1]["score"]


def spawn_pickup(pickup_type: str, state: GameState):
    """Spawn a pickup at a non-overlapping position. Uses state.level for geometry when available."""
    size = (64, 64)
    max_attempts = 50
    for _ in range(max_attempts):
        r = random_spawn_position(size, state)
        overlaps = False
        for existing_pickup in state.pickups:
            if r.colliderect(existing_pickup["rect"]):
                overlaps = True
                break
        if state.level and state.level.moving_health_zone and r.colliderect(state.level.moving_health_zone["rect"]):
            overlaps = True
        
        if not overlaps:
            # All pickups look the same (mystery) - randomized color so player doesn't know what they're getting
            mystery_colors = [
                (180, 100, 255),  # purple
                (100, 255, 180),  # green
                (255, 180, 100),  # orange
                (180, 255, 255),  # cyan
                (255, 100, 180),  # pink
                (255, 255, 100),  # yellow
            ]
            color = random.choice(mystery_colors)
            run_time = getattr(state, "run_time", 0.0)
            state.pickups.append({
                "type": pickup_type,
                "rect": r,
                "color": color,
                "timer": 15.0,
                "age": 0.0,
                "spawn_t": run_time,
            })
            return


def spawn_weapon_in_center(weapon_type: str, state: GameState, width: int, height: int):
    """Spawn a weapon pickup in the center of the screen (level completion reward). Only giant is dropped."""
    if weapon_type not in ("giant", "giant_bullets"):
        return
    # Weapon colors are now imported from config_weapons.py
    weapon_pickup_size = (80, 80)  # Bigger for level completion rewards (2x from 40x40)
    weapon_pickup_rect = pygame.Rect(
        width // 2 - weapon_pickup_size[0] // 2,
        height // 2 - weapon_pickup_size[1] // 2,
        weapon_pickup_size[0],
        weapon_pickup_size[1]
    )
    run_time = getattr(state, "run_time", 0.0)
    state.pickups.append({
        "type": weapon_type,
        "rect": weapon_pickup_rect,
        "color": WEAPON_DISPLAY_COLORS.get(weapon_type, (180, 100, 255)),
        "timer": 30.0,  # Level completion weapons last longer
        "age": 0.0,
        "spawn_t": run_time,
        "is_weapon_drop": True,
        "is_level_reward": True,  # Mark as level completion reward
    })


def spawn_weapon_drop(enemy: dict, state: GameState):
    """Spawn a bonus-points drop from a killed enemy. 1/10th former rate; despawns after 7s."""
    # 1.5% chance to drop (1/10th of former 15% rate)
    if random.random() >= 0.015:
        return
    size = (56, 56)
    r = pygame.Rect(
        enemy["rect"].centerx - size[0] // 2,
        enemy["rect"].centery - size[1] // 2,
        size[0], size[1]
    )
    run_time = getattr(state, "run_time", 0.0)
    state.pickups.append({
        "type": "bonus",
        "rect": r,
        "color": (255, 215, 0),  # gold for bonus points
        "spawn_t": run_time,
        "age": 0.0,
    })


# Rendering helper functions are now imported from rendering.py


def create_pickup_collection_effect(x: int, y: int, color: tuple[int, int, int], state: GameState):
    """Create particle effect when pickup is collected."""
    for _ in range(12):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(50, 150)
        state.collection_effects.append({
            "x": float(x),
            "y": float(y),
            "vel_x": math.cos(angle) * speed,
            "vel_y": math.sin(angle) * speed,
            "color": color,
            "life": 0.4,  # particle lifetime
            "size": random.randint(3, 6),
        })


# Rendering helper functions are now imported from rendering.py
# Projectile spawning functions moved to systems/projectile_spawning.py


def calculate_kill_score(wave_num: int, run_time: float) -> int:
    """Calculate score for killing an enemy."""
    return SCORE_BASE_POINTS + (wave_num * SCORE_WAVE_MULTIPLIER) + int(run_time * SCORE_TIME_MULTIPLIER)


def kill_enemy(enemy: dict, state: GameState, width: int, height: int, event_bus: object | None = None) -> None:
    """Handle enemy death: drop weapon, update score, remove from list, and clean up projectiles."""
    play_sfx("enemy_death")
    is_boss = enemy.get("is_boss", False)
    
    # Spawner enemy: when killed, all spawned enemies die
    if enemy.get("is_spawner"):
        # Find and kill all enemies spawned by this spawner
        for spawned_enemy in state.enemies[:]:
            if spawned_enemy.get("spawned_by") is enemy:
                # Recursively kill spawned enemy (but don't drop weapons for spawned enemies)
                spawned_enemy_type = spawned_enemy.get("type", "enemy")
                # Remove projectiles
                for proj in state.enemy_projectiles[:]:
                    if proj.get("enemy_type") == spawned_enemy_type:
                        state.enemy_projectiles.remove(proj)
                # Remove from list
                try:
                    state.enemies.remove(spawned_enemy)
                except ValueError:
                    pass
                state.enemies_killed += 1
                state.score += calculate_kill_score(state.wave_number, state.run_time)
    
    # Add defeat message
    enemy_type = enemy.get("type", "enemy")
    state.enemy_defeat_messages.append({
        "enemy_type": enemy_type,
        "timer": 3.0,  # Display for 3 seconds
    })
    
    # Remove projectiles and damage numbers associated with this dead enemy
    enemy_pos = pygame.Vector2(enemy["rect"].center)
    cleanup_radius_sq = 2500  # 50 pixels squared - damage numbers within this range are removed
    
    # Remove ALL enemy projectiles from this dead enemy (by matching enemy_type)
    # This ensures projectiles are removed regardless of distance when enemy dies
    for proj in state.enemy_projectiles[:]:
        # Remove if projectile matches this enemy's type
        # This removes all projectiles from this enemy, even if they've traveled far
        if proj.get("enemy_type") == enemy_type:
            state.enemy_projectiles.remove(proj)
    
    # Remove damage numbers near the dead enemy's position
    for dmg_num in state.damage_numbers[:]:
        dmg_pos = pygame.Vector2(dmg_num["x"], dmg_num["y"])
        if (dmg_pos - enemy_pos).length_squared() < cleanup_radius_sq:
            state.damage_numbers.remove(dmg_num)
    
    # If boss is killed, spawn level completion weapon in center
    if is_boss:
        # Weapon unlock order is now imported from config_weapons.py
        if state.current_level in WEAPON_UNLOCK_ORDER:
            weapon_to_unlock = WEAPON_UNLOCK_ORDER[state.current_level]
            if weapon_to_unlock not in state.unlocked_weapons:
                spawn_weapon_in_center(weapon_to_unlock, state, width, height)
    else:
        # Regular enemies drop weapons randomly (except suicide enemies which despawn)
        if not enemy.get("is_suicide"):
            spawn_weapon_drop(enemy, state)
    
    try:
        state.enemies.remove(enemy)
    except ValueError:
        pass  # Already removed
    score_delta = calculate_kill_score(state.wave_number, state.run_time)
    state.enemies_killed += 1
    state.score += score_delta

    if event_bus is not None and hasattr(event_bus, "publish"):
        try:
            event_bus.publish(GameEvent("enemy_killed", {
                "enemy_type": enemy_type,
                "is_boss": is_boss,
                "wave_number": state.wave_number,
                "score_delta": score_delta,
            }))
        except Exception:
            import logging
            logging.exception("Failed to publish enemy_killed")


# apply_pickup_effect is now imported from pickups.py


# render_hud_text is now imported from rendering.py


def reset_after_death(state: GameState, width: int, height: int):
    state.player_hp = state.player_max_hp
    state.player_health_regen_rate = 0.0  # Reset health regeneration rate
    state.random_damage_multiplier = 1.0  # Reset random damage multiplier
    state.damage_numbers.clear()  # Clear damage numbers on death
    state.weapon_pickup_messages.clear()  # Clear weapon pickup messages on death
    state.grenade_explosions.clear()  # Clear grenade explosions on death
    state.grenade_time_since_used = 999.0  # Reset grenade cooldown
    state.missiles.clear()  # Clear missiles on death
    state.missile_time_since_used = 999.0  # Reset missile cooldown
    state.dropped_ally = None  # Clear dropped ally on death
    state.ally_drop_timer = 0.0  # Reset ally drop timer on death
    # Keep map as-is on respawn: do not reposition moving_health_zone or hazard_obstacles
    state.overshield = 0  # Reset overshield
    state.armor_drain_timer = 0.0
    state.player_time_since_shot = 999.0
    state.laser_time_since_shot = 999.0
    state.wave_beam_time_since_shot = 999.0
    state.wave_beam_pattern_index = 0
    state.pos_timer = 0.0
    # Keep wave/level and weapons on respawn so the map does not reset
    state.previous_boost_state = False
    state.previous_slow_state = False
    state.player_current_zones = set()
    state.jump_cooldown_timer = 0.0
    state.jump_timer = 0.0
    state.is_jumping = False
    state.jump_velocity = pygame.Vector2(0, 0)
    state.laser_beams.clear()
    state.enemy_laser_beams.clear()
    state.wave_beams.clear()
    # Keep hazard obstacles as-is on respawn (map no longer resets)
    # Reset shield
    state.shield_active = False
    state.shield_duration_remaining = 0.0
    state.shield_cooldown_remaining = 0.0

    # Respawn at death position: do not move player_rect (player stays where they died).
    # Optionally keep on-screen if they died in a weird spot:
    player = state.player_rect
    if player is not None:
        clamp_rect_to_screen(player, width, height)

    state.player_bullets.clear()
    state.enemy_projectiles.clear()
    state.friendly_projectiles.clear()
    # Do not clear friendly_ai or call start_wave: keep current wave and enemies.
    # Respawn = player at death position (unchanged), projectiles/explosions cleared; enemies and wave continue.


if __name__ == "__main__":
    main()
