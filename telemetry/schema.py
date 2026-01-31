"""
Database schema: table definitions, migrations, indexes, and views.
All functions operate on an open sqlite3 connection; they do not hold connection state.
"""
import sqlite3


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1;",
        (name,),
    ).fetchone()
    return row is not None


def get_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()
    rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
    return {r[1] for r in rows}


def _add_column_if_missing(conn: sqlite3.Connection, table: str, col: str, ddl: str) -> None:
    try:
        cols = get_columns(conn, table)
        if col in cols:
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl};")
        conn.commit()
    except sqlite3.OperationalError as e:
        if "no such table" in str(e).lower():
            pass
        else:
            raise


def _create_index_if_missing(conn: sqlite3.Connection, table: str, index_name: str, columns: str) -> None:
    try:
        conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({columns});")
    except sqlite3.OperationalError:
        pass


def _create_views(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("""
            CREATE VIEW IF NOT EXISTS player_performance_summary AS
            SELECT 
                r.id AS run_id,
                r.difficulty,
                r.max_level,
                r.final_score,
                r.seconds_survived,
                r.enemies_killed,
                r.damage_dealt,
                r.damage_taken,
                CASE 
                    WHEN r.shots_fired > 0 
                    THEN CAST(r.hits AS REAL) / r.shots_fired * 100.0 
                    ELSE 0.0 
                END AS accuracy_pct,
                CASE 
                    WHEN r.seconds_survived > 0 
                    THEN CAST(r.enemies_killed AS REAL) / r.seconds_survived 
                    ELSE 0.0 
                END AS kills_per_second,
                CASE 
                    WHEN r.seconds_survived > 0 
                    THEN CAST(r.damage_dealt AS REAL) / r.seconds_survived 
                    ELSE 0.0 
                END AS dps
            FROM runs r;
        """)
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("""
            CREATE VIEW IF NOT EXISTS wave_performance AS
            SELECT 
                w.run_id,
                w.wave_number,
                w.enemies_spawned,
                w.hp_scale,
                w.speed_scale,
                COUNT(DISTINCT eh.id) AS enemies_killed,
                COALESCE(SUM(eh.damage), 0) AS damage_dealt,
                MIN(CASE WHEN w.event_type = 'start' THEN w.t END) AS start_time,
                MIN(CASE WHEN w.event_type = 'end' THEN w.t END) AS end_time
            FROM waves w
            LEFT JOIN enemy_hits eh ON eh.run_id = w.run_id 
                AND eh.t BETWEEN 
                    (SELECT MIN(t) FROM waves w2 WHERE w2.run_id = w.run_id AND w2.wave_number = w.wave_number AND w2.event_type = 'start')
                    AND COALESCE(
                        (SELECT MIN(t) FROM waves w3 WHERE w3.run_id = w.run_id AND w3.wave_number = w.wave_number + 1 AND w3.event_type = 'start'),
                        (SELECT seconds_survived FROM runs WHERE id = w.run_id)
                    )
            GROUP BY w.run_id, w.wave_number, w.enemies_spawned, w.hp_scale, w.speed_scale;
        """)
    except sqlite3.OperationalError:
        pass


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables, run migrations, create indexes and views. Idempotent."""
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            seconds_survived REAL,
            player_max_hp INTEGER NOT NULL,
            player_hp_end INTEGER,
            shots_fired INTEGER NOT NULL DEFAULT 0,
            hits INTEGER NOT NULL DEFAULT 0,
            damage_taken INTEGER NOT NULL DEFAULT 0,
            enemies_spawned INTEGER NOT NULL DEFAULT 0,
            enemies_killed INTEGER NOT NULL DEFAULT 0
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS enemy_spawns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            enemy_type TEXT NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            w INTEGER NOT NULL,
            h INTEGER NOT NULL,
            hp INTEGER NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS shots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            origin_x INTEGER NOT NULL,
            origin_y INTEGER NOT NULL,
            target_x INTEGER NOT NULL,
            target_y INTEGER NOT NULL,
            dir_x REAL NOT NULL,
            dir_y REAL NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS enemy_hits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            enemy_type TEXT NOT NULL,
            enemy_x INTEGER NOT NULL,
            enemy_y INTEGER NOT NULL,
            damage INTEGER NOT NULL,
            enemy_hp_after INTEGER NOT NULL,
            killed INTEGER NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_damage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            amount INTEGER NOT NULL,
            source_type TEXT NOT NULL,
            source_enemy_type TEXT,
            player_x INTEGER NOT NULL,
            player_y INTEGER NOT NULL,
            player_hp_after INTEGER NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_deaths (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            player_x INTEGER NOT NULL,
            player_y INTEGER NOT NULL,
            lives_left INTEGER NOT NULL,
            wave_number INTEGER,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS run_state_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            player_hp INTEGER NOT NULL,
            enemies_alive INTEGER NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS waves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            wave_number INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            enemies_spawned INTEGER NOT NULL,
            hp_scale REAL NOT NULL,
            speed_scale REAL NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS enemy_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            enemy_type TEXT NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            speed REAL NOT NULL,
            vel_x REAL NOT NULL,
            vel_y REAL NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_velocities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            vel_x REAL NOT NULL,
            vel_y REAL NOT NULL,
            speed REAL NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS bullet_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            bullet_type TEXT NOT NULL,
            shape TEXT NOT NULL,
            color_r INTEGER NOT NULL,
            color_g INTEGER NOT NULL,
            color_b INTEGER NOT NULL,
            source_enemy_type TEXT,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS score_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            score INTEGER NOT NULL,
            score_change INTEGER NOT NULL,
            source TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS level_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            level INTEGER NOT NULL,
            level_name TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS boss_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            wave_number INTEGER NOT NULL,
            phase INTEGER NOT NULL,
            hp INTEGER NOT NULL,
            max_hp INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS weapon_switches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            weapon_mode TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pickup_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            pickup_type TEXT NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            collected INTEGER NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS overshield_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            overshield INTEGER NOT NULL,
            max_overshield INTEGER NOT NULL,
            change INTEGER NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone_name TEXT NOT NULL UNIQUE,
            zone_type TEXT NOT NULL,
            x_min INTEGER NOT NULL,
            x_max INTEGER NOT NULL,
            y_min INTEGER NOT NULL,
            y_max INTEGER NOT NULL
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            action_type TEXT NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            duration REAL,
            success INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_zone_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            zone_id INTEGER,
            zone_name TEXT NOT NULL,
            zone_type TEXT NOT NULL,
            event_type TEXT NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE,
            FOREIGN KEY(zone_id) REFERENCES zones(id) ON DELETE SET NULL
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS friendly_ai_spawns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            friendly_type TEXT NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            w INTEGER NOT NULL,
            h INTEGER NOT NULL,
            hp INTEGER NOT NULL,
            behavior TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS friendly_ai_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            friendly_type TEXT NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            speed REAL NOT NULL,
            vel_x REAL NOT NULL,
            vel_y REAL NOT NULL,
            target_enemy_type TEXT,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS friendly_ai_shots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            friendly_type TEXT NOT NULL,
            origin_x INTEGER NOT NULL,
            origin_y INTEGER NOT NULL,
            target_x INTEGER NOT NULL,
            target_y INTEGER NOT NULL,
            target_enemy_type TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS friendly_ai_deaths (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            friendly_type TEXT NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            killed_by TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS wave_enemy_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            wave_number INTEGER NOT NULL,
            enemy_type TEXT NOT NULL,
            count INTEGER NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS frame_times (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            t REAL NOT NULL,
            frame_time_ms REAL NOT NULL,
            fps REAL NOT NULL,
            player_bullets INTEGER NOT NULL,
            enemy_projectiles INTEGER NOT NULL,
            enemies INTEGER NOT NULL,
            friendly_projectiles INTEGER NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)

    # Wave summaries for ML training (Dynamic Difficulty Adjustment)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS wave_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            wave_number INTEGER NOT NULL,
            
            -- Wave metadata
            wave_start_t REAL NOT NULL,
            wave_end_t REAL,
            wave_duration_sec REAL,
            
            -- Difficulty settings applied
            hp_scale REAL NOT NULL,
            speed_scale REAL NOT NULL,
            enemies_spawned INTEGER NOT NULL,
            
            -- Player performance metrics (inputs for ML)
            shots_fired INTEGER NOT NULL DEFAULT 0,
            shots_hit INTEGER NOT NULL DEFAULT 0,
            accuracy_pct REAL,
            damage_dealt INTEGER NOT NULL DEFAULT 0,
            damage_taken INTEGER NOT NULL DEFAULT 0,
            deaths_this_wave INTEGER NOT NULL DEFAULT 0,
            pickups_collected INTEGER NOT NULL DEFAULT 0,
            abilities_used INTEGER NOT NULL DEFAULT 0,
            enemies_killed INTEGER NOT NULL DEFAULT 0,
            
            -- Weapon-specific tracking
            rockets_fired INTEGER NOT NULL DEFAULT 0,
            rockets_hit INTEGER NOT NULL DEFAULT 0,
            rocket_kills INTEGER NOT NULL DEFAULT 0,
            grenades_thrown INTEGER NOT NULL DEFAULT 0,
            grenade_kills INTEGER NOT NULL DEFAULT 0,
            laser_time REAL NOT NULL DEFAULT 0.0,
            laser_kills INTEGER NOT NULL DEFAULT 0,
            
            -- Player state at wave end
            player_hp_start INTEGER,
            player_hp_end INTEGER,
            player_hp_pct_end REAL,
            
            -- Derived metrics
            kills_per_second REAL,
            damage_per_second REAL,
            
            -- Outcome label for training (survived/died/struggled/dominated)
            outcome TEXT,
            
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE,
            UNIQUE(run_id, wave_number)
        );
    """)

    conn.commit()

    _add_column_if_missing(conn, "runs", "damage_dealt", "damage_dealt INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "runs", "deaths", "deaths INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "runs", "max_wave", "max_wave INTEGER")
    _add_column_if_missing(conn, "runs", "final_score", "final_score INTEGER")
    _add_column_if_missing(conn, "runs", "max_level", "max_level INTEGER")
    _add_column_if_missing(conn, "runs", "difficulty", "difficulty TEXT")
    _add_column_if_missing(conn, "runs", "endurance_mode", "endurance_mode INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "player_deaths", "wave_number", "wave_number INTEGER")
    _add_column_if_missing(conn, "shots", "shape", "shape TEXT")
    _add_column_if_missing(conn, "shots", "color_r", "color_r INTEGER")
    _add_column_if_missing(conn, "shots", "color_g", "color_g INTEGER")
    _add_column_if_missing(conn, "shots", "color_b", "color_b INTEGER")

    conn.commit()

    _create_index_if_missing(conn, "enemy_hits", "idx_enemy_hits_run_t", "run_id, t")
    _create_index_if_missing(conn, "player_damage", "idx_player_damage_run_t", "run_id, t")
    _create_index_if_missing(conn, "run_state_samples", "idx_run_state_run_t", "run_id, t")
    _create_index_if_missing(conn, "waves", "idx_waves_run_wave", "run_id, wave_number")
    _create_index_if_missing(conn, "score_events", "idx_score_run_t", "run_id, t")
    _create_index_if_missing(conn, "weapon_switches", "idx_weapon_run_t", "run_id, t")
    _create_index_if_missing(conn, "pickup_events", "idx_pickup_run_t", "run_id, t")
    _create_index_if_missing(conn, "boss_events", "idx_boss_run_wave", "run_id, wave_number")
    _create_index_if_missing(conn, "player_actions", "idx_actions_run_t", "run_id, t")
    _create_index_if_missing(conn, "player_actions", "idx_actions_type", "action_type")
    _create_index_if_missing(conn, "player_zone_visits", "idx_zone_visits_run_t", "run_id, t")
    _create_index_if_missing(conn, "player_zone_visits", "idx_zone_visits_zone", "zone_id")
    _create_index_if_missing(conn, "friendly_ai_spawns", "idx_friendly_spawns_run_t", "run_id, t")
    _create_index_if_missing(conn, "friendly_ai_positions", "idx_friendly_pos_run_t", "run_id, t")
    _create_index_if_missing(conn, "friendly_ai_shots", "idx_friendly_shots_run_t", "run_id, t")
    _create_index_if_missing(conn, "friendly_ai_deaths", "idx_friendly_deaths_run_t", "run_id, t")
    _create_index_if_missing(conn, "wave_enemy_types", "idx_wave_enemy_types_run_wave", "run_id, wave_number")
    _create_index_if_missing(conn, "wave_enemy_types", "idx_wave_enemy_types_type", "enemy_type")
    _create_index_if_missing(conn, "frame_times", "idx_frame_times_run_t", "run_id, t")
    _create_index_if_missing(conn, "wave_summaries", "idx_wave_summaries_run_wave", "run_id, wave_number")
    _create_index_if_missing(conn, "wave_summaries", "idx_wave_summaries_outcome", "outcome")

    conn.commit()
    _create_views(conn)
