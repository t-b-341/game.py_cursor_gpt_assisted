"""Tests for the physics implementation (C extension or Python fallback).

These tests run against whatever implementation is resolved at import time
(C if game_physics is available, else Python). They ensure correct behavior
so that improvements to game_physics.c can be made in small, tested steps.

Run with C: pytest tests/test_physics_module.py -v
Run with Python fallback: physics_loader.resolve_physics(force_python=True) then pytest
"""
from __future__ import annotations

import math

import pytest

from physics_loader import (
    batch_rect_collisions,
    batch_distance_squared,
    distance,
    distance_squared,
    find_dodge_threats,
    find_in_radius,
    find_nearest_index,
    get_grid_cell_index,
    get_grid_cell_indices_for_rect,
    normalize,
    resolve_physics,
    rotate_vector,
)

# Ensure physics is resolved when this test module runs (idempotent)
@pytest.fixture(scope="module", autouse=True)
def _resolve_physics():
    resolve_physics(force_python=False)
    yield


def _get_physics():
    from physics_loader import get_physics
    return get_physics()


class TestDistance:
    """distance and distance_squared."""

    def test_distance_squared(self):
        assert distance_squared(0, 0, 3, 4) == 25.0
        assert distance_squared(1, 1, 1, 1) == 0.0

    def test_distance(self):
        assert abs(distance(0, 0, 3, 4) - 5.0) < 1e-9
        assert distance(0, 0, 0, 0) == 0.0


class TestFindInRadius:
    """find_in_radius: indices of entities within radius_squared."""

    def test_empty(self):
        assert find_in_radius(0, 0, 100, [], []) == []

    def test_none_in_radius(self):
        x = [10.0, 20.0]
        y = [10.0, 20.0]
        assert find_in_radius(0, 0, 1, x, y) == []

    def test_all_in_radius(self):
        x = [0.0, 1.0, 2.0]
        y = [0.0, 0.0, 0.0]
        r_sq = 100
        result = find_in_radius(0, 0, r_sq, x, y)
        assert set(result) == {0, 1, 2}

    def test_some_in_radius(self):
        x = [0.0, 5.0, 10.0]
        y = [0.0, 0.0, 0.0]
        r_sq = 5 * 5 + 1  # 26, so (5,0) is in
        result = find_in_radius(0, 0, r_sq, x, y)
        assert set(result) == {0, 1}


class TestGetGridCellIndicesForRect:
    """get_grid_cell_indices_for_rect: cell indices a rect overlaps."""

    def test_single_cell(self):
        # rect in one cell
        out = get_grid_cell_indices_for_rect(0, 0, 10, 10, cell_size=32, cols=10, rows=10)
        assert out == [0]

    def test_multiple_cells(self):
        # rect (0,0,64,64) with cell_size 32 -> columns 0,1,2 and rows 0,1,2 -> 9 cells
        out = get_grid_cell_indices_for_rect(0, 0, 64, 64, cell_size=32, cols=10, rows=10)
        assert len(out) == 9
        assert set(out) == {0, 1, 2, 10, 11, 12, 20, 21, 22}

    def test_clamped_to_grid(self):
        out = get_grid_cell_indices_for_rect(-100, -100, 500, 500, cell_size=32, cols=5, rows=5)
        assert len(out) == 25
        assert set(out) == set(range(25))

    def test_zero_width_or_height_returns_empty(self):
        out = get_grid_cell_indices_for_rect(0, 0, 0, 10, cell_size=32, cols=10, rows=10)
        assert out == []
        out = get_grid_cell_indices_for_rect(0, 0, 10, 0, cell_size=32, cols=10, rows=10)
        assert out == []


class TestFindDodgeThreats:
    """find_dodge_threats: bullet indices that are threats (in range and time)."""

    def test_empty(self):
        assert find_dodge_threats(0, 0, 100, 1.0, [], [], [], []) == []

    def test_bullet_far_away(self):
        # bullet at (100,0), enemy at (0,0), vel (10,0) -> time 10s, threshold 1 -> not a threat
        out = find_dodge_threats(
            0, 0, 100*100, 1.0,
            [100.0], [0.0], [10.0], [0.0]
        )
        assert out == []

    def test_bullet_approaching(self):
        # bullet at (10,0), vel (-10,0), enemy at (0,0) -> time 1s, threshold 2 -> threat
        out = find_dodge_threats(
            0, 0, 20*20, 2.0,
            [10.0], [0.0], [-10.0], [0.0]
        )
        assert out == [0]

    def test_bullet_moving_away(self):
        # bullet far and moving away: (100,0) vel (10,0) -> time_to_reach = 10 > threshold 2 -> not a threat
        out = find_dodge_threats(
            0, 0, 150*150, 2.0,
            [100.0], [0.0], [10.0], [0.0]
        )
        assert out == []


class TestBatchRectCollisions:
    """batch_rect_collisions: (a_idx, b_idx) pairs that collide."""

    def test_empty(self):
        assert batch_rect_collisions([], [], [], [], [], [], [], []) == []

    def test_no_collision(self):
        ax, ay, aw, ah = [0], [0], [10], [10]
        bx, by, bw, bh = [20], [20], [10], [10]
        assert batch_rect_collisions(ax, ay, aw, ah, bx, by, bw, bh) == []

    def test_one_collision(self):
        ax, ay, aw, ah = [0], [0], [10], [10]
        bx, by, bw, bh = [5], [5], [10], [10]
        out = batch_rect_collisions(ax, ay, aw, ah, bx, by, bw, bh)
        assert out == [(0, 0)]

    def test_multiple_pairs(self):
        ax, ay, aw, ah = [0, 50], [0, 0], [10, 10], [10, 10]
        bx, by, bw, bh = [5, 55], [5, 5], [10, 10], [10, 10]
        out = batch_rect_collisions(ax, ay, aw, ah, bx, by, bw, bh)
        assert set(out) == {(0, 0), (1, 1)}


class TestCanMoveRect:
    """can_move_rect: movement valid against bounds and other rects."""

    def test_empty_other_rects(self):
        from physics_loader import get_physics
        p = _get_physics()
        if not hasattr(p, "can_move_rect"):
            pytest.skip("no can_move_rect on impl")
        # move within bounds, no obstacles
        assert p.can_move_rect(10, 10, 20, 20, 5, 0, [], 800, 600) is True

    def test_blocked_by_bounds(self):
        from physics_loader import get_physics
        p = _get_physics()
        if not hasattr(p, "can_move_rect"):
            pytest.skip("no can_move_rect on impl")
        # move past right edge
        assert p.can_move_rect(780, 10, 20, 20, 50, 0, [], 800, 600) is False

    def test_blocked_by_other_rect(self):
        from physics_loader import get_physics
        import pygame
        p = _get_physics()
        if not hasattr(p, "can_move_rect"):
            pytest.skip("no can_move_rect on impl")
        other = pygame.Rect(30, 10, 20, 20)
        # move into other
        assert p.can_move_rect(10, 10, 20, 20, 15, 0, [other], 800, 600) is False


class TestCheckBulletCollisions:
    """check_bullet_collisions: (bullet, target) pairs that collide. Uses raw impl."""

    def test_no_collision(self):
        import pygame
        p = _get_physics()
        if not hasattr(p, "check_bullet_collisions"):
            pytest.skip("no check_bullet_collisions on impl")
        bullet = type("Bullet", (), {"rect": pygame.Rect(0, 0, 4, 4)})()
        target = type("Target", (), {"rect": pygame.Rect(100, 100, 20, 20)})()
        out = p.check_bullet_collisions([bullet], [target])
        assert out == []

    def test_one_collision(self):
        import pygame
        p = _get_physics()
        if not hasattr(p, "check_bullet_collisions"):
            pytest.skip("no check_bullet_collisions on impl")
        bullet = type("Bullet", (), {"rect": pygame.Rect(10, 10, 4, 4)})()
        target = type("Target", (), {"rect": pygame.Rect(8, 8, 20, 20)})()
        out = p.check_bullet_collisions([bullet], [target])
        assert len(out) == 1
        assert out[0][0] is bullet and out[0][1] is target


class TestNormalizeAndRotate:
    """normalize, rotate_vector."""

    def test_normalize(self):
        nx, ny = normalize(3, 4)
        assert abs(math.hypot(nx, ny) - 1.0) < 1e-9
        assert abs(nx - 0.6) < 1e-9 and abs(ny - 0.8) < 1e-9

    def test_normalize_zero(self):
        nx, ny = normalize(0, 0)
        assert (nx, ny) == (1.0, 0.0)

    def test_rotate_90(self):
        rx, ry = rotate_vector(1, 0, math.pi / 2)
        assert abs(rx) < 1e-9 and abs(ry - 1.0) < 1e-9


class TestBatchDistanceSquaredAndNearest:
    """batch_distance_squared, find_nearest_index."""

    def test_batch_distance_squared(self):
        out = batch_distance_squared(0, 0, [3, 0], [4, 0])
        assert out == [25.0, 0.0]

    def test_find_nearest_index(self):
        idx = find_nearest_index(0, 0, [10, 0, 5], [10, 0, 0])
        assert idx == 1
        assert find_nearest_index(0, 0, [], []) == -1


class TestGridCellIndex:
    """get_grid_cell_index for a point."""

    def test_cell_index(self):
        assert get_grid_cell_index(0, 0, 32, 10) == 0
        assert get_grid_cell_index(32, 32, 32, 10) == 11
