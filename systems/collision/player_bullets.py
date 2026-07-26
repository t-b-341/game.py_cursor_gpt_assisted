"""Player bullet collisions: vs enemies, blocks, off-screen, and dead-enemy cleanup.

Moved verbatim from systems/collision_projectiles.py - this is the implementation
that has actually been running. See AGENTS.md §10.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from ..collision_common import record_enemy_hit, set_enemy_damage_flash
from ..spatial_grid import invalidate_block_grid
from .helpers import (
    build_block_grid as _build_block_grid,
    build_enemy_grid as _build_enemy_grid,
    create_damage_number as _create_damage_number,
)

if TYPE_CHECKING:
    from state import GameState


try:
    from gpu_physics import check_collisions_batch, CUDA_AVAILABLE
    _USE_GPU_COLLISION = CUDA_AVAILABLE
except Exception:  # pragma: no cover - gpu_physics is not present in this repo
    _USE_GPU_COLLISION = False
    check_collisions_batch = None


def handle_dead_enemies(state, ctx: dict) -> None:
    kill = ctx.get("kill_enemy")
    if not kill:
        return
    for enemy in state.enemies[:]:
        if enemy.get("hp", 1) <= 0:
            kill(enemy, state)


def handle_player_bullet_offscreen(state, ctx: dict) -> None:
    """Remove offscreen bullets using efficient filtering."""
    offscreen = ctx.get("rect_offscreen")
    if not offscreen:
        return
    # Use list comprehension for O(n) removal instead of O(n²)
    state.player_bullets[:] = [b for b in state.player_bullets if not offscreen(b["rect"])]


def _process_bullet_enemy_hit(state, ctx: dict, bullet: dict, enemy: dict) -> None:
    """Apply one bullet–enemy collision (shield reflect, reflective shield, or direct damage). Caller breaks after one hit per bullet."""
    kill = ctx.get("kill_enemy")
    size = ctx.get("enemy_projectile_size", (12, 12))
    color = ctx.get("enemy_projectiles_color", (200, 200, 200))
    if not kill:
        return
    player_damage = state.player_bullet_damage
    if enemy.get("has_shield") and not enemy.get("has_reflective_shield"):
        center = pygame.Vector2(enemy["rect"].center)
        bcenter = pygame.Vector2(bullet["rect"].center)
        to_bullet = (bcenter - center)
        if to_bullet.length_squared() > 0:
            to_bullet = to_bullet.normalize()
        sh_angle = enemy.get("shield_angle", 0.0)
        sh_dir = pygame.Vector2(math.cos(sh_angle), math.sin(sh_angle))
        from_front = to_bullet.dot(-sh_dir) > 0.0
        if from_front:
            dmg = int((bullet.get("damage", player_damage)) * enemy.get("reflect_damage_mult", 1.5))
            ref = pygame.Rect(
                enemy["rect"].centerx - size[0] // 2,
                enemy["rect"].centery - size[1] // 2,
                size[0], size[1],
            )
            state.enemy_projectiles.append({
                "rect": ref,
                "vel": to_bullet * enemy.get("projectile_speed", 300),
                "enemy_type": enemy["type"],
                "color": enemy.get("projectile_color", color),
                "shape": enemy.get("projectile_shape", "circle"),
                "bounces": 0,
                "damage": dmg,
            })
            if bullet in state.player_bullets:
                state.player_bullets.remove(bullet)
            return
    if enemy.get("has_reflective_shield"):
        center = pygame.Vector2(enemy["rect"].center)
        bcenter = pygame.Vector2(bullet["rect"].center)
        bdir = (bcenter - center)
        if bdir.length_squared() > 0:
            bdir = bdir.normalize()
        sh_angle = enemy.get("shield_angle", 0.0)
        sh_dir = pygame.Vector2(math.cos(sh_angle), math.sin(sh_angle))
        if bdir.dot(-sh_dir) > 0.0:
            dmg = bullet.get("damage", player_damage)
            enemy["shield_hp"] = enemy.get("shield_hp", 0) + dmg
            if enemy["shield_hp"] > 0:
                ref = pygame.Rect(
                    enemy["rect"].centerx - size[0] // 2,
                    enemy["rect"].centery - size[1] // 2,
                    size[0], size[1],
                )
                state.enemy_projectiles.append({
                    "rect": ref,
                    "vel": -bdir * enemy.get("projectile_speed", 300),
                    "enemy_type": enemy["type"],
                    "color": enemy.get("projectile_color", color),
                    "shape": enemy.get("projectile_shape", "circle"),
                    "bounces": 0,
                })
                enemy["shield_hp"] = 0
            if bullet in state.player_bullets:
                state.player_bullets.remove(bullet)
            return
        dmg = bullet.get("damage", player_damage)
        enemy["hp"] -= dmg
        record_enemy_hit(state, ctx, enemy, dmg, enemy["hp"], enemy["hp"] <= 0)
        set_enemy_damage_flash(enemy, ctx)
        state.damage_numbers.append(_create_damage_number(
            enemy["rect"].centerx, enemy["rect"].y - 20, dmg
        ))
        if enemy["hp"] <= 0:
            kill(enemy, state)
        if bullet.get("penetration", 0) <= 0:
            if bullet in state.player_bullets:
                state.player_bullets.remove(bullet)
            return
        bullet["penetration"] = bullet.get("penetration", 0) - 1
        return
    dmg = bullet.get("damage", player_damage)
    enemy["hp"] -= dmg
    record_enemy_hit(state, ctx, enemy, dmg, enemy["hp"], enemy["hp"] <= 0)
    set_enemy_damage_flash(enemy, ctx)
    state.damage_numbers.append(_create_damage_number(
        enemy["rect"].centerx, enemy["rect"].y - 20, dmg
    ))
    if enemy["hp"] <= 0:
        kill(enemy, state)
    if bullet.get("penetration", 0) <= 0:
        if bullet in state.player_bullets:
            state.player_bullets.remove(bullet)
        return
    bullet["penetration"] = bullet.get("penetration", 0) - 1


def handle_player_bullet_enemy_collisions(state, ctx: dict) -> None:
    """Handle bullet-enemy collisions using spatial grid for O(n) performance."""
    kill = ctx.get("kill_enemy")
    if not kill:
        return
    config = ctx.get("config")
    use_gpu = _USE_GPU_COLLISION and (
        config is not None and bool(getattr(config, "use_gpu_physics", False))
    ) and (check_collisions_batch is not None)

    if use_gpu and state.player_bullets and state.enemies:
        bullets_data = [
            {"x": b["rect"].x, "y": b["rect"].y, "w": b["rect"].w, "h": b["rect"].h}
            for b in state.player_bullets
        ]
        targets_data = [
            {"x": e["rect"].x, "y": e["rect"].y, "w": e["rect"].w, "h": e["rect"].h}
            for e in state.enemies
        ]
        pairs = check_collisions_batch(bullets_data, targets_data)
        by_bullet = {}
        for bi, ei in pairs:
            if bi not in by_bullet and bi < len(state.player_bullets) and ei < len(state.enemies):
                by_bullet[bi] = (state.player_bullets[bi], state.enemies[ei])
        for bullet, enemy in by_bullet.values():
            if bullet in state.player_bullets and enemy in state.enemies:
                _process_bullet_enemy_hit(state, ctx, bullet, enemy)
        return

    # Use spatial grid for O(n) collision detection instead of O(n*m)
    if not state.player_bullets or not state.enemies:
        return
    
    enemy_grid = _build_enemy_grid(state, ctx)
    bullets_to_remove = set()
    
    for bullet in state.player_bullets:
        if id(bullet) in bullets_to_remove:
            continue
        
        # Query only nearby enemies using spatial grid
        for enemy in enemy_grid.query_rect(bullet["rect"]):
            if enemy.get("hp", 1) <= 0:
                continue
            if not bullet["rect"].colliderect(enemy["rect"]):
                continue
            _process_bullet_enemy_hit(state, ctx, bullet, enemy)
            if bullet.get("penetration", 0) <= 0:
                bullets_to_remove.add(id(bullet))
            break
    
    # Bulk remove processed bullets
    if bullets_to_remove:
        state.player_bullets[:] = [b for b in state.player_bullets if id(b) not in bullets_to_remove]


def handle_player_bullet_block_collisions(state, dt: float, ctx: dict) -> None:
    """Handle bullet-block collisions using spatial grid for better performance."""
    check_hazard = ctx.get("check_point_in_hazard")
    lev = getattr(state, "level", None)
    if lev is None:
        return
    d_blocks = lev.destructible_blocks
    m_blocks = lev.moveable_blocks
    g_blocks = lev.giant_blocks + lev.super_giant_blocks
    trapezo = lev.trapezoid_blocks
    tri = lev.triangle_blocks
    hazards = lev.hazard_obstacles
    player_damage = state.player_bullet_damage

    # Build spatial grid for blocks
    block_grid = _build_block_grid(state, ctx)
    
    # Track items to remove (avoid O(n) removal during iteration)
    bullets_to_remove = set()
    d_blocks_to_remove = set()
    m_blocks_to_remove = set()

    for bullet in state.player_bullets:
        if id(bullet) in bullets_to_remove:
            continue
        
        bullet_removed = False
        
        # Query nearby blocks from spatial grid
        for block in block_grid.query_rect(bullet["rect"]):
            if bullet_removed:
                break
                
            block_rect = block.get("bounding_rect") or block.get("rect")
            if not block_rect or not bullet["rect"].colliderect(block_rect):
                continue
            
            # Destructible blocks
            if block.get("is_destructible"):
                dmg = bullet.get("damage", player_damage)
                block["hp"] -= dmg
                if block["hp"] <= 0:
                    if block in d_blocks:
                        d_blocks_to_remove.add(id(block))
                    elif block in m_blocks:
                        m_blocks_to_remove.add(id(block))
                if bullet.get("penetration", 0) <= 0:
                    if not bullet.get("bouncing", False):
                        bullets_to_remove.add(id(bullet))
                        bullet_removed = True
                    else:
                        bullet["vel"] = bullet["vel"].reflect(pygame.Vector2(1, 0))
                break
            
            # Giant/super giant blocks (indestructible)
            if block in g_blocks:
                if not bullet.get("bouncing", False):
                    bullets_to_remove.add(id(bullet))
                    bullet_removed = True
                else:
                    bullet["vel"] = bullet["vel"].reflect(pygame.Vector2(1, 0))
                break
            
            # Trapezoid blocks
            if block in trapezo:
                if not bullet.get("bouncing", False):
                    bullets_to_remove.add(id(bullet))
                    bullet_removed = True
                else:
                    bullet["vel"] = bullet["vel"].reflect(pygame.Vector2(1, 0))
                break
            
            # Triangle blocks
            if block in tri:
                if not bullet.get("bouncing", False):
                    bullets_to_remove.add(id(bullet))
                    bullet_removed = True
                else:
                    bullet["vel"] = bullet["vel"].reflect(pygame.Vector2(1, 0))
                break
        # Handle hazard collisions (not in spatial grid due to polygon shapes)
        if bullet_removed or not check_hazard:
            continue
        for hazard in hazards:
            if not hazard.get("points") or len(hazard["points"]) < 3:
                continue
            bc = pygame.Vector2(bullet["rect"].center)
            if check_hazard(bc, hazard["points"], hazard["bounding_rect"]):
                vel = bullet.get("vel", pygame.Vector2(0, 0))
                if vel.length_squared() > 0:
                    v = hazard.get("velocity", pygame.Vector2(0, 0))
                    hazard["velocity"] = v + vel.normalize() * 200.0 * dt
                bullets_to_remove.add(id(bullet))
                break
    
    # Bulk remove - O(n) instead of O(n²) with .remove() in loop
    if bullets_to_remove:
        state.player_bullets[:] = [b for b in state.player_bullets if id(b) not in bullets_to_remove]
    if d_blocks_to_remove:
        lev.destructible_blocks[:] = [b for b in d_blocks if id(b) not in d_blocks_to_remove]
        invalidate_block_grid()
    if m_blocks_to_remove:
        lev.moveable_blocks[:] = [b for b in m_blocks if id(b) not in m_blocks_to_remove]
        invalidate_block_grid()
