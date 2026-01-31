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
    # Additional entity counts for performance analysis
    missiles: int = 0  # Number of active missiles
    explosions: int = 0  # Number of active explosions
    laser_beams: int = 0  # Number of active laser beams
    damage_numbers: int = 0  # Number of floating damage numbers
    friendly_ai: int = 0  # Number of friendly AI units
    wave_number: int = 0  # Current wave (for correlation)


@dataclass
class WaveSummaryEvent:
    """Per-wave summary for ML training (Dynamic Difficulty Adjustment).
    
    Logged at the end of each wave to capture player performance.
    Used as training data for difficulty prediction models.
    """
    wave_number: int
    wave_start_t: float
    wave_end_t: float
    wave_duration_sec: float
    
    # Difficulty settings that were applied
    hp_scale: float
    speed_scale: float
    enemies_spawned: int
    
    # Player performance metrics
    shots_fired: int
    shots_hit: int
    accuracy_pct: float
    damage_dealt: int
    damage_taken: int
    deaths_this_wave: int
    pickups_collected: int
    abilities_used: int
    enemies_killed: int
    
    # Weapon-specific tracking
    rockets_fired: int = 0
    rockets_hit: int = 0
    rocket_kills: int = 0
    grenades_thrown: int = 0
    grenade_kills: int = 0
    laser_time: float = 0.0
    laser_kills: int = 0
    
    # Player state
    player_hp_start: int = 0
    player_hp_end: int = 0
    player_hp_pct_end: float = 0.0
    
    # Derived metrics
    kills_per_second: float = 0.0
    damage_per_second: float = 0.0
    
    # Outcome label: 'dominated' (hp>80%), 'comfortable' (hp 50-80%), 
    #                'challenged' (hp 20-50%), 'struggled' (hp 1-20%), 'died' (hp=0)
    outcome: str = "unknown"
