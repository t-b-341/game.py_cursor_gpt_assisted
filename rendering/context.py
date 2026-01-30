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
        camera = get_camera()
        
        # Get world dimensions from ctx
        world_width = ctx.get("WIDTH", 1920)
        world_height = ctx.get("HEIGHT", 1080)
        
        # Get display dimensions - either from ctx or from screen surface
        # When camera is active, display is the actual screen size
        if camera:
            display_width = camera.display_width
            display_height = camera.display_height
        else:
            # Fallback to screen surface size or ctx values
            display_width = ctx.get("display_width", screen.get_width())
            display_height = ctx.get("display_height", screen.get_height())
        
        return cls(
            screen=screen,
            font=ctx.get("font") or _default_font(28),
            big_font=ctx.get("big_font") or _default_font(56),
            small_font=ctx.get("small_font") or _default_font(20),
            width=world_width,
            height=world_height,
            display_width=display_width,
            display_height=display_height,
            camera=camera,
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


def build_gameplay_ctx(
    app_ctx: Any,
    game_state: Any,
    current_state: str,
    level_themes: dict,
    width: int | None = None,
    height: int | None = None,
) -> dict:
    """Build the gameplay_ctx dict for rendering.
    
    This centralizes the gameplay context construction to avoid duplication
    in _render_current_scene (used for both gameplay and pause overlay).
    
    Args:
        app_ctx: AppContext with config, fonts, etc.
        game_state: GameState with level, teleporter_pads, etc.
        current_state: Current screen state (STATE_PLAYING, STATE_PAUSED, etc.)
        level_themes: Dict of level themes
        width: Override width (uses app_ctx.width if None)
        height: Override height (uses app_ctx.height if None)
    
    Returns:
        Dict with all gameplay rendering context
    """
    from config_weapons import WEAPON_NAMES
    from constants import (
        grenade_cooldown,
        missile_cooldown,
        ally_drop_cooldown,
        overshield_recharge_cooldown,
        shield_duration,
    )
    
    w = width if width is not None else app_ctx.width
    h = height if height is not None else app_ctx.height
    lv = game_state.level
    
    return {
        "level_themes": level_themes,
        "trapezoid_blocks": lv.trapezoid_blocks if lv else [],
        "triangle_blocks": lv.triangle_blocks if lv else [],
        "destructible_blocks": lv.destructible_blocks if lv else [],
        "moveable_destructible_blocks": lv.moveable_blocks if lv else [],
        "giant_blocks": lv.giant_blocks if lv else [],
        "super_giant_blocks": lv.super_giant_blocks if lv else [],
        "hazard_obstacles": lv.hazard_obstacles if lv else [],
        "moving_health_zone": lv.moving_health_zone if lv else None,
        "teleporter_pads": game_state.teleporter_pads,
        "small_font": app_ctx.small_font,
        "weapon_names": WEAPON_NAMES,
        "WIDTH": w,
        "HEIGHT": h,
        "font": app_ctx.font,
        "big_font": app_ctx.big_font,
        "ui_show_hud": app_ctx.config.show_hud,
        "ui_show_metrics": app_ctx.config.show_metrics,
        "ui_show_health_bars": app_ctx.config.show_health_bars,
        "ui_show_fps": app_ctx.config.show_fps,
        "ui_show_perf_overlay": getattr(app_ctx.config, "show_perf_overlay", False),
        "overshield_max": game_state.player_max_hp,
        "grenade_cooldown": grenade_cooldown,
        "missile_cooldown": missile_cooldown,
        "ally_drop_cooldown": ally_drop_cooldown,
        "overshield_recharge_cooldown": overshield_recharge_cooldown,
        "shield_duration": shield_duration,
        "aiming_mode": app_ctx.config.aim_mode,
        "current_state": current_state,
        "enable_screen_flash": getattr(app_ctx.config, "enable_screen_flash", True),
        "screen_flash_duration": getattr(app_ctx.config, "screen_flash_duration", 0.25),
        "screen_flash_max_alpha": getattr(app_ctx.config, "screen_flash_max_alpha", 100),
        "enable_wave_banner": getattr(app_ctx.config, "enable_wave_banner", True),
    }
