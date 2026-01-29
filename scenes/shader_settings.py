"""ShaderSettingsScreen: UI for configuring shader effects with preview."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Dict, Any

import pygame

from rendering import draw_centered_text, RenderContext
from scenes.transitions import SceneTransition, KIND_POP
from gpu_gl_utils import (
    get_gl_context,
    get_fullscreen_quad,
    get_utility_shader,
    get_shaders_by_category,
    get_all_categories,
    ShaderCategory,
    create_utility_shader_program,
    HAS_MODERNGL,
)
from shader_effects.managers import get_shockwave_manager, get_screenshake_manager, get_light_manager
from shader_effects.pipeline import ShaderPipelineManager, ShaderCategory as PipelineCategory
from shader_effects.registry import SHADER_SPECS, ShaderCategory as RegistryCategory, get_shader_spec
from collections import defaultdict

if TYPE_CHECKING:
    from state import GameState

SHADER_SETTINGS_STATE_ID = "SHADER_SETTINGS"

# Build shaders by category from registry
shaders_by_category: dict[RegistryCategory, list[str]] = defaultdict(list)
for spec in SHADER_SPECS.values():
    shaders_by_category[spec.category].append(spec.name)


class ShaderSettingsScreen:
    """Screen for configuring shader effects with live preview."""
    
    def __init__(self) -> None:
        # Initialize with first category selected
        categories = list(RegistryCategory)
        self.selected_category: Optional[str] = categories[0].value.upper() if categories else None
        self.selected_shader: Optional[str] = None
        self.time = 0.0
        
        # UI state
        self.category_scroll = 0
        self.shader_scroll = 0
        self.param_scroll = 0
        
        # Parameter selection state
        self.selected_param_index: int = 0
        self._param_keys: list[str] = []
        
        # Preview pipeline (isolated from main game)
        self.preview_pipeline = ShaderPipelineManager()
        self.preview_surface: Optional[pygame.Surface] = None
        
        # Shader uniform values (current settings)
        self.shader_uniforms: Dict[str, Dict[str, Any]] = {}
        self.shader_enabled: Dict[str, bool] = {}
        
        # Initialize with defaults from registry
        for shader_name, spec in SHADER_SPECS.items():
            self.shader_uniforms[shader_name] = spec.default_uniforms.copy()
        
        # Load saved settings (will merge with defaults)
        self._load_settings()
        
        # Select first shader in initial category if available
        if self.selected_category:
            try:
                cat_enum = RegistryCategory[self.selected_category]
                shaders = shaders_by_category.get(cat_enum, [])
                if shaders:
                    self.selected_shader = shaders[0]
            except KeyError:
                pass
        
        # Demo animation state
        self.demo_time = 0.0
        self.last_shockwave_trigger = 0.0
        self.last_ripple_trigger = 0.0
        
        # Debug overlay
        self.debug_overlay_enabled = False
    
    def state_id(self) -> str:
        return SHADER_SETTINGS_STATE_ID
    
    def handle_input(self, events, game_state: "GameState", ctx: dict) -> dict:
        out = {"screen": None, "quit": False, "restart": False, "restart_to_wave1": False, "replay": False, "pop": False, "start_game": False}
        
        keys_pressed = pygame.key.get_pressed()
        
        for e in events:
            if not hasattr(e, "type") or e.type != pygame.KEYDOWN:
                continue
            key = getattr(e, "key", None)
            if key is None:
                continue
            
            try:
                if key == pygame.K_ESCAPE:
                    out["pop"] = True
                    break
                elif key == pygame.K_F1:
                    # F1 to start game directly from shader settings
                    from constants import STATE_PLAYING
                    out["screen"] = STATE_PLAYING
                    out["start_game"] = True
                    break
                elif key == pygame.K_F12:
                    self.debug_overlay_enabled = not self.debug_overlay_enabled
                elif key == pygame.K_s and keys_pressed[pygame.K_LCTRL]:
                    # Ctrl+S to save
                    self._save_settings()
                elif key == pygame.K_l and keys_pressed[pygame.K_LCTRL]:
                    # Ctrl+L to load
                    self._load_settings()
                elif key == pygame.K_UP:
                    # Navigate parameter list if shader selected AND we're at the first parameter, otherwise navigate categories/shaders
                    # If at first parameter, navigate shader list instead
                    if self.selected_shader and self._param_keys and self.selected_param_index > 0:
                        # Navigate within parameters
                        self.selected_param_index = max(0, self.selected_param_index - 1)
                    else:
                        # Navigate shader list or category list
                        self._navigate_up()
                elif key == pygame.K_DOWN:
                    # Navigate parameter list if shader selected AND not at last parameter, otherwise navigate categories/shaders
                    # If at last parameter, navigate shader list instead
                    if self.selected_shader and self._param_keys and self.selected_param_index < len(self._param_keys) - 1:
                        # Navigate within parameters
                        self.selected_param_index = min(len(self._param_keys) - 1, self.selected_param_index + 1)
                    else:
                        # Navigate shader list or category list
                        self._navigate_down()
                elif key == pygame.K_LEFT:
                    old_shader = self.selected_shader
                    self._navigate_left()
                    if old_shader == self.selected_shader and old_shader is not None:
                        print(f"[ShaderSettings] LEFT: navigation didn't change selection")
                elif key == pygame.K_RIGHT:
                    old_shader = self.selected_shader
                    self._navigate_right()
                    if old_shader == self.selected_shader and self.selected_category and not self.selected_shader:
                        print(f"[ShaderSettings] RIGHT: navigation didn't select shader")
                elif key == pygame.K_RETURN or key == pygame.K_SPACE:
                    self._toggle_selected_shader()
                elif key == pygame.K_a and keys_pressed[pygame.K_LCTRL]:
                    # Ctrl+A to apply settings to game
                    self._apply_to_game()
                elif key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    self._adjust_parameter(0.1)
                elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    self._adjust_parameter(-0.1)
            except Exception as ex:
                # Log error but don't crash - allow other keys to work
                import traceback
                print(f"[ShaderSettings] Error processing key {key}: {ex}")
                traceback.print_exc()
        
        return out
    
    def _navigate_up(self) -> None:
        """Navigate up in current selection."""
        try:
            if self.selected_shader:
                # Navigate shader list
                try:
                    cat_enum = RegistryCategory[self.selected_category] if self.selected_category else RegistryCategory.CORE
                    shaders = shaders_by_category.get(cat_enum, [])
                except KeyError:
                    shaders = []
                if shaders and len(shaders) > 1:
                    idx = shaders.index(self.selected_shader) if self.selected_shader in shaders else 0
                    idx = max(0, idx - 1)
                    self.selected_shader = shaders[idx]
                    # Reset parameter selection when changing shader
                    self._update_param_keys()
            elif self.selected_category:
                # Navigate category list
                categories = list(RegistryCategory)
                if categories and len(categories) > 1:
                    try:
                        current_cat = RegistryCategory[self.selected_category]
                        idx = categories.index(current_cat)
                    except (KeyError, ValueError):
                        idx = 0
                    idx = max(0, idx - 1)
                    self.selected_category = categories[idx].value.upper()
                    # Select first shader in new category
                    shaders = shaders_by_category.get(categories[idx], [])
                    self.selected_shader = shaders[0] if shaders else None
                    # Reset parameter selection when changing shader
                    if self.selected_shader:
                        self._update_param_keys()
                    else:
                        self._param_keys = []
                        self.selected_param_index = 0
        except Exception as ex:
            import traceback
            print(f"[ShaderSettings] Error in _navigate_up: {ex}")
            traceback.print_exc()
    
    def _navigate_down(self) -> None:
        """Navigate down in current selection."""
        try:
            if self.selected_shader:
                try:
                    cat_enum = RegistryCategory[self.selected_category] if self.selected_category else RegistryCategory.CORE
                    shaders = shaders_by_category.get(cat_enum, [])
                except KeyError:
                    shaders = []
                if shaders and len(shaders) > 1:
                    idx = shaders.index(self.selected_shader) if self.selected_shader in shaders else 0
                    idx = min(len(shaders) - 1, idx + 1)
                    self.selected_shader = shaders[idx]
                    # Reset parameter selection when changing shader
                    self._update_param_keys()
            elif self.selected_category:
                categories = list(RegistryCategory)
                if categories and len(categories) > 1:
                    try:
                        current_cat = RegistryCategory[self.selected_category]
                        idx = categories.index(current_cat)
                    except (KeyError, ValueError):
                        idx = 0
                    idx = min(len(categories) - 1, idx + 1)
                    self.selected_category = categories[idx].value.upper()
                    shaders = shaders_by_category.get(categories[idx], [])
                    self.selected_shader = shaders[0] if shaders else None
                    # Reset parameter selection when changing shader
                    if self.selected_shader:
                        self._update_param_keys()
                    else:
                        self._param_keys = []
                        self.selected_param_index = 0
        except Exception as ex:
            import traceback
            print(f"[ShaderSettings] Error in _navigate_down: {ex}")
            traceback.print_exc()
    
    def _navigate_left(self) -> None:
        """Navigate to category selection."""
        try:
            if self.selected_shader:
                self.selected_shader = None
                # Reset parameter selection when leaving shader
                self._param_keys = []
                self.selected_param_index = 0
        except Exception as ex:
            import traceback
            print(f"[ShaderSettings] Error in _navigate_left: {ex}")
            traceback.print_exc()
    
    def _navigate_right(self) -> None:
        """Navigate to shader selection."""
        try:
            if self.selected_category and not self.selected_shader:
                try:
                    cat_enum = RegistryCategory[self.selected_category]
                    shaders = shaders_by_category.get(cat_enum, [])
                except KeyError:
                    shaders = []
                self.selected_shader = shaders[0] if shaders else None
                # Build parameter keys when shader is selected
                if self.selected_shader:
                    self._update_param_keys()
        except Exception as ex:
            import traceback
            print(f"[ShaderSettings] Error in _navigate_right: {ex}")
            traceback.print_exc()
    
    def _toggle_selected_shader(self) -> None:
        """Toggle selected shader on/off."""
        if self.selected_shader:
            self.shader_enabled[self.selected_shader] = not self.shader_enabled.get(self.selected_shader, False)
            self._update_preview_pipeline()
    
    def _update_param_keys(self) -> None:
        """Update parameter keys list for currently selected shader."""
        if not self.selected_shader:
            self._param_keys = []
            return
        
        uniforms = self.shader_uniforms.get(self.selected_shader, {})
        param_items = list(uniforms.items())
        self._param_keys = [key for key, _ in param_items]
        # Reset selection to first parameter
        if self._param_keys:
            self.selected_param_index = 0
    
    def _adjust_parameter(self, delta: float) -> None:
        """Adjust the selected parameter of the selected shader."""
        if not self.selected_shader:
            return
        
        # Ensure param keys are built
        if not self._param_keys:
            self._update_param_keys()
        
        uniforms = self.shader_uniforms.get(self.selected_shader, {})
        if not uniforms or not self._param_keys:
            return
        
        # Clamp index
        if self.selected_param_index < 0:
            self.selected_param_index = 0
        if self.selected_param_index >= len(self._param_keys):
            self.selected_param_index = len(self._param_keys) - 1
        
        key = self._param_keys[self.selected_param_index]
        value = uniforms.get(key)
        
        if isinstance(value, (int, float)):
            # Simple clamp; adjust if you want per-uniform ranges later
            new_value = value + delta
            new_value = max(0.0, min(10.0, new_value))
            uniforms[key] = new_value
            self._update_preview_pipeline()
        # If it's a tuple (e.g. vec3), you can later extend this to adjust a specific component.
    
    def _update_preview_pipeline(self) -> None:
        """Update preview pipeline with enabled shaders."""
        self.preview_pipeline.clear()
        
        # Add enabled shaders to pipeline
        for shader_name, enabled in self.shader_enabled.items():
            if enabled:
                shader_info = get_utility_shader(shader_name)
                if shader_info:
                    _, _, category = shader_info
                    # Create a simple pass function
                    def make_pass_fn(name: str):
                        def pass_fn(surface, dt, context):
                            # In real implementation, this would use moderngl
                            return surface
                        return pass_fn
                    
                    # For now, just mark as enabled
                    # Full implementation would create actual shader programs
                    pass
    
    def update(self, dt: float, game_state: "GameState", ctx: dict) -> None:
        """Update scene state."""
        self.time += dt
        self.demo_time += dt
        
        # Update demo animations
        self._update_demo_animations(dt)
    
    def _update_demo_animations(self, dt: float) -> None:
        """Update demo animations based on selected category."""
        if not self.selected_category:
            return
        
        # Update time-based uniforms
        for shader_name in self.shader_enabled:
            if self.shader_enabled[shader_name]:
                uniforms = self.shader_uniforms.get(shader_name, {})
                if "u_Time" in uniforms:
                    uniforms["u_Time"] = self.demo_time
        
        # Category-specific animations
        try:
            cat_enum = RegistryCategory[self.selected_category]
            
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
                    if "water_ripple" in self.shader_enabled and self.shader_enabled["water_ripple"]:
                        uniforms = self.shader_uniforms.get("water_ripple", {})
                        uniforms["u_Center"] = (0.3 + (self.demo_time * 0.1) % 0.4, 0.3 + (self.demo_time * 0.15) % 0.4)
            
            elif cat_enum == RegistryCategory.LIGHTING:
                # Rotate light source
                light_mgr = get_light_manager()
                if light_mgr.lights:
                    angle = self.demo_time * 0.5
                    light_mgr.lights[0].pos = (0.5 + math.cos(angle) * 0.3, 0.5 + math.sin(angle) * 0.3)
        except (KeyError, TypeError):
            pass
    
    def handle_input_transition(self, events, game_state: "GameState", ctx: dict) -> SceneTransition:
        """Handle input and return transition."""
        # Always process input - this updates selected_category, selected_shader, etc.
        result = self.handle_input(events, game_state, ctx)
        # Store result for retrieval by game.py (avoids calling handle_input twice)
        self._last_input_result = result
        if result.get("pop"):
            return SceneTransition.pop()
        if result.get("start_game") or result.get("screen") == "PLAYING":
            # Start game - return to menu or start directly
            # The start_game flag will be handled by the game loop
            return SceneTransition.none()  # Let the game loop handle start_game flag
        # Return NONE - navigation and parameter adjustments handled in handle_input above
        # The state (selected_category, selected_shader, selected_param_index) was updated in handle_input
        return SceneTransition.none()
    
    def update_transition(self, dt: float, game_state: "GameState", ctx: dict) -> SceneTransition:
        """Update scene and return transition."""
        self.update(dt, game_state, ctx)
        return SceneTransition.none()
    
    def render(self, render_ctx: RenderContext, game_state: "GameState", ctx: dict) -> None:
        """Render shader settings screen."""
        if not HAS_MODERNGL:
            # Fallback rendering when moderngl not available
            render_ctx.screen.fill((20, 20, 30))
            draw_centered_text(
                render_ctx.screen,
                render_ctx.font,
                render_ctx.big_font,
                render_ctx.width,
                "Shader Settings Unavailable",
                render_ctx.height // 2 - 30,
                color=(255, 100, 100),
                use_big=False,
            )
            draw_centered_text(
                render_ctx.screen,
                render_ctx.font,
                render_ctx.big_font,
                render_ctx.width,
                "moderngl not installed",
                render_ctx.height // 2 + 10,
                color=(180, 180, 180),
            )
            draw_centered_text(
                render_ctx.screen,
                render_ctx.font,
                render_ctx.big_font,
                render_ctx.width,
                "Press ESC to return",
                render_ctx.height // 2 + 50,
                color=(160, 160, 160),
            )
            return
        
        screen = render_ctx.screen
        width, height = render_ctx.width, render_ctx.height
        
        # Clear screen
        screen.fill((20, 20, 30))
        
        # Layout: Left panel (categories), Middle (shaders), Right (preview), Bottom (params)
        panel_width = width // 4
        preview_width = width // 2
        param_height = height // 3
        
        # Draw category list (left)
        self._render_category_list(screen, 0, 0, panel_width, height - param_height, render_ctx)
        
        # Draw shader list (middle-left)
        self._render_shader_list(screen, panel_width, 0, panel_width, height - param_height, render_ctx)
        
        # Draw preview (right)
        self._render_preview(screen, panel_width * 2, 0, preview_width, height - param_height, render_ctx)
        
        # Draw parameters (bottom)
        self._render_parameters(screen, 0, height - param_height, width, param_height, render_ctx)
        
        # Draw controls at bottom
        controls_y = height - 80
        font = render_ctx.small_font
        start_text = font.render("F1: Start Game", True, (150, 200, 255))
        screen.blit(start_text, (width - 250, controls_y))
        
        apply_text = font.render("Ctrl+A: Apply to Game", True, (150, 255, 150))
        screen.blit(apply_text, (width - 250, controls_y + 20))
        
        note_text = font.render("Note: Enable 'use_gpu_shader_pipeline' in config for shaders to work", True, (200, 200, 150))
        screen.blit(note_text, (10, controls_y + 40))
        
        # Draw debug overlay if enabled
        if self.debug_overlay_enabled:
            self._render_debug_overlay(screen, render_ctx)
    
    def _render_category_list(self, screen: pygame.Surface, x: int, y: int, w: int, h: int, render_ctx: RenderContext) -> None:
        """Render category list."""
        pygame.draw.rect(screen, (30, 30, 40), (x, y, w, h))
        pygame.draw.rect(screen, (60, 60, 80), (x, y, w, h), 2)
        
        categories = list(RegistryCategory)
        font = render_ctx.font
        start_y = y + 20
        
        for i, cat in enumerate(categories):
            cat_name = cat.value.upper()
            color = (255, 255, 255) if cat_name == self.selected_category else (180, 180, 180)
            if cat_name == self.selected_category:
                pygame.draw.rect(screen, (60, 60, 100), (x + 5, start_y + i * 30 - 2, w - 10, 26))
            
            text = font.render(cat_name, True, color)
            screen.blit(text, (x + 10, start_y + i * 30))
    
    def _render_shader_list(self, screen: pygame.Surface, x: int, y: int, w: int, h: int, render_ctx: RenderContext) -> None:
        """Render shader list for selected category."""
        pygame.draw.rect(screen, (30, 30, 40), (x, y, w, h))
        pygame.draw.rect(screen, (60, 60, 80), (x, y, w, h), 2)
        
        if not self.selected_category:
            text = render_ctx.font.render("Select a category", True, (150, 150, 150))
            screen.blit(text, (x + 10, y + 20))
            return
        
        # Find category enum from string
        try:
            cat_enum = RegistryCategory[self.selected_category]
            shaders = shaders_by_category.get(cat_enum, [])
        except KeyError:
            shaders = []
        
        font = render_ctx.font
        start_y = y + 20
        
        for i, shader_name in enumerate(shaders):
            enabled = self.shader_enabled.get(shader_name, False)
            color = (100, 255, 100) if enabled else (255, 100, 100)
            if shader_name == self.selected_shader:
                pygame.draw.rect(screen, (60, 60, 100), (x + 5, start_y + i * 30 - 2, w - 10, 26))
                color = (255, 255, 100)
            
            status = "[ON]" if enabled else "[OFF]"
            text = font.render(f"{status} {shader_name}", True, color)
            screen.blit(text, (x + 10, start_y + i * 30))
    
    def _render_preview(self, screen: pygame.Surface, x: int, y: int, w: int, h: int, render_ctx: RenderContext) -> None:
        """Render shader preview."""
        pygame.draw.rect(screen, (15, 15, 25), (x, y, w, h))
        pygame.draw.rect(screen, (60, 60, 80), (x, y, w, h), 2)
        
        # Create or update preview surface
        if self.preview_surface is None or self.preview_surface.get_size() != (w - 20, h - 40):
            self.preview_surface = pygame.Surface((w - 20, h - 40))
        
        # Render demo scene
        self._render_demo_scene(self.preview_surface)
        
        # TODO: Wire this preview to the actual GPU shader pipeline so selected shader + uniforms are applied.
        # Apply shader pipeline (placeholder - would use actual GPU shaders)
        # For now, just blit the demo scene
        screen.blit(pygame.transform.scale(self.preview_surface, (w - 20, h - 40)), (x + 10, y + 30))
        
        # Draw title
        title = render_ctx.font.render("Preview", True, (200, 200, 200))
        screen.blit(title, (x + 10, y + 5))
        
        # Draw "visual demo" label indicating shaders are not yet applied
        demo_label = render_ctx.small_font.render("Preview (no shaders applied yet)", True, (150, 150, 150))
        screen.blit(demo_label, (x + 10, y + 20))
    
    def _render_demo_scene(self, surface: pygame.Surface) -> None:
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
            cat_enum = RegistryCategory[self.selected_category] if self.selected_category else None
            if cat_enum == RegistryCategory.RETRO:
                # Scrolling background
                offset = int(self.demo_time * 10) % 40
                for i in range(-40, w + 40, 40):
                    pygame.draw.rect(surface, (100, 150, 200), (i + offset, h // 3, 20, 20))
        except (KeyError, TypeError):
            pass
    
    def _render_parameters(self, screen: pygame.Surface, x: int, y: int, w: int, h: int, render_ctx: RenderContext) -> None:
        """Render shader parameters."""
        pygame.draw.rect(screen, (25, 25, 35), (x, y, w, h))
        pygame.draw.rect(screen, (60, 60, 80), (x, y, w, h), 2)
        
        if not self.selected_shader:
            text = render_ctx.font.render("Select a shader to adjust parameters", True, (150, 150, 150))
            screen.blit(text, (x + 10, y + 10))
            return
        
        # Ensure param keys are built (in case they weren't built yet)
        if not self._param_keys:
            self._update_param_keys()
        
        uniforms = self.shader_uniforms.get(self.selected_shader, {})
        
        # Use _param_keys to ensure consistent ordering with selection index
        if not self._param_keys:
            text = render_ctx.font.render("No parameters available", True, (150, 150, 150))
            screen.blit(text, (x + 10, y + 10))
            return
        
        # Render parameter controls
        font = render_ctx.small_font
        start_y = y + 10
        
        for idx, key in enumerate(self._param_keys):
            value = uniforms.get(key)
            is_selected = (idx == self.selected_param_index)
            
            # Highlight selected parameter
            if is_selected:
                # Draw highlight background
                pygame.draw.rect(screen, (50, 60, 80), (x + 5, start_y + idx * 25 - 2, w - 10, 22))
                # Use brighter color for selected
                text_color = (255, 255, 150)
                prefix = "▶ "
            else:
                text_color = (200, 200, 200)
                prefix = "  "
            
            if isinstance(value, (int, float)):
                text = font.render(f"{prefix}{key}: {value:.2f} (+/- to adjust)", True, text_color)
                screen.blit(text, (x + 10, start_y + idx * 25))
            elif isinstance(value, tuple) and len(value) == 2:
                text = font.render(f"{prefix}{key}: ({value[0]:.2f}, {value[1]:.2f})", True, text_color)
                screen.blit(text, (x + 10, start_y + idx * 25))
            elif isinstance(value, tuple) and len(value) == 3:
                text = font.render(f"{prefix}{key}: ({value[0]:.2f}, {value[1]:.2f}, {value[2]:.2f})", True, text_color)
                screen.blit(text, (x + 10, start_y + idx * 25))
    
    def _render_debug_overlay(self, screen: pygame.Surface, render_ctx: RenderContext) -> None:
        """Render debug overlay showing active shaders and uniforms."""
        font = render_ctx.small_font
        y = 10
        
        # Show active shaders
        active = [name for name, enabled in self.shader_enabled.items() if enabled]
        text = font.render(f"Active shaders: {', '.join(active) if active else 'None'}", True, (255, 255, 0))
        screen.blit(text, (10, y))
        y += 25
        
        # Show selected shader uniforms
        if self.selected_shader:
            uniforms = self.shader_uniforms.get(self.selected_shader, {})
            for key, value in list(uniforms.items())[:5]:  # Show first 5
                text = font.render(f"{key} = {value}", True, (200, 200, 200))
                screen.blit(text, (10, y))
                y += 20
    
    def _save_settings(self) -> None:
        """Save shader settings to config file."""
        settings = {
            "enabled": self.shader_enabled,
            "uniforms": self.shader_uniforms,
        }
        
        config_path = Path("config/shaders.json")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(config_path, "w") as f:
                json.dump(settings, f, indent=2)
            print(f"[ShaderSettings] Saved settings to {config_path}")
            # Apply settings to global shader pipeline after saving
            self._apply_settings_to_pipeline()
        except Exception as e:
            print(f"[ShaderSettings] Failed to save: {e}")
    
    def _apply_settings_to_pipeline(self) -> None:
        """Apply current shader settings to the global gameplay shader pipeline."""
        try:
            from shader_effects.registry import get_shader_spec
            from shader_effects.pipeline import pipeline_category_for_registry_category
            
            # Prepare enabled shaders list
            enabled_shaders = []
            for shader_name, enabled in self.shader_enabled.items():
                if enabled:
                    spec = get_shader_spec(shader_name)
                    if spec:
                        uniforms = self.shader_uniforms.get(shader_name, spec.default_uniforms.copy())
                        pipeline_cat = pipeline_category_for_registry_category(spec.category)
                        enabled_shaders.append({
                            "name": shader_name,
                            "category": pipeline_cat,
                            "uniforms": uniforms,
                            "spec": spec
                        })
            
            # Store the enabled shaders list for the game to use
            _store_applied_shader_settings(enabled_shaders)
            
            print(f"[ShaderSettings] Prepared {len(enabled_shaders)} shaders for gameplay pipeline")
        except Exception as e:
            print(f"[ShaderSettings] Failed to prepare settings: {e}")
            import traceback
            traceback.print_exc()
    
    def _load_settings(self) -> None:
        """Load shader settings from config file."""
        config_path = Path("config/shaders.json")
        
        if not config_path.exists():
            # Already initialized with defaults in __init__
            return
        
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
        except Exception as e:
            print(f"[ShaderSettings] Failed to load: {e}")
            # Keep defaults already set in __init__
    
    def _apply_to_game(self) -> None:
        """Apply current shader settings directly to the gameplay pipeline."""
        try:
            # First save and prepare settings
            self._save_settings()
            # Then apply to the actual pipeline
            from rendering_shaders import apply_shader_settings_to_pipeline
            apply_shader_settings_to_pipeline()
            print("[ShaderSettings] Applied shader settings to gameplay pipeline (Ctrl+A)")
        except Exception as e:
            print(f"[ShaderSettings] Failed to apply to game: {e}")
            import traceback
            traceback.print_exc()

# Global storage for applied shader settings
_applied_shader_settings: list[dict] = []

def _store_applied_shader_settings(shaders: list[dict]) -> None:
    """Store shader settings to be applied to the gameplay pipeline."""
    global _applied_shader_settings
    _applied_shader_settings = shaders

def get_applied_shader_settings() -> list[dict]:
    """Get the shader settings that should be applied to gameplay."""
    return _applied_shader_settings.copy()

def load_and_apply_shader_settings_from_file() -> None:
    """Load shader settings from config/shaders.json and prepare them for application."""
    config_path = Path("config/shaders.json")
    if not config_path.exists():
        return
    
    try:
        with open(config_path, "r") as f:
            settings = json.load(f)
        
        from shader_effects.registry import get_shader_spec
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
        
        _store_applied_shader_settings(enabled_shaders)
        print(f"[ShaderSettings] Loaded {len(enabled_shaders)} shaders from {config_path}")
    except Exception as e:
        print(f"[ShaderSettings] Failed to load settings from file: {e}")
    
    def on_enter(self, game_state: "GameState", ctx: dict) -> None:
        """Called when scene is entered."""
        if not HAS_MODERNGL:
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Shader settings unavailable: moderngl not installed")
            # Scene will handle this gracefully in render() by showing a message
            return
        
        if not self.selected_category:
            categories = list(RegistryCategory)
            if categories:
                self.selected_category = categories[0].value.upper()
                shaders = shaders_by_category.get(categories[0], [])
                self.selected_shader = shaders[0] if shaders else None
                # Reset parameter selection when entering scene
                self.selected_param_index = 0
                self._param_keys = []
    
    def on_exit(self, game_state: "GameState", ctx: dict) -> None:
        """Called when scene is exited."""
        # Save settings and apply them to the game pipeline
        self._save_settings()
        # Settings are automatically applied in _save_settings via _apply_settings_to_pipeline
        # The game can call get_applied_shader_settings() to get the enabled shaders and apply them
