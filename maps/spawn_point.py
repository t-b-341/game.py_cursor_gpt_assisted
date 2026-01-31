"""Spawn point definitions for map-based enemy spawning."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SpawnPoint:
    """A spawn point on the map where enemies can appear.
    
    Attributes:
        x: Tile X coordinate
        y: Tile Y coordinate
        enemy_pool: List of enemy type IDs that can spawn here
        wave_min: Minimum wave number for this spawn to activate
        wave_max: Maximum wave number (None = no limit)
        max_spawns: Maximum times this point can spawn (-1 = unlimited)
        spawn_delay: Delay in seconds between spawns from this point
        is_boss_spawn: If True, this is a boss spawn location
    """
    x: int
    y: int
    enemy_pool: list[str] = field(default_factory=lambda: ["grunt"])
    wave_min: int = 1
    wave_max: int | None = None
    max_spawns: int = -1  # -1 = unlimited
    spawn_delay: float = 0.0
    is_boss_spawn: bool = False
    
    # Runtime state (not saved)
    times_spawned: int = field(default=0, repr=False)
    
    def can_spawn_on_wave(self, wave: int) -> bool:
        """Check if this spawn point is active for the given wave."""
        if wave < self.wave_min:
            return False
        if self.wave_max is not None and wave > self.wave_max:
            return False
        if self.max_spawns >= 0 and self.times_spawned >= self.max_spawns:
            return False
        return True
    
    def get_random_enemy_type(self) -> str | None:
        """Get a random enemy type from the pool."""
        import random
        if not self.enemy_pool:
            return None
        return random.choice(self.enemy_pool)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "x": self.x,
            "y": self.y,
            "enemy_pool": self.enemy_pool.copy(),
            "wave_min": self.wave_min,
            "wave_max": self.wave_max,
            "max_spawns": self.max_spawns,
            "spawn_delay": self.spawn_delay,
            "is_boss_spawn": self.is_boss_spawn,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpawnPoint:
        """Create from dict."""
        return cls(
            x=data.get("x", 0),
            y=data.get("y", 0),
            enemy_pool=data.get("enemy_pool", ["grunt"]),
            wave_min=data.get("wave_min", 1),
            wave_max=data.get("wave_max"),
            max_spawns=data.get("max_spawns", -1),
            spawn_delay=data.get("spawn_delay", 0.0),
            is_boss_spawn=data.get("is_boss_spawn", False),
        )


# Common enemy pools for quick selection
ENEMY_POOLS = {
    "basic": ["grunt", "fast"],
    "mixed": ["grunt", "fast", "tank", "sniper"],
    "heavy": ["tank", "elite"],
    "suicide": ["suicide"],
    "spawners": ["spawner"],
    "all": ["grunt", "fast", "tank", "sniper", "elite", "suicide", "spawner"],
}


def get_available_enemy_types() -> list[str]:
    """Get list of all available enemy types for spawn pools."""
    try:
        from config.enemy_data import ENEMY_TEMPLATES
        return [t.get("type", "unknown") for t in ENEMY_TEMPLATES if not t.get("is_ambient")]
    except ImportError:
        return ["grunt", "fast", "tank", "sniper", "elite", "suicide", "spawner"]
