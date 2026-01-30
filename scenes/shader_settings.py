"""ShaderSettingsScreen: re-export from split modules for backward compatibility.

This file has been split into:
- shader_settings_model.py: Data model, persistence, global settings storage
- shader_settings_preview.py: Preview rendering and demo animations
- shader_settings_screen.py: Main UI scene class

Import from here for backward compatibility, or import directly from the specific modules.
"""
from __future__ import annotations

# Re-export the main scene class
from scenes.shader_settings_screen import ShaderSettingsScreen, SHADER_SETTINGS_STATE_ID

# Re-export model functions for external use
from scenes.shader_settings_model import (
    ShaderSettingsModel,
    shaders_by_category,
    get_applied_shader_settings,
    store_applied_shader_settings,
    load_and_apply_shader_settings_from_file,
    prepare_shader_settings_for_pipeline,
)

# Re-export preview class
from scenes.shader_settings_preview import ShaderSettingsPreview

__all__ = [
    # Main scene
    "ShaderSettingsScreen",
    "SHADER_SETTINGS_STATE_ID",
    # Model
    "ShaderSettingsModel",
    "shaders_by_category",
    "get_applied_shader_settings",
    "store_applied_shader_settings",
    "load_and_apply_shader_settings_from_file",
    "prepare_shader_settings_for_pipeline",
    # Preview
    "ShaderSettingsPreview",
]
