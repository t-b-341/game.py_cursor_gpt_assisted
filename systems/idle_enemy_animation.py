"""
Idle enemy animation system for decorative floating enemies.

Used on the pause screen to display animated enemy shapes that float,
bounce, and periodically exit/re-enter the screen.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame


@dataclass
class IdleEnemy:
    """An animated enemy that floats around the screen."""
    x: float
    y: float
    vx: float
    vy: float
    size: int
    color: tuple[int, int, int]
    shape: str  # "circle", "square", "triangle"
    bob_offset: float = 0.0
    bob_speed: float = 2.0
    time_to_exit: float = 0.0
    exiting: bool = False
    exit_target_x: float = 0.0
    exit_target_y: float = 0.0
    returning: bool = False


ENEMY_COLORS = [
    (255, 100, 100),  # Red - basic
    (100, 100, 255),  # Blue - ranged
    (255, 200, 100),  # Orange - fast
    (150, 80, 200),   # Purple - ambient
    (100, 255, 100),  # Green - healer
    (255, 255, 100),  # Yellow - suicide
]

ENEMY_SHAPES = ["circle", "square", "triangle"]

# Module-level state
_idle_enemies: list[IdleEnemy] = []
_idle_enemies_initialized: bool = False
_screen_size: tuple[int, int] = (0, 0)


def _init_idle_enemies(width: int, height: int, count: int = 8) -> None:
    """Initialize idle enemies."""
    global _idle_enemies, _idle_enemies_initialized, _screen_size
    _idle_enemies = []
    _screen_size = (width, height)
    for _ in range(count):
        enemy = _create_idle_enemy(width, height, spawn_onscreen=True)
        _idle_enemies.append(enemy)
    _idle_enemies_initialized = True


def _create_idle_enemy(width: int, height: int, spawn_onscreen: bool = True) -> IdleEnemy:
    """Create a new idle enemy with random properties."""
    size = random.randint(20, 45)
    color = random.choice(ENEMY_COLORS)
    shape = random.choice(ENEMY_SHAPES)

    if spawn_onscreen:
        margin = 100
        x = random.uniform(margin, width - margin)
        y = random.uniform(margin, height - margin)
    else:
        side = random.randint(0, 3)
        if side == 0:
            x, y = random.uniform(0, width), -size - 20
        elif side == 1:
            x, y = width + size + 20, random.uniform(0, height)
        elif side == 2:
            x, y = random.uniform(0, width), height + size + 20
        else:
            x, y = -size - 20, random.uniform(0, height)

    speed = random.uniform(20, 60)
    angle = random.uniform(0, 2 * math.pi)
    vx = math.cos(angle) * speed
    vy = math.sin(angle) * speed

    return IdleEnemy(
        x=x, y=y, vx=vx, vy=vy,
        size=size, color=color, shape=shape,
        bob_offset=random.uniform(0, 2 * math.pi),
        bob_speed=random.uniform(1.5, 3.0),
        time_to_exit=random.uniform(5.0, 15.0),
    )


def update_idle_enemies(dt: float, width: int, height: int) -> None:
    """Update all idle enemies (called each frame while displayed)."""
    global _idle_enemies, _idle_enemies_initialized, _screen_size

    if not _idle_enemies_initialized or _screen_size != (width, height):
        _init_idle_enemies(width, height)
        return

    margin = 150
    for enemy in _idle_enemies:
        enemy.bob_offset += enemy.bob_speed * dt
        if enemy.exiting:
            _update_exiting_enemy(enemy, width, height, margin, dt)
        elif enemy.returning:
            _update_returning_enemy(enemy, width, height, dt)
        else:
            _update_floating_enemy(enemy, width, height, dt)


def _update_exiting_enemy(enemy: IdleEnemy, width: int, height: int, margin: int, dt: float) -> None:
    """Update an enemy that is flying off screen."""
    dx = enemy.exit_target_x - enemy.x
    dy = enemy.exit_target_y - enemy.y
    dist = math.sqrt(dx * dx + dy * dy)
    if dist > 1:
        speed = 200
        enemy.x += (dx / dist) * speed * dt
        enemy.y += (dy / dist) * speed * dt

    if (enemy.x < -margin or enemy.x > width + margin or
        enemy.y < -margin or enemy.y > height + margin):
        enemy.exiting = False
        enemy.returning = True
        _respawn_enemy_offscreen(enemy, width, height)


def _respawn_enemy_offscreen(enemy: IdleEnemy, width: int, height: int) -> None:
    """Respawn an enemy at a random offscreen location heading toward center."""
    side = random.randint(0, 3)
    if side == 0:
        enemy.x, enemy.y = random.uniform(0, width), -enemy.size - 20
    elif side == 1:
        enemy.x, enemy.y = width + enemy.size + 20, random.uniform(0, height)
    elif side == 2:
        enemy.x, enemy.y = random.uniform(0, width), height + enemy.size + 20
    else:
        enemy.x, enemy.y = -enemy.size - 20, random.uniform(0, height)

    target_x = width // 2 + random.uniform(-200, 200)
    target_y = height // 2 + random.uniform(-200, 200)
    dx, dy = target_x - enemy.x, target_y - enemy.y
    dist = math.sqrt(dx * dx + dy * dy)
    if dist > 1:
        speed = random.uniform(40, 80)
        enemy.vx = (dx / dist) * speed
        enemy.vy = (dy / dist) * speed
    enemy.time_to_exit = random.uniform(5.0, 15.0)


def _update_returning_enemy(enemy: IdleEnemy, width: int, height: int, dt: float) -> None:
    """Update an enemy returning to the screen."""
    enemy.x += enemy.vx * dt
    enemy.y += enemy.vy * dt
    if 50 < enemy.x < width - 50 and 50 < enemy.y < height - 50:
        enemy.returning = False


def _update_floating_enemy(enemy: IdleEnemy, width: int, height: int, dt: float) -> None:
    """Update a normally floating enemy."""
    enemy.x += enemy.vx * dt
    enemy.y += enemy.vy * dt

    # Bounce off edges
    if enemy.x < 50:
        enemy.vx = abs(enemy.vx) + random.uniform(-10, 10)
        enemy.x = 50
    elif enemy.x > width - 50:
        enemy.vx = -abs(enemy.vx) + random.uniform(-10, 10)
        enemy.x = width - 50

    if enemy.y < 100:
        enemy.vy = abs(enemy.vy) + random.uniform(-10, 10)
        enemy.y = 100
    elif enemy.y > height - 150:
        enemy.vy = -abs(enemy.vy) + random.uniform(-10, 10)
        enemy.y = height - 150

    # Random direction changes
    if random.random() < 0.01:
        enemy.vx += random.uniform(-20, 20)
        enemy.vy += random.uniform(-20, 20)
        speed = math.sqrt(enemy.vx ** 2 + enemy.vy ** 2)
        if speed > 80:
            enemy.vx = (enemy.vx / speed) * 80
            enemy.vy = (enemy.vy / speed) * 80

    # Check exit timer
    enemy.time_to_exit -= dt
    if enemy.time_to_exit <= 0:
        enemy.exiting = True
        side = random.randint(0, 3)
        if side == 0:
            enemy.exit_target_x, enemy.exit_target_y = random.uniform(0, width), -100
        elif side == 1:
            enemy.exit_target_x, enemy.exit_target_y = width + 100, random.uniform(0, height)
        elif side == 2:
            enemy.exit_target_x, enemy.exit_target_y = random.uniform(0, width), height + 100
        else:
            enemy.exit_target_x, enemy.exit_target_y = -100, random.uniform(0, height)


def render_idle_enemies(screen: pygame.Surface, run_time: float) -> None:
    """Render all idle enemies on the screen."""
    for enemy in _idle_enemies:
        bob_y = math.sin(enemy.bob_offset) * 5
        x, y = int(enemy.x), int(enemy.y + bob_y)
        size, color = enemy.size, enemy.color
        border_color = (max(0, color[0] - 60), max(0, color[1] - 60), max(0, color[2] - 60))

        if enemy.shape == "circle":
            pygame.draw.circle(screen, color, (x, y), size // 2)
            pygame.draw.circle(screen, border_color, (x, y), size // 2, 3)
        elif enemy.shape == "square":
            rect = pygame.Rect(x - size // 2, y - size // 2, size, size)
            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, border_color, rect, 3)
        elif enemy.shape == "triangle":
            half = size // 2
            points = [(x, y - half), (x - half, y + half), (x + half, y + half)]
            pygame.draw.polygon(screen, color, points)
            pygame.draw.polygon(screen, border_color, points, 3)


def reset_idle_enemies() -> None:
    """Reset idle enemies (call when leaving the screen that displays them)."""
    global _idle_enemies_initialized
    _idle_enemies_initialized = False
