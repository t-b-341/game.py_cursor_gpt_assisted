"""Tests for projectile motion logic (pos += vel * dt, no display)."""
import pygame
import pytest


def update_projectile_position(rect: pygame.Rect, vel: pygame.Vector2, dt: float) -> None:
    """Apply the same update rule as the game: position += velocity * dt (int truncation)."""
    rect.x += int(vel.x * dt)
    rect.y += int(vel.y * dt)


def test_projectile_moves_in_direction_of_velocity():
    rect = pygame.Rect(100, 100, 8, 8)
    vel = pygame.Vector2(200.0, 0.0)
    update_projectile_position(rect, vel, 0.5)
    assert rect.x == 200 and rect.y == 100


def test_projectile_moves_by_vel_times_dt():
    rect = pygame.Rect(0, 0, 4, 4)
    vel = pygame.Vector2(100.0, 50.0)
    update_projectile_position(rect, vel, 1.0)
    assert rect.x == 100 and rect.y == 50


def test_projectile_truncates_to_int():
    rect = pygame.Rect(0, 0, 4, 4)
    vel = pygame.Vector2(33.0, 33.0)
    update_projectile_position(rect, vel, 0.5)
    assert rect.x == 16 and rect.y == 16  # 16.5 -> 16


def test_projectile_zero_velocity_unchanged():
    rect = pygame.Rect(50, 50, 8, 8)
    vel = pygame.Vector2(0.0, 0.0)
    update_projectile_position(rect, vel, 1.0)
    assert rect.x == 50 and rect.y == 50


def test_projectile_small_dt_small_move():
    rect = pygame.Rect(100, 100, 8, 8)
    vel = pygame.Vector2(1000.0, 0.0)
    update_projectile_position(rect, vel, 0.001)
    assert rect.x == 101 and rect.y == 100
