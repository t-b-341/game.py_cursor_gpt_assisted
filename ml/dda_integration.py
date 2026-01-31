"""DDA (Dynamic Difficulty Adjustment) integration with game systems.

This module provides hooks to integrate ML-based difficulty adjustment
with the wave spawning system.

Usage:
    from ml.dda_integration import dda

    # At wave start
    dda.on_wave_start(state, wave_number, hp_scale, speed_scale, enemies_spawned)

    # During gameplay (call as events happen)
    dda.on_shot_fired()
    dda.on_shot_hit()
    dda.on_damage_dealt(damage)
    dda.on_damage_taken(damage)
    dda.on_player_death()
    dda.on_pickup_collected()
    dda.on_ability_used()
    dda.on_enemy_killed()

    # At wave end
    dda.on_wave_end(state, telemetry)

    # Get difficulty adjustment for next wave
    adjustment = dda.get_difficulty_adjustment()
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .wave_tracker import WaveTracker

if TYPE_CHECKING:
    from state import GameState
    from telemetry import Telemetry


class DDAIntegration:
    """Integration layer for Dynamic Difficulty Adjustment.
    
    Tracks wave performance and provides difficulty adjustments.
    Uses ML model if trained, otherwise falls back to heuristics.
    """
    
    def __init__(self):
        self._tracker = WaveTracker()
        self._model = None
        self._last_summary = None
        self._last_adjustment: Optional[dict] = None
        self._enabled = True
        
    def _get_model(self):
        """Lazy-load the DDA model."""
        if self._model is None:
            try:
                from .dda_model import get_dda_model
                self._model = get_dda_model()
            except Exception:
                # Model loading failed, will use fallback
                pass
        return self._model
    
    def enable(self) -> None:
        """Enable DDA."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable DDA (use base difficulty)."""
        self._enabled = False
    
    def is_enabled(self) -> bool:
        """Check if DDA is enabled."""
        return self._enabled
    
    def reset(self) -> None:
        """Reset tracker for new run."""
        self._tracker.reset()
        self._last_summary = None
        self._last_adjustment = None
    
    def on_wave_start(
        self,
        state: "GameState",
        wave_number: int,
        hp_scale: float,
        speed_scale: float,
        enemies_spawned: int,
    ) -> None:
        """Call when a new wave starts."""
        run_time = getattr(state, "run_time", 0.0)
        self._tracker.on_wave_start(
            wave_number=wave_number,
            hp_scale=hp_scale,
            speed_scale=speed_scale,
            enemies_spawned=enemies_spawned,
            state=state,
            run_time=run_time,
        )
    
    def on_wave_end(
        self,
        state: "GameState",
        telemetry: Optional["Telemetry"] = None,
    ) -> Optional[dict]:
        """Call when wave ends. Returns adjustment for next wave.
        
        Args:
            state: Current game state
            telemetry: Telemetry instance for logging (optional)
        
        Returns:
            Difficulty adjustment dict or None
        """
        run_time = getattr(state, "run_time", 0.0)
        summary_event = self._tracker.on_wave_end(state, run_time)
        
        if summary_event is None:
            return None
        
        self._last_summary = summary_event
        
        # Log to telemetry if available
        if telemetry is not None:
            try:
                telemetry.log_wave_summary(summary_event)
            except Exception:
                pass  # Don't fail gameplay for telemetry errors
        
        # Calculate adjustment for next wave
        if self._enabled:
            self._last_adjustment = self._calculate_adjustment(summary_event)
        else:
            self._last_adjustment = None
        
        return self._last_adjustment
    
    def _calculate_adjustment(self, summary) -> dict:
        """Calculate difficulty adjustment from wave summary."""
        model = self._get_model()
        if model is None:
            return self._fallback_adjustment(summary)
        
        # Convert event to dict for model
        wave_stats = {
            "accuracy_pct": summary.accuracy_pct,
            "kills_per_second": summary.kills_per_second,
            "damage_per_second": summary.damage_per_second,
            "damage_taken": summary.damage_taken,
            "deaths_this_wave": summary.deaths_this_wave,
            "pickups_collected": summary.pickups_collected,
            "abilities_used": summary.abilities_used,
            "wave_duration_sec": summary.wave_duration_sec,
            "hp_scale": summary.hp_scale,
            "speed_scale": summary.speed_scale,
            "enemies_spawned": summary.enemies_spawned,
            "player_hp_start": summary.player_hp_start,
            "player_hp_pct_end": summary.player_hp_pct_end,
            "outcome": summary.outcome,
        }
        
        return model.predict(wave_stats)
    
    def _fallback_adjustment(self, summary) -> dict:
        """Simple heuristic fallback for difficulty adjustment."""
        outcome = summary.outcome
        
        adjustments = {
            "died": {"hp_mult": 0.85, "speed_mult": 0.85, "spawn_mult": 0.8, "projectile_speed_mult": 0.85},
            "struggled": {"hp_mult": 0.95, "speed_mult": 0.95, "spawn_mult": 0.9, "projectile_speed_mult": 0.95},
            "challenged": {"hp_mult": 1.0, "speed_mult": 1.0, "spawn_mult": 1.0, "projectile_speed_mult": 1.0},
            "comfortable": {"hp_mult": 1.1, "speed_mult": 1.05, "spawn_mult": 1.05, "projectile_speed_mult": 1.0},
            "dominated": {"hp_mult": 1.2, "speed_mult": 1.15, "spawn_mult": 1.2, "projectile_speed_mult": 1.1},
        }
        
        return adjustments.get(outcome, adjustments["challenged"])
    
    def get_difficulty_adjustment(self) -> Optional[dict]:
        """Get the last calculated difficulty adjustment.
        
        Returns dict with:
            - hp_mult: Enemy HP multiplier
            - speed_mult: Enemy speed multiplier
            - spawn_mult: Spawn count multiplier
            - projectile_speed_mult: Projectile speed multiplier
        """
        return self._last_adjustment
    
    def get_last_outcome(self) -> Optional[str]:
        """Get the outcome of the last wave."""
        if self._last_summary is None:
            return None
        return self._last_summary.outcome
    
    # Event handlers (delegate to tracker)
    def on_shot_fired(self) -> None:
        """Regular left-click shot fired."""
        self._tracker.on_shot_fired()
    
    def on_shot_hit(self) -> None:
        """Regular shot hit enemy."""
        self._tracker.on_shot_hit()
    
    def on_damage_dealt(self, damage: int) -> None:
        self._tracker.on_damage_dealt(damage)
    
    def on_damage_taken(self, damage: int) -> None:
        self._tracker.on_damage_taken(damage)
    
    def on_player_death(self) -> None:
        self._tracker.on_player_death()
    
    def on_pickup_collected(self) -> None:
        self._tracker.on_pickup_collected()
    
    def on_ability_used(self) -> None:
        self._tracker.on_ability_used()
    
    def on_enemy_killed(self, weapon: str = "shot") -> None:
        """Enemy killed. weapon: 'shot', 'rocket', 'grenade', 'laser', 'other'."""
        self._tracker.on_enemy_killed(weapon)
    
    # Weapon-specific tracking
    def on_rocket_fired(self) -> None:
        """Rocket/missile fired (R key)."""
        self._tracker.on_rocket_fired()
    
    def on_rocket_hit(self) -> None:
        """Rocket hit an enemy."""
        self._tracker.on_rocket_hit()
    
    def on_grenade_thrown(self) -> None:
        """Grenade thrown (E key)."""
        self._tracker.on_grenade_thrown()
    
    def on_laser_active(self, dt: float) -> None:
        """Laser beam active for dt seconds."""
        self._tracker.on_laser_active(dt)


# Global singleton instance
_dda: Optional[DDAIntegration] = None


def get_dda() -> DDAIntegration:
    """Get the global DDA integration instance."""
    global _dda
    if _dda is None:
        _dda = DDAIntegration()
    return _dda


# Convenience shortcut
dda = get_dda()
