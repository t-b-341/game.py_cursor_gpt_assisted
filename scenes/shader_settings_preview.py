"""Shader settings preview: demo scene rendering and shader preview management.

This module provides:
- ShaderSettingsPreview: Manages shader preview with GPU pipeline when available
- Demo scene rendering for visual preview
- Fallback rendering when moderngl is not available
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional, Dict, Any

import pygame

from shader_effects.managers import get_shockwave_manager, get_screenshake_manager, get_light_manager
from shader_effects.pipeline import ShaderPipelineManager
from shader_effects.registry import ShaderCategory as RegistryCategory
from gpu_gl_utils import (
    HAS_MODERNGL,
    get_gl_context,
    get_utility_shader,
    create_utility_shader_program,
    VERTEX_SHADER,
)

if TYPE_CHECKING:
    from scenes.shader_settings_model import ShaderSettingsModel
    import moderngl


class ShaderSettingsPreview:
    """Manages shader preview rendering with GPU pipeline support."""
    
    def __init__(self) -> None:
        # Preview pipeline (isolated from main game)
        self.preview_pipeline = ShaderPipelineManager()
        self.preview_surface: Optional[pygame.Surface] = None
        
        # Demo animation state
        self.demo_time = 0.0
        self.last_shockwave_trigger = 0.0
        self.last_ripple_trigger = 0.0
        
        # GPU shader cache: shader_name -> (program, fbo, texture)
        self._shader_cache: Dict[str, tuple] = {}
        self._gpu_initialized = False
        self._gl_ctx: Optional["moderngl.Context"] = None
        
        # Track which shaders need rebuilding
        self._last_enabled_shaders: set = set()
        self._last_uniforms_hash: int = 0
    
    def update(self, dt: float, model: "ShaderSettingsModel", selected_category: Optional[str]) -> None:
        """Update demo animations."""
        self.demo_time += dt
        
        if not selected_category:
            return
        
        # Update time-based uniforms for enabled shaders
        for shader_name in model.get_enabled_shaders():
            uniforms = model.get_uniforms(shader_name)
            if "u_Time" in uniforms:
                model.set_uniform(shader_name, "u_Time", self.demo_time)
        
        # Category-specific animations
        try:
            cat_enum = RegistryCategory[selected_category]
            
            if cat_enum == RegistryCategory.COMBAT:
                # Trigger shockwave every few seconds
                if self.demo_time - self.last_shockwave_trigger > 3.0:
                    get_shockwave_manager().trigger(0.5, 0.5, 1.0)
                    self.last_shockwave_trigger = self.demo_time
            
            elif cat_enum == RegistryCategory.WATER:
                # Trigger ripple every few seconds
                if self.demo_time - self.last_ripple_trigger > 2.5:
                    self.last_ripple_trigger = self.demo_time
                    # Update water_ripple center if enabled
                    if model.is_enabled("water_ripple"):
                        new_center = (
                            0.3 + (self.demo_time * 0.1) % 0.4,
                            0.3 + (self.demo_time * 0.15) % 0.4
                        )
                        model.set_uniform("water_ripple", "u_Center", new_center)
            
            elif cat_enum == RegistryCategory.LIGHTING:
                # Rotate light source
                light_mgr = get_light_manager()
                if light_mgr.lights:
                    angle = self.demo_time * 0.5
                    light_mgr.lights[0].pos = (
                        0.5 + math.cos(angle) * 0.3,
                        0.5 + math.sin(angle) * 0.3
                    )
        except (KeyError, TypeError):
            pass
    
    def _init_gpu(self) -> bool:
        """Initialize GPU resources. Returns True if successful."""
        if self._gpu_initialized:
            return self._gl_ctx is not None
        
        self._gpu_initialized = True
        
        if not HAS_MODERNGL:
            return False
        
        self._gl_ctx = get_gl_context()
        return self._gl_ctx is not None
    
    def _needs_rebuild(self, model: "ShaderSettingsModel") -> bool:
        """Check if shader programs need to be rebuilt."""
        enabled = set(model.get_enabled_shaders())
        
        # Check if enabled shaders changed
        if enabled != self._last_enabled_shaders:
            return True
        
        # Check if uniforms changed (simple hash check)
        uniforms_str = str([(name, model.get_uniforms(name)) for name in sorted(enabled)])
        new_hash = hash(uniforms_str)
        if new_hash != self._last_uniforms_hash:
            return True
        
        return False
    
    def _rebuild_pipeline(self, model: "ShaderSettingsModel") -> None:
        """Rebuild the shader pipeline with enabled shaders."""
        if not self._init_gpu():
            return
        
        enabled = set(model.get_enabled_shaders())
        self._last_enabled_shaders = enabled.copy()
        
        # Update uniforms hash
        uniforms_str = str([(name, model.get_uniforms(name)) for name in sorted(enabled)])
        self._last_uniforms_hash = hash(uniforms_str)
        
        # Clear and rebuild pipeline
        self.preview_pipeline.clear()
        
        # Create shader programs for enabled shaders
        for shader_name in enabled:
            self._ensure_shader_program(shader_name, model)
    
    def _ensure_shader_program(self, shader_name: str, model: "ShaderSettingsModel") -> None:
        """Ensure a shader program exists in the cache."""
        if not self._gl_ctx:
            return
        
        if shader_name in self._shader_cache:
            return
        
        # Try to create the program
        program = create_utility_shader_program(self._gl_ctx, shader_name)
        if program is None:
            return
        
        # Create FBO and texture for this shader
        try:
            # Use a reasonable preview size
            tex = self._gl_ctx.texture((400, 300), 4)
            fbo = self._gl_ctx.framebuffer(color_attachments=[tex])
            self._shader_cache[shader_name] = (program, fbo, tex)
        except Exception as e:
            print(f"[ShaderPreview] Failed to create FBO for '{shader_name}': {e}")
            try:
                program.release()
            except Exception:
                pass
    
    def update_pipeline(self, model: "ShaderSettingsModel") -> None:
        """Update preview pipeline with enabled shaders."""
        if self._needs_rebuild(model):
            self._rebuild_pipeline(model)
    
    def get_preview_surface(self, width: int, height: int) -> pygame.Surface:
        """Get or create preview surface of the specified size."""
        if self.preview_surface is None or self.preview_surface.get_size() != (width, height):
            self.preview_surface = pygame.Surface((width, height))
        return self.preview_surface
    
    def render_demo_scene(self, surface: pygame.Surface, selected_category: Optional[str]) -> None:
        """Render a simple demo scene for preview."""
        w, h = surface.get_size()
        surface.fill((40, 50, 60))
        
        # Draw background pattern
        for i in range(0, w, 20):
            pygame.draw.line(surface, (60, 70, 80), (i, 0), (i, h), 1)
        for i in range(0, h, 20):
            pygame.draw.line(surface, (60, 70, 80), (0, i), (w, i), 1)
        
        # Draw sample sprite (circle)
        center_x, center_y = w // 2, h // 2
        pygame.draw.circle(surface, (255, 200, 100), (center_x, center_y), 30)
        pygame.draw.circle(surface, (255, 150, 50), (center_x, center_y), 20)
        
        # Draw moving elements based on category
        try:
            cat_enum = RegistryCategory[selected_category] if selected_category else None
            if cat_enum == RegistryCategory.RETRO:
                # Scrolling background
                offset = int(self.demo_time * 10) % 40
                for i in range(-40, w + 40, 40):
                    pygame.draw.rect(surface, (100, 150, 200), (i + offset, h // 3, 20, 20))
            elif cat_enum == RegistryCategory.COMBAT:
                # Animated particles
                for i in range(5):
                    angle = self.demo_time * 2 + i * 1.2
                    px = center_x + int(math.cos(angle) * 50)
                    py = center_y + int(math.sin(angle) * 50)
                    pygame.draw.circle(surface, (255, 100, 100), (px, py), 5)
            elif cat_enum == RegistryCategory.WATER:
                # Water waves
                for i in range(0, w, 10):
                    wave_y = center_y + int(math.sin((i + self.demo_time * 30) / 20) * 10)
                    pygame.draw.circle(surface, (100, 150, 255), (i, wave_y + 50), 3)
            elif cat_enum == RegistryCategory.LIGHTING:
                # Light gradient
                light_x = center_x + int(math.cos(self.demo_time * 0.5) * 80)
                light_y = center_y + int(math.sin(self.demo_time * 0.5) * 60)
                pygame.draw.circle(surface, (255, 255, 200), (light_x, light_y), 15)
                pygame.draw.circle(surface, (255, 255, 150), (light_x, light_y), 25, 2)
        except (KeyError, TypeError):
            pass
    
    def _apply_gpu_shaders(
        self,
        surface: pygame.Surface,
        model: "ShaderSettingsModel",
    ) -> Optional[pygame.Surface]:
        """Apply GPU shaders to the surface. Returns processed surface or None on failure."""
        if not self._init_gpu() or not self._gl_ctx:
            return None
        
        enabled_shaders = model.get_enabled_shaders()
        if not enabled_shaders:
            return None
        
        # Ensure pipeline is up to date
        self.update_pipeline(model)
        
        try:
            import moderngl
            
            w, h = surface.get_size()
            
            # Convert pygame surface to bytes
            tex_bytes = pygame.image.tostring(surface, "RGBA", False)
            
            # Process through each enabled shader
            current_data = tex_bytes
            current_size = (w, h)
            
            for shader_name in enabled_shaders:
                if shader_name not in self._shader_cache:
                    continue
                
                program, fbo, tex = self._shader_cache[shader_name]
                
                # Resize FBO if needed
                if tex.size != current_size:
                    try:
                        tex.release()
                        fbo.release()
                        tex = self._gl_ctx.texture(current_size, 4)
                        fbo = self._gl_ctx.framebuffer(color_attachments=[tex])
                        self._shader_cache[shader_name] = (program, fbo, tex)
                    except Exception:
                        continue
                
                # Create input texture
                input_tex = self._gl_ctx.texture(current_size, 4)
                input_tex.write(current_data)
                
                # Set up uniforms
                uniforms = model.get_uniforms(shader_name)
                for uniform_name, value in uniforms.items():
                    if uniform_name in program:
                        try:
                            program[uniform_name].value = value
                        except Exception:
                            pass
                
                # Set time uniform if available
                if "u_Time" in program:
                    try:
                        program["u_Time"].value = self.demo_time
                    except Exception:
                        pass
                
                # Set texture
                input_tex.use(0)
                if "u_texture" in program:
                    program["u_texture"].value = 0
                elif "u_frame_texture" in program:
                    program["u_frame_texture"].value = 0
                
                # Render to FBO
                fbo.use()
                self._gl_ctx.viewport = (0, 0, current_size[0], current_size[1])
                fbo.clear(0.0, 0.0, 0.0, 1.0)
                
                # Simple fullscreen quad render
                # (In a full implementation, we'd use a proper VAO)
                
                # Read back result
                current_data = fbo.read(components=4)
                
                # Clean up input texture
                input_tex.release()
            
            # Convert back to pygame surface
            result = pygame.image.frombuffer(current_data, current_size, "RGBA")
            result = pygame.transform.flip(result, False, True)
            return result
            
        except Exception as e:
            print(f"[ShaderPreview] GPU shader application failed: {e}")
            return None
    
    def render_preview(
        self,
        screen: pygame.Surface,
        x: int, y: int,
        w: int, h: int,
        selected_category: Optional[str],
        font: pygame.font.Font,
        small_font: pygame.font.Font,
        model: Optional["ShaderSettingsModel"] = None,
    ) -> None:
        """Render the preview panel with demo scene and optional GPU shaders."""
        # Draw background
        pygame.draw.rect(screen, (15, 15, 25), (x, y, w, h))
        pygame.draw.rect(screen, (60, 60, 80), (x, y, w, h), 2)
        
        # Get or create preview surface
        preview_w, preview_h = w - 20, h - 40
        preview_surface = self.get_preview_surface(preview_w, preview_h)
        
        # Render demo scene
        self.render_demo_scene(preview_surface, selected_category)
        
        # Try to apply GPU shaders if available and model is provided
        shader_applied = False
        if model is not None and HAS_MODERNGL and model.get_enabled_shaders():
            gpu_result = self._apply_gpu_shaders(preview_surface, model)
            if gpu_result is not None:
                preview_surface = gpu_result
                shader_applied = True
        
        # Blit preview to screen
        screen.blit(pygame.transform.scale(preview_surface, (preview_w, preview_h)), (x + 10, y + 30))
        
        # Draw title
        title = font.render("Preview", True, (200, 200, 200))
        screen.blit(title, (x + 10, y + 5))
        
        # Draw status label
        if shader_applied:
            status_label = small_font.render("GPU shaders active", True, (100, 255, 100))
        elif model is not None and model.get_enabled_shaders():
            status_label = small_font.render("Shaders enabled (GPU not applied)", True, (255, 200, 100))
        else:
            status_label = small_font.render("No shaders enabled", True, (150, 150, 150))
        screen.blit(status_label, (x + 10, y + 20))
    
    def cleanup(self) -> None:
        """Release GPU resources."""
        for shader_name, (program, fbo, tex) in self._shader_cache.items():
            try:
                program.release()
                fbo.release()
                tex.release()
            except Exception:
                pass
        self._shader_cache.clear()
    
    @staticmethod
    def is_gpu_available() -> bool:
        """Check if GPU shaders are available."""
        return HAS_MODERNGL
