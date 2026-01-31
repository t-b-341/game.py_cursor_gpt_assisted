"""Enemy AI functions - threat detection and evasion."""
import math
import random

import pygame

from config.balance import (
    ALLY_AGGRO_RADIUS,
    ALLY_AGGRO_PRIORITY,
    DROPPED_ALLY_AGGRO_RADIUS,
    DROPPED_ALLY_AGGRO_PRIORITY,
    DECOY_AGGRO_RADIUS,
    DECOY_AGGRO_PRIORITY,
)
from physics_loader import distance_squared as c_distance_squared, find_dodge_threats


def find_nearest_threat(
    enemy_pos: pygame.Vector2,
    player: pygame.Rect | None,
    friendly_ai: list[dict],
    decoys: list[dict] | None = None,
    *,
    allow_player: bool = True,
) -> tuple[pygame.Vector2, str] | None:
    """Find the nearest threat (player or friendly AI or decoy) to an enemy.
    
    Aggro priority system:
    0. Decoys have HIGHEST priority - always targeted when in range (player's tactical distraction)
    1. Dropped allies have high priority within their large aggro radius (400px, 90% chance)
    2. Regular allies draw aggro within their radius (250px, 70% chance)
    3. Player is targeted if no allies are drawing aggro or RNG favors player
    4. Fallback to nearest friendly if player targeting not allowed
    
    This makes allies and decoys effective at tanking and drawing enemy fire away from the player.
    """
    if player is None or not allow_player:
        player_pos = None
    else:
        player_pos = pygame.Vector2(player.center)

    # Extract enemy position once for C function calls
    ex, ey = enemy_pos.x, enemy_pos.y

    # Priority 0: Check decoys first (highest priority - player's tactical distraction)
    decoy_aggro_radius_sq = DECOY_AGGRO_RADIUS * DECOY_AGGRO_RADIUS
    if decoys:
        decoy_threats = []
        for decoy in decoys:
            if decoy.get("hp", 0) <= 0:
                continue
            decoy_pos = pygame.Vector2(decoy["rect"].center)
            decoy_dist_sq = c_distance_squared(ex, ey, decoy_pos.x, decoy_pos.y)
            if decoy_dist_sq <= decoy_aggro_radius_sq:
                decoy_threats.append((decoy_pos, decoy_dist_sq))
        
        if decoy_threats:
            # Always target nearest decoy when in range
            decoy_threats.sort(key=lambda x: x[1])
            return (decoy_threats[0][0], "decoy")

    # Use configurable aggro radii
    dropped_aggro_radius_sq = DROPPED_ALLY_AGGRO_RADIUS * DROPPED_ALLY_AGGRO_RADIUS
    ally_aggro_radius_sq = ALLY_AGGRO_RADIUS * ALLY_AGGRO_RADIUS

    # Collect and categorize friendly AI threats by distance
    # Each entry: (position, distance_squared, target_type, aggro_radius_sq, aggro_priority)
    dropped_ally_threats = []
    regular_ally_threats = []
    
    for f in friendly_ai:
        if f.get("hp", 0) <= 0:
            continue
        friendly_pos = pygame.Vector2(f["rect"].center)
        # Use C-accelerated distance calculation
        friendly_dist_sq = c_distance_squared(ex, ey, friendly_pos.x, friendly_pos.y)
        
        # Get ally's aggro multiplier (tank allies can have higher values)
        aggro_mult = f.get("aggro_mult", 1.0)
        
        if f.get("is_dropped_ally", False):
            # Dropped allies use their own larger radius, scaled by aggro_mult
            effective_radius_sq = (DROPPED_ALLY_AGGRO_RADIUS * aggro_mult) ** 2
            dropped_ally_threats.append((
                friendly_pos, friendly_dist_sq, "dropped_ally",
                effective_radius_sq, DROPPED_ALLY_AGGRO_PRIORITY
            ))
        else:
            # Regular allies use base radius, scaled by aggro_mult
            effective_radius_sq = (ALLY_AGGRO_RADIUS * aggro_mult) ** 2
            regular_ally_threats.append((
                friendly_pos, friendly_dist_sq, "friendly",
                effective_radius_sq, ALLY_AGGRO_PRIORITY
            ))
    
    # Sort by distance (closest first)
    dropped_ally_threats.sort(key=lambda x: x[1])
    regular_ally_threats.sort(key=lambda x: x[1])
    
    # Priority 1: Dropped allies within their aggro radius (highest priority)
    # Dropped allies ALWAYS draw aggro when in range - this is a deliberate player tactic
    if dropped_ally_threats:
        nearest_dropped = dropped_ally_threats[0]
        pos, dist_sq, target_type, radius_sq, _priority = nearest_dropped
        if dist_sq <= radius_sq:
            return (pos, target_type)
    
    # Priority 2: Regular allies within their aggro radius
    # Regular allies have a CHANCE to draw aggro, creating more dynamic combat
    if regular_ally_threats:
        nearest_ally = regular_ally_threats[0]
        pos, dist_sq, target_type, radius_sq, priority = nearest_ally
        if dist_sq <= radius_sq:
            # Probability-based targeting creates variety in combat
            if random.random() < priority:
                return (pos, target_type)
    
    # Priority 3: Target player if allowed
    if player_pos is not None:
        return (player_pos, "player")
    
    # Fallback: target nearest friendly (any type) if player not available
    all_friendlies = dropped_ally_threats + regular_ally_threats
    if all_friendlies:
        all_friendlies.sort(key=lambda x: x[1])
        nearest = all_friendlies[0]
        return (nearest[0], nearest[2])
    
    return None


def find_threats_in_dodge_range(
    enemy_pos: pygame.Vector2,
    player_bullets: list[dict],
    friendly_projectiles: list[dict],
    dodge_range: float = 200.0,
) -> list[pygame.Vector2]:
    """Find bullets (player or friendly) that are close enough to dodge.
    
    Uses C-accelerated find_dodge_threats for performance.
    """
    ex, ey = enemy_pos.x, enemy_pos.y
    dodge_range_sq = dodge_range * dodge_range
    time_threshold = 0.5  # Only dodge bullets that will hit within 0.5 seconds
    
    # Combine all projectiles for batch processing
    all_projectiles = list(player_bullets) + list(friendly_projectiles)
    if not all_projectiles:
        return []
    
    # Extract data for C function
    bullets_x = []
    bullets_y = []
    bullets_vx = []
    bullets_vy = []
    
    for b in all_projectiles:
        bullets_x.append(float(b["rect"].centerx))
        bullets_y.append(float(b["rect"].centery))
        vel = b.get("vel")
        if vel is not None:
            bullets_vx.append(float(vel.x) if hasattr(vel, 'x') else float(vel[0]))
            bullets_vy.append(float(vel.y) if hasattr(vel, 'y') else float(vel[1]))
        else:
            bullets_vx.append(0.0)
            bullets_vy.append(0.0)
    
    # Use C-accelerated function
    threat_indices = find_dodge_threats(
        ex, ey, dodge_range_sq, time_threshold,
        bullets_x, bullets_y, bullets_vx, bullets_vy
    )
    
    # Convert indices to Vector2 positions
    threats = []
    for idx in threat_indices:
        if 0 <= idx < len(all_projectiles):
            b = all_projectiles[idx]
            threats.append(pygame.Vector2(b["rect"].centerx, b["rect"].centery))
    
    return threats
