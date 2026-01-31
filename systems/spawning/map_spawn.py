"""Custom map spawning - spawn enemies from map spawn points.

Extracted from spawn_system.py for better organization.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pygame

from game_logging import get_logger
from config.enemy_defs import (
    ENEMY_SPEED_SCALE_MULTIPLIER,
    get_enemy_def,
)
from constants import difficulty_multipliers
from enemies import log_enemy_spawns, make_enemy_from_template

if TYPE_CHECKING:
    from state import GameState

_log = get_logger(__name__)


def spawn_enemies_from_map(state: "GameState", map_grid, wave_num: int, ctx: dict) -> int:
    """Spawn enemies using a custom map's spawn points.
    
    Args:
        state: Game state to add enemies to
        map_grid: MapGrid with spawn_points
        wave_num: Current wave number
        ctx: Level context with callbacks
    
    Returns:
        Number of enemies spawned
    """
    from maps.editor import TILE_SIZE
    
    telemetry = ctx.get("telemetry")
    telemetry_enabled = ctx.get("telemetry_enabled", False)
    difficulty = ctx.get("difficulty", "NORMAL")
    diff_settings = difficulty_multipliers.get(difficulty, difficulty_multipliers["NORMAL"])
    # Extract specific multipliers from difficulty settings
    hp_mult = diff_settings.get("enemy_hp", 1.0)
    speed_mult = diff_settings.get("enemy_speed", 1.0)
    
    spawned_count = 0
    
    _log.debug(f"Spawning from map '{map_grid.name}' wave {wave_num}, spawn_points: {len(map_grid.spawn_points)}")
    
    for spawn_point in map_grid.spawn_points:
        if not spawn_point.can_spawn_on_wave(wave_num):
            _log.debug(f"Spawn point ({spawn_point.x},{spawn_point.y}) not active for wave {wave_num}")
            continue
        
        enemy_type = spawn_point.get_random_enemy_type()
        if not enemy_type:
            _log.debug(f"Spawn point ({spawn_point.x},{spawn_point.y}) has no enemy types")
            continue
        
        # Get enemy template
        enemy_def = get_enemy_def(enemy_type)
        if not enemy_def:
            _log.warning(f"Unknown enemy type '{enemy_type}', falling back to grunt")
            # Fall back to grunt if unknown type
            enemy_def = get_enemy_def("grunt")
        
        # Calculate world position from tile coordinates
        world_x = spawn_point.x * TILE_SIZE + TILE_SIZE // 2
        world_y = spawn_point.y * TILE_SIZE + TILE_SIZE // 2
        
        # Create enemy from template with difficulty scaling
        hp_scale = 1.0 + (wave_num - 1) * 0.1
        final_speed_scale = (1.0 + (wave_num - 1) * ENEMY_SPEED_SCALE_MULTIPLIER) * speed_mult
        
        enemy = make_enemy_from_template(enemy_def, hp_scale * hp_mult, final_speed_scale)
        
        # Position the enemy
        enemy_size = enemy["rect"].size
        enemy["rect"] = pygame.Rect(
            world_x - enemy_size[0] // 2,
            world_y - enemy_size[1] // 2,
            enemy_size[0],
            enemy_size[1]
        )
        
        state.enemies.append(enemy)
        spawn_point.times_spawned += 1
        spawned_count += 1
        
        # Log telemetry
        if telemetry_enabled and telemetry:
            ref = [state.enemies_spawned]
            log_enemy_spawns([enemy], telemetry, state.run_time, ref)
            state.enemies_spawned = ref[0]
    
    return spawned_count


def start_wave_from_map(wave_num: int, state: "GameState", map_grid, ctx: dict) -> None:
    """Start a wave using custom map spawn points.
    
    Args:
        wave_num: Wave number to start
        state: Game state
        map_grid: Custom MapGrid with spawn points
        ctx: Level context
    """
    enemies_before = len(state.enemies)
    trigger = getattr(state, "wave_start_reason", "map_spawn")
    _log_wave_reset(state, trigger, wave_num, enemies_before)
    state.wave_start_reason = ""
    
    # Show wave banner
    if ctx.get("enable_wave_banner", True):
        state.wave_banner_timer = ctx.get("wave_banner_duration", 1.5)
        state.wave_banner_text = f"WAVE {wave_num}"
    
    pf = ctx.get("play_sfx")
    if callable(pf):
        pf("WAVE START")
    
    # Reset wave state
    state.enemies = []
    state.boss_active = False
    state.wave_damage_taken = 0
    state.side_quests["no_hit_wave"]["active"] = True
    state.side_quests["no_hit_wave"]["completed"] = False
    
    if state.lives != 999:
        state.lives = 3
    
    # Calculate level/wave from wave number
    state.current_level = min(state.max_level, (wave_num - 1) // 3 + 1)
    state.wave_in_level = ((wave_num - 1) % 3) + 1
    
    # Spawn enemies from map
    spawned = spawn_enemies_from_map(state, map_grid, wave_num, ctx)
    
    # If no spawns from map, spawn some default enemies
    if spawned == 0:
        _log.info("No spawn points spawned, using fallback spawning")
        # Fallback: spawn a few grunts
        w = ctx.get("width", 1920)
        h = ctx.get("height", 1080)
        random_spawn = ctx.get("random_spawn_position")
        num_to_spawn = 3 + wave_num
        for i in range(num_to_spawn):
            enemy_def = get_enemy_def("grunt")
            if not enemy_def:
                _log.error("Could not get grunt enemy def!")
                continue
            enemy = make_enemy_from_template(enemy_def, 1.0, 1.0)
            if random_spawn:
                enemy["rect"] = random_spawn((enemy["rect"].w, enemy["rect"].h), state)
            else:
                enemy["rect"].x = random.randint(100, w - 100)
                enemy["rect"].y = random.randint(100, h - 100)
            state.enemies.append(enemy)
            spawned += 1
        _log.debug(f"Fallback spawned {spawned} grunts")
    else:
        _log.debug(f"Spawned {spawned} enemies from map spawn points")
    
    state.wave_active = True
    _log.info(f"Wave active, total enemies: {len(state.enemies)}")
    
    # Log to telemetry
    telemetry = ctx.get("telemetry")
    if telemetry and ctx.get("telemetry_enabled"):
        try:
            telemetry.log_wave_start(
                wave_num, state.run_id, state.run_time, spawned
            )
        except Exception:
            pass


def _log_wave_reset(state, trigger: str, wave_num: int, enemies_before: int) -> None:
    """Append to wave_reset_log and print so we can trace spurious resets."""
    entry = {
        "run_time": getattr(state, "run_time", 0.0),
        "trigger": trigger,
        "wave_num": wave_num,
        "enemies_before": enemies_before,
    }
    log = getattr(state, "wave_reset_log", None)
    if log is not None:
        log.append(entry)
        # Keep last 20 entries
        while len(log) > 20:
            log.pop(0)
    msg = (
        f"[WAVE-RESET] run_time={entry['run_time']:.1f}s trigger={trigger!r} "
        f"wave_num={wave_num} enemies_before={enemies_before}"
    )
    print(msg)
