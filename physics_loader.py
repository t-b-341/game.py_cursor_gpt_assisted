"""Resolve and expose the physics implementation (C extension or Python fallback).

Call resolve_physics(force_python) at startup; then geometry_utils and other
consumers use get_physics() for vec_toward / can_move_rect / distance_squared.
The main game sets ctx.using_c_physics from the returned flag.
"""
from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any

import pygame

_impl: Any = None
_using_c: bool = False


def _python_vec_toward(ax: float, ay: float, bx: float, by: float) -> tuple[float, float]:
    v = pygame.Vector2(bx - ax, by - ay)
    if v.length_squared() < 1e-12:
        return (1.0, 0.0)
    v = v.normalize()
    return (v.x, v.y)


def _python_can_move_rect(
    x: int, y: int, w: int, h: int,
    dx: int, dy: int,
    other_rects: list[Any],
    screen_width: int, screen_height: int,
) -> bool:
    test = pygame.Rect(x + dx, y + dy, w, h)
    if test.left < 0 or test.right > screen_width or test.top < 0 or test.bottom > screen_height:
        return False
    for o in other_rects:
        if test.colliderect(o):
            return False
    return True


def _python_distance_squared(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate squared distance between two points (avoids sqrt)."""
    dx = x2 - x1
    dy = y2 - y1
    return dx * dx + dy * dy


def _python_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate distance between two points."""
    dx = x2 - x1
    dy = y2 - y1
    return math.sqrt(dx * dx + dy * dy)


def _python_batch_distance_squared(cx: float, cy: float, targets_x: list, targets_y: list) -> list:
    """Compute squared distances from center point to all targets."""
    result = []
    for tx, ty in zip(targets_x, targets_y):
        dx = tx - cx
        dy = ty - cy
        result.append(dx * dx + dy * dy)
    return result


def _python_find_in_radius(cx: float, cy: float, r_sq: float, entities_x: list, entities_y: list) -> list:
    """Find indices of entities within radius squared."""
    result = []
    for i, (ex, ey) in enumerate(zip(entities_x, entities_y)):
        dx = ex - cx
        dy = ey - cy
        if dx * dx + dy * dy <= r_sq:
            result.append(i)
    return result


def _python_get_grid_cell_index(x: int, y: int, cell_size: int, cols: int) -> int:
    """Get grid cell index for a point."""
    col = x // cell_size
    row = y // cell_size
    return row * cols + col


def _python_get_grid_cell_indices_for_rect(rx: int, ry: int, rw: int, rh: int, 
                                            cell_size: int, cols: int, rows: int) -> list:
    """Get all grid cell indices a rect overlaps."""
    min_col = max(0, rx // cell_size)
    max_col = min(cols - 1, (rx + rw) // cell_size)
    min_row = max(0, ry // cell_size)
    max_row = min(rows - 1, (ry + rh) // cell_size)
    
    result = []
    for row in range(min_row, max_row + 1):
        for col in range(min_col, max_col + 1):
            result.append(row * cols + col)
    return result


def _python_rotate_vector(x: float, y: float, angle: float) -> tuple[float, float]:
    """Rotate a 2D vector by angle (radians)."""
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return (x * cos_a - y * sin_a, x * sin_a + y * cos_a)


def _python_find_nearest_index(cx: float, cy: float, positions_x: list, positions_y: list) -> int:
    """Find index of nearest entity from position lists. Returns -1 if empty."""
    if not positions_x:
        return -1
    min_dist_sq = float('inf')
    nearest_idx = -1
    for i, (ex, ey) in enumerate(zip(positions_x, positions_y)):
        dx = ex - cx
        dy = ey - cy
        dist_sq = dx * dx + dy * dy
        if dist_sq < min_dist_sq:
            min_dist_sq = dist_sq
            nearest_idx = i
    return nearest_idx


def _python_find_dodge_threats(ex: float, ey: float, dodge_range_sq: float, time_threshold: float,
                               bullets_x: list, bullets_y: list, 
                               bullets_vx: list, bullets_vy: list) -> list:
    """Find bullet indices that are threats within dodge range and time threshold."""
    result = []
    for i in range(len(bullets_x)):
        bx, by = bullets_x[i], bullets_y[i]
        dx = bx - ex
        dy = by - ey
        dist_sq = dx * dx + dy * dy
        
        if dist_sq < dodge_range_sq:
            vx, vy = bullets_vx[i], bullets_vy[i]
            vel_len_sq = vx * vx + vy * vy
            
            if vel_len_sq > 0.0001:
                dist = math.sqrt(dist_sq)
                vel_len = math.sqrt(vel_len_sq)
                time_to_reach = dist / vel_len
                
                if time_to_reach < time_threshold:
                    result.append(i)
    return result


def _python_batch_rect_collisions(ax: list, ay: list, aw: list, ah: list,
                                  bx: list, by: list, bw: list, bh: list) -> list:
    """Batch check rect-rect collisions, return list of (a_idx, b_idx) pairs."""
    result = []
    for i in range(len(ax)):
        a_left, a_top, a_w, a_h = ax[i], ay[i], aw[i], ah[i]
        a_right = a_left + a_w
        a_bottom = a_top + a_h
        
        for j in range(len(bx)):
            b_left, b_top, b_w, b_h = bx[j], by[j], bw[j], bh[j]
            b_right = b_left + b_w
            b_bottom = b_top + b_h
            
            # AABB collision check
            if not (a_right < b_left or b_right < a_left or
                    a_bottom < b_top or b_bottom < a_top):
                result.append((i, j))
    return result


def _python_normalize(x: float, y: float) -> tuple[float, float]:
    """Normalize a 2D vector."""
    length = math.sqrt(x * x + y * y)
    if length < 0.0001:
        return (1.0, 0.0)
    return (x / length, y / length)


def _python_physics_namespace() -> SimpleNamespace:
    return SimpleNamespace(
        vec_toward=_python_vec_toward,
        can_move_rect=_python_can_move_rect,
        distance_squared=_python_distance_squared,
        distance=_python_distance,
        batch_distance_squared=_python_batch_distance_squared,
        find_in_radius=_python_find_in_radius,
        get_grid_cell_index=_python_get_grid_cell_index,
        get_grid_cell_indices_for_rect=_python_get_grid_cell_indices_for_rect,
        rotate_vector=_python_rotate_vector,
        find_nearest_index=_python_find_nearest_index,
        find_dodge_threats=_python_find_dodge_threats,
        batch_rect_collisions=_python_batch_rect_collisions,
        normalize=_python_normalize,
    )


def resolve_physics(force_python: bool = False) -> tuple[Any, bool]:
    """Resolve the physics implementation. Call once at startup before using geometry_utils.

    Returns:
        (physics_impl, using_c): impl has vec_toward(ax,ay,bx,by)->(x,y) and
        can_move_rect(x,y,w,h,dx,dy,other_rects,sw,sh)->bool. using_c is True
        iff the C-accelerated module is in use.
    """
    global _impl, _using_c
    if force_python:
        _impl = _python_physics_namespace()
        _using_c = False
        print("C-accelerated physics unavailable; using Python fallback.")
        return (_impl, False)
    try:
        import game_physics  # type: ignore
        _impl = game_physics
        _using_c = True
        print("Using C-accelerated physics module.")
        return (_impl, True)
    except ImportError:
        _impl = _python_physics_namespace()
        _using_c = False
        print("C-accelerated physics unavailable; using Python fallback.")
        return (_impl, False)


def get_physics() -> Any:
    """Return the resolved physics implementation. resolve_physics() must have been called first."""
    return _impl


def is_using_c() -> bool:
    """Return True if using C-accelerated physics."""
    return _using_c


# Convenience functions that use the resolved implementation
def distance_squared(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate squared distance between two points. Uses C if available."""
    if _impl is None:
        return _python_distance_squared(x1, y1, x2, y2)
    return _impl.distance_squared(x1, y1, x2, y2)


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate distance between two points. Uses C if available."""
    if _impl is None:
        return _python_distance(x1, y1, x2, y2)
    return _impl.distance(x1, y1, x2, y2)


def batch_distance_squared(cx: float, cy: float, targets_x: list, targets_y: list) -> list:
    """Compute squared distances from center to all targets. Uses C if available."""
    if _impl is None or not hasattr(_impl, 'batch_distance_squared'):
        return _python_batch_distance_squared(cx, cy, targets_x, targets_y)
    return _impl.batch_distance_squared(cx, cy, targets_x, targets_y)


def find_in_radius(cx: float, cy: float, r_sq: float, entities_x: list, entities_y: list) -> list:
    """Find indices of entities within radius squared. Uses C if available."""
    if _impl is None or not hasattr(_impl, 'find_in_radius'):
        return _python_find_in_radius(cx, cy, r_sq, entities_x, entities_y)
    return _impl.find_in_radius(cx, cy, r_sq, entities_x, entities_y)


def get_grid_cell_index(x: int, y: int, cell_size: int, cols: int) -> int:
    """Get grid cell index for a point. Uses C if available."""
    if _impl is None or not hasattr(_impl, 'get_grid_cell_index'):
        return _python_get_grid_cell_index(x, y, cell_size, cols)
    return _impl.get_grid_cell_index(x, y, cell_size, cols)


def get_grid_cell_indices_for_rect(rx: int, ry: int, rw: int, rh: int,
                                   cell_size: int, cols: int, rows: int) -> list:
    """Get all grid cell indices a rect overlaps. Uses C if available."""
    if _impl is None or not hasattr(_impl, 'get_grid_cell_indices_for_rect'):
        return _python_get_grid_cell_indices_for_rect(rx, ry, rw, rh, cell_size, cols, rows)
    return _impl.get_grid_cell_indices_for_rect(rx, ry, rw, rh, cell_size, cols, rows)


def rotate_vector(x: float, y: float, angle: float) -> tuple[float, float]:
    """Rotate a 2D vector by angle (radians). Uses C if available."""
    if _impl is None or not hasattr(_impl, 'rotate_vector'):
        return _python_rotate_vector(x, y, angle)
    return _impl.rotate_vector(x, y, angle)


def find_nearest_index(cx: float, cy: float, positions_x: list, positions_y: list) -> int:
    """Find index of nearest entity from position lists. Uses C if available."""
    if _impl is None or not hasattr(_impl, 'find_nearest_index'):
        return _python_find_nearest_index(cx, cy, positions_x, positions_y)
    return _impl.find_nearest_index(cx, cy, positions_x, positions_y)


def find_dodge_threats(ex: float, ey: float, dodge_range_sq: float, time_threshold: float,
                       bullets_x: list, bullets_y: list,
                       bullets_vx: list, bullets_vy: list) -> list:
    """Find bullet indices that are threats within dodge range. Uses C if available."""
    if _impl is None or not hasattr(_impl, 'find_dodge_threats'):
        return _python_find_dodge_threats(ex, ey, dodge_range_sq, time_threshold,
                                          bullets_x, bullets_y, bullets_vx, bullets_vy)
    return _impl.find_dodge_threats(ex, ey, dodge_range_sq, time_threshold,
                                    bullets_x, bullets_y, bullets_vx, bullets_vy)


def batch_rect_collisions(ax: list, ay: list, aw: list, ah: list,
                          bx: list, by: list, bw: list, bh: list) -> list:
    """Batch check rect-rect collisions. Uses C if available."""
    if _impl is None or not hasattr(_impl, 'batch_rect_collisions'):
        return _python_batch_rect_collisions(ax, ay, aw, ah, bx, by, bw, bh)
    return _impl.batch_rect_collisions(ax, ay, aw, ah, bx, by, bw, bh)


def normalize(x: float, y: float) -> tuple[float, float]:
    """Normalize a 2D vector. Uses C if available."""
    if _impl is None or not hasattr(_impl, 'normalize'):
        return _python_normalize(x, y)
    return _impl.normalize(x, y)
