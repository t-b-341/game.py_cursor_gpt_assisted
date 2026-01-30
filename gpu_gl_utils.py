"""Shared moderngl helpers: context, fullscreen quad geometry, texture, and a basic program.
Used by ShaderTestScene and rendering_shaders for post-process.
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Optional, Tuple, Dict, List

try:
    import moderngl  # type: ignore[import-untyped]
    HAS_MODERNGL = True
except ImportError:
    moderngl = None  # type: ignore[assignment]
    HAS_MODERNGL = False

# Export HAS_MODERNGL as public constant
__all__ = ["HAS_MODERNGL", "get_gl_context", "get_fullscreen_quad", "gpu_upscale_surface",
           "load_shader_file", "register_utility_shader", "get_utility_shader",
           "create_utility_shader_program", "get_shaders_by_category", "get_all_categories",
           "get_all_shaders", "ShaderCategory"]

_gl_ctx: Optional["moderngl.Context"] = None

# Shader categories (DEPRECATED: use shader_effects.registry.ShaderCategory instead)
# Kept for backward compatibility with gpu_gl_utils registration
class ShaderCategory:
    """Shader category constants."""
    CORE = "CORE"
    ATMOSPHERE = "ATMOSPHERE"
    RETRO = "RETRO"
    COMBAT = "COMBAT"
    WATER = "WATER"
    OUTLINES = "OUTLINES"
    LIGHTING = "LIGHTING"
    DEBUG = "DEBUG"

# Utility shader registry: name -> (vertex_shader_source, fragment_shader_source, category)
_utility_shaders: Dict[str, Tuple[str, str, str]] = {}

# Fullscreen quad NDC pos+uv, triangle strip (same layout for all callers)
QUAD_POS_UV = struct.pack(
    "16f",
    -1.0, -1.0, 0.0, 0.0,
    1.0, -1.0, 1.0, 0.0,
    -1.0, 1.0, 0.0, 1.0,
    1.0, 1.0, 1.0, 1.0,
)

VERTEX_SHADER = """
#version 330
in vec2 in_pos;
in vec2 in_uv;
out vec2 v_uv;
void main() {
    gl_Position = vec4(in_pos, 0.0, 1.0);
    v_uv = in_uv;
}
"""

# u_effect: 0 = shader_test (desaturate), 1 = gameplay (contrast + pulse), 2 = passthrough/upscale
FRAGMENT_SHADER = """
#version 330
uniform sampler2D u_frame_texture;
uniform float u_time;
uniform int u_effect;
in vec2 v_uv;
out vec4 fragColor;
void main() {
    vec4 c = texture(u_frame_texture, v_uv);
    if (u_effect == 0) {
        float gray = dot(c.rgb, vec3(0.299, 0.587, 0.114));
        vec3 mixed = mix(c.rgb, vec3(gray), 0.3);
        fragColor = vec4(mixed, c.a);
    } else if (u_effect == 1) {
        vec2 centered = v_uv - 0.5;
        float dist = length(centered);
        float vignette = smoothstep(0.7, 0.3, dist);
        float pulse = 0.9 + 0.1 * sin(u_time * 2.0);
        vec3 base = c.rgb * pulse;
        vec3 final_rgb = base * vignette;
        fragColor = vec4(final_rgb, c.a);
    } else {
        fragColor = c;
    }
}
"""


def get_gl_context() -> Optional["moderngl.Context"]:
    global _gl_ctx
    if moderngl is None:
        return None
    if _gl_ctx is None:
        try:
            _gl_ctx = moderngl.create_context()
        except Exception:
            _gl_ctx = None
    return _gl_ctx


class FullscreenQuad:
    """Holds texture, VBO, VAO, and program for a fullscreen quad at a given size."""

    def __init__(self, ctx: "moderngl.Context", size: Tuple[int, int]) -> None:
        self.ctx = ctx
        self.size = size
        self.texture = ctx.texture(size, 4)
        self.vbo = ctx.buffer(QUAD_POS_UV)
        self.program = ctx.program(
            vertex_shader=VERTEX_SHADER,
            fragment_shader=FRAGMENT_SHADER,
        )
        self.vao = ctx.vertex_array(
            self.program,
            [(self.vbo, "2f 2f", "in_pos", "in_uv")],
        )

    def ensure_size(self, size: Tuple[int, int]) -> None:
        if size == self.size:
            return
        try:
            self.texture.release()
        except Exception:
            pass
        self.size = size
        self.texture = self.ctx.texture(size, 4)

    def render(self) -> None:
        if moderngl is not None:
            self.vao.render(moderngl.TRIANGLE_STRIP)


_quad_cache: dict[Tuple[int, int], "FullscreenQuad"] = {}
_upscale_fbo = None
_upscale_fbo_size: Optional[Tuple[int, int]] = None


def gpu_upscale_surface(surface: "object", target_size: Tuple[int, int]) -> Optional["object"]:
    """Upscale a pygame Surface to target_size on the GPU (bilinear). Returns new Surface or None on failure."""
    global _upscale_fbo, _upscale_fbo_size
    try:
        import pygame
    except ImportError:
        return None
    ctx = get_gl_context()
    if ctx is None:
        return None
    src_size = (surface.get_width(), surface.get_height())
    if src_size[0] < 1 or src_size[1] < 1 or target_size[0] < 1 or target_size[1] < 1:
        return None
    quad = get_fullscreen_quad(src_size)
    if quad is None:
        return None
    if _upscale_fbo is None or _upscale_fbo_size != target_size:
        if _upscale_fbo is not None:
            try:
                _upscale_fbo.release()
            except Exception:
                pass
            _upscale_fbo = None
        try:
            out_tex = ctx.texture(target_size, 4)
            _upscale_fbo = ctx.framebuffer(color_attachments=[out_tex])
            _upscale_fbo_size = target_size
        except Exception:
            _upscale_fbo_size = None
            return None
    try:
        tex_bytes = pygame.image.tostring(surface, "RGBA", False)
    except Exception:
        try:
            tex_bytes = bytes(surface.get_view("0"))
        except Exception:
            return None
    quad.texture.write(tex_bytes)
    quad.program["u_effect"] = 2
    quad.texture.use(0)
    quad.program["u_frame_texture"] = 0
    _upscale_fbo.use()
    ctx.viewport = (0, 0, target_size[0], target_size[1])
    _upscale_fbo.clear(0.0, 0.0, 0.0, 1.0)
    quad.render()
    data = _upscale_fbo.read(components=4)
    out_surf = pygame.image.frombuffer(data, target_size, "RGBA")
    out_surf = pygame.transform.flip(out_surf, False, True)
    return out_surf


def get_fullscreen_quad(size: Tuple[int, int]) -> Optional["FullscreenQuad"]:
    ctx = get_gl_context()
    if ctx is None:
        return None
    if size not in _quad_cache:
        _quad_cache[size] = FullscreenQuad(ctx, size)
    else:
        _quad_cache[size].ensure_size(size)
    return _quad_cache[size]


def load_shader_file(shader_path: str | Path) -> Optional[str]:
    """
    Load a shader file from disk.
    
    Args:
        shader_path: Path to the shader file (relative to project root or absolute)
    
    Returns:
        Shader source code as string, or None if file not found or error occurred
    
    Uses get_resource_path() for PyInstaller compatibility.
    """
    from resource_paths import get_resource_path
    
    try:
        path = Path(shader_path)
        
        # If absolute path, use directly
        if path.is_absolute():
            if path.exists():
                return path.read_text(encoding="utf-8")
            else:
                print(f"[Shader] File not found: {shader_path}")
                return None
        
        # Try using get_resource_path (works for both dev and PyInstaller)
        resolved_path = Path(get_resource_path(str(shader_path)))
        if resolved_path.exists():
            return resolved_path.read_text(encoding="utf-8")
        
        # Fallback: try relative to project root
        project_root = Path(__file__).resolve().parent
        fallback_path = project_root / path
        if fallback_path.exists():
            return fallback_path.read_text(encoding="utf-8")
        
        # Fallback: try assets/shaders directory
        assets_path = project_root / "assets" / "shaders" / Path(shader_path).name
        if assets_path.exists():
            return assets_path.read_text(encoding="utf-8")
        
        # Last resort: try get_resource_path with just the filename in assets/shaders
        if not str(shader_path).startswith("assets"):
            shader_name = Path(shader_path).name
            resolved_assets_path = Path(get_resource_path(f"assets/shaders/{shader_name}"))
            if resolved_assets_path.exists():
                return resolved_assets_path.read_text(encoding="utf-8")
        
        print(f"[Shader] File not found: {shader_path}")
        return None
    except Exception as e:
        print(f"[Shader] Error loading {shader_path}: {e}")
        return None


def register_utility_shader(
    name: str,
    vertex_shader: Optional[str] = None,
    fragment_shader: Optional[str] = None,
    category: str = ShaderCategory.CORE,
) -> bool:
    """
    Register a utility shader that can be used for post-processing.
    
    Args:
        name: Unique name for the shader (e.g., "blur")
        vertex_shader: Vertex shader source code (uses default if None)
        fragment_shader: Fragment shader source code or path to .frag file
        category: Shader category (default: CORE)
    
    Returns:
        True if registration successful, False otherwise
    """
    if not HAS_MODERNGL:
        print(f"[Shader] Cannot register utility shader '{name}': moderngl not available")
        return False
    
    # Use default vertex shader if not provided
    vert_src = vertex_shader if vertex_shader is not None else VERTEX_SHADER
    
    # Load fragment shader from file if it looks like a path
    frag_src = fragment_shader
    if frag_src and (frag_src.endswith(".frag") or "/" in frag_src or "\\" in frag_src):
        loaded = load_shader_file(frag_src)
        if loaded is None:
            return False
        frag_src = loaded
    
    if frag_src is None:
        print(f"[Shader] Fragment shader required for utility shader '{name}'")
        return False
    
    _utility_shaders[name] = (vert_src, frag_src, category)
    print(f"[Shader] Registered utility shader: {name} (category: {category})")
    return True


def get_utility_shader(name: str) -> Optional[Tuple[str, str, str]]:
    """
    Get a registered utility shader by name.
    
    Args:
        name: Shader name (e.g., "blur")
    
    Returns:
        Tuple of (vertex_shader_source, fragment_shader_source, category) or None if not found
    """
    return _utility_shaders.get(name)


def get_shaders_by_category(category: str) -> List[str]:
    """
    Get all shader names in a specific category.
    
    Args:
        category: Category name (e.g., ShaderCategory.CORE)
    
    Returns:
        List of shader names in that category
    """
    return [name for name, (_, _, cat) in _utility_shaders.items() if cat == category]


def get_all_categories() -> List[str]:
    """
    Get all unique shader categories.
    
    Returns:
        List of category names
    """
    categories = set(cat for _, _, cat in _utility_shaders.values())
    return sorted(list(categories))


def get_all_shaders() -> Dict[str, str]:
    """
    Get all registered shaders with their categories.
    
    Returns:
        Dictionary mapping shader name to category
    """
    return {name: cat for name, (_, _, cat) in _utility_shaders.items()}


def create_utility_shader_program(ctx: "moderngl.Context", name: str) -> Optional["moderngl.Program"]:
    """
    Create a moderngl Program from a registered utility shader.
    
    Args:
        ctx: moderngl context
        name: Shader name (e.g., "blur")
    
    Returns:
        moderngl.Program or None if shader not found or creation failed
    """
    shader_sources = get_utility_shader(name)
    if shader_sources is None:
        print(f"[Shader] Utility shader '{name}' not found")
        return None
    
    vert_src, frag_src, _ = shader_sources
    try:
        return ctx.program(vertex_shader=vert_src, fragment_shader=frag_src)
    except Exception as e:
        print(f"[Shader] Failed to create program for '{name}': {e}")
        return None


# Register built-in utility shaders on module load
def _register_builtin_utility_shaders() -> None:
    """Register built-in utility shaders with categories."""
    if not HAS_MODERNGL:
        return
    
    # Core utility shaders
    register_utility_shader("blur", fragment_shader="assets/shaders/blur.frag", category=ShaderCategory.CORE)
    
    # Atmosphere effects
    register_utility_shader("vignette", fragment_shader="assets/shaders/vignette.frag", category=ShaderCategory.ATMOSPHERE)
    register_utility_shader("gradient_fog", fragment_shader="assets/shaders/gradient_fog.frag", category=ShaderCategory.ATMOSPHERE)
    register_utility_shader("film_grain", fragment_shader="assets/shaders/film_grain.frag", category=ShaderCategory.ATMOSPHERE)
    
    # Retro effects
    register_utility_shader("pixelate", fragment_shader="assets/shaders/pixelate.frag", category=ShaderCategory.RETRO)
    register_utility_shader("crt_scanlines", fragment_shader="assets/shaders/crt_scanlines.frag", category=ShaderCategory.RETRO)
    register_utility_shader("chromatic_aberration", fragment_shader="assets/shaders/chromatic_aberration.frag", category=ShaderCategory.RETRO)
    
    # Combat effects
    register_utility_shader("shockwave", fragment_shader="assets/shaders/shockwave.frag", category=ShaderCategory.COMBAT)
    register_utility_shader("screenshake", fragment_shader="assets/shaders/screenshake.frag", category=ShaderCategory.COMBAT)
    register_utility_shader("time_warp", fragment_shader="assets/shaders/time_warp.frag", category=ShaderCategory.COMBAT)
    register_utility_shader("shockwave_sprite", fragment_shader="assets/shaders/shockwave_sprite.frag", category=ShaderCategory.COMBAT)
    
    # Water effects
    register_utility_shader("water_ripple", fragment_shader="assets/shaders/water_ripple.frag", category=ShaderCategory.WATER)
    register_utility_shader("distortion", fragment_shader="assets/shaders/distortion.frag", category=ShaderCategory.WATER)
    
    # Outlines
    register_utility_shader("edge_detect", fragment_shader="assets/shaders/edge_detect.frag", category=ShaderCategory.OUTLINES)
    
    # Lighting
    register_utility_shader("lighting", fragment_shader="assets/shaders/lighting.frag", category=ShaderCategory.LIGHTING)
    register_utility_shader("radial_light_mask", fragment_shader="assets/shaders/radial_light_mask.frag", category=ShaderCategory.LIGHTING)
    register_utility_shader("additive_light", fragment_shader="assets/shaders/additive_light.frag", category=ShaderCategory.LIGHTING)
    
    # Bloom pipeline shaders (CORE)
    register_utility_shader("bloom_extract", fragment_shader="assets/shaders/bloom_extract.frag", category=ShaderCategory.CORE)
    register_utility_shader("bloom_combine", fragment_shader="assets/shaders/bloom_combine.frag", category=ShaderCategory.CORE)
    
    # Color grading (ATMOSPHERE)
    register_utility_shader("color_grade", fragment_shader="assets/shaders/color_grade.frag", category=ShaderCategory.ATMOSPHERE)


# Auto-register on import
_register_builtin_utility_shaders()
