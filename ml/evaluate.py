"""DDA Evaluation and Verification Tools.

Usage:
    python -m ml.evaluate              # Show all stats
    python -m ml.evaluate --compare    # Compare DDA on vs off
    python -m ml.evaluate --plot       # Generate visualization plots
    python -m ml.evaluate --live       # Show real-time DDA decisions

Answers the question: "Is the ML actually improving gameplay?"
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Optional

# Key metrics for evaluating DDA effectiveness
IDEAL_OUTCOME = "challenged"  # Player survives with 20-50% HP
GOOD_OUTCOMES = {"challenged", "comfortable"}  # Acceptable range


def get_db_connection(db_path: str = "game_telemetry.db") -> Optional[sqlite3.Connection]:
    """Get database connection if file exists."""
    if not Path(db_path).exists():
        print(f"Database not found: {db_path}")
        print("Play some games with telemetry enabled first!")
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def check_data_availability(conn: sqlite3.Connection) -> dict:
    """Check what data is available for evaluation."""
    stats = {}
    
    # Check if wave_summaries table exists
    cursor = conn.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='wave_summaries'
    """)
    stats["has_wave_summaries"] = cursor.fetchone() is not None
    
    if stats["has_wave_summaries"]:
        cursor = conn.execute("SELECT COUNT(*) FROM wave_summaries")
        stats["wave_summary_count"] = cursor.fetchone()[0]
    else:
        stats["wave_summary_count"] = 0
    
    # Check runs
    cursor = conn.execute("SELECT COUNT(*) FROM runs")
    stats["run_count"] = cursor.fetchone()[0]
    
    # Check waves
    cursor = conn.execute("SELECT COUNT(*) FROM waves")
    stats["wave_count"] = cursor.fetchone()[0]
    
    return stats


def get_outcome_distribution(conn: sqlite3.Connection) -> dict:
    """Get distribution of wave outcomes."""
    cursor = conn.execute("""
        SELECT outcome, COUNT(*) as count 
        FROM wave_summaries 
        WHERE outcome IS NOT NULL
        GROUP BY outcome
        ORDER BY count DESC
    """)
    
    outcomes = {}
    total = 0
    for row in cursor:
        outcomes[row["outcome"]] = row["count"]
        total += row["count"]
    
    # Calculate percentages
    distribution = {}
    for outcome, count in outcomes.items():
        distribution[outcome] = {
            "count": count,
            "percent": (count / total * 100) if total > 0 else 0
        }
    
    return {"distribution": distribution, "total": total}


def get_survival_metrics(conn: sqlite3.Connection) -> dict:
    """Get survival-related metrics."""
    metrics = {}
    
    # Average waves survived per run
    cursor = conn.execute("""
        SELECT AVG(max_wave) as avg_waves, MAX(max_wave) as max_waves
        FROM runs WHERE max_wave IS NOT NULL
    """)
    row = cursor.fetchone()
    metrics["avg_waves_survived"] = row["avg_waves"] or 0
    metrics["max_waves_survived"] = row["max_waves"] or 0
    
    # Average HP at wave end (excluding deaths)
    cursor = conn.execute("""
        SELECT AVG(player_hp_pct_end) as avg_hp_pct
        FROM wave_summaries
        WHERE outcome != 'died' AND player_hp_pct_end IS NOT NULL
    """)
    row = cursor.fetchone()
    metrics["avg_hp_at_wave_end"] = (row["avg_hp_pct"] or 0) * 100
    
    # Death rate per wave
    cursor = conn.execute("""
        SELECT 
            SUM(CASE WHEN outcome = 'died' THEN 1 ELSE 0 END) as deaths,
            COUNT(*) as total
        FROM wave_summaries
    """)
    row = cursor.fetchone()
    if row["total"] > 0:
        metrics["death_rate_pct"] = row["deaths"] / row["total"] * 100
    else:
        metrics["death_rate_pct"] = 0
    
    return metrics


def get_weapon_stats(conn: sqlite3.Connection) -> dict:
    """Get weapon usage statistics."""
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
    
    total_shots = row["total_shots"] or 0
    total_rockets = row["total_rockets"] or 0
    total_grenades = row["total_grenades"] or 0
    total_kills = row["total_kills"] or 0
    
    # Calculate weapon preference
    total_attacks = total_shots + (total_rockets * 3) + total_grenades
    
    return {
        "total_shots": total_shots,
        "total_rockets": total_rockets,
        "total_grenades": total_grenades,
        "total_kills": total_kills,
        "rocket_kills": row["rocket_kills"] or 0,
        "grenade_kills": row["grenade_kills"] or 0,
        "rocket_preference": (total_rockets * 3) / max(1, total_attacks) * 100,
    }


def get_difficulty_progression(conn: sqlite3.Connection) -> list:
    """Get how difficulty scales over waves (to verify DDA is adjusting)."""
    cursor = conn.execute("""
        SELECT 
            wave_number,
            AVG(hp_scale) as avg_hp_scale,
            AVG(speed_scale) as avg_speed_scale,
            AVG(enemies_spawned) as avg_enemies,
            AVG(player_hp_pct_end) as avg_hp_end,
            COUNT(*) as sample_count
        FROM wave_summaries
        GROUP BY wave_number
        ORDER BY wave_number
        LIMIT 20
    """)
    
    return [dict(row) for row in cursor]


def calculate_dda_effectiveness(conn: sqlite3.Connection) -> dict:
    """Calculate how effective the DDA is at achieving target outcomes."""
    outcome_data = get_outcome_distribution(conn)
    dist = outcome_data["distribution"]
    total = outcome_data["total"]
    
    if total == 0:
        return {"score": 0, "message": "No data available"}
    
    # Score calculation:
    # - "challenged" is ideal (weight: 1.0)
    # - "comfortable" is good (weight: 0.7)
    # - "struggled" is acceptable (weight: 0.4)
    # - "died" is bad (weight: 0.0)
    # - "dominated" means too easy (weight: 0.2)
    
    weights = {
        "challenged": 1.0,
        "comfortable": 0.7,
        "struggled": 0.4,
        "dominated": 0.2,
        "died": 0.0,
    }
    
    weighted_sum = 0
    for outcome, data in dist.items():
        weight = weights.get(outcome, 0.5)
        weighted_sum += weight * data["count"]
    
    score = (weighted_sum / total) * 100 if total > 0 else 0
    
    # Determine effectiveness level
    if score >= 70:
        message = "Excellent - DDA is keeping players in the sweet spot"
    elif score >= 55:
        message = "Good - Most waves are appropriately challenging"
    elif score >= 40:
        message = "Fair - Room for improvement in difficulty tuning"
    else:
        message = "Needs work - Too many deaths or dominated waves"
    
    return {
        "score": score,
        "message": message,
        "ideal_outcome_pct": dist.get("challenged", {}).get("percent", 0),
        "good_outcome_pct": sum(
            dist.get(o, {}).get("percent", 0) for o in GOOD_OUTCOMES
        ),
    }


def print_evaluation_report(db_path: str = "game_telemetry.db"):
    """Print comprehensive DDA evaluation report."""
    conn = get_db_connection(db_path)
    if conn is None:
        return
    
    print("\n" + "=" * 60)
    print("     DDA EVALUATION REPORT")
    print("=" * 60)
    
    # Data availability
    data_stats = check_data_availability(conn)
    print("\n[DATA AVAILABILITY]")
    print(f"   Total runs: {data_stats['run_count']}")
    print(f"   Total waves logged: {data_stats['wave_count']}")
    print(f"   Wave summaries (ML data): {data_stats['wave_summary_count']}")
    
    if data_stats['wave_summary_count'] < 10:
        print("\n[!] Need more data! Play at least 10+ waves with telemetry enabled.")
        print("    Go to Options > Telemetry > Enabled")
        conn.close()
        return
    
    # Outcome distribution
    outcome_data = get_outcome_distribution(conn)
    print("\n[OUTCOME DISTRIBUTION]")
    print("   (Target: 'challenged' = 20-50% HP remaining)")
    for outcome, data in sorted(outcome_data["distribution"].items(), 
                                  key=lambda x: -x[1]["count"]):
        bar = "#" * int(data["percent"] / 5)
        marker = " <- IDEAL" if outcome == "challenged" else ""
        print(f"   {outcome:12s}: {data['percent']:5.1f}% {bar}{marker}")
    
    # DDA Effectiveness Score
    effectiveness = calculate_dda_effectiveness(conn)
    print(f"\n[DDA EFFECTIVENESS SCORE]: {effectiveness['score']:.1f}/100")
    print(f"   {effectiveness['message']}")
    print(f"   Ideal outcomes (challenged): {effectiveness['ideal_outcome_pct']:.1f}%")
    print(f"   Good outcomes (challenged+comfortable): {effectiveness['good_outcome_pct']:.1f}%")
    
    # Survival metrics
    survival = get_survival_metrics(conn)
    print("\n[SURVIVAL METRICS]")
    print(f"   Avg waves survived: {survival['avg_waves_survived']:.1f}")
    print(f"   Max waves survived: {survival['max_waves_survived']}")
    print(f"   Avg HP at wave end: {survival['avg_hp_at_wave_end']:.1f}%")
    print(f"   Death rate: {survival['death_rate_pct']:.1f}% of waves")
    
    # Weapon stats
    weapons = get_weapon_stats(conn)
    print("\n[WEAPON USAGE] (Your Playstyle)")
    print(f"   Regular shots: {weapons['total_shots']}")
    print(f"   Rockets fired: {weapons['total_rockets']} ({weapons['rocket_kills']} kills)")
    print(f"   Grenades thrown: {weapons['total_grenades']} ({weapons['grenade_kills']} kills)")
    print(f"   Rocket preference: {weapons['rocket_preference']:.1f}%")
    
    # Difficulty progression
    progression = get_difficulty_progression(conn)
    if progression:
        print("\n[DIFFICULTY OVER WAVES] (first 10)")
        print("   Wave | HP Scale | Speed | Enemies | Avg HP End")
        print("   " + "-" * 48)
        for row in progression[:10]:
            print(f"   {row['wave_number']:4d} | "
                  f"{row['avg_hp_scale']:8.2f} | "
                  f"{row['avg_speed_scale']:5.2f} | "
                  f"{row['avg_enemies']:7.1f} | "
                  f"{(row['avg_hp_end'] or 0)*100:6.1f}%")
    
    print("\n" + "=" * 60)
    
    # Recommendations
    print("\n[RECOMMENDATIONS]")
    if effectiveness['score'] < 50:
        if survival['death_rate_pct'] > 30:
            print("   - Death rate is high - DDA should lower difficulty more aggressively")
        if effectiveness.get('dominated_pct', 0) > 20:
            print("   - Too many 'dominated' waves - increase difficulty faster")
    else:
        print("   - DDA is working well! Continue collecting data for model training.")
    
    if data_stats['wave_summary_count'] >= 50:
        print("   - You have enough data to train the ML model:")
        print("     python -m ml.train --gpu")
    else:
        need = 50 - data_stats['wave_summary_count']
        print(f"   - Collect {need} more wave summaries before training the model")
    
    conn.close()


def show_live_dda_decisions(db_path: str = "game_telemetry.db"):
    """Show the most recent DDA decisions."""
    conn = get_db_connection(db_path)
    if conn is None:
        return
    
    print("\n[RECENT DDA DECISIONS] (last 10 waves)")
    print("-" * 70)
    
    cursor = conn.execute("""
        SELECT 
            wave_number,
            outcome,
            player_hp_pct_end,
            hp_scale,
            speed_scale,
            enemies_spawned,
            rockets_fired,
            shots_fired,
            enemies_killed
        FROM wave_summaries
        ORDER BY id DESC
        LIMIT 10
    """)
    
    print("Wave | Outcome     | HP End | Difficulty      | Kills | Weapons")
    print("-" * 70)
    
    for row in cursor:
        hp_pct = (row["player_hp_pct_end"] or 0) * 100
        rockets = row["rockets_fired"] or 0
        shots = row["shots_fired"] or 0
        weapon_str = f"R:{rockets} S:{shots}"
        
        print(f"{row['wave_number']:4d} | "
              f"{row['outcome']:11s} | "
              f"{hp_pct:5.1f}% | "
              f"HP:{row['hp_scale']:.2f} SPD:{row['speed_scale']:.2f} | "
              f"{row['enemies_killed']:5d} | "
              f"{weapon_str}")
    
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Evaluate DDA effectiveness")
    parser.add_argument("--db", default="game_telemetry.db", help="Database path")
    parser.add_argument("--live", action="store_true", help="Show recent DDA decisions")
    parser.add_argument("--compare", action="store_true", help="Compare with/without DDA")
    
    args = parser.parse_args()
    
    if args.live:
        show_live_dda_decisions(args.db)
    else:
        print_evaluation_report(args.db)


if __name__ == "__main__":
    main()
