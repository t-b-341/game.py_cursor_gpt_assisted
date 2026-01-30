"""
Buffered SQLite telemetry writer. Buffers inserts, flushes on timer or when full, closes cleanly.
"""
import sqlite3
from typing import Optional

from . import schema
from .events import (
    BossEvent,
    BulletMetadataEvent,
    EnemyHitEvent,
    EnemyPositionEvent,
    EnemySpawnEvent,
    FrameTimeEvent,
    FriendlyAIDeathEvent,
    FriendlyAIPositionEvent,
    FriendlyAIShotEvent,
    FriendlyAISpawnEvent,
    LevelEvent,
    OvershieldEvent,
    PickupEvent,
    PlayerActionEvent,
    PlayerDamageEvent,
    PlayerDeathEvent,
    PlayerPosEvent,
    PlayerVelocityEvent,
    ScoreEvent,
    ShotEvent,
    WaveEnemyTypeEvent,
    WaveEvent,
    WeaponSwitchEvent,
    ZoneVisitEvent,
)


class NoOpTelemetry:
    """No-op implementation when telemetry is disabled. Every method is a no-op."""

    def __getattr__(self, name: str):
        return lambda *args, **kwargs: None


class Telemetry:
    """
    Buffered SQLite telemetry writer.
    Buffers inserts in memory, flushes on a timer or when buffers get large, flushes and closes on shutdown.
    """

    def __init__(
        self,
        db_path: str = "game_telemetry.db",
        flush_interval_s: float = 0.5,
        max_buffer: int = 500,
    ):
        self.db_path = db_path
        self.flush_interval_s = float(flush_interval_s)
        self.max_buffer = int(max_buffer)

        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode = WAL;")
        self.conn.execute("PRAGMA synchronous = NORMAL;")
        self.conn.execute("PRAGMA cache_size = -64000;")
        self.conn.execute("PRAGMA foreign_keys = ON;")
        schema.init_schema(self.conn)

        self.run_id: Optional[int] = None
        self._time_since_flush = 0.0

        self._enemy_spawn_buf: list[tuple] = []
        self._pos_buf: list[tuple] = []
        self._shot_buf: list[tuple] = []
        self._enemy_hit_buf: list[tuple] = []
        self._player_damage_buf: list[tuple] = []
        self._player_death_buf: list[tuple] = []
        self._wave_buf: list[tuple] = []
        self._enemy_pos_buf: list[tuple] = []
        self._player_velocity_buf: list[tuple] = []
        self._bullet_metadata_buf: list[tuple] = []
        self._score_buf: list[tuple] = []
        self._level_buf: list[tuple] = []
        self._boss_buf: list[tuple] = []
        self._weapon_switch_buf: list[tuple] = []
        self._pickup_buf: list[tuple] = []
        self._overshield_buf: list[tuple] = []
        self._player_action_buf: list[tuple] = []
        self._zone_visit_buf: list[tuple] = []
        self._friendly_spawn_buf: list[tuple] = []
        self._friendly_position_buf: list[tuple] = []
        self._friendly_shot_buf: list[tuple] = []
        self._friendly_death_buf: list[tuple] = []
        self._wave_enemy_types_buf: list[tuple] = []
        self._run_state_buf: list[tuple] = []
        self._frame_time_buf: list[tuple] = []

    def start_run(self, started_at_iso: str, player_max_hp: int) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO runs (started_at, player_max_hp) VALUES (?, ?);",
            (started_at_iso, int(player_max_hp)),
        )
        self.conn.commit()
        self.run_id = cur.lastrowid
        return self.run_id

    def end_run(
        self,
        ended_at_iso: str,
        seconds_survived: float,
        player_hp_end: int,
        shots_fired: int,
        hits: int,
        damage_taken: int,
        damage_dealt: int,
        enemies_spawned: int,
        enemies_killed: int,
        deaths: int,
        max_wave: Optional[int] = None,
        final_score: Optional[int] = None,
        max_level: Optional[int] = None,
        difficulty: Optional[str] = None,
        endurance_mode: bool = False,
    ) -> None:
        if self.run_id is None:
            return
        self.flush(force=True)
        cols = schema.get_columns(self.conn, "runs")
        update_fields = [
            "ended_at = ?", "seconds_survived = ?", "player_hp_end = ?",
            "shots_fired = ?", "hits = ?", "damage_taken = ?",
            "damage_dealt = ?", "enemies_spawned = ?", "enemies_killed = ?", "deaths = ?"
        ]
        values = [
            ended_at_iso, float(seconds_survived), int(player_hp_end),
            int(shots_fired), int(hits), int(damage_taken),
            int(damage_dealt), int(enemies_spawned), int(enemies_killed), int(deaths)
        ]
        if "max_wave" in cols and max_wave is not None:
            update_fields.append("max_wave = ?")
            values.append(int(max_wave))
        if "final_score" in cols and final_score is not None:
            update_fields.append("final_score = ?")
            values.append(int(final_score))
        if "max_level" in cols and max_level is not None:
            update_fields.append("max_level = ?")
            values.append(int(max_level))
        if "difficulty" in cols and difficulty is not None:
            update_fields.append("difficulty = ?")
            values.append(difficulty)
        if "endurance_mode" in cols:
            update_fields.append("endurance_mode = ?")
            values.append(1 if endurance_mode else 0)
        values.append(int(self.run_id))
        self.conn.execute(
            f"UPDATE runs SET {', '.join(update_fields)} WHERE id = ?;",
            tuple(values),
        )
        self.conn.commit()

    def log_enemy_spawn(self, event: EnemySpawnEvent) -> None:
        if self.run_id is None:
            return
        self._enemy_spawn_buf.append(
            (self.run_id, event.t, event.enemy_type, event.x, event.y, event.w, event.h, event.hp)
        )

    def log_player_position(self, event: PlayerPosEvent) -> None:
        if self.run_id is None:
            return
        self._pos_buf.append((self.run_id, event.t, event.x, event.y))

    def log_shot(
        self,
        event: ShotEvent,
        shape: Optional[str] = None,
        color: Optional[tuple[int, int, int]] = None,
    ) -> None:
        if self.run_id is None:
            return
        if shape and color:
            pass  # Handled via bullet_metadata table
        self._shot_buf.append(
            (self.run_id, event.t, event.origin_x, event.origin_y, event.target_x, event.target_y, event.dir_x, event.dir_y)
        )

    def log_enemy_hit(self, event: EnemyHitEvent) -> None:
        if self.run_id is None:
            return
        self._enemy_hit_buf.append(
            (
                self.run_id, float(event.t), event.enemy_type,
                int(event.enemy_x), int(event.enemy_y), int(event.damage),
                int(event.enemy_hp_after), 1 if event.killed else 0,
            )
        )

    def log_player_damage(self, event: PlayerDamageEvent) -> None:
        if self.run_id is None:
            return
        self._player_damage_buf.append(
            (
                self.run_id, float(event.t), int(event.amount), event.source_type,
                event.source_enemy_type, int(event.player_x), int(event.player_y),
                int(event.player_hp_after),
            )
        )

    def log_player_death(self, event: PlayerDeathEvent) -> None:
        if self.run_id is None:
            return
        wave = int(getattr(event, "wave_number", 0))
        self._player_death_buf.append(
            (self.run_id, float(event.t), int(event.player_x), int(event.player_y), int(event.lives_left), wave)
        )

    def log_run_state_sample(self, t: float, player_hp: int, enemies_alive: int) -> None:
        """Log a single run-state sample (HP, enemy count) for difficulty time-series. Call at POS_SAMPLE_INTERVAL."""
        if self.run_id is None:
            return
        self._run_state_buf.append((self.run_id, float(t), int(player_hp), int(enemies_alive)))

    def log_wave(self, event: WaveEvent) -> None:
        if self.run_id is None:
            return
        self._wave_buf.append(
            (
                self.run_id, float(event.t), int(event.wave_number), event.event_type,
                int(event.enemies_spawned), float(event.hp_scale), float(event.speed_scale),
            )
        )

    def log_enemy_position(self, event: EnemyPositionEvent) -> None:
        if self.run_id is None:
            return
        self._enemy_pos_buf.append(
            (
                self.run_id, float(event.t), event.enemy_type,
                int(event.x), int(event.y), float(event.speed),
                float(event.vel_x), float(event.vel_y),
            )
        )

    def log_player_velocity(self, event: PlayerVelocityEvent) -> None:
        if self.run_id is None:
            return
        self._player_velocity_buf.append(
            (
                self.run_id, float(event.t), int(event.x), int(event.y),
                float(event.vel_x), float(event.vel_y), float(event.speed),
            )
        )

    def log_bullet_metadata(self, event: BulletMetadataEvent) -> None:
        if self.run_id is None:
            return
        self._bullet_metadata_buf.append(
            (
                self.run_id, float(event.t), event.bullet_type, event.shape,
                int(event.color_r), int(event.color_g), int(event.color_b),
                event.source_enemy_type,
            )
        )

    def log_score(self, event: ScoreEvent) -> None:
        if self.run_id is None:
            return
        self._score_buf.append(
            (self.run_id, float(event.t), int(event.score), int(event.score_change), event.source)
        )

    def log_level(self, event: LevelEvent) -> None:
        if self.run_id is None:
            return
        self._level_buf.append((self.run_id, float(event.t), int(event.level), event.level_name))

    def log_boss(self, event: BossEvent) -> None:
        if self.run_id is None:
            return
        self._boss_buf.append(
            (
                self.run_id, float(event.t), int(event.wave_number), int(event.phase),
                int(event.hp), int(event.max_hp), event.event_type,
            )
        )

    def log_weapon_switch(self, event: WeaponSwitchEvent) -> None:
        if self.run_id is None:
            return
        self._weapon_switch_buf.append((self.run_id, float(event.t), event.weapon_mode))

    def log_pickup(self, event: PickupEvent) -> None:
        if self.run_id is None:
            return
        self._pickup_buf.append(
            (self.run_id, float(event.t), event.pickup_type, int(event.x), int(event.y), 1 if event.collected else 0)
        )

    def log_overshield(self, event: OvershieldEvent) -> None:
        if self.run_id is None:
            return
        self._overshield_buf.append(
            (self.run_id, float(event.t), int(event.overshield), int(event.max_overshield), int(event.change))
        )

    def log_player_action(self, event: PlayerActionEvent) -> None:
        if self.run_id is None:
            return
        self._player_action_buf.append(
            (
                self.run_id, float(event.t), event.action_type, int(event.x), int(event.y),
                float(event.duration) if event.duration is not None else None,
                1 if event.success else 0,
            )
        )

    def log_zone_visit(self, event: ZoneVisitEvent) -> None:
        if self.run_id is None:
            return
        zone_id = None
        try:
            row = self.conn.execute(
                "SELECT id FROM zones WHERE zone_name = ? LIMIT 1;",
                (event.zone_name,),
            ).fetchone()
            if row:
                zone_id = row[0]
        except sqlite3.OperationalError:
            pass
        self._zone_visit_buf.append(
            (
                self.run_id, float(event.t), zone_id, event.zone_name, event.zone_type,
                event.event_type, int(event.x), int(event.y),
            )
        )

    def log_friendly_spawn(self, event: FriendlyAISpawnEvent) -> None:
        if self.run_id is None:
            return
        self._friendly_spawn_buf.append(
            (
                self.run_id, float(event.t), event.friendly_type,
                int(event.x), int(event.y), int(event.w), int(event.h), int(event.hp), event.behavior,
            )
        )

    def log_friendly_position(self, event: FriendlyAIPositionEvent) -> None:
        if self.run_id is None:
            return
        self._friendly_position_buf.append(
            (
                self.run_id, float(event.t), event.friendly_type,
                int(event.x), int(event.y), float(event.speed),
                float(event.vel_x), float(event.vel_y), event.target_enemy_type,
            )
        )

    def log_friendly_shot(self, event: FriendlyAIShotEvent) -> None:
        if self.run_id is None:
            return
        self._friendly_shot_buf.append(
            (
                self.run_id, float(event.t), event.friendly_type,
                int(event.origin_x), int(event.origin_y), int(event.target_x), int(event.target_y),
                event.target_enemy_type,
            )
        )

    def log_friendly_death(self, event: FriendlyAIDeathEvent) -> None:
        if self.run_id is None:
            return
        self._friendly_death_buf.append(
            (self.run_id, float(event.t), event.friendly_type, int(event.x), int(event.y), event.killed_by)
        )

    def log_wave_enemy_types(self, event: WaveEnemyTypeEvent) -> None:
        if self.run_id is None:
            return
        self._wave_enemy_types_buf.append(
            (self.run_id, float(event.t), int(event.wave_number), event.enemy_type, int(event.count))
        )

    def log_frame_time(self, event: FrameTimeEvent) -> None:
        """Log frame timing data for performance analysis."""
        if self.run_id is None:
            return
        self._frame_time_buf.append(
            (
                self.run_id, float(event.t), float(event.frame_time_ms), float(event.fps),
                int(event.player_bullets), int(event.enemy_projectiles),
                int(event.enemies), int(event.friendly_projectiles),
            )
        )

    def tick(self, dt: float) -> None:
        self._time_since_flush += float(dt)
        if self._time_since_flush >= self.flush_interval_s:
            self.flush()
        total = (
            len(self._enemy_spawn_buf) + len(self._pos_buf) + len(self._shot_buf)
            + len(self._enemy_hit_buf) + len(self._player_damage_buf) + len(self._player_death_buf)
            + len(self._wave_buf) + len(self._enemy_pos_buf) + len(self._player_velocity_buf)
            + len(self._bullet_metadata_buf) + len(self._score_buf) + len(self._level_buf)
            + len(self._boss_buf) + len(self._weapon_switch_buf) + len(self._pickup_buf)
            + len(self._overshield_buf) + len(self._wave_enemy_types_buf) + len(self._run_state_buf)
            + len(self._frame_time_buf)
        )
        if total >= self.max_buffer:
            self.flush()

    def flush(self, force: bool = False) -> None:
        if not force:
            self._time_since_flush = 0.0
        cur = self.conn.cursor()
        wrote_any = False

        def run(table_sql_values: list[tuple[str, str, list]]) -> bool:
            nonlocal wrote_any
            for sql, params in table_sql_values:
                if params:
                    cur.executemany(sql, params)
                    wrote_any = True
            return wrote_any

        if self._enemy_spawn_buf:
            cur.executemany(
                "INSERT INTO enemy_spawns (run_id, t, enemy_type, x, y, w, h, hp) VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                self._enemy_spawn_buf,
            )
            self._enemy_spawn_buf.clear()
            wrote_any = True
        if self._pos_buf:
            cur.executemany(
                "INSERT INTO player_positions (run_id, t, x, y) VALUES (?, ?, ?, ?);",
                self._pos_buf,
            )
            self._pos_buf.clear()
            wrote_any = True
        if self._shot_buf:
            cur.executemany(
                "INSERT INTO shots (run_id, t, origin_x, origin_y, target_x, target_y, dir_x, dir_y) VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                self._shot_buf,
            )
            self._shot_buf.clear()
            wrote_any = True
        if self._enemy_hit_buf:
            cur.executemany(
                "INSERT INTO enemy_hits (run_id, t, enemy_type, enemy_x, enemy_y, damage, enemy_hp_after, killed) VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                self._enemy_hit_buf,
            )
            self._enemy_hit_buf.clear()
            wrote_any = True
        if self._player_damage_buf:
            cur.executemany(
                "INSERT INTO player_damage (run_id, t, amount, source_type, source_enemy_type, player_x, player_y, player_hp_after) VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                self._player_damage_buf,
            )
            self._player_damage_buf.clear()
            wrote_any = True
        if self._player_death_buf:
            cur.executemany(
                "INSERT INTO player_deaths (run_id, t, player_x, player_y, lives_left, wave_number) VALUES (?, ?, ?, ?, ?, ?);",
                self._player_death_buf,
            )
            self._player_death_buf.clear()
            wrote_any = True
        if self._run_state_buf:
            cur.executemany(
                "INSERT INTO run_state_samples (run_id, t, player_hp, enemies_alive) VALUES (?, ?, ?, ?);",
                self._run_state_buf,
            )
            self._run_state_buf.clear()
            wrote_any = True
        if self._wave_buf:
            cur.executemany(
                "INSERT INTO waves (run_id, t, wave_number, event_type, enemies_spawned, hp_scale, speed_scale) VALUES (?, ?, ?, ?, ?, ?, ?);",
                self._wave_buf,
            )
            self._wave_buf.clear()
            wrote_any = True
        if self._enemy_pos_buf:
            cur.executemany(
                "INSERT INTO enemy_positions (run_id, t, enemy_type, x, y, speed, vel_x, vel_y) VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                self._enemy_pos_buf,
            )
            self._enemy_pos_buf.clear()
            wrote_any = True
        if self._player_velocity_buf:
            cur.executemany(
                "INSERT INTO player_velocities (run_id, t, x, y, vel_x, vel_y, speed) VALUES (?, ?, ?, ?, ?, ?, ?);",
                self._player_velocity_buf,
            )
            self._player_velocity_buf.clear()
            wrote_any = True
        if self._bullet_metadata_buf:
            cur.executemany(
                "INSERT INTO bullet_metadata (run_id, t, bullet_type, shape, color_r, color_g, color_b, source_enemy_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                self._bullet_metadata_buf,
            )
            self._bullet_metadata_buf.clear()
            wrote_any = True
        if self._score_buf:
            cur.executemany(
                "INSERT INTO score_events (run_id, t, score, score_change, source) VALUES (?, ?, ?, ?, ?);",
                self._score_buf,
            )
            self._score_buf.clear()
            wrote_any = True
        if self._level_buf:
            cur.executemany(
                "INSERT INTO level_events (run_id, t, level, level_name) VALUES (?, ?, ?, ?);",
                self._level_buf,
            )
            self._level_buf.clear()
            wrote_any = True
        if self._boss_buf:
            cur.executemany(
                "INSERT INTO boss_events (run_id, t, wave_number, phase, hp, max_hp, event_type) VALUES (?, ?, ?, ?, ?, ?, ?);",
                self._boss_buf,
            )
            self._boss_buf.clear()
            wrote_any = True
        if self._weapon_switch_buf:
            cur.executemany(
                "INSERT INTO weapon_switches (run_id, t, weapon_mode) VALUES (?, ?, ?);",
                self._weapon_switch_buf,
            )
            self._weapon_switch_buf.clear()
            wrote_any = True
        if self._pickup_buf:
            cur.executemany(
                "INSERT INTO pickup_events (run_id, t, pickup_type, x, y, collected) VALUES (?, ?, ?, ?, ?, ?);",
                self._pickup_buf,
            )
            self._pickup_buf.clear()
            wrote_any = True
        if self._overshield_buf:
            cur.executemany(
                "INSERT INTO overshield_events (run_id, t, overshield, max_overshield, change) VALUES (?, ?, ?, ?, ?);",
                self._overshield_buf,
            )
            self._overshield_buf.clear()
            wrote_any = True
        if self._player_action_buf:
            cur.executemany(
                "INSERT INTO player_actions (run_id, t, action_type, x, y, duration, success) VALUES (?, ?, ?, ?, ?, ?, ?);",
                self._player_action_buf,
            )
            self._player_action_buf.clear()
            wrote_any = True
        if self._zone_visit_buf:
            cur.executemany(
                "INSERT INTO player_zone_visits (run_id, t, zone_id, zone_name, zone_type, event_type, x, y) VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                self._zone_visit_buf,
            )
            self._zone_visit_buf.clear()
            wrote_any = True
        if self._friendly_spawn_buf:
            cur.executemany(
                "INSERT INTO friendly_ai_spawns (run_id, t, friendly_type, x, y, w, h, hp, behavior) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
                self._friendly_spawn_buf,
            )
            self._friendly_spawn_buf.clear()
            wrote_any = True
        if self._friendly_position_buf:
            cur.executemany(
                "INSERT INTO friendly_ai_positions (run_id, t, friendly_type, x, y, speed, vel_x, vel_y, target_enemy_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
                self._friendly_position_buf,
            )
            self._friendly_position_buf.clear()
            wrote_any = True
        if self._friendly_shot_buf:
            cur.executemany(
                "INSERT INTO friendly_ai_shots (run_id, t, friendly_type, origin_x, origin_y, target_x, target_y, target_enemy_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                self._friendly_shot_buf,
            )
            self._friendly_shot_buf.clear()
            wrote_any = True
        if self._friendly_death_buf:
            cur.executemany(
                "INSERT INTO friendly_ai_deaths (run_id, t, friendly_type, x, y, killed_by) VALUES (?, ?, ?, ?, ?, ?);",
                self._friendly_death_buf,
            )
            self._friendly_death_buf.clear()
            wrote_any = True
        if self._wave_enemy_types_buf:
            cur.executemany(
                "INSERT INTO wave_enemy_types (run_id, t, wave_number, enemy_type, count) VALUES (?, ?, ?, ?, ?);",
                self._wave_enemy_types_buf,
            )
            self._wave_enemy_types_buf.clear()
            wrote_any = True
        if self._frame_time_buf:
            cur.executemany(
                "INSERT INTO frame_times (run_id, t, frame_time_ms, fps, player_bullets, enemy_projectiles, enemies, friendly_projectiles) VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                self._frame_time_buf,
            )
            self._frame_time_buf.clear()
            wrote_any = True

        if wrote_any:
            self.conn.commit()

    def close(self) -> None:
        self.flush(force=True)
        self.conn.close()
