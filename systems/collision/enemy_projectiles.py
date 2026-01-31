"""Enemy projectile collision handling.

Handles:
- Enemy projectiles vs player
- Enemy projectiles vs friendly AI
- Enemy projectiles vs destructible blocks
- Offscreen/expired projectile cleanup
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..spatial_grid import SpatialGrid, invalidate_block_grid
from .helpers import build_block_grid

if TYPE_CHECKING:
    from state import GameState


# Reusable grids for friendlies and decoys
_friendly_grid: SpatialGrid | None = None
_decoy_grid: SpatialGrid | None = None


def _build_friendly_grid(state: "GameState", ctx: dict) -> SpatialGrid:
    """Build spatial grid for friendly AI entities."""
    global _friendly_grid
    width = ctx.get("world_width", ctx.get("width", 1920))
    height = ctx.get("world_height", ctx.get("height", 1080))
    
    if _friendly_grid is None:
        _friendly_grid = SpatialGrid(width, height, cell_size=128)
    else:
        _friendly_grid.clear()
    
    for friendly in state.friendly_ai:
        if friendly.get("hp", 1) > 0:
            _friendly_grid.insert(friendly, friendly["rect"])
    
    return _friendly_grid


def _build_decoy_grid(state: "GameState", ctx: dict) -> SpatialGrid:
    """Build spatial grid for decoys."""
    global _decoy_grid
    width = ctx.get("world_width", ctx.get("width", 1920))
    height = ctx.get("world_height", ctx.get("height", 1080))
    
    decoys = getattr(state, "decoys", None)
    if not decoys:
        return None
    
    if _decoy_grid is None:
        _decoy_grid = SpatialGrid(width, height, cell_size=128)
    else:
        _decoy_grid.clear()
    
    for decoy in decoys:
        if decoy.get("hp", 1) > 0:
            _decoy_grid.insert(decoy, decoy["rect"])
    
    return _decoy_grid


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
    
    block_grid = build_block_grid(state, ctx)
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
    """Apply enemy projectile damage to friendlies; uses spatial grid for O(n) instead of O(n*m)."""
    if not state.enemy_projectiles or not state.friendly_ai:
        return
    
    # Build spatial grid for friendlies
    friendly_grid = _build_friendly_grid(state, ctx)
    
    projs_to_remove = set()
    friendlies_to_remove = set()
    
    for proj in state.enemy_projectiles:
        if id(proj) in projs_to_remove:
            continue
        
        # Query only nearby friendlies using spatial grid
        for friendly in friendly_grid.query_rect(proj["rect"]):
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
    """Apply enemy projectile damage to decoys; uses spatial grid for O(n) instead of O(n*m).
    
    This is the core mechanic - decoys draw fire and get destroyed, protecting the player.
    """
    decoys = getattr(state, "decoys", None)
    if not state.enemy_projectiles or not decoys:
        return
    
    # Build spatial grid for decoys
    decoy_grid = _build_decoy_grid(state, ctx)
    if decoy_grid is None:
        return
    
    projs_to_remove = set()
    decoys_to_remove = set()
    
    for proj in state.enemy_projectiles:
        if id(proj) in projs_to_remove:
            continue
        
        # Query only nearby decoys using spatial grid
        for decoy in decoy_grid.query_rect(proj["rect"]):
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
