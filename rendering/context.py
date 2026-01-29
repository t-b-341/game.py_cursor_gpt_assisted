"""
RenderContext: screen, fonts, and layout for a single frame.
Build from AppContext via RenderContext.from_app_ctx(app_ctx).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pygame

from asset_manager import get_font


def _default_font(size: int) -> pygame.font.Font:
    """Fallback font when ctx has no font; uses centralized asset_manager."""
    return get_font("main", size)


@dataclass
class RenderContext:
    """Screen, fonts, and layout constants for a single frame. Build from AppContext for consistency."""
    screen: pygame.Surface  # The surface to render to (world_surface or display)
    font: pygame.font.Font
    big_font: pygame.font.Font
    small_font: pygame.font.Font
    width: int  # World width (for layout calculations)
    height: int  # World height (for layout calculations)
    display_screen: pygame.Surface = None  # The actual display (for final scaled blit)
    display_width: int = 0  # Display width
    display_height: int = 0  # Display height
    world_scale: float = 1.0  # Scale factor for world -> display

    @classmethod
    def from_app_ctx(cls, app_ctx: Any, for_gameplay: bool = True) -> RenderContext:
        """Build a RenderContext from AppContext.
        
        Args:
            app_ctx: The AppContext with screen, fonts, and dimensions.
            for_gameplay: If True (default), use world_surface for rendering (larger world).
                          If False, use display surface directly (for menus/UI).
        """
        world_scale = getattr(app_ctx.config, 'world_scale', 1.0) if hasattr(app_ctx, 'config') else 1.0
        display_width = getattr(app_ctx, 'display_width', app_ctx.width)
        display_height = getattr(app_ctx, 'display_height', app_ctx.height)
        
        if for_gameplay:
            # Use world_surface for gameplay rendering (scaled world)
            render_surface = getattr(app_ctx, 'world_surface', None) or app_ctx.screen
            width = app_ctx.width
            height = app_ctx.height
        else:
            # Use display screen directly for menus (native resolution)
            render_surface = app_ctx.screen
            width = display_width
            height = display_height
            world_scale = 1.0  # No scaling for menus
        
        return cls(
            screen=render_surface,
            font=app_ctx.font,
            big_font=app_ctx.big_font,
            small_font=app_ctx.small_font,
            width=width,
            height=height,
            display_screen=app_ctx.screen,
            display_width=display_width,
            display_height=display_height,
            world_scale=world_scale,
        )
    
    @classmethod
    def for_menu(cls, app_ctx: Any) -> RenderContext:
        """Create a RenderContext for menu/UI rendering (uses display, not world surface)."""
        return cls.from_app_ctx(app_ctx, for_gameplay=False)

    @classmethod
    def from_screen_and_ctx(cls, screen: pygame.Surface, ctx: dict) -> RenderContext:
        """Build from (screen, ctx) when app_ctx is not available. ctx must have font, big_font, small_font, WIDTH, HEIGHT."""
        return cls(
            screen=screen,
            font=ctx.get("font") or _default_font(28),
            big_font=ctx.get("big_font") or _default_font(56),
            small_font=ctx.get("small_font") or _default_font(20),
            width=ctx.get("WIDTH", 1920),
            height=ctx.get("HEIGHT", 1080),
        )
