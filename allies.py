"""Ally and friendly AI behavior and helper functions."""
import random
import pygame
from entities import Friendly
from telemetry import FriendlyAISpawnEvent, FriendlyAIShotEvent


def find_nearest_enemy(friendly_pos: pygame.Vector2, enemies: list[dict]) -> dict | None:
    """Find the nearest enemy to a friendly AI unit."""
    if not enemies:
        return None
    nearest = None
    min_dist = float("inf")
    for e in enemies:
        dist = (pygame.Vector2(e["rect"].center) - friendly_pos).length_squared()
        if dist < min_dist:
            min_dist = dist
            nearest = e
    return nearest


def make_friendly_from_template(t: dict, hp_scale: float, speed_scale: float) -> Friendly:
    """Create a friendly AI unit from a template."""
    # Randomize health between 50-100, full health at wave start (green bar)
    max_hp = random.randint(50, 100)
    hp = max_hp  # Always start with full health at wave start (green bar)
    data = {
        "type": t["type"],
        "rect": pygame.Rect(t["rect"].x, t["rect"].y, t["rect"].w, t["rect"].h),
        "color": t["color"],
        "hp": hp,
        "max_hp": max_hp,  # Full health, green bar at wave start
        "shoot_cooldown": t["shoot_cooldown"] / 3.0,  # 300% fire rate (faster = lower cooldown, increased from 1.5)
        "time_since_shot": random.uniform(0.0, t["shoot_cooldown"] / 3.0),
        "projectile_speed": t["projectile_speed"],
        "projectile_color": t["projectile_color"],
        "projectile_shape": t["projectile_shape"],
        "speed": t["speed"] * speed_scale * 2.2,  # 2x movement speed (was 1.1)
        "behavior": t["behavior"],
        "damage": int(t["damage"] * 1.1),  # 110% damage
        "target": None,  # Current target enemy
        "aggro_mult": t.get("aggro_mult", 1.0),  # Multiplier for aggro radius (tank allies can have higher)
    }
    if t.get("fires_missiles"):
        data["fires_missiles"] = True
        data["missile_burst_interval"] = t.get("missile_burst_interval", 7.0)
        data["missile_burst_count"] = t.get("missile_burst_count", 3)
        data["missile_damage"] = t.get("missile_damage", 300)
        data["missile_explosion_radius"] = t.get("missile_explosion_radius", 80)
        data["ally_missile_cooldown"] = 0.0
    return Friendly(data)


def spawn_friendly_ai(
    count: int,
    hp_scale: float,
    speed_scale: float,
    friendly_ai_templates: list[dict],
    friendly_ai: list[dict],
    random_spawn_position,
    telemetry,
    run_time: float,
):
    """Spawn friendly AI units."""
    spawned_list = []
    for _ in range(count):
        tmpl = random.choice(friendly_ai_templates)
        friendly = make_friendly_from_template(tmpl, hp_scale, speed_scale)
        # Use random_spawn_position to prevent spawning on blocks or health zone
        friendly["rect"] = random_spawn_position((friendly["rect"].w, friendly["rect"].h))
        friendly_ai.append(friendly)
        spawned_list.append(friendly)
    
    # Log friendly AI spawns
    for f in spawned_list:
        telemetry.log_friendly_spawn(
            FriendlyAISpawnEvent(
                t=run_time,
                friendly_type=f["type"],
                x=f["rect"].x,
                y=f["rect"].y,
                w=f["rect"].w,
                h=f["rect"].h,
                hp=f["hp"],
                behavior=f["behavior"],
            )
        )


def spawn_friendly_projectile(
    friendly: dict,
    target: dict,
    friendly_projectiles: list[dict],
    vec_toward,
    telemetry,
    run_time: float,
):
    """Spawn a projectile from friendly AI targeting an enemy."""
    d = vec_toward(
        friendly["rect"].centerx, friendly["rect"].centery,
        target["rect"].centerx, target["rect"].centery
    )
    r = pygame.Rect(
        friendly["rect"].centerx - 6,
        friendly["rect"].centery - 6,
        12, 12
    )
    friendly_projectiles.append({
        "rect": r,
        "vel": d * friendly["projectile_speed"],
        "damage": friendly["damage"],
        "color": friendly["projectile_color"],
        "shape": friendly["projectile_shape"],
        "source_type": friendly["type"],
        "target_enemy_type": target.get("type", "unknown"),  # Store target type for telemetry
    })
    
    # Log friendly AI shot
    telemetry.log_friendly_shot(
        FriendlyAIShotEvent(
            t=run_time,
            friendly_type=friendly["type"],
            origin_x=friendly["rect"].centerx,
            origin_y=friendly["rect"].centery,
            target_x=target["rect"].centerx,
            target_y=target["rect"].centery,
            target_enemy_type=target.get("type", "unknown"),
        )
    )


def update_friendly_ai(
    friendly_ai: list[dict],
    enemies: list[dict],
    blocks: list[dict],
    dt: float,
    find_nearest_enemy_func,
    vec_toward_func,
    move_enemy_with_push_func,
    spawn_friendly_projectile_func,
    state=None,
    *,
    player_rect=None,
    spawn_ally_missile_func=None,
):
    """Update friendly AI movement, targeting, and shooting.
    Allies follow the player around the map; move target is always player (or ally_command_target when active).
    Enemy is used only for shooting when in range.
    Allies with fires_missiles use spawn_ally_missile_func for 3-shot burst every 7s (or template interval).
    
    When an ally is commanded (right-click) and collides with an enemy, the ally explodes
    with a radius of 1/2 the player's bomb size.
    
    Args:
        friendly_ai: List of friendly AI units (modified in place)
        enemies: List of enemy units
        blocks: List of block objects for collision
        dt: Delta time
        find_nearest_enemy_func: Function to find nearest enemy
        vec_toward_func: Function to calculate direction vector
        move_enemy_with_push_func: Function to move friendly with collision
        spawn_friendly_projectile_func: Function to spawn friendly projectile
        state: Game state (for ally_command_target); optional
        player_rect: If provided, used as follow target; otherwise state.player_rect. Pass explicitly so ally follows reliably.
        spawn_ally_missile_func: Optional (friendly, target, state) -> None for missile-firing allies.
    """
    if player_rect is None and state is not None:
        player_rect = getattr(state, "player_rect", None)
    ally_cmd = getattr(state, "ally_command_target", None) if state else None
    ally_cmd_time = getattr(state, "ally_command_timer", 0.0) if state else 0.0

    for friendly in friendly_ai[:]:
        if friendly.get("hp", 1) <= 0:
            friendly_ai.remove(friendly)
            continue

        target = find_nearest_enemy_func(pygame.Vector2(friendly["rect"].center), enemies)
        move_toward_x, move_toward_y = None, None

        # Follow player around map: move toward player (or command target); only use enemy for shooting
        is_commanded = ally_cmd is not None and ally_cmd_time > 0
        if is_commanded:
            move_toward_x, move_toward_y = ally_cmd[0], ally_cmd[1]
        elif player_rect is not None:
            move_toward_x = player_rect.centerx
            move_toward_y = player_rect.centery

        if move_toward_x is not None and move_toward_y is not None:
            direction = vec_toward_func(
                friendly["rect"].centerx, friendly["rect"].centery,
                move_toward_x, move_toward_y
            )
            friendly_speed = friendly.get("speed", 100) * dt
            move_x = int(direction.x * friendly_speed)
            move_y = int(direction.y * friendly_speed)
            move_enemy_with_push_func(friendly["rect"], move_x, move_y, blocks)

        # When commanded (right-click), check for collision/proximity with enemies and explode
        if is_commanded and state is not None and player_rect is not None:
            ally_rect = friendly.get("rect") if hasattr(friendly, "get") else friendly["rect"]
            if ally_rect is None:
                continue
            ally_center = pygame.Vector2(ally_rect.center)
            # Proximity threshold: ally explodes when within this distance of enemy center
            # Using a combination of rect collision OR center-to-center distance
            proximity_threshold = max(ally_rect.w, ally_rect.h) + 10  # Ally size + small buffer
            
            for enemy in enemies:
                if enemy.get("hp", 0) <= 0:
                    continue
                enemy_rect = enemy.get("rect") if hasattr(enemy, "get") else enemy["rect"]
                if enemy_rect is None:
                    continue
                    
                # Check both rect collision AND proximity (center-to-center distance)
                enemy_center = pygame.Vector2(enemy_rect.center)
                distance = (ally_center - enemy_center).length()
                collides = ally_rect.colliderect(enemy_rect) or distance < proximity_threshold
                
                if collides:
                    # Explode! Radius = 1/2 of player's bomb (player bomb = player.w * 10)
                    explosion_radius = player_rect.w * 5 if player_rect else 140
                    grenade_explosions = getattr(state, "grenade_explosions", None)
                    if grenade_explosions is not None:
                        grenade_explosions.append({
                            "x": ally_rect.centerx,
                            "y": ally_rect.centery,
                            "radius": 0,
                            "max_radius": explosion_radius,
                            "timer": 0.3,
                            "damage": 750,  # Half of player grenade damage (1500 / 2)
                            "source": "ally_explosion",
                        })
                        # Play explosion sound
                        from systems.audio_system import play_sfx
                        play_sfx("GRENADE")
                    # Kill the ally
                    friendly["hp"] = 0
                    if friendly in friendly_ai:
                        friendly_ai.remove(friendly)
                    break  # Ally is gone, stop checking enemies

        # Skip shooting if ally just exploded
        if friendly.get("hp", 0) <= 0:
            continue

        if target:
            if friendly.get("fires_missiles") and spawn_ally_missile_func and state is not None:
                friendly["ally_missile_cooldown"] = friendly.get("ally_missile_cooldown", 0.0) + dt
                if friendly["ally_missile_cooldown"] >= friendly.get("missile_burst_interval", 7.0):
                    spawn_ally_missile_func(friendly, target, state)
                    friendly["ally_missile_cooldown"] = 0.0
            else:
                friendly["shoot_cooldown"] = friendly.get("shoot_cooldown", 0.0) + dt
                if friendly["shoot_cooldown"] >= friendly.get("shoot_cooldown_time", 0.5):
                    spawn_friendly_projectile_func(friendly, target)
                    friendly["shoot_cooldown"] = 0.0
