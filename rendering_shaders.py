"""Optional shader-based gameplay rendering wrapper. Renders to offscreen then blit; ready for future GPU pass."""
from __future__ import annotations

import logging
import time
import pygame

from rendering import RenderContext
from visual_effects import apply_gameplay_effects, apply_gameplay_final_blit
from shader_effects import get_gameplay_shader_stack
from shader_effects.pipeline import ShaderPipelineManager
from shader_effects.context import ShaderContext
from typing import Callable, Optional

try:
    from gpu_gl_utils import get_gl_context, get_fullscreen_quad, gpu_upscale_surface, HAS_MODERNGL
except ImportError:
    HAS_MODERNGL = False
    get_gl_context = None  # type: ignore[assignment]
    get_fullscreen_quad = None  # type: ignore[assignment]
    gpu_upscale_surface = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Global shader pipeline (initialized on first use)
_shader_pipeline: ShaderPipelineManager | None = None

def _create_shader_render_pass(shader_name: str, uniforms: dict) -> Optional[Callable]:
    """Create a render pass function for a GPU shader."""
    if not HAS_MODERNGL:
        return None
    
    try:
        from gpu_gl_utils import get_gl_context, get_fullscreen_quad, create_utility_shader_program
        
        gl_ctx = get_gl_context()
        if gl_ctx is None:
            return None
        
        # Create shader program
        program = create_utility_shader_program(gl_ctx, shader_name)
        if program is None:
            logger.warning(f"Could not create shader program for {shader_name}")
            return None
        
        quad = get_fullscreen_quad()
        if quad is None:
            return None
        
        def render_pass(surface: pygame.Surface, dt: float, context: dict) -> pygame.Surface:
            """Render pass that applies the GPU shader to the surface."""
            try:
                # Upload surface to texture
                texture = gl_ctx.texture(surface.get_size(), 4)
                texture.write(surface.get_view("1"))
                
                # Set uniforms
                for key, value in uniforms.items():
                    try:
                        if key.startswith("u_"):
                            if isinstance(value, (int, float)):
                                program[key].value = float(value)
                            elif isinstance(value, (tuple, list)) and len(value) == 2:
                                program[key].value = tuple(float(v) for v in value)
                            elif isinstance(value, (tuple, list)) and len(value) == 3:
                                program[key].value = tuple(float(v) for v in value)
                            elif isinstance(value, (tuple, list)) and len(value) == 4:
                                program[key].value = tuple(float(v) for v in value)
                    except (KeyError, AttributeError):
                        pass  # Uniform doesn't exist in shader, skip
                
                # Set time uniform if available
                if "u_Time" in program:
                    program["u_Time"].value = context.get("time", 0.0)
                if "u_DeltaTime" in program:
                    program["u_DeltaTime"].value = context.get("delta_time", dt)
                
                # Render
                texture.use(0)
                quad.render(program)
                
                # Read back to surface (simplified - would need proper texture readback)
                # For now, return original surface (GPU path would handle this differently)
                return surface
            except Exception as e:
                logger.error(f"Error in render pass for {shader_name}: {e}")
                return surface
        
        return render_pass
    except Exception as e:
        logger.warning(f"Failed to create render pass for {shader_name}: {e}")
        return None

def apply_shader_settings_to_pipeline() -> None:
    """Apply shader settings from config/shaders.json to the gameplay shader pipeline."""
    global _shader_pipeline
    try:
        from scenes.shader_settings import load_and_apply_shader_settings_from_file, get_applied_shader_settings
        
        # Load settings from file
        load_and_apply_shader_settings_from_file()
        
        # Get the prepared shader settings
        shader_settings = get_applied_shader_settings()
        
        if not shader_settings:
            logger.info("No shader settings to apply")
            return
        
        # Initialize pipeline if needed
        if _shader_pipeline is None:
            _shader_pipeline = ShaderPipelineManager()
            logger.info("Initialized GPU shader pipeline for custom shader settings")
        
        # Clear existing shaders
        _shader_pipeline.clear()
        
        # Add enabled shaders with their uniforms
        applied_count = 0
        for shader_info in shader_settings:
            name = shader_info["name"]
            category = shader_info["category"]
            uniforms = shader_info["uniforms"]
            
            # Create render pass for this shader
            render_pass = _create_shader_render_pass(name, uniforms)
            if render_pass is not None:
                _shader_pipeline.add_shader(
                    name,
                    category,
                    render_pass,
                    default_uniforms=uniforms
                )
                applied_count += 1
            else:
                logger.warning(f"Could not create render pass for shader {name}, skipping")
        
        if applied_count > 0:
            logger.info(f"Applied {applied_count} custom shaders to gameplay pipeline")
        else:
            logger.info("No valid shaders found in settings or render passes could not be created")
    except Exception as e:
        logger.error(f"Failed to apply shader settings to pipeline: {e}", exc_info=True)

# Log rendering path once per session
_rendering_path_logged = False

def _log_rendering_path(config) -> None:
    """Log which rendering path is being used (called once per session)."""
    global _rendering_path_logged
    if _rendering_path_logged:
        return
    
    use_gpu_pipeline = (
        config is not None
        and getattr(config, "use_gpu_shader_pipeline", False)
        and HAS_MODERNGL
    )
    
    if use_gpu_pipeline and HAS_MODERNGL:
        logger.info("Using GPU shader pipeline")
    else:
        logger.info("Using CPU visual effects pipeline")
    
    _rendering_path_logged = True

_gl_start_time = time.perf_counter()

# FBO for readback (gameplay renders to this, then reads pixels to blit to pygame)
_gl_fbo = None
_gl_size: tuple[int, int] | None = None


def _gl_postprocess_offscreen_surface(offscreen_surface, render_ctx, ctx, game_state=None) -> bool:
    if not HAS_MODERNGL or get_fullscreen_quad is None or get_gl_context is None:
        return False
    try:
        width, height = offscreen_surface.get_size()
        size = (width, height)
        quad = get_fullscreen_quad(size)
        if quad is None:
            return False
        gl_ctx = get_gl_context()
        if gl_ctx is None:
            return False

        global _gl_fbo, _gl_size
        if _gl_fbo is None or _gl_size != size:
            if _gl_fbo is not None:
                try:
                    _gl_fbo.release()
                except Exception:
                    pass
                _gl_fbo = None
            try:
                out_tex = gl_ctx.texture(size, 4)
                _gl_fbo = gl_ctx.framebuffer(color_attachments=[out_tex])
                _gl_size = size
            except Exception:
                _gl_size = None
                return False

        try:
            tex_bytes = pygame.image.tostring(offscreen_surface, "RGBA", False)
        except AttributeError:
            tex_bytes = bytes(offscreen_surface.get_view("0"))
        quad.texture.write(tex_bytes)
        quad.program["u_effect"] = 1
        now = time.perf_counter()
        elapsed = float(now - _gl_start_time)
        quad.program["u_time"] = elapsed
        quad.texture.use(0)
        quad.program["u_frame_texture"] = 0
        _gl_fbo.use()
        gl_ctx.viewport = (0, 0, width, height)
        _gl_fbo.clear(0.0, 0.0, 0.0, 1.0)
        quad.render()
        data = _gl_fbo.read(components=4)
        out_surf = pygame.image.frombuffer(data, (width, height), "RGBA")
        out_surf = pygame.transform.flip(out_surf, False, True)
        # Optional damage wobble on final blit (when enable_damage_wobble and timer > 0)
        apply_gameplay_final_blit(out_surf, render_ctx.screen, ctx, game_state)
        return True
    except Exception:
        return False


_offscreen_surface = None
_offscreen_size: tuple[int, int] | None = None


def _get_offscreen_surface(render_ctx: RenderContext, size: tuple[int, int] | None = None) -> pygame.Surface:
    """Return a surface of the given size or render_ctx size; (re)create if size changed.
    When config.internal_resolution_scale < 1, pass a smaller size for CPU-based effects."""
    global _offscreen_surface, _offscreen_size
    if size is None:
        size = (render_ctx.width, render_ctx.height)
    if _offscreen_surface is None or _offscreen_size != size:
        _offscreen_surface = pygame.Surface(size).convert_alpha()
        _offscreen_surface.fill((0, 0, 0, 255))
        _offscreen_size = size
    return _offscreen_surface


def _render_gameplay_frame(render_ctx, game_state, ctx) -> None:
    """Invoke the normal gameplay renderer into the given render_ctx (caller may pass temp ctx with offscreen screen)."""
    from screens import gameplay as gameplay_screen

    gameplay_ctx = ctx.get("gameplay_ctx") if isinstance(ctx, dict) else getattr(ctx, "gameplay_ctx", None)
    if gameplay_ctx is not None:
        gameplay_screen.render(render_ctx, game_state, gameplay_ctx)


def render_gameplay_frame_to_surface(surface, width, height, font, big_font, small_font, game_state, ctx) -> None:
    """Render the raw gameplay frame into the given surface. No shaders or effects. Used for pause backdrop."""
    from systems.camera import get_camera
    temp_ctx = RenderContext(
        screen=surface,
        width=width,
        height=height,
        font=font,
        big_font=big_font,
        small_font=small_font,
        # Pass through camera and display dimensions for correct HUD positioning
        display_width=width,
        display_height=height,
        camera=get_camera(),
    )
    _render_gameplay_frame(temp_ctx, game_state, ctx)


def render_gameplay_with_optional_shaders(render_ctx, game_state, ctx) -> None:
    """
    Renders to an offscreen surface, then blits (or runs GL post-process) according to
    config.use_shaders / config.use_gpu_shaders and config.shader_profile.
    GPU path when (use_gpu_shaders or use_shaders) and profile "gl_basic".
    GPU shader pipeline when config.use_gpu_shader_pipeline is True.
    CPU effects can use config.internal_resolution_scale for a smaller offscreen, then scale up.
    """
    config = getattr(ctx, "config", None)
    if config is None and isinstance(ctx, dict):
        app_ctx = ctx.get("app_ctx")
        config = getattr(app_ctx, "config", None) if app_ctx else None
    use_shaders = bool(getattr(config, "use_shaders", False))
    use_gpu_shaders = bool(getattr(config, "use_gpu_shaders", False))
    profile = "none"
    if config is not None:
        profile = getattr(config, "shader_profile", "none")
    if profile not in ("none", "cpu_tint", "gl_basic"):
        profile = "none"
    if not use_shaders and not use_gpu_shaders:
        profile = "none"

    use_gl_path = profile == "gl_basic" and HAS_MODERNGL and (use_gpu_shaders or use_shaders)
    
    # When shaders are enabled (CPU or GPU), use full resolution for best quality
    # The GPU can handle full-res processing, and CPU effects work better at full res when GPU is helping
    use_gpu_pipeline = (
        config is not None
        and getattr(config, "use_gpu_shader_pipeline", False)
        and HAS_MODERNGL
    )
    enable_gameplay_shaders = config is not None and getattr(config, "enable_gameplay_shaders", False)
    
    # Use full resolution when shaders are enabled (CPU+GPU working together)
    # Only use reduced resolution when no shaders are enabled (pure CPU path for performance)
    if use_gpu_pipeline or enable_gameplay_shaders:
        scale = 1.0  # Full resolution when shaders are active
    elif not use_gl_path:
        scale = max(0.25, min(1.0, float(getattr(config, "internal_resolution_scale", 1.0))))
    else:
        scale = 1.0  # Full resolution for GL path
    
    # When camera is active, use display dimensions for the offscreen
    # The camera handles viewport within the world; we render at display size
    if render_ctx.camera and render_ctx.display_width and render_ctx.display_height:
        base_w = render_ctx.display_width
        base_h = render_ctx.display_height
    else:
        base_w = render_ctx.width
        base_h = render_ctx.height
    
    offscreen_w = max(1, int(base_w * scale))
    offscreen_h = max(1, int(base_h * scale))
    offscreen_size = (offscreen_w, offscreen_h)

    offscreen_surface = _get_offscreen_surface(render_ctx, offscreen_size)
    temp_ctx = RenderContext(
        screen=offscreen_surface,
        width=render_ctx.width,  # Keep world dimensions for game logic
        height=render_ctx.height,
        font=render_ctx.font,
        big_font=render_ctx.big_font,
        small_font=render_ctx.small_font,
        # HUD uses offscreen/display dimensions for positioning
        display_width=offscreen_w,
        display_height=offscreen_h,
        camera=render_ctx.camera,
    )
    offscreen_surface.fill((0, 0, 0, 255))
    _render_gameplay_frame(temp_ctx, game_state, ctx)
    
    # Log rendering path once
    _log_rendering_path(config)

    # Determine if we're using GPU pipeline
    use_gpu_pipeline = (
        config is not None
        and getattr(config, "use_gpu_shader_pipeline", False)
        and HAS_MODERNGL
    )
    
    # CPU shader stack: Apply CPU effects first (they work well as base effects)
    # When GPU pipeline is also enabled, run CPU effects at full resolution since GPU can handle the load
    cpu_effect_scale = 1.0  # Default to full resolution when GPU is available
    if config is not None and getattr(config, "enable_gameplay_shaders", False):
        gameplay_stack = get_gameplay_shader_stack(config)
        if gameplay_stack:
            t = time.perf_counter() - _gl_start_time
            eff_ctx = {"time": t}
            
            # If GPU pipeline is enabled, use full resolution for CPU effects (GPU can handle it)
            # Otherwise, use reduced resolution to maintain performance
            if use_gpu_pipeline:
                cpu_effect_scale = 1.0  # Full resolution when GPU is helping
            else:
                # CPU-only path: use reduced resolution for performance
                cpu_effect_scale = max(0.25, min(1.0, float(getattr(config, "internal_resolution_scale", 1.0))))
                if cpu_effect_scale >= 0.99:
                    cpu_effect_scale = 0.5  # default half-res for CPU-only effect chain
            
            ew = max(1, int(offscreen_w * cpu_effect_scale))
            eh = max(1, int(offscreen_h * cpu_effect_scale))
            
            if cpu_effect_scale < 1.0:
                # Scale down for CPU processing
                surf = pygame.transform.smoothscale(offscreen_surface, (ew, eh))
            else:
                # Full resolution
                surf = offscreen_surface.copy()
            
            # Apply CPU effects
            for eff in gameplay_stack:
                surf = eff.apply(surf, 0.016, eff_ctx)
            
            # Scale back up if we scaled down
            if cpu_effect_scale < 1.0:
                # Prefer GPU upscale when available to keep resolution high without CPU cost
                if HAS_MODERNGL and (use_gpu_shaders or use_shaders) and gpu_upscale_surface is not None:
                    scaled_back = gpu_upscale_surface(surf, (offscreen_w, offscreen_h))
                else:
                    scaled_back = None
                if scaled_back is None:
                    scaled_back = pygame.transform.smoothscale(surf, (offscreen_w, offscreen_h))
                offscreen_surface.blit(scaled_back, (0, 0))
            else:
                # Full resolution - blit directly
                offscreen_surface.blit(surf, (0, 0))
    
    # GPU shader pipeline: Apply GPU shaders after CPU effects (adds additional enhancement)
    # This allows CPU and GPU to work together - CPU provides base effects, GPU adds polish
    if use_gpu_pipeline:
        global _shader_pipeline
        if _shader_pipeline is None:
            _shader_pipeline = ShaderPipelineManager()
            logger.info("Initialized GPU shader pipeline")
        
        # Build shader context
        t = time.perf_counter() - _gl_start_time
        shader_ctx: ShaderContext = {
            "time": t,
            "delta_time": 0.016,
        }
        if game_state is not None:
            max_hp = max(1, getattr(game_state, "player_max_hp", 100))
            current_hp = getattr(game_state, "player_hp", 100)
            shader_ctx["health"] = current_hp / max_hp
        
        # Execute GPU shader pipeline on the CPU-processed surface
        # This allows both CPU and GPU effects to work together
        try:
            processed = _shader_pipeline.execute_pipeline(offscreen_surface, dt=0.016, context=shader_ctx)
            offscreen_surface = processed
        except Exception as e:
            logger.error(f"GPU shader pipeline failed: {e}", exc_info=True)
            # Continue with CPU-processed result if GPU fails
    
    # Lightweight CPU effects (vignette, scanlines) - apply these last as final polish
    # These are lightweight enough to run even when GPU pipeline is active
    if config is not None and getattr(config, "enable_gameplay_shaders", False):
        apply_gameplay_effects(offscreen_surface, ctx, game_state)

    if use_gl_path:
        ok = _gl_postprocess_offscreen_surface(offscreen_surface, render_ctx, ctx, game_state)
        if ok:
            return

    if profile == "cpu_tint" or (profile == "gl_basic" and (use_shaders or use_gpu_shaders)):
        overlay = pygame.Surface(offscreen_surface.get_size(), flags=pygame.SRCALPHA)
        overlay.fill((80, 0, 120, 60))  # RGBA: mild purple tint, low alpha
        offscreen_surface.blit(overlay, (0, 0))

    # Scale to display size - needed when world dimensions differ from display (camera mode)
    # or when we rendered at lower internal resolution (CPU path)
    display_w = render_ctx.display_width or render_ctx.width
    display_h = render_ctx.display_height or render_ctx.height
    offscreen_size = offscreen_surface.get_size()
    
    if offscreen_size != (display_w, display_h):
        # Scale offscreen to display dimensions
        scaled = pygame.transform.smoothscale(offscreen_surface, (display_w, display_h))
        apply_gameplay_final_blit(scaled, render_ctx.screen, ctx, game_state)
    else:
        apply_gameplay_final_blit(offscreen_surface, render_ctx.screen, ctx, game_state)
