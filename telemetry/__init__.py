"""
Telemetry package: structured logging of game events to SQLite.
Public API for the rest of the game.
"""
from .events import (
    BossEvent,
    BulletMetadataEvent,
    EnemyHitEvent,
    EnemyPositionEvent,
    EnemySpawnEvent,
    FrameTimeEvent,
    FriendlyAIDeathEvent,
    FriendlyAIPositionEvent,
    FriendlyAIShotEvent,
    FriendlyAISpawnEvent,
    LevelEvent,
    OvershieldEvent,
    PickupEvent,
    PlayerActionEvent,
    PlayerDamageEvent,
    PlayerDeathEvent,
    PlayerPosEvent,
    PlayerVelocityEvent,
    ScoreEvent,
    ShotEvent,
    WaveEnemyTypeEvent,
    WaveEvent,
    WeaponSwitchEvent,
    ZoneVisitEvent,
)
from .writer import NoOpTelemetry, Telemetry


def init_telemetry(
    db_path: str = "game_telemetry.db",
    flush_interval_s: float = 0.5,
    max_buffer: int = 500,
) -> Telemetry:
    """Create and return a Telemetry instance ready to log. Call start_run when a game run begins."""
    return Telemetry(db_path=db_path, flush_interval_s=flush_interval_s, max_buffer=max_buffer)


__all__ = [
    "init_telemetry",
    "Telemetry",
    "NoOpTelemetry",
    "EnemySpawnEvent",
    "PlayerPosEvent",
    "ShotEvent",
    "EnemyHitEvent",
    "PlayerDamageEvent",
    "PlayerDeathEvent",
    "WaveEvent",
    "WaveEnemyTypeEvent",
    "EnemyPositionEvent",
    "PlayerVelocityEvent",
    "BulletMetadataEvent",
    "ScoreEvent",
    "LevelEvent",
    "BossEvent",
    "WeaponSwitchEvent",
    "PickupEvent",
    "OvershieldEvent",
    "PlayerActionEvent",
    "ZoneVisitEvent",
    "FriendlyAISpawnEvent",
    "FriendlyAIPositionEvent",
    "FriendlyAIShotEvent",
    "FriendlyAIDeathEvent",
    "FrameTimeEvent",
]
