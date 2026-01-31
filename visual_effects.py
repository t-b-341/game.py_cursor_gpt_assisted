"""Lightweight CPU-based visual effects for menus and gameplay.

Effect functions take a surface, optionally parameters, and modify it in place (or return
a new surface). They are designed to be chained. Used by apply_menu_effects,
apply_pause_effects, and apply_gameplay_effects, which are called from the main loop
and from rendering_shaders.
"""
from __future__ import annotations

import math
import time
from typing import Any

import pygame

# -----------------------------------------------------------------------------
# Surface caching for performance (avoid per-frame allocations)
# -----------------------------------------------------------------------------

_surface_cache: dict[tuple, pygame.Surface] = {}
_CACHE_MAX_SIZE = 32  # Limit cache size to avoid memory bloat


def _get_cached_surface(key: tuple, w: int, h: int, alpha: bool = True) -> pygame.Surface:
    """Get or create a cached surface. Clears if cache too large."""
    global _surface_cache
    if len(_surface_cache) > _CACHE_MAX_SIZE:
        _surface_cache.clear()
    if key not in _surface_cache:
        flags = pygame.SRCALPHA if alpha else 0
        _surface_cache[key] = pygame.Surface((w, h), flags=flags)
    return _surface_cache[key]


# -----------------------------------------------------------------------------
# Reusable effect primitives (surface in, mutate or return)
# -----------------------------------------------------------------------------


def apply_scanlines(surface: pygame.Surface, strength: float = 0.06) -> None:
    """CRT-style horizontal scanlines. Modifies surface in place.
    strength: 0 = none, ~0.1 = subtle, 0.2+ = pronounced.
    """
    if strength <= 0:
        return
    w, h = surface.get_size()
    line_height = max(1, min(4, h // 270))
    alpha = int(min(255, 255 * strength))
    # Cache key: (effect_type, dimensions, line_height, alpha)
    cache_key = ("scanlines", w, h, line_height, alpha)
    overlay = _get_cached_surface(cache_key, w, h, alpha=True)
    # Only regenerate if not already built (check a pixel)
    if overlay.get_at((0, 0))[3] != alpha:
        overlay.fill((0, 0, 0, 0))  # Clear
        for y in range(0, h, line_height * 2):
            overlay.fill((0, 0, 0, alpha), (0, y, w, line_height))
    surface.blit(overlay, (0, 0))


def apply_vignette(surface: pygame.Surface, strength: float = 0.35, radius: float = 0.75) -> None:
    """Darken edges (vignette). Modifies surface in place.
    strength: max alpha at corners (0..1). radius: fractional distance from center where falloff starts.
    """
    if strength <= 0:
        return
    w, h = surface.get_size()
    # Cache key includes strength and radius (rounded for reasonable bucketing)
    strength_key = int(strength * 100)
    radius_key = int(radius * 100)
    cache_key = ("vignette", w, h, strength_key, radius_key)
    
    if cache_key in _surface_cache:
        surface.blit(_surface_cache[cache_key], (0, 0))
        return
    
    # Build vignette mask (expensive - only done once per size/params combo)
    m = 64
    mask = pygame.Surface((m, m), flags=pygame.SRCALPHA)
    cx, cy = (m - 1) / 2.0, (m - 1) / 2.0
    max_d = math.sqrt(cx * cx + cy * cy)
    for i in range(m):
        for j in range(m):
            d = math.sqrt((i - cx) ** 2 + (j - cy) ** 2) / max_d
            # smoothstep: darken when d > radius
            t = (d - radius) / (1.0 - radius) if radius < 1.0 else 0.0
            t = max(0.0, min(1.0, t))
            a = int(255 * strength * (1.0 - (1.0 - t) * (1.0 - t)))
            mask.set_at((i, j), (0, 0, 0, a))
    scaled = pygame.transform.smoothscale(mask, (w, h))
    
    # Cache the scaled vignette
    if len(_surface_cache) > _CACHE_MAX_SIZE:
        _surface_cache.clear()
    _surface_cache[cache_key] = scaled
    surface.blit(scaled, (0, 0))


def apply_color_tint(surface: pygame.Surface, r: int, g: int, b: int, alpha: int) -> None:
    """Add a flat color tint overlay. Modifies surface in place."""
    if alpha <= 0:
        return
    w, h = surface.get_size()
    alpha = min(255, alpha)
    cache_key = ("tint", w, h, r, g, b, alpha)
    
    if cache_key in _surface_cache:
        surface.blit(_surface_cache[cache_key], (0, 0))
        return
    
    overlay = pygame.Surface((w, h), flags=pygame.SRCALPHA)
    overlay.fill((r, g, b, alpha))
    
    if len(_surface_cache) > _CACHE_MAX_SIZE:
        _surface_cache.clear()
    _surface_cache[cache_key] = overlay
    surface.blit(overlay, (0, 0))


def get_pulse_factor(rate: float = 2.0) -> float:
    """Returns 0..1 for a gentle breathing pulse. Use when drawing menu selection highlight."""
    t = time.perf_counter() * rate
    return 0.5 + 0.5 * math.sin(t)


# -----------------------------------------------------------------------------
# Profile-driven effect stacks (used by apply_*_effects)
# -----------------------------------------------------------------------------

def _apply_menu_profile(surface: pygame.Surface, profile: str) -> None:
    """Apply effect stack for main menu / title by profile name."""
    if profile == "crt":
        apply_scanlines(surface, 0.08)
        apply_color_tint(surface, 20, 25, 50, 25)  # cool blue
    elif profile == "soft_glow":
        apply_color_tint(surface, 60, 35, 20, 30)  # warm orange
        apply_vignette(surface, 0.25, 0.7)


def _apply_pause_profile(surface: pygame.Surface) -> None:
    """Subtle vignette + cool tint to differentiate pause from gameplay."""
    apply_vignette(surface, 0.2, 0.8)
    apply_color_tint(surface, 15, 20, 40, 20)


def _apply_gameplay_profile(surface: pygame.Surface, profile: str) -> None:
    """Apply effect stack for gameplay by profile name. Kept subtle."""
    if profile == "subtle_vignette":
        apply_vignette(surface, 0.2, 0.75)
    elif profile == "crt_light":
        apply_vignette(surface, 0.18, 0.78)
        apply_scanlines(surface, 0.04)


def _apply_damage_wobble_blit(
    source: pygame.Surface, dest: pygame.Surface, wobble_t: float, intensity: float = 2.0
) -> None:
    """Blit source onto dest with a slight offset based on remaining wobble time. Used when damage_wobble_timer > 0."""
    if wobble_t <= 0 or intensity <= 0:
        dest.blit(source, (0, 0))
        return
    # Short sine-based jitter; decays with wobble_t
    s = intensity * min(1.0, wobble_t / 0.15)
    dx = int(s * (1.5 * math.sin(wobble_t * 40)))
    dy = int(s * (1.2 * math.sin(wobble_t * 37 + 1)))
    dest.blit(source, (dx, dy))


# -----------------------------------------------------------------------------
# Public API: called from game loop and rendering_shaders
# -----------------------------------------------------------------------------

def _get_config(ctx: Any) -> Any:
    """Get config from app context or from dict with 'app_ctx'."""
    if ctx is None:
        return None
    if isinstance(ctx, dict):
        app = ctx.get("app_ctx")
        return getattr(app, "config", None) if app else None
    return getattr(ctx, "config", None)


def apply_menu_effects(surface: pygame.Surface, ctx: Any) -> None:
    """Apply menu/title effect stack. No-op if disabled or profile is 'none'.
    ctx: app context or dict with app_ctx.config (enable_menu_shaders, menu_effect_profile).
    """
    try:
        config = _get_config(ctx)
        if config is None or not getattr(config, "enable_menu_shaders", False):
            return
        profile = getattr(config, "menu_effect_profile", "none") or "none"
        if profile not in ("crt", "soft_glow"):
            return
        _apply_menu_profile(surface, profile)
    except Exception:
        pass


def apply_pause_effects(surface: pygame.Surface, ctx: Any) -> None:
    """Apply pause-screen effect stack. No-op if menu shaders disabled.
    ctx: app context or dict with app_ctx.config.
    """
    try:
        config = _get_config(ctx)
        if config is None or not getattr(config, "enable_menu_shaders", False):
            return
        _apply_pause_profile(surface)
    except Exception:
        pass


def apply_gameplay_effects(
    surface: pygame.Surface, ctx: Any, game_state: Any = None
) -> None:
    """Apply gameplay effect stack (vignette/scanlines by profile). Does not do damage wobble;
    that is done by the caller when blitting to screen if enable_damage_wobble and timer > 0.
    ctx: has config (enable_gameplay_shaders, gameplay_effect_profile).
    """
    try:
        config = _get_config(ctx)
        if config is None or not getattr(config, "enable_gameplay_shaders", False):
            return
        profile = getattr(config, "gameplay_effect_profile", "none") or "none"
        if profile not in ("subtle_vignette", "crt_light"):
            return
        _apply_gameplay_profile(surface, profile)
    except Exception:
        pass


def apply_gameplay_final_blit(
    source: pygame.Surface, dest: pygame.Surface, ctx: Any, game_state: Any = None
) -> None:
    """Blit gameplay frame to screen, applying damage wobble when enabled and timer > 0."""
    wobble_t = getattr(game_state, "damage_wobble_timer", 0.0) or 0.0 if game_state else 0.0
    config = _get_config(ctx)
    use_wobble = config is not None and getattr(config, "enable_damage_wobble", False) and wobble_t > 0
    if use_wobble:
        _apply_damage_wobble_blit(source, dest, wobble_t, intensity=2.0)
    else:
        dest.blit(source, (0, 0))
