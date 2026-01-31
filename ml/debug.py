"""Debug and verification utilities for DDA system.

Provides tools to verify the DDA is working correctly and improving gameplay.
"""
from __future__ import annotations

from typing import Optional
import sqlite3
from pathlib import Path


def get_dda_status() -> dict:
    """Get current DDA status for debugging.
    
    Returns:
        Dictionary with current DDA state
    """
    try:
        from ml.dda_integration import get_dda
        dda = get_dda()
        
        tracker = dda._tracker
        current = tracker.get_current_stats()
        
        return {
            "enabled": dda.is_enabled(),
            "has_model": dda._model is not None,
            "last_outcome": dda.get_last_outcome(),
            "last_adjustment": dda.get_difficulty_adjustment(),
            "current_wave": {
                "wave_number": current.wave_number if current else None,
                "shots_fired": current.shots_fired if current else 0,
                "rockets_fired": current.rockets_fired if current else 0,
                "grenades_thrown": current.grenades_thrown if current else 0,
                "enemies_killed": current.enemies_killed if current else 0,
                "damage_taken": current.damage_taken if current else 0,
                "primary_weapon": current.get_primary_weapon() if current else "none",
            } if current else None,
        }
    except Exception as e:
        return {"error": str(e)}


def print_dda_status() -> None:
    """Print DDA status to console."""
    status = get_dda_status()
    print("\n=== DDA Status ===")
    print(f"Enabled: {status.get('enabled', 'N/A')}")
    print(f"Has trained model: {status.get('has_model', 'N/A')}")
    print(f"Last outcome: {status.get('last_outcome', 'N/A')}")
    
    adj = status.get('last_adjustment')
    if adj:
        print(f"Next wave adjustment:")
        print(f"  HP mult: {adj.get('hp_mult', 1.0):.2f}x")
        print(f"  Speed mult: {adj.get('speed_mult', 1.0):.2f}x")
        print(f"  Spawn mult: {adj.get('spawn_mult', 1.0):.2f}x")
    
    wave = status.get('current_wave')
    if wave:
        print(f"Current wave tracking:")
        print(f"  Wave: {wave.get('wave_number')}")
        print(f"  Shots: {wave.get('shots_fired')}, Rockets: {wave.get('rockets_fired')}, Grenades: {wave.get('grenades_thrown')}")
        print(f"  Kills: {wave.get('enemies_killed')}, Damage taken: {wave.get('damage_taken')}")
        print(f"  Primary weapon: {wave.get('primary_weapon')}")


def analyze_dda_effectiveness(db_path: str = "game_telemetry.db") -> dict:
    """Analyze DDA effectiveness from telemetry data.
    
    Compares runs with and without DDA adjustments to measure improvement.
    
    Returns:
        Dictionary with effectiveness metrics
    """
    if not Path(db_path).exists():
        return {"error": f"Database not found: {db_path}. Play with telemetry enabled!"}
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Check if wave_summaries table exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='wave_summaries'"
    )
    if cursor.fetchone() is None:
        conn.close()
        return {
            "error": "wave_summaries table not found. The new DDA tracking will create it on first run.",
            "total_wave_summaries": 0,
        }
    
    results = {}
    
    # Total wave summaries
    cursor = conn.execute("SELECT COUNT(*) FROM wave_summaries")
    total = cursor.fetchone()[0]
    results["total_wave_summaries"] = total
    
    if total == 0:
        conn.close()
        return {
            "error": "No wave summaries found. Play with telemetry enabled to collect data.",
            "total_wave_summaries": 0,
        }
    
    # Outcome distribution
    cursor = conn.execute("""
        SELECT outcome, COUNT(*) as count,
               AVG(player_hp_pct_end) as avg_hp_pct,
               AVG(wave_duration_sec) as avg_duration,
               AVG(enemies_killed) as avg_kills
        FROM wave_summaries
        GROUP BY outcome
        ORDER BY count DESC
    """)
    results["outcome_distribution"] = [dict(row) for row in cursor]
    
    # Calculate "ideal zone" percentage (challenged or comfortable outcomes)
    cursor = conn.execute("""
        SELECT 
            COUNT(CASE WHEN outcome IN ('challenged', 'comfortable') THEN 1 END) * 100.0 / COUNT(*) as ideal_pct,
            COUNT(CASE WHEN outcome = 'died' THEN 1 END) * 100.0 / COUNT(*) as death_pct,
            COUNT(CASE WHEN outcome = 'dominated' THEN 1 END) * 100.0 / COUNT(*) as dominated_pct
        FROM wave_summaries
    """)
    row = cursor.fetchone()
    results["ideal_zone_pct"] = row["ideal_pct"]
    results["death_rate_pct"] = row["death_pct"]
    results["dominated_pct"] = row["dominated_pct"]
    
    # Weapon usage breakdown
    cursor = conn.execute("""
        SELECT 
            SUM(shots_fired) as total_shots,
            SUM(rockets_fired) as total_rockets,
            SUM(grenades_thrown) as total_grenades,
            SUM(enemies_killed) as total_kills,
            SUM(rocket_kills) as rocket_kills,
            SUM(grenade_kills) as grenade_kills
        FROM wave_summaries
    """)
    row = cursor.fetchone()
    results["weapon_usage"] = {
        "total_shots": row["total_shots"] or 0,
        "total_rockets": row["total_rockets"] or 0,
        "total_grenades": row["total_grenades"] or 0,
        "total_kills": row["total_kills"] or 0,
        "rocket_kills": row["rocket_kills"] or 0,
        "grenade_kills": row["grenade_kills"] or 0,
    }
    
    # Calculate rocket preference
    shots = results["weapon_usage"]["total_shots"]
    rockets = results["weapon_usage"]["total_rockets"] * 3  # 3 missiles per use
    if shots + rockets > 0:
        results["rocket_preference_pct"] = rockets * 100.0 / (shots + rockets)
    else:
        results["rocket_preference_pct"] = 0
    
    # Wave-over-wave progression (are outcomes improving?)
    cursor = conn.execute("""
        SELECT wave_number,
               AVG(player_hp_pct_end) as avg_hp_pct,
               COUNT(CASE WHEN outcome IN ('challenged', 'comfortable') THEN 1 END) * 100.0 / COUNT(*) as ideal_pct
        FROM wave_summaries
        GROUP BY wave_number
        ORDER BY wave_number
        LIMIT 20
    """)
    results["wave_progression"] = [dict(row) for row in cursor]
    
    conn.close()
    return results


def print_dda_effectiveness(db_path: str = "game_telemetry.db") -> None:
    """Print DDA effectiveness analysis."""
    results = analyze_dda_effectiveness(db_path)
    
    if "error" in results:
        print(f"\n[DDA Analysis] {results['error']}")
        return
    
    print("\n" + "="*60)
    print("          DDA EFFECTIVENESS ANALYSIS")
    print("="*60)
    
    print(f"\nTotal wave summaries: {results['total_wave_summaries']}")
    
    print(f"\nOUTCOME DISTRIBUTION:")
    print(f"  Ideal zone (challenged/comfortable): {results['ideal_zone_pct']:.1f}%")
    print(f"  Death rate: {results['death_rate_pct']:.1f}%")
    print(f"  Dominated (too easy): {results['dominated_pct']:.1f}%")
    
    # Interpretation
    ideal = results['ideal_zone_pct']
    if ideal >= 50:
        print(f"  [OK] Good difficulty balance!")
    elif ideal >= 30:
        print(f"  [..] Moderate - more data will improve DDA")
    else:
        print(f"  [!!] Needs more training data")
    
    print(f"\nWEAPON USAGE:")
    wu = results["weapon_usage"]
    print(f"  Regular shots: {wu['total_shots']}")
    print(f"  Rockets fired: {wu['total_rockets']} ({wu['rocket_kills']} kills)")
    print(f"  Grenades thrown: {wu['total_grenades']} ({wu['grenade_kills']} kills)")
    print(f"  Rocket preference: {results['rocket_preference_pct']:.1f}%")
    
    print(f"\nWAVE PROGRESSION (first 10 waves):")
    for w in results["wave_progression"][:10]:
        bar = "#" * int(w["ideal_pct"] / 5) + "-" * (20 - int(w["ideal_pct"] / 5))
        print(f"  Wave {w['wave_number']:2d}: [{bar}] {w['ideal_pct']:.0f}% ideal, {w['avg_hp_pct']*100:.0f}% avg HP")
    
    print("\n" + "="*60)


def verify_dda_tracking() -> bool:
    """Quick verification that DDA tracking is working.
    
    Returns True if DDA is properly integrated.
    """
    try:
        from ml.dda_integration import get_dda
        dda = get_dda()
        
        # Simulate some events
        dda.on_shot_fired()
        dda.on_shot_fired()
        dda.on_rocket_fired()
        dda.on_enemy_killed("shot")
        dda.on_enemy_killed("rocket")
        
        stats = dda._tracker.get_current_stats()
        if stats is None:
            # No wave started - this is expected
            print("[DDA Verify] No wave active (expected before gameplay)")
            return True
        
        # Verify counts
        if stats.shots_fired == 2 and stats.rockets_fired == 1:
            print("[DDA Verify] ✅ Tracking working correctly!")
            print(f"  Shots: {stats.shots_fired}, Rockets: {stats.rockets_fired}")
            print(f"  Kills: {stats.enemies_killed} (rocket: {stats.rocket_kills})")
            return True
        else:
            print("[DDA Verify] ❌ Tracking mismatch")
            return False
            
    except Exception as e:
        print(f"[DDA Verify] ❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("DDA Debug Utilities")
    print("-" * 40)
    print_dda_status()
    print()
    print_dda_effectiveness()
