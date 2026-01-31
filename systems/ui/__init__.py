"""UI system package - HUD rendering, overlays, damage numbers, etc.

This package handles all UI rendering during gameplay:
- HUD (health bars, score, weapon indicators)
- Overlays (wave banners, warnings)
- Damage numbers
- FPS graph and performance overlay

The main entry point is render() which orchestrates all UI drawing.
"""

from .core import (
    render,
    render_hud,
    render_overlays,
)

__all__ = [
    "render",
    "render_hud", 
    "render_overlays",
]
