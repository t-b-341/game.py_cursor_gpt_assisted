"""Collisions for projectiles, beams, hazards, explosives: vs enemies, blocks, player, friendlies."""
from __future__ import annotations

import math
import pygame

from .collision_common import apply_player_damage, set_enemy_damage_flash

try:
    from gpu_physics import check_collisions_batch, CUDA_AVAILABLE
    _USE_GPU_COLLISION = CUDA_AVAILABLE  # Single capability flag: True only when GPU path is usable
except Exception:
    _USE_GPU_COLLISION = False
    check_collisions_batch = None


def handle_hazard_enemy_collisions(state, dt: float, ctx: dict) -> None:
    lev = getattr(state, "level", None)
    hazards = lev.hazard_obstacles if lev else []
    for hazard in hazards:
        if not hazard.get("points") or len(hazard["points"]) < 3:
            continue
        hazard_damage = hazard.get("damage", 10)
        check = ctx.get("check_point_in_hazard")
        kill = ctx.get("kill_enemy")
        if not check or not kill:
            continue
        for enemy in state.enemies[:]:
            center = pygame.Vector2(enemy["rect"].center)
            if check(center, hazard["points"], hazard["bounding_rect"]):
                enemy["hp"] -= hazard_damage * dt
                set_enemy_damage_flash(enemy, ctx)
                if enemy["hp"] <= 0:
                    kill(enemy, state)


def handle_laser_beam_collisions(state, dt: float, ctx: dict) -> None:
    line_rect = ctx.get("line_rect_intersection")
    kill = ctx.get("kill_enemy")
    if not line_rect or not kill:
        return
    for beam in state.laser_beams[:]:
        beam["timer"] = beam.get("timer", 0.1) - dt
        if beam["timer"] <= 0:
            state.laser_beams.remove(beam)
            continue
        damage = beam.get("damage", 50) * dt * 60
        for enemy in state.enemies[:]:
            if line_rect(beam["start"], beam["end"], enemy["rect"]):
                enemy["hp"] -= damage
                set_enemy_damage_flash(enemy, ctx)
                if enemy["hp"] <= 0:
                    kill(enemy, state)


def handle_dead_enemies(state, ctx: dict) -> None:
    kill = ctx.get("kill_enemy")
    if not kill:
        return
    for enemy in state.enemies[:]:
        if enemy.get("hp", 1) <= 0:
            kill(enemy, state)


def handle_player_bullet_offscreen(state, ctx: dict) -> None:
    offscreen = ctx.get("rect_offscreen")
    if not offscreen:
        return
    for bullet in state.player_bullets[:]:
        if offscreen(bullet["rect"]) and bullet in state.player_bullets:
            state.player_bullets.remove(bullet)


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
        set_enemy_damage_flash(enemy, ctx)
        state.damage_numbers.append({
            "x": enemy["rect"].centerx,
            "y": enemy["rect"].y - 20,
            "damage": int(dmg),
            "timer": 2.0,
            "color": (255, 255, 100),
        })
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
    set_enemy_damage_flash(enemy, ctx)
    state.damage_numbers.append({
        "x": enemy["rect"].centerx,
        "y": enemy["rect"].y - 20,
        "damage": int(dmg),
        "timer": 2.0,
        "color": (255, 255, 100),
    })
    if enemy["hp"] <= 0:
        kill(enemy, state)
    if bullet.get("penetration", 0) <= 0:
        if bullet in state.player_bullets:
            state.player_bullets.remove(bullet)
        return
    bullet["penetration"] = bullet.get("penetration", 0) - 1


def handle_player_bullet_enemy_collisions(state, ctx: dict) -> None:
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

    for bullet in state.player_bullets[:]:
        for enemy in state.enemies[:]:
            if not bullet["rect"].colliderect(enemy["rect"]):
                continue
            _process_bullet_enemy_hit(state, ctx, bullet, enemy)
            break


def handle_player_bullet_block_collisions(state, dt: float, ctx: dict) -> None:
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

    for bullet in state.player_bullets[:]:
        if bullet.get("removed"):
            continue
        for block in d_blocks + m_blocks:
            if not block.get("is_destructible") or not bullet["rect"].colliderect(block["rect"]):
                continue
            dmg = bullet.get("damage", player_damage)
            block["hp"] -= dmg
            if block["hp"] <= 0:
                if block in d_blocks:
                    d_blocks.remove(block)
                else:
                    m_blocks.remove(block)
            if bullet.get("penetration", 0) <= 0:
                if not bullet.get("bouncing", False):
                    if bullet in state.player_bullets:
                        state.player_bullets.remove(bullet)
                    bullet["removed"] = True
                    break
                bullet["vel"] = bullet["vel"].reflect(pygame.Vector2(1, 0))
            break
        if bullet.get("removed"):
            continue
        for block in g_blocks:
            if bullet["rect"].colliderect(block["rect"]):
                if not bullet.get("bouncing", False):
                    if bullet in state.player_bullets:
                        state.player_bullets.remove(bullet)
                    bullet["removed"] = True
                    break
                bullet["vel"] = bullet["vel"].reflect(pygame.Vector2(1, 0))
                break
        if bullet.get("removed"):
            continue
        for tb in trapezo:
            br = tb.get("bounding_rect", tb.get("rect"))
            if bullet["rect"].colliderect(br):
                if not bullet.get("bouncing", False):
                    if bullet in state.player_bullets:
                        state.player_bullets.remove(bullet)
                    bullet["removed"] = True
                    break
                bullet["vel"] = bullet["vel"].reflect(pygame.Vector2(1, 0))
                break
        if bullet.get("removed"):
            continue
        for tr in tri:
            br = tr.get("bounding_rect", tr.get("rect"))
            if bullet["rect"].colliderect(br):
                if not bullet.get("bouncing", False):
                    if bullet in state.player_bullets:
                        state.player_bullets.remove(bullet)
                    bullet["removed"] = True
                    break
                bullet["vel"] = bullet["vel"].reflect(pygame.Vector2(1, 0))
                break
        if bullet.get("removed"):
            continue
        if not check_hazard:
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
                if bullet in state.player_bullets:
                    state.player_bullets.remove(bullet)
                bullet["removed"] = True
                break


def handle_enemy_projectile_lifetime_offscreen(state, ctx: dict) -> None:
    offscreen = ctx.get("rect_offscreen")
    for proj in state.enemy_projectiles[:]:
        if "lifetime" in proj and proj["lifetime"] <= 0:
            if proj in state.enemy_projectiles:
                state.enemy_projectiles.remove(proj)
            continue
        if offscreen and offscreen(proj["rect"]) and proj in state.enemy_projectiles:
            state.enemy_projectiles.remove(proj)


def handle_enemy_projectile_block_collisions(state, ctx: dict) -> None:
    lev = getattr(state, "level", None)
    if lev is None:
        return
    d_blocks = lev.destructible_blocks
    m_blocks = lev.moveable_blocks
    for proj in state.enemy_projectiles[:]:
        for block in d_blocks + m_blocks:
            if block.get("is_destructible") and proj["rect"].colliderect(block["rect"]):
                block["hp"] -= proj.get("damage", 10)
                if block["hp"] <= 0:
                    if block in d_blocks:
                        d_blocks.remove(block)
                    else:
                        m_blocks.remove(block)
                if proj in state.enemy_projectiles:
                    state.enemy_projectiles.remove(proj)
                break


def handle_enemy_projectile_friendly_collisions(state, ctx: dict) -> None:
    """Apply enemy projectile damage to friendlies; remove hit projectiles and dead friendlies."""
    for proj in state.enemy_projectiles[:]:
        for friendly in state.friendly_ai[:]:
            if friendly.get("hp", 1) <= 0:
                continue
            if not proj["rect"].colliderect(friendly["rect"]):
                continue
            damage = proj.get("damage", 10)
            friendly["hp"] = friendly.get("hp", friendly.get("max_hp", 100)) - damage
            if proj in state.enemy_projectiles:
                state.enemy_projectiles.remove(proj)
            if friendly["hp"] <= 0 and friendly in state.friendly_ai:
                state.friendly_ai.remove(friendly)
            break


def handle_friendly_projectile_offscreen_blocks_enemies(state, ctx: dict) -> None:
    offscreen = ctx.get("rect_offscreen")
    kill = ctx.get("kill_enemy")
    lev = getattr(state, "level", None)
    if lev is None:
        d_blocks, m_blocks = [], []
    else:
        d_blocks = lev.destructible_blocks
        m_blocks = lev.moveable_blocks
    for proj in state.friendly_projectiles[:]:
        if offscreen and offscreen(proj["rect"]):
            state.friendly_projectiles.remove(proj)
            continue
        for block in d_blocks + m_blocks:
            if block.get("is_destructible") and proj["rect"].colliderect(block["rect"]):
                block["hp"] -= proj.get("damage", 20)
                if block["hp"] <= 0:
                    if block in d_blocks:
                        d_blocks.remove(block)
                    else:
                        m_blocks.remove(block)
                state.friendly_projectiles.remove(proj)
                break
        else:
            for enemy in state.enemies[:]:
                if proj["rect"].colliderect(enemy["rect"]):
                    dmg = proj.get("damage", 20)
                    enemy["hp"] -= dmg
                    set_enemy_damage_flash(enemy, ctx)
                    state.damage_numbers.append({
                        "x": enemy["rect"].centerx,
                        "y": enemy["rect"].y - 20,
                        "damage": int(dmg),
                        "timer": 2.0,
                        "color": (255, 255, 100),
                    })
                    if enemy["hp"] <= 0 and kill:
                        kill(enemy, state)
                    state.friendly_projectiles.remove(proj)
                    break


def handle_grenade_explosion_damage(state, dt: float, ctx: dict) -> None:
    kill = ctx.get("kill_enemy")
    lev = getattr(state, "level", None)
    d_blocks = lev.destructible_blocks if lev else []
    m_blocks = lev.moveable_blocks if lev else []
    player = state.player_rect

    for explosion in state.grenade_explosions[:]:
        explosion["timer"] = explosion.get("timer", 0.3) - dt
        explosion["radius"] = int(explosion.get("max_radius", 150) * (1.0 - explosion["timer"] / 0.3))
        if explosion["timer"] <= 0:
            state.grenade_explosions.remove(explosion)
            continue
        pos = pygame.Vector2(explosion["x"], explosion["y"])
        r = explosion["radius"]
        damage_val = explosion.get("damage", 500)
        source = explosion.get("source", "")
        if source != "enemy_player_allies_only":
            for enemy in state.enemies[:]:
                d = (pygame.Vector2(enemy["rect"].center) - pos).length()
                if d <= r:
                    enemy["hp"] -= damage_val
                    set_enemy_damage_flash(enemy, ctx)
                    state.damage_numbers.append({
                        "x": enemy["rect"].centerx,
                        "y": enemy["rect"].y - 20,
                        "damage": int(damage_val),
                        "timer": 2.0,
                        "color": (255, 200, 100),
                    })
                    if enemy["hp"] <= 0 and kill:
                        kill(enemy, state)
        if source == "enemy_player_allies_only":
            for friendly in state.friendly_ai[:]:
                d = (pygame.Vector2(friendly["rect"].center) - pos).length()
                if d <= r:
                    friendly["hp"] = friendly.get("hp", friendly.get("max_hp", 100)) - damage_val
                    if friendly["hp"] <= 0 and friendly in state.friendly_ai:
                        state.friendly_ai.remove(friendly)
        if player:
            pd = (pygame.Vector2(player.center) - pos).length()
            if pd <= r and source not in ("player", "wall_impact"):
                if not state.shield_active:
                    apply_player_damage(state, damage_val, ctx)
        if source != "enemy_player_allies_only":
            for block in list(d_blocks) + list(m_blocks):
                if not block.get("is_destructible"):
                    continue
                bp = pygame.Vector2(block["rect"].center)
                if (bp - pos).length() <= r:
                    block["hp"] -= damage_val
                    if block["hp"] <= 0:
                        if block in d_blocks:
                            d_blocks.remove(block)
                        else:
                            m_blocks.remove(block)


def handle_missile_collisions(state, ctx: dict) -> None:
    player = state.player_rect
    offscreen = ctx.get("rect_offscreen")
    kill = ctx.get("kill_enemy")
    md = ctx.get("missile_damage", 800)

    for missile in state.missiles[:]:
        if offscreen and offscreen(missile["rect"]):
            if missile in state.missiles:
                state.missiles.remove(missile)
            continue
        hit = False
        hit_ally = None  # Track which ally was hit (if any)
        
        if missile.get("target_player"):
            # Check if missile hits the dropped ally (they draw missile aggro)
            dropped_ally = getattr(state, "dropped_ally", None)
            if dropped_ally and dropped_ally in state.friendly_ai and dropped_ally.get("hp", 0) > 0:
                ally_rect = dropped_ally.get("rect")
                if ally_rect and missile["rect"].colliderect(ally_rect):
                    hit = True
                    hit_ally = dropped_ally
            
            # Also check player collision (missile may still hit player if no ally intercepts)
            if not hit and player and missile["rect"].colliderect(player):
                hit = True
                if not state.shield_active:
                    apply_player_damage(state, missile.get("damage", md), ctx)
        elif missile.get("target_enemy") and missile["target_enemy"] in state.enemies:
            if missile["rect"].colliderect(missile["target_enemy"]["rect"]):
                hit = True
        if hit:
            pos = pygame.Vector2(missile["rect"].center)
            rad = missile.get("explosion_radius", 150)
            dmg = missile.get("damage", md)
            
            # Damage enemies in explosion radius
            for enemy in state.enemies[:]:
                if (pygame.Vector2(enemy["rect"].center) - pos).length() <= rad:
                    enemy["hp"] -= dmg
                    set_enemy_damage_flash(enemy, ctx)
                    state.damage_numbers.append({
                        "x": enemy["rect"].centerx,
                        "y": enemy["rect"].y - 20,
                        "damage": int(dmg),
                        "timer": 2.0,
                        "color": (255, 150, 50),
                    })
                    if enemy["hp"] <= 0 and kill:
                        kill(enemy, state)
            
            # Damage the ally that was directly hit
            if hit_ally:
                hit_ally["hp"] = hit_ally.get("hp", 0) - dmg
                ally_rect = hit_ally.get("rect")
                if ally_rect:
                    state.damage_numbers.append({
                        "x": ally_rect.centerx,
                        "y": ally_rect.y - 20,
                        "damage": int(dmg),
                        "timer": 2.0,
                        "color": (100, 200, 255),  # Blue for ally damage
                    })
                # Remove ally if dead
                if hit_ally["hp"] <= 0:
                    if hit_ally in state.friendly_ai:
                        state.friendly_ai.remove(hit_ally)
                    if getattr(state, "dropped_ally", None) == hit_ally:
                        state.dropped_ally = None
            
            # Damage player if in explosion radius (and no shield)
            if missile.get("target_player") and player:
                if (pygame.Vector2(player.center) - pos).length() <= rad and not state.shield_active:
                    apply_player_damage(state, dmg, ctx)
            
            if missile in state.missiles:
                state.missiles.remove(missile)