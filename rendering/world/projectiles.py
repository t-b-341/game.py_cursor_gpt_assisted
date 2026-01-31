"""Projectile rendering with surface caching.

Provides:
- Cached projectile surface generation
- Batch rendering for efficient multi-projectile drawing
"""
from __future__ import annotations

from typing import Any

import pygame

from ..context import RenderContext, get_camera_offset

# Projectile surface cache: (color, shape, size) -> Surface
_projectile_surface_cache: dict[tuple, pygame.Surface] = {}


def _get_cached_projectile_surface(color: tuple[int, int, int], shape: str, size: tuple[int, int]) -> pygame.Surface:
    """Get or create a cached surface for a projectile shape."""
    # Round size to reduce cache entries (projectiles are typically similar sizes)
    w, h = max(4, (size[0] // 4) * 4), max(4, (size[1] // 4) * 4)
    cache_key = (color, shape, w, h)
    
    if cache_key not in _projectile_surface_cache:
        # Create surface with alpha for proper blending
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        
        if shape == "circle":
            pygame.draw.circle(surf, color, (w // 2, h // 2), w // 2)
        elif shape == "diamond":
            hw, hh = w // 2, h // 2
            points = [(hw, 0), (w, hh), (hw, h), (0, hh)]
            pygame.draw.polygon(surf, color, points)
        else:  # rect
            pygame.draw.rect(surf, color, (0, 0, w, h))
        
        # Use convert_alpha() for hardware-accelerated blitting with transparency
        _projectile_surface_cache[cache_key] = surf.convert_alpha()
    
    return _projectile_surface_cache[cache_key]


def draw_projectile(screen: pygame.Surface, rect: pygame.Rect, color: tuple[int, int, int], shape: str) -> None:
    """Draw a projectile with the specified shape using cached surfaces."""
    surf = _get_cached_projectile_surface(color, shape, (rect.w, rect.h))
    # Blit cached surface (faster than drawing primitives each frame)
    screen.blit(surf, rect.topleft)


def draw_projectiles(screen: pygame.Surface, state: Any, render_ctx: RenderContext = None) -> None:
    """Draw enemy, player, and friendly projectiles with cached surface blitting.
    
    Uses pre-rendered cached surfaces instead of drawing primitives each frame.
    Groups by cache key (color, shape, size) for efficient batch processing.
    """
    cam_x, cam_y = get_camera_offset(render_ctx)
    
    # Collect all projectiles grouped by their visual cache key
    # cache_key -> list of (x, y) positions
    batches: dict[tuple, list[tuple[int, int]]] = {}
    
    all_projectiles = (
        list(getattr(state, "enemy_projectiles", [])) +
        list(getattr(state, "player_bullets", [])) +
        list(getattr(state, "friendly_projectiles", []))
    )
    
    for proj in all_projectiles:
        rect = proj.get("rect")
        if not rect:
            continue
        
        # Culling: skip off-screen projectiles
        if render_ctx and not render_ctx.is_visible(rect):
            continue
        
        color = proj.get("color", (255, 255, 255))
        shape = proj.get("shape", "circle")
        # Round size to reduce cache entries
        w, h = max(4, (rect.w // 4) * 4), max(4, (rect.h // 4) * 4)
        cache_key = (color, shape, w, h)
        
        if cache_key not in batches:
            batches[cache_key] = []
        # Apply camera offset to position
        batches[cache_key].append((rect.x - cam_x, rect.y - cam_y))
    
    # Blit cached surfaces for each batch using blits() for better performance
    for cache_key, positions in batches.items():
        color, shape, w, h = cache_key
        surf = _get_cached_projectile_surface(color, shape, (w, h))
        # Use blits() for batch blitting (faster than individual blit calls)
        if len(positions) > 1:
            blit_list = [(surf, pos) for pos in positions]
            screen.blits(blit_list, doreturn=False)
        elif positions:
            screen.blit(surf, positions[0])


def draw_effects(screen: pygame.Surface, state: Any, render_ctx: RenderContext = None) -> None:
    """Draw grenade explosions and missiles."""
    cam_x, cam_y = get_camera_offset(render_ctx)
    
    for explosion in getattr(state, "grenade_explosions", []):
        ex, ey = explosion["x"] - cam_x, explosion["y"] - cam_y
        pygame.draw.circle(screen, (255, 100, 0), (int(ex), int(ey)), explosion["radius"], 3)
        pygame.draw.circle(screen, (255, 200, 0), (int(ex), int(ey)), explosion["radius"] // 2)
        
    for missile in getattr(state, "missiles", []):
        r = missile["rect"]
        if render_ctx and not render_ctx.is_visible(r):
            continue
        screen_r = pygame.Rect(r.x - cam_x, r.y - cam_y, r.w, r.h)
        # Enemy missiles (target_player) are lime green, player missiles are purple
        if missile.get("target_player"):
            # Lime green for enemy missiles
            pygame.draw.rect(screen, (50, 255, 50), screen_r)
            pygame.draw.rect(screen, (30, 180, 30), screen_r, 2)
        else:
            # Purple for player missiles
            pygame.draw.rect(screen, (160, 80, 220), screen_r)
            pygame.draw.rect(screen, (100, 40, 160), screen_r, 2)


def draw_beams(screen: pygame.Surface, state: Any, render_ctx: RenderContext = None) -> None:
    """Draw laser and wave beams (player and enemy)."""
    cam_x, cam_y = get_camera_offset(render_ctx)
    
    for beam in getattr(state, "laser_beams", []):
        if "start" in beam and "end" in beam:
            start = beam["start"]
            end = beam["end"]
            # Apply camera offset
            s = (start.x - cam_x, start.y - cam_y) if hasattr(start, 'x') else (start[0] - cam_x, start[1] - cam_y)
            e = (end.x - cam_x, end.y - cam_y) if hasattr(end, 'x') else (end[0] - cam_x, end[1] - cam_y)
            pygame.draw.line(screen, beam.get("color", (255, 50, 50)), s, e, beam.get("width", 5))
            
    for beam in getattr(state, "enemy_laser_beams", []):
        if "start" in beam and "end" in beam:
            start, end = beam["start"], beam["end"]
            # Apply camera offset
            sx, sy = (start.x - cam_x, start.y - cam_y) if hasattr(start, 'x') else (start[0] - cam_x, start[1] - cam_y)
            ex, ey = (end.x - cam_x, end.y - cam_y) if hasattr(end, 'x') else (end[0] - cam_x, end[1] - cam_y)
            
            deploy_timer = beam.get("deploy_timer", 0.0)
            deploy_time = max(0.001, beam.get("deploy_time", 1.0))
            if deploy_timer > 0:
                frac = 1.0 - (deploy_timer / deploy_time)
                mid = (sx + (ex - sx) * frac, sy + (ey - sy) * frac)
                color = beam.get("color", (200, 80, 255))
                deploy_color = (color[0] // 2, color[1] // 2, min(255, color[2] // 2 + 128))
                pygame.draw.line(screen, deploy_color, (sx, sy), mid, max(1, beam.get("width", 4) - 1))
            else:
                pygame.draw.line(screen, beam.get("color", (200, 80, 255)), (sx, sy), (ex, ey), beam.get("width", 4))


def clear_projectile_cache() -> None:
    """Clear all cached projectile surfaces."""
    _projectile_surface_cache.clear()
