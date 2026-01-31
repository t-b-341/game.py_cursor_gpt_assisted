"""Telemetry logging integration during gameplay. Per-frame sampling and flush tick."""
from __future__ import annotations

from config.balance import POS_SAMPLE_INTERVAL
from context import AppContext
from telemetry import PlayerPosEvent, FrameTimeEvent
from state import GameState

# Sample frame times every N seconds (balance between detail and database size)
FRAME_TIME_SAMPLE_INTERVAL = 0.05  # 20 samples per second

# Track last frame time sample time (module-level to avoid adding to AppContext)
_last_frame_time_sample_t: float = -1.0


def update_telemetry(gs: GameState, dt: float, app_ctx: AppContext) -> None:
    """Per-frame telemetry: flush tick and position/run_state samples at POS_SAMPLE_INTERVAL.
    Reads/writes app_ctx.last_telemetry_sample_t. No-op if telemetry disabled or no client."""
    if not getattr(app_ctx.config, "enable_telemetry", False) or not app_ctx.telemetry_client:
        return
    client = app_ctx.telemetry_client
    client.tick(dt)
    now = gs.run_time
    last_t = app_ctx.last_telemetry_sample_t
    if last_t < 0:
        app_ctx.last_telemetry_sample_t = now
        return
    if now - last_t < POS_SAMPLE_INTERVAL or not gs.player_rect:
        return
    client.log_player_position(
        PlayerPosEvent(t=now, x=gs.player_rect.centerx, y=gs.player_rect.centery)
    )
    client.log_run_state_sample(now, gs.player_hp, len(gs.enemies))
    app_ctx.last_telemetry_sample_t = now


def log_frame_time(gs: GameState, dt: float, app_ctx: AppContext) -> None:
    """Log frame timing data for performance analysis.
    
    Args:
        gs: Game state with entity counts
        dt: Frame delta time in seconds
        app_ctx: App context with telemetry client
    """
    global _last_frame_time_sample_t
    
    if not getattr(app_ctx.config, "enable_telemetry", False) or not app_ctx.telemetry_client:
        return
    
    now = gs.run_time
    if _last_frame_time_sample_t < 0:
        _last_frame_time_sample_t = now
        return
    
    if now - _last_frame_time_sample_t < FRAME_TIME_SAMPLE_INTERVAL:
        return
    
    _last_frame_time_sample_t = now
    
    # Calculate frame metrics
    frame_time_ms = dt * 1000.0
    fps = 1.0 / dt if dt > 0 else 0.0
    
    # Get entity counts - comprehensive list for performance debugging
    player_bullets = len(getattr(gs, "player_bullets", []))
    enemy_projectiles = len(getattr(gs, "enemy_projectiles", []))
    enemies = len(getattr(gs, "enemies", []))
    friendly_projectiles = len(getattr(gs, "friendly_projectiles", []))
    missiles = len(getattr(gs, "missiles", []))
    explosions = len(getattr(gs, "grenade_explosions", []))
    laser_beams = len(getattr(gs, "laser_beams", []))
    damage_numbers = len(getattr(gs, "damage_numbers", []))
    friendly_ai = len(getattr(gs, "friendly_ai", []))
    wave_number = getattr(gs, "wave_number", 0)
    
    app_ctx.telemetry_client.log_frame_time(
        FrameTimeEvent(
            t=now,
            frame_time_ms=frame_time_ms,
            fps=fps,
            player_bullets=player_bullets,
            enemy_projectiles=enemy_projectiles,
            enemies=enemies,
            friendly_projectiles=friendly_projectiles,
            missiles=missiles,
            explosions=explosions,
            laser_beams=laser_beams,
            damage_numbers=damage_numbers,
            friendly_ai=friendly_ai,
            wave_number=wave_number,
        )
    )


def reset_frame_time_sampling() -> None:
    """Reset frame time sampling (call on new run)."""
    global _last_frame_time_sample_t
    _last_frame_time_sample_t = -1.0
