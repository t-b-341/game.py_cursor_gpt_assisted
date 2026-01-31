"""
Enemy entity: wraps the existing enemy dict for unified Entity interface
while keeping full dict-like access (enemy["rect"], enemy["hp"], etc.) for compatibility.

Optimized for performance: hot properties stored as direct slots, with fast-path get().
"""
from typing import Any, Optional

import pygame

from .base import Entity


# Properties that are accessed frequently in hot loops - stored as slots
_HOT_PROPERTIES = frozenset({
    "rect", "hp", "max_hp", "type", "speed", "color",
    "shoot_cooldown", "time_since_shot", "projectile_speed",
})


class Enemy(Entity):
    """
    Enemy that extends Entity and wraps the legacy dict representation.
    Supports both attribute access (.rect, .hp, .alive) and dict access (["rect"], ["hp"])
    so existing code using enemy["rect"] or enemy.get("color") keeps working.
    
    Hot properties are stored as direct slots for faster access.
    """

    __slots__ = (
        "_data",
        # Hot properties cached as slots
        "_type", "_speed", "_color", "_max_hp",
        "_shoot_cooldown", "_time_since_shot", "_projectile_speed",
    )

    def __init__(self, data: dict):
        rect = data.get("rect")
        hp = data.get("hp", 0)
        super().__init__(rect=rect, hp=hp, alive=hp > 0)
        self._data = data
        
        # Cache hot properties as slots for faster access
        self._type = data.get("type", "enemy")
        self._speed = data.get("speed", 80)
        self._color = data.get("color", (200, 50, 50))
        self._max_hp = data.get("max_hp", hp)
        self._shoot_cooldown = data.get("shoot_cooldown", 1.0)
        self._time_since_shot = data.get("time_since_shot", 0.0)
        self._projectile_speed = data.get("projectile_speed", 300)

    @property
    def rect(self) -> Optional[pygame.Rect]:
        return self._rect

    @rect.setter
    def rect(self, value: Optional[pygame.Rect]) -> None:
        self._rect = value
        self._data["rect"] = value

    @property
    def hp(self) -> int:
        return self._hp

    @hp.setter
    def hp(self, value: int) -> None:
        self._hp = int(value)
        self._data["hp"] = self._hp

    @property
    def alive(self) -> bool:
        return self._hp > 0

    def __getitem__(self, key: str) -> Any:
        # Fast path for hot properties
        if key == "rect":
            return self._rect
        if key == "hp":
            return self._hp
        if key == "type":
            return self._type
        if key == "speed":
            return self._speed
        if key == "color":
            return self._color
        if key == "max_hp":
            return self._max_hp
        if key == "shoot_cooldown":
            return self._shoot_cooldown
        if key == "time_since_shot":
            return self._time_since_shot
        if key == "projectile_speed":
            return self._projectile_speed
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value
        # Sync hot properties to slots
        if key == "rect":
            self._rect = value
        elif key == "hp":
            self._hp = int(value)
        elif key == "type":
            self._type = value
        elif key == "speed":
            self._speed = value
        elif key == "color":
            self._color = value
        elif key == "max_hp":
            self._max_hp = value
        elif key == "shoot_cooldown":
            self._shoot_cooldown = value
        elif key == "time_since_shot":
            self._time_since_shot = value
        elif key == "projectile_speed":
            self._projectile_speed = value

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        """Optimized get() with fast-path for hot properties."""
        # Fast path for frequently accessed properties
        if key == "hp":
            return self._hp
        if key == "rect":
            return self._rect
        if key == "type":
            return self._type
        if key == "speed":
            return self._speed
        if key == "color":
            return self._color
        if key == "max_hp":
            return self._max_hp
        if key == "shoot_cooldown":
            return self._shoot_cooldown
        if key == "time_since_shot":
            return self._time_since_shot
        if key == "projectile_speed":
            return self._projectile_speed
        # Slow path for optional/rare properties
        return self._data.get(key, default)

    def update(self, dt: float, state: Any) -> None:
        """Per-enemy logic remains in the game loop; this is a hook for future use."""
        pass

    def draw(self, screen: pygame.Surface, state: Any = None) -> None:
        """Draw this enemy (rect only; health bars stay in the game loop)."""
        if self._rect is None:
            return
        pygame.draw.rect(screen, self._color, self._rect)
