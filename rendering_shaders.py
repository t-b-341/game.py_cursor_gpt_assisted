"""Shader rendering - backward compatibility import.

The shader rendering has been moved to rendering/shaders/ package for organization.
This file provides backward compatibility for existing imports.
"""
# Re-export from the new package location
from rendering.shaders.pipeline import (
    render_gameplay_with_optional_shaders,
    render_gameplay_frame_to_surface,
    apply_shader_settings_to_pipeline,
    _gpu_debug_count,
)

__all__ = [
    "render_gameplay_with_optional_shaders",
    "render_gameplay_frame_to_surface",
    "apply_shader_settings_to_pipeline",
    "_gpu_debug_count",
]
