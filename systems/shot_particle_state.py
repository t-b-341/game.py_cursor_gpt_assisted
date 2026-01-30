"""
Shot particle state for GPU shader effects.

Tracks recent player shots, rockets, and bombs to feed position/strength uniforms 
to the shot_particle_burst shader. Keeps only the most recent effects and
fades them out over their respective lifetimes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum


class EffectType(Enum):
    """Type of particle effect."""
    SHOT = "shot"       # Regular bullet - small, quick fade
    ROCKET = "rocket"   # Rocket/missile - medium, orange glow
    BOMB = "bomb"       # Grenade/explosion - large, bright flash


# Effect type configurations: (lifetime, base_strength, radius_multiplier)
EFFECT_CONFIGS = {
    EffectType.SHOT: (0.20, 1.0, 1.0),
    EffectType.ROCKET: (0.35, 1.5, 1.5),
    EffectType.BOMB: (0.50, 2.0, 2.5),
}


@dataclass
class ShotData:
    """Data for a single shot/effect."""
    screen_pos: Tuple[float, float]  # Normalized [0,1] screen space
    time_since_shot: float = 0.0
    effect_type: EffectType = EffectType.SHOT
    
    @property
    def lifetime(self) -> float:
        """Get lifetime for this effect type."""
        return EFFECT_CONFIGS[self.effect_type][0]
    
    @property
    def base_strength(self) -> float:
        """Get base strength multiplier for this effect type."""
        return EFFECT_CONFIGS[self.effect_type][1]
    
    @property
    def radius_mult(self) -> float:
        """Get radius multiplier for this effect type."""
        return EFFECT_CONFIGS[self.effect_type][2]


@dataclass
class ShotParticleState:
    """Tracks recent shots for GPU particle effects."""
    recent_shots: List[ShotData] = field(default_factory=list)
    max_shots: int = 5  # Increased to handle multiple effect types
    
    def add_shot(self, screen_pos: Tuple[float, float], effect_type: EffectType = EffectType.SHOT) -> None:
        """Add a new shot at the given screen position (normalized 0-1)."""
        shot = ShotData(screen_pos=screen_pos, time_since_shot=0.0, effect_type=effect_type)
        self.recent_shots.append(shot)
        # Keep only the most recent shots
        if len(self.recent_shots) > self.max_shots:
            self.recent_shots = self.recent_shots[-self.max_shots:]
    
    def add_rocket(self, screen_pos: Tuple[float, float]) -> None:
        """Convenience method to add a rocket effect."""
        self.add_shot(screen_pos, EffectType.ROCKET)
    
    def add_bomb(self, screen_pos: Tuple[float, float]) -> None:
        """Convenience method to add a bomb/grenade effect."""
        self.add_shot(screen_pos, EffectType.BOMB)
    
    def update(self, dt: float) -> None:
        """Update shot timers and remove expired shots."""
        for shot in self.recent_shots:
            shot.time_since_shot += dt
        # Remove expired shots based on their individual lifetimes
        self.recent_shots = [
            s for s in self.recent_shots 
            if s.time_since_shot < s.lifetime
        ]
    
    def get_active_shot(self) -> Optional[ShotData]:
        """Get the most impactful active shot (prioritize bombs > rockets > shots)."""
        if not self.recent_shots:
            return None
        
        # Sort by effect importance (bombs first) and recency
        def importance(s: ShotData) -> Tuple[int, float]:
            type_order = {EffectType.BOMB: 0, EffectType.ROCKET: 1, EffectType.SHOT: 2}
            # Fresh effects (low time_since_shot) have higher priority
            return (type_order[s.effect_type], s.time_since_shot)
        
        return min(self.recent_shots, key=importance)
    
    def get_uniforms(self) -> Tuple[Tuple[float, float], float, float]:
        """
        Get uniforms for the shot_particle_burst shader.
        
        Returns:
            (u_shot_pos, u_shot_strength, u_effect_radius) tuple
        """
        shot = self.get_active_shot()
        if shot is None:
            return ((0.5, 0.5), 0.0, 1.0)
        
        # Calculate strength based on time (1.0 -> 0.0 over lifetime)
        time_ratio = shot.time_since_shot / shot.lifetime
        strength = max(0.0, 1.0 - time_ratio) * shot.base_strength
        
        return (shot.screen_pos, strength, shot.radius_mult)


# Module-level singleton
_shot_particle_state: Optional[ShotParticleState] = None


def get_shot_particle_state() -> ShotParticleState:
    """Get or create the shot particle state singleton."""
    global _shot_particle_state
    if _shot_particle_state is None:
        _shot_particle_state = ShotParticleState()
    return _shot_particle_state


def reset_shot_particle_state() -> None:
    """Reset the shot particle state (e.g., on new game)."""
    global _shot_particle_state
    _shot_particle_state = None
