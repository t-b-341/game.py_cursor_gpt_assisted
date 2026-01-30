"""AI logic: enemy targeting, ally behavior, queen shield/missiles, suicide, reflector, shooting."""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import pygame

from constants import STATE_NAME_INPUT
from .perf_timing import perf_timer

if TYPE_CHECKING:
    from state import GameState


def update(state: "GameState", dt: float) -> None:
    """Run AI updates for enemies and allies. Called from gameplay screen."""
    with perf_timer("ai_system"):
        ctx = getattr(state, "level_context", None)
        if ctx is None:
            return
        _update_ally_ai(state, dt, ctx)
        _update_enemy_ai(state, dt, ctx)


def _update_ally_ai(state, dt: float, ctx: dict) -> None:
    """Update friendly AI (drones/allies). Delegates to level_context's update_friendly_ai."""
    update_friendly = ctx.get("update_friendly_ai")
    if update_friendly:
        update_friendly(state, dt)


def _update_enemy_ai(state, dt: float, ctx: dict) -> None:
    """Target selection, queen shield/missiles, suicide detonation, reflector shield aim, shooting."""
    player = state.player_rect
    if player is None:
        return
    find_threat = ctx.get("find_nearest_threat")
    vec_toward = ctx.get("vec_toward")
    kill_enemy = ctx.get("kill_enemy")
    reset_after_death = ctx.get("reset_after_death")
    missile_damage = ctx.get("missile_damage", 100)
    testing_mode = ctx.get("testing_mode", False)
    invulnerability_mode = ctx.get("invulnerability_mode", False)
    spawn_projectile = ctx.get("spawn_enemy_projectile")
    spawn_projectile_predictive = ctx.get("spawn_enemy_projectile_predictive")

    player_targeting_slots = ctx.get("_player_targeting_slots", set())
    for enemy in state.enemies[:]:
        enemy_pos = pygame.Vector2(enemy["rect"].center)
        allow_player = id(enemy) in player_targeting_slots
        target_info = find_threat(enemy_pos, player, state.friendly_ai, allow_player=allow_player) if find_threat else None
        if target_info:
            target_pos, target_type = target_info
            direction = vec_toward(enemy_pos.x, enemy_pos.y, target_pos.x, target_pos.y) if vec_toward else pygame.Vector2(1, 0)
        else:
            direction = pygame.Vector2(1, 0)

        # Queen: shield phase and missile firing
        if enemy.get("type") == "queen" and enemy.get("has_shield"):
            _update_queen_shield(enemy, dt)
        if enemy.get("type") == "queen" and enemy.get("can_use_missiles"):
            _update_queen_missiles(enemy, dt, target_info, state, missile_damage)

        # Suicide: detonate when close, apply damage, remove enemy
        if enemy.get("is_suicide"):
            if _try_suicide_detonate(enemy, player, state, ctx, kill_enemy, reset_after_death, testing_mode, invulnerability_mode):
                continue

        # Reflector / shield enemy: turn shield toward target (shield enemies reflect unless flanked)
        if target_info and (enemy.get("has_reflective_shield") or (enemy.get("has_shield") and not enemy.get("has_reflective_shield"))):
            _update_reflector_shield_angle(enemy, target_info, dt)

        # Ambient: stationary, fires one rocket at player every 6s (dodgeable)
        if enemy.get("is_ambient") and spawn_projectile and player:
            rocket_cd = enemy.get("rocket_cooldown", 0.0) + dt
            enemy["rocket_cooldown"] = rocket_cd
            if rocket_cd >= enemy.get("shoot_cooldown", 6.0):
                spawn_projectile(enemy, state)
                enemy["rocket_cooldown"] = 0.0
            continue

        # Super large: rockets + grenades (grenades damage only player and allies)
        if enemy.get("fires_rockets") and target_info:
            missile_damage = ctx.get("missile_damage", 800)
            rcd = enemy.get("rocket_cooldown", 0.0) + dt
            enemy["rocket_cooldown"] = rcd
            if rcd >= enemy.get("rocket_interval", 5.0):
                missile_rect = pygame.Rect(
                    enemy["rect"].centerx - 8, enemy["rect"].centery - 8, 16, 16
                )
                state.missiles.append({
                    "rect": missile_rect,
                    "vel": pygame.Vector2(0, 0),
                    "target_enemy": None,
                    "target_player": True,
                    "speed": 400,
                    "damage": missile_damage // 2,
                    "explosion_radius": 100,
                })
                enemy["rocket_cooldown"] = 0.0
        if enemy.get("can_use_grenades_player_allies_only"):
            tsg = enemy.get("time_since_grenade", 999.0) + dt
            enemy["time_since_grenade"] = tsg
            if tsg >= enemy.get("grenade_cooldown", 8.0):
                state.grenade_explosions.append({
                    "x": enemy["rect"].centerx,
                    "y": enemy["rect"].centery,
                    "radius": 0,
                    "max_radius": enemy.get("grenade_radius", 120),
                    "timer": 0.3,
                    "damage": enemy.get("grenade_damage", 400),
                    "source": "enemy_player_allies_only",
                })
                enemy["time_since_grenade"] = 0.0
        if enemy.get("fires_rockets") or enemy.get("can_use_grenades_player_allies_only"):
            continue  # Super large uses only rockets + grenades, no normal projectiles

        # Large laser: single beam at player
        if enemy.get("fires_laser") and target_info and vec_toward:
            lcd = enemy.get("laser_cooldown", 0.0) + dt
            enemy["laser_cooldown"] = lcd
            if lcd >= enemy.get("laser_interval", 3.0):
                target_pos, _ = target_info
                dx = target_pos.x - enemy["rect"].centerx
                dy = target_pos.y - enemy["rect"].centery
                length = enemy.get("laser_length", 600)
                if dx * dx + dy * dy >= 1e-6:
                    scale = length / math.sqrt(dx * dx + dy * dy)
                    end_pos = pygame.Vector2(enemy["rect"].centerx + dx * scale, enemy["rect"].centery + dy * scale)
                else:
                    end_pos = pygame.Vector2(enemy["rect"].centerx + length, enemy["rect"].centery)
                deploy = enemy.get("laser_deploy_time", 2.0)
                state.enemy_laser_beams.append({
                    "start": pygame.Vector2(enemy["rect"].center),
                    "end": end_pos,
                    "damage": enemy.get("laser_damage", 80) * 60,  # per second in collision
                    "timer": enemy.get("laser_duration", 0.4),
                    "deploy_time": deploy,
                    "deploy_timer": deploy,  # countdown: no damage until 0, then beam is active
                    "color": (180, 100, 255),
                    "width": 4,
                })
                enemy["laser_cooldown"] = 0.0
            continue

        # Super large triple laser: three beams with spread
        if enemy.get("fires_triple_laser") and target_info and vec_toward:
            lcd = enemy.get("laser_cooldown", 0.0) + dt
            enemy["laser_cooldown"] = lcd
            if lcd >= enemy.get("laser_interval", 4.0):
                target_pos, _ = target_info
                cx, cy = enemy["rect"].centerx, enemy["rect"].centery
                dx = target_pos.x - cx
                dy = target_pos.y - cy
                length = enemy.get("laser_length", 700)
                spread_deg = enemy.get("laser_spread_deg", 15) * (3.14159265 / 180.0)
                base_angle = math.atan2(dy, dx)
                deploy = enemy.get("laser_deploy_time", 2.0)
                for off in (-spread_deg, 0, spread_deg):
                    a = base_angle + off
                    ex = cx + length * math.cos(a)
                    ey = cy + length * math.sin(a)
                    state.enemy_laser_beams.append({
                        "start": pygame.Vector2(cx, cy),
                        "end": pygame.Vector2(ex, ey),
                        "damage": enemy.get("laser_damage", 120) * 60,
                        "timer": enemy.get("laser_duration", 0.5),
                        "deploy_time": deploy,
                        "deploy_timer": deploy,
                        "color": (200, 80, 255),
                        "width": 6,
                    })
                enemy["laser_cooldown"] = 0.0
            continue

        # Non-reflector shooting
        if not enemy.get("has_reflective_shield") and spawn_projectile and spawn_projectile_predictive:
            enemy["shoot_cooldown"] = enemy.get("shoot_cooldown", 999.0) + dt
            if enemy["shoot_cooldown"] >= enemy.get("shoot_cooldown_time", 1.0):
                if target_info:
                    if enemy.get("is_predictive", False):
                        spawn_projectile_predictive(enemy, direction, state)
                    else:
                        spawn_projectile(enemy, state)
                enemy["shoot_cooldown"] = 0.0


def _update_queen_shield(enemy: dict, dt: float) -> None:
    shield_timer = enemy.get("shield_timer", 0.0) + dt
    shield_active = enemy.get("shield_active", False)
    shield_phase_duration = enemy.get("shield_phase_duration", 15.0)
    shield_active_duration = enemy.get("shield_active_duration", 7.5)

    if shield_active:
        if shield_timer >= shield_active_duration:
            enemy["shield_active"] = False
            enemy["shield_timer"] = 0.0
            enemy["shield_phase_duration"] = random.uniform(10.0, 20.0)
    else:
        if shield_timer >= shield_phase_duration:
            enemy["shield_active"] = True
            enemy["shield_timer"] = 0.0
            enemy["shield_active_duration"] = random.uniform(5.0, 10.0)

    enemy["shield_timer"] = shield_timer


def _update_queen_missiles(
    enemy: dict, dt: float, target_info, state, missile_damage: float
) -> None:
    time_since_missile = enemy.get("time_since_missile", 999.0) + dt
    missile_cooldown = enemy.get("missile_cooldown", 10.0)

    if time_since_missile >= missile_cooldown and target_info:
        missile_rect = pygame.Rect(
            enemy["rect"].centerx - 8,
            enemy["rect"].centery - 8,
            16, 16,
        )
        state.missiles.append({
            "rect": missile_rect,
            "vel": pygame.Vector2(0, 0),
            "target_enemy": None,
            "target_player": True,
            "speed": 500,
            "damage": missile_damage,
            "explosion_radius": 150,
            "source": "queen",
        })
        time_since_missile = 0.0

    enemy["time_since_missile"] = time_since_missile


def _try_suicide_detonate(
    enemy: dict,
    player: pygame.Rect,
    state,
    ctx: dict,
    kill_enemy,
    reset_after_death,
    testing_mode: bool,
    invulnerability_mode: bool,
) -> bool:
    """Detonate if in range; apply player damage; kill enemy. Returns True if enemy was killed (caller should continue)."""
    player_pos = pygame.Vector2(player.center)
    enemy_pos = pygame.Vector2(enemy["rect"].center)
    dist_to_player = (enemy_pos - player_pos).length()
    detonation_distance = enemy.get("detonation_distance", 50)

    if dist_to_player > detonation_distance:
        return False

    explosion_range = enemy.get("explosion_range", 150)
    state.grenade_explosions.append({
        "x": enemy["rect"].centerx,
        "y": enemy["rect"].centery,
        "radius": 0,
        "max_radius": explosion_range,
        "timer": 0.3,
        "damage": 500,
    })

    if dist_to_player <= explosion_range:
        if state.shield_active:
            pass
        elif not (testing_mode and invulnerability_mode):
            damage = 500
            if state.overshield > 0:
                damage_to_overshield = min(damage, state.overshield)
                state.overshield = max(0, state.overshield - damage)
                remaining_damage = damage - damage_to_overshield
            else:
                remaining_damage = damage
            if remaining_damage > 0:
                state.player_hp -= remaining_damage
            state.damage_taken += damage
            state.wave_damage_taken += damage
            if state.player_hp <= 0:
                if state.lives > 0:
                    state.lives -= 1
                    if reset_after_death:
                        reset_after_death(state)
                else:
                    state.final_score_for_high_score = state.score
                    state.player_name_input = ""
                    state.name_input_active = True
                    state.current_screen = STATE_NAME_INPUT

    if kill_enemy:
        kill_enemy(enemy, state)
    return True


def _update_reflector_shield_angle(enemy: dict, target_info, dt: float) -> None:
    target_pos, _ = target_info
    enemy_center = pygame.Vector2(enemy["rect"].center)
    to_target = (target_pos - enemy_center).normalize()
    target_angle = math.atan2(to_target.y, to_target.x)

    shield_angle = enemy.get("shield_angle", 0.0)
    turn_speed = enemy.get("turn_speed", 0.5) * dt

    angle_diff = target_angle - shield_angle
    while angle_diff > math.pi:
        angle_diff -= 2 * math.pi
    while angle_diff < -math.pi:
        angle_diff += 2 * math.pi

    if abs(angle_diff) > turn_speed:
        shield_angle += turn_speed if angle_diff > 0 else -turn_speed
    else:
        shield_angle = target_angle

    enemy["shield_angle"] = shield_angle
