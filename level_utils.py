"""Level/setup helper functions. Used by game.py for block filtering, enemy cloning, and level context building."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from config.enemy_defs import ENEMY_TEMPLATES
from enemies import make_enemy_from_template

if TYPE_CHECKING:
    from context import AppContext
    from state import GameState


def filter_blocks_no_overlap(block_list: list[dict], all_other_blocks: list[list[dict]], player_rect: pygame.Rect) -> list[dict]:
    """Filter blocks to remove those too close to player and overlapping with other blocks."""
    filtered = []
    player_center = pygame.Vector2(player_rect.center)
    player_size = max(player_rect.w, player_rect.h)  # Use larger dimension (28)
    min_block_distance = player_size * 10  # 10x player size = 280 pixels

    for block in block_list:
        block_rect = block["rect"]
        block_center = pygame.Vector2(block_rect.center)

        # Check distance from player
        if block_center.distance_to(player_center) < min_block_distance:
            continue

        # Check collision with player
        if block_rect.colliderect(player_rect):
            continue

        # Check collision with other blocks
        overlaps = False
        for other_block_list in all_other_blocks:
            for other_block in other_block_list:
                if block_rect.colliderect(other_block["rect"]):
                    overlaps = True
                    break
            if overlaps:
                break

        # Check collision with other blocks in same list (prevent self-overlap)
        if not overlaps:
            for other_block in block_list:
                if other_block is not block and block_rect.colliderect(other_block["rect"]):
                    overlaps = True
                    break

        if not overlaps:
            filtered.append(block)

    return filtered


def clone_enemies_from_templates() -> list[dict]:
    # Kept for compatibility but waves use start_wave() instead.
    return [make_enemy_from_template(t, 1.0, 1.0) for t in ENEMY_TEMPLATES]


def make_level_context(ctx: "AppContext", game_state: "GameState") -> dict:
    """Build the level_context dict for movement_system and collision_system.
    
    Contains callables and data that systems need to interact with level geometry,
    spawn projectiles, handle player death, etc. Uses lambdas to capture ctx/game_state.
    
    Args:
        ctx: AppContext with config, telemetry, event_bus
        game_state: GameState with level geometry, teleporter_pads
    
    Returns:
        Dict with all level context callables and data
    """
    from config.balance import (
        overshield_recharge_cooldown,
        ally_drop_cooldown,
        ENEMY_PROJECTILE_SIZE,
        ENEMY_PROJECTILES_COLOR,
        missile_damage,
    )
    # Use uppercase constants
    enemy_projectile_size = ENEMY_PROJECTILE_SIZE
    enemy_projectiles_color = ENEMY_PROJECTILES_COLOR
    from allies import find_nearest_enemy, update_friendly_ai
    from enemies import find_nearest_threat
    from geometry_utils import clamp_rect_to_screen, vec_toward, line_rect_intersection
    from hazards import check_point_in_hazard
    from systems.collision_movement import move_player_with_push, move_enemy_with_push
    from pickups import apply_pickup_effect
    from systems.audio_system import play_sfx
    from systems.enemy_death import reset_after_death, kill_enemy
    from systems.projectile_spawning import (
        spawn_enemy_projectile,
        spawn_enemy_projectile_predictive,
        spawn_ally_missile,
    )
    from allies import spawn_friendly_projectile
    from systems.spawn_helpers import random_spawn_position, create_pickup_collection_effect
    from telemetry import PlayerDeathEvent
    
    w, h = ctx.width, ctx.height
    lv = game_state.level

    def _log_player_death(t, px, py, lives_left, wave_num):
        if ctx.config.enable_telemetry and ctx.telemetry_client:
            ctx.telemetry_client.log_player_death(
                PlayerDeathEvent(t=t, player_x=px, player_y=py, lives_left=lives_left, wave_number=wave_num)
            )

    return {
        "move_player": lambda p, dx, dy: move_player_with_push(p, dx, dy, lv, w, h),
        "move_enemy": lambda s, rect, mx, my: move_enemy_with_push(rect, mx, my, lv, s, w, h),
        "clamp": lambda r: clamp_rect_to_screen(r, w, h),
        "blocks": lv.static_blocks,
        "width": w,
        "height": h,
        "main_area_rect": pygame.Rect(int(w * 0.25), int(h * 0.25), int(w * 0.5), int(h * 0.5)),
        "rect_offscreen": lambda r: r.right < 0 or r.left > w or r.bottom < 0 or r.top > h,
        "vec_toward": vec_toward,
        "update_friendly_ai": lambda s, dt: update_friendly_ai(
            s.friendly_ai, s.enemies, lv.static_blocks, dt,
            find_nearest_enemy, vec_toward,
            lambda rect, mx, my, bl: move_enemy_with_push(rect, mx, my, lv, s, w, h),
            lambda f, t: spawn_friendly_projectile(f, t, s.friendly_projectiles, vec_toward, ctx.telemetry_client, s.run_time),
            state=s,
            player_rect=getattr(s, "player_rect", None),
            spawn_ally_missile_func=lambda f, t, st: spawn_ally_missile(f, t, st),
        ),
        "kill_enemy": lambda e, s: kill_enemy(e, s, w, h, getattr(ctx, "event_bus", None)),
        "destructible_blocks": lv.destructible_blocks,
        "moveable_destructible_blocks": lv.moveable_blocks,
        "giant_blocks": lv.giant_blocks,
        "super_giant_blocks": lv.super_giant_blocks,
        "trapezoid_blocks": lv.trapezoid_blocks,
        "triangle_blocks": lv.triangle_blocks,
        "hazard_obstacles": lv.hazard_obstacles,
        "moving_health_zone": lv.moving_health_zone,
        "teleporter_pads": game_state.teleporter_pads,
        "check_point_in_hazard": check_point_in_hazard,
        "line_rect_intersection": line_rect_intersection,
        "testing_mode": ctx.config.testing_mode,
        "invulnerability_mode": ctx.config.invulnerability_mode,
        "reset_after_death": lambda s: reset_after_death(s, w, h),
        "create_pickup_collection_effect": create_pickup_collection_effect,
        "apply_pickup_effect": lambda pt, s: apply_pickup_effect(pt, s, ctx),
        "enemy_projectile_size": enemy_projectile_size,
        "enemy_projectiles_color": enemy_projectiles_color,
        "missile_damage": missile_damage,
        "find_nearest_threat": find_nearest_threat,
        "spawn_enemy_projectile": lambda e, s: spawn_enemy_projectile(e, s, ctx.telemetry_client, ctx.config.enable_telemetry),
        "spawn_enemy_projectile_predictive": spawn_enemy_projectile_predictive,
        "difficulty": ctx.config.difficulty,
        "random_spawn_position": lambda size, state, max_attempts=25: random_spawn_position(size, state, w, h, max_attempts),
        "telemetry": ctx.telemetry_client,
        "telemetry_enabled": ctx.config.enable_telemetry,
        "overshield_recharge_cooldown": overshield_recharge_cooldown,
        "ally_drop_cooldown": ally_drop_cooldown,
        "play_sfx": play_sfx,
        "damage_flash_duration": getattr(ctx.config, "damage_flash_duration", 0.12),
        "screen_flash_duration": getattr(ctx.config, "screen_flash_duration", 0.25),
        "screen_flash_max_alpha": getattr(ctx.config, "screen_flash_max_alpha", 100),
        "enable_damage_flash": getattr(ctx.config, "enable_damage_flash", True),
        "enable_screen_flash": getattr(ctx.config, "enable_screen_flash", True),
        "enable_damage_wobble": getattr(ctx.config, "enable_damage_wobble", False),
        "enable_wave_banner": getattr(ctx.config, "enable_wave_banner", True),
        "wave_banner_duration": getattr(ctx.config, "wave_banner_duration", 1.5),
        "base_enemies_per_wave": getattr(ctx.config, "base_enemies_per_wave", 12),
        "enemy_spawn_multiplier": getattr(ctx.config, "enemy_spawn_multiplier", 3.5),
        "log_player_death": _log_player_death,
        "config": ctx.config,
    }
