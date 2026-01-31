"""Entity rendering: pickups, allies, enemies, player.

Handles:
- Pickup items with labels
- Friendly AI units
- Enemy units with damage flash
- Player character
"""
from __future__ import annotations

from typing import Any

import pygame

from ..context import RenderContext, get_camera_offset


def draw_pickups(screen: pygame.Surface, state: Any, ctx: dict, render_ctx: RenderContext = None) -> None:
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


def draw_allies_and_enemies(screen: pygame.Surface, state: Any, render_ctx: RenderContext = None) -> None:
    """Draw friendly AI and enemies (unified entity.draw or rect fallback)."""
    cam_x, cam_y = get_camera_offset(render_ctx)
    
    # Draw friendly AI
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
    
    # Draw enemies
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
        
        # Highlight when few enemies remain
        if highlight_when_few and r:
            screen_r = pygame.Rect(r.x - cam_x, r.y - cam_y, r.w, r.h)
            out = screen_r.inflate(8, 8)
            pygame.draw.rect(screen, (255, 255, 0), out, 3)


def draw_player(screen: pygame.Surface, state: Any, render_ctx: RenderContext = None) -> None:
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
