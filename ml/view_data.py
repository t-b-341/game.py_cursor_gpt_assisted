"""Quick script to view wave summary data."""
import sqlite3
from pathlib import Path

db_path = "game_telemetry.db"

if not Path(db_path).exists():
    print(f"Database not found: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("=== Your Wave Data ===\n")

cursor = conn.execute("""
    SELECT wave_number, wave_duration_sec, shots_fired, rockets_fired, grenades_thrown,
           enemies_killed, rocket_kills, damage_taken, player_hp_pct_end, outcome
    FROM wave_summaries
    ORDER BY wave_number
""")

for row in cursor:
    print(f"Wave {row['wave_number']}:")
    print(f"  Duration: {row['wave_duration_sec']:.1f}s")
    print(f"  Weapons: {row['shots_fired']} shots, {row['rockets_fired']} rockets, {row['grenades_thrown']} grenades")
    print(f"  Kills: {row['enemies_killed']} total, {row['rocket_kills']} from rockets")
    print(f"  Damage taken: {row['damage_taken']}, HP at end: {row['player_hp_pct_end']*100:.0f}%")
    print(f"  Outcome: {row['outcome']}")
    print()

conn.close()
