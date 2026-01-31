"""Friendly AI projectile collision handling.

Handles:
- Friendly projectiles vs enemies
- Friendly projectiles vs destructible blocks
- Offscreen projectile cleanup
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..collision_common import set_enemy_damage_flash
from ..spatial_grid import get_enemy_grid, get_block_grid, SpatialGrid, invalidate_block_grid

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


def _build_block_grid(state: "GameState", ctx: dict) -> SpatialGrid:
    """Build spatial grid containing all collidable blocks."""
    cached = ctx.get("_block_grid")
    if cached is not None:
        return cached
    
    lev = getattr(state, "level", None)
    if lev is None:
        return SpatialGrid(1920, 1080, 64)
    
    all_blocks = []
    for block in getattr(lev, "destructible_blocks", []):
        if block.get("is_destructible"):
            all_blocks.append(block)
    for block in getattr(lev, "moveable_blocks", []):
        if block.get("is_destructible"):
            all_blocks.append(block)
    
    width: int = ctx.get("width", 1920)
    height: int = ctx.get("height", 1080)
    grid = get_block_grid(width, height)
    if all_blocks:
        grid.insert_all(all_blocks)
    
    ctx["_block_grid"] = grid
    return grid


def handle_friendly_projectile_offscreen_blocks_enemies(state: "GameState", ctx: dict) -> None:
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
            state.damage_numbers.append(_create_damage_number(
                enemy["rect"].centerx, enemy["rect"].y - 20, dmg
            ))
            if enemy["hp"] <= 0 and kill:
                kill(enemy, state)
            projs_to_remove.add(id(proj))
            break
    
    # Bulk removal
    if projs_to_remove:
        state.friendly_projectiles[:] = [p for p in state.friendly_projectiles if id(p) not in projs_to_remove]
    if d_blocks_to_remove and lev:
        lev.destructible_blocks[:] = [b for b in d_blocks if id(b) not in d_blocks_to_remove]
        invalidate_block_grid()
    if m_blocks_to_remove and lev:
        lev.moveable_blocks[:] = [b for b in m_blocks if id(b) not in m_blocks_to_remove]
        invalidate_block_grid()
