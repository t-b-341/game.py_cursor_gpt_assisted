"""
Level geometry building: blocks, trapezoids, triangles, zones, teleporter pads, wave beams.

Extracted from game.py for better code organization. These functions handle creating
and positioning level geometry elements.
"""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import pygame

# TELEPORTER_SIZE: 1.5x player size (28) = 42
TELEPORTER_SIZE = 42

from geometry_utils import line_rect_intersection
from hazards import hazard_obstacles
from level_state import LevelState

if TYPE_CHECKING:
    pass


def build_level_geometry(width: int, height: int) -> LevelState:
    """Build all level blocks, trapezoids, triangles, zones. Used once at startup; result stored in game_state.level."""
    static_blocks: list = []
    destructible_blocks = [
        {"rect": pygame.Rect(300, 200, 80, 80), "color": (150, 100, 200), "hp": 500, "max_hp": 500, "is_destructible": True, "is_moveable": True, "crack_level": 0},
        {"rect": pygame.Rect(450, 300, 60, 60), "color": (100, 200, 150), "hp": 400, "max_hp": 400, "is_destructible": True, "is_moveable": True, "crack_level": 0},
        {"rect": pygame.Rect(200, 500, 90, 50), "color": (200, 150, 100), "hp": 600, "max_hp": 600, "is_destructible": True, "is_moveable": True, "crack_level": 0},
        {"rect": pygame.Rect(750, 600, 70, 70), "color": (150, 150, 200), "hp": 450, "max_hp": 450, "is_destructible": True, "is_moveable": True, "crack_level": 0},
        {"rect": pygame.Rect(150, 700, 100, 40), "color": (200, 200, 100), "hp": 550, "max_hp": 550, "is_destructible": True, "is_moveable": True, "crack_level": 0},
        {"rect": pygame.Rect(1100, 300, 90, 90), "color": (180, 120, 180), "hp": 550, "max_hp": 550, "is_destructible": True, "is_moveable": True, "crack_level": 0},
        {"rect": pygame.Rect(1300, 500, 70, 70), "color": (120, 180, 120), "is_moveable": True},
        {"rect": pygame.Rect(1000, 800, 80, 60), "color": (200, 120, 100), "is_moveable": True},
        {"rect": pygame.Rect(400, 1000, 100, 50), "color": (150, 150, 220), "is_moveable": True},
        {"rect": pygame.Rect(800, 1200, 70, 70), "color": (220, 200, 120), "is_moveable": True},
        {"rect": pygame.Rect(1200, 1000, 90, 40), "color": (200, 150, 200), "is_moveable": True},
        {"rect": pygame.Rect(1400, 700, 60, 60), "color": (100, 200, 200), "is_moveable": True},
    ]
    moveable_destructible_blocks = [
        {"rect": pygame.Rect(350, 400, 120, 120), "color": (200, 100, 100), "hp": 400, "max_hp": 400, "is_destructible": True, "is_moveable": True, "crack_level": 0},
        {"rect": pygame.Rect(850, 500, 120, 120), "color": (100, 200, 100), "hp": 350, "max_hp": 350, "is_destructible": True, "is_moveable": True, "crack_level": 0},
        {"rect": pygame.Rect(650, 700, 120, 120), "color": (200, 150, 100), "hp": 450, "max_hp": 450, "is_destructible": True, "is_moveable": True, "crack_level": 0},
        {"rect": pygame.Rect(1050, 300, 120, 120), "color": (200, 120, 150), "is_moveable": True},
        {"rect": pygame.Rect(200, 600, 120, 120), "color": (150, 150, 200), "is_moveable": True},
        {"rect": pygame.Rect(500, 900, 120, 120), "color": (200, 100, 150), "is_moveable": True},
    ]
    giant_blocks = [
        {"rect": pygame.Rect(200, 200, 200, 200), "color": (80, 80, 120), "is_moveable": False, "size": "giant"},
        {"rect": pygame.Rect(1000, 400, 200, 200), "color": (80, 80, 120), "is_moveable": False, "size": "giant"},
        {"rect": pygame.Rect(600, 800, 200, 200), "color": (80, 80, 120), "is_moveable": False, "size": "giant"},
    ]
    super_giant_blocks = [
        {"rect": pygame.Rect(500, 300, 300, 300), "color": (60, 60, 100), "is_moveable": False, "size": "super_giant"},
        {"rect": pygame.Rect(1200, 700, 300, 300), "color": (60, 60, 100), "is_moveable": False, "size": "super_giant"},
    ]
    trapezoid_blocks = []
    triangle_blocks = []

    left_trap_height = height // 4
    left_gap = 50
    left_trap_width = 100
    for i in range(3):
        y_start = i * (left_trap_height + left_gap)
        y_end = y_start + left_trap_height
        trap_rect = pygame.Rect(-60, y_start, left_trap_width + 60, y_end - y_start)
        trapezoid_blocks.append({
            "points": [(-60, y_start), (left_trap_width, y_start + 20), (left_trap_width, y_end - 20), (-60, y_end)],
            "bounding_rect": trap_rect, "rect": trap_rect, "color": (140, 110, 170), "is_moveable": True, "side": "left"
        })
    right_trap_height = height // 3
    right_trap_width = 100
    right_y1 = 0
    gap_size = 150
    right_y2 = right_trap_height + gap_size
    trap_rect1 = pygame.Rect(width - right_trap_width, right_y1, right_trap_width + 60, right_trap_height)
    trapezoid_blocks.append({
        "points": [(width - right_trap_width, right_y1 + 20), (width + 60, right_y1), (width + 60, right_y1 + right_trap_height), (width - right_trap_width, right_y1 + right_trap_height - 20)],
        "bounding_rect": trap_rect1, "rect": trap_rect1, "color": (110, 130, 190), "is_moveable": True, "side": "right"
    })
    gap_center_y = right_y1 + right_trap_height + gap_size // 2
    ts = 40
    tri_rect_gap1 = pygame.Rect(width - right_trap_width - ts, gap_center_y - ts // 2, ts, ts)
    triangle_blocks.append({
        "points": [(width - right_trap_width - ts, gap_center_y), (width - right_trap_width, gap_center_y - ts // 2), (width - right_trap_width, gap_center_y + ts // 2)],
        "bounding_rect": tri_rect_gap1, "rect": tri_rect_gap1, "color": (120, 140, 200), "is_moveable": True, "side": "right"
    })
    tri_rect_gap2 = pygame.Rect(width - ts // 2, gap_center_y - ts // 2, ts, ts)
    triangle_blocks.append({
        "points": [(width, gap_center_y - ts // 2), (width, gap_center_y + ts // 2), (width - ts // 2, gap_center_y)],
        "bounding_rect": tri_rect_gap2, "rect": tri_rect_gap2, "color": (120, 140, 200), "is_moveable": True, "side": "right"
    })
    bottom_right_trap_height = height - right_y2
    trap_rect2 = pygame.Rect(width - right_trap_width, right_y2, right_trap_width + 60, bottom_right_trap_height)
    trapezoid_blocks.append({
        "points": [(width - right_trap_width, right_y2 + 20), (width + 60, right_y2), (width + 60, height), (width - right_trap_width, height - 20)],
        "bounding_rect": trap_rect2, "rect": trap_rect2, "color": (110, 130, 190), "is_moveable": True, "side": "right"
    })
    top_trap_width = width // 5.5
    top_trap_height = 80
    top_trap_spacing = (width - 5 * top_trap_width) / 6
    for i in range(5):
        x_start = top_trap_spacing + i * (top_trap_width + top_trap_spacing)
        x_end = x_start + top_trap_width
        trap_rect = pygame.Rect(x_start, -60, x_end - x_start, top_trap_height + 60)
        trapezoid_blocks.append({
            "points": [(x_start, -60), (x_end, -60), (x_end - 20, top_trap_height), (x_start + 20, top_trap_height)],
            "bounding_rect": trap_rect, "rect": trap_rect, "color": (100, 120, 180), "is_moveable": True, "side": "top"
        })
        tc = (x_start + x_end) // 2
        tsz = 30
        tri_rect1 = pygame.Rect(tc - tsz, -100, tsz, 40)
        triangle_blocks.append({
            "points": [(tc - tsz, -60), (tc, -100), (tc - tsz // 2, -60)],
            "bounding_rect": tri_rect1, "rect": tri_rect1, "color": (120, 140, 200), "is_moveable": True, "side": "top"
        })
        tri_rect2 = pygame.Rect(tc, -100, tsz, 40)
        triangle_blocks.append({
            "points": [(tc + tsz // 2, -60), (tc, -100), (tc + tsz, -60)],
            "bounding_rect": tri_rect2, "rect": tri_rect2, "color": (120, 140, 200), "is_moveable": True, "side": "top"
        })
    bottom_triangle_count = 10
    btw = width // bottom_triangle_count
    bth = 40
    for i in range(bottom_triangle_count):
        x_center = i * btw + btw // 2
        tri_rect = pygame.Rect(x_center - btw // 2, height, btw, bth)
        triangle_blocks.append({
            "points": [(x_center - btw // 2, height), (x_center, height + bth), (x_center + btw // 2, height)],
            "bounding_rect": tri_rect, "rect": tri_rect, "color": (120, 100, 160), "is_moveable": True, "side": "bottom"
        })
    destructible_blocks.extend([
        {"rect": pygame.Rect(240, 360, 70, 70), "color": (160, 110, 210), "is_moveable": True},
        {"rect": pygame.Rect(400, 520, 60, 60), "color": (110, 210, 160), "is_moveable": True},
        {"rect": pygame.Rect(560, 680, 80, 50), "color": (210, 160, 110), "is_moveable": True},
        {"rect": pygame.Rect(720, 840, 70, 70), "color": (160, 160, 210), "is_moveable": True},
        {"rect": pygame.Rect(880, 1000, 60, 60), "color": (210, 210, 110), "is_moveable": True},
        {"rect": pygame.Rect(1040, 1160, 80, 50), "color": (190, 130, 190), "is_moveable": True},
        {"rect": pygame.Rect(1200, 1320, 70, 70), "color": (130, 190, 130), "hp": 450, "max_hp": 450, "is_destructible": True, "is_moveable": True, "crack_level": 0},
        {"rect": pygame.Rect(1360, 1160, 60, 60), "color": (210, 130, 110), "hp": 500, "max_hp": 500, "is_destructible": True, "is_moveable": True, "crack_level": 0},
        {"rect": pygame.Rect(1520, 1000, 80, 50), "color": (160, 160, 230), "hp": 600, "max_hp": 600, "is_destructible": True, "is_moveable": True, "crack_level": 0},
        {"rect": pygame.Rect(1680, 840, 70, 70), "color": (230, 210, 130), "hp": 450, "max_hp": 450, "is_destructible": True, "is_moveable": True, "crack_level": 0},
        {"rect": pygame.Rect(1840, 680, 60, 60), "color": (200, 160, 210), "hp": 550, "max_hp": 550, "is_destructible": True, "is_moveable": True, "crack_level": 0},
        {"rect": pygame.Rect(200, 840, 80, 50), "color": (110, 210, 210), "hp": 400, "max_hp": 400, "is_destructible": True, "is_moveable": True, "crack_level": 0},
    ])
    moving_health_zone = {
        "rect": pygame.Rect(width // 4 - 75, height // 4 - 75, 150, 150),
        "heal_rate": 20.0, "color": (100, 255, 100, 80), "name": "Moving Healing Zone", "zone_id": 1,
        "velocity": 30.0, "target": None,
    }
    max_health_zone_attempts = 100
    for _ in range(max_health_zone_attempts):
        hz_overlaps = False
        for bl in [destructible_blocks, moveable_destructible_blocks, giant_blocks, super_giant_blocks]:
            for block in bl:
                if moving_health_zone["rect"].colliderect(block["rect"]):
                    hz_overlaps = True
                    break
            if hz_overlaps:
                break
        if not hz_overlaps:
            for tb in trapezoid_blocks:
                if moving_health_zone["rect"].colliderect(tb.get("bounding_rect", tb.get("rect"))):
                    hz_overlaps = True
                    break
        if not hz_overlaps:
            for tr in triangle_blocks:
                if moving_health_zone["rect"].colliderect(tr.get("bounding_rect", tr.get("rect"))):
                    hz_overlaps = True
                    break
        if not hz_overlaps:
            break
        new_x = random.randint(100, width - 250)
        new_y = random.randint(100, height - 250)
        moving_health_zone["rect"].center = (new_x, new_y)

    return LevelState(
        static_blocks=static_blocks,
        trapezoid_blocks=trapezoid_blocks,
        triangle_blocks=triangle_blocks,
        destructible_blocks=destructible_blocks,
        moveable_blocks=moveable_destructible_blocks,
        giant_blocks=giant_blocks,
        super_giant_blocks=super_giant_blocks,
        hazard_obstacles=hazard_obstacles,
        moving_health_zone=moving_health_zone,
    )


def place_teleporter_pads(level: LevelState, width: int, height: int) -> list:
    """Place two linked teleporter pads so they don't overlap level geometry or each other."""
    pad_a = {"rect": pygame.Rect(0, 0, TELEPORTER_SIZE, TELEPORTER_SIZE), "linked_rect": None}
    pad_b = {"rect": pygame.Rect(0, 0, TELEPORTER_SIZE, TELEPORTER_SIZE), "linked_rect": None}
    pad_a["linked_rect"] = pad_b["rect"]
    pad_b["linked_rect"] = pad_a["rect"]
    pads = [pad_a, pad_b]
    max_attempts = 100
    d = level.destructible_blocks
    m = level.moveable_blocks
    g = level.giant_blocks
    sg = level.super_giant_blocks
    tb = level.trapezoid_blocks
    tr = level.triangle_blocks
    zone = level.moving_health_zone
    for idx, pad in enumerate(pads):
        for _ in range(max_attempts):
            overlaps = False
            if idx == 0:
                pad["rect"].center = (random.randint(80, width // 2 - 60), random.randint(80, height // 2 - 60))
            else:
                pad["rect"].center = (random.randint(width // 2 + 60, width - 80), random.randint(height // 2 + 60, height - 80))
            for bl in [d, m, g, sg]:
                for block in bl:
                    if pad["rect"].colliderect(block["rect"]):
                        overlaps = True
                        break
                if overlaps:
                    break
            if not overlaps:
                for t in tb:
                    if pad["rect"].colliderect(t.get("bounding_rect", t.get("rect"))):
                        overlaps = True
                        break
            if not overlaps:
                for t in tr:
                    if pad["rect"].colliderect(t.get("bounding_rect", t.get("rect"))):
                        overlaps = True
                        break
            if not overlaps and zone and not pad["rect"].colliderect(zone["rect"]):
                other = pads[1 - idx]
                if not pad["rect"].colliderect(other["rect"]):
                    break
    return pads


def generate_wave_beam_points(
    start_pos: pygame.Vector2,
    direction: pygame.Vector2,
    pattern: str,
    length: int,
    amplitude: float = 50.0,
    frequency: float = 0.02,
    time_offset: float = 0.0
) -> list[pygame.Vector2]:
    """Generate points along a wave pattern beam.
    
    Args:
        start_pos: Starting position of the beam
        direction: Normalized direction vector
        pattern: Wave pattern type ("sine", "cosine", "tangent", etc.)
        length: Length of the beam in pixels
        amplitude: Amplitude of the wave (pixels)
        frequency: Frequency of the wave (cycles per pixel)
        time_offset: Time-based phase offset for undulation (in seconds)
    
    Returns:
        List of points along the wave path
    """
    points = []
    perp = pygame.Vector2(-direction.y, direction.x)  # Perpendicular vector for wave offset
    
    num_points = max(200, length // 5)  # Generate more points for smoother solid line
    step = length / num_points
    
    # Undulation: 0.5 second period = 4 * pi radians per second (2 * pi / 0.5)
    undulation_phase = time_offset * 4 * math.pi  # Phase offset for 0.5 second period
    
    for i in range(num_points + 1):
        t = i * step
        x = start_pos.x + direction.x * t
        y = start_pos.y + direction.y * t
        
        # Calculate wave offset based on pattern with time-based undulation
        wave_value = 0.0
        angle = t * frequency * 2 * math.pi + undulation_phase
        
        if pattern == "sine":
            wave_value = math.sin(angle)
        elif pattern == "cosine":
            wave_value = math.cos(angle)
        elif pattern == "tangent":
            # Clamp to prevent infinite values
            wave_value = math.tan(angle)
            wave_value = max(-10.0, min(10.0, wave_value))
        elif pattern == "cotangent":
            # Clamp to prevent infinite values
            if abs(math.sin(angle)) > 0.01:
                wave_value = math.cos(angle) / math.sin(angle)
                wave_value = max(-10.0, min(10.0, wave_value))
            else:
                wave_value = 0.0
        elif pattern == "secant":
            # Clamp to prevent infinite values
            if abs(math.cos(angle)) > 0.01:
                wave_value = 1.0 / math.cos(angle)
                wave_value = max(-10.0, min(10.0, wave_value))
            else:
                wave_value = 0.0
        elif pattern == "cosecant":
            # Clamp to prevent infinite values
            if abs(math.sin(angle)) > 0.01:
                wave_value = 1.0 / math.sin(angle)
                wave_value = max(-10.0, min(10.0, wave_value))
            else:
                wave_value = 0.0
        
        # Apply wave offset perpendicular to direction
        offset = perp * (wave_value * amplitude)
        point = pygame.Vector2(x, y) + offset
        points.append(point)
    
    return points


def check_wave_beam_collision(points: list[pygame.Vector2], rect: pygame.Rect, width: int) -> tuple[pygame.Vector2 | None, float]:
    """Check if a wave beam (represented by points) collides with a rectangle.
    
    Returns:
        Tuple of (closest_hit_point, distance) or (None, infinity) if no collision
    """
    closest_hit = None
    closest_dist = float('inf')
    
    # Check each segment of the beam
    for i in range(len(points) - 1):
        p1 = points[i]
        p2 = points[i + 1]
        
        # Check if this segment intersects the rect
        hit = line_rect_intersection(p1, p2, rect)
        if hit:
            dist = (hit - points[0]).length()
            if dist < closest_dist:
                closest_dist = dist
                closest_hit = hit
    
    # Also check if any point is inside the rect (for thick beams)
    for point in points:
        if rect.collidepoint(point.x, point.y):
            dist = (point - points[0]).length()
            if dist < closest_dist:
                closest_dist = dist
                closest_hit = point
    
    return (closest_hit, closest_dist)
