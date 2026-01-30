"""Collisions for projectiles, beams, hazards, explosives: vs enemies, blocks, player, friendlies.

Performance optimizations:
- Spatial grid partitioning reduces O(n*m) collision checks to O(n) average
- Filter-based list updates avoid O(n) removal during iteration
- Bulk processing where possible
- C-accelerated distance calculations where available
"""
from __future__ import annotations

import math
import pygame

from .collision_common import apply_player_damage, set_enemy_damage_flash
from .spatial_grid import get_projectile_grid, get_enemy_grid, get_block_grid, SpatialGrid
from physics_loader import distance_squared as c_distance_squared

try:
    from gpu_physics import check_collisions_batch, CUDA_AVAILABLE
    _USE_GPU_COLLISION = CUDA_AVAILABLE  # Single capability flag: True only when GPU path is usable
except Exception:
    _USE_GPU_COLLISION = False
    check_collisions_batch = None


def _build_enemy_grid(state, ctx: dict) -> SpatialGrid:
    """Build spatial grid containing all enemies. Uses frame caching to avoid rebuilding."""
    width = ctx.get("width", 1920)
    height = ctx.get("height", 1080)
    frame_id = ctx.get("frame_id", -1)
    grid = get_enemy_grid(width, height, frame_id=frame_id)
    # Only insert if grid was just cleared (not cached)
    if len(grid._obj_cells) == 0 and state.enemies:
        grid.insert_all(state.enemies)
    return grid


def _build_block_grid(state, ctx: dict) -> SpatialGrid:
    """Build spatial grid containing all collidable blocks. Uses frame caching.
    
    DEPRECATED: Use build_block_grid_cached() and ctx["_block_grid"] instead.
    """
    # Check if pre-built grid is available in context
    cached = ctx.get("_block_grid")
    if cached is not None:
        return cached
    
    return build_block_grid_cached(state, ctx)


def build_block_grid_cached(state, ctx: dict) -> SpatialGrid:
    """Build spatial grid containing all collidable blocks.
    
    Called once per collision update frame. Results stored in ctx["_block_grid"].
    """
    width = ctx.get("width", 1920)
    height = ctx.get("height", 1080)
    frame_id = ctx.get("frame_id", -1)
    
    lev = getattr(state, "level", None)
    if lev is None:
        return get_block_grid(width, height, frame_id=frame_id)
    
    grid = get_block_grid(width, height, frame_id=frame_id)
    
    # Only insert if grid was just cleared (not cached this frame)
    if len(grid._obj_cells) > 0:
        return grid
    
    # Insert all block types
    for block in lev.destructible_blocks:
        if block.get("rect"):
            grid.insert(block, block["rect"])
    for block in lev.moveable_blocks:
        if block.get("rect"):
            grid.insert(block, block["rect"])
    for block in lev.giant_blocks + lev.super_giant_blocks:
        if block.get("rect"):
            grid.insert(block, block["rect"])
    for tb in lev.trapezoid_blocks:
        br = tb.get("bounding_rect", tb.get("rect"))
        if br:
            grid.insert(tb, br)
    for tr in lev.triangle_blocks:
        br = tr.get("bounding_rect", tr.get("rect"))
        if br:
            grid.insert(tr, br)
    
    return grid


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
    if m_blocks_to_remove:
        lev.moveable_blocks[:] = [b for b in m_blocks if id(b) not in m_blocks_to_remove]


def handle_enemy_projectile_lifetime_offscreen(state, ctx: dict) -> None:
    """Remove expired and offscreen enemy projectiles using efficient filtering."""
    offscreen = ctx.get("rect_offscreen")
    
    def should_keep(proj):
        # Remove if lifetime expired
        if "lifetime" in proj and proj["lifetime"] <= 0:
            return False
        # Remove if offscreen
        if offscreen and offscreen(proj["rect"]):
            return False
        return True
    
    # Use list comprehension for O(n) removal instead of O(n²)
    state.enemy_projectiles[:] = [p for p in state.enemy_projectiles if should_keep(p)]


def handle_enemy_projectile_block_collisions(state, ctx: dict) -> None:
    """Handle enemy projectile-block collisions with spatial grid."""
    lev = getattr(state, "level", None)
    if lev is None:
        return
    d_blocks = lev.destructible_blocks
    m_blocks = lev.moveable_blocks
    
    if not state.enemy_projectiles:
        return
    
    block_grid = _build_block_grid(state, ctx)
    projs_to_remove = set()
    d_blocks_to_remove = set()
    m_blocks_to_remove = set()
    
    for proj in state.enemy_projectiles:
        if id(proj) in projs_to_remove:
            continue
        
        for block in block_grid.query_rect(proj["rect"]):
            if not block.get("is_destructible"):
                continue
            block_rect = block.get("rect")
            if not block_rect or not proj["rect"].colliderect(block_rect):
                continue
            
            block["hp"] -= proj.get("damage", 10)
            if block["hp"] <= 0:
                if block in d_blocks:
                    d_blocks_to_remove.add(id(block))
                elif block in m_blocks:
                    m_blocks_to_remove.add(id(block))
            projs_to_remove.add(id(proj))
            break
    
    # Bulk removal
    if projs_to_remove:
        state.enemy_projectiles[:] = [p for p in state.enemy_projectiles if id(p) not in projs_to_remove]
    if d_blocks_to_remove:
        lev.destructible_blocks[:] = [b for b in d_blocks if id(b) not in d_blocks_to_remove]
    if m_blocks_to_remove:
        lev.moveable_blocks[:] = [b for b in m_blocks if id(b) not in m_blocks_to_remove]


def handle_enemy_projectile_friendly_collisions(state, ctx: dict) -> None:
    """Apply enemy projectile damage to friendlies; uses filter-based removal."""
    if not state.enemy_projectiles or not state.friendly_ai:
        return
    
    projs_to_remove = set()
    friendlies_to_remove = set()
    
    for proj in state.enemy_projectiles:
        if id(proj) in projs_to_remove:
            continue
        
        for friendly in state.friendly_ai:
            if friendly.get("hp", 1) <= 0:
                continue
            if not proj["rect"].colliderect(friendly["rect"]):
                continue
            
            damage = proj.get("damage", 10)
            friendly["hp"] = friendly.get("hp", friendly.get("max_hp", 100)) - damage
            projs_to_remove.add(id(proj))
            
            if friendly["hp"] <= 0:
                friendlies_to_remove.add(id(friendly))
            break
    
    # Bulk removal
    if projs_to_remove:
        state.enemy_projectiles[:] = [p for p in state.enemy_projectiles if id(p) not in projs_to_remove]
    if friendlies_to_remove:
        state.friendly_ai[:] = [f for f in state.friendly_ai if id(f) not in friendlies_to_remove]


def handle_friendly_projectile_offscreen_blocks_enemies(state, ctx: dict) -> None:
    """Handle friendly projectile collisions with spatial grid and filter-based removal."""
    offscreen = ctx.get("rect_offscreen")
    kill = ctx.get("kill_enemy")
    lev = getattr(state, "level", None)
    
    if not state.friendly_projectiles:
        return
    
    if lev is None:
        d_blocks, m_blocks = [], []
    else:
        d_blocks = lev.destructible_blocks
        m_blocks = lev.moveable_blocks
    
    # Build spatial grids
    block_grid = _build_block_grid(state, ctx)
    enemy_grid = _build_enemy_grid(state, ctx)
    
    projs_to_remove = set()
    d_blocks_to_remove = set()
    m_blocks_to_remove = set()
    
    for proj in state.friendly_projectiles:
        if id(proj) in projs_to_remove:
            continue
        
        # Check offscreen
        if offscreen and offscreen(proj["rect"]):
            projs_to_remove.add(id(proj))
            continue
        
        hit_block = False
        # Check block collisions using spatial grid
        for block in block_grid.query_rect(proj["rect"]):
            if not block.get("is_destructible"):
                continue
            block_rect = block.get("rect")
            if not block_rect or not proj["rect"].colliderect(block_rect):
                continue
            
            block["hp"] -= proj.get("damage", 20)
            if block["hp"] <= 0:
                if block in d_blocks:
                    d_blocks_to_remove.add(id(block))
                elif block in m_blocks:
                    m_blocks_to_remove.add(id(block))
            projs_to_remove.add(id(proj))
            hit_block = True
            break
        
        if hit_block:
            continue
        
        # Check enemy collisions using spatial grid
        for enemy in enemy_grid.query_rect(proj["rect"]):
            if enemy.get("hp", 1) <= 0:
                continue
            if not proj["rect"].colliderect(enemy["rect"]):
                continue
            
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
            projs_to_remove.add(id(proj))
            break
    
    # Bulk removal
    if projs_to_remove:
        state.friendly_projectiles[:] = [p for p in state.friendly_projectiles if id(p) not in projs_to_remove]
    if d_blocks_to_remove and lev:
        lev.destructible_blocks[:] = [b for b in d_blocks if id(b) not in d_blocks_to_remove]
    if m_blocks_to_remove and lev:
        lev.moveable_blocks[:] = [b for b in m_blocks if id(b) not in m_blocks_to_remove]


def handle_grenade_explosion_damage(state, dt: float, ctx: dict) -> None:
    """Handle grenade explosion damage with filter-based removal."""
    kill = ctx.get("kill_enemy")
    lev = getattr(state, "level", None)
    d_blocks = lev.destructible_blocks if lev else []
    m_blocks = lev.moveable_blocks if lev else []
    player = state.player_rect

    explosions_to_remove = set()
    friendlies_to_remove = set()
    d_blocks_to_remove = set()
    m_blocks_to_remove = set()

    for explosion in state.grenade_explosions:
        explosion["timer"] = explosion.get("timer", 0.3) - dt
        explosion["radius"] = int(explosion.get("max_radius", 150) * (1.0 - explosion["timer"] / 0.3))
        if explosion["timer"] <= 0:
            explosions_to_remove.add(id(explosion))
            continue
        px, py = explosion["x"], explosion["y"]
        r = explosion["radius"]
        r_sq = r * r  # Use squared radius to avoid sqrt
        damage_val = explosion.get("damage", 500)
        source = explosion.get("source", "")
        if source != "enemy_player_allies_only":
            for enemy in state.enemies:
                # Use C-accelerated distance_squared (avoids sqrt)
                d_sq = c_distance_squared(enemy["rect"].centerx, enemy["rect"].centery, px, py)
                if d_sq <= r_sq:
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
            for friendly in state.friendly_ai:
                d_sq = c_distance_squared(friendly["rect"].centerx, friendly["rect"].centery, px, py)
                if d_sq <= r_sq:
                    friendly["hp"] = friendly.get("hp", friendly.get("max_hp", 100)) - damage_val
                    if friendly["hp"] <= 0:
                        friendlies_to_remove.add(id(friendly))
        if player:
            pd_sq = c_distance_squared(player.centerx, player.centery, px, py)
            if pd_sq <= r_sq and source not in ("player", "wall_impact", "ally_explosion"):
                if not state.shield_active:
                    apply_player_damage(state, damage_val, ctx)
        if source != "enemy_player_allies_only":
            for block in list(d_blocks) + list(m_blocks):
                if not block.get("is_destructible"):
                    continue
                d_sq = c_distance_squared(block["rect"].centerx, block["rect"].centery, px, py)
                if d_sq <= r_sq:
                    block["hp"] -= damage_val
                    if block["hp"] <= 0:
                        if block in d_blocks:
                            d_blocks_to_remove.add(id(block))
                        elif block in m_blocks:
                            m_blocks_to_remove.add(id(block))
    
    # Bulk removal
    if explosions_to_remove:
        state.grenade_explosions[:] = [e for e in state.grenade_explosions if id(e) not in explosions_to_remove]
    if friendlies_to_remove:
        state.friendly_ai[:] = [f for f in state.friendly_ai if id(f) not in friendlies_to_remove]
    if d_blocks_to_remove and lev:
        lev.destructible_blocks[:] = [b for b in d_blocks if id(b) not in d_blocks_to_remove]
    if m_blocks_to_remove and lev:
        lev.moveable_blocks[:] = [b for b in m_blocks if id(b) not in m_blocks_to_remove]


def handle_missile_collisions(state, ctx: dict) -> None:
    """Handle missile collisions with filter-based removal."""
    player = state.player_rect
    offscreen = ctx.get("rect_offscreen")
    kill = ctx.get("kill_enemy")
    md = ctx.get("missile_damage", 800)

    missiles_to_remove = set()
    friendlies_to_remove = set()

    for missile in state.missiles:
        if id(missile) in missiles_to_remove:
            continue
        
        if offscreen and offscreen(missile["rect"]):
            missiles_to_remove.add(id(missile))
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
            # Player can dodge missiles while dashing (is_jumping = True)
            is_dashing = getattr(state, "is_jumping", False)
            if not hit and player and missile["rect"].colliderect(player) and not is_dashing:
                hit = True
                if not state.shield_active:
                    apply_player_damage(state, missile.get("damage", md), ctx)
        elif missile.get("target_enemy") and missile["target_enemy"] in state.enemies:
            if missile["rect"].colliderect(missile["target_enemy"]["rect"]):
                hit = True
        
        if hit:
            mx, my = missile["rect"].centerx, missile["rect"].centery
            rad = missile.get("explosion_radius", 150)
            rad_sq = rad * rad  # Use squared radius to avoid sqrt
            dmg = missile.get("damage", md)
            
            # Damage enemies in explosion radius using C-accelerated distance_squared
            for enemy in state.enemies:
                if c_distance_squared(enemy["rect"].centerx, enemy["rect"].centery, mx, my) <= rad_sq:
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
                # Mark ally for removal if dead
                if hit_ally["hp"] <= 0:
                    friendlies_to_remove.add(id(hit_ally))
                    if getattr(state, "dropped_ally", None) == hit_ally:
                        state.dropped_ally = None
            
            # Damage player if in explosion radius (and no shield)
            if missile.get("target_player") and player:
                if c_distance_squared(player.centerx, player.centery, mx, my) <= rad_sq and not state.shield_active:
                    apply_player_damage(state, dmg, ctx)
            
            missiles_to_remove.add(id(missile))
    
    # Bulk removal
    if missiles_to_remove:
        state.missiles[:] = [m for m in state.missiles if id(m) not in missiles_to_remove]
    if friendlies_to_remove:
        state.friendly_ai[:] = [f for f in state.friendly_ai if id(f) not in friendlies_to_remove]