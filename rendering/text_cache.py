"""Text surface caching for rendering optimization.

Caches rendered text surfaces to avoid repeated font.render() calls.
Uses LRU eviction to bound memory usage.

Usage:
    from rendering.text_cache import get_text_surface, clear_text_cache
    
    # Render text (cached automatically)
    surface = get_text_surface(font, "Score: 1000", (255, 255, 255))
    screen.blit(surface, (10, 10))
    
    # For dynamic values, use format strings
    surface = get_text_surface(font, f"HP: {player_hp}", (255, 0, 0))
"""
from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    pass


# LRU cache with max size
_MAX_CACHE_SIZE = 500
_text_surface_cache: OrderedDict[tuple, pygame.Surface] = OrderedDict()

# Stats for debugging
_cache_hits = 0
_cache_misses = 0


def get_text_surface(
    font: pygame.font.Font,
    text: str,
    color: tuple[int, int, int],
    antialias: bool = True,
) -> pygame.Surface:
    """Get a cached text surface, rendering only if not in cache.
    
    Args:
        font: Pygame font to use
        text: Text string to render
        color: RGB color tuple
        antialias: Whether to use antialiasing (default True)
    
    Returns:
        Cached or newly rendered text surface
    """
    global _cache_hits, _cache_misses
    
    # Cache key includes font id to handle multiple fonts
    cache_key = (id(font), text, color, antialias)
    
    if cache_key in _text_surface_cache:
        _cache_hits += 1
        # Move to end (most recently used)
        _text_surface_cache.move_to_end(cache_key)
        return _text_surface_cache[cache_key]
    
    _cache_misses += 1
    
    # Render new surface
    surface = font.render(text, antialias, color)
    
    # Add to cache with LRU eviction
    _text_surface_cache[cache_key] = surface
    while len(_text_surface_cache) > _MAX_CACHE_SIZE:
        _text_surface_cache.popitem(last=False)  # Remove oldest
    
    return surface


def get_text_surface_with_bg(
    font: pygame.font.Font,
    text: str,
    color: tuple[int, int, int],
    bg_color: tuple[int, int, int] | None = None,
    antialias: bool = True,
) -> pygame.Surface:
    """Get a cached text surface with optional background color.
    
    Args:
        font: Pygame font to use
        text: Text string to render
        color: RGB color tuple for text
        bg_color: Optional RGB color for background
        antialias: Whether to use antialiasing
    
    Returns:
        Cached or newly rendered text surface
    """
    global _cache_hits, _cache_misses
    
    cache_key = (id(font), text, color, bg_color, antialias, "with_bg")
    
    if cache_key in _text_surface_cache:
        _cache_hits += 1
        _text_surface_cache.move_to_end(cache_key)
        return _text_surface_cache[cache_key]
    
    _cache_misses += 1
    
    if bg_color is not None:
        surface = font.render(text, antialias, color, bg_color)
    else:
        surface = font.render(text, antialias, color)
    
    _text_surface_cache[cache_key] = surface
    while len(_text_surface_cache) > _MAX_CACHE_SIZE:
        _text_surface_cache.popitem(last=False)
    
    return surface


def clear_text_cache() -> None:
    """Clear the entire text cache."""
    _text_surface_cache.clear()


def get_cache_stats() -> dict:
    """Get cache statistics for debugging."""
    return {
        "size": len(_text_surface_cache),
        "max_size": _MAX_CACHE_SIZE,
        "hits": _cache_hits,
        "misses": _cache_misses,
        "hit_rate": _cache_hits / (_cache_hits + _cache_misses) if (_cache_hits + _cache_misses) > 0 else 0.0,
    }


def reset_cache_stats() -> None:
    """Reset cache statistics."""
    global _cache_hits, _cache_misses
    _cache_hits = 0
    _cache_misses = 0


# Convenience function for common patterns
def render_text_centered(
    screen: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    color: tuple[int, int, int],
    center_x: int,
    y: int,
) -> pygame.Rect:
    """Render cached text centered at x position.
    
    Returns:
        The blit rect for the rendered text
    """
    surface = get_text_surface(font, text, color)
    rect = surface.get_rect(centerx=center_x, y=y)
    screen.blit(surface, rect)
    return rect


def render_text_right(
    screen: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    color: tuple[int, int, int],
    right_x: int,
    y: int,
) -> pygame.Rect:
    """Render cached text right-aligned at x position.
    
    Returns:
        The blit rect for the rendered text
    """
    surface = get_text_surface(font, text, color)
    rect = surface.get_rect(right=right_x, y=y)
    screen.blit(surface, rect)
    return rect
