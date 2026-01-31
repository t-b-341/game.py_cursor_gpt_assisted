"""
World rendering: background, terrain, entities, projectiles, effects, beams.

Performance optimizations:
- Cached projectile surfaces avoid recreating shapes each frame
- Batch blitting for projectiles of the same type
"""
from __future__ import annotations

import math
from typing import Any

import pygame

from .context import RenderContext, get_camera_offset

# Module-level caches for rendering optimization
_wall_texture_cache = {}
_trapezoid_surface_cache: dict = {}
_triangle_surface_cache: dict = {}

# Projectile surface cache: (color, shape, size) -> Surface
_projectile_surface_cache: dict[tuple, pygame.Surface] = {}

# Health zone surface cache: (width, height, color, is_triangle) -> Surface
_health_zone_cache: dict[tuple, pygame.Surface] = {}


def _create_cached_silver_wall_texture(width: int, height: int) -> pygame.Surface:
    """Create a cached silver wall texture surface."""
    surf = pygame.Surface((width, height))
    silver_base = (192, 192, 192)
    silver_dark = (160, 160, 160)
    silver_light = (220, 220, 220)

    surf.fill(silver_base)
    brick_width = max(8, width // 4)
    brick_height = max(6, height // 3)
    for y in range(brick_height, height, brick_height):
        pygame.draw.line(surf, silver_dark, (0, y), (width, y), 1)
    offset = 0
    for y in range(0, height, brick_height * 2):
        for x in range(offset, width, brick_width):
            pygame.draw.line(surf, silver_dark, (x, y), (x, min(y + brick_height, height)), 1)
        offset = brick_width // 2 if offset == 0 else 0
    for i in range(0, width, brick_width):
        for j in range(0, height, brick_height):
            highlight_x = i + brick_width // 4
            highlight_y = j + brick_height // 4
            if highlight_x < width and highlight_y < height:
                pygame.draw.circle(surf, silver_light, (highlight_x, highlight_y), 2)
    return surf


def _create_cached_cracked_brick_texture(width: int, height: int, crack_level: int) -> pygame.Surface:
    """Create a cached cracked brick wall texture surface."""
    surf = pygame.Surface((width, height))
    brick_red = (180, 80, 60)
    brick_dark = (140, 60, 40)
    brick_light = (200, 100, 80)
    mortar = (100, 100, 100)
    surf.fill(brick_red)
    brick_width = max(10, width // 4)
    brick_height = max(8, height // 3)
    for y in range(brick_height, height, brick_height):
        pygame.draw.line(surf, mortar, (0, y), (width, y), 2)
    offset = 0
    for y in range(0, height, brick_height * 2):
        for x in range(offset, width, brick_width):
            pygame.draw.line(surf, mortar, (x, y), (x, min(y + brick_height, height)), 2)
        offset = brick_width // 2 if offset == 0 else 0
    offset = 0
    for y in range(0, height, brick_height):
        for x in range(offset, width, brick_width):
            brick_rect = pygame.Rect(x + 1, y + 1, min(brick_width - 2, width - x - 1), min(brick_height - 2, height - y - 1))
            if brick_rect.w > 0 and brick_rect.h > 0:
                pygame.draw.line(surf, brick_light, (brick_rect.left, brick_rect.top), (brick_rect.right, brick_rect.top), 1)
                pygame.draw.line(surf, brick_light, (brick_rect.left, brick_rect.top), (brick_rect.left, brick_rect.bottom), 1)
                pygame.draw.line(surf, brick_dark, (brick_rect.right, brick_rect.top), (brick_rect.right, brick_rect.bottom), 1)
                pygame.draw.line(surf, brick_dark, (brick_rect.left, brick_rect.bottom), (brick_rect.right, brick_rect.bottom), 1)
        offset = brick_width // 2 if offset == 0 else 0
    if crack_level >= 1:
        center = (width // 2, height // 2)
        crack_color = (40, 40, 40)
        for i in range(crack_level):
            angle = (i * 2.4) * math.pi / 3
            end_x = center[0] + math.cos(angle) * (width // 2)
            end_y = center[1] + math.sin(angle) * (height // 2)
            pygame.draw.line(surf, crack_color, center, (end_x, end_y), 2)
        if crack_level >= 2:
            for i in range(crack_level):
                angle = (i * 1.8 + 0.5) * math.pi / 3
                start_x = center[0] + math.cos(angle) * (width // 4)
                start_y = center[1] + math.sin(angle) * (height // 4)
                end_x = start_x + math.cos(angle) * (width // 3)
                end_y = start_y + math.sin(angle) * (height // 3)
                pygame.draw.line(surf, crack_color, (start_x, start_y), (end_x, end_y), 1)
    return surf


def draw_silver_wall_texture(screen: pygame.Surface, rect: pygame.Rect) -> None:
    """Draw a silver wall texture for indestructible blocks (uses cached surface when possible)."""
    cache_key = (rect.w // 10 * 10, rect.h // 10 * 10)
    if cache_key not in _wall_texture_cache:
        # Use convert() for hardware-accelerated blitting
        _wall_texture_cache[cache_key] = _create_cached_silver_wall_texture(cache_key[0], cache_key[1]).convert()
    cached_surf = _wall_texture_cache[cache_key]
    if cache_key[0] == rect.w and cache_key[1] == rect.h:
        screen.blit(cached_surf, rect.topleft)
    else:
        scaled = pygame.transform.scale(cached_surf, (rect.w, rect.h))
        screen.blit(scaled, rect.topleft)


def draw_cracked_brick_wall_texture(screen: pygame.Surface, rect: pygame.Rect, crack_level: int = 1) -> None:
    """Draw a cracked brick wall texture for destructible blocks (uses cached surface when possible)."""
    cache_key = (rect.w // 10 * 10, rect.h // 10 * 10, crack_level)
    if cache_key not in _wall_texture_cache:
        _wall_texture_cache[cache_key] = _create_cached_cracked_brick_texture(cache_key[0], cache_key[1], crack_level)
    cached_surf = _wall_texture_cache[cache_key]
    if cache_key[0] == rect.w and cache_key[1] == rect.h:
        screen.blit(cached_surf, rect.topleft)
    else:
        scaled = pygame.transform.scale(cached_surf, (rect.w, rect.h))
        screen.blit(scaled, rect.topleft)


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


def _draw_terrain(screen: pygame.Surface, state: Any, ctx: dict, render_ctx: RenderContext = None) -> None:
    """Draw static obstacles: trapezoid/triangle blocks, destructible/giant blocks, hazards, health zone."""
    # Get camera offset for positioning
    cam_x, cam_y = get_camera_offset(render_ctx)
    
    trapezoid_blocks = ctx.get("trapezoid_blocks", [])
    triangle_blocks = ctx.get("triangle_blocks", [])
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
                
    for block in ctx.get("giant_blocks", []):
        rect = block.get("rect")
        if render_ctx and rect and not render_ctx.is_visible(rect):
            continue
        screen_rect = pygame.Rect(rect.x - cam_x, rect.y - cam_y, rect.w, rect.h) if rect else None
        if screen_rect:
            draw_silver_wall_texture(screen, screen_rect)
            
    for block in ctx.get("super_giant_blocks", []):
        rect = block.get("rect")
        if render_ctx and rect and not render_ctx.is_visible(rect):
            continue
        screen_rect = pygame.Rect(rect.x - cam_x, rect.y - cam_y, rect.w, rect.h) if rect else None
        if screen_rect:
            draw_silver_wall_texture(screen, screen_rect)

    for hazard in ctx.get("hazard_obstacles", []):
        points = hazard.get("points", [])
        if len(points) >= 3:
            # Offset hazard points by camera
            screen_pts = [(p.x - cam_x, p.y - cam_y) if hasattr(p, 'x') else (p[0] - cam_x, p[1] - cam_y) for p in points]
            pygame.draw.polygon(screen, hazard["color"], screen_pts)
            pygame.draw.polygon(screen, (255, 255, 255), screen_pts, 2)

    zone = ctx.get("moving_health_zone")
    if zone:
        zone_rect = zone["rect"]
        if not render_ctx or render_ctx.is_visible(zone_rect):
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


def _draw_pickups(screen: pygame.Surface, state: Any, ctx: dict, render_ctx: RenderContext = None) -> None:
    """Draw pickups and their labels."""
    cam_x, cam_y = get_camera_offset(render_ctx)
    weapon_names = ctx.get("weapon_names", {})
    small_font = ctx.get("small_font")
    for pickup in getattr(state, "pickups", []):
        rect = pickup["rect"]
        # Culling
        if render_ctx and not render_ctx.is_visible(rect):
            continue
        center = (rect.centerx - cam_x, rect.centery - cam_y)
        pygame.draw.circle(screen, pickup["color"], center, rect.w // 2)
        pygame.draw.circle(screen, (255, 255, 255), center, rect.w // 2, 2)
        if small_font:
            if pickup.get("is_weapon_drop", False):
                pickup_name = weapon_names.get(pickup.get("type", ""), pickup.get("type", "").upper())
            else:
                pickup_name = pickup.get("type", "").upper().replace("_", " ")
            name_surf = small_font.render(pickup_name, True, (255, 255, 255))
            name_rect = name_surf.get_rect(center=(rect.centerx - cam_x, rect.y - 20 - cam_y))
            outline_surf = small_font.render(pickup_name, True, (0, 0, 0))
            for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                screen.blit(outline_surf, (name_rect.x + dx, name_rect.y + dy))
            screen.blit(name_surf, name_rect)


def _draw_projectiles(screen: pygame.Surface, state: Any, render_ctx: RenderContext = None) -> None:
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


def _draw_allies_and_enemies(screen: pygame.Surface, state: Any, render_ctx: RenderContext = None) -> None:
    """Draw friendly AI and enemies (unified entity.draw or rect fallback)."""
    cam_x, cam_y = get_camera_offset(render_ctx)
    
    for friendly in getattr(state, "friendly_ai", []):
        r = friendly.get("rect")
        if render_ctx and r and not render_ctx.is_visible(r):
            continue
        if hasattr(friendly, "draw"):
            # For objects with custom draw, pass camera offset
            if hasattr(friendly, "draw_with_offset"):
                friendly.draw_with_offset(screen, cam_x, cam_y)
            else:
                # Fallback: draw at offset position
                if r:
                    screen_r = pygame.Rect(r.x - cam_x, r.y - cam_y, r.w, r.h)
                    pygame.draw.rect(screen, friendly.get("color", (100, 200, 100)), screen_r)
        else:
            if r:
                screen_r = pygame.Rect(r.x - cam_x, r.y - cam_y, r.w, r.h)
                pygame.draw.rect(screen, friendly.get("color", (100, 200, 100)), screen_r)
                
    enemies_list = getattr(state, "enemies", [])
    highlight_when_few = len(enemies_list) <= 5
    for enemy in enemies_list:
        r = enemy.get("rect") if isinstance(enemy, dict) else getattr(enemy, "rect", None)
        if render_ctx and r and not render_ctx.is_visible(r):
            continue
        if hasattr(enemy, "draw"):
            if hasattr(enemy, "draw_with_offset"):
                enemy.draw_with_offset(screen, cam_x, cam_y)
            elif r:
                # Fallback for dict-based enemies
                screen_r = pygame.Rect(r.x - cam_x, r.y - cam_y, r.w, r.h)
                base_color = enemy.get("color", (200, 50, 50))
                pygame.draw.rect(screen, base_color, screen_r)
        elif r:
            screen_r = pygame.Rect(r.x - cam_x, r.y - cam_y, r.w, r.h)
            base_color = enemy.get("color", (200, 50, 50))
            flash_t = enemy.get("damage_flash_timer", 0.0)
            if flash_t > 0:
                flash_frac = min(1.0, flash_t / 0.12)
                base_color = tuple(min(255, int(c + (255 - c) * flash_frac)) for c in base_color)
            # Draw rhomboid shape for evasive enemies, rectangle for others
            if enemy.get("shape") == "rhomboid":
                cx, cy = screen_r.centerx, screen_r.centery
                hw, hh = screen_r.width // 2, screen_r.height // 2
                points = [(cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)]
                pygame.draw.polygon(screen, base_color, points)
            else:
                pygame.draw.rect(screen, base_color, screen_r)
        if highlight_when_few and r:
            screen_r = pygame.Rect(r.x - cam_x, r.y - cam_y, r.w, r.h)
            out = screen_r.inflate(8, 8)
            pygame.draw.rect(screen, (255, 255, 0), out, 3)


def _draw_effects(screen: pygame.Surface, state: Any, render_ctx: RenderContext = None) -> None:
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


def _draw_player(screen: pygame.Surface, state: Any, render_ctx: RenderContext = None) -> None:
    """Draw player circle (and border); shield-active uses light blue tint."""
    cam_x, cam_y = get_camera_offset(render_ctx)
    
    player = getattr(state, "player_rect", None)
    if player is None:
        return
    
    # Player center in screen coords
    center = (player.centerx - cam_x, player.centery - cam_y)
    
    player_color = (255, 255, 255)
    border_color = (200, 200, 200)
    if getattr(state, "shield_active", False):
        player_color = (100, 200, 255)  # Light blue when shield active
        border_color = (150, 220, 255)
    pygame.draw.circle(screen, border_color, center, player.w // 2 + 2, 2)
    pygame.draw.circle(screen, player_color, center, player.w // 2)


def _draw_beams(screen: pygame.Surface, state: Any, render_ctx: RenderContext = None) -> None:
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
        
        _draw_terrain(render_ctx.screen, state, ctx, render_ctx)
        _draw_pickups(render_ctx.screen, state, ctx, render_ctx)


def render_entities(state: Any, ctx: dict, render_ctx: RenderContext) -> None:
    """Draw entities: allies, enemies, and player. Mid-layer of the frame."""
    with perf_timer("render_entities"):
        _draw_allies_and_enemies(render_ctx.screen, state, render_ctx)
        _draw_player(render_ctx.screen, state, render_ctx)


def render_projectiles(state: Any, ctx: dict, render_ctx: RenderContext) -> None:
    """Draw projectiles, particles (explosions, missiles), and beams. On top of entities."""
    with perf_timer("render_projectiles"):
        _draw_projectiles(render_ctx.screen, state, render_ctx)
        _draw_effects(render_ctx.screen, state, render_ctx)
        _draw_beams(render_ctx.screen, state, render_ctx)


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
