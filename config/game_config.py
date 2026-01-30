"""Centralized game configuration: difficulty, player class, options toggles, feel, and juice.

All scalar config and toggles that are chosen in menus or at startup live here.
Passed via AppContext.config so systems use ctx.config.<field>.

Balance and tuning constants (scoring, cooldowns, damage, projectile/weapon defaults)
live in config.balance; constants.py re-exports them for backward compatibility.

Tuning guide (which values to tweak for feel):
- More floaty vs tight movement: player_base_speed, movement_smoothing (0=instant, 1=full smoothing).
- Faster vs slower weapons: player_base_shoot_cooldown, per-weapon cooldown_multiplier in config_weapons.
- Easier vs harder early waves: base_enemies_per_wave, enemy_spawn_multiplier, difficulty multiplers in constants.
- Feel profiles: use FEEL_PROFILE_CASUAL / FEEL_PROFILE_ARCADE to apply preset overrides (see apply_feel_profile).
- On-screen debug info (wave, enemy count, player HP): set debug_draw_overlay=True to enable the debug HUD in gameplay.
- GPU physics: set use_gpu_physics=True (requires CUDA_AVAILABLE from gpu_physics).
- Post-process profile: shader_profile "none" | "cpu_tint" | "gl_basic" (only when use_shaders=True).
- Lightweight CPU effects: enable_menu_shaders + menu_effect_profile ("crt" | "soft_glow"), enable_gameplay_shaders + gameplay_effect_profile ("subtle_vignette" | "crt_light"), enable_damage_wobble (see visual_effects).
- Shader stacks: enable_menu_shaders + menu_shader_profile, enable_pause_shaders + pause_shader_profile, enable_gameplay_shaders + gameplay_shader_profile (see shader_effects.SHADER_PROFILES, get_*_shader_stack).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from constants import (
    AIM_MOUSE,
    DIFFICULTY_NORMAL,
    PLAYER_CLASS_BALANCED,
)


# Preset feel profiles for manual testing (casual = floatier, easier; arcade = snappier, harder).
FEEL_PROFILE_CASUAL = "casual"
FEEL_PROFILE_ARCADE = "arcade"
FEEL_PROFILES = {
    FEEL_PROFILE_CASUAL: {
        "player_base_speed": 380,
        "player_base_shoot_cooldown": 0.10,
        "base_enemies_per_wave": 10,
        "enemy_spawn_multiplier": 3.0,
        "movement_smoothing": 0.0,
    },
    FEEL_PROFILE_ARCADE: {
        "player_base_speed": 500,
        "player_base_shoot_cooldown": 0.08,
        "base_enemies_per_wave": 14,
        "enemy_spawn_multiplier": 4.0,
        "movement_smoothing": 0.0,
    },
}


@dataclass
class GameConfig:
    """Difficulty, player class, aim mode, feel tuning, difficulty pacing, juice, and option toggles.

    Replaces scattered flags on AppContext. Built at startup and when
    the user changes options in menus; attach to ctx.config.
    
    Safe Mode:
    When safe_mode=True, optional/heavy features are disabled:
    - GPU shaders disabled (use_gpu_shaders, use_gpu_shader_pipeline -> False)
    - CUDA physics disabled (use_gpu_physics -> False)
    - Telemetry disabled (enable_telemetry -> False)
    This makes the game more robust on weak/misconfigured systems.
    """
    # Safe mode: disables GPU shaders, CUDA physics, and telemetry for compatibility
    safe_mode: bool = False
    
    difficulty: str = DIFFICULTY_NORMAL
    player_class: str = PLAYER_CLASS_BALANCED
    aim_mode: str = AIM_MOUSE
    aiming_mechanic: str = "mouse"  # "mouse", "lockon", "predictive", "directional", "hybrid"
    enable_telemetry: bool = False
    show_metrics: bool = True
    show_hud: bool = True
    show_health_bars: bool = True
    show_player_health_bar: bool = True
    show_fps: bool = True  # Show FPS graph in bottom-left corner
    show_perf_overlay: bool = False  # Show detailed performance overlay with entity counts
    target_fps: int = 0  # Target frame rate (60, 120, 144, 240, or 0 for uncapped/max)
    profile_enabled: bool = False
    testing_mode: bool = False
    invulnerability_mode: bool = False
    default_weapon_mode: str = "giant"
    # Mod settings (for custom game modes)
    mod_enemy_spawn_multiplier: float = 1.0  # Custom enemy spawn multiplier
    mod_custom_waves_enabled: bool = False
    custom_waves: list = field(default_factory=list)  # Custom wave definitions (list of dicts)
    debug_draw_overlay: bool = False  # When True, gameplay shows a small debug HUD (wave, enemies, HP, lives).
    use_shaders: bool = False  # When True, use GPU shaders for rendering (requires moderngl).
    shader_profile: str = "none"  # "none" | "cpu_tint" | "gl_basic"; only applies when use_shaders=True.
    # Lightweight CPU effect toggles and profiles (visual_effects module)
    enable_menu_shaders: bool = False  # Apply effect stack to title/options/pause (scanlines, vignette, tint).
    enable_gameplay_shaders: bool = False  # Apply subtle vignette/scanlines to gameplay.
    menu_effect_profile: str = "none"  # "none" | "crt" | "soft_glow"; used when enable_menu_shaders=True.
    gameplay_effect_profile: str = "none"  # "none" | "subtle_vignette" | "crt_light"; used when enable_gameplay_shaders=True.
    enable_damage_wobble: bool = False  # Brief screen jitter when player takes damage (if gameplay style fits).
    # Shader/effect stack toggles and profile names (shader_effects.SHADER_PROFILES + get_*_shader_stack)
    enable_pause_shaders: bool = False  # Apply effect stack to pause overlay when True.
    menu_shader_profile: str = "none"  # "none" | "menu_crt" | "menu_neon"; used when enable_menu_shaders=True.
    pause_shader_profile: str = "none"  # "none" | "pause_dim_vignette"; used when enable_pause_shaders=True.
    gameplay_shader_profile: str = "none"  # "none" | "gameplay_subtle_vignette" | "gameplay_retro"; used when enable_gameplay_shaders=True.
    use_gpu_physics: bool = False  # When True AND CUDA_AVAILABLE, use GPU-accelerated physics code paths.

    # Projectile limits for performance (0 = unlimited)
    max_player_bullets: int = 200  # Maximum player bullets on screen
    max_enemy_projectiles: int = 300  # Maximum enemy projectiles on screen
    max_friendly_projectiles: int = 100  # Maximum friendly AI projectiles
    max_missiles: int = 30  # Maximum missiles on screen
    max_explosions: int = 20  # Maximum active explosions
    max_laser_beams: int = 10  # Maximum laser beams on screen

    # Graphics/performance preset (centralized; future presets low/medium/high/ultra can map onto these)
    graphics_preset: str = "low"  # "low" | "medium" | "high" | "ultra"; currently informational, values drive the flags below.
    use_gpu_shaders: bool = False  # When True, use GPU (OpenGL) path for shader postprocess when shader_profile allows.
    use_gpu_shader_pipeline: bool = False  # When True, use GPU shader pipeline instead of CPU visual effects.
    internal_resolution_scale: float = 1.0  # Scale for CPU-based effect offscreen (e.g. 0.5 = half-res); 1.0 = full res.
    
    # World scale: makes the playable area larger (zoomed out view)
    # 1.0 = normal, 1.33 = 33% larger world, 1.5 = 50% larger world
    # The world is rendered at this scale then scaled down to fit the display
    world_scale: float = 1.33  # Default 33% larger world

    # Game speed / timescale (1.0 = normal, 0.75 = slower, 1.25 = faster)
    # Applied to dt in the main game loop for smoother pacing
    timescale: float = 1.0
    
    # Audio (used by systems.audio_system)
    sfx_volume: float = 1.0
    music_volume: float = 0.3
    mute_sfx: bool = False
    mute_music: bool = False

    # --- Feel: movement (used when applying class stats and in movement/input) ---
    player_base_speed: int = 300  # Base px/s before class multiplier (e.g. 300 * 1.5 = 450 for balanced)
    player_base_damage: int = 20   # Base damage before class multiplier
    player_base_shoot_cooldown: float = 0.12  # Base seconds between shots before class multiplier
    movement_dead_zone: float = 0.0   # 0–1; for future analog stick support; digital keys ignore
    movement_smoothing: float = 0.0   # 0 = instant (current); >0 = optional smoothing (hook only)

    # --- Feel: difficulty / pacing (spawn_system uses these if set; else uses config_enemies/constants) ---
    base_enemies_per_wave: int = 12
    enemy_spawn_multiplier: float = 3.5

    # --- Juice: visual feedback (durations in seconds; magnitudes 0–1 or alpha 0–255) ---
    enable_damage_flash: bool = True
    damage_flash_duration: float = 0.12
    damage_flash_brightness: float = 1.0   # 1.0 = full white tint when hit
    enable_screen_flash: bool = True
    screen_flash_duration: float = 0.25
    screen_flash_max_alpha: int = 100
    enable_wave_banner: bool = True
    wave_banner_duration: float = 1.5


def apply_feel_profile(config: GameConfig, profile: str) -> None:
    """Apply a preset feel profile (FEEL_PROFILE_CASUAL or FEEL_PROFILE_ARCADE) to config. In-place."""
    presets = FEEL_PROFILES.get(profile)
    if not presets:
        return
    for k, v in presets.items():
        if hasattr(config, k):
            setattr(config, k, v)


def apply_safe_mode(config: GameConfig) -> None:
    """
    Apply safe mode overrides to disable heavy/optional features.
    
    When safe_mode is True, this disables:
    - GPU shaders (use_gpu_shaders, use_gpu_shader_pipeline, use_shaders)
    - CUDA physics (use_gpu_physics)
    - Telemetry (enable_telemetry)
    - All shader effect stacks (enable_menu_shaders, enable_pause_shaders, enable_gameplay_shaders)
    
    Call this after loading config but before starting the game.
    """
    if not config.safe_mode:
        return
    
    # Disable GPU shaders
    config.use_gpu_shaders = False
    config.use_gpu_shader_pipeline = False
    config.use_shaders = False
    config.shader_profile = "none"
    
    # Disable shader effect stacks
    config.enable_menu_shaders = False
    config.enable_pause_shaders = False
    config.enable_gameplay_shaders = False
    config.menu_shader_profile = "none"
    config.pause_shader_profile = "none"
    config.gameplay_shader_profile = "none"
    
    # Disable CUDA physics
    config.use_gpu_physics = False
    
    # Disable telemetry
    config.enable_telemetry = False


def log_startup_config(config: GameConfig) -> None:
    """
    Log a summary of key config settings at startup.
    
    Useful for debugging and verifying safe_mode is active.
    """
    print("=" * 60)
    print("GAME STARTUP CONFIGURATION")
    print("=" * 60)
    
    if config.safe_mode:
        print("[SAFE MODE] Active - heavy features disabled for compatibility")
    else:
        print("[SAFE MODE] Inactive - all features enabled")
    
    print(f"  GPU Shaders:     {'DISABLED' if not config.use_gpu_shaders else 'Enabled'}")
    print(f"  GPU Pipeline:    {'DISABLED' if not config.use_gpu_shader_pipeline else 'Enabled'}")
    print(f"  CUDA Physics:    {'DISABLED' if not config.use_gpu_physics else 'Enabled'}")
    print(f"  Telemetry:       {'DISABLED' if not config.enable_telemetry else 'Enabled'}")
    print(f"  Menu Shaders:    {'DISABLED' if not config.enable_menu_shaders else 'Enabled'}")
    print(f"  Gameplay Shaders:{'DISABLED' if not config.enable_gameplay_shaders else 'Enabled'}")
    print("=" * 60)
