"""
Overlays: debug HUD, and any future flash/warnings/banners drawn on top.
"""
from __future__ import annotations

import pygame

from .context import RenderContext
from .text_cache import get_text_surface


def render_debug_overlay(
    render_ctx: RenderContext,
    game_state,
    *,
    lines: list[str] | None = None,
    extra_lines: list[str] | None = None,
) -> None:
    """
    Draw a small debug HUD in a corner of the screen.
    If 'lines' is provided, use those as extra lines; otherwise derive a few defaults from game_state.
    If 'extra_lines' is provided, append them to the final line list.
    This function does NOT decide when to be called; caller controls that.
    """
    DEBUG_BG_COLOR = (20, 20, 30)
    DEBUG_TEXT_COLOR = (255, 255, 255)
    PAD = 6
    LINE_SPACING = 5

    if lines is None:
        lines = [
            f"wave: {getattr(game_state, 'wave_number', 0)}",
            f"enemies: {len(getattr(game_state, 'enemies', []))}",
            f"player_hp: {getattr(game_state, 'player_hp', 0)}/{getattr(game_state, 'player_max_hp', 1)}",
            f"lives: {getattr(game_state, 'lives', 0)}",
        ]
    if extra_lines is not None:
        lines = list(lines) + list(extra_lines)

    font = render_ctx.small_font
    x, y = PAD, PAD
    
    # Pre-render all text surfaces using cache
    text_surfaces = [get_text_surface(font, s, DEBUG_TEXT_COLOR) for s in lines]
    max_w = max(surf.get_width() for surf in text_surfaces) if text_surfaces else 0
    
    line_height = font.get_height() + LINE_SPACING
    total_h = len(lines) * line_height - LINE_SPACING + 2 * PAD
    total_w = max_w + 2 * PAD

    bg = pygame.Surface((total_w, total_h))
    bg.fill(DEBUG_BG_COLOR)
    bg.set_alpha(200)
    render_ctx.screen.blit(bg, (x, y))

    ty = y + PAD
    for surf in text_surfaces:
        render_ctx.screen.blit(surf, (x + PAD, ty))
        ty += line_height
