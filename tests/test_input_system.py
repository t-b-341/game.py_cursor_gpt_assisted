"""Tests for systems/input_system.py - gameplay input handling."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pygame
import pytest

from systems.input_system import (
    _scale_mouse_pos,
    _log_weapon_switch,
    handle_gameplay_input,
)
from constants import STATE_PLAYING, STATE_ENDURANCE, STATE_PAUSED


class KeyPressedMock:
    """Mock for pygame.key.get_pressed() that handles large key constants."""
    def __init__(self, pressed_keys=None):
        self._pressed = set(pressed_keys or [])
    
    def __getitem__(self, key):
        return key in self._pressed


@dataclass
class FakeGameState:
    """Minimal fake GameState for testing input handling."""
    current_screen: str = STATE_PLAYING
    player_rect: pygame.Rect = field(default_factory=lambda: pygame.Rect(100, 100, 32, 32))
    
    # Movement
    move_input_x: int = 0
    move_input_y: int = 0
    last_horizontal_key: int = 0
    last_vertical_key: int = 0
    last_move_velocity: pygame.Vector2 = field(default_factory=lambda: pygame.Vector2(0, 0))
    
    # Speed/boost
    speed_mult: float = 1.0
    boost_meter: float = 100.0
    previous_boost_state: bool = False
    previous_slow_state: bool = False
    
    # Weapons
    current_weapon_mode: str = "triple"
    previous_weapon_mode: str = "triple"
    unlocked_weapons: set = field(default_factory=lambda: {"triple", "laser", "giant"})
    laser_beams: list = field(default_factory=list)
    fire_pressed: bool = False
    
    # Abilities/timers
    run_time: float = 0.0
    shield_active: bool = False
    shield_recharge_timer: float = 10.0
    shield_recharge_cooldown: float = 5.0
    shield_duration_remaining: float = 0.0
    shield_cooldown: float = 0.0
    shield_cooldown_remaining: float = 0.0
    overshield: int = 0
    overshield_recharge_timer: float = 10.0
    armor_drain_timer: float = 0.0
    grenade_time_since_used: float = 10.0
    grenade_explosions: list = field(default_factory=list)
    missile_time_since_used: float = 10.0
    missiles: list = field(default_factory=list)
    enemies: list = field(default_factory=list)
    ally_drop_timer: float = 30.0
    friendly_ai: list = field(default_factory=list)
    dropped_ally: dict = None
    player_stat_multipliers: dict = field(default_factory=dict)
    player_max_hp: int = 100
    
    # Jump/dash
    is_jumping: bool = False
    jump_timer: float = 0.0
    jump_cooldown_timer: float = 2.0
    jump_velocity: pygame.Vector2 = field(default_factory=lambda: pygame.Vector2(0, 0))
    
    # Ally commands
    ally_command_target: tuple = None
    ally_command_timer: float = 0.0


class TestScaleMousePos:
    """Tests for _scale_mouse_pos helper function."""
    
    def test_scale_no_camera_no_scale(self):
        """Returns same position when world_scale is 1.0 and no camera."""
        result = _scale_mouse_pos((100, 200), 1.0, None)
        assert result == (100.0, 200.0)
    
    def test_scale_with_world_scale(self):
        """Scales position by world_scale when > 1.0."""
        result = _scale_mouse_pos((100, 200), 2.0, None)
        assert result == (200.0, 400.0)
    
    def test_scale_with_camera(self):
        """Uses camera.screen_to_world when camera provided."""
        mock_camera = MagicMock()
        mock_camera.screen_to_world.return_value = (150.0, 250.0)
        
        result = _scale_mouse_pos((100, 200), 1.0, mock_camera)
        
        mock_camera.screen_to_world.assert_called_once_with(100, 200)
        assert result == (150.0, 250.0)


class TestLogWeaponSwitch:
    """Tests for _log_weapon_switch helper function."""
    
    def test_logs_when_telemetry_enabled(self):
        """Logs weapon switch when telemetry is enabled."""
        mock_telemetry = MagicMock()
        game_state = FakeGameState(run_time=5.0)
        ctx = {"telemetry_enabled": True, "telemetry": mock_telemetry}
        
        _log_weapon_switch(game_state, ctx, "laser")
        
        mock_telemetry.log_weapon_switch.assert_called_once()
        call_args = mock_telemetry.log_weapon_switch.call_args[0][0]
        assert call_args.weapon_mode == "laser"
        assert call_args.t == 5.0
    
    def test_no_log_when_telemetry_disabled(self):
        """Does not log when telemetry is disabled."""
        mock_telemetry = MagicMock()
        game_state = FakeGameState()
        ctx = {"telemetry_enabled": False, "telemetry": mock_telemetry}
        
        _log_weapon_switch(game_state, ctx, "laser")
        
        mock_telemetry.log_weapon_switch.assert_not_called()
    
    def test_no_log_when_no_telemetry_client(self):
        """Does not crash when telemetry client is None."""
        game_state = FakeGameState()
        ctx = {"telemetry_enabled": True, "telemetry": None}
        
        # Should not raise
        _log_weapon_switch(game_state, ctx, "laser")


class TestHandleGameplayInput:
    """Tests for handle_gameplay_input function."""
    
    @pytest.fixture
    def game_state(self):
        return FakeGameState()
    
    @pytest.fixture
    def ctx(self):
        return {
            "controls": {},
            "aiming_mode": "mouse",
            "width": 800,
            "height": 600,
            "world_scale": 1.0,
            "dt": 0.016,
            "boost_meter_max": 100.0,
            "boost_drain_per_s": 45.0,
            "boost_regen_per_s": 25.0,
            "boost_speed_mult": 1.7,
            "slow_speed_mult": 0.45,
        }
    
    def test_ignores_input_when_not_playing(self, game_state, ctx):
        """Input is ignored when not in PLAYING or ENDURANCE state."""
        game_state.current_screen = STATE_PAUSED
        game_state.move_input_x = 99  # Set to non-default value
        
        with patch("pygame.key.get_pressed", return_value=KeyPressedMock()):
            with patch("pygame.mouse.get_pressed", return_value=(False, False, False)):
                with patch("systems.camera.get_camera", return_value=None):
                    handle_gameplay_input([], game_state, ctx)
        
        # Should not have been modified
        assert game_state.move_input_x == 99
    
    def test_processes_input_when_playing(self, game_state, ctx):
        """Input is processed when in STATE_PLAYING."""
        game_state.current_screen = STATE_PLAYING
        
        with patch("pygame.key.get_pressed", return_value=KeyPressedMock()):
            with patch("pygame.mouse.get_pressed", return_value=(False, False, False)):
                with patch("systems.camera.get_camera", return_value=None):
                    handle_gameplay_input([], game_state, ctx)
        
        # Should have reset move inputs
        assert game_state.move_input_x == 0
        assert game_state.move_input_y == 0
    
    def test_processes_input_when_endurance(self, game_state, ctx):
        """Input is processed when in STATE_ENDURANCE."""
        game_state.current_screen = STATE_ENDURANCE
        
        with patch("pygame.key.get_pressed", return_value=KeyPressedMock()):
            with patch("pygame.mouse.get_pressed", return_value=(False, False, False)):
                with patch("systems.camera.get_camera", return_value=None):
                    handle_gameplay_input([], game_state, ctx)
        
        # Should have processed (not ignored)
        assert game_state.move_input_x == 0
    
    def test_weapon_switch_to_laser(self, game_state, ctx):
        """Pressing 2 switches to laser weapon."""
        game_state.current_weapon_mode = "triple"
        
        # Create a KEYDOWN event for K_2
        event = MagicMock()
        event.type = pygame.KEYDOWN
        event.key = pygame.K_2
        
        with patch("pygame.key.get_pressed", return_value=KeyPressedMock()):
            with patch("pygame.mouse.get_pressed", return_value=(False, False, False)):
                with patch("systems.camera.get_camera", return_value=None):
                    handle_gameplay_input([event], game_state, ctx)
        
        assert game_state.current_weapon_mode == "laser"
        assert game_state.previous_weapon_mode == "triple"
    
    def test_weapon_switch_clears_laser_beams(self, game_state, ctx):
        """Switching away from laser clears laser beams."""
        game_state.current_weapon_mode = "laser"
        game_state.laser_beams = [{"beam": 1}, {"beam": 2}]
        
        # Switch to triple
        event = MagicMock()
        event.type = pygame.KEYDOWN
        event.key = pygame.K_1
        
        with patch("pygame.key.get_pressed", return_value=KeyPressedMock()):
            with patch("pygame.mouse.get_pressed", return_value=(False, False, False)):
                with patch("systems.camera.get_camera", return_value=None):
                    handle_gameplay_input([event], game_state, ctx)
        
        assert game_state.current_weapon_mode == "triple"
        assert game_state.laser_beams == []
    
    def test_weapon_switch_requires_unlock(self, game_state, ctx):
        """Cannot switch to weapon that is not unlocked."""
        game_state.current_weapon_mode = "triple"
        game_state.unlocked_weapons = {"triple"}  # Only triple unlocked
        
        event = MagicMock()
        event.type = pygame.KEYDOWN
        event.key = pygame.K_2  # Try to switch to laser
        
        with patch("pygame.key.get_pressed", return_value=KeyPressedMock()):
            with patch("pygame.mouse.get_pressed", return_value=(False, False, False)):
                with patch("systems.camera.get_camera", return_value=None):
                    handle_gameplay_input([event], game_state, ctx)
        
        # Should remain on triple
        assert game_state.current_weapon_mode == "triple"
    
    def test_boost_drains_meter(self, game_state, ctx):
        """Holding boost key drains boost meter."""
        game_state.boost_meter = 100.0
        
        # Boost key is K_LSHIFT
        with patch("pygame.key.get_pressed", return_value=KeyPressedMock([pygame.K_LSHIFT])):
            with patch("pygame.mouse.get_pressed", return_value=(False, False, False)):
                with patch("systems.camera.get_camera", return_value=None):
                    handle_gameplay_input([], game_state, ctx)
        
        assert game_state.boost_meter < 100.0
        assert game_state.speed_mult == 1.7  # Boost speed multiplier
        assert game_state.previous_boost_state is True
    
    def test_boost_regenerates_when_not_held(self, game_state, ctx):
        """Boost meter regenerates when not boosting."""
        game_state.boost_meter = 50.0
        
        with patch("pygame.key.get_pressed", return_value=KeyPressedMock()):
            with patch("pygame.mouse.get_pressed", return_value=(False, False, False)):
                with patch("systems.camera.get_camera", return_value=None):
                    handle_gameplay_input([], game_state, ctx)
        
        assert game_state.boost_meter > 50.0
        assert game_state.speed_mult == 1.0
    
    def test_fire_pressed_on_mouse_click(self, game_state, ctx):
        """fire_pressed is True when left mouse button is held."""
        with patch("pygame.key.get_pressed", return_value=KeyPressedMock()):
            with patch("pygame.mouse.get_pressed", return_value=(True, False, False)):
                with patch("systems.camera.get_camera", return_value=None):
                    handle_gameplay_input([], game_state, ctx)
        
        assert game_state.fire_pressed is True
    
    def test_spawn_player_bullet_callback(self, game_state, ctx):
        """spawn_player_bullet callback is called when provided."""
        mock_spawn = MagicMock()
        ctx["spawn_player_bullet"] = mock_spawn
        
        with patch("pygame.key.get_pressed", return_value=KeyPressedMock()):
            with patch("pygame.mouse.get_pressed", return_value=(True, False, False)):
                with patch("systems.camera.get_camera", return_value=None):
                    handle_gameplay_input([], game_state, ctx)
        
        mock_spawn.assert_called_once()
    
    def test_dash_activates_jump(self, game_state, ctx):
        """Pressing dash key activates jump/dash."""
        game_state.is_jumping = False
        game_state.jump_cooldown_timer = 2.0  # Cooldown ready
        game_state.last_move_velocity = pygame.Vector2(1, 0)
        
        event = MagicMock()
        event.type = pygame.KEYDOWN
        event.key = pygame.K_SPACE  # Default dash key
        
        with patch("pygame.key.get_pressed", return_value=KeyPressedMock()):
            with patch("pygame.mouse.get_pressed", return_value=(False, False, False)):
                with patch("systems.camera.get_camera", return_value=None):
                    with patch("systems.audio_system.play_sfx"):
                        handle_gameplay_input([event], game_state, ctx)
        
        assert game_state.is_jumping is True
        assert game_state.jump_cooldown_timer == 0.0
    
    def test_dash_respects_cooldown(self, game_state, ctx):
        """Dash does not activate if cooldown not ready."""
        game_state.is_jumping = False
        game_state.jump_cooldown_timer = 0.0  # Cooldown not ready
        
        event = MagicMock()
        event.type = pygame.KEYDOWN
        event.key = pygame.K_SPACE
        
        with patch("pygame.key.get_pressed", return_value=KeyPressedMock()):
            with patch("pygame.mouse.get_pressed", return_value=(False, False, False)):
                with patch("systems.camera.get_camera", return_value=None):
                    handle_gameplay_input([event], game_state, ctx)
        
        assert game_state.is_jumping is False
