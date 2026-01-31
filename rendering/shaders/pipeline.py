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

# Debug message counter (limit console spam)
_gpu_debug_count: int = 0

def _create_shader_render_pass(shader_name: str, uniforms: dict) -> Optional[Callable]:
    """Create a render pass function for a GPU shader.
    
    Creates a framebuffer-based render pass that:
    1. Uploads the input surface to a texture
    2. Renders to a framebuffer using the shader
    3. Reads back the result to a pygame surface (cached for performance)
    
    Performance optimizations:
    - FBO/texture caching per size
    - Output surface reuse
    - Early-out when effect is inactive (via _skip_particle_effect context flag)
    """
    if not HAS_MODERNGL:
        logger.debug(f"Cannot create render pass for {shader_name}: moderngl not available")
        return None
    
    try:
        from gpu_gl_utils import get_gl_context, create_utility_shader_program
        import moderngl
        
        gl_ctx = get_gl_context()
        if gl_ctx is None:
            logger.debug(f"Cannot create render pass for {shader_name}: GL context is None")
            # Try creating a standalone context
            try:
                gl_ctx = moderngl.create_standalone_context()
                logger.debug(f"Created standalone context for {shader_name}")
            except Exception as e:
                logger.debug(f"Failed to create standalone context: {e}")
                return None
        
        # Create shader program
        program = create_utility_shader_program(gl_ctx, shader_name)
        if program is None:
            logger.debug(f"Could not create shader program for {shader_name}")
            return None
        
        logger.debug(f"Created shader program for {shader_name}")
        
        # Cache for FBO, textures, and output surfaces (per size)
        fbo_cache: dict = {}
        
        def render_pass(surface: pygame.Surface, dt: float, context: dict) -> pygame.Surface:
            """Render pass that applies the GPU shader to the surface."""
            nonlocal fbo_cache
            
            # Early-out optimization: skip GPU work entirely when no effect active
            # This avoids expensive texture upload/download when not needed
            if context.get("_skip_particle_effect", False):
                return surface
            
            # Debug: confirm render pass is being called (uses global counter)
            global _gpu_debug_count
            strength = context.get("u_shot_strength", 0)
            if _gpu_debug_count < 15:
                logger.debug(f"Render pass called for {shader_name}, strength={strength:.3f}")
            
            try:
                size = surface.get_size()
                if size[0] < 1 or size[1] < 1:
                    return surface
                
                # Get or create FBO for this size
                if size not in fbo_cache:
                    out_tex = gl_ctx.texture(size, 4)
                    out_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
                    fbo = gl_ctx.framebuffer(color_attachments=[out_tex])
                    
                    # Create input texture
                    in_tex = gl_ctx.texture(size, 4)
                    in_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
                    
                    # Create vertex buffer and VAO for this program
                    import struct
                    quad_data = struct.pack(
                        "16f",
                        -1.0, -1.0, 0.0, 0.0,
                         1.0, -1.0, 1.0, 0.0,
                        -1.0,  1.0, 0.0, 1.0,
                         1.0,  1.0, 1.0, 1.0,
                    )
                    vbo = gl_ctx.buffer(quad_data)
                    vao = gl_ctx.vertex_array(
                        program,
                        [(vbo, "2f 2f", "in_pos", "in_uv")],
                    )
                    
                    # Pre-allocate output surface for reuse
                    out_surf = pygame.Surface(size, pygame.SRCALPHA)
                    
                    fbo_cache[size] = {
                        "fbo": fbo,
                        "out_tex": out_tex,
                        "in_tex": in_tex,
                        "vao": vao,
                        "vbo": vbo,
                        "out_surf": out_surf,
                    }
                
                cache = fbo_cache[size]
                fbo = cache["fbo"]
                in_tex = cache["in_tex"]
                vao = cache["vao"]
                out_surf = cache["out_surf"]
                
                # Upload surface to input texture
                try:
                    tex_bytes = pygame.image.tostring(surface, "RGBA", False)
                except Exception as e:
                    logger.debug(f"tostring fallback: {e}")
                    tex_bytes = bytes(surface.get_view("0"))
                in_tex.write(tex_bytes)
                
                # Set uniforms from context (dynamic values like shot position)
                for key, value in context.items():
                    try:
                        if key.startswith("u_") and key in program:
                            if isinstance(value, (int, float)):
                                program[key].value = float(value)
                            elif isinstance(value, (tuple, list)) and len(value) == 2:
                                program[key].value = tuple(float(v) for v in value)
                            elif isinstance(value, (tuple, list)) and len(value) == 3:
                                program[key].value = tuple(float(v) for v in value)
                            elif isinstance(value, (tuple, list)) and len(value) == 4:
                                program[key].value = tuple(float(v) for v in value)
                    except (KeyError, AttributeError):
                        pass
                
                # Set time uniform
                if "u_Time" in program:
                    program["u_Time"].value = context.get("time", 0.0)
                if "u_DeltaTime" in program:
                    program["u_DeltaTime"].value = context.get("delta_time", dt)
                
                # Set texture uniform
                if "u_frame_texture" in program:
                    program["u_frame_texture"].value = 0
                
                # Render to FBO
                fbo.use()
                gl_ctx.viewport = (0, 0, size[0], size[1])
                fbo.clear(0.0, 0.0, 0.0, 1.0)
                in_tex.use(0)
                vao.render(moderngl.TRIANGLE_STRIP)
                
                # Read back result to cached surface
                # OpenGL FBO read returns rows bottom-to-top, but since we uploaded
                # pygame data with row 0 at GL bottom (tostring flipped=False), the
                # rendered FBO has the image upside-down. FBO.read() returns this
                # upside-down image with the visual bottom first, which corresponds
                # to the original top. So the read data is actually in pygame order
                # and should NOT be flipped again.
                data = fbo.read(components=4)
                temp_surf = pygame.image.frombuffer(data, size, "RGBA")
                out_surf.blit(temp_surf, (0, 0))  # No flip needed
                
                if _gpu_debug_count < 15:
                    logger.debug(f"Render pass complete, output size={out_surf.get_size()}")
                return out_surf
            except Exception as e:
                logger.error(f"Error in render pass for {shader_name}: {e}", exc_info=True)
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
                except Exception as e:
                    logger.debug(f"FBO release error (ignored): {e}")
                _gl_fbo = None
            try:
                out_tex = gl_ctx.texture(size, 4)
                _gl_fbo = gl_ctx.framebuffer(color_attachments=[out_tex])
                _gl_size = size
            except Exception as e:
                logger.warning(f"Failed to create FBO: {e}")
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
    except Exception as e:
        logger.debug(f"GPU shader pass failed (falling back to CPU): {e}")
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


def _apply_cpu_shader_effects(
    offscreen_surface: pygame.Surface,
    offscreen_w: int,
    offscreen_h: int,
    config,
    use_shaders: bool,
    use_gpu_shaders: bool,
) -> None:
    """Apply CPU shader stack effects to offscreen surface (in-place).
    
    This is the heavy CPU path that runs when GPU pipeline is NOT active.
    Uses reduced resolution for performance, then scales back up.
    """
    gameplay_stack = get_gameplay_shader_stack(config)
    if not gameplay_stack:
        return
    
    t = time.perf_counter() - _gl_start_time
    eff_ctx = {"time": t}
    
    # CPU-only path: use reduced resolution for performance
    cpu_effect_scale = max(0.25, min(1.0, float(getattr(config, "internal_resolution_scale", 1.0))))
    if cpu_effect_scale >= 0.99:
        cpu_effect_scale = 0.5  # default half-res for CPU-only effect chain
    
    ew = max(1, int(offscreen_w * cpu_effect_scale))
    eh = max(1, int(offscreen_h * cpu_effect_scale))
    
    if cpu_effect_scale < 1.0:
        surf = pygame.transform.smoothscale(offscreen_surface, (ew, eh))
    else:
        surf = offscreen_surface.copy()
    
    # Apply CPU effects
    for eff in gameplay_stack:
        surf = eff.apply(surf, 0.016, eff_ctx)
    
    # Scale back up if we scaled down
    if cpu_effect_scale < 1.0:
        # Prefer GPU upscale when available
        if HAS_MODERNGL and (use_gpu_shaders or use_shaders) and gpu_upscale_surface is not None:
            scaled_back = gpu_upscale_surface(surf, (offscreen_w, offscreen_h))
        else:
            scaled_back = None
        if scaled_back is None:
            scaled_back = pygame.transform.smoothscale(surf, (offscreen_w, offscreen_h))
        offscreen_surface.blit(scaled_back, (0, 0))
    else:
        offscreen_surface.blit(surf, (0, 0))


def _apply_gpu_visual_effects(
    offscreen_surface: pygame.Surface,
    game_state,
    render_ctx,
) -> None:
    """Apply lightweight GPU-path visual effects (muzzle flash, rocket glows)."""
    from systems.shot_particle_state import get_shot_particle_state
    
    shot_state = get_shot_particle_state()
    shot_state.update(0.016)
    shot_pos, shot_strength, effect_radius = shot_state.get_uniforms()
    
    # Render muzzle flash (skip rockets - they have their own glow)
    if shot_strength > 0.01 and effect_radius < 1.4:
        _render_cpu_shot_flash(offscreen_surface, shot_pos, shot_strength, effect_radius)
    
    # Render glowing spheres following rockets
    camera = getattr(render_ctx, "camera", None)
    _render_rocket_glows(offscreen_surface, game_state, camera)


def _render_cpu_shot_flash(surface: pygame.Surface, shot_pos: tuple, strength: float, radius_mult: float) -> None:
    """Render a small CPU-based muzzle flash at the shot position.
    
    Args:
        surface: The surface to draw on
        shot_pos: Normalized (0-1) screen position
        strength: Effect strength (0-1+, fades over time)
        radius_mult: Radius multiplier (1.0 for shot, 1.5 for rocket, 2.5 for bomb)
    """
    if strength <= 0.01:
        return
    
    w, h = surface.get_size()
    
    # Convert normalized position to screen pixels
    center_x = int(shot_pos[0] * w)
    center_y = int(shot_pos[1] * h)
    
    # Much smaller radius - just a subtle muzzle flash
    base_radius = 12  # Fixed small size
    radius = int(base_radius * min(radius_mult, 1.5) * (0.6 + strength * 0.4))
    
    if radius < 3:
        return
    
    # Create a small surface for the flash effect with alpha
    flash_size = radius * 2
    flash_surf = pygame.Surface((flash_size, flash_size), pygame.SRCALPHA)
    
    # Draw concentric circles for soft glow
    base_color = (255, 240, 200)  # Warm white-yellow
    
    num_rings = min(4, max(2, radius // 3))
    for i in range(num_rings, 0, -1):
        ring_radius = int(radius * i / num_rings)
        alpha = int(120 * strength * (i / num_rings) ** 2)
        alpha = min(255, max(0, alpha))
        
        color = (*base_color, alpha)
        pygame.draw.circle(flash_surf, color, (radius, radius), ring_radius)
    
    # Blit the flash onto the main surface
    blit_x = center_x - radius
    blit_y = center_y - radius
    surface.blit(flash_surf, (blit_x, blit_y), special_flags=pygame.BLEND_RGBA_ADD)


def _render_rocket_glow(surface: pygame.Surface, rocket_x: int, rocket_y: int, time_offset: float = 0.0) -> None:
    """Render a fading glowing sphere effect at a rocket's position.
    
    Args:
        surface: The surface to draw on
        rocket_x: Rocket center X in screen coordinates
        rocket_y: Rocket center Y in screen coordinates
        time_offset: Optional time offset for pulse variation
    """
    import math
    
    # Pulsing radius for organic feel
    pulse = 0.85 + 0.15 * math.sin(time_offset * 8.0)
    base_radius = int(18 * pulse)  # Small glowing sphere
    
    if base_radius < 4:
        return
    
    # Create glow surface
    glow_size = base_radius * 2 + 4
    glow_surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
    center = glow_size // 2
    
    # Draw glowing sphere with multiple layers for smooth falloff
    # Outer glow - orange/red
    outer_color = (255, 120, 50, 40)
    pygame.draw.circle(glow_surf, outer_color, (center, center), base_radius + 2)
    
    # Middle glow - orange
    mid_color = (255, 160, 80, 80)
    pygame.draw.circle(glow_surf, mid_color, (center, center), int(base_radius * 0.75))
    
    # Inner core - bright yellow-white
    inner_color = (255, 220, 150, 140)
    pygame.draw.circle(glow_surf, inner_color, (center, center), int(base_radius * 0.45))
    
    # Bright center
    core_color = (255, 255, 220, 180)
    pygame.draw.circle(glow_surf, core_color, (center, center), int(base_radius * 0.25))
    
    # Blit with additive blending
    blit_x = rocket_x - center
    blit_y = rocket_y - center
    surface.blit(glow_surf, (blit_x, blit_y), special_flags=pygame.BLEND_RGBA_ADD)


def _render_rocket_glows(surface: pygame.Surface, game_state, camera) -> None:
    """Render glowing spheres following all active missiles (R key).
    
    Args:
        surface: The surface to draw on
        game_state: Game state containing missiles list
        camera: Camera for world-to-screen conversion
    """
    import time
    
    if game_state is None:
        return
    
    # Missiles are stored in state.missiles (R key seeking missiles)
    missiles = getattr(game_state, "missiles", [])
    if not missiles:
        return
    
    current_time = time.perf_counter()
    
    for missile in missiles:
        rect = missile.get("rect")
        if rect is None:
            continue
        
        # Convert world position to screen position
        world_x, world_y = rect.centerx, rect.centery
        
        if camera:
            screen_x = world_x - camera.x
            screen_y = world_y - camera.y
        else:
            screen_x = world_x
            screen_y = world_y
        
        # Use missile id for time offset variation (makes each pulse slightly different)
        time_offset = current_time + hash(id(missile)) * 0.001
        
        _render_rocket_glow(surface, int(screen_x), int(screen_y), time_offset)


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
    
    # CPU shader stack: Apply CPU effects (heavy - only when explicitly enabled and GPU pipeline NOT active)
    if config is not None and getattr(config, "enable_gameplay_shaders", False) and not use_gpu_pipeline:
        _apply_cpu_shader_effects(offscreen_surface, offscreen_w, offscreen_h, config, use_shaders, use_gpu_shaders)
    
    # GPU path: lightweight visual effects (muzzle flash, rocket glows)
    if use_gpu_pipeline:
        _apply_gpu_visual_effects(offscreen_surface, game_state, render_ctx)
    
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
