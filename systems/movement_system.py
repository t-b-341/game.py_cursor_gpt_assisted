"""Movement updates: player, enemies, projectiles, missiles, allies.

All per-frame position updates are centralized here. Geometry and callables come from state.level_context.
"""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import pygame

from constants import MAX_ENEMIES_TARGETING_PLAYER
from enemies import find_nearest_threat, find_threats_in_dodge_range
from physics_loader import distance_squared as c_distance_squared

try:
    from ecs_components import PositionComponent, VelocityComponent
    _ECS_AVAILABLE = True
except ImportError:
    _ECS_AVAILABLE = False

try:
    from gpu_physics import update_bullets_batch, CUDA_AVAILABLE
    _USE_GPU = CUDA_AVAILABLE  # Single capability flag: True only when GPU path is usable
except Exception:
    _USE_GPU = False
    update_bullets_batch = None

_gpu_bullet_logged = False

if TYPE_CHECKING:
    from state import GameState


def update(state: "GameState", dt: float) -> None:
    """Update movement for all moving entities. Called from gameplay."""
    ctx = getattr(state, "level_context", None)
    if ctx is None:
        return

    player = state.player_rect
    if player is None:
        return

    _update_player(state, dt, ctx)
    _update_enemies(state, dt, ctx)
    _update_player_bullets(state, dt, ctx)
    _update_enemy_projectiles(state, dt, ctx)
    _update_friendly_projectiles(state, dt, ctx)
    _update_missiles(state, dt, ctx)
    _update_ecs_position_velocity(state, dt)
    # Ally AI is run in ai_system.update()


def _update_player(state, dt: float, ctx: dict) -> None:
    """Player position from input and jump velocity."""
    player = state.player_rect
    if player is None:
        return

    move_x = getattr(state, "move_input_x", 0)
    move_y = getattr(state, "move_input_y", 0)
    speed_mult = getattr(state, "speed_mult", 1.0)
    move_player = ctx.get("move_player")
    clamp = ctx.get("clamp")

    if move_x != 0 or move_y != 0:
        move_dir = pygame.Vector2(move_x, move_y).normalize()
        move_speed = state.player_speed * speed_mult * state.player_stat_multipliers["speed"]
        if state.is_jumping:
            move_speed += state.jump_velocity.length()
        move_amount = move_speed * dt
        move_vec = move_dir * move_amount
        state.last_move_velocity = move_dir * move_speed
        if move_player:
            move_player(player, int(move_vec.x), int(move_vec.y))
        if clamp:
            clamp(player)
    else:
        state.last_move_velocity = pygame.Vector2(0, 0)

    if state.is_jumping:
        player.x += int(state.jump_velocity.x * dt)
        player.y += int(state.jump_velocity.y * dt)
        if clamp:
            clamp(player)


def _nearest_point_on_perimeter(pos: pygame.Vector2, rect: pygame.Rect) -> pygame.Vector2:
    """Nearest point on the perimeter of rect to pos."""
    x, y = pos.x, pos.y
    cx = max(rect.left, min(rect.right, x))
    cy = max(rect.top, min(rect.bottom, y))
    candidates = [
        (cx, rect.top),
        (cx, rect.bottom),
        (rect.left, cy),
        (rect.right, cy),
    ]
    best = min(candidates, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)
    return pygame.Vector2(best[0], best[1])


def _update_enemies(state, dt: float, ctx: dict) -> None:
    """Enemy position: chase target, patrol outer until player leaves main area, stuck/wander/dodge."""
    player = state.player_rect
    if player is None:
        return

    move_enemy = ctx.get("move_enemy")
    vec_toward = ctx.get("vec_toward")
    width = ctx.get("width", 1920)
    height = ctx.get("height", 1080)
    main_area = ctx.get("main_area_rect")
    outer_margin = 80
    outer_rect = pygame.Rect(outer_margin, outer_margin, width - 2 * outer_margin, height - 2 * outer_margin) if (width > 2 * outer_margin and height > 2 * outer_margin) else None

    if not move_enemy or not vec_toward:
        return

    player_in_main = main_area and main_area.collidepoint(player.centerx, player.centery) if main_area else False

    # Only allow up to N enemies to target the player; the rest target friendlies or patrol. Closest N by distance get the slots.
    # Use C-accelerated distance calculations for performance
    pcx, pcy = player.centerx, player.centery
    candidates = [
        (e, c_distance_squared(e["rect"].centerx, e["rect"].centery, pcx, pcy))
        for e in state.enemies
        if e.get("hp", 1) > 0 and not e.get("is_ambient")
    ]
    candidates.sort(key=lambda x: x[1])
    ctx["_player_targeting_slots"] = set(id(e) for e, _ in candidates[:MAX_ENEMIES_TARGETING_PLAYER])

    for enemy in state.enemies:
        if enemy.get("hp", 1) <= 0:
            continue
        if enemy.get("is_ambient"):
            continue  # Stationary

        current_pos = pygame.Vector2(enemy["rect"].center)
        last_pos = enemy.get("last_pos", current_pos)
        stuck_timer = enemy.get("stuck_timer", 0.0)
        # Use C-accelerated distance for stuck detection
        distance_moved_sq = c_distance_squared(current_pos.x, current_pos.y, last_pos.x, last_pos.y)
        distance_moved = math.sqrt(distance_moved_sq) if distance_moved_sq > 0 else 0.0
        if distance_moved < 5.0:
            stuck_timer += dt
        else:
            stuck_timer = 0.0
        enemy["last_pos"] = current_pos
        enemy["stuck_timer"] = stuck_timer

        enemy_pos = pygame.Vector2(enemy["rect"].center)
        allow_player = id(enemy) in ctx.get("_player_targeting_slots", set())
        target_info = find_nearest_threat(enemy_pos, player, state.friendly_ai, allow_player=allow_player)

        # When player is in main area, non-boss non-patrol enemies patrol the outer area
        if target_info and player_in_main and outer_rect and not enemy.get("is_boss") and not enemy.get("is_patrol"):
            patrol_target = _nearest_point_on_perimeter(enemy_pos, outer_rect)
            target_pos = patrol_target
        elif target_info:
            target_pos, _ = target_info
        else:
            target_pos = None

        if target_pos is not None:
            direction = vec_toward(enemy_pos.x, enemy_pos.y, target_pos.x, target_pos.y)
            if direction.length_squared() < 1e-6:
                direction = pygame.Vector2(1, 0)  # already at target, avoid normalizing zero
            else:
                direction = direction.normalize()
            enemy_speed = enemy.get("speed", 80) * dt

            # Bait grenades: approach player then retreat from grenade range (get in, get out)
            if target_info and not enemy.get("is_boss") and not enemy.get("is_patrol") and not enemy.get("is_ambient"):
                target_pos_v, target_type = target_info
                if target_type == "player":
                    dist_to_player = enemy_pos.distance_to(pygame.Vector2(player.center))
                    GRENADE_BAIT_INNER, GRENADE_BAIT_OUTER = 120.0, 220.0
                    phase = enemy.get("bait_phase", "approach")
                    if dist_to_player < GRENADE_BAIT_INNER:
                        phase = "retreat"
                    elif dist_to_player > GRENADE_BAIT_OUTER:
                        phase = "approach"
                    enemy["bait_phase"] = phase
                    if phase == "retreat":
                        away = vec_toward(player.centerx, player.centery, enemy_pos.x, enemy_pos.y)
                        if away.length_squared() >= 1e-6:
                            direction = away.normalize()

            if len(state.enemies) <= 5 and not player_in_main:
                direction = vec_toward(enemy_pos.x, enemy_pos.y, player.centerx, player.centery)
                if direction.length_squared() >= 1e-6:
                    direction = direction.normalize()
            else:
                if stuck_timer >= 5.0:
                    direction = -direction
                    random_angle = random.uniform(0, 2 * math.pi)
                    escape_dir = pygame.Vector2(math.cos(random_angle), math.sin(random_angle))
                    direction = direction + escape_dir * 0.5
                    if direction.length_squared() >= 1e-6:
                        direction = direction.normalize()
                    else:
                        direction = escape_dir
                    enemy["stuck_timer"] = 0.0

                if random.random() < 0.25:
                    wander_angle = random.uniform(-0.8, 0.8)
                    cos_a = math.cos(wander_angle)
                    sin_a = math.sin(wander_angle)
                    direction = pygame.Vector2(
                        direction.x * cos_a - direction.y * sin_a,
                        direction.x * sin_a + direction.y * cos_a,
                    )
                    if direction.length_squared() >= 1e-6:
                        direction = direction.normalize()
                    # else keep previous direction

                if random.random() < 0.05:
                    random_angle = random.uniform(0, 2 * math.pi)
                    direction = pygame.Vector2(math.cos(random_angle), math.sin(random_angle))

                # Dodge shots: always try to sidestep when bullets/projectiles are in range
                # Evasive enemies have larger dodge range and stronger dodge
                is_evasive = enemy.get("is_evasive", False)
                dodge_range = 320.0 if is_evasive else 220.0
                dodge_strength = 1.2 if is_evasive else 0.6
                dodge_threats = find_threats_in_dodge_range(
                    enemy_pos, state.player_bullets, state.friendly_projectiles, dodge_range
                )
                if dodge_threats:
                    dodge_dir = pygame.Vector2(-direction.y, direction.x)
                    if random.random() < 0.5:
                        dodge_dir = -dodge_dir
                    direction = direction + dodge_dir * dodge_strength
                    if direction.length_squared() >= 1e-6:
                        direction = direction.normalize()

            move_x = int(direction.x * enemy_speed)
            move_y = int(direction.y * enemy_speed)
            move_enemy(state, enemy["rect"], move_x, move_y)

        if enemy.get("is_patrol"):
            patrol_side = enemy.get("patrol_side", 0)
            patrol_progress = enemy.get("patrol_progress", 0.0)
            patrol_speed = 0.3 * dt
            patrol_progress += patrol_speed
            if patrol_progress >= 1.0:
                patrol_progress = 0.0
                patrol_side = (patrol_side + 1) % 4
                enemy["patrol_side"] = patrol_side
            enemy["patrol_progress"] = patrol_progress
            border_margin = 50
            if patrol_side == 0:
                x = border_margin + (width - 2 * border_margin) * patrol_progress
                y = border_margin
            elif patrol_side == 1:
                x = width - border_margin
                y = border_margin + (height - 2 * border_margin) * patrol_progress
            elif patrol_side == 2:
                x = width - border_margin - (width - 2 * border_margin) * patrol_progress
                y = height - border_margin
            else:
                x = border_margin
                y = height - border_margin - (height - 2 * border_margin) * patrol_progress
            enemy["rect"].center = (int(x), int(y))


def _update_player_bullets(state, dt: float, ctx: dict) -> None:
    """Advance player bullet positions (no collision/removal).
    GPU physics is gated solely by config.use_gpu_physics (config from app_ctx via level_context)."""
    global _gpu_bullet_logged
    config = ctx.get("config")
    use_gpu = _USE_GPU and (config is not None and bool(getattr(config, "use_gpu_physics", False)))

    if use_gpu and not _gpu_bullet_logged:
        print("GPU bullet physics: ENABLED (config + CUDA)")
        _gpu_bullet_logged = True
    elif _USE_GPU and config is not None and not use_gpu and not _gpu_bullet_logged:
        print("GPU bullet physics: DISABLED by config")
        _gpu_bullet_logged = True

    if use_gpu and update_bullets_batch is not None and state.player_bullets:
        bullets_data = [
            {"x": b["rect"].x, "y": b["rect"].y, "vx": b["vel"].x, "vy": b["vel"].y, "w": b["rect"].w, "h": b["rect"].h}
            for b in state.player_bullets
        ]
        w, h = ctx.get("width", 0), ctx.get("height", 0)
        keep_indices = update_bullets_batch(bullets_data, dt, w, h)
        new_bullets = []
        for idx in keep_indices:
            if 0 <= idx < len(state.player_bullets):
                b = state.player_bullets[idx]
                b["rect"].x = int(bullets_data[idx]["x"])
                b["rect"].y = int(bullets_data[idx]["y"])
                new_bullets.append(b)
        state.player_bullets[:] = new_bullets
        return

    for bullet in state.player_bullets:
        bullet["rect"].x += int(bullet["vel"].x * dt)
        bullet["rect"].y += int(bullet["vel"].y * dt)


def _update_enemy_projectiles(state, dt: float, ctx: dict) -> None:
    """Advance enemy projectile positions and lifetime."""
    for proj in state.enemy_projectiles:
        proj["rect"].x += int(proj["vel"].x * dt)
        proj["rect"].y += int(proj["vel"].y * dt)
        if "lifetime" in proj:
            proj["lifetime"] -= dt


def _update_friendly_projectiles(state, dt: float, ctx: dict) -> None:
    """Advance friendly projectile positions."""
    for proj in state.friendly_projectiles:
        proj["rect"].x += int(proj["vel"].x * dt)
        proj["rect"].y += int(proj["vel"].y * dt)


def _missile_hits_wall(missile_rect: pygame.Rect, state: "GameState") -> bool:
    """True if missile rect overlaps any solid block (walls block missiles). Uses LevelState instead of module-level globals."""
    lev = getattr(state, "level", None)
    if lev is None:
        return False
    for b in lev.static_blocks:
        if missile_rect.colliderect(b.get("rect", b)):
            return True
    for b in lev.destructible_blocks:
        if missile_rect.colliderect(b.get("rect", b)):
            return True
    for b in lev.moveable_blocks:
        if missile_rect.colliderect(b.get("rect", b)):
            return True
    for gb in lev.giant_blocks:
        if missile_rect.colliderect(gb.get("rect", gb)):
            return True
    for sgb in lev.super_giant_blocks:
        if missile_rect.colliderect(sgb.get("rect", sgb)):
            return True
    for tb in lev.trapezoid_blocks:
        r = tb.get("bounding_rect") or tb.get("rect")
        if r and missile_rect.colliderect(r):
            return True
    for tr in lev.triangle_blocks:
        r = tr.get("bounding_rect") or tr.get("rect")
        if r and missile_rect.colliderect(r):
            return True
    return False


def _update_missiles(state, dt: float, ctx: dict) -> None:
    """Update missile velocities (seek), positions; walls block missiles (explode on hit).
    
    Dropped allies draw missile aggro - enemy missiles will redirect to target
    the dropped ally instead of the player when one is active.
    """
    player = state.player_rect
    if player is None:
        return

    for missile in state.missiles[:]:
        if missile.get("target_player"):
            # Check if there's a dropped ally to draw missile aggro
            dropped_ally = getattr(state, "dropped_ally", None)
            if dropped_ally and dropped_ally in state.friendly_ai and dropped_ally.get("hp", 0) > 0:
                # Dropped ally draws missile attention - redirect to ally
                ally_rect = dropped_ally.get("rect")
                if ally_rect:
                    target_pos = pygame.Vector2(ally_rect.center)
                else:
                    target_pos = pygame.Vector2(player.center)
            else:
                # No dropped ally, target player as normal
                target_pos = pygame.Vector2(player.center)
            
            missile_pos = pygame.Vector2(missile["rect"].center)
            d = (target_pos - missile_pos)
            if d.length_squared() > 0:
                direction = d.normalize()
                missile["vel"] = direction * missile["speed"]
        elif missile.get("target_enemy"):
            if missile["target_enemy"] not in state.enemies:
                target_enemy = None
                min_dist = float("inf")
                for e in state.enemies:
                    d = (pygame.Vector2(e["rect"].center) - pygame.Vector2(missile["rect"].center)).length_squared()
                    if d < min_dist:
                        min_dist = d
                        target_enemy = e
                missile["target_enemy"] = target_enemy
            if missile["target_enemy"]:
                target_pos = pygame.Vector2(missile["target_enemy"]["rect"].center)
                missile_pos = pygame.Vector2(missile["rect"].center)
                d = (target_pos - missile_pos)
                if d.length_squared() > 0:
                    direction = d.normalize()
                    missile["vel"] = direction * missile["speed"]

        missile["rect"].x += int(missile["vel"].x * dt)
        missile["rect"].y += int(missile["vel"].y * dt)

        if _missile_hits_wall(missile["rect"], state):
            state.grenade_explosions.append({
                "x": missile["rect"].centerx,
                "y": missile["rect"].centery,
                "radius": 0,
                "max_radius": missile.get("explosion_radius", 150),
                "timer": 0.3,
                "damage": missile.get("damage", 100),
                "source": "wall_impact",  # Player takes no damage from missile-on-wall explosions
            })
            state.missiles.remove(missile)


def _update_ecs_position_velocity(state: "GameState", dt: float) -> None:
    """Move ECS entities that have PositionComponent and VelocityComponent. No-op if registry empty."""
    if not _ECS_AVAILABLE:
        return
    ecs = getattr(state, "ecs_entities", None)
    if not ecs:
        return
    for eid in state.get_entities_with(PositionComponent, VelocityComponent):
        comps = ecs.get(eid, {})
        pos = comps.get(PositionComponent)
        vel = comps.get(VelocityComponent)
        if pos is None or vel is None or pos.rect is None:
            continue
        pos.rect.x += int(vel.vx * dt)
        pos.rect.y += int(vel.vy * dt)
