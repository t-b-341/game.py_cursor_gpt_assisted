"""Gameplay input parsing: movement, firing, weapons, abilities. Called only when state is PLAYING or ENDURANCE."""
from __future__ import annotations

import random

import pygame

from constants import (
    AIM_ARROWS,
    MOUSE_BUTTON_RIGHT,
    STATE_ENDURANCE,
    STATE_PLAYING,
    ally_drop_cooldown,
    grenade_cooldown,
    grenade_damage,
    jump_cooldown,
    jump_duration,
    jump_speed,
    missile_cooldown,
    missile_damage,
    overshield_recharge_cooldown,
    shield_duration,
)
from config_enemies import FRIENDLY_AI_TEMPLATES
from allies import make_friendly_from_template


def _add_particle_effect(player_rect, camera, ctx, effect_type: str) -> None:
    """Add a particle effect at the player's position.
    
    Args:
        player_rect: Player's rect for position
        camera: Camera object for coordinate conversion
        ctx: Context with display dimensions
        effect_type: "shot", "rocket", or "bomb"
    """
    try:
        from systems.shot_particle_state import get_shot_particle_state, EffectType
        
        # Get display dimensions
        display_w = ctx.get("width", 800)
        display_h = ctx.get("height", 600)
        
        # Convert to normalized screen coordinates
        if camera:
            screen_x = (player_rect.centerx - camera.x) / display_w
            screen_y = (player_rect.centery - camera.y) / display_h
        else:
            screen_x = player_rect.centerx / display_w
            screen_y = player_rect.centery / display_h
        
        # Clamp to valid range
        screen_x = max(0.0, min(1.0, screen_x))
        screen_y = max(0.0, min(1.0, screen_y))
        
        # Add the appropriate effect
        shot_state = get_shot_particle_state()
        if effect_type == "rocket":
            shot_state.add_rocket((screen_x, screen_y))
        elif effect_type == "bomb":
            shot_state.add_bomb((screen_x, screen_y))
        else:
            shot_state.add_shot((screen_x, screen_y))
    except Exception:
        pass  # Silently fail if particle system unavailable


def _scale_mouse_pos(pos: tuple[int, int], world_scale: float, camera=None) -> tuple[float, float]:
    """Scale mouse position from display space to world space.
    
    If camera is provided, uses camera offset instead of world_scale.
    """
    if camera is not None:
        # Camera mode: screen -> world
        return camera.screen_to_world(pos[0], pos[1])
    elif world_scale > 1.0:
        # Legacy scaling mode
        return (float(pos[0] * world_scale), float(pos[1] * world_scale))
    return (float(pos[0]), float(pos[1]))


def handle_gameplay_input(events, game_state, ctx) -> None:
    """Parse gameplay-only input: move, jump/dash, fire, weapon switch, abilities.
    ctx must have: controls, aiming_mode, width, height, spawn_player_bullet, spawn_laser_beam.
    Only call when game_state.current_screen is STATE_PLAYING or STATE_ENDURANCE.
    """
    from systems.camera import get_camera
    
    state = getattr(game_state, "current_screen", None)
    if state not in (STATE_PLAYING, STATE_ENDURANCE):
        return

    controls = ctx.get("controls") or {}
    aiming_mode = ctx.get("aiming_mode")
    player = game_state.player_rect
    
    # Get world scale and camera for mouse coordinate conversion
    world_scale = ctx.get("world_scale", 1.0)
    camera = get_camera()  # Use camera if available

    # ---- Event-driven: direct allies, shield, overshield, grenade, missile, ally drop, weapon switch, dash ----
    direct_allies_binding = controls.get("direct_allies", MOUSE_BUTTON_RIGHT)
    overshield_recharge_cooldown_val = ctx.get("overshield_recharge_cooldown", overshield_recharge_cooldown)
    shield_duration_val = ctx.get("shield_duration", shield_duration)
    grenade_cooldown_val = ctx.get("grenade_cooldown", grenade_cooldown)
    missile_cooldown_val = ctx.get("missile_cooldown", missile_cooldown)
    ally_drop_cooldown_val = ctx.get("ally_drop_cooldown", ally_drop_cooldown)
    overshield_max = ctx.get("overshield_max", 0)

    for event in events:
        if event.type == pygame.MOUSEBUTTONDOWN:
            if direct_allies_binding == MOUSE_BUTTON_RIGHT and event.button == 3:
                # Scale mouse position to world coordinates
                world_pos = _scale_mouse_pos(event.pos, world_scale, camera)
                game_state.ally_command_target = world_pos
                game_state.ally_command_timer = 5.0

        if event.type == pygame.KEYDOWN:
            if direct_allies_binding != MOUSE_BUTTON_RIGHT and event.key == direct_allies_binding:
                mx, my = pygame.mouse.get_pos()
                world_pos = _scale_mouse_pos((mx, my), world_scale, camera)
                game_state.ally_command_target = world_pos
                game_state.ally_command_timer = 5.0

            if event.key == pygame.K_LALT:
                if (game_state.shield_recharge_timer >= game_state.shield_recharge_cooldown
                        and not game_state.shield_active):
                    game_state.shield_active = True
                    game_state.shield_duration_remaining = shield_duration_val
                    game_state.shield_cooldown = shield_duration_val
                    game_state.shield_recharge_cooldown = game_state.shield_cooldown
                    game_state.shield_recharge_timer = 0.0
                    game_state.shield_cooldown_remaining = 0.0

            if event.key == pygame.K_TAB:
                if game_state.overshield_recharge_timer >= overshield_recharge_cooldown_val:
                    game_state.overshield = game_state.player_max_hp
                    game_state.armor_drain_timer = 0.0
                    game_state.overshield_recharge_timer = 0.0

            if event.key == pygame.K_e and player:
                if game_state.grenade_time_since_used >= grenade_cooldown_val:
                    r = player.w * 10
                    game_state.grenade_explosions.append({
                        "x": player.centerx, "y": player.centery, "radius": 0, "max_radius": r,
                        "timer": 0.3, "damage": grenade_damage, "source": "player",
                    })
                    game_state.grenade_time_since_used = 0.0
                    # Play grenade sound
                    from systems.audio_system import play_sfx
                    play_sfx("GRENADE")
                    # Add bomb particle effect
                    _add_particle_effect(player, camera, ctx, "bomb")

            if event.key == pygame.K_r and player:
                if game_state.missile_time_since_used >= missile_cooldown_val:
                    target_enemy = None
                    min_dist = float("inf")
                    for enemy in game_state.enemies:
                        d = (pygame.Vector2(enemy["rect"].center) - pygame.Vector2(player.center)).length_squared()
                        if d < min_dist:
                            min_dist, target_enemy = d, enemy
                    if target_enemy:
                        for ox, oy in [(-10, -10), (0, -15), (10, -10)]:
                            mr = pygame.Rect(player.centerx - 8 + ox, player.centery - 8 + oy, 16, 16)
                            game_state.missiles.append({
                                "rect": mr, "vel": pygame.Vector2(0, 0), "target_enemy": target_enemy,
                                "speed": 500, "damage": missile_damage, "explosion_radius": 150,
                            })
                        game_state.missile_time_since_used = 0.0
                        # Play rocket sound
                        from systems.audio_system import play_sfx
                        play_sfx("ROCKET")
                        # Add rocket particle effect
                        _add_particle_effect(player, camera, ctx, "rocket")

            if event.key == controls.get("ally_drop", pygame.K_q) and player:
                # Only use ability if cooldown is ready - otherwise ignore the keypress
                if game_state.ally_drop_timer >= ally_drop_cooldown_val and FRIENDLY_AI_TEMPLATES:
                    ally_template = random.choice(FRIENDLY_AI_TEMPLATES)
                    pc = pygame.Vector2(player.center)
                    d = (-game_state.last_move_velocity.normalize() if game_state.last_move_velocity.length_squared() > 0
                         else pygame.Vector2(0, 1))
                    pos = pc + d * 60
                    friendly = make_friendly_from_template(ally_template, 1.0, 1.0)
                    hp = max(1, game_state.player_max_hp // 2)
                    friendly["hp"] = friendly["max_hp"] = hp
                    friendly["rect"].center = (int(pos.x), int(pos.y))
                    friendly["is_dropped_ally"] = True
                    game_state.friendly_ai.append(friendly)
                    game_state.dropped_ally = friendly
                    game_state.ally_drop_timer = 0.0

            if event.key == pygame.K_1 and "triple" in game_state.unlocked_weapons:
                game_state.previous_weapon_mode = game_state.current_weapon_mode
                if game_state.previous_weapon_mode == "laser":
                    game_state.laser_beams.clear()
                game_state.current_weapon_mode = "triple"
            elif event.key == pygame.K_2 and "laser" in game_state.unlocked_weapons:
                game_state.previous_weapon_mode = game_state.current_weapon_mode
                if game_state.previous_weapon_mode == "laser":
                    game_state.laser_beams.clear()
                game_state.current_weapon_mode = "laser"
            elif event.key == pygame.K_3 and "giant" in game_state.unlocked_weapons:
                game_state.previous_weapon_mode = game_state.current_weapon_mode
                if game_state.previous_weapon_mode == "laser":
                    game_state.laser_beams.clear()
                game_state.current_weapon_mode = "giant"

            dash_key = controls.get("dash", pygame.K_SPACE)
            if event.key == dash_key:
                if (not game_state.is_jumping
                        and getattr(game_state, "jump_cooldown_timer", 0.0) >= jump_cooldown):
                    game_state.is_jumping = True
                    game_state.jump_timer = 0.0
                    game_state.jump_cooldown_timer = 0.0
                    lv = game_state.last_move_velocity
                    if lv.length_squared() > 0:
                        game_state.jump_velocity = lv.normalize() * jump_speed
                    else:
                        game_state.jump_velocity = pygame.Vector2(0, -jump_speed)
                    # Play dodge sound
                    from systems.audio_system import play_sfx
                    play_sfx("DODGE")

    # ---- Polled: movement, boost/slow, fire, laser ----
    keys = pygame.key.get_pressed()
    move_x = 0
    move_y = 0
    if keys[controls.get("move_left", pygame.K_a)]:
        move_x = -1
        game_state.last_horizontal_key = controls.get("move_left", pygame.K_a)
    elif keys[controls.get("move_right", pygame.K_d)]:
        move_x = 1
        game_state.last_horizontal_key = controls.get("move_right", pygame.K_d)
    if keys[controls.get("move_up", pygame.K_w)]:
        move_y = -1
        game_state.last_vertical_key = controls.get("move_up", pygame.K_w)
    elif keys[controls.get("move_down", pygame.K_s)]:
        move_y = 1
        game_state.last_vertical_key = controls.get("move_down", pygame.K_s)

    boost_meter_max = ctx.get("boost_meter_max", 100.0)
    boost_drain = ctx.get("boost_drain_per_s", 45.0)
    boost_regen = ctx.get("boost_regen_per_s", 25.0)
    boost_speed_mult = ctx.get("boost_speed_mult", 1.7)
    slow_speed_mult = ctx.get("slow_speed_mult", 0.45)
    dt = ctx.get("dt", 0.016)

    is_boosting = keys[controls.get("boost", pygame.K_LSHIFT)] and game_state.boost_meter > 0
    is_slowing = keys[controls.get("slow", pygame.K_LCTRL)]
    if is_boosting:
        game_state.boost_meter = max(0, game_state.boost_meter - boost_drain * dt)
        game_state.speed_mult = boost_speed_mult
        game_state.previous_boost_state = True
    else:
        game_state.boost_meter = min(boost_meter_max, game_state.boost_meter + boost_regen * dt)
        game_state.speed_mult = 1.0
        game_state.previous_boost_state = False
    if is_slowing:
        game_state.speed_mult *= slow_speed_mult
        game_state.previous_slow_state = True
    else:
        game_state.previous_slow_state = False

    game_state.move_input_x = move_x
    game_state.move_input_y = move_y

    # Fire and laser: set flag and call callbacks; callbacks (from game.py) perform cooldown check and spawn
    mouse = pygame.mouse.get_pressed()
    shoot_input = mouse[0] or (aiming_mode == AIM_ARROWS and (
        keys[pygame.K_LEFT] or keys[pygame.K_RIGHT] or keys[pygame.K_UP] or keys[pygame.K_DOWN]))
    game_state.fire_pressed = shoot_input
    if ctx.get("spawn_player_bullet"):
        ctx["spawn_player_bullet"]()
    if ctx.get("spawn_laser_beam"):
        ctx["spawn_laser_beam"]()
