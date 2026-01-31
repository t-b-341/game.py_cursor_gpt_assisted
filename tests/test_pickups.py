"""Tests for pickups.py - pickup effect handlers."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pygame
import pytest

from pickups import (
    apply_pickup_effect,
    PICKUP_HANDLERS,
    _apply_health_pickup,
    _apply_boost_pickup,
    _apply_overshield_pickup,
    _apply_max_health_pickup,
    _apply_speed_pickup,
    _apply_firerate_permanent_pickup,
    _apply_bullet_damage_pickup,
    _apply_giant_bullets_pickup,
    _apply_triple_shot_pickup,
    _apply_laser_pickup,
    _apply_spawn_boost_pickup,
    _apply_bonus_pickup,
)
from constants import boost_meter_max, jump_cooldown, PICKUP_BONUS_POINTS


@dataclass
class FakeGameState:
    """Minimal fake GameState for testing pickup effects."""
    player_hp: int = 100
    player_max_hp: int = 100
    boost_meter: float = 50.0
    overshield: int = 0
    jump_cooldown_timer: float = 0.0
    fire_rate_buff_t: float = 0.0
    player_health_regen_rate: float = 0.0
    random_damage_multiplier: float = 1.0
    score: int = 0
    run_time: float = 0.0
    player_rect: pygame.Rect = field(default_factory=lambda: pygame.Rect(100, 100, 32, 32))
    
    # Weapons
    current_weapon_mode: str = "basic"
    previous_weapon_mode: str = "basic"
    unlocked_weapons: set = field(default_factory=lambda: {"basic"})
    laser_beams: list = field(default_factory=list)
    weapon_pickup_messages: list = field(default_factory=list)
    
    # Stat multipliers
    player_stat_multipliers: dict = field(default_factory=lambda: {
        "speed": 1.0,
        "firerate": 1.0,
        "bullet_size": 1.0,
        "bullet_speed": 1.0,
        "bullet_damage": 1.0,
        "bullet_knockback": 1.0,
        "bullet_penetration": 0,
        "bullet_explosion_radius": 0.0,
        "ally_drop_cooldown": 1.0,
    })


@dataclass
class FakeConfig:
    enable_telemetry: bool = False


@dataclass
class FakeAppContext:
    config: FakeConfig = field(default_factory=FakeConfig)
    telemetry_client: object = None


class TestPickupHandlerRegistry:
    """Tests for the pickup handler registry."""
    
    def test_all_handlers_exist(self):
        """All expected pickup types have handlers."""
        expected_types = [
            "bonus", "boost", "sprint", "armor", "overshield",
            "dash_recharge", "firerate", "health", "max_health",
            "speed", "firerate_permanent", "bullet_size", "bullet_speed",
            "bullet_damage", "bullet_knockback", "bullet_penetration",
            "bullet_explosion", "health_regen", "random_damage",
            "spawn_boost", "giant_bullets", "giant", "triple_shot",
            "triple", "laser", "basic",
        ]
        
        for pickup_type in expected_types:
            assert pickup_type in PICKUP_HANDLERS, f"Missing handler for {pickup_type}"
    
    def test_handlers_are_callable(self):
        """All handlers are callable functions."""
        for name, handler in PICKUP_HANDLERS.items():
            assert callable(handler), f"Handler for {name} is not callable"


class TestHealthPickups:
    """Tests for health-related pickup effects."""
    
    def test_health_pickup_restores_hp(self):
        """Health pickup restores 250 HP."""
        state = FakeGameState(player_hp=50, player_max_hp=500)
        ctx = FakeAppContext()
        
        _apply_health_pickup(state, ctx, "health")
        
        assert state.player_hp == 300  # 50 + 250
    
    def test_health_pickup_caps_at_max(self):
        """Health pickup does not exceed max HP."""
        state = FakeGameState(player_hp=90, player_max_hp=100)
        ctx = FakeAppContext()
        
        _apply_health_pickup(state, ctx, "health")
        
        assert state.player_hp == 100  # Capped at max
    
    def test_max_health_pickup_increases_max(self):
        """Max health pickup increases both max HP and current HP."""
        state = FakeGameState(player_hp=100, player_max_hp=100)
        ctx = FakeAppContext()
        
        _apply_max_health_pickup(state, ctx, "max_health")
        
        assert state.player_max_hp == 115  # +15
        assert state.player_hp == 115  # Also healed


class TestBoostPickups:
    """Tests for boost/sprint pickup effects."""
    
    def test_boost_pickup_restores_meter(self):
        """Boost pickup restores 45 meter."""
        state = FakeGameState(boost_meter=10.0)
        ctx = FakeAppContext()
        
        _apply_boost_pickup(state, ctx, "boost")
        
        assert state.boost_meter == 55.0  # 10 + 45
    
    def test_boost_pickup_caps_at_max(self):
        """Boost pickup does not exceed max meter."""
        state = FakeGameState(boost_meter=80.0)
        ctx = FakeAppContext()
        
        _apply_boost_pickup(state, ctx, "boost")
        
        assert state.boost_meter == boost_meter_max  # Capped


class TestArmorPickups:
    """Tests for overshield/armor pickup effects."""
    
    def test_overshield_pickup_adds_armor(self):
        """Overshield pickup adds 25 armor."""
        state = FakeGameState(overshield=0, player_max_hp=100)
        ctx = FakeAppContext()
        
        _apply_overshield_pickup(state, ctx, "overshield")
        
        assert state.overshield == 25
    
    def test_overshield_pickup_stacks(self):
        """Overshield pickup stacks with existing armor."""
        state = FakeGameState(overshield=50, player_max_hp=100)
        ctx = FakeAppContext()
        
        _apply_overshield_pickup(state, ctx, "overshield")
        
        assert state.overshield == 75
    
    def test_overshield_pickup_caps_at_max_hp(self):
        """Overshield caps at player max HP."""
        state = FakeGameState(overshield=90, player_max_hp=100)
        ctx = FakeAppContext()
        
        _apply_overshield_pickup(state, ctx, "overshield")
        
        assert state.overshield == 100  # Capped at max_hp


class TestStatPickups:
    """Tests for stat-modifying pickup effects."""
    
    def test_speed_pickup_increases_multiplier(self):
        """Speed pickup increases speed multiplier."""
        state = FakeGameState()
        ctx = FakeAppContext()
        
        _apply_speed_pickup(state, ctx, "speed")
        
        assert state.player_stat_multipliers["speed"] == 1.15
    
    def test_firerate_permanent_increases_multiplier(self):
        """Firerate permanent pickup increases fire rate."""
        state = FakeGameState()
        ctx = FakeAppContext()
        
        _apply_firerate_permanent_pickup(state, ctx, "firerate_permanent")
        
        assert state.player_stat_multipliers["firerate"] == 1.12
    
    def test_firerate_permanent_caps_at_2x(self):
        """Firerate permanent caps at 2.0x to prevent performance issues."""
        state = FakeGameState()
        state.player_stat_multipliers["firerate"] = 1.95
        ctx = FakeAppContext()
        
        _apply_firerate_permanent_pickup(state, ctx, "firerate_permanent")
        
        assert state.player_stat_multipliers["firerate"] == 2.0  # Capped
    
    def test_bullet_damage_increases(self):
        """Bullet damage pickup increases damage multiplier."""
        state = FakeGameState()
        ctx = FakeAppContext()
        
        _apply_bullet_damage_pickup(state, ctx, "bullet_damage")
        
        assert state.player_stat_multipliers["bullet_damage"] == 1.20


class TestWeaponPickups:
    """Tests for weapon unlock/switch pickup effects."""
    
    def test_giant_bullets_unlocks_weapon(self):
        """Giant bullets pickup unlocks the weapon."""
        state = FakeGameState()
        ctx = FakeAppContext()
        
        _apply_giant_bullets_pickup(state, ctx, "giant")
        
        assert "giant" in state.unlocked_weapons
        assert state.current_weapon_mode == "giant"
    
    def test_triple_shot_unlocks_and_shows_message(self):
        """Triple shot pickup unlocks weapon and shows pickup message."""
        state = FakeGameState()
        ctx = FakeAppContext()
        
        _apply_triple_shot_pickup(state, ctx, "triple")
        
        assert "triple" in state.unlocked_weapons
        assert state.current_weapon_mode == "triple"
        assert len(state.weapon_pickup_messages) == 1
        assert "TRIPLE" in state.weapon_pickup_messages[0]["weapon_name"]
    
    def test_laser_unlocks_and_shows_message(self):
        """Laser pickup unlocks weapon and shows pickup message."""
        state = FakeGameState()
        ctx = FakeAppContext()
        
        _apply_laser_pickup(state, ctx, "laser")
        
        assert "laser" in state.unlocked_weapons
        assert state.current_weapon_mode == "laser"
        assert len(state.weapon_pickup_messages) == 1
    
    def test_weapon_switch_clears_laser_beams(self):
        """Switching away from laser clears laser beams."""
        state = FakeGameState()
        state.current_weapon_mode = "laser"
        state.laser_beams = [{"beam": 1}]
        ctx = FakeAppContext()
        
        _apply_giant_bullets_pickup(state, ctx, "giant")
        
        assert state.laser_beams == []
        assert state.previous_weapon_mode == "laser"


class TestSpawnBoostPickup:
    """Tests for spawn boost pickup effect."""
    
    def test_spawn_boost_reduces_cooldown(self):
        """Spawn boost reduces ally drop cooldown by 20%."""
        state = FakeGameState()
        ctx = FakeAppContext()
        
        _apply_spawn_boost_pickup(state, ctx, "spawn_boost")
        
        assert state.player_stat_multipliers["ally_drop_cooldown"] == 0.8
    
    def test_spawn_boost_stacks_multiplicatively(self):
        """Multiple spawn boosts stack multiplicatively."""
        state = FakeGameState()
        ctx = FakeAppContext()
        
        _apply_spawn_boost_pickup(state, ctx, "spawn_boost")
        _apply_spawn_boost_pickup(state, ctx, "spawn_boost")
        
        assert abs(state.player_stat_multipliers["ally_drop_cooldown"] - 0.64) < 0.01
    
    def test_spawn_boost_has_minimum(self):
        """Spawn boost has a minimum of 20% (0.2)."""
        state = FakeGameState()
        state.player_stat_multipliers["ally_drop_cooldown"] = 0.25
        ctx = FakeAppContext()
        
        _apply_spawn_boost_pickup(state, ctx, "spawn_boost")
        
        assert state.player_stat_multipliers["ally_drop_cooldown"] == 0.2  # Minimum


class TestBonusPickup:
    """Tests for bonus pickup effect."""
    
    def test_bonus_pickup_adds_points(self):
        """Bonus pickup adds points to score."""
        state = FakeGameState(score=1000)
        ctx = FakeAppContext()
        
        _apply_bonus_pickup(state, ctx, "bonus")
        
        assert state.score == 1000 + PICKUP_BONUS_POINTS


class TestApplyPickupEffect:
    """Tests for the main apply_pickup_effect function."""
    
    def test_applies_known_pickup(self):
        """apply_pickup_effect calls the correct handler."""
        state = FakeGameState(player_hp=50, player_max_hp=500)
        ctx = FakeAppContext()
        
        apply_pickup_effect("health", state, ctx)
        
        assert state.player_hp == 300  # Health pickup applied
    
    def test_handles_unknown_pickup(self, capsys):
        """apply_pickup_effect handles unknown pickup types gracefully."""
        state = FakeGameState()
        ctx = FakeAppContext()
        
        # Should not raise
        apply_pickup_effect("unknown_pickup_type", state, ctx)
        
        # Should print warning
        captured = capsys.readouterr()
        assert "unknown" in captured.out.lower() or "Unknown" in captured.out
    
    def test_aliases_work(self):
        """Pickup type aliases (e.g., 'giant' and 'giant_bullets') work."""
        state1 = FakeGameState()
        state2 = FakeGameState()
        ctx = FakeAppContext()
        
        apply_pickup_effect("giant", state1, ctx)
        apply_pickup_effect("giant_bullets", state2, ctx)
        
        # Both should unlock giant weapon
        assert "giant" in state1.unlocked_weapons
        assert "giant" in state2.unlocked_weapons
