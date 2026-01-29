"""
Centralized audio: SFX and music via play_sfx(), play_music(), stop_music().

Uses asset_manager for loading (assets/sfx/, assets/music/). Volume and mute
are stored here and can be synced from GameConfig; all playback respects them.
Call init_mixer() after pygame.init() if you want explicit mixer settings.
"""
from __future__ import annotations

from typing import Any, Optional

import pygame

# Import after pygame is inited (callers do pygame.init() before first play)
def _get_asset_manager():
    from asset_manager import get_sound, get_music_path
    return get_sound, get_music_path

# Volume and mute state (0.0..1.0; used for all playback until updated)
_sfx_volume: float = 1.0
_music_volume: float = 1.0
_mute_sfx: bool = False
_mute_music: bool = False


def init_mixer(frequency: int = 44100, size: int = -16, channels: int = 2, buffer: int = 512) -> bool:
    """
    Initialize pygame.mixer with the given settings. Call after pygame.init().
    Returns True if init succeeded. If mixer was already inited, no-op and returns True.
    """
    if pygame.mixer.get_init():
        return True
    try:
        pygame.mixer.init(frequency, size, channels, buffer)
        return True
    except pygame.error:
        return False


def set_sfx_volume(value: float) -> None:
    """Set volume for all SFX (0.0..1.0). Applied to future play_sfx() calls."""
    global _sfx_volume
    _sfx_volume = max(0.0, min(1.0, float(value)))


def set_music_volume(value: float) -> None:
    """Set volume for music (0.0..1.0). Applied immediately to music channel and future play_music()."""
    global _music_volume
    _music_volume = max(0.0, min(1.0, float(value)))
    if pygame.mixer.get_init():
        v = 0.0 if _mute_music else _music_volume
        pygame.mixer.music.set_volume(v)


def set_muted(*, sfx: Optional[bool] = None, music: Optional[bool] = None) -> None:
    """Mute or unmute SFX and/or music. Omitted argument is left unchanged."""
    global _mute_sfx, _mute_music
    if sfx is not None:
        _mute_sfx = bool(sfx)
    if music is not None:
        _mute_music = bool(music)
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(0.0 if _mute_music else _music_volume)


def unmute_all() -> None:
    """Unmute both SFX and music."""
    set_muted(sfx=False, music=False)


def get_sfx_volume() -> float:
    return _sfx_volume


def get_music_volume() -> float:
    return _music_volume


def is_muted_sfx() -> bool:
    return _mute_sfx


def is_muted_music() -> bool:
    return _mute_music


def sync_from_config(config: Any) -> None:
    """Apply config.sfx_volume, config.music_volume, config.mute_sfx, config.mute_music if present."""
    if hasattr(config, "sfx_volume"):
        set_sfx_volume(config.sfx_volume)
    if hasattr(config, "music_volume"):
        set_music_volume(config.music_volume)
    if hasattr(config, "mute_sfx"):
        set_muted(sfx=config.mute_sfx)
    if hasattr(config, "mute_music"):
        set_muted(music=config.mute_music)


def play_sfx(name: str, debug: bool = False) -> bool:
    """
    Play a sound effect from assets/sfx/ or Game Sound FX/ by name. Respects SFX volume and mute.
    Returns True if playback started, False if sound missing or muted.
    """
    if _mute_sfx:
        if debug:
            print(f"[audio] SFX muted, skipping: {name}")
        return False
    get_sound, _ = _get_asset_manager()
    snd = get_sound(name)
    if snd is None:
        if debug:
            print(f"[audio] Sound not found: {name}")
        return False
    snd.set_volume(_sfx_volume)
    snd.play()
    if debug:
        print(f"[audio] Playing: {name} at volume {_sfx_volume}")
    return True


def play_music(name: str, loop: bool = True) -> bool:
    """
    Play a music track from assets/music/ by name. Respects music volume and mute.
    loop=True: play indefinitely; loop=False: play once.
    Returns True if playback started, False if file missing or mixer not ready.
    """
    if not pygame.mixer.get_init():
        return False
    _, get_music_path = _get_asset_manager()
    path = get_music_path(name)
    if not path:
        return False
    try:
        pygame.mixer.music.load(path)
        v = 0.0 if _mute_music else _music_volume
        pygame.mixer.music.set_volume(v)
        pygame.mixer.music.play(-1 if loop else 0)
        return True
    except pygame.error:
        return False


def stop_music() -> None:
    """Stop the currently playing music track."""
    if pygame.mixer.get_init():
        pygame.mixer.music.stop()
