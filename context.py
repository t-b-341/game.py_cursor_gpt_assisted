"""Application-level context: display, timing, fonts, telemetry, and config.

Holds resources and config that are shared for the lifetime of the window.
Does NOT hold dynamic game state (entities, score, wave, etc.); that lives in GameState.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pygame

from config.game_config import GameConfig


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
