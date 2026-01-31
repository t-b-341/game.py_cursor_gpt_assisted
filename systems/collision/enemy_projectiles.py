"""Enemy projectile collision handling.

Handles:
- Enemy projectiles vs player
- Enemy projectiles vs friendly AI
- Enemy projectiles vs destructible blocks
- Offscreen/expired projectile cleanup
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..spatial_grid import get_block_grid, SpatialGrid, invalidate_block_grid

if TYPE_CHECKING:
    from state import GameState


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


def handle_enemy_projectile_lifetime_offscreen(state: "GameState", ctx: dict) -> None:
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


def handle_enemy_projectile_block_collisions(state: "GameState", ctx: dict) -> None:
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
        invalidate_block_grid()
    if m_blocks_to_remove:
        lev.moveable_blocks[:] = [b for b in m_blocks if id(b) not in m_blocks_to_remove]
        invalidate_block_grid()


def handle_enemy_projectile_friendly_collisions(state: "GameState", ctx: dict) -> None:
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


def handle_enemy_projectile_decoy_collisions(state: "GameState", ctx: dict) -> None:
    """Apply enemy projectile damage to decoys; decoys absorb projectiles.
    
    This is the core mechanic - decoys draw fire and get destroyed, protecting the player.
    """
    decoys = getattr(state, "decoys", None)
    if not state.enemy_projectiles or not decoys:
        return
    
    projs_to_remove = set()
    decoys_to_remove = set()
    
    for proj in state.enemy_projectiles:
        if id(proj) in projs_to_remove:
            continue
        
        for decoy in decoys:
            if decoy.get("hp", 1) <= 0:
                continue
            if not proj["rect"].colliderect(decoy["rect"]):
                continue
            
            # Decoy absorbs the projectile
            decoy["hp"] = decoy.get("hp", 1) - 1
            projs_to_remove.add(id(proj))
            
            if decoy["hp"] <= 0:
                decoys_to_remove.add(id(decoy))
            break
    
    # Bulk removal
    if projs_to_remove:
        state.enemy_projectiles[:] = [p for p in state.enemy_projectiles if id(p) not in projs_to_remove]
    if decoys_to_remove:
        state.decoys[:] = [d for d in state.decoys if id(d) not in decoys_to_remove]
