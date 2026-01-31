"""Spawn helper functions for pickups, weapons, and positioning.

Extracted from game.py to reduce file size.
"""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import pygame

from config.projectile_defs import WEAPON_DISPLAY_COLORS

if TYPE_CHECKING:
    from state import GameState


def random_spawn_position(
    size: tuple[int, int],
    state: "GameState",
    width: int,
    height: int,
    max_attempts: int = 25,
) -> pygame.Rect:
    """Find a spawn position not overlapping player or blocks.
    
    Args:
        size: (width, height) of the object to spawn
        state: GameState with player_rect, level, pickups, teleporter_pads
        width: World width
        height: World height
        max_attempts: Max random positions to try
        
    Returns:
        pygame.Rect at a valid spawn position
    """
    w, h = size
    lev = getattr(state, "level", None)
    if state.player_rect is None:
        player_center = pygame.Vector2(width // 2, height // 2)
        player_size = 28
    else:
        player_center = pygame.Vector2(state.player_rect.center)
        player_size = max(state.player_rect.w, state.player_rect.h)
    min_distance = player_size * 10
    
    for _ in range(max_attempts):
        x = random.randint(0, width - w)
        y = random.randint(0, height - h)
        candidate = pygame.Rect(x, y, w, h)
        candidate_center = pygame.Vector2(candidate.center)
        if candidate_center.distance_to(player_center) < min_distance:
            continue
        if state.player_rect is not None and candidate.colliderect(state.player_rect):
            continue
        if lev is not None:
            if any(candidate.colliderect(b["rect"]) for b in lev.static_blocks):
                continue
            if any(candidate.colliderect(b["rect"]) for b in lev.moveable_blocks):
                continue
            if any(candidate.colliderect(b["rect"]) for b in lev.destructible_blocks):
                continue
            if any(candidate.colliderect(b["rect"]) for b in lev.giant_blocks):
                continue
            if any(candidate.colliderect(b["rect"]) for b in lev.super_giant_blocks):
                continue
            if any(candidate.colliderect(tb["bounding_rect"]) for tb in lev.trapezoid_blocks):
                continue
            if any(candidate.colliderect(tr["bounding_rect"]) for tr in lev.triangle_blocks):
                continue
            if lev.moving_health_zone and candidate.colliderect(lev.moving_health_zone["rect"]):
                continue
        if any(candidate.colliderect(p["rect"]) for p in state.pickups):
            continue
        if any(candidate.colliderect(pad["rect"]) for pad in state.teleporter_pads):
            continue
        return candidate
    return pygame.Rect(max(0, width // 2 - w), max(0, height // 2 - h), w, h)


def spawn_pickup(pickup_type: str, state: "GameState", width: int, height: int) -> None:
    """Spawn a pickup at a non-overlapping position.
    
    Args:
        pickup_type: Type of pickup to spawn
        state: GameState to add pickup to
        width: World width
        height: World height
    """
    size = (64, 64)
    max_attempts = 50
    for _ in range(max_attempts):
        r = random_spawn_position(size, state, width, height)
        overlaps = False
        for existing_pickup in state.pickups:
            if r.colliderect(existing_pickup["rect"]):
                overlaps = True
                break
        if state.level and state.level.moving_health_zone and r.colliderect(state.level.moving_health_zone["rect"]):
            overlaps = True
        
        if not overlaps:
            # All pickups look the same (mystery) - randomized color so player doesn't know what they're getting
            mystery_colors = [
                (180, 100, 255),  # purple
                (100, 255, 180),  # green
                (255, 180, 100),  # orange
                (180, 255, 255),  # cyan
                (255, 100, 180),  # pink
                (255, 255, 100),  # yellow
            ]
            color = random.choice(mystery_colors)
            run_time = getattr(state, "run_time", 0.0)
            state.pickups.append({
                "type": pickup_type,
                "rect": r,
                "color": color,
                "timer": 15.0,
                "age": 0.0,
                "spawn_t": run_time,
            })
            return


def spawn_weapon_in_center(weapon_type: str, state: "GameState", width: int, height: int) -> None:
    """Spawn a weapon pickup in the center of the screen (level completion reward).
    
    Only 'giant' weapon type is dropped.
    """
    if weapon_type not in ("giant", "giant_bullets"):
        return
    weapon_pickup_size = (80, 80)  # Bigger for level completion rewards
    weapon_pickup_rect = pygame.Rect(
        width // 2 - weapon_pickup_size[0] // 2,
        height // 2 - weapon_pickup_size[1] // 2,
        weapon_pickup_size[0],
        weapon_pickup_size[1]
    )
    run_time = getattr(state, "run_time", 0.0)
    state.pickups.append({
        "type": weapon_type,
        "rect": weapon_pickup_rect,
        "color": WEAPON_DISPLAY_COLORS.get(weapon_type, (180, 100, 255)),
        "timer": 30.0,  # Level completion weapons last longer
        "age": 0.0,
        "spawn_t": run_time,
        "is_weapon_drop": True,
        "is_level_reward": True,
    })


def spawn_weapon_drop(enemy: dict, state: "GameState") -> None:
    """Spawn a bonus-points drop from a killed enemy.
    
    1.5% chance to drop (1/10th of former 15% rate); despawns after 7s.
    """
    if random.random() >= 0.015:
        return
    size = (56, 56)
    r = pygame.Rect(
        enemy["rect"].centerx - size[0] // 2,
        enemy["rect"].centery - size[1] // 2,
        size[0], size[1]
    )
    run_time = getattr(state, "run_time", 0.0)
    state.pickups.append({
        "type": "bonus",
        "rect": r,
        "color": (255, 215, 0),  # gold for bonus points
        "spawn_t": run_time,
        "age": 0.0,
    })


def create_pickup_collection_effect(x: int, y: int, color: tuple[int, int, int], state: "GameState") -> None:
    """Create particle effect when pickup is collected."""
    for _ in range(12):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(50, 150)
        state.collection_effects.append({
            "x": float(x),
            "y": float(y),
            "vel_x": math.cos(angle) * speed,
            "vel_y": math.sin(angle) * speed,
            "color": color,
            "life": 0.4,
            "size": random.randint(3, 6),
        })
