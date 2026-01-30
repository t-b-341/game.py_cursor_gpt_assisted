"""
Central shader registry with categories and default uniforms.

This module defines SHADER_SPECS, which is the single source of truth for shader
metadata (name, category, default uniform values). UI and pipeline code should
use this registry instead of hardcoding shader uniforms and categories.

To add a new shader:
1. Create the shader .frag file in assets/shaders/
2. Add a ShaderSpec entry to SHADER_SPECS with appropriate category and defaults
3. The shader will automatically appear in ShaderTestScene and ShaderSettingsScreen
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class ShaderCategory(Enum):
    """
    Shader effect categories for organization.
    
    This enum describes semantic shader groups (CORE, ATMOSPHERE, etc.).
    It is used for UI grouping and metadata, not pipeline ordering.
    For pipeline ordering, see shader_effects.pipeline.ShaderCategory and
    pipeline_category_for_registry_category().
    """
    CORE = "core"
    ATMOSPHERE = "atmosphere"
    RETRO = "retro"
    COMBAT = "combat"
    WATER = "water"
    OUTLINES = "outlines"
    LIGHTING = "lighting"
    DEBUG = "debug"


@dataclass(frozen=True)
class ShaderSpec:
    """Specification for a shader effect."""
    name: str
    category: ShaderCategory
    default_uniforms: Dict[str, Any]


SHADER_SPECS: Dict[str, ShaderSpec] = {
    "vignette": ShaderSpec(
        name="vignette",
        category=ShaderCategory.ATMOSPHERE,
        default_uniforms={
            "u_Radius": 0.78,
            "u_Smoothness": 0.22,
            "u_Intensity": 0.4,
        },
    ),
    "pixelate": ShaderSpec(
        name="pixelate",
        category=ShaderCategory.RETRO,
        default_uniforms={
            "u_PixelSize": 1.0,
        },
    ),
    "color_grade": ShaderSpec(
        name="color_grade",
        category=ShaderCategory.ATMOSPHERE,
        default_uniforms={
            "u_LUT_Size": 16.0,
            "u_Intensity": 0.5,
        },
    ),
    "bloom_extract": ShaderSpec(
        name="bloom_extract",
        category=ShaderCategory.CORE,
        default_uniforms={
            "u_Threshold": 0.7,
        },
    ),
    "bloom_combine": ShaderSpec(
        name="bloom_combine",
        category=ShaderCategory.CORE,
        default_uniforms={
            "u_Intensity": 0.5,
        },
    ),
    "chromatic_aberration": ShaderSpec(
        name="chromatic_aberration",
        category=ShaderCategory.RETRO,
        default_uniforms={
            "u_Intensity": 0.0,
        },
    ),
    "gradient_fog": ShaderSpec(
        name="gradient_fog",
        category=ShaderCategory.ATMOSPHERE,
        default_uniforms={
            "u_FogColor": (0.7, 0.75, 0.8),
            "u_Start": 0.3,
            "u_End": 1.0,
            "u_Intensity": 0.5,
        },
    ),
    "film_grain": ShaderSpec(
        name="film_grain",
        category=ShaderCategory.ATMOSPHERE,
        default_uniforms={
            "u_Intensity": 0.15,
            "u_GrainScale": 1.0,
        },
    ),
    "radial_light_mask": ShaderSpec(
        name="radial_light_mask",
        category=ShaderCategory.LIGHTING,
        default_uniforms={
            "u_LightCenter": (0.5, 0.5),
            "u_InnerRadius": 0.2,
            "u_OuterRadius": 0.8,
            "u_Intensity": 0.8,
        },
    ),
    "crt_scanlines": ShaderSpec(
        name="crt_scanlines",
        category=ShaderCategory.RETRO,
        default_uniforms={
            "u_ScanlineIntensity": 0.5,
            "u_ChannelOffset": 0.003,
            "u_Curvature": 0.05,
        },
    ),
    "distortion": ShaderSpec(
        name="distortion",
        category=ShaderCategory.COMBAT,
        default_uniforms={
            "u_Strength": 0.0,
        },
    ),
    "shockwave": ShaderSpec(
        name="shockwave",
        category=ShaderCategory.COMBAT,
        default_uniforms={
            "u_Amplitude": 0.03,
            "u_Speed": 3.0,
        },
    ),
    "screenshake": ShaderSpec(
        name="screenshake",
        category=ShaderCategory.COMBAT,
        default_uniforms={
            "u_ShakeIntensity": 0.0,
        },
    ),
    "time_warp": ShaderSpec(
        name="time_warp",
        category=ShaderCategory.COMBAT,
        default_uniforms={
            "u_TimeScale": 1.0,
            "u_WarpIntensity": 0.0,
        },
    ),
    "additive_light": ShaderSpec(
        name="additive_light",
        category=ShaderCategory.LIGHTING,
        default_uniforms={
            "u_Color": (1.0, 1.0, 1.0),
            "u_Intensity": 1.0,
        },
    ),
    "shockwave_sprite": ShaderSpec(
        name="shockwave_sprite",
        category=ShaderCategory.COMBAT,
        default_uniforms={
            "u_Amplitude": 0.05,
            "u_Speed": 3.0,
        },
    ),
    "water_ripple": ShaderSpec(
        name="water_ripple",
        category=ShaderCategory.WATER,
        default_uniforms={
            "u_Amplitude": 0.02,
            "u_Speed": 2.0,
            "u_Frequency": 6.0,
        },
    ),
    "edge_detect": ShaderSpec(
        name="edge_detect",
        category=ShaderCategory.OUTLINES,
        default_uniforms={
            "u_Threshold": 0.2,
            "u_Intensity": 1.0,
            "u_Color": (0.0, 0.0, 0.0),
        },
    ),
    "lighting": ShaderSpec(
        name="lighting",
        category=ShaderCategory.LIGHTING,
        default_uniforms={
            "u_ambient_color": (0.2, 0.2, 0.3),
            "u_ambient_intensity": 0.3,
        },
    ),
    # Note: "lighting_2d" is an alias for "lighting" - both refer to the same shader
    "lighting_2d": ShaderSpec(
        name="lighting_2d",
        category=ShaderCategory.LIGHTING,
        default_uniforms={
            "u_ambient_color": (0.2, 0.2, 0.3),
            "u_ambient_intensity": 0.3,
        },
    ),
    "blur": ShaderSpec(
        name="blur",
        category=ShaderCategory.CORE,
        default_uniforms={
            "u_Direction": (1.0, 0.0),
            "u_BlurSize": 5.0,
        },
    ),
    "shot_particle_burst": ShaderSpec(
        name="shot_particle_burst",
        category=ShaderCategory.COMBAT,
        default_uniforms={
            "u_shot_pos": (0.5, 0.5),
            "u_shot_strength": 0.0,
            "u_effect_radius": 1.0,
        },
    ),
}


def get_shader_spec(name: str) -> Optional[ShaderSpec]:
    """Get a shader specification by name."""
    return SHADER_SPECS.get(name)
