"""Shader settings data model: storage, defaults, load/save, and global state."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from shader_effects.registry import SHADER_SPECS, ShaderCategory as RegistryCategory, get_shader_spec


# Build shaders by category from registry
shaders_by_category: dict[RegistryCategory, list[str]] = defaultdict(list)
for _spec in SHADER_SPECS.values():
    shaders_by_category[_spec.category].append(_spec.name)


class ShaderSettingsModel:
    """Data model for shader settings with persistence support."""
    
    def __init__(self) -> None:
        # Shader uniform values (current settings)
        self.shader_uniforms: Dict[str, Dict[str, Any]] = {}
        self.shader_enabled: Dict[str, bool] = {}
        
        # Initialize with defaults from registry
        for shader_name, spec in SHADER_SPECS.items():
            self.shader_uniforms[shader_name] = spec.default_uniforms.copy()
    
    def get_uniforms(self, shader_name: str) -> Dict[str, Any]:
        """Get uniforms for a shader, with defaults if not set."""
        return self.shader_uniforms.get(shader_name, {}).copy()
    
    def set_uniform(self, shader_name: str, key: str, value: Any) -> None:
        """Set a single uniform value for a shader."""
        if shader_name not in self.shader_uniforms:
            spec = get_shader_spec(shader_name)
            self.shader_uniforms[shader_name] = spec.default_uniforms.copy() if spec else {}
        self.shader_uniforms[shader_name][key] = value
    
    def is_enabled(self, shader_name: str) -> bool:
        """Check if a shader is enabled."""
        return self.shader_enabled.get(shader_name, False)
    
    def set_enabled(self, shader_name: str, enabled: bool) -> None:
        """Enable or disable a shader."""
        self.shader_enabled[shader_name] = enabled
    
    def toggle_enabled(self, shader_name: str) -> bool:
        """Toggle shader enabled state. Returns new state."""
        new_state = not self.is_enabled(shader_name)
        self.set_enabled(shader_name, new_state)
        return new_state
    
    def get_enabled_shaders(self) -> List[str]:
        """Get list of enabled shader names."""
        return [name for name, enabled in self.shader_enabled.items() if enabled]
    
    def save(self, config_path: Path | str | None = None) -> bool:
        """Save shader settings to config file. Returns True on success."""
        if config_path is None:
            config_path = Path("config/shaders.json")
        else:
            config_path = Path(config_path)
        
        settings = {
            "enabled": self.shader_enabled,
            "uniforms": self.shader_uniforms,
        }
        
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(config_path, "w") as f:
                json.dump(settings, f, indent=2)
            print(f"[ShaderSettings] Saved settings to {config_path}")
            return True
        except Exception as e:
            print(f"[ShaderSettings] Failed to save: {e}")
            return False
    
    def load(self, config_path: Path | str | None = None) -> bool:
        """Load shader settings from config file. Returns True on success."""
        if config_path is None:
            config_path = Path("config/shaders.json")
        else:
            config_path = Path(config_path)
        
        if not config_path.exists():
            return False
        
        try:
            with open(config_path, "r") as f:
                settings = json.load(f)
            
            # Load enabled flags
            saved_enabled = settings.get("enabled", {})
            self.shader_enabled.update(saved_enabled)
            
            # Load uniforms, merging with registry defaults
            saved_uniforms = settings.get("uniforms", {})
            for shader_name, saved_values in saved_uniforms.items():
                spec = get_shader_spec(shader_name)
                if spec:
                    # Start with registry defaults, then apply saved values
                    self.shader_uniforms[shader_name] = spec.default_uniforms.copy()
                    self.shader_uniforms[shader_name].update(saved_values)
                else:
                    # Unknown shader, use saved values as-is
                    self.shader_uniforms[shader_name] = saved_values
            
            print(f"[ShaderSettings] Loaded settings from {config_path}")
            return True
        except Exception as e:
            print(f"[ShaderSettings] Failed to load: {e}")
            return False


# Global storage for applied shader settings (used by gameplay pipeline)
_applied_shader_settings: List[dict] = []


def store_applied_shader_settings(shaders: List[dict]) -> None:
    """Store shader settings to be applied to the gameplay pipeline."""
    global _applied_shader_settings
    _applied_shader_settings = shaders


def get_applied_shader_settings() -> List[dict]:
    """Get the shader settings that should be applied to gameplay."""
    return _applied_shader_settings.copy()


def prepare_shader_settings_for_pipeline(model: ShaderSettingsModel) -> List[dict]:
    """Convert model settings to pipeline-ready shader list."""
    from shader_effects.pipeline import pipeline_category_for_registry_category
    
    enabled_shaders = []
    for shader_name in model.get_enabled_shaders():
        spec = get_shader_spec(shader_name)
        if spec:
            uniforms = model.get_uniforms(shader_name)
            if not uniforms:
                uniforms = spec.default_uniforms.copy()
            pipeline_cat = pipeline_category_for_registry_category(spec.category)
            enabled_shaders.append({
                "name": shader_name,
                "category": pipeline_cat,
                "uniforms": uniforms,
                "spec": spec
            })
    
    return enabled_shaders


def load_and_apply_shader_settings_from_file() -> None:
    """Load shader settings from config/shaders.json and prepare them for application."""
    config_path = Path("config/shaders.json")
    if not config_path.exists():
        return
    
    try:
        with open(config_path, "r") as f:
            settings = json.load(f)
        
        from shader_effects.pipeline import pipeline_category_for_registry_category
        
        enabled_shaders = []
        saved_enabled = settings.get("enabled", {})
        saved_uniforms = settings.get("uniforms", {})
        
        for shader_name, enabled in saved_enabled.items():
            if enabled:
                spec = get_shader_spec(shader_name)
                if spec:
                    uniforms = saved_uniforms.get(shader_name, spec.default_uniforms.copy())
                    pipeline_cat = pipeline_category_for_registry_category(spec.category)
                    enabled_shaders.append({
                        "name": shader_name,
                        "category": pipeline_cat,
                        "uniforms": uniforms,
                        "spec": spec
                    })
        
        store_applied_shader_settings(enabled_shaders)
        print(f"[ShaderSettings] Loaded {len(enabled_shaders)} shaders from {config_path}")
    except Exception as e:
        print(f"[ShaderSettings] Failed to load settings from file: {e}")
