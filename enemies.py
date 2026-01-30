"""Enemy behavior and helper functions."""
import math
import random
import pygame
from entities import Enemy
from config_enemies import (
    ENEMY_HP_SCALE_MULTIPLIER,
    ENEMY_SPEED_SCALE_MULTIPLIER,
    ENEMY_FIRE_RATE_MULTIPLIER,
    ENEMY_HP_CAP,
    QUEEN_FIXED_HP,
)
from constants import (
    ENEMY_COLOR,
    ENEMY_PROJECTILES_COLOR,
    ALLY_AGGRO_RADIUS,
    ALLY_AGGRO_PRIORITY,
    DROPPED_ALLY_AGGRO_RADIUS,
    DROPPED_ALLY_AGGRO_PRIORITY,
)
from geometry_utils import clamp_rect_to_screen
from physics_loader import distance_squared as c_distance_squared
from telemetry import EnemySpawnEvent


def move_enemy_with_push_cached(
    enemy_rect: pygame.Rect,
    move_x: int,
    move_y: int,
    block_list: list[dict],
    cached_moveable_destructible_rects: list,
    cached_trapezoid_rects: list,
    cached_triangle_rects: list,
    destructible_blocks: list[dict],
    giant_blocks: list[dict],
    super_giant_blocks: list[dict],
    pickups: list[dict],
    friendly_ai: list[dict],
    enemies: list[dict],
    player: pygame.Rect,
    moving_health_zone: dict,
    width: int,
    height: int,
):
    """Optimized enemy movement - enemies cannot go through objects and must navigate around them."""
    # Cache rects for performance
    block_rects = [b["rect"] for b in block_list]
    cached_destructible_rects = [b["rect"] for b in destructible_blocks]
    cached_giant_rects = [gb["rect"] for gb in giant_blocks]
    cached_super_giant_rects = [sgb["rect"] for sgb in super_giant_blocks]
    cached_pickup_rects = [p["rect"] for p in pickups]
    cached_friendly_rects = [f["rect"] for f in friendly_ai if f.get("hp", 1) > 0]
    cached_enemy_rects = [e["rect"] for e in enemies if e["rect"] is not enemy_rect]

    for axis_dx, axis_dy in [(move_x, 0), (0, move_y)]:
        if axis_dx == 0 and axis_dy == 0:
            continue

        enemy_rect.x += axis_dx
        enemy_rect.y += axis_dy

        # Check collisions with all objects - enemies cannot pass through anything
        collision = False
        
        # Check regular blocks
        for rect in block_rects:
            if enemy_rect.colliderect(rect):
                collision = True
                break
        
        # Check destructible blocks
        if not collision:
            for rect in cached_destructible_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break
        
        # Check moveable destructible blocks
        if not collision:
            for rect in cached_moveable_destructible_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break
        
        # Check giant blocks (unmovable)
        if not collision:
            for rect in cached_giant_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break
        
        # Check super giant blocks (unmovable)
        if not collision:
            for rect in cached_super_giant_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break
        
        # Check trapezoid blocks
        if not collision:
            for rect in cached_trapezoid_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break
        
        # Check triangle blocks
        if not collision:
            for rect in cached_triangle_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break
        
        # Check pickups
        if not collision:
            for rect in cached_pickup_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break
        
        # Check health zone
        if not collision:
            if enemy_rect.colliderect(moving_health_zone["rect"]):
                collision = True
        
        # Check player
        if not collision:
            if enemy_rect.colliderect(player):
                collision = True
        
        # Check friendly AI
        if not collision:
            for rect in cached_friendly_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break
        
        # Check other enemies (prevent enemy stacking)
        if not collision:
            for rect in cached_enemy_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break

        # If collision detected, revert movement
        if collision:
            enemy_rect.x -= axis_dx
            enemy_rect.y -= axis_dy

    clamp_rect_to_screen(enemy_rect, width, height)


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


def make_enemy_from_template(t: dict, hp_scale: float, speed_scale: float) -> Enemy:
    """Create an enemy from a template with scaling applied."""
    # Apply scaling multipliers from config
    # Exception: Queen (player clone) has fixed HP and special speed multiplier
    if t.get("type") == "queen":
        hp = QUEEN_FIXED_HP
        base_speed = t.get("speed", 80)
        final_speed = base_speed * ENEMY_SPEED_SCALE_MULTIPLIER
    elif t.get("type") in ("super_large", "super_large_triple_laser"):
        hp = int(t["hp"] * hp_scale * 1.5)  # Scale but no normal cap
        base_spd = t.get("speed", 20)
        final_speed = base_spd * speed_scale * ENEMY_SPEED_SCALE_MULTIPLIER
    elif t.get("type") == "large_laser":
        hp = int(t["hp"] * hp_scale * ENEMY_HP_SCALE_MULTIPLIER * 10)
        hp = min(hp, ENEMY_HP_CAP * 10)
        final_speed = t.get("speed", 50) * speed_scale * ENEMY_SPEED_SCALE_MULTIPLIER
    elif t.get("is_ambient"):
        hp = t["hp"]
        final_speed = 0  # Stationary
    else:
        hp = int(t["hp"] * hp_scale * ENEMY_HP_SCALE_MULTIPLIER * 10)
        hp = min(hp, ENEMY_HP_CAP * 10)
        final_speed = t.get("speed", 80) * speed_scale * ENEMY_SPEED_SCALE_MULTIPLIER

    shoot_cd = t["shoot_cooldown"] / ENEMY_FIRE_RATE_MULTIPLIER
    if t.get("is_ambient"):
        shoot_cd = t["shoot_cooldown"]  # Ambient: rocket every 6s, no fire-rate modifier
    
    enemy = {
        "type": t["type"],
        "rect": pygame.Rect(t["rect"].x, t["rect"].y, t["rect"].w, t["rect"].h),
        "color": t.get("color", ENEMY_COLOR),  # Use template color if specified, else default red
        "hp": hp,
        "max_hp": hp,
        "shoot_cooldown": shoot_cd,
        "time_since_shot": random.uniform(0.0, shoot_cd),
        "projectile_speed": t["projectile_speed"],
        "projectile_color": t.get("projectile_color", ENEMY_PROJECTILES_COLOR),
        "projectile_shape": t.get("projectile_shape", "circle"),
        "speed": final_speed,  # Speed (queen gets special multiplier, others get normal scaling)
    }
    # Add shield properties if present
    if t.get("has_shield"):
        enemy["has_shield"] = True
        enemy["shield_angle"] = random.uniform(0, 2 * math.pi)
        enemy["shield_length"] = t.get("shield_length", 50)
    if t.get("has_reflective_shield"):
        enemy["has_reflective_shield"] = True
        enemy["shield_angle"] = random.uniform(0, 2 * math.pi)
        enemy["shield_length"] = t.get("shield_length", 60)
        enemy["shield_hp"] = 0
        enemy["turn_speed"] = t.get("turn_speed", 0.5)
    if t.get("is_predictive"):
        enemy["is_predictive"] = True
    if t.get("is_evasive"):
        enemy["is_evasive"] = True
    if t.get("shape"):
        enemy["shape"] = t["shape"]
    if t.get("is_ambient"):
        enemy["is_ambient"] = True
        enemy["rocket_cooldown"] = t.get("rocket_cooldown", 0.0)
    if t.get("enemy_size_class"):
        enemy["enemy_size_class"] = t["enemy_size_class"]
    if t.get("is_flamethrower"):
        enemy["is_flamethrower"] = True
        enemy["flame_damage"] = t.get("flame_damage", 8)
    if t.get("reflect_damage_mult") is not None:
        enemy["reflect_damage_mult"] = t["reflect_damage_mult"]
    if t.get("fires_rockets"):
        enemy["fires_rockets"] = True
        enemy["rocket_cooldown"] = t.get("rocket_cooldown", 0.0)
        enemy["rocket_interval"] = t.get("rocket_interval", 5.0)
    if t.get("can_use_grenades_player_allies_only"):
        enemy["can_use_grenades_player_allies_only"] = True
        enemy["grenade_cooldown"] = t.get("grenade_cooldown", 8.0)
        enemy["time_since_grenade"] = t.get("time_since_grenade", 999.0)
        enemy["grenade_damage"] = t.get("grenade_damage", 400)
        enemy["grenade_radius"] = t.get("grenade_radius", 120)
    if t.get("fires_laser"):
        enemy["fires_laser"] = True
        enemy["laser_cooldown"] = t.get("laser_cooldown", 0.0)
        enemy["laser_interval"] = t.get("laser_interval", 3.0)
        enemy["laser_duration"] = t.get("laser_duration", 0.4)
        enemy["laser_deploy_time"] = t.get("laser_deploy_time", 2.0)
        enemy["laser_damage"] = t.get("laser_damage", 80)
        enemy["laser_length"] = t.get("laser_length", 600)
    if t.get("fires_triple_laser"):
        enemy["fires_triple_laser"] = True
        enemy["laser_cooldown"] = t.get("laser_cooldown", 0.0)
        enemy["laser_interval"] = t.get("laser_interval", 4.0)
        enemy["laser_duration"] = t.get("laser_duration", 0.5)
        enemy["laser_deploy_time"] = t.get("laser_deploy_time", 2.0)
        enemy["laser_damage"] = t.get("laser_damage", 120)
        enemy["laser_length"] = t.get("laser_length", 700)
        enemy["laser_spread_deg"] = t.get("laser_spread_deg", 15)
    
    # Add queen-specific properties
    if t.get("type") == "queen":
        enemy["name"] = t.get("name", "queen")
        enemy["can_use_grenades"] = t.get("can_use_grenades", False)
        enemy["grenade_cooldown"] = t.get("grenade_cooldown", 5.0)
        enemy["time_since_grenade"] = t.get("time_since_grenade", 999.0)
        enemy["damage_taken_since_rage"] = 0
        enemy["rage_mode_active"] = False
        enemy["rage_mode_timer"] = 0.0
        # rage_damage_threshold is set in template (randomized at module load time)
        enemy["rage_damage_threshold"] = t.get("rage_damage_threshold", random.randint(300, 500))
        enemy["predicts_player"] = t.get("predicts_player", False)
    return Enemy(enemy)


def log_enemy_spawns(
    new_enemies: list[dict],
    telemetry,
    run_time: float,
    enemies_spawned_ref: list[int],  # List with one element to simulate global variable
):
    """Log enemy spawns to telemetry."""
    for e in new_enemies:
        enemies_spawned_ref[0] += 1
        telemetry.log_enemy_spawn(
            EnemySpawnEvent(
                t=run_time,
                enemy_type=e["type"],
                x=e["rect"].x,
                y=e["rect"].y,
                w=e["rect"].w,
                h=e["rect"].h,
                hp=e["hp"],
            )
        )


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
