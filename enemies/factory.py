"""Enemy factory and telemetry functions."""
import math
import random

import pygame

from entities import Enemy
from config_enemies import (
    ENEMY_HP_SCALE_MULTIPLIER,
    ENEMY_SPEED_SCALE_MULTIPLIER,
    ENEMY_FIRE_RATE_MULTIPLIER,
    ENEMY_HP_CAP,
    QUEEN_FIXED_HP,
)
from constants import ENEMY_COLOR, ENEMY_PROJECTILES_COLOR
from telemetry import EnemySpawnEvent


def make_enemy_from_template(t: dict, hp_scale: float, speed_scale: float) -> Enemy:
    """Create an enemy from a template with scaling applied."""
    # Apply scaling multipliers from config
    # Exception: Queen (player clone) has fixed HP and special speed multiplier
    if t.get("type") == "queen":
        hp = QUEEN_FIXED_HP
        base_speed = t.get("speed", 80)
        final_speed = base_speed * ENEMY_SPEED_SCALE_MULTIPLIER
    elif t.get("type") in ("super_large", "super_large_triple_laser"):
        hp = int(t["hp"] * hp_scale * 1.5)  # Scale but no normal cap
        base_spd = t.get("speed", 20)
        final_speed = base_spd * speed_scale * ENEMY_SPEED_SCALE_MULTIPLIER
    elif t.get("type") == "large_laser":
        hp = int(t["hp"] * hp_scale * ENEMY_HP_SCALE_MULTIPLIER * 10)
        hp = min(hp, ENEMY_HP_CAP * 10)
        final_speed = t.get("speed", 50) * speed_scale * ENEMY_SPEED_SCALE_MULTIPLIER
    elif t.get("is_ambient"):
        hp = t["hp"]
        final_speed = 0  # Stationary
    else:
        hp = int(t["hp"] * hp_scale * ENEMY_HP_SCALE_MULTIPLIER * 10)
        hp = min(hp, ENEMY_HP_CAP * 10)
        final_speed = t.get("speed", 80) * speed_scale * ENEMY_SPEED_SCALE_MULTIPLIER

    shoot_cd = t["shoot_cooldown"] / ENEMY_FIRE_RATE_MULTIPLIER
    if t.get("is_ambient"):
        shoot_cd = t["shoot_cooldown"]  # Ambient: rocket every 6s, no fire-rate modifier
    
    enemy = {
        "type": t["type"],
        "rect": pygame.Rect(t["rect"].x, t["rect"].y, t["rect"].w, t["rect"].h),
        "color": t.get("color", ENEMY_COLOR),  # Use template color if specified, else default red
        "hp": hp,
        "max_hp": hp,
        "shoot_cooldown": shoot_cd,
        "time_since_shot": random.uniform(0.0, shoot_cd),
        "projectile_speed": t["projectile_speed"],
        "projectile_color": t.get("projectile_color", ENEMY_PROJECTILES_COLOR),
        "projectile_shape": t.get("projectile_shape", "circle"),
        "speed": final_speed,  # Speed (queen gets special multiplier, others get normal scaling)
    }
    # Add shield properties if present
    if t.get("has_shield"):
        enemy["has_shield"] = True
        enemy["shield_angle"] = random.uniform(0, 2 * math.pi)
        enemy["shield_length"] = t.get("shield_length", 50)
    if t.get("has_reflective_shield"):
        enemy["has_reflective_shield"] = True
        enemy["shield_angle"] = random.uniform(0, 2 * math.pi)
        enemy["shield_length"] = t.get("shield_length", 60)
        enemy["shield_hp"] = 0
        enemy["turn_speed"] = t.get("turn_speed", 0.5)
    if t.get("is_predictive"):
        enemy["is_predictive"] = True
    if t.get("is_evasive"):
        enemy["is_evasive"] = True
    if t.get("shape"):
        enemy["shape"] = t["shape"]
    if t.get("is_ambient"):
        enemy["is_ambient"] = True
        enemy["rocket_cooldown"] = t.get("rocket_cooldown", 0.0)
    if t.get("enemy_size_class"):
        enemy["enemy_size_class"] = t["enemy_size_class"]
    if t.get("is_flamethrower"):
        enemy["is_flamethrower"] = True
        enemy["flame_damage"] = t.get("flame_damage", 8)
    if t.get("reflect_damage_mult") is not None:
        enemy["reflect_damage_mult"] = t["reflect_damage_mult"]
    if t.get("fires_rockets"):
        enemy["fires_rockets"] = True
        enemy["rocket_cooldown"] = t.get("rocket_cooldown", 0.0)
        enemy["rocket_interval"] = t.get("rocket_interval", 5.0)
    if t.get("can_use_grenades_player_allies_only"):
        enemy["can_use_grenades_player_allies_only"] = True
        enemy["grenade_cooldown"] = t.get("grenade_cooldown", 8.0)
        enemy["time_since_grenade"] = t.get("time_since_grenade", 999.0)
        enemy["grenade_damage"] = t.get("grenade_damage", 400)
        enemy["grenade_radius"] = t.get("grenade_radius", 120)
    if t.get("fires_laser"):
        enemy["fires_laser"] = True
        enemy["laser_cooldown"] = t.get("laser_cooldown", 0.0)
        enemy["laser_interval"] = t.get("laser_interval", 3.0)
        enemy["laser_duration"] = t.get("laser_duration", 0.4)
        enemy["laser_deploy_time"] = t.get("laser_deploy_time", 2.0)
        enemy["laser_damage"] = t.get("laser_damage", 80)
        enemy["laser_length"] = t.get("laser_length", 600)
    if t.get("fires_triple_laser"):
        enemy["fires_triple_laser"] = True
        enemy["laser_cooldown"] = t.get("laser_cooldown", 0.0)
        enemy["laser_interval"] = t.get("laser_interval", 4.0)
        enemy["laser_duration"] = t.get("laser_duration", 0.5)
        enemy["laser_deploy_time"] = t.get("laser_deploy_time", 2.0)
        enemy["laser_damage"] = t.get("laser_damage", 120)
        enemy["laser_length"] = t.get("laser_length", 700)
        enemy["laser_spread_deg"] = t.get("laser_spread_deg", 15)
    
    # Add queen-specific properties
    if t.get("type") == "queen":
        enemy["name"] = t.get("name", "queen")
        enemy["can_use_grenades"] = t.get("can_use_grenades", False)
        enemy["grenade_cooldown"] = t.get("grenade_cooldown", 5.0)
        enemy["time_since_grenade"] = t.get("time_since_grenade", 999.0)
        enemy["damage_taken_since_rage"] = 0
        enemy["rage_mode_active"] = False
        enemy["rage_mode_timer"] = 0.0
        # rage_damage_threshold is set in template (randomized at module load time)
        enemy["rage_damage_threshold"] = t.get("rage_damage_threshold", random.randint(300, 500))
        enemy["predicts_player"] = t.get("predicts_player", False)
    return Enemy(enemy)


def log_enemy_spawns(
    new_enemies: list[dict],
    telemetry,
    run_time: float,
    enemies_spawned_ref: list[int],  # List with one element to simulate global variable
):
    """Log enemy spawns to telemetry."""
    for e in new_enemies:
        enemies_spawned_ref[0] += 1
        telemetry.log_enemy_spawn(
            EnemySpawnEvent(
                t=run_time,
                enemy_type=e["type"],
                x=e["rect"].x,
                y=e["rect"].y,
                w=e["rect"].w,
                h=e["rect"].h,
                hp=e["hp"],
            )
        )
