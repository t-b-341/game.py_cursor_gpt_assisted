"""
Rendering: drawing utilities for textures, projectiles, health bars, and text.

RenderContext holds screen, fonts, and layout; render functions accept it to avoid
repeated lookups. Build from AppContext via RenderContext.from_app_ctx(app_ctx).

Re-exports from context, world, hud, overlays, and menu_helpers so existing imports still work:
  from rendering import RenderContext, draw_centered_text, render_background, ...
"""
from __future__ import annotations

from .context import RenderContext, build_gameplay_ctx, get_camera_offset
from .hud import draw_centered_text, draw_health_bar, render_hud_text
from .menu_helpers import (
    get_menu_option_rects,
    render_menu_title,
    render_menu_options,
    handle_menu_navigation,
    render_confirmation_dialog,
    clear_menu_cache,
)
from .overlays import render_debug_overlay
from .text_cache import (
    get_text_surface,
    get_text_surface_with_bg,
    clear_text_cache,
    get_cache_stats,
    render_text_centered,
    render_text_right,
)
from .world import (
    render_background,
    render_entities,
    render_gameplay,
    render_projectiles,
)

__all__ = [
    "RenderContext",
    "build_gameplay_ctx",
    "get_camera_offset",
    "draw_centered_text",
    "draw_health_bar",
    "render_hud_text",
    "render_background",
    "render_entities",
    "render_projectiles",
    "render_gameplay",
    "render_debug_overlay",
    # Menu helpers
    "get_menu_option_rects",
    "render_menu_title",
    "render_menu_options",
    "handle_menu_navigation",
    "render_confirmation_dialog",
    "clear_menu_cache",
    # Text caching
    "get_text_surface",
    "get_text_surface_with_bg",
    "clear_text_cache",
    "get_cache_stats",
    "render_text_centered",
    "render_text_right",
]
