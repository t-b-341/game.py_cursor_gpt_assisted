"""Explosion and missile collision handling.

Handles:
- Grenade explosions (damage to enemies, player, friendlies, blocks)
- Missile collisions and explosions
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..collision_common import apply_player_damage, set_enemy_damage_flash
from ..spatial_grid import get_enemy_grid, SpatialGrid, invalidate_block_grid
from physics_loader import distance_squared as c_distance_squared

if TYPE_CHECKING:
    from state import GameState


def _create_damage_number(x, y, damage, color=(255, 255, 100), timer=2.0):
    """Create a damage number dict for display."""
    return {"x": x, "y": y, "damage": int(damage), "timer": timer, "color": color}


def _build_enemy_grid(state: "GameState", ctx: dict) -> SpatialGrid:
    """Build spatial grid containing all enemies."""
    width: int = ctx.get("width", 1920)
    height: int = ctx.get("height", 1080)
    frame_id: int = ctx.get("frame_id", -1)
    grid = get_enemy_grid(width, height, frame_id=frame_id)
    if len(grid._obj_cells) == 0 and state.enemies:
        grid.insert_all(state.enemies)
    return grid


def handle_grenade_explosion_damage(state: "GameState", dt: float, ctx: dict) -> None:
    """Handle grenade explosion damage with filter-based removal.
    
    Performance: Uses spatial grid queries to reduce O(explosions * enemies) to O(explosions * nearby_enemies).
    """
    kill = ctx.get("kill_enemy")
    lev = getattr(state, "level", None)
    d_blocks = lev.destructible_blocks if lev else []
    m_blocks = lev.moveable_blocks if lev else []
    player = state.player_rect

    explosions_to_remove = set()
    friendlies_to_remove = set()
    d_blocks_to_remove = set()
    m_blocks_to_remove = set()
    
    # Build enemy grid once for all explosions (uses frame caching)
    enemy_grid = _build_enemy_grid(state, ctx) if state.enemies else None

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
        
        # Use spatial grid to query only enemies near explosion radius
        if source != "enemy_player_allies_only" and enemy_grid:
            for enemy in enemy_grid.query_radius(px, py, r):
                # Use C-accelerated distance_squared (avoids sqrt)
                d_sq = c_distance_squared(enemy["rect"].centerx, enemy["rect"].centery, px, py)
                if d_sq <= r_sq:
                    enemy["hp"] -= damage_val
                    set_enemy_damage_flash(enemy, ctx)
                    state.damage_numbers.append(_create_damage_number(
                        enemy["rect"].centerx, enemy["rect"].y - 20, damage_val, (255, 200, 100)
                    ))
                    if enemy["hp"] <= 0 and kill:
                        enemy["killed_by"] = "grenade"  # Tag for DDA tracking
                        kill(enemy, state)
        
        # Damage friendlies if explosion targets player/allies
        if source == "enemy_player_allies_only":
            for friendly in state.friendly_ai:
                d_sq = c_distance_squared(friendly["rect"].centerx, friendly["rect"].centery, px, py)
                if d_sq <= r_sq:
                    friendly["hp"] = friendly.get("hp", friendly.get("max_hp", 100)) - damage_val
                    if friendly["hp"] <= 0:
                        friendlies_to_remove.add(id(friendly))
        
        # Damage player
        if player:
            pd_sq = c_distance_squared(player.centerx, player.centery, px, py)
            if pd_sq <= r_sq and source not in ("player", "wall_impact", "ally_explosion"):
                if not state.shield_active:
                    apply_player_damage(state, damage_val, ctx)
        
        # Damage destructible blocks using spatial grid
        if source != "enemy_player_allies_only":
            block_grid = ctx.get("_block_grid")
            if block_grid:
                # Query blocks near explosion using spatial grid
                for block in block_grid.query_radius(px, py, r):
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
            else:
                # Fallback: iterate all blocks (slower)
                for block in d_blocks:
                    if not block.get("is_destructible"):
                        continue
                    d_sq = c_distance_squared(block["rect"].centerx, block["rect"].centery, px, py)
                    if d_sq <= r_sq:
                        block["hp"] -= damage_val
                        if block["hp"] <= 0:
                            d_blocks_to_remove.add(id(block))
                for block in m_blocks:
                    if not block.get("is_destructible"):
                        continue
                    d_sq = c_distance_squared(block["rect"].centerx, block["rect"].centery, px, py)
                    if d_sq <= r_sq:
                        block["hp"] -= damage_val
                        if block["hp"] <= 0:
                            m_blocks_to_remove.add(id(block))
    
    # Bulk removal
    if explosions_to_remove:
        state.grenade_explosions[:] = [e for e in state.grenade_explosions if id(e) not in explosions_to_remove]
    if friendlies_to_remove:
        state.friendly_ai[:] = [f for f in state.friendly_ai if id(f) not in friendlies_to_remove]
    if d_blocks_to_remove and lev:
        lev.destructible_blocks[:] = [b for b in d_blocks if id(b) not in d_blocks_to_remove]
        invalidate_block_grid()
    if m_blocks_to_remove and lev:
        lev.moveable_blocks[:] = [b for b in m_blocks if id(b) not in m_blocks_to_remove]
        invalidate_block_grid()


def handle_missile_collisions(state: "GameState", ctx: dict) -> None:
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
            
            # Use spatial grid to query only enemies near explosion radius
            enemy_grid = _build_enemy_grid(state, ctx) if state.enemies else None
            if enemy_grid:
                for enemy in enemy_grid.query_radius(mx, my, rad):
                    if c_distance_squared(enemy["rect"].centerx, enemy["rect"].centery, mx, my) <= rad_sq:
                        enemy["hp"] -= dmg
                        set_enemy_damage_flash(enemy, ctx)
                        state.damage_numbers.append(_create_damage_number(
                            enemy["rect"].centerx, enemy["rect"].y - 20, dmg, (255, 150, 50)
                        ))
                        if enemy["hp"] <= 0 and kill:
                            enemy["killed_by"] = "rocket"  # Tag for DDA tracking
                            kill(enemy, state)
            
            # Damage the ally that was directly hit
            if hit_ally:
                hit_ally["hp"] = hit_ally.get("hp", 0) - dmg
                ally_rect = hit_ally.get("rect")
                if ally_rect:
                    state.damage_numbers.append(_create_damage_number(
                        ally_rect.centerx, ally_rect.y - 20, dmg, (100, 200, 255)  # Blue for ally
                    ))
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
