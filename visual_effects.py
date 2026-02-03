"""Lightweight CPU-based visual effects for menus and gameplay.

Effect functions take a surface, optionally parameters, and modify it in place (or return
a new surface). They are designed to be chained. Used by apply_menu_effects,
apply_pause_effects, and apply_gameplay_effects, which are called from the main loop
and from rendering_shaders. All effects are CPU-only (no shaders).
"""
from __future__ import annotations

import math
import random
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


def ease_out_quad(t: float) -> float:
    """Easing: 0 at 0, 1 at 1, smooth deceleration at end. Use for decay (e.g. damage wobble)."""
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) * (1.0 - t)


def apply_film_grain(surface: pygame.Surface, strength: float = 0.12, seed: int = 0) -> None:
    """Add subtle film grain (noise) overlay. Modifies surface in place.
    strength: 0 = none, ~0.1 = subtle, 0.2+ = pronounced.
    Uses sparse sampling for performance (every 2px).
    """
    if strength <= 0:
        return
    w, h = surface.get_size()
    rng = random.Random(seed if seed else int(time.perf_counter() * 1000) % (2**31))
    step = 2
    for y in range(0, h, step):
        for x in range(0, w, step):
            v = rng.randint(0, 255)
            a = int(255 * strength * (0.5 + (v / 255.0 - 0.5)))
            if a <= 0:
                continue
            c = surface.get_at((x, y))
            d = (v - 128) * 2
            nr = max(0, min(255, c[0] + d))
            ng = max(0, min(255, c[1] + d))
            nb = max(0, min(255, c[2] + d))
            surface.set_at((x, y), (nr, ng, nb, c[3]))
    return


def apply_film_grain_fast(surface: pygame.Surface, strength: float = 0.08) -> None:
    """Faster film grain: overlay semi-transparent random pixels (sparse, no per-pixel get_at)."""
    if strength <= 0:
        return
    w, h = surface.get_size()
    n = (w * h) // 80
    rng = random.Random(int(time.perf_counter() * 1000) % (2**31))
    alpha = int(255 * strength)
    for _ in range(n):
        x = rng.randint(0, w - 1)
        y = rng.randint(0, h - 1)
        g = rng.randint(0, 255)
        surface.set_at((x, y), (g, g, g, alpha))
    return


def apply_low_hp_pulse(
    surface: pygame.Surface,
    hp_ratio: float,
    threshold: float = 0.35,
    strength: float = 0.25,
    rate: float = 4.0,
) -> None:
    """When hp_ratio <= threshold, pulse a red tint (danger feel). Modifies surface in place.
    hp_ratio: current_hp / max_hp (0..1). threshold: start pulsing below this. strength: max tint alpha.
    """
    if hp_ratio > threshold or strength <= 0:
        return
    t = time.perf_counter() * rate
    intensity = (1.0 - hp_ratio / threshold) * (0.5 + 0.5 * math.sin(t))
    a = int(255 * strength * intensity)
    if a <= 0:
        return
    w, h = surface.get_size()
    overlay = pygame.Surface((w, h), flags=pygame.SRCALPHA)
    overlay.fill((120, 0, 20, a))
    surface.blit(overlay, (0, 0))


def apply_radial_darken(
    surface: pygame.Surface, center_x: float, center_y: float, radius: float, strength: float = 0.4
) -> None:
    """Darken pixels outside a circular region (e.g. spotlight / tunnel). Modifies surface in place.
    center_x, center_y: 0..1 normalized. radius: 0..1. strength: max darkening at edges.
    """
    if strength <= 0 or radius <= 0:
        return
    w, h = surface.get_size()
    cx, cy = center_x * w, center_y * h
    # Build small mask and scale (cheap)
    m = 32
    mask = pygame.Surface((m, m), flags=pygame.SRCALPHA)
    for i in range(m):
        for j in range(m):
            ny, nx = j / (m - 1), i / (m - 1)
            dy = (ny - center_y) * h
            dx = (nx - center_x) * w
            d = math.sqrt(dx * dx + dy * dy) / (radius * max(w, h) * 0.5)
            t = max(0.0, min(1.0, (d - 0.8) / 0.2))
            a = int(255 * strength * (1.0 - (1.0 - t) * (1.0 - t)))
            mask.set_at((i, j), (0, 0, 0, a))
    scaled = pygame.transform.smoothscale(mask, (w, h))
    surface.blit(scaled, (0, 0))


def apply_swirl(
    surface: pygame.Surface,
    center_x: float = 0.5,
    center_y: float = 0.5,
    strength: float = 1.0,
    radius_ratio: float = 0.9,
    step: int | None = None,
) -> None:
    """Apply a polar twist (swirl) around a center. Modifies surface in place.
    center_x, center_y: 0..1 normalized. strength: twist in radians (0.5=subtle, 2=strong).
    radius_ratio: 0..1, fraction of half-diagonal where twist falls off to zero.
    step: 1=smooth and slower; 2+ = compute at lower res and scale up (faster).
    """
    if strength == 0 or radius_ratio <= 0:
        return
    w, h = surface.get_size()
    s = step if step is not None else max(2, min(w, h) // 80)
    # Work at reduced size when step > 1 for speed, then scale up for full coverage
    sw, sh = max(1, w // s), max(1, h // s)
    cx = center_x * (sw - 1)
    cy = center_y * (sh - 1)
    max_r = radius_ratio * math.sqrt(cx * cx + cy * cy)
    if max_r < 1:
        return
    # Source: scale down for sampling
    src = pygame.transform.smoothscale(surface, (sw, sh)) if (sw, sh) != (w, h) else surface.copy()
    out = pygame.Surface((sw, sh))
    out.blit(src, (0, 0))
    for y in range(sh):
        for x in range(sw):
            dx = x - cx
            dy = y - cy
            r = math.sqrt(dx * dx + dy * dy)
            if r < 1e-6:
                continue
            t = 1.0 - min(1.0, r / max_r)
            angle_offset = strength * t * t
            angle = math.atan2(dy, dx)
            new_angle = angle + angle_offset
            sx = int(cx + r * math.cos(new_angle))
            sy = int(cy + r * math.sin(new_angle))
            if 0 <= sx < sw and 0 <= sy < sh:
                out.set_at((x, y), src.get_at((sx, sy)))
    if (sw, sh) != (w, h):
        out = pygame.transform.smoothscale(out, (w, h))
    surface.blit(out, (0, 0))


# -----------------------------------------------------------------------------
# Profile-driven effect stacks (used by apply_*_effects)
# -----------------------------------------------------------------------------

def _apply_menu_profile(surface: pygame.Surface, profile: str) -> None:
    """Apply effect stack for main menu / title by profile name. All CPU-only."""
    if profile == "crt":
        apply_scanlines(surface, 0.08)
        apply_color_tint(surface, 20, 25, 50, 25)  # cool blue
    elif profile == "soft_glow":
        apply_color_tint(surface, 60, 35, 20, 30)  # warm orange
        apply_vignette(surface, 0.25, 0.7)
    elif profile == "grainy":
        apply_vignette(surface, 0.3, 0.7)
        apply_color_tint(surface, 25, 20, 30, 20)
        apply_film_grain_fast(surface, 0.07)
    elif profile == "swirly":
        apply_swirl(surface, 0.5, 0.5, strength=0.8, radius_ratio=0.85, step=3)
        apply_vignette(surface, 0.22, 0.78)


def _apply_pause_profile(surface: pygame.Surface) -> None:
    """Subtle vignette + cool tint to differentiate pause from gameplay."""
    apply_vignette(surface, 0.2, 0.8)
    apply_color_tint(surface, 15, 20, 40, 20)


def _apply_gameplay_profile(
    surface: pygame.Surface, profile: str, game_state: Any = None
) -> None:
    """Apply effect stack for gameplay by profile name. Kept subtle. All CPU-only."""
    if profile == "subtle_vignette":
        apply_vignette(surface, 0.2, 0.75)
    elif profile == "crt_light":
        apply_vignette(surface, 0.18, 0.78)
        apply_scanlines(surface, 0.04)
    elif profile == "film_grain":
        apply_vignette(surface, 0.18, 0.78)
        apply_film_grain_fast(surface, 0.06)
    elif profile == "atmospheric":
        apply_vignette(surface, 0.25, 0.72)
        apply_color_tint(surface, 15, 20, 35, 18)
        apply_film_grain_fast(surface, 0.04)
    if game_state is not None:
        hp = getattr(game_state, "player_hp", None)
        max_hp = getattr(game_state, "player_max_hp", None)
        if hp is not None and max_hp is not None and max_hp > 0:
            apply_low_hp_pulse(surface, hp / max_hp, threshold=0.35, strength=0.22, rate=4.0)


def _apply_damage_wobble_blit(
    source: pygame.Surface,
    dest: pygame.Surface,
    wobble_t: float,
    wobble_duration: float = 0.2,
    intensity: float = 2.0,
) -> None:
    """Blit source onto dest with a slight offset. Wobble decays smoothly (ease_out) over wobble_duration."""
    if wobble_t <= 0 or intensity <= 0:
        dest.blit(source, (0, 0))
        return
    # Eased decay: full intensity at start, smooth drop by end of duration
    if wobble_duration <= 0:
        decay = 0.0
    else:
        t_norm = min(1.0, wobble_t / wobble_duration)
        decay = ease_out_quad(1.0 - t_norm)
    s = intensity * decay
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
        if profile not in ("crt", "soft_glow", "grainy", "swirly"):
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
    """Apply gameplay effect stack (vignette, scanlines, film grain, low-HP pulse by profile).
    Does not do damage wobble; that is done by the caller when blitting to screen.
    All effects are CPU-only (no shaders). ctx: config (enable_gameplay_shaders, gameplay_effect_profile).
    """
    try:
        config = _get_config(ctx)
        if config is None or not getattr(config, "enable_gameplay_shaders", False):
            return
        profile = getattr(config, "gameplay_effect_profile", "none") or "none"
        if profile not in ("subtle_vignette", "crt_light", "film_grain", "atmospheric"):
            return
        _apply_gameplay_profile(surface, profile, game_state)
    except Exception:
        pass


def apply_gameplay_final_blit(
    source: pygame.Surface, dest: pygame.Surface, ctx: Any, game_state: Any = None
) -> None:
    """Blit gameplay frame to screen, applying damage wobble when enabled and timer > 0 (eased decay)."""
    wobble_t = getattr(game_state, "damage_wobble_timer", 0.0) or 0.0 if game_state else 0.0
    config = _get_config(ctx)
    use_wobble = config is not None and getattr(config, "enable_damage_wobble", False) and wobble_t > 0
    if use_wobble:
        _apply_damage_wobble_blit(source, dest, wobble_t, wobble_duration=0.2, intensity=2.0)
    else:
        dest.blit(source, (0, 0))
