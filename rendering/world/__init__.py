"""World rendering package: background, terrain, entities, projectiles, effects, beams.

This package splits world rendering into focused modules:
- textures: Wall texture generation and caching
- projectiles: Projectile, effect, and beam rendering
- terrain: Terrain blocks, hazards, health zones
- entities: Pickups, allies, enemies, player

Main entry points:
- render_background(): Background, tile maps, terrain, pickups
- render_entities(): Allies, enemies, player
- render_projectiles(): Projectiles, effects, beams
- render_gameplay(): Legacy combined entry point

Performance optimizations:
- Cached projectile surfaces avoid recreating shapes each frame
- Batch blitting for projectiles of the same type
- Culling for off-screen entities
"""
from __future__ import annotations

from typing import Any

import pygame

from ..context import RenderContext
from .textures import (
    draw_silver_wall_texture,
    draw_cracked_brick_wall_texture,
    clear_texture_cache,
)
from .projectiles import (
    draw_projectile,
    draw_projectiles,
    draw_effects,
    draw_beams,
    _get_cached_projectile_surface,
    clear_projectile_cache,
)
from .terrain import (
    draw_terrain,
    clear_terrain_cache,
)
from .entities import (
    draw_pickups,
    draw_allies_and_enemies,
    draw_player,
)

# Import perf_timer for performance tracking
from systems.perf_timing import perf_timer


def _draw_tile_map(screen: pygame.Surface, ctx: dict, render_ctx: RenderContext) -> None:
    """Draw tile-based map layer (if map_manager is available in app_ctx)."""
    app_ctx = ctx.get("app_ctx")
    if app_ctx is None:
        return
    
    map_manager = getattr(app_ctx, "map_manager", None)
    if map_manager is None or map_manager.current_map is None:
        return
    
    # Use camera from render_ctx if available
    camera = render_ctx.camera if render_ctx else None
    map_manager.render(screen, camera)


def _track_culling_stats(render_ctx: RenderContext, total: int, visible: int) -> None:
    """Track entity culling stats on the camera."""
    if render_ctx and render_ctx.camera:
        render_ctx.camera.entities_total += total
        render_ctx.camera.entities_culled += (total - visible)


def render_background(state: Any, ctx: dict, render_ctx: RenderContext) -> None:
    """Draw background (theme fill), tile maps, terrain/obstacles, and pickups. First layer of the frame."""
    with perf_timer("render_background"):
        if not ctx:
            return
        level_themes = ctx.get("level_themes", {})
        default_theme = level_themes.get(1, {})
        theme = level_themes.get(getattr(state, "current_level", 1), default_theme)
        bg = theme.get("bg_color", (0, 0, 0))
        render_ctx.screen.fill(bg)
        
        # Render tile map (if available) - drawn below terrain/entities
        _draw_tile_map(render_ctx.screen, ctx, render_ctx)
        
        draw_terrain(render_ctx.screen, state, ctx, render_ctx)
        draw_pickups(render_ctx.screen, state, ctx, render_ctx)


def render_entities(state: Any, ctx: dict, render_ctx: RenderContext) -> None:
    """Draw entities: allies, enemies, and player. Mid-layer of the frame."""
    with perf_timer("render_entities"):
        draw_allies_and_enemies(render_ctx.screen, state, render_ctx)
        draw_player(render_ctx.screen, state, render_ctx)


def render_projectiles(state: Any, ctx: dict, render_ctx: RenderContext) -> None:
    """Draw projectiles, particles (explosions, missiles), and beams. On top of entities."""
    with perf_timer("render_projectiles"):
        draw_projectiles(render_ctx.screen, state, render_ctx)
        draw_effects(render_ctx.screen, state, render_ctx)
        draw_beams(render_ctx.screen, state, render_ctx)


def render_gameplay(state: Any, screen: pygame.Surface, ctx: dict) -> None:
    """Legacy world-only entry point: background, entities, projectiles. Prefer screens.gameplay.render (five-phase pipeline).

    Draw order: (1) background+terrain+pickups, (2) allies+enemies+player, (3) projectiles+effects+beams.
    For full frame, caller must also call render_hud and render_overlays (e.g. from systems.ui_system).
    ctx must contain: level_themes, trapezoid_blocks, ..., small_font, weapon_names (see render_background/_draw_*).
    """
    if not ctx:
        return
    rctx = RenderContext.from_screen_and_ctx(screen, ctx)
    render_background(state, ctx, rctx)
    render_entities(state, ctx, rctx)
    render_projectiles(state, ctx, rctx)


def clear_all_caches() -> None:
    """Clear all world rendering caches."""
    clear_texture_cache()
    clear_projectile_cache()
    clear_terrain_cache()


# Re-export for backward compatibility
__all__ = [
    # Main render functions
    "render_background",
    "render_entities",
    "render_projectiles",
    "render_gameplay",
    # Texture functions
    "draw_silver_wall_texture",
    "draw_cracked_brick_wall_texture",
    # Projectile functions
    "draw_projectile",
    "_get_cached_projectile_surface",
    # Cache clearing
    "clear_all_caches",
    "clear_texture_cache",
    "clear_projectile_cache",
    "clear_terrain_cache",
]
