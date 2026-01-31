"""Shader rendering package - GPU and CPU visual effects.

This package handles shader-based rendering:
- GPU shaders via OpenGL (when available)
- CPU fallback effects
- Shader pipeline management

Main entry point is render_gameplay_with_optional_shaders().
"""

from .pipeline import (
    render_gameplay_with_optional_shaders,
    render_gameplay_frame_to_surface,
    apply_shader_settings_to_pipeline,
)

__all__ = [
    "render_gameplay_with_optional_shaders",
    "render_gameplay_frame_to_surface",
    "apply_shader_settings_to_pipeline",
]
