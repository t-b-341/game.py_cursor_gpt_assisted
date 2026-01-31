"""
Projectile spawning: player bullets, enemy projectiles, boss projectiles, ally missiles.

Extracted from game.py for better code organization. These functions handle creating
and configuring projectile entities with proper stats, colors, damage, and telemetry.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from config.projectile_defs import get_projectile_def
from config.balance import (
    player_bullet_speed,
    player_bullet_size,
    player_bullets_color,
    player_bullet_shapes,
    ENEMY_PROJECTILE_SIZE,
    ENEMY_PROJECTILES_COLOR,
)
from config_weapons import WEAPON_CONFIGS

# Aliases for compatibility with original code style
enemy_projectile_size = ENEMY_PROJECTILE_SIZE
enemy_projectiles_color = ENEMY_PROJECTILES_COLOR
from constants import (
    AIM_ARROWS,
    UNLOCKED_WEAPON_DAMAGE_MULT,
)
from enemies import find_nearest_threat
from geometry_utils import vec_toward
from systems.audio_system import play_sfx
from telemetry import ShotEvent, BulletMetadataEvent
from systems.shot_particle_state import get_shot_particle_state

if TYPE_CHECKING:
    from state import GameState
    from context import AppContext


def spawn_player_bullet_and_log(state: GameState, ctx: AppContext):
    """Spawn player bullet(s) based on current weapon mode and aiming direction.
    
    Handles weapon configs, stat multipliers, spread patterns, and telemetry logging.
    """
    if state.player_rect is None:
        return
    
    # Check projectile limit for performance
    max_bullets = getattr(ctx.config, "max_player_bullets", 200)
    if max_bullets > 0 and len(state.player_bullets) >= max_bullets:
        return  # Don't spawn more bullets if at limit
    # Determine aiming direction based on aiming mode
    if ctx.config.aim_mode == AIM_ARROWS:
        # Arrow key aiming
        keys = pygame.key.get_pressed()
        dx = 0
        dy = 0
        if keys[pygame.K_LEFT]:
            dx = -1
        if keys[pygame.K_RIGHT]:
            dx = 1
        if keys[pygame.K_UP]:
            dy = -1
        if keys[pygame.K_DOWN]:
            dy = 1
        
        if dx == 0 and dy == 0:
            # No arrow keys pressed, use last movement direction or default
            if state.last_move_velocity.length_squared() > 0:
                base_dir = state.last_move_velocity.normalize()
            else:
                base_dir = pygame.Vector2(1, 0)  # Default right
        else:
            base_dir = pygame.Vector2(dx, dy).normalize()
        
        # Calculate target position for telemetry (extend direction from player)
        target_dist = 100  # Distance to calculate target point
        mx = int(state.player_rect.centerx + base_dir.x * target_dist)
        my = int(state.player_rect.centery + base_dir.y * target_dist)
    else:
        # Mouse aiming (default) - use world coordinates for aiming
        mx, my = ctx.get_world_mouse_pos()
        base_dir = vec_toward(state.player_rect.centerx, state.player_rect.centery, mx, my)

    shape = player_bullet_shapes[state.player_bullet_shape_index % len(player_bullet_shapes)]
    state.player_bullet_shape_index = (state.player_bullet_shape_index + 1) % len(player_bullet_shapes)

    # Resolve weapon params from data-driven def when available, else WEAPON_CONFIGS
    weapon_mode = state.current_weapon_mode
    pd = get_projectile_def("player_" + weapon_mode) if weapon_mode != "laser" else None
    if pd:
        base_speed = pd["speed"]
        base_size = pd["size"]
        weapon_config = {
            "damage_multiplier": pd["damage_multiplier"],
            "size_multiplier": pd["size_multiplier"],
            "speed_multiplier": 1.0,
            "spread_angle_deg": pd["spread_angle_deg"],
            "num_projectiles": pd["num_projectiles"],
            "color": pd["color"],
            "explosion_radius": pd["explosion_radius"],
            "max_bounces": pd["max_bounces"],
            "is_rocket": pd["is_rocket"],
        }
    else:
        weapon_config = WEAPON_CONFIGS.get(weapon_mode, WEAPON_CONFIGS["basic"])
        base_speed = player_bullet_speed * weapon_config["speed_multiplier"]
        base_size = player_bullet_size

    # Determine shot pattern based on weapon mode
    if weapon_config["num_projectiles"] > 1:
        # Multi-projectile weapons (triple, basic)
        spread_angle_deg = weapon_config["spread_angle_deg"]
        directions = [
            base_dir,  # center
            base_dir.rotate(-spread_angle_deg),  # left
            base_dir.rotate(spread_angle_deg),  # right
        ]
    else:
        directions = [base_dir]

    # Spawn bullets for each direction
    for d in directions:
        # Apply stat multipliers and weapon-specific multipliers
        size_mult = state.player_stat_multipliers["bullet_size"] * weapon_config["size_multiplier"]
        effective_size = (
            int(base_size[0] * size_mult),
            int(base_size[1] * size_mult),
        )
        effective_speed = base_speed * state.player_stat_multipliers["bullet_speed"]
        base_damage = int(state.player_bullet_damage * state.player_stat_multipliers["bullet_damage"])
        # Apply weapon damage multiplier
        effective_damage = int(base_damage * weapon_config["damage_multiplier"])
        # Unlocked-weapon shots deal 1.75x damage
        if state.current_weapon_mode in state.unlocked_weapons:
            effective_damage = int(effective_damage * UNLOCKED_WEAPON_DAMAGE_MULT)
        
        # Apply random damage multiplier (from random_damage pickup)
        effective_damage = int(effective_damage * state.random_damage_multiplier)
        
        # Rocket launcher: always has explosion
        if weapon_config["is_rocket"]:
            rocket_explosion = max(weapon_config["explosion_radius"], state.player_stat_multipliers["bullet_explosion_radius"] + 100.0)
        else:
            rocket_explosion = max(weapon_config["explosion_radius"], state.player_stat_multipliers["bullet_explosion_radius"])

    r = pygame.Rect(
        state.player_rect.centerx - effective_size[0] // 2,
        state.player_rect.centery - effective_size[1] // 2,
        effective_size[0],
        effective_size[1],
    )
    state.player_bullets.append({
        "rect": r,
        "vel": d * effective_speed,
        "shape": shape,
        "color": weapon_config.get("color", player_bullets_color),
        "damage": effective_damage,
        "penetration": int(state.player_stat_multipliers["bullet_penetration"]),
        "explosion_radius": rocket_explosion,
        "knockback": state.player_stat_multipliers["bullet_knockback"],
        "bounces": weapon_config["max_bounces"],
        "is_rocket": weapon_config["is_rocket"],
    })
    state.shots_fired += 1
    
    # Play sound effect based on weapon mode
    if weapon_config["is_rocket"]:
        play_sfx("ROCKET")
    else:
        play_sfx("BASIC SHOT")
    
    # Record shot for GPU particle effect
    # Convert player position to normalized screen coordinates [0,1]
    display_w = getattr(ctx, 'display_width', ctx.width) if hasattr(ctx, 'display_width') else 800
    display_h = getattr(ctx, 'display_height', ctx.height) if hasattr(ctx, 'display_height') else 600
    
    # Get camera offset if available
    from systems.camera import get_camera
    camera = get_camera()
    if camera:
        screen_x = (state.player_rect.centerx - camera.x) / display_w
        screen_y = (state.player_rect.centery - camera.y) / display_h
    else:
        screen_x = state.player_rect.centerx / display_w
        screen_y = state.player_rect.centery / display_h
    
    # Clamp to valid range and add shot
    screen_x = max(0.0, min(1.0, screen_x))
    screen_y = max(0.0, min(1.0, screen_y))
    
    # Use rocket effect for rocket weapons, otherwise regular shot
    shot_state = get_shot_particle_state()
    if weapon_config.get("is_rocket", False):
        shot_state.add_rocket((screen_x, screen_y))
    else:
        shot_state.add_shot((screen_x, screen_y))

    if ctx.config.enable_telemetry and ctx.telemetry_client:
        ctx.telemetry_client.log_shot(
            ShotEvent(
                t=state.run_time,
                origin_x=state.player_rect.centerx,
                origin_y=state.player_rect.centery,
                target_x=mx,
                target_y=my,
                dir_x=float(d.x),
                dir_y=float(d.y),
            )
        )
    
        # Log bullet metadata
        ctx.telemetry_client.log_bullet_metadata(
            BulletMetadataEvent(
                t=state.run_time,
                bullet_type="player",
                shape=shape,
                color_r=player_bullets_color[0],
                color_g=player_bullets_color[1],
                color_b=player_bullets_color[2],
            )
        )
    
    # Track shot for DDA (regardless of telemetry setting)
    _track_dda_shot()


# DDA tracking helpers (lazy-loaded)
_dda_integration = None


def _get_dda():
    """Lazy-load DDA integration."""
    global _dda_integration
    if _dda_integration is None:
        try:
            from ml.dda_integration import get_dda
            _dda_integration = get_dda()
        except ImportError:
            _dda_integration = False
    return _dda_integration if _dda_integration is not False else None


def _track_dda_shot() -> None:
    """Track regular shot for DDA."""
    dda = _get_dda()
    if dda:
        dda.on_shot_fired()


def spawn_enemy_projectile(enemy: dict, state: GameState, telemetry_client=None, telemetry_enabled: bool = False):
    """Spawn projectile from enemy targeting nearest threat (player or friendly AI).
    
    Respects max-enemies-targeting-player cap and projectile limits.
    """
    if state.player_rect is None:
        return
    
    # Check projectile limit for performance
    ctx = getattr(state, "level_context", None)
    config = ctx.get("config") if ctx else None
    max_projectiles = getattr(config, "max_enemy_projectiles", 300) if config else 300
    if max_projectiles > 0 and len(state.enemy_projectiles) >= max_projectiles:
        return  # Don't spawn more projectiles if at limit
    e_pos = pygame.Vector2(enemy["rect"].center)
    ctx = getattr(state, "level_context", None)
    allow_player = id(enemy) in ctx.get("_player_targeting_slots", set()) if ctx else True
    threat_result = find_nearest_threat(e_pos, state.player_rect, state.friendly_ai, allow_player=allow_player)
    
    # Calculate direction
    if threat_result:
        threat_pos, threat_type = threat_result
        d = vec_toward(e_pos.x, e_pos.y, threat_pos.x, threat_pos.y)
    elif allow_player:
        # Fallback to player if no threats and this enemy may target player
        d = vec_toward(enemy["rect"].centerx, enemy["rect"].centery, state.player_rect.centerx, state.player_rect.centery)
    else:
        # No threat and not allowed to target player; fire in a neutral direction
        d = pygame.Vector2(1, 0)
    
    edef = get_projectile_def("enemy_default")
    proj_size = edef["size"] if edef else enemy_projectile_size
    default_color = edef["color"] if edef else enemy_projectiles_color
    # Create projectile rect and properties (used regardless of threat result)
    r = pygame.Rect(
        enemy["rect"].centerx - proj_size[0] // 2,
        enemy["rect"].centery - proj_size[1] // 2,
        proj_size[0],
        proj_size[1],
    )
    proj_color = enemy.get("projectile_color", default_color)
    proj_shape = enemy.get("projectile_shape", "circle")
    bounces = enemy.get("bouncing_projectiles", False)
    
    proj_damage = enemy.get("flame_damage", enemy.get("damage", 10))
    state.enemy_projectiles.append({
        "rect": r,
        "vel": d * enemy["projectile_speed"],
        "enemy_type": enemy["type"],
        "color": proj_color,
        "shape": proj_shape,
        "bounces": 10 if bounces else 0,
        "damage": proj_damage,
    })
    
    # Log enemy projectile metadata
    if telemetry_enabled and telemetry_client:
        telemetry_client.log_bullet_metadata(
            BulletMetadataEvent(
                t=state.run_time,
                bullet_type="enemy",
                shape=proj_shape,
                color_r=proj_color[0],
                color_g=proj_color[1],
                color_b=proj_color[2],
                source_enemy_type=enemy["type"],
            )
        )


def spawn_enemy_projectile_predictive(enemy: dict, direction: pygame.Vector2, state: GameState):
    """Spawn projectile from predictive enemy in a specific direction (predicted player position)."""
    edef = get_projectile_def("enemy_default")
    proj_size = edef["size"] if edef else enemy_projectile_size
    default_color = edef["color"] if edef else enemy_projectiles_color
    r = pygame.Rect(
        enemy["rect"].centerx - proj_size[0] // 2,
        enemy["rect"].centery - proj_size[1] // 2,
        proj_size[0],
        proj_size[1],
    )
    proj_color = enemy.get("projectile_color", default_color)
    proj_shape = enemy.get("projectile_shape", "diamond")  # Rhomboid shape
    state.enemy_projectiles.append({
        "rect": r,
        "vel": direction * enemy["projectile_speed"],
        "enemy_type": enemy["type"],
        "color": proj_color,
        "shape": proj_shape,
        "bounces": 0,
        "lifetime": 5.0,  # Projectiles disappear after 5 seconds to prevent lingering
    })


def spawn_boss_projectile(boss: dict, direction: pygame.Vector2, state: GameState):
    """Spawn a projectile from the boss in a specific direction."""
    edef = get_projectile_def("enemy_default")
    proj_size = edef["size"] if edef else enemy_projectile_size
    default_color = edef["color"] if edef else enemy_projectiles_color
    r = pygame.Rect(
        boss["rect"].centerx - proj_size[0] // 2,
        boss["rect"].centery - proj_size[1] // 2,
        proj_size[0],
        proj_size[1],
    )
    proj_color = boss.get("projectile_color", default_color)
    proj_shape = boss.get("projectile_shape", "circle")
    state.enemy_projectiles.append({
        "rect": r,
        "vel": direction * boss["projectile_speed"],
        "enemy_type": boss["type"],
        "color": proj_color,
        "shape": proj_shape,
        "bounces": 0,
        "lifetime": 5.0,  # Boss projectiles disappear after 5 seconds to prevent lingering
    })


def spawn_ally_missile(friendly: dict, target_enemy: dict, state: GameState) -> None:
    """Spawn a burst of seeking missiles from an ally (e.g. striker) toward target_enemy."""
    burst = friendly.get("missile_burst_count", 3)
    damage = friendly.get("missile_damage", 300)
    radius = friendly.get("missile_explosion_radius", 80)
    speed_val = 500
    burst_offsets = [(-10, -10), (0, -15), (10, -10)]
    for i in range(burst):
        ox, oy = burst_offsets[i % len(burst_offsets)]
        cx, cy = friendly["rect"].centerx, friendly["rect"].centery
        r = pygame.Rect(cx - 8 + ox, cy - 8 + oy, 16, 16)
        state.missiles.append({
            "rect": r,
            "vel": pygame.Vector2(0, 0),
            "target_enemy": target_enemy,
            "speed": speed_val,
            "damage": damage,
            "explosion_radius": radius,
        })
