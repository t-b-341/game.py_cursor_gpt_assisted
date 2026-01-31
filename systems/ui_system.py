"""UI system - backward compatibility import.

The UI system has been split into the systems/ui/ package for organization.
This file provides backward compatibility for existing imports.
"""
# Re-export from the new package location
from .ui import render, render_hud, render_overlays

__all__ = ["render", "render_hud", "render_overlays"]
