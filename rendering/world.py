"""
World rendering: background, terrain, entities, projectiles, effects, beams.
"""
from __future__ import annotations

import math
from typing import Any

import pygame

from .context import RenderContext

# Module-level caches for rendering optimization
_wall_texture_cache = {}
_trapezoid_surface_cache: dict = {}
_triangle_surface_cache: dict = {}


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
        _wall_texture_cache[cache_key] = _create_cached_silver_wall_texture(cache_key[0], cache_key[1])
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


def draw_projectile(screen: pygame.Surface, rect: pygame.Rect, color: tuple[int, int, int], shape: str) -> None:
    """Draw a projectile with the specified shape."""
    if shape == "circle":
        pygame.draw.circle(screen, color, rect.center, rect.w // 2)
    elif shape == "diamond":
        cx, cy = rect.center
        hw, hh = rect.w // 2, rect.h // 2
        points = [(cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)]
        pygame.draw.polygon(screen, color, points)
    else:
        pygame.draw.rect(screen, color, rect)


def _draw_terrain(screen: pygame.Surface, state: Any, ctx: dict) -> None:
    """Draw static obstacles: trapezoid/triangle blocks, destructible/giant blocks, hazards, health zone."""
    trapezoid_blocks = ctx.get("trapezoid_blocks", [])
    triangle_blocks = ctx.get("triangle_blocks", [])
    for tr in trapezoid_blocks:
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
            screen.blit(surf, offset)

    for tr in triangle_blocks:
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
            screen.blit(surf, offset)

    for block in ctx.get("destructible_blocks", []):
        if block.get("is_destructible") and block.get("hp", 0) > 0:
            draw_cracked_brick_wall_texture(screen, block["rect"], block.get("crack_level", 0))
        else:
            draw_silver_wall_texture(screen, block["rect"])
    for block in ctx.get("moveable_destructible_blocks", []):
        if block.get("is_destructible") and block.get("hp", 0) > 0:
            draw_cracked_brick_wall_texture(screen, block["rect"], block.get("crack_level", 0))
        else:
            draw_silver_wall_texture(screen, block["rect"])
    for block in ctx.get("giant_blocks", []):
        draw_silver_wall_texture(screen, block["rect"])
    for block in ctx.get("super_giant_blocks", []):
        draw_silver_wall_texture(screen, block["rect"])

    for hazard in ctx.get("hazard_obstacles", []):
        points = hazard.get("points", [])
        if len(points) >= 3:
            pygame.draw.polygon(screen, hazard["color"], points)
            pygame.draw.polygon(screen, (255, 255, 255), points, 2)

    zone = ctx.get("moving_health_zone")
    if zone:
        zone_width = zone["rect"].w
        zone_height = zone["rect"].h
        use_triangle = (getattr(state, "wave_in_level", 1) % 2 == 0)
        zone_surf = pygame.Surface((zone["rect"].w + 20, zone["rect"].h + 20), pygame.SRCALPHA)
        if use_triangle:
            triangle_points = [
                (zone_width // 2, 10),
                (10, zone_height + 10),
                (zone_width + 10, zone_height + 10),
            ]
            pygame.draw.polygon(zone_surf, zone["color"], triangle_points)
            screen.blit(zone_surf, (zone["rect"].x - 10, zone["rect"].y - 10))
            border_color = (50, 255, 50)
            zone_center = (zone["rect"].centerx, zone["rect"].centery)
            pygame.draw.polygon(screen, border_color, [
                (zone_center[0], zone["rect"].y),
                (zone["rect"].x, zone["rect"].bottom),
                (zone["rect"].right, zone["rect"].bottom),
            ], 3)
        else:
            pygame.draw.rect(zone_surf, zone["color"], (10, 10, zone["rect"].w, zone["rect"].h))
            screen.blit(zone_surf, (zone["rect"].x - 10, zone["rect"].y - 10))
            border_color = (50, 255, 50)
            pygame.draw.rect(screen, border_color, zone["rect"], 3)

    for pad in ctx.get("teleporter_pads", []):
        r = pad.get("rect")
        if not r:
            continue
        cx, cy = r.centerx, r.centery
        half = r.w // 2
        pts = [(cx, cy - half), (cx + half, cy), (cx, cy + half), (cx - half, cy)]
        pygame.draw.polygon(screen, (50, 220, 80), pts)
        pygame.draw.polygon(screen, (180, 80, 220), pts, 3)


def _draw_pickups(screen: pygame.Surface, state: Any, ctx: dict) -> None:
    """Draw pickups and their labels."""
    weapon_names = ctx.get("weapon_names", {})
    small_font = ctx.get("small_font")
    for pickup in getattr(state, "pickups", []):
        pygame.draw.circle(screen, pickup["color"], pickup["rect"].center, pickup["rect"].w // 2)
        pygame.draw.circle(screen, (255, 255, 255), pickup["rect"].center, pickup["rect"].w // 2, 2)
        if small_font:
            if pickup.get("is_weapon_drop", False):
                pickup_name = weapon_names.get(pickup.get("type", ""), pickup.get("type", "").upper())
            else:
                pickup_name = pickup.get("type", "").upper().replace("_", " ")
            name_surf = small_font.render(pickup_name, True, (255, 255, 255))
            name_rect = name_surf.get_rect(center=(pickup["rect"].centerx, pickup["rect"].y - 20))
            outline_surf = small_font.render(pickup_name, True, (0, 0, 0))
            for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                screen.blit(outline_surf, (name_rect.x + dx, name_rect.y + dy))
            screen.blit(name_surf, name_rect)


def _draw_projectiles(screen: pygame.Surface, state: Any) -> None:
    """Draw enemy, player, and friendly projectiles."""
    for proj in getattr(state, "enemy_projectiles", []):
        draw_projectile(screen, proj["rect"], proj["color"], proj.get("shape", "circle"))
    for bullet in getattr(state, "player_bullets", []):
        draw_projectile(screen, bullet["rect"], bullet["color"], bullet.get("shape", "circle"))
    for proj in getattr(state, "friendly_projectiles", []):
        draw_projectile(screen, proj["rect"], proj["color"], proj.get("shape", "circle"))


def _draw_allies_and_enemies(screen: pygame.Surface, state: Any) -> None:
    """Draw friendly AI and enemies (unified entity.draw or rect fallback)."""
    for friendly in getattr(state, "friendly_ai", []):
        if hasattr(friendly, "draw"):
            friendly.draw(screen)
        else:
            r = friendly.get("rect")
            if r:
                pygame.draw.rect(screen, friendly.get("color", (100, 200, 100)), r)
    enemies_list = getattr(state, "enemies", [])
    highlight_when_few = len(enemies_list) <= 5
    for enemy in enemies_list:
        r = enemy.get("rect") if isinstance(enemy, dict) else getattr(enemy, "rect", None)
        if hasattr(enemy, "draw"):
            enemy.draw(screen)
        elif r:
            base_color = enemy.get("color", (200, 50, 50))
            flash_t = enemy.get("damage_flash_timer", 0.0)
            if flash_t > 0:
                flash_frac = min(1.0, flash_t / 0.12)
                base_color = tuple(min(255, int(c + (255 - c) * flash_frac)) for c in base_color)
            # Draw rhomboid shape for evasive enemies, rectangle for others
            if enemy.get("shape") == "rhomboid":
                cx, cy = r.centerx, r.centery
                hw, hh = r.width // 2, r.height // 2
                points = [(cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)]
                pygame.draw.polygon(screen, base_color, points)
            else:
                pygame.draw.rect(screen, base_color, r)
        if highlight_when_few and r:
            out = r.inflate(8, 8)
            pygame.draw.rect(screen, (255, 255, 0), out, 3)


def _draw_effects(screen: pygame.Surface, state: Any) -> None:
    """Draw grenade explosions and missiles."""
    for explosion in getattr(state, "grenade_explosions", []):
        pygame.draw.circle(screen, (255, 100, 0), (explosion["x"], explosion["y"]), explosion["radius"], 3)
        pygame.draw.circle(screen, (255, 200, 0), (explosion["x"], explosion["y"]), explosion["radius"] // 2)
    for missile in getattr(state, "missiles", []):
        pygame.draw.rect(screen, (160, 80, 220), missile["rect"])
        pygame.draw.rect(screen, (100, 40, 160), missile["rect"], 2)


def _draw_player(screen: pygame.Surface, state: Any) -> None:
    """Draw player circle (and border); shield-active uses light blue tint."""
    player = getattr(state, "player_rect", None)
    if player is None:
        return
    player_color = (255, 255, 255)
    border_color = (200, 200, 200)
    if getattr(state, "shield_active", False):
        player_color = (100, 200, 255)  # Light blue when shield active
        border_color = (150, 220, 255)
    pygame.draw.circle(screen, border_color, player.center, player.w // 2 + 2, 2)
    pygame.draw.circle(screen, player_color, player.center, player.w // 2)


def _draw_beams(screen: pygame.Surface, state: Any) -> None:
    """Draw laser and wave beams (player and enemy)."""
    for beam in getattr(state, "laser_beams", []):
        if "start" in beam and "end" in beam:
            pygame.draw.line(
                screen, beam.get("color", (255, 50, 50)), beam["start"], beam["end"], beam.get("width", 5)
            )
    for beam in getattr(state, "enemy_laser_beams", []):
        if "start" in beam and "end" in beam:
            start, end = beam["start"], beam["end"]
            deploy_timer = beam.get("deploy_timer", 0.0)
            deploy_time = max(0.001, beam.get("deploy_time", 1.0))
            if deploy_timer > 0:
                frac = 1.0 - (deploy_timer / deploy_time)
                mid = pygame.Vector2(
                    start.x + (end.x - start.x) * frac,
                    start.y + (end.y - start.y) * frac,
                )
                color = beam.get("color", (200, 80, 255))
                deploy_color = (color[0] // 2, color[1] // 2, min(255, color[2] // 2 + 128))
                pygame.draw.line(
                    screen, deploy_color, start, mid, max(1, beam.get("width", 4) - 1)
                )
            else:
                pygame.draw.line(
                    screen, beam.get("color", (200, 80, 255)), start, end, beam.get("width", 4)
                )


def render_background(state: Any, ctx: dict, render_ctx: RenderContext) -> None:
    """Draw background (theme fill), terrain/obstacles, and pickups. First layer of the frame."""
    if not ctx:
        return
    level_themes = ctx.get("level_themes", {})
    default_theme = level_themes.get(1, {})
    theme = level_themes.get(getattr(state, "current_level", 1), default_theme)
    bg = theme.get("bg_color", (0, 0, 0))
    render_ctx.screen.fill(bg)
    _draw_terrain(render_ctx.screen, state, ctx)
    _draw_pickups(render_ctx.screen, state, ctx)


def render_entities(state: Any, ctx: dict, render_ctx: RenderContext) -> None:
    """Draw entities: allies, enemies, and player. Mid-layer of the frame."""
    _draw_allies_and_enemies(render_ctx.screen, state)
    _draw_player(render_ctx.screen, state)


def render_projectiles(state: Any, ctx: dict, render_ctx: RenderContext) -> None:
    """Draw projectiles, particles (explosions, missiles), and beams. On top of entities."""
    _draw_projectiles(render_ctx.screen, state)
    _draw_effects(render_ctx.screen, state)
    _draw_beams(render_ctx.screen, state)


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
