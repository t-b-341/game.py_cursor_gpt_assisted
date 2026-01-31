"""Wave performance tracker for ML data collection.

Tracks per-wave statistics during gameplay and generates WaveSummaryEvents
for training the Dynamic Difficulty Adjustment model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from state import GameState
    from telemetry import Telemetry


def calculate_outcome(hp_pct: float, died: bool) -> str:
    """Calculate outcome label from HP percentage.
    
    Args:
        hp_pct: Player HP as percentage (0.0 to 1.0)
        died: Whether player died during the wave
    
    Returns:
        One of: 'died', 'struggled', 'challenged', 'comfortable', 'dominated'
    """
    if died or hp_pct <= 0:
        return "died"
    elif hp_pct < 0.2:
        return "struggled"
    elif hp_pct < 0.5:
        return "challenged"  # Ideal difficulty
    elif hp_pct < 0.8:
        return "comfortable"
    else:
        return "dominated"


@dataclass
class WaveStats:
    """Statistics for a single wave."""
    wave_number: int = 0
    wave_start_t: float = 0.0
    wave_end_t: Optional[float] = None
    
    # Difficulty settings
    hp_scale: float = 1.0
    speed_scale: float = 1.0
    enemies_spawned: int = 0
    
    # Counters (accumulated during wave)
    shots_fired: int = 0
    shots_hit: int = 0
    damage_dealt: int = 0
    damage_taken: int = 0
    deaths_this_wave: int = 0
    pickups_collected: int = 0
    abilities_used: int = 0  # Grenade, missile, shield, dash
    enemies_killed: int = 0
    
    # Weapon-specific tracking
    rockets_fired: int = 0
    rockets_hit: int = 0
    rocket_kills: int = 0
    grenades_thrown: int = 0
    grenade_kills: int = 0
    laser_time: float = 0.0  # Seconds of laser active
    laser_kills: int = 0
    
    # Player state
    player_hp_start: int = 0
    player_hp_end: int = 0
    player_max_hp: int = 100
    
    def get_accuracy_pct(self) -> float:
        """Calculate accuracy percentage (regular shots only)."""
        if self.shots_fired == 0:
            return 0.0
        return (self.shots_hit / self.shots_fired) * 100.0
    
    def get_rocket_accuracy_pct(self) -> float:
        """Calculate rocket hit percentage."""
        if self.rockets_fired == 0:
            return 0.0
        return (self.rockets_hit / self.rockets_fired) * 100.0
    
    def get_total_attacks(self) -> int:
        """Total offensive actions (shots + rockets + grenades)."""
        return self.shots_fired + self.rockets_fired + self.grenades_thrown
    
    def get_primary_weapon(self) -> str:
        """Determine player's primary weapon this wave based on usage."""
        usage = {
            "shots": self.shots_fired,
            "rockets": self.rockets_fired * 3,  # Weight rockets (3 missiles per use)
            "grenades": self.grenades_thrown,
            "laser": int(self.laser_time * 2),  # Approximate laser shots
        }
        if max(usage.values()) == 0:
            return "none"
        return max(usage, key=usage.get)
    
    def get_duration_sec(self) -> float:
        """Get wave duration in seconds."""
        if self.wave_end_t is None:
            return 0.0
        return self.wave_end_t - self.wave_start_t
    
    def get_hp_pct_end(self) -> float:
        """Get player HP percentage at wave end."""
        if self.player_max_hp <= 0:
            return 0.0
        return self.player_hp_end / self.player_max_hp
    
    def get_kills_per_second(self) -> float:
        """Calculate kills per second."""
        duration = self.get_duration_sec()
        if duration <= 0:
            return 0.0
        return self.enemies_killed / duration
    
    def get_damage_per_second(self) -> float:
        """Calculate damage dealt per second."""
        duration = self.get_duration_sec()
        if duration <= 0:
            return 0.0
        return self.damage_dealt / duration
    
    def get_outcome(self) -> str:
        """Get outcome label for ML training."""
        return calculate_outcome(self.get_hp_pct_end(), self.deaths_this_wave > 0)


class WaveTracker:
    """Tracks wave performance metrics for ML training.
    
    Usage:
        tracker = WaveTracker()
        
        # At wave start
        tracker.on_wave_start(wave_num, hp_scale, speed_scale, enemies_spawned, state)
        
        # During wave (call these as events occur)
        tracker.on_shot_fired()
        tracker.on_shot_hit()
        tracker.on_damage_dealt(damage)
        tracker.on_damage_taken(damage)
        tracker.on_player_death()
        tracker.on_pickup_collected()
        tracker.on_ability_used()
        tracker.on_enemy_killed()
        
        # At wave end
        summary_event = tracker.on_wave_end(state, run_time)
        telemetry.log_wave_summary(summary_event)
    """
    
    def __init__(self):
        self._current: Optional[WaveStats] = None
        self._history: list[WaveStats] = []
    
    def on_wave_start(
        self,
        wave_number: int,
        hp_scale: float,
        speed_scale: float,
        enemies_spawned: int,
        state: "GameState",
        run_time: float,
    ) -> None:
        """Call when a new wave starts."""
        # Save previous wave if exists
        if self._current is not None:
            self._history.append(self._current)
        
        # Start tracking new wave
        self._current = WaveStats(
            wave_number=wave_number,
            wave_start_t=run_time,
            hp_scale=hp_scale,
            speed_scale=speed_scale,
            enemies_spawned=enemies_spawned,
            player_hp_start=getattr(state, "player_hp", 100),
            player_max_hp=getattr(state, "player_max_hp", 100),
        )
    
    def on_wave_end(self, state: "GameState", run_time: float) -> Optional["WaveSummaryEvent"]:
        """Call when wave ends. Returns a WaveSummaryEvent for logging."""
        if self._current is None:
            return None
        
        from telemetry import WaveSummaryEvent
        
        self._current.wave_end_t = run_time
        self._current.player_hp_end = getattr(state, "player_hp", 0)
        
        event = WaveSummaryEvent(
            wave_number=self._current.wave_number,
            wave_start_t=self._current.wave_start_t,
            wave_end_t=self._current.wave_end_t,
            wave_duration_sec=self._current.get_duration_sec(),
            hp_scale=self._current.hp_scale,
            speed_scale=self._current.speed_scale,
            enemies_spawned=self._current.enemies_spawned,
            shots_fired=self._current.shots_fired,
            shots_hit=self._current.shots_hit,
            accuracy_pct=self._current.get_accuracy_pct(),
            damage_dealt=self._current.damage_dealt,
            damage_taken=self._current.damage_taken,
            deaths_this_wave=self._current.deaths_this_wave,
            pickups_collected=self._current.pickups_collected,
            abilities_used=self._current.abilities_used,
            enemies_killed=self._current.enemies_killed,
            # Weapon-specific tracking
            rockets_fired=self._current.rockets_fired,
            rockets_hit=self._current.rockets_hit,
            rocket_kills=self._current.rocket_kills,
            grenades_thrown=self._current.grenades_thrown,
            grenade_kills=self._current.grenade_kills,
            laser_time=self._current.laser_time,
            laser_kills=self._current.laser_kills,
            # Player state
            player_hp_start=self._current.player_hp_start,
            player_hp_end=self._current.player_hp_end,
            player_hp_pct_end=self._current.get_hp_pct_end(),
            kills_per_second=self._current.get_kills_per_second(),
            damage_per_second=self._current.get_damage_per_second(),
            outcome=self._current.get_outcome(),
        )
        
        # Save to history
        self._history.append(self._current)
        self._current = None
        
        return event
    
    # Event handlers for tracking during wave
    def on_shot_fired(self) -> None:
        """Regular left-click shot fired."""
        if self._current:
            self._current.shots_fired += 1
    
    def on_shot_hit(self) -> None:
        """Regular shot hit an enemy."""
        if self._current:
            self._current.shots_hit += 1
    
    def on_damage_dealt(self, damage: int) -> None:
        if self._current:
            self._current.damage_dealt += damage
    
    def on_damage_taken(self, damage: int) -> None:
        if self._current:
            self._current.damage_taken += damage
    
    def on_player_death(self) -> None:
        if self._current:
            self._current.deaths_this_wave += 1
    
    def on_pickup_collected(self) -> None:
        if self._current:
            self._current.pickups_collected += 1
    
    def on_ability_used(self) -> None:
        if self._current:
            self._current.abilities_used += 1
    
    def on_enemy_killed(self, weapon: str = "shot") -> None:
        """Enemy killed. weapon can be: 'shot', 'rocket', 'grenade', 'laser', 'other'."""
        if self._current:
            self._current.enemies_killed += 1
            if weapon == "rocket":
                self._current.rocket_kills += 1
            elif weapon == "grenade":
                self._current.grenade_kills += 1
            elif weapon == "laser":
                self._current.laser_kills += 1
    
    # Weapon-specific tracking
    def on_rocket_fired(self) -> None:
        """Rocket/missile fired (R key)."""
        if self._current:
            self._current.rockets_fired += 1
            self._current.abilities_used += 1
    
    def on_rocket_hit(self) -> None:
        """Rocket hit an enemy."""
        if self._current:
            self._current.rockets_hit += 1
    
    def on_grenade_thrown(self) -> None:
        """Grenade thrown (E key)."""
        if self._current:
            self._current.grenades_thrown += 1
            self._current.abilities_used += 1
    
    def on_laser_active(self, dt: float) -> None:
        """Laser beam active for dt seconds."""
        if self._current:
            self._current.laser_time += dt
    
    def get_current_stats(self) -> Optional[WaveStats]:
        """Get current wave stats (for real-time display)."""
        return self._current
    
    def get_history(self) -> list[WaveStats]:
        """Get history of completed waves."""
        return self._history.copy()
    
    def reset(self) -> None:
        """Reset tracker for new run."""
        self._current = None
        self._history.clear()
