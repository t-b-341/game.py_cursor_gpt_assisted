"""
RenderContext: screen, fonts, and layout for a single frame.
Build from AppContext via RenderContext.from_app_ctx(app_ctx).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

import pygame

from asset_manager import get_font

if TYPE_CHECKING:
    from systems.camera import Camera


def _default_font(size: int) -> pygame.font.Font:
    """Fallback font when ctx has no font; uses centralized asset_manager."""
    return get_font("main", size)


@dataclass
class RenderContext:
    """Screen, fonts, and layout constants for a single frame. Build from AppContext for consistency."""
    screen: pygame.Surface  # The surface to render to (display when using camera)
    font: pygame.font.Font
    big_font: pygame.font.Font
    small_font: pygame.font.Font
    width: int  # World width (for layout calculations)
    height: int  # World height (for layout calculations)
    display_screen: pygame.Surface = None  # The actual display (for final scaled blit)
    display_width: int = 0  # Display width
    display_height: int = 0  # Display height
    world_scale: float = 1.0  # Scale factor for world -> display (1.0 when using camera)
    camera: "Camera" = None  # Camera for viewport/culling (None for menus)

    @classmethod
    def from_app_ctx(cls, app_ctx: Any, for_gameplay: bool = True) -> RenderContext:
        """Build a RenderContext from AppContext.
        
        Args:
            app_ctx: The AppContext with screen, fonts, and dimensions.
            for_gameplay: If True (default), use world_surface for rendering (larger world).
                          If False, use display surface directly (for menus/UI).
        """
        from systems.camera import get_camera
        
        display_width = getattr(app_ctx, 'display_width', app_ctx.width)
        display_height = getattr(app_ctx, 'display_height', app_ctx.height)
        camera = get_camera() if for_gameplay else None
        
        if for_gameplay and camera is not None:
            # Camera mode: render directly to display, camera handles viewport
            render_surface = app_ctx.screen
            width = app_ctx.width  # World width for logic
            height = app_ctx.height  # World height for logic
            world_scale = 1.0  # No scaling needed with camera
        elif for_gameplay:
            # Legacy mode: use world_surface with scaling
            world_scale = getattr(app_ctx.config, 'world_scale', 1.0) if hasattr(app_ctx, 'config') else 1.0
            render_surface = getattr(app_ctx, 'world_surface', None) or app_ctx.screen
            width = app_ctx.width
            height = app_ctx.height
        else:
            # Menu mode: use display screen directly
            render_surface = app_ctx.screen
            width = display_width
            height = display_height
            world_scale = 1.0
            camera = None
        
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
            camera=camera,
        )
    
    @classmethod
    def for_menu(cls, app_ctx: Any) -> RenderContext:
        """Create a RenderContext for menu/UI rendering (uses display, not world surface)."""
        return cls.from_app_ctx(app_ctx, for_gameplay=False)

    @classmethod
    def from_screen_and_ctx(cls, screen: pygame.Surface, ctx: dict) -> RenderContext:
        """Build from (screen, ctx) when app_ctx is not available. ctx must have font, big_font, small_font, WIDTH, HEIGHT."""
        from systems.camera import get_camera
        return cls(
            screen=screen,
            font=ctx.get("font") or _default_font(28),
            big_font=ctx.get("big_font") or _default_font(56),
            small_font=ctx.get("small_font") or _default_font(20),
            width=ctx.get("WIDTH", 1920),
            height=ctx.get("HEIGHT", 1080),
            camera=get_camera(),
        )
    
    # Camera helper methods
    def world_to_screen(self, world_x: float, world_y: float) -> tuple[int, int]:
        """Convert world coordinates to screen coordinates using camera offset."""
        if self.camera:
            return self.camera.world_to_screen(world_x, world_y)
        return (int(world_x), int(world_y))
    
    def world_rect_to_screen(self, world_rect: pygame.Rect) -> pygame.Rect:
        """Convert a world-space rect to screen-space rect."""
        if self.camera:
            return self.camera.world_rect_to_screen(world_rect)
        return world_rect
    
    def is_visible(self, world_rect: pygame.Rect) -> bool:
        """Check if a world-space rect is visible in the viewport."""
        if self.camera:
            return self.camera.is_visible(world_rect)
        return True  # No camera = everything visible
    
    @property
    def camera_offset(self) -> tuple[int, int]:
        """Get the current camera offset (for manual offset calculations)."""
        if self.camera:
            return (int(self.camera.x), int(self.camera.y))
        return (0, 0)
