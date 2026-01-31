"""
Simulation update steps for one fixed timestep. Run in order via SIMULATION_SYSTEMS.
Each function has signature (gs, sim_dt, app_ctx). game.py calls these from _update_simulation.
"""
from __future__ import annotations

import pygame

from config.balance import jump_duration
from context import AppContext
from game_utils import update_pickup_effects
from hazards import update_hazard_obstacles
from state import GameState
from systems.registry import SIMULATION_SYSTEMS as REGISTRY_SYSTEMS


def _sim_player_and_ability_timers(gs: GameState, sim_dt: float, app_ctx: AppContext) -> None:
    gs.player_time_since_shot += sim_dt
    gs.laser_time_since_shot += sim_dt
    gs.grenade_time_since_used += sim_dt
    gs.missile_time_since_used += sim_dt
    gs.jump_cooldown_timer += sim_dt
    gs.jump_timer += sim_dt
    gs.overshield_recharge_timer += sim_dt
    if gs.overshield > 0:
        gs.armor_drain_timer = getattr(gs, "armor_drain_timer", 0.0) + sim_dt
        while gs.armor_drain_timer >= 0.5 and gs.overshield > 0:
            gs.overshield = max(0, gs.overshield - 50)
            gs.armor_drain_timer -= 0.5
    else:
        gs.armor_drain_timer = 0.0
    if gs.shield_active:
        gs.shield_duration_remaining -= sim_dt
    gs.shield_cooldown_remaining -= sim_dt
    gs.shield_recharge_timer += sim_dt
    gs.ally_drop_timer += sim_dt
    gs.ally_command_timer = max(0.0, getattr(gs, "ally_command_timer", 0.0) - sim_dt)
    gs.teleporter_cooldown = max(0.0, getattr(gs, "teleporter_cooldown", 0.0) - sim_dt)
    gs.fire_rate_buff_t += sim_dt
    gs.pos_timer += sim_dt
    gs.ui.continue_blink_t += sim_dt


def _sim_damage_and_weapon_message_cleanup(gs: GameState, sim_dt: float, app_ctx: AppContext) -> None:
    for dmg_num in gs.damage_numbers[:]:
        dmg_num["timer"] -= sim_dt
        if dmg_num["timer"] <= 0:
            gs.damage_numbers.remove(dmg_num)
    for msg in gs.weapon_pickup_messages[:]:
        msg["timer"] -= sim_dt
        if msg["timer"] <= 0:
            gs.weapon_pickup_messages.remove(msg)


def _sim_shield_and_jump_state(gs: GameState, sim_dt: float, app_ctx: AppContext) -> None:
    if gs.shield_active and gs.shield_duration_remaining <= 0.0:
        gs.shield_active = False
        gs.shield_cooldown_remaining = gs.shield_cooldown
        gs.shield_recharge_timer = 0.0
    if gs.is_jumping:
        gs.jump_timer += sim_dt
        if gs.jump_timer >= jump_duration:
            gs.is_jumping = False
            gs.jump_velocity = pygame.Vector2(0, 0)


def _sim_hazards(gs: GameState, sim_dt: float, app_ctx: AppContext) -> None:
    if gs.level:
        update_hazard_obstacles(sim_dt, gs.level.hazard_obstacles, gs.current_level, app_ctx.width, app_ctx.height)


def _sim_entity_updates(gs: GameState, sim_dt: float, app_ctx: AppContext) -> None:
    for entity in gs.enemies:
        if hasattr(entity, "update"):
            entity.update(sim_dt, gs)
    for entity in gs.friendly_ai:
        if hasattr(entity, "update"):
            entity.update(sim_dt, gs)


def _sim_defeat_messages_cleanup(gs: GameState, sim_dt: float, app_ctx: AppContext) -> None:
    for msg in gs.enemy_defeat_messages[:]:
        msg["timer"] -= sim_dt
        if msg["timer"] <= 0:
            gs.enemy_defeat_messages.remove(msg)


def _sim_pickup_effects(gs: GameState, sim_dt: float, app_ctx: AppContext) -> None:
    update_pickup_effects(sim_dt, gs)


def _sim_registry_systems(gs: GameState, sim_dt: float, app_ctx: AppContext) -> None:
    for system_update in REGISTRY_SYSTEMS:
        system_update(gs, sim_dt)


def _sim_juice_timers(gs: GameState, sim_dt: float, app_ctx: AppContext) -> None:
    gs.screen_damage_flash_timer = max(0.0, gs.screen_damage_flash_timer - sim_dt)
    gs.damage_wobble_timer = max(0.0, getattr(gs, "damage_wobble_timer", 0.0) - sim_dt)
    gs.wave_banner_timer = max(0.0, gs.wave_banner_timer - sim_dt)
    for e in gs.enemies:
        if isinstance(e, dict) and "damage_flash_timer" in e:
            e["damage_flash_timer"] = max(0.0, e["damage_flash_timer"] - sim_dt)


def _sim_wave_beams_cleanup(gs: GameState, sim_dt: float, app_ctx: AppContext) -> None:
    """Clean up expired wave beams to prevent unbounded growth."""
    if not gs.wave_beams:
        return
    # Use filter-based removal for efficiency
    gs.wave_beams[:] = [
        beam for beam in gs.wave_beams
        if (beam.__setitem__("timer", beam.get("timer", 0.1) - sim_dt) or True)
        and beam.get("timer", 0) > 0
    ]


def _sim_limit_damage_numbers(gs: GameState, sim_dt: float, app_ctx: AppContext) -> None:
    """Limit damage numbers to prevent accumulation during intense combat."""
    MAX_DAMAGE_NUMBERS = 50  # Keep only the most recent
    if len(gs.damage_numbers) > MAX_DAMAGE_NUMBERS:
        # Sort by timer (newest first) and keep only MAX
        gs.damage_numbers.sort(key=lambda x: x.get("timer", 0), reverse=True)
        gs.damage_numbers[:] = gs.damage_numbers[:MAX_DAMAGE_NUMBERS]


def _sim_enforce_entity_limits(gs: GameState, sim_dt: float, app_ctx: AppContext) -> None:
    """Enforce limits on missiles, explosions, and laser beams to prevent late-game slowdown."""
    cfg = app_ctx.config if app_ctx else None
    
    # Missile limit (default 30)
    max_missiles = getattr(cfg, "max_missiles", 30) if cfg else 30
    if len(gs.missiles) > max_missiles:
        # Remove oldest missiles (first in list)
        gs.missiles[:] = gs.missiles[-max_missiles:]
    
    # Explosion limit (default 20)
    max_explosions = getattr(cfg, "max_explosions", 20) if cfg else 20
    if len(gs.grenade_explosions) > max_explosions:
        # Keep explosions with most time remaining
        gs.grenade_explosions.sort(key=lambda x: x.get("timer", 0), reverse=True)
        gs.grenade_explosions[:] = gs.grenade_explosions[:max_explosions]
    
    # Laser beam limit (default 10)
    max_lasers = getattr(cfg, "max_laser_beams", 10) if cfg else 10
    if len(gs.laser_beams) > max_lasers:
        gs.laser_beams[:] = gs.laser_beams[-max_lasers:]


def _sim_camera_update(gs: GameState, sim_dt: float, app_ctx: AppContext) -> None:
    """Update camera to follow the player. Should run after movement systems."""
    from systems.camera import get_camera
    from systems.perf_timing import perf_timer
    
    with perf_timer("camera_update"):
        camera = get_camera()
        if camera is None:
            return
        
        player = gs.player_rect
        if player is not None:
            camera.follow(player, sim_dt)
            
            # Reset stats for next frame
            camera.reset_stats()


SIMULATION_SYSTEMS = [
    _sim_player_and_ability_timers,
    _sim_damage_and_weapon_message_cleanup,
    _sim_shield_and_jump_state,
    _sim_hazards,
    _sim_entity_updates,
    _sim_defeat_messages_cleanup,
    _sim_pickup_effects,
    _sim_registry_systems,
    _sim_juice_timers,
    _sim_wave_beams_cleanup,
    _sim_limit_damage_numbers,
    _sim_enforce_entity_limits,
    _sim_camera_update,  # Update camera after all movement
]
