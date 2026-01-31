"""Feature extraction for DDA model training.

Converts wave summary data into normalized feature vectors for ML training.
"""
from __future__ import annotations

from typing import Any, Optional
import sqlite3

# Feature names in order (for model interpretation)
FEATURE_NAMES = [
    "combat_effectiveness",   # Combined metric: kills / total attacks (weapon-agnostic)
    "kills_per_second",       # Typically 0-5, normalized
    "damage_per_second",      # Typically 0-1000, normalized
    "damage_taken_rate",      # Damage taken per second
    "deaths_this_wave",       # 0-3 typically
    "pickups_per_minute",     # Resource management
    "abilities_per_minute",   # Skill usage rate (rockets, grenades, etc.)
    "wave_duration_sec",      # How long wave lasted
    "current_hp_scale",       # Difficulty applied
    "current_speed_scale",    # Difficulty applied
    "enemies_spawned",        # Wave intensity
    "hp_pct_at_start",        # Starting condition
    "rocket_preference",      # How much player relies on rockets vs shots
    "grenade_usage_rate",     # Grenades per minute
]

# Normalization constants (based on expected ranges)
FEATURE_NORMS = {
    "combat_effectiveness": 1.0,  # Already 0-1 (kills / attacks)
    "kills_per_second": 5.0,
    "damage_per_second": 1000.0,
    "damage_taken_rate": 200.0,
    "deaths_this_wave": 3.0,
    "pickups_per_minute": 10.0,
    "abilities_per_minute": 30.0,
    "wave_duration_sec": 120.0,
    "current_hp_scale": 2.0,
    "current_speed_scale": 2.0,
    "enemies_spawned": 50.0,
    "hp_pct_at_start": 1.0,
    "rocket_preference": 1.0,  # 0 = all shots, 1 = all rockets
    "grenade_usage_rate": 10.0,  # Grenades per minute
}


def extract_wave_features(row: dict) -> list[float]:
    """Extract normalized features from a wave_summaries row.
    
    Args:
        row: Dictionary with wave summary data (from DB or WaveStats)
    
    Returns:
        List of normalized feature values in FEATURE_NAMES order
    """
    duration = row.get("wave_duration_sec", 1.0) or 1.0
    duration_min = duration / 60.0
    
    # Calculate combat effectiveness (weapon-agnostic)
    # This works whether player uses shots, rockets, or grenades
    shots = row.get("shots_fired", 0) or 0
    rockets = row.get("rockets_fired", 0) or 0
    grenades = row.get("grenades_thrown", 0) or 0
    kills = row.get("enemies_killed", 0) or 0
    
    # Total offensive actions (weight rockets x3 since they fire 3 missiles)
    total_attacks = shots + (rockets * 3) + grenades
    combat_effectiveness = kills / max(1, total_attacks) if total_attacks > 0 else 0.0
    
    # Rocket preference: 0 = all shots, 1 = all rockets
    # This helps the model understand playstyle
    rocket_attacks = rockets * 3
    shot_attacks = shots
    if rocket_attacks + shot_attacks > 0:
        rocket_preference = rocket_attacks / (rocket_attacks + shot_attacks)
    else:
        rocket_preference = 0.5  # Neutral if no attacks
    
    # Grenades per minute
    grenade_rate = grenades / max(0.1, duration_min)
    
    features = [
        combat_effectiveness / FEATURE_NORMS["combat_effectiveness"],
        (row.get("kills_per_second", 0) or 0) / FEATURE_NORMS["kills_per_second"],
        (row.get("damage_per_second", 0) or 0) / FEATURE_NORMS["damage_per_second"],
        ((row.get("damage_taken", 0) or 0) / duration) / FEATURE_NORMS["damage_taken_rate"],
        (row.get("deaths_this_wave", 0) or 0) / FEATURE_NORMS["deaths_this_wave"],
        ((row.get("pickups_collected", 0) or 0) / max(0.1, duration_min)) / FEATURE_NORMS["pickups_per_minute"],
        ((row.get("abilities_used", 0) or 0) / max(0.1, duration_min)) / FEATURE_NORMS["abilities_per_minute"],
        duration / FEATURE_NORMS["wave_duration_sec"],
        (row.get("hp_scale", 1.0) or 1.0) / FEATURE_NORMS["current_hp_scale"],
        (row.get("speed_scale", 1.0) or 1.0) / FEATURE_NORMS["current_speed_scale"],
        (row.get("enemies_spawned", 0) or 0) / FEATURE_NORMS["enemies_spawned"],
        (row.get("player_hp_start", 100) or 100) / (row.get("player_max_hp", 100) or 100),
        rocket_preference / FEATURE_NORMS["rocket_preference"],
        grenade_rate / FEATURE_NORMS["grenade_usage_rate"],
    ]
    
    # Clamp all features to [0, 1]
    return [max(0.0, min(1.0, f)) for f in features]


def extract_difficulty_target(row: dict) -> list[float]:
    """Extract target difficulty parameters from a wave summary.
    
    The target is based on the outcome: if player struggled/died, lower difficulty;
    if dominated, increase difficulty.
    
    Returns:
        [hp_mult, speed_mult, spawn_mult, projectile_speed_mult] in range [0, 1]
    """
    outcome = row.get("outcome", "comfortable")
    hp_scale = row.get("hp_scale", 1.0) or 1.0
    speed_scale = row.get("speed_scale", 1.0) or 1.0
    
    # Adjustment factors based on outcome
    adjustments = {
        "died": -0.15,        # Significantly easier
        "struggled": -0.08,   # Somewhat easier
        "challenged": 0.0,    # Just right, maintain
        "comfortable": 0.05,  # Slightly harder
        "dominated": 0.12,    # Much harder
    }
    
    adjustment = adjustments.get(outcome, 0.0)
    
    # Calculate target difficulty (what we should have used)
    target_hp = (hp_scale + adjustment * 0.8) / 2.0  # Normalize to 0-1 (assuming max 2.0)
    target_speed = (speed_scale + adjustment * 0.6) / 2.0
    target_spawn = 0.5 + adjustment  # Base 0.5, adjust up/down
    target_proj_speed = 0.5 + adjustment * 0.5  # Smaller adjustment for projectile speed
    
    return [
        max(0.0, min(1.0, target_hp)),
        max(0.0, min(1.0, target_speed)),
        max(0.0, min(1.0, target_spawn)),
        max(0.0, min(1.0, target_proj_speed)),
    ]


def load_training_data(db_path: str = "game_telemetry.db") -> tuple[list[list[float]], list[list[float]]]:
    """Load training data from telemetry database.
    
    Args:
        db_path: Path to SQLite database
    
    Returns:
        (features, targets) tuple where each is a list of samples
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("""
        SELECT * FROM wave_summaries 
        WHERE wave_duration_sec > 5  -- Filter out very short waves
        AND enemies_spawned > 0      -- Filter out empty waves
        ORDER BY run_id, wave_number
    """)
    
    features = []
    targets = []
    
    for row in cursor:
        row_dict = dict(row)
        features.append(extract_wave_features(row_dict))
        targets.append(extract_difficulty_target(row_dict))
    
    conn.close()
    return features, targets


def get_training_stats(db_path: str = "game_telemetry.db") -> dict:
    """Get statistics about available training data.
    
    Returns:
        Dictionary with counts and distribution info
    """
    conn = sqlite3.connect(db_path)
    
    stats = {}
    
    # Total wave summaries
    cursor = conn.execute("SELECT COUNT(*) FROM wave_summaries")
    stats["total_waves"] = cursor.fetchone()[0]
    
    # Outcome distribution
    cursor = conn.execute("""
        SELECT outcome, COUNT(*) as count 
        FROM wave_summaries 
        GROUP BY outcome
    """)
    stats["outcomes"] = {row[0]: row[1] for row in cursor}
    
    # Run count
    cursor = conn.execute("SELECT COUNT(DISTINCT run_id) FROM wave_summaries")
    stats["total_runs"] = cursor.fetchone()[0]
    
    # Average wave duration
    cursor = conn.execute("SELECT AVG(wave_duration_sec) FROM wave_summaries")
    stats["avg_wave_duration"] = cursor.fetchone()[0]
    
    conn.close()
    return stats
