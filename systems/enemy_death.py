"""Enemy death handling and player respawn logic.

Extracted from game.py to reduce file size.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pygame

from config_weapons import WEAPON_UNLOCK_ORDER
from event_bus import GameEvent
from game_utils import calculate_kill_score
from systems.audio_system import play_sfx
from systems.spawn_helpers import spawn_weapon_in_center, spawn_weapon_drop

if TYPE_CHECKING:
    from state import GameState


def kill_enemy(
    enemy: dict,
    state: "GameState",
    width: int,
    height: int,
    event_bus: object | None = None,
) -> None:
    """Handle enemy death: drop weapon, update score, remove from list, and clean up projectiles.
    
    Args:
        enemy: Enemy dict being killed
        state: GameState
        width: World width (for weapon spawn)
        height: World height (for weapon spawn)
        event_bus: Optional event bus for publishing enemy_killed event
    """
    play_sfx("enemy_death")
    is_boss = enemy.get("is_boss", False)
    
    # Spawner enemy: when killed, all spawned enemies die
    if enemy.get("is_spawner"):
        for spawned_enemy in state.enemies[:]:
            if spawned_enemy.get("spawned_by") is enemy:
                spawned_enemy_type = spawned_enemy.get("type", "enemy")
                # Remove projectiles
                for proj in state.enemy_projectiles[:]:
                    if proj.get("enemy_type") == spawned_enemy_type:
                        state.enemy_projectiles.remove(proj)
                # Remove from list
                try:
                    state.enemies.remove(spawned_enemy)
                except ValueError:
                    pass
                state.enemies_killed += 1
                state.score += calculate_kill_score(state.wave_number, state.run_time)
    
    # Add defeat message
    enemy_type = enemy.get("type", "enemy")
    state.enemy_defeat_messages.append({
        "enemy_type": enemy_type,
        "timer": 3.0,
    })
    
    # Remove projectiles and damage numbers associated with this dead enemy
    enemy_pos = pygame.Vector2(enemy["rect"].center)
    cleanup_radius_sq = 2500  # 50 pixels squared
    
    # Remove ALL enemy projectiles from this dead enemy (by matching enemy_type)
    for proj in state.enemy_projectiles[:]:
        if proj.get("enemy_type") == enemy_type:
            state.enemy_projectiles.remove(proj)
    
    # Remove damage numbers near the dead enemy's position
    for dmg_num in state.damage_numbers[:]:
        dmg_pos = pygame.Vector2(dmg_num["x"], dmg_num["y"])
        if (dmg_pos - enemy_pos).length_squared() < cleanup_radius_sq:
            state.damage_numbers.remove(dmg_num)
    
    # If boss is killed, spawn level completion weapon in center
    if is_boss:
        if state.current_level in WEAPON_UNLOCK_ORDER:
            weapon_to_unlock = WEAPON_UNLOCK_ORDER[state.current_level]
            if weapon_to_unlock not in state.unlocked_weapons:
                spawn_weapon_in_center(weapon_to_unlock, state, width, height)
    else:
        # Regular enemies drop weapons randomly (except suicide enemies)
        if not enemy.get("is_suicide"):
            spawn_weapon_drop(enemy, state)
    
    try:
        state.enemies.remove(enemy)
    except ValueError:
        pass  # Already removed
    
    score_delta = calculate_kill_score(state.wave_number, state.run_time)
    state.enemies_killed += 1
    state.score += score_delta

    if event_bus is not None and hasattr(event_bus, "publish"):
        try:
            event_bus.publish(GameEvent("enemy_killed", {
                "enemy_type": enemy_type,
                "is_boss": is_boss,
                "wave_number": state.wave_number,
                "score_delta": score_delta,
            }))
        except Exception:
            logging.exception("Failed to publish enemy_killed")


def reset_after_death(state: "GameState", width: int, height: int) -> None:
    """Reset player state after death (respawn).
    
    Clears projectiles, explosions, and resets cooldowns. Keeps wave/level and weapons.
    
    Args:
        state: GameState to reset
        width: World width (for clamping player position)
        height: World height (for clamping player position)
    """
    from geometry_utils import clamp_rect_to_screen
    
    state.player_hp = state.player_max_hp
    state.player_health_regen_rate = 0.0
    state.random_damage_multiplier = 1.0
    state.damage_numbers.clear()
    state.weapon_pickup_messages.clear()
    state.grenade_explosions.clear()
    state.grenade_time_since_used = 999.0
    state.missiles.clear()
    state.missile_time_since_used = 999.0
    state.dropped_ally = None
    state.ally_drop_timer = 0.0
    state.overshield = 0
    state.armor_drain_timer = 0.0
    state.player_time_since_shot = 999.0
    state.laser_time_since_shot = 999.0
    state.wave_beam_time_since_shot = 999.0
    state.wave_beam_pattern_index = 0
    state.pos_timer = 0.0
    state.previous_boost_state = False
    state.previous_slow_state = False
    state.player_current_zones = set()
    state.jump_cooldown_timer = 0.0
    state.jump_timer = 0.0
    state.is_jumping = False
    state.jump_velocity = pygame.Vector2(0, 0)
    state.laser_beams.clear()
    state.enemy_laser_beams.clear()
    state.wave_beams.clear()
    state.shield_active = False
    state.shield_duration_remaining = 0.0
    state.shield_cooldown_remaining = 0.0

    # Respawn at death position, clamped to screen
    player = state.player_rect
    if player is not None:
        clamp_rect_to_screen(player, width, height)

    state.player_bullets.clear()
    state.enemy_projectiles.clear()
    state.friendly_projectiles.clear()
    # Do not clear friendly_ai or call start_wave: keep current wave and enemies.
    # Respawn = player at death position (unchanged), projectiles/explosions cleared; enemies and wave continue.
