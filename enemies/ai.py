"""Enemy AI functions - threat detection and evasion."""
import math
import random

import pygame

from constants import (
    ALLY_AGGRO_RADIUS,
    ALLY_AGGRO_PRIORITY,
    DROPPED_ALLY_AGGRO_RADIUS,
    DROPPED_ALLY_AGGRO_PRIORITY,
)
from physics_loader import distance_squared as c_distance_squared


def find_nearest_threat(
    enemy_pos: pygame.Vector2,
    player: pygame.Rect | None,
    friendly_ai: list[dict],
    *,
    allow_player: bool = True,
) -> tuple[pygame.Vector2, str] | None:
    """Find the nearest threat (player or friendly AI) to an enemy.
    
    Aggro priority system:
    1. Dropped allies have highest priority within their large aggro radius (400px, 90% chance)
    2. Regular allies draw aggro within their radius (250px, 70% chance)
    3. Player is targeted if no allies are drawing aggro or RNG favors player
    4. Fallback to nearest friendly if player targeting not allowed
    
    This makes allies effective at tanking and drawing enemy fire away from the player.
    """
    if player is None or not allow_player:
        player_pos = None
    else:
        player_pos = pygame.Vector2(player.center)

    # Use configurable aggro radii
    dropped_aggro_radius_sq = DROPPED_ALLY_AGGRO_RADIUS * DROPPED_ALLY_AGGRO_RADIUS
    ally_aggro_radius_sq = ALLY_AGGRO_RADIUS * ALLY_AGGRO_RADIUS

    # Collect and categorize friendly AI threats by distance
    # Each entry: (position, distance_squared, target_type, aggro_radius_sq, aggro_priority)
    dropped_ally_threats = []
    regular_ally_threats = []
    
    # Extract enemy position once for C function calls
    ex, ey = enemy_pos.x, enemy_pos.y
    
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
    """Find bullets (player or friendly) that are close enough to dodge."""
    threats = []
    enemy_v2 = pygame.Vector2(enemy_pos)
    dodge_range_sq = dodge_range * dodge_range  # Use squared distance for faster comparison
    
    # Check player bullets
    for b in player_bullets:
        bullet_pos = pygame.Vector2(b["rect"].center)
        dist_sq = (bullet_pos - enemy_v2).length_squared()
        if dist_sq < dodge_range_sq:
            # Only compute actual distance if in range
            dist = math.sqrt(dist_sq)
            # Predict where bullet will be
            bullet_vel = b.get("vel", pygame.Vector2(0, 0))
            vel_length = bullet_vel.length()
            time_to_reach = dist / vel_length if vel_length > 0 else 999
            if time_to_reach < 0.5:  # Only dodge if bullet will reach soon
                threats.append(bullet_pos)
    
    # Check friendly projectiles
    for fp in friendly_projectiles:
        bullet_pos = pygame.Vector2(fp["rect"].center)
        dist_sq = (bullet_pos - enemy_v2).length_squared()
        if dist_sq < dodge_range_sq:
            # Only compute actual distance if in range
            dist = math.sqrt(dist_sq)
            bullet_vel = fp.get("vel", pygame.Vector2(0, 0))
            vel_length = bullet_vel.length()
            time_to_reach = dist / vel_length if vel_length > 0 else 999
            if time_to_reach < 0.5:
                threats.append(bullet_pos)
    
    return threats
