"""
Centralized asset loading and caching.

Resolves paths under assets/ (images, sfx, music, fonts, data), loads and caches
pygame surfaces, sounds, and fonts. Use get_image(), get_sound(), get_font() instead
of scattering pygame.image.load / mixer.Sound / font.Font across the codebase.

Missing assets are handled gracefully: a clear message is printed and a fallback
is returned when possible (e.g. SysFont for fonts, a tiny placeholder surface for images).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import pygame

# Base path: project root / assets (parent of this file's directory)
_PROJECT_ROOT = Path(__file__).resolve().parent
_ASSETS_DIR = _PROJECT_ROOT / "assets"
_IMAGES_DIR = _ASSETS_DIR / "images"
_SFX_DIR = _ASSETS_DIR / "sfx"
_GAME_SFX_DIR = _PROJECT_ROOT / "Game Sound FX"  # Additional SFX folder
_MUSIC_DIR = _ASSETS_DIR / "music"
_FONTS_DIR = _ASSETS_DIR / "fonts"
_DATA_DIR = _ASSETS_DIR / "data"

# Caches: key -> loaded resource
_image_cache: dict[str, pygame.Surface] = {}
_sound_cache: dict[str, pygame.mixer.Sound] = {}
_font_cache: dict[tuple[str, int], pygame.font.Font] = {}

# Track missing assets to avoid spamming logs
_missing_reported: set[str] = set()


def _report_missing(kind: str, path: Path, detail: str = "") -> None:
    key = f"{kind}:{path}"
    if key in _missing_reported:
        return
    _missing_reported.add(key)
    msg = f"[asset_manager] Missing {kind}: {path}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def _resolve_subpath(base: Path, name: str, extensions: tuple[str, ...]) -> Optional[Path]:
    """Return path if name (with optional extension) exists under base; else None."""
    p = base / name
    if p.exists():
        return p
    if os.path.splitext(name)[1]:
        return None
    for ext in extensions:
        q = base / f"{name}{ext}"
        if q.exists():
            return q
    return None


def get_assets_dir() -> Path:
    """Return the base assets directory (project_root/assets)."""
    return _ASSETS_DIR


def get_image(name: str, convert_alpha: bool = True) -> pygame.Surface:
    """
    Load and cache an image from assets/images/.
    name: filename without path (e.g. "player" -> assets/images/player.png).
    Tries .png, .jpg, .jpeg. Uses convert_alpha() by default for transparency.
    On error: prints clear message and returns a small placeholder surface.
    """
    key = f"{name}_{convert_alpha}"
    if key in _image_cache:
        return _image_cache[key]

    extensions = (".png", ".jpg", ".jpeg")
    path = _resolve_subpath(_IMAGES_DIR, name, extensions)
    if path is None:
        _report_missing("image", _IMAGES_DIR / name, "tried " + ", ".join(extensions))
        # Placeholder: small gray surface so callers don't crash
        surf = pygame.Surface((8, 8))
        surf.fill((80, 80, 80))
        _image_cache[key] = surf
        return surf

    try:
        surf = pygame.image.load(str(path))
        if convert_alpha:
            surf = surf.convert_alpha()
        else:
            surf = surf.convert()
        _image_cache[key] = surf
        return surf
    except Exception as e:
        _report_missing("image", path, str(e))
        surf = pygame.Surface((8, 8))
        surf.fill((80, 80, 80))
        _image_cache[key] = surf
        return surf


def get_sound(name: str) -> Optional[pygame.mixer.Sound]:
    """
    Load and cache a sound from assets/sfx/ or Game Sound FX/.
    name: filename without path (e.g. "enemy_death" -> assets/sfx/enemy_death.wav).
    Tries .wav, .ogg. Returns None if missing or if mixer not initialized.
    """
    if name in _sound_cache:
        return _sound_cache[name]

    if not pygame.mixer.get_init():
        return None

    extensions = (".wav", ".ogg")
    # Try assets/sfx/ first, then Game Sound FX/
    path = _resolve_subpath(_SFX_DIR, name, extensions)
    if path is None:
        path = _resolve_subpath(_GAME_SFX_DIR, name, extensions)
    if path is None:
        _report_missing("sound", _SFX_DIR / name, "tried " + ", ".join(extensions))
        return None

    try:
        snd = pygame.mixer.Sound(str(path))
        _sound_cache[name] = snd
        return snd
    except Exception as e:
        _report_missing("sound", path, str(e))
        return None


def get_music_path(name: str) -> Optional[str]:
    """
    Return the full path to a music file in assets/music/ for use with pygame.mixer.music.load().
    Tries .ogg, .mp3, .wav. Returns None if not found.
    """
    extensions = (".ogg", ".mp3", ".wav")
    path = _resolve_subpath(_MUSIC_DIR, name, extensions)
    if path is None:
        _report_missing("music", _MUSIC_DIR / name, "tried " + ", ".join(extensions))
        return None
    return str(path)


def get_font(name: str, size: int) -> pygame.font.Font:
    """
    Load and cache a font from assets/fonts/, or fall back to pygame.font.SysFont(None, size).
    name: logical name or filename (e.g. "main" -> assets/fonts/main.ttf, or "main.ttf").
    size: point size. If no font file exists, returns SysFont(None, size) and caches it
    under ("sys", size) to avoid repeated lookups for the same size.
    """
    cache_key = (name, size)
    if cache_key in _font_cache:
        return _font_cache[cache_key]

    extensions = (".ttf", ".otf")
    path = _resolve_subpath(_FONTS_DIR, name, extensions)
    if path is not None:
        try:
            f = pygame.font.Font(str(path), size)
            _font_cache[cache_key] = f
            return f
        except Exception as e:
            _report_missing("font", path, str(e))

    # Fallback: system font
    try:
        f = pygame.font.SysFont(None, size)
        _font_cache[cache_key] = f
        return f
    except Exception as e:
        _report_missing("font", _FONTS_DIR / name, f"fallback SysFont failed: {e}")
        # Last resort: default font at size 28 if that works
        try:
            f = pygame.font.SysFont(None, 28)
            _font_cache[cache_key] = f
            return f
        except Exception:
            raise RuntimeError("No font could be loaded") from e


def get_data_path(name: str, default_extension: str = ".json") -> Optional[Path]:
    """
    Return Path to a file in assets/data/, or None if not found.
    Use for JSON/config files. Doesn't load or cache; caller reads the file.
    """
    p = _DATA_DIR / name
    if p.exists():
        return p
    if not os.path.splitext(name)[1]:
        p = _DATA_DIR / f"{name}{default_extension}"
        if p.exists():
            return p
    return None


def clear_caches() -> None:
    """Clear all loaded caches (e.g. when switching resolution or reloading assets)."""
    global _image_cache, _sound_cache, _font_cache, _missing_reported
    _image_cache.clear()
    _sound_cache.clear()
    _font_cache.clear()
    _missing_reported.clear()
