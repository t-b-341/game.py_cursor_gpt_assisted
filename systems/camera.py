"""Camera system for viewport management.

The camera follows the player and provides world-to-screen coordinate conversion.
Entities outside the viewport can be culled for performance.

Usage:
    camera = Camera(display_width, display_height, world_width, world_height)
    camera.follow(player_rect, dt)
    
    # In rendering:
    screen_x, screen_y = camera.world_to_screen(world_x, world_y)
    if camera.is_visible(entity_rect):
        # render entity
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    pass


@dataclass
class Camera:
    """Viewport camera that follows a target and handles coordinate conversion.
    
    Attributes:
        display_width: Width of the display/screen in pixels
        display_height: Height of the display/screen in pixels
        world_width: Width of the game world in pixels
        world_height: Height of the game world in pixels
        x: Camera X position (top-left of viewport in world coords)
        y: Camera Y position (top-left of viewport in world coords)
        smoothing: Camera follow smoothing (0 = instant, higher = smoother)
        margin: Pixels of margin around viewport for culling (render slightly off-screen)
    """
    display_width: int
    display_height: int
    world_width: int
    world_height: int
    x: float = 0.0
    y: float = 0.0
    smoothing: float = 8.0  # Lerp speed (higher = faster follow)
    margin: int = 64  # Extra margin for culling (entities slightly off-screen still render)
    
    # Performance tracking
    entities_total: int = field(default=0, repr=False)
    entities_culled: int = field(default=0, repr=False)
    
    def __post_init__(self):
        """Center camera on world initially."""
        self.x = max(0, (self.world_width - self.display_width) // 2)
        self.y = max(0, (self.world_height - self.display_height) // 2)
    
    @property
    def viewport(self) -> pygame.Rect:
        """Get the current viewport rectangle in world coordinates."""
        return pygame.Rect(int(self.x), int(self.y), self.display_width, self.display_height)
    
    @property
    def viewport_with_margin(self) -> pygame.Rect:
        """Get viewport with margin for culling (slightly larger than visible area)."""
        return pygame.Rect(
            int(self.x) - self.margin,
            int(self.y) - self.margin,
            self.display_width + self.margin * 2,
            self.display_height + self.margin * 2
        )
    
    def follow(self, target_rect: pygame.Rect, dt: float) -> None:
        """Move camera to follow a target (typically the player).
        
        Uses smooth interpolation for natural camera movement.
        Camera is clamped to world bounds.
        
        Args:
            target_rect: The rect to follow (camera centers on this)
            dt: Delta time in seconds
        """
        if target_rect is None:
            return
        
        # Target position: center the target in the viewport
        target_x = target_rect.centerx - self.display_width // 2
        target_y = target_rect.centery - self.display_height // 2
        
        # Smooth interpolation (lerp)
        if self.smoothing > 0 and dt > 0:
            lerp_factor = min(1.0, self.smoothing * dt)
            self.x += (target_x - self.x) * lerp_factor
            self.y += (target_y - self.y) * lerp_factor
        else:
            self.x = target_x
            self.y = target_y
        
        # Clamp to world bounds
        self.x = max(0, min(self.x, self.world_width - self.display_width))
        self.y = max(0, min(self.y, self.world_height - self.display_height))
    
    def center_on(self, world_x: float, world_y: float) -> None:
        """Instantly center camera on a world position."""
        self.x = world_x - self.display_width // 2
        self.y = world_y - self.display_height // 2
        # Clamp to world bounds
        self.x = max(0, min(self.x, self.world_width - self.display_width))
        self.y = max(0, min(self.y, self.world_height - self.display_height))
    
    def world_to_screen(self, world_x: float, world_y: float) -> tuple[int, int]:
        """Convert world coordinates to screen coordinates.
        
        Args:
            world_x: X position in world space
            world_y: Y position in world space
            
        Returns:
            (screen_x, screen_y) tuple
        """
        return (int(world_x - self.x), int(world_y - self.y))
    
    def screen_to_world(self, screen_x: float, screen_y: float) -> tuple[int, int]:
        """Convert screen coordinates to world coordinates.
        
        Args:
            screen_x: X position on screen
            screen_y: Y position on screen
            
        Returns:
            (world_x, world_y) tuple
        """
        return (int(screen_x + self.x), int(screen_y + self.y))
    
    def world_rect_to_screen(self, world_rect: pygame.Rect) -> pygame.Rect:
        """Convert a world-space rect to screen-space rect."""
        return pygame.Rect(
            int(world_rect.x - self.x),
            int(world_rect.y - self.y),
            world_rect.width,
            world_rect.height
        )
    
    def is_visible(self, world_rect: pygame.Rect) -> bool:
        """Check if a world-space rect is visible in the viewport.
        
        Uses margin for smooth transitions (entities slightly off-screen are still "visible").
        
        Args:
            world_rect: Rect in world coordinates
            
        Returns:
            True if any part of the rect is in the viewport (with margin)
        """
        return self.viewport_with_margin.colliderect(world_rect)
    
    def is_point_visible(self, world_x: float, world_y: float) -> bool:
        """Check if a world-space point is visible in the viewport."""
        vp = self.viewport_with_margin
        return vp.left <= world_x <= vp.right and vp.top <= world_y <= vp.bottom
    
    def cull_entities(self, entities: list, get_rect=None) -> list:
        """Filter a list of entities to only those visible in the viewport.
        
        Updates culling statistics for performance monitoring.
        
        Args:
            entities: List of entities to filter
            get_rect: Optional function to get rect from entity.
                     If None, assumes entity["rect"] or entity.rect
                     
        Returns:
            List of visible entities
        """
        self.entities_total = len(entities)
        
        if not entities:
            self.entities_culled = 0
            return []
        
        vp = self.viewport_with_margin
        visible = []
        
        for entity in entities:
            if get_rect:
                rect = get_rect(entity)
            elif isinstance(entity, dict):
                rect = entity.get("rect")
            else:
                rect = getattr(entity, "rect", None)
            
            if rect and vp.colliderect(rect):
                visible.append(entity)
        
        self.entities_culled = self.entities_total - len(visible)
        return visible
    
    def get_culling_stats(self) -> dict:
        """Get culling performance statistics."""
        return {
            "total": self.entities_total,
            "culled": self.entities_culled,
            "visible": self.entities_total - self.entities_culled,
            "cull_rate": self.entities_culled / max(1, self.entities_total),
            "viewport_x": int(self.x),
            "viewport_y": int(self.y),
        }
    
    def reset_stats(self) -> None:
        """Reset per-frame culling statistics."""
        self.entities_total = 0
        self.entities_culled = 0


# Module-level camera instance (set during game init)
_active_camera: Camera | None = None


def get_camera() -> Camera | None:
    """Get the active camera instance."""
    return _active_camera


def set_camera(camera: Camera) -> None:
    """Set the active camera instance."""
    global _active_camera
    _active_camera = camera


def create_camera(display_width: int, display_height: int, 
                  world_width: int, world_height: int,
                  smoothing: float = 8.0) -> Camera:
    """Create and set the active camera.
    
    Args:
        display_width: Display/screen width
        display_height: Display/screen height
        world_width: World width (can be larger than display)
        world_height: World height (can be larger than display)
        smoothing: Camera follow smoothing factor
        
    Returns:
        The created Camera instance
    """
    camera = Camera(
        display_width=display_width,
        display_height=display_height,
        world_width=world_width,
        world_height=world_height,
        smoothing=smoothing,
    )
    set_camera(camera)
    return camera
