"""Terrain and block rendering.

Handles:
- Trapezoid and triangle blocks
- Static/destructible/moveable blocks
- Hazards and health zones
- Teleporter pads
"""
from __future__ import annotations

from typing import Any

import pygame

from ..context import RenderContext, get_camera_offset
from .textures import draw_silver_wall_texture, draw_cracked_brick_wall_texture

# Surface caches for complex shapes
_trapezoid_surface_cache: dict = {}
_triangle_surface_cache: dict = {}

# Health zone surface cache: (width, height, color, is_triangle) -> Surface
_health_zone_cache: dict[tuple, pygame.Surface] = {}


def draw_terrain(screen: pygame.Surface, state: Any, ctx: dict, render_ctx: RenderContext = None) -> None:
    """Draw static obstacles: trapezoid/triangle blocks, destructible/giant blocks, hazards, health zone."""
    # Get camera offset for positioning
    cam_x, cam_y = get_camera_offset(render_ctx)
    
    trapezoid_blocks = ctx.get("trapezoid_blocks", [])
    triangle_blocks = ctx.get("triangle_blocks", [])
    
    # Draw trapezoid blocks
    for tr in trapezoid_blocks:
        # Culling: skip if not visible
        bounding = tr.get("bounding_rect", tr.get("rect"))
        if render_ctx and bounding and not render_ctx.is_visible(bounding):
            continue
        
        block_id = f"trap_{id(tr)}"
        if block_id not in _trapezoid_surface_cache:
            points = tr.get("points", [])
            if points:
                min_x = min(p[0] for p in points)
                max_x = max(p[0] for p in points)
                min_y = min(p[1] for p in points)
                max_y = max(p[1] for p in points)
                cached_surf = pygame.Surface((max_x - min_x + 10, max_y - min_y + 10), pygame.SRCALPHA)
                offset_pts = [(p[0] - min_x + 5, p[1] - min_y + 5) for p in points]
                pygame.draw.polygon(cached_surf, tr["color"], offset_pts)
                pygame.draw.polygon(cached_surf, (255, 255, 255), offset_pts, 2)
                _trapezoid_surface_cache[block_id] = (cached_surf, (min_x - 5, min_y - 5))
        if block_id in _trapezoid_surface_cache:
            surf, offset = _trapezoid_surface_cache[block_id]
            screen.blit(surf, (offset[0] - cam_x, offset[1] - cam_y))

    # Draw triangle blocks
    for tr in triangle_blocks:
        bounding = tr.get("bounding_rect", tr.get("rect"))
        if render_ctx and bounding and not render_ctx.is_visible(bounding):
            continue
        
        block_id = f"tri_{id(tr)}"
        if block_id not in _triangle_surface_cache:
            points = tr.get("points", [])
            if points:
                min_x = min(p[0] for p in points)
                max_x = max(p[0] for p in points)
                min_y = min(p[1] for p in points)
                max_y = max(p[1] for p in points)
                cached_surf = pygame.Surface((max_x - min_x + 10, max_y - min_y + 10), pygame.SRCALPHA)
                offset_pts = [(p[0] - min_x + 5, p[1] - min_y + 5) for p in points]
                pygame.draw.polygon(cached_surf, tr["color"], offset_pts)
                pygame.draw.polygon(cached_surf, (255, 255, 255), offset_pts, 2)
                _triangle_surface_cache[block_id] = (cached_surf, (min_x - 5, min_y - 5))
        if block_id in _triangle_surface_cache:
            surf, offset = _triangle_surface_cache[block_id]
            screen.blit(surf, (offset[0] - cam_x, offset[1] - cam_y))

    # Static blocks from custom maps (walls, rocks, etc.)
    for block in ctx.get("static_blocks", []):
        rect = block.get("rect")
        if render_ctx and rect and not render_ctx.is_visible(rect):
            continue
        screen_rect = pygame.Rect(rect.x - cam_x, rect.y - cam_y, rect.w, rect.h) if rect else None
        if screen_rect:
            color = block.get("color", (40, 40, 45))
            pygame.draw.rect(screen, color, screen_rect)
            # Draw a subtle border for visibility
            border_color = tuple(min(255, c + 30) for c in color)
            pygame.draw.rect(screen, border_color, screen_rect, 2)
    
    # Destructible blocks
    for block in ctx.get("destructible_blocks", []):
        rect = block.get("rect")
        if render_ctx and rect and not render_ctx.is_visible(rect):
            continue
        screen_rect = pygame.Rect(rect.x - cam_x, rect.y - cam_y, rect.w, rect.h) if rect else None
        if screen_rect:
            if block.get("is_destructible") and block.get("hp", 0) > 0:
                draw_cracked_brick_wall_texture(screen, screen_rect, block.get("crack_level", 0))
            else:
                draw_silver_wall_texture(screen, screen_rect)
                
    # Moveable destructible blocks
    for block in ctx.get("moveable_destructible_blocks", []):
        rect = block.get("rect")
        if render_ctx and rect and not render_ctx.is_visible(rect):
            continue
        screen_rect = pygame.Rect(rect.x - cam_x, rect.y - cam_y, rect.w, rect.h) if rect else None
        if screen_rect:
            if block.get("is_destructible") and block.get("hp", 0) > 0:
                draw_cracked_brick_wall_texture(screen, screen_rect, block.get("crack_level", 0))
            else:
                draw_silver_wall_texture(screen, screen_rect)
                
    # Giant blocks
    for block in ctx.get("giant_blocks", []):
        rect = block.get("rect")
        if render_ctx and rect and not render_ctx.is_visible(rect):
            continue
        screen_rect = pygame.Rect(rect.x - cam_x, rect.y - cam_y, rect.w, rect.h) if rect else None
        if screen_rect:
            draw_silver_wall_texture(screen, screen_rect)
            
    # Super giant blocks
    for block in ctx.get("super_giant_blocks", []):
        rect = block.get("rect")
        if render_ctx and rect and not render_ctx.is_visible(rect):
            continue
        screen_rect = pygame.Rect(rect.x - cam_x, rect.y - cam_y, rect.w, rect.h) if rect else None
        if screen_rect:
            draw_silver_wall_texture(screen, screen_rect)

    # Hazards
    for hazard in ctx.get("hazard_obstacles", []):
        points = hazard.get("points", [])
        if len(points) >= 3:
            # Offset hazard points by camera
            screen_pts = [(p.x - cam_x, p.y - cam_y) if hasattr(p, 'x') else (p[0] - cam_x, p[1] - cam_y) for p in points]
            pygame.draw.polygon(screen, hazard["color"], screen_pts)
            pygame.draw.polygon(screen, (255, 255, 255), screen_pts, 2)

    # Health zone
    _draw_health_zone(screen, state, ctx, render_ctx, cam_x, cam_y)
    
    # Teleporter pads
    _draw_teleporter_pads(screen, ctx, render_ctx, cam_x, cam_y)


def _draw_health_zone(screen: pygame.Surface, state: Any, ctx: dict, render_ctx: RenderContext, cam_x: int, cam_y: int) -> None:
    """Draw the moving health zone if present."""
    zone = ctx.get("moving_health_zone")
    if not zone:
        return
        
    zone_rect = zone["rect"]
    if render_ctx and not render_ctx.is_visible(zone_rect):
        return
        
    zone_width = zone_rect.w
    zone_height = zone_rect.h
    use_triangle = (getattr(state, "wave_in_level", 1) % 2 == 0)
    
    # Cache the zone surface by size, color, and shape
    cache_key = (zone_width, zone_height, zone["color"], use_triangle)
    if cache_key not in _health_zone_cache:
        zone_surf = pygame.Surface((zone_width + 20, zone_height + 20), pygame.SRCALPHA)
        if use_triangle:
            triangle_points = [
                (zone_width // 2, 10),
                (10, zone_height + 10),
                (zone_width + 10, zone_height + 10),
            ]
            pygame.draw.polygon(zone_surf, zone["color"], triangle_points)
        else:
            pygame.draw.rect(zone_surf, zone["color"], (10, 10, zone_width, zone_height))
        _health_zone_cache[cache_key] = zone_surf.convert_alpha()
    
    zone_surf = _health_zone_cache[cache_key]
    screen.blit(zone_surf, (zone_rect.x - 10 - cam_x, zone_rect.y - 10 - cam_y))
    
    # Draw border (position changes, so can't cache)
    border_color = (50, 255, 50)
    if use_triangle:
        zone_center = (zone_rect.centerx - cam_x, zone_rect.centery - cam_y)
        pygame.draw.polygon(screen, border_color, [
            (zone_center[0], zone_rect.y - cam_y),
            (zone_rect.x - cam_x, zone_rect.bottom - cam_y),
            (zone_rect.right - cam_x, zone_rect.bottom - cam_y),
        ], 3)
    else:
        screen_zone_rect = pygame.Rect(zone_rect.x - cam_x, zone_rect.y - cam_y, zone_rect.w, zone_rect.h)
        pygame.draw.rect(screen, border_color, screen_zone_rect, 3)
    
    # Draw "HEALTH RECHARGE" label centered on the zone
    small_font = ctx.get("small_font")
    if small_font:
        label_text = "HEALTH RECHARGE"
        label_surf = small_font.render(label_text, True, (255, 255, 255))
        outline_surf = small_font.render(label_text, True, (0, 0, 0))
        label_x = zone_rect.centerx - cam_x - label_surf.get_width() // 2
        label_y = zone_rect.centery - cam_y - label_surf.get_height() // 2
        # Draw outline for visibility
        for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            screen.blit(outline_surf, (label_x + dx, label_y + dy))
        screen.blit(label_surf, (label_x, label_y))


def _draw_teleporter_pads(screen: pygame.Surface, ctx: dict, render_ctx: RenderContext, cam_x: int, cam_y: int) -> None:
    """Draw teleporter pads."""
    for pad in ctx.get("teleporter_pads", []):
        r = pad.get("rect")
        if not r:
            continue
        if render_ctx and not render_ctx.is_visible(r):
            continue
        cx, cy = r.centerx - cam_x, r.centery - cam_y
        half = r.w // 2
        pts = [(cx, cy - half), (cx + half, cy), (cx, cy + half), (cx - half, cy)]
        pygame.draw.polygon(screen, (50, 220, 80), pts)
        pygame.draw.polygon(screen, (180, 80, 220), pts, 3)


def clear_terrain_cache() -> None:
    """Clear all cached terrain surfaces."""
    _trapezoid_surface_cache.clear()
    _triangle_surface_cache.clear()
    _health_zone_cache.clear()
