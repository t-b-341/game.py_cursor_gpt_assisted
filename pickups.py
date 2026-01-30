"""
Pickup effect handlers.

This module contains handlers for all pickup types, organized in a registry pattern
for easy extension and testing.
"""
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from state import GameState
    from context import AppContext

from constants import (
    boost_meter_max,
    jump_cooldown,
    fire_rate_buff_duration,
    ally_drop_cooldown,
    PICKUP_BONUS_POINTS,
)
from config_weapons import WEAPON_NAMES, WEAPON_DISPLAY_COLORS
from telemetry import PlayerActionEvent


def _apply_boost_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply boost/sprint pickup effect."""
    game_state.boost_meter = min(boost_meter_max, game_state.boost_meter + 45.0)


def _apply_overshield_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply armor/overshield pickup effect. Caps at player_max_hp (same as TAB activation)."""
    overshield_cap = game_state.player_max_hp
    game_state.overshield = min(overshield_cap, game_state.overshield + 25)


def _apply_dash_recharge_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply dash recharge pickup effect."""
    game_state.jump_cooldown_timer = jump_cooldown  # Dash ready immediately


def _apply_firerate_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply temporary fire rate boost pickup effect."""
    game_state.fire_rate_buff_t = fire_rate_buff_duration


def _apply_health_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply health pickup effect - restores 250 HP (capped at max HP)."""
    game_state.player_hp = min(game_state.player_max_hp, game_state.player_hp + 250)


def _apply_max_health_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply max health pickup effect - increases max HP by 15 and heals by the same amount."""
    game_state.player_max_hp += 15
    game_state.player_hp += 15  # also heal by the same amount


def _apply_speed_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply speed pickup effect - increases speed multiplier by 0.15."""
    game_state.player_stat_multipliers["speed"] += 0.15


def _apply_firerate_permanent_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply permanent fire rate pickup effect - capped at 2.0x to prevent performance issues."""
    game_state.player_stat_multipliers["firerate"] = min(2.0, game_state.player_stat_multipliers["firerate"] + 0.12)


def _apply_bullet_size_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply bullet size pickup effect - increases bullet size multiplier by 0.20."""
    game_state.player_stat_multipliers["bullet_size"] += 0.20


def _apply_bullet_speed_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply bullet speed pickup effect - increases bullet speed multiplier by 0.15."""
    game_state.player_stat_multipliers["bullet_speed"] += 0.15


def _apply_bullet_damage_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply bullet damage pickup effect - increases bullet damage multiplier by 0.20."""
    game_state.player_stat_multipliers["bullet_damage"] += 0.20


def _apply_bullet_knockback_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply bullet knockback pickup effect - increases bullet knockback multiplier by 0.25."""
    game_state.player_stat_multipliers["bullet_knockback"] += 0.25


def _apply_bullet_penetration_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply bullet penetration pickup effect - increases penetration count by 1."""
    game_state.player_stat_multipliers["bullet_penetration"] += 1


def _apply_bullet_explosion_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply bullet explosion pickup effect - increases explosion radius by 25.0."""
    game_state.player_stat_multipliers["bullet_explosion_radius"] += 25.0


def _apply_health_regen_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply health regeneration pickup effect - increases regen rate by 5.0 HP per second."""
    game_state.player_health_regen_rate += 5.0


def _apply_random_damage_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply random damage pickup effect - randomizes damage multiplier between 0.5x and 2.0x."""
    game_state.random_damage_multiplier = random.uniform(0.5, 2.0)


def _apply_spawn_boost_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply spawn boost pickup effect - reduces ally drop cooldown by 20% (stacks multiplicatively)."""
    # Store cooldown multiplier in player_stat_multipliers (stacks with each pickup)
    mults = game_state.player_stat_multipliers
    current_mult = mults.get("ally_drop_cooldown", 1.0)
    mults["ally_drop_cooldown"] = max(0.2, current_mult * 0.8)  # Min 20% of original (5 pickups)


def _switch_weapon(game_state: "GameState", ctx: "AppContext", weapon_name: str) -> None:
    """Helper function to switch to a weapon and log telemetry."""
    game_state.previous_weapon_mode = game_state.current_weapon_mode
    # Clear beams when switching away from beam weapons
    if game_state.previous_weapon_mode == "laser":
        game_state.laser_beams.clear()
    game_state.current_weapon_mode = weapon_name
    
    # Log weapon switch from pickup
    if game_state.previous_weapon_mode != game_state.current_weapon_mode:
        if ctx.config.enable_telemetry and ctx.telemetry_client and game_state.player_rect:
            ctx.telemetry_client.log_player_action(PlayerActionEvent(
                t=game_state.run_time,
                action_type="weapon_switch",
                x=game_state.player_rect.centerx,
                y=game_state.player_rect.centery,
                duration=None,
                success=True
            ))


def _apply_giant_bullets_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply giant bullets weapon pickup effect."""
    game_state.unlocked_weapons.add("giant")
    _switch_weapon(game_state, ctx, "giant")


def _apply_triple_shot_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply triple shot weapon pickup effect."""
    game_state.unlocked_weapons.add("triple")
    _switch_weapon(game_state, ctx, "triple")
    # Weapon names and colors are now imported from config_weapons.py
    game_state.weapon_pickup_messages.append({
        "weapon_name": WEAPON_NAMES.get("triple", "TRIPLE SHOT"),
        "timer": 3.0,
        "color": WEAPON_DISPLAY_COLORS.get("triple", (255, 255, 255))
    })


def _apply_laser_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply laser weapon pickup effect."""
    game_state.unlocked_weapons.add("laser")
    _switch_weapon(game_state, ctx, "laser")
    # Weapon names and colors are now imported from config_weapons.py
    game_state.weapon_pickup_messages.append({
        "weapon_name": WEAPON_NAMES.get("laser", "LASER BEAM"),
        "timer": 3.0,
        "color": WEAPON_DISPLAY_COLORS.get("laser", (255, 255, 255))
    })


def _apply_basic_weapon_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply basic weapon pickup effect."""
    game_state.unlocked_weapons.add("basic")  # Should already be unlocked, but ensure it
    _switch_weapon(game_state, ctx, "basic")
    # Weapon names and colors are now imported from config_weapons.py
    game_state.weapon_pickup_messages.append({
        "weapon_name": WEAPON_NAMES.get("basic", "BASIC FIRE"),
        "timer": 3.0,
        "color": WEAPON_DISPLAY_COLORS.get("basic", (255, 255, 255))
    })


def _apply_bonus_pickup(game_state: "GameState", ctx: "AppContext", pickup_type: str) -> None:
    """Apply bonus pickup effect: add points only."""
    game_state.score += PICKUP_BONUS_POINTS


# Registry mapping pickup types to their handler functions
PICKUP_HANDLERS = {
    "bonus": _apply_bonus_pickup,
    "boost": _apply_boost_pickup,
    "sprint": _apply_boost_pickup,
    "armor": _apply_overshield_pickup,
    "overshield": _apply_overshield_pickup,
    "dash_recharge": _apply_dash_recharge_pickup,
    "firerate": _apply_firerate_pickup,
    "health": _apply_health_pickup,
    "max_health": _apply_max_health_pickup,
    "speed": _apply_speed_pickup,
    "firerate_permanent": _apply_firerate_permanent_pickup,
    "bullet_size": _apply_bullet_size_pickup,
    "bullet_speed": _apply_bullet_speed_pickup,
    "bullet_damage": _apply_bullet_damage_pickup,
    "bullet_knockback": _apply_bullet_knockback_pickup,
    "bullet_penetration": _apply_bullet_penetration_pickup,
    "bullet_explosion": _apply_bullet_explosion_pickup,
    "health_regen": _apply_health_regen_pickup,
    "random_damage": _apply_random_damage_pickup,
    "spawn_boost": _apply_spawn_boost_pickup,
    "giant_bullets": _apply_giant_bullets_pickup,
    "giant": _apply_giant_bullets_pickup,
    "triple_shot": _apply_triple_shot_pickup,
    "triple": _apply_triple_shot_pickup,
    "laser": _apply_laser_pickup,
    "basic": _apply_basic_weapon_pickup,
}


def apply_pickup_effect(pickup_type: str, state: "GameState", ctx: "AppContext") -> None:
    """
    Apply the effect of a collected pickup.
    
    Args:
        pickup_type: The type of pickup (e.g., "health", "boost", "giant", etc.)
        state: The current game state
        ctx: The application context
        
    Raises:
        None - unknown pickup types are logged but do not raise exceptions
    """
    handler = PICKUP_HANDLERS.get(pickup_type)
    if handler:
        handler(state, ctx, pickup_type)
    else:
        # Log warning for unknown pickup types but don't crash
        print(f"[Pickup] Warning: Unknown pickup type '{pickup_type}' - no effect applied")
