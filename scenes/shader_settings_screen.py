"""ShaderSettingsScreen: UI scene for configuring shader effects with preview."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List

import pygame

from rendering import draw_centered_text, RenderContext
from scenes.transitions import SceneTransition
from scenes.shader_settings_model import (
    ShaderSettingsModel,
    shaders_by_category,
    store_applied_shader_settings,
    prepare_shader_settings_for_pipeline,
)
from scenes.shader_settings_preview import ShaderSettingsPreview
from shader_effects.registry import ShaderCategory as RegistryCategory
from gpu_gl_utils import HAS_MODERNGL

if TYPE_CHECKING:
    from state import GameState

SHADER_SETTINGS_STATE_ID = "SHADER_SETTINGS"


class ShaderSettingsScreen:
    """Screen for configuring shader effects with live preview."""
    
    def __init__(self) -> None:
        # Data model for shader settings
        self.model = ShaderSettingsModel()
        
        # Preview manager
        self.preview = ShaderSettingsPreview()
        
        # UI state
        categories = list(RegistryCategory)
        self.selected_category: Optional[str] = categories[0].value.upper() if categories else None
        self.selected_shader: Optional[str] = None
        self.time = 0.0
        
        # Scroll state
        self.category_scroll = 0
        self.shader_scroll = 0
        self.param_scroll = 0
        
        # Parameter selection state
        self.selected_param_index: int = 0
        self._param_keys: List[str] = []
        
        # Load saved settings
        self.model.load()
        
        # Select first shader in initial category if available
        if self.selected_category:
            try:
                cat_enum = RegistryCategory[self.selected_category]
                shaders = shaders_by_category.get(cat_enum, [])
                if shaders:
                    self.selected_shader = shaders[0]
            except KeyError:
                pass
        
        # Debug overlay
        self.debug_overlay_enabled = False
    
    def state_id(self) -> str:
        return SHADER_SETTINGS_STATE_ID
    
    def handle_input(self, events, game_state: "GameState", ctx: dict) -> dict:
        out = {
            "screen": None,
            "quit": False,
            "restart": False,
            "restart_to_wave1": False,
            "replay": False,
            "pop": False,
            "start_game": False,
        }
        
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
                    self.model.load()
                elif key == pygame.K_UP:
                    if self.selected_shader and self._param_keys and self.selected_param_index > 0:
                        self.selected_param_index = max(0, self.selected_param_index - 1)
                    else:
                        self._navigate_up()
                elif key == pygame.K_DOWN:
                    if self.selected_shader and self._param_keys and self.selected_param_index < len(self._param_keys) - 1:
                        self.selected_param_index = min(len(self._param_keys) - 1, self.selected_param_index + 1)
                    else:
                        self._navigate_down()
                elif key == pygame.K_LEFT:
                    self._navigate_left()
                elif key == pygame.K_RIGHT:
                    self._navigate_right()
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
                import traceback
                print(f"[ShaderSettings] Error processing key {key}: {ex}")
                traceback.print_exc()
        
        return out
    
    def _navigate_up(self) -> None:
        """Navigate up in current selection."""
        try:
            if self.selected_shader:
                try:
                    cat_enum = RegistryCategory[self.selected_category] if self.selected_category else RegistryCategory.CORE
                    shaders = shaders_by_category.get(cat_enum, [])
                except KeyError:
                    shaders = []
                if shaders and len(shaders) > 1:
                    idx = shaders.index(self.selected_shader) if self.selected_shader in shaders else 0
                    idx = max(0, idx - 1)
                    self.selected_shader = shaders[idx]
                    self._update_param_keys()
            elif self.selected_category:
                categories = list(RegistryCategory)
                if categories and len(categories) > 1:
                    try:
                        current_cat = RegistryCategory[self.selected_category]
                        idx = categories.index(current_cat)
                    except (KeyError, ValueError):
                        idx = 0
                    idx = max(0, idx - 1)
                    self.selected_category = categories[idx].value.upper()
                    shaders = shaders_by_category.get(categories[idx], [])
                    self.selected_shader = shaders[0] if shaders else None
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
                if self.selected_shader:
                    self._update_param_keys()
        except Exception as ex:
            import traceback
            print(f"[ShaderSettings] Error in _navigate_right: {ex}")
            traceback.print_exc()
    
    def _toggle_selected_shader(self) -> None:
        """Toggle selected shader on/off."""
        if self.selected_shader:
            self.model.toggle_enabled(self.selected_shader)
            self.preview.update_pipeline(self.model)
    
    def _update_param_keys(self) -> None:
        """Update parameter keys list for currently selected shader."""
        if not self.selected_shader:
            self._param_keys = []
            return
        
        uniforms = self.model.get_uniforms(self.selected_shader)
        self._param_keys = list(uniforms.keys())
        if self._param_keys:
            self.selected_param_index = 0
    
    def _adjust_parameter(self, delta: float) -> None:
        """Adjust the selected parameter of the selected shader."""
        if not self.selected_shader:
            return
        
        if not self._param_keys:
            self._update_param_keys()
        
        if not self._param_keys:
            return
        
        # Clamp index
        self.selected_param_index = max(0, min(len(self._param_keys) - 1, self.selected_param_index))
        
        key = self._param_keys[self.selected_param_index]
        uniforms = self.model.get_uniforms(self.selected_shader)
        value = uniforms.get(key)
        
        if isinstance(value, (int, float)):
            new_value = max(0.0, min(10.0, value + delta))
            self.model.set_uniform(self.selected_shader, key, new_value)
            self.preview.update_pipeline(self.model)
    
    def _save_settings(self) -> None:
        """Save shader settings and prepare for pipeline."""
        self.model.save()
        self._apply_settings_to_pipeline()
    
    def _apply_settings_to_pipeline(self) -> None:
        """Apply current shader settings to the global gameplay shader pipeline."""
        try:
            enabled_shaders = prepare_shader_settings_for_pipeline(self.model)
            store_applied_shader_settings(enabled_shaders)
            print(f"[ShaderSettings] Prepared {len(enabled_shaders)} shaders for gameplay pipeline")
        except Exception as e:
            print(f"[ShaderSettings] Failed to prepare settings: {e}")
            import traceback
            traceback.print_exc()
    
    def _apply_to_game(self) -> None:
        """Apply current shader settings directly to the gameplay pipeline."""
        try:
            self._save_settings()
            from rendering_shaders import apply_shader_settings_to_pipeline
            apply_shader_settings_to_pipeline()
            print("[ShaderSettings] Applied shader settings to gameplay pipeline (Ctrl+A)")
        except Exception as e:
            print(f"[ShaderSettings] Failed to apply to game: {e}")
            import traceback
            traceback.print_exc()
    
    def update(self, dt: float, game_state: "GameState", ctx: dict) -> None:
        """Update scene state."""
        self.time += dt
        self.preview.update(dt, self.model, self.selected_category)
    
    def handle_input_transition(self, events, game_state: "GameState", ctx: dict) -> SceneTransition:
        """Handle input and return transition."""
        result = self.handle_input(events, game_state, ctx)
        self._last_input_result = result
        
        if result.get("pop"):
            return SceneTransition.pop()
        if result.get("start_game") or result.get("screen") == "PLAYING":
            return SceneTransition.none()
        return SceneTransition.none()
    
    def update_transition(self, dt: float, game_state: "GameState", ctx: dict) -> SceneTransition:
        """Update scene and return transition."""
        self.update(dt, game_state, ctx)
        return SceneTransition.none()
    
    def render(self, render_ctx: RenderContext, game_state: "GameState", ctx: dict) -> None:
        """Render shader settings screen."""
        if not HAS_MODERNGL:
            self._render_no_moderngl(render_ctx)
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
        
        # Draw preview (right) - pass model for GPU shader application
        self.preview.render_preview(
            screen,
            panel_width * 2, 0,
            preview_width, height - param_height,
            self.selected_category,
            render_ctx.font,
            render_ctx.small_font,
            model=self.model,
        )
        
        # Draw parameters (bottom)
        self._render_parameters(screen, 0, height - param_height, width, param_height, render_ctx)
        
        # Draw controls at bottom
        self._render_controls(screen, width, height, render_ctx)
        
        # Draw debug overlay if enabled
        if self.debug_overlay_enabled:
            self._render_debug_overlay(screen, render_ctx)
    
    def _render_no_moderngl(self, render_ctx: RenderContext) -> None:
        """Render fallback when moderngl not available."""
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
        
        try:
            cat_enum = RegistryCategory[self.selected_category]
            shaders = shaders_by_category.get(cat_enum, [])
        except KeyError:
            shaders = []
        
        font = render_ctx.font
        start_y = y + 20
        
        for i, shader_name in enumerate(shaders):
            enabled = self.model.is_enabled(shader_name)
            color = (100, 255, 100) if enabled else (255, 100, 100)
            if shader_name == self.selected_shader:
                pygame.draw.rect(screen, (60, 60, 100), (x + 5, start_y + i * 30 - 2, w - 10, 26))
                color = (255, 255, 100)
            
            status = "[ON]" if enabled else "[OFF]"
            text = font.render(f"{status} {shader_name}", True, color)
            screen.blit(text, (x + 10, start_y + i * 30))
    
    def _render_parameters(self, screen: pygame.Surface, x: int, y: int, w: int, h: int, render_ctx: RenderContext) -> None:
        """Render shader parameters."""
        pygame.draw.rect(screen, (25, 25, 35), (x, y, w, h))
        pygame.draw.rect(screen, (60, 60, 80), (x, y, w, h), 2)
        
        if not self.selected_shader:
            text = render_ctx.font.render("Select a shader to adjust parameters", True, (150, 150, 150))
            screen.blit(text, (x + 10, y + 10))
            return
        
        if not self._param_keys:
            self._update_param_keys()
        
        if not self._param_keys:
            text = render_ctx.font.render("No parameters available", True, (150, 150, 150))
            screen.blit(text, (x + 10, y + 10))
            return
        
        uniforms = self.model.get_uniforms(self.selected_shader)
        font = render_ctx.small_font
        start_y = y + 10
        
        for idx, key in enumerate(self._param_keys):
            value = uniforms.get(key)
            is_selected = (idx == self.selected_param_index)
            
            if is_selected:
                pygame.draw.rect(screen, (50, 60, 80), (x + 5, start_y + idx * 25 - 2, w - 10, 22))
                text_color = (255, 255, 150)
                prefix = "▶ "
            else:
                text_color = (200, 200, 200)
                prefix = "  "
            
            if isinstance(value, (int, float)):
                text = font.render(f"{prefix}{key}: {value:.2f} (+/- to adjust)", True, text_color)
            elif isinstance(value, tuple) and len(value) == 2:
                text = font.render(f"{prefix}{key}: ({value[0]:.2f}, {value[1]:.2f})", True, text_color)
            elif isinstance(value, tuple) and len(value) == 3:
                text = font.render(f"{prefix}{key}: ({value[0]:.2f}, {value[1]:.2f}, {value[2]:.2f})", True, text_color)
            else:
                text = font.render(f"{prefix}{key}: {value}", True, text_color)
            
            screen.blit(text, (x + 10, start_y + idx * 25))
    
    def _render_controls(self, screen: pygame.Surface, width: int, height: int, render_ctx: RenderContext) -> None:
        """Render control hints."""
        controls_y = height - 80
        font = render_ctx.small_font
        
        start_text = font.render("F1: Start Game", True, (150, 200, 255))
        screen.blit(start_text, (width - 250, controls_y))
        
        apply_text = font.render("Ctrl+A: Apply to Game", True, (150, 255, 150))
        screen.blit(apply_text, (width - 250, controls_y + 20))
        
        note_text = font.render("Note: these settings apply to the preview and shader-test scenes only", True, (200, 200, 150))
        screen.blit(note_text, (10, controls_y + 40))
    
    def _render_debug_overlay(self, screen: pygame.Surface, render_ctx: RenderContext) -> None:
        """Render debug overlay showing active shaders and uniforms."""
        font = render_ctx.small_font
        y = 10
        
        active = self.model.get_enabled_shaders()
        text = font.render(f"Active shaders: {', '.join(active) if active else 'None'}", True, (255, 255, 0))
        screen.blit(text, (10, y))
        y += 25
        
        if self.selected_shader:
            uniforms = self.model.get_uniforms(self.selected_shader)
            for key, value in list(uniforms.items())[:5]:
                text = font.render(f"{key} = {value}", True, (200, 200, 200))
                screen.blit(text, (10, y))
                y += 20
    
    def on_enter(self, game_state: "GameState", ctx: dict) -> None:
        """Called when scene is entered."""
        if not HAS_MODERNGL:
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Shader settings unavailable: moderngl not installed")
            return
        
        if not self.selected_category:
            categories = list(RegistryCategory)
            if categories:
                self.selected_category = categories[0].value.upper()
                shaders = shaders_by_category.get(categories[0], [])
                self.selected_shader = shaders[0] if shaders else None
                self.selected_param_index = 0
                self._param_keys = []
    
    def on_exit(self, game_state: "GameState", ctx: dict) -> None:
        """Called when scene is exited."""
        self._save_settings()
