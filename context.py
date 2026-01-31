"""Application-level context: display, timing, fonts, telemetry, and config.

Holds resources and config that are shared for the lifetime of the window.
Does NOT hold dynamic game state (entities, score, wave, etc.); that lives in GameState.

Also provides CtxHelper for typed access to the ctx dict passed through systems.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, TYPE_CHECKING

import pygame

from config.game_config import GameConfig

if TYPE_CHECKING:
    from state import GameState


# Default screen dimensions
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080


class CtxHelper:
    """Typed accessor for the ctx dictionary passed through systems and scenes.
    
    Eliminates repeated ctx.get("key", default) calls with typed properties.
    
    Usage:
        ctx_h = CtxHelper(ctx)
        width = ctx_h.width  # Instead of ctx.get("width", 1920)
        app = ctx_h.app_ctx  # Instead of ctx.get("app_ctx")
    """
    
    __slots__ = ("_ctx",)
    
    def __init__(self, ctx: dict) -> None:
        self._ctx = ctx
    
    # Display dimensions
    @property
    def width(self) -> int:
        return self._ctx.get("width", DEFAULT_WIDTH)
    
    @property
    def height(self) -> int:
        return self._ctx.get("height", DEFAULT_HEIGHT)
    
    @property
    def screen_rect(self) -> tuple[int, int, int, int]:
        """Get (0, 0, width, height) tuple."""
        return (0, 0, self.width, self.height)
    
    # Context objects
    @property
    def app_ctx(self) -> Optional["AppContext"]:
        return self._ctx.get("app_ctx")
    
    @property
    def gameplay_ctx(self) -> Optional[dict]:
        return self._ctx.get("gameplay_ctx")
    
    @property
    def render_ctx(self) -> Optional[Any]:
        return self._ctx.get("render_ctx")
    
    # Config shortcuts
    @property
    def config(self) -> Optional[GameConfig]:
        app = self.app_ctx
        return getattr(app, "config", None) if app else None
    
    @property
    def telemetry(self) -> Optional[Any]:
        app = self.app_ctx
        return getattr(app, "telemetry_client", None) if app else None
    
    @property
    def event_bus(self) -> Optional[Any]:
        app = self.app_ctx
        return getattr(app, "event_bus", None) if app else None
    
    @property
    def map_manager(self) -> Optional[Any]:
        app = self.app_ctx
        return getattr(app, "map_manager", None) if app else None
    
    # Gameplay state shortcuts
    @property
    def player(self) -> Optional[Any]:
        """Get player from gameplay_ctx."""
        gctx = self.gameplay_ctx
        return gctx.get("player") if gctx else None
    
    @property
    def enemies(self) -> list:
        """Get enemies list from gameplay_ctx."""
        gctx = self.gameplay_ctx
        return gctx.get("enemies", []) if gctx else []
    
    @property
    def projectiles(self) -> list:
        """Get projectiles list from gameplay_ctx."""
        gctx = self.gameplay_ctx
        return gctx.get("projectiles", []) if gctx else []
    
    # Camera
    @property
    def camera_offset(self) -> tuple[float, float]:
        """Get camera offset (default 0, 0)."""
        gctx = self.gameplay_ctx
        if gctx:
            return (gctx.get("camera_offset_x", 0.0), gctx.get("camera_offset_y", 0.0))
        return (0.0, 0.0)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Fallback for custom keys."""
        return self._ctx.get(key, default)
    
    def __getitem__(self, key: str) -> Any:
        """Dict-like access for compatibility."""
        return self._ctx[key]
    
    def __contains__(self, key: str) -> bool:
        """Support 'in' operator."""
        return key in self._ctx


@dataclass
class AppContext:
    """Application-level resources and configuration.

    Created after Pygame init and passed into the main loop and screen/context
    consumers. Contains only true app-level resources and config, not
    per-run game state.
    """
    # Display and timing (from pygame)
    screen: pygame.Surface  # The actual display surface
    clock: pygame.time.Clock
    font: pygame.font.Font
    big_font: pygame.font.Font
    small_font: pygame.font.Font

    # Display dimensions (actual screen/window size)
    display_width: int = 0
    display_height: int = 0
    
    # World dimensions (may be larger than display if world_scale > 1.0)
    # This is the actual playable area size
    width: int = 0  # World width (used by game logic)
    height: int = 0  # World height (used by game logic)
    
    # World render surface (larger than display when world_scale > 1.0)
    # Render to this, then scale down to screen
    world_surface: pygame.Surface = None
    
    # Cached offscreen surface for pause/menu shader effects (avoids per-frame allocation)
    # Recreated when display dimensions change
    _offscreen_surface: Optional[pygame.Surface] = None
    _offscreen_size: tuple[int, int] = (0, 0)

    # Telemetry (optional; None or no-op when disabled). Enable/disable is in config.
    telemetry_client: Optional[Any] = None  # Telemetry | NoOpTelemetry
    last_telemetry_sample_t: float = -1.0  # per-frame sampling clock; updated by telemetry_system

    # Run timestamp for telemetry (ISO string when a run starts)
    run_started_at: Optional[str] = None

    # Key bindings (loaded once per run from controls file)
    controls: dict[str, int] = field(default_factory=dict)

    # Centralized game options (difficulty, player class, aim mode, toggles).
    # Graphics/performance: config.graphics_preset, config.use_gpu_physics, config.use_gpu_shaders, config.internal_resolution_scale.
    config: GameConfig = field(default_factory=GameConfig)

    # Physics backend: True if C-accelerated game_physics is in use, False if Python fallback
    using_c_physics: bool = False

    # Event bus for decoupling systems (optional; None or no-op when not set)
    event_bus: Optional[Any] = None
    
    # Map manager for tile-based maps (optional; None when not in use)
    map_manager: Optional[Any] = None
    
    def get_world_mouse_pos(self) -> tuple[int, int]:
        """Get mouse position in world coordinates (scaled from display coordinates).
        
        When world_scale > 1.0, the world is larger than the display.
        This converts display mouse position to world coordinates.
        """
        display_x, display_y = pygame.mouse.get_pos()
        world_scale = getattr(self.config, 'world_scale', 1.0) if self.config else 1.0
        if world_scale > 1.0 and self.display_width > 0 and self.display_height > 0:
            # Scale mouse position from display space to world space
            world_x = int(display_x * world_scale)
            world_y = int(display_y * world_scale)
            return (world_x, world_y)
        return (display_x, display_y)
    
    def get_offscreen_surface(self, width: int, height: int) -> pygame.Surface:
        """Get a cached offscreen surface for pause/menu shader effects.
        
        The surface is recreated only when dimensions change.
        Returns a surface with convert_alpha() for transparency support.
        """
        if self._offscreen_surface is None or self._offscreen_size != (width, height):
            self._offscreen_surface = pygame.Surface((width, height)).convert_alpha()
            self._offscreen_size = (width, height)
        return self._offscreen_surface
