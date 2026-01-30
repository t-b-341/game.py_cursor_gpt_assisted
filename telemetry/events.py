"""
Event value types for telemetry. Used when logging shots, spawns, hits, etc.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class EnemySpawnEvent:
    t: float
    enemy_type: str
    x: int
    y: int
    w: int
    h: int
    hp: int


@dataclass
class PlayerPosEvent:
    t: float
    x: int
    y: int


@dataclass
class ShotEvent:
    t: float
    origin_x: int
    origin_y: int
    target_x: int
    target_y: int
    dir_x: float
    dir_y: float


@dataclass
class EnemyHitEvent:
    t: float
    enemy_type: str
    enemy_x: int
    enemy_y: int
    damage: int
    enemy_hp_after: int
    killed: bool


@dataclass
class PlayerDamageEvent:
    t: float
    amount: int
    source_type: str
    source_enemy_type: Optional[str]
    player_x: int
    player_y: int
    player_hp_after: int


@dataclass
class PlayerDeathEvent:
    t: float
    player_x: int
    player_y: int
    lives_left: int
    wave_number: int = 0  # Wave when death occurred (for death-position viz)


@dataclass
class WaveEvent:
    t: float
    wave_number: int
    event_type: str
    enemies_spawned: int
    hp_scale: float
    speed_scale: float


@dataclass
class WaveEnemyTypeEvent:
    t: float
    wave_number: int
    enemy_type: str
    count: int


@dataclass
class EnemyPositionEvent:
    t: float
    enemy_type: str
    x: int
    y: int
    speed: float
    vel_x: float
    vel_y: float


@dataclass
class PlayerVelocityEvent:
    t: float
    x: int
    y: int
    vel_x: float
    vel_y: float
    speed: float


@dataclass
class BulletMetadataEvent:
    t: float
    bullet_type: str
    shape: str
    color_r: int
    color_g: int
    color_b: int
    source_enemy_type: Optional[str] = None


@dataclass
class ScoreEvent:
    t: float
    score: int
    score_change: int
    source: str


@dataclass
class LevelEvent:
    t: float
    level: int
    level_name: str


@dataclass
class BossEvent:
    t: float
    wave_number: int
    phase: int
    hp: int
    max_hp: int
    event_type: str


@dataclass
class WeaponSwitchEvent:
    t: float
    weapon_mode: str


@dataclass
class PickupEvent:
    t: float
    pickup_type: str
    x: int
    y: int
    collected: bool


@dataclass
class OvershieldEvent:
    t: float
    overshield: int
    max_overshield: int
    change: int


@dataclass
class PlayerActionEvent:
    t: float
    action_type: str
    x: int
    y: int
    duration: Optional[float] = None
    success: bool = True


@dataclass
class ZoneVisitEvent:
    t: float
    zone_id: int
    zone_name: str
    zone_type: str
    event_type: str
    x: int
    y: int


@dataclass
class FriendlyAISpawnEvent:
    t: float
    friendly_type: str
    x: int
    y: int
    w: int
    h: int
    hp: int
    behavior: str


@dataclass
class FriendlyAIPositionEvent:
    t: float
    friendly_type: str
    x: int
    y: int
    speed: float
    vel_x: float
    vel_y: float
    target_enemy_type: Optional[str]


@dataclass
class FriendlyAIShotEvent:
    t: float
    friendly_type: str
    origin_x: int
    origin_y: int
    target_x: int
    target_y: int
    target_enemy_type: str


@dataclass
class FriendlyAIDeathEvent:
    t: float
    friendly_type: str
    x: int
    y: int
    killed_by: str


@dataclass
class FrameTimeEvent:
    """Frame timing data for performance analysis."""
    t: float  # Game time when frame was recorded
    frame_time_ms: float  # Frame duration in milliseconds
    fps: float  # Instantaneous FPS (1000 / frame_time_ms)
    player_bullets: int  # Number of player bullets
    enemy_projectiles: int  # Number of enemy projectiles
    enemies: int  # Number of enemies
    friendly_projectiles: int  # Number of friendly projectiles
