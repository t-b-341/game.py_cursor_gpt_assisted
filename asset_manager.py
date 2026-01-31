"""
Centralized asset loading and caching.

Resolves paths under assets/ (images, sfx, music, fonts, data), loads and caches
pygame surfaces, sounds, and fonts. Use get_image(), get_sound(), get_font() instead
of scattering pygame.image.load / mixer.Sound / font.Font across the codebase.

Missing assets are handled gracefully: a clear message is printed and a fallback
is returned when possible (e.g. SysFont for fonts, a tiny placeholder surface for images).

Supports async preloading via background threads to eliminate first-use stutter.
"""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path
from typing import Any, Optional, Callable

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

# Async loading infrastructure
_preload_executor: Optional[ThreadPoolExecutor] = None
_preload_lock = threading.Lock()
_preload_futures: list[Future] = []
_preload_progress: dict[str, str] = {}  # asset_name -> status


def _get_preload_executor() -> ThreadPoolExecutor:
    """Get or create the preload thread pool."""
    global _preload_executor
    with _preload_lock:
        if _preload_executor is None:
            _preload_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="preload")
        return _preload_executor


def shutdown_preload_executor() -> None:
    """Shutdown the preload thread pool."""
    global _preload_executor
    with _preload_lock:
        if _preload_executor is not None:
            _preload_executor.shutdown(wait=False)
            _preload_executor = None


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


# =============================================================================
# ASYNC PRELOADING
# =============================================================================

def get_sound_async(name: str) -> Future[Optional[pygame.mixer.Sound]]:
    """Load a sound asynchronously. Returns a Future.
    
    Usage:
        future = get_sound_async("explosion")
        # Later:
        sound = future.result()  # Blocks until loaded
        # Or check without blocking:
        if future.done():
            sound = future.result()
    """
    executor = _get_preload_executor()
    return executor.submit(get_sound, name)


def preload_sounds(names: list[str], on_complete: Optional[Callable[[], None]] = None) -> None:
    """Preload multiple sounds in background threads.
    
    Args:
        names: List of sound names to preload
        on_complete: Optional callback when all sounds are loaded
    """
    global _preload_futures
    
    executor = _get_preload_executor()
    futures = []
    
    for name in names:
        if name not in _sound_cache:
            _preload_progress[name] = "loading"
            future = executor.submit(_preload_sound_task, name)
            futures.append(future)
    
    _preload_futures.extend(futures)
    
    if on_complete and futures:
        def wait_and_callback():
            for f in futures:
                try:
                    f.result()
                except Exception:
                    pass
            on_complete()
        executor.submit(wait_and_callback)


def _preload_sound_task(name: str) -> None:
    """Background task to preload a sound."""
    try:
        get_sound(name)
        _preload_progress[name] = "done"
    except Exception as e:
        _preload_progress[name] = f"error: {e}"


def preload_images(names: list[str], on_complete: Optional[Callable[[], None]] = None) -> None:
    """Preload multiple images in background threads.
    
    Note: pygame.image.load must be called from main thread after pygame.init().
    This queues the file reads but final Surface creation happens on main thread.
    """
    global _preload_futures
    
    executor = _get_preload_executor()
    futures = []
    
    for name in names:
        key = f"{name}_True"
        if key not in _image_cache:
            _preload_progress[name] = "loading"
            future = executor.submit(_preload_image_task, name)
            futures.append(future)
    
    _preload_futures.extend(futures)
    
    if on_complete and futures:
        def wait_and_callback():
            for f in futures:
                try:
                    f.result()
                except Exception:
                    pass
            on_complete()
        executor.submit(wait_and_callback)


def _preload_image_task(name: str) -> None:
    """Background task to preload an image."""
    try:
        get_image(name)
        _preload_progress[name] = "done"
    except Exception as e:
        _preload_progress[name] = f"error: {e}"


def preload_all_sfx(on_complete: Optional[Callable[[], None]] = None) -> None:
    """Preload all sound effects from assets/sfx/ and Game Sound FX/ directories."""
    sounds_to_load = []
    
    # Collect all sound files
    for sfx_dir in [_SFX_DIR, _GAME_SFX_DIR]:
        if sfx_dir.exists():
            for path in sfx_dir.iterdir():
                if path.suffix.lower() in (".wav", ".ogg"):
                    sounds_to_load.append(path.stem)
    
    preload_sounds(sounds_to_load, on_complete)


def preload_all_images(on_complete: Optional[Callable[[], None]] = None) -> None:
    """Preload all images from assets/images/ directory."""
    images_to_load = []
    
    if _IMAGES_DIR.exists():
        for path in _IMAGES_DIR.iterdir():
            if path.suffix.lower() in (".png", ".jpg", ".jpeg"):
                images_to_load.append(path.stem)
    
    preload_images(images_to_load, on_complete)


def get_preload_progress() -> tuple[int, int]:
    """Get preloading progress as (completed, total)."""
    total = len(_preload_progress)
    completed = sum(1 for status in _preload_progress.values() if status == "done")
    return completed, total


def is_preloading() -> bool:
    """Check if preloading is still in progress."""
    return any(not f.done() for f in _preload_futures)


def wait_for_preload(timeout: Optional[float] = None) -> bool:
    """Wait for all preloading to complete. Returns True if all completed."""
    from concurrent.futures import wait, ALL_COMPLETED
    if not _preload_futures:
        return True
    done, not_done = wait(_preload_futures, timeout=timeout, return_when=ALL_COMPLETED)
    return len(not_done) == 0
