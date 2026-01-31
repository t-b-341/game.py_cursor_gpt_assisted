"""Tests for game_init.py"""
import pytest
from unittest.mock import patch, MagicMock
import pygame

from game_init import (
    build_loop_params,
    build_scene_stack,
    AppResult,
)


class TestBuildLoopParams:
    """Tests for build_loop_params function."""

    def test_default_values(self):
        """Should return sensible defaults for 144 FPS."""
        fps, fixed_dt, max_steps = build_loop_params()
        
        assert fps == 144
        assert fixed_dt == 1.0 / 60.0  # 60Hz physics
        assert max_steps == 8

    def test_custom_fps(self):
        """Should accept custom target FPS."""
        fps, _, _ = build_loop_params(target_fps=60)
        assert fps == 60

    def test_uncapped_fps(self):
        """target_fps=0 should return 0 (uncapped)."""
        fps, _, _ = build_loop_params(target_fps=0)
        assert fps == 0

    def test_fixed_dt_always_60hz(self):
        """Physics should always run at 60Hz regardless of display FPS."""
        _, fixed_dt_30, _ = build_loop_params(target_fps=30)
        _, fixed_dt_144, _ = build_loop_params(target_fps=144)
        _, fixed_dt_240, _ = build_loop_params(target_fps=240)
        
        expected = 1.0 / 60.0
        assert fixed_dt_30 == expected
        assert fixed_dt_144 == expected
        assert fixed_dt_240 == expected


class TestBuildSceneStack:
    """Tests for build_scene_stack function."""

    def test_returns_scene_stack(self):
        """Should return a SceneStack instance."""
        from scenes import SceneStack
        stack = build_scene_stack()
        assert isinstance(stack, SceneStack)

    def test_has_title_scene(self):
        """Should have TitleScene pushed."""
        from scenes import TitleScene
        stack = build_scene_stack()
        current = stack.current()
        assert isinstance(current, TitleScene)

    def test_stack_not_empty(self):
        """Stack should not be empty after build."""
        stack = build_scene_stack()
        assert stack.current() is not None


class TestAppResult:
    """Tests for AppResult container class."""

    def test_default_values(self):
        """AppResult should have None/0 defaults."""
        result = AppResult()
        
        assert result.ctx is None
        assert result.game_state is None
        assert result.scene_stack is None
        assert result.fps == 0
        assert result.fixed_dt == 0.0
        assert result.max_sim_steps == 0
        assert result.update_simulation is None
        assert result.simulation_accumulator == 0.0

    def test_can_set_values(self):
        """AppResult should allow setting values."""
        result = AppResult()
        result.fps = 144
        result.fixed_dt = 1.0 / 60.0
        result.simulation_accumulator = 0.5
        
        assert result.fps == 144
        assert result.fixed_dt == 1.0 / 60.0
        assert result.simulation_accumulator == 0.5


class TestBuildAppContext:
    """Tests for build_app_context function (with mocking)."""

    @pytest.fixture
    def mock_pygame(self):
        """Mock pygame for testing without display."""
        with patch('game_init.pygame') as mock:
            mock.Surface = MagicMock(return_value=MagicMock())
            mock.time.Clock = MagicMock()
            yield mock

    @pytest.fixture
    def mock_dependencies(self):
        """Mock heavy dependencies."""
        with patch('game_init.load_controls') as mock_controls, \
             patch('game_init.set_screen_dimensions') as mock_dims, \
             patch('game_init.sync_from_config') as mock_sync, \
             patch('game_init.get_font') as mock_font, \
             patch('systems.camera.create_camera') as mock_camera:
            
            mock_controls.return_value = {}
            mock_font.return_value = MagicMock()
            mock_camera.return_value = MagicMock()
            
            yield {
                'controls': mock_controls,
                'dimensions': mock_dims,
                'sync': mock_sync,
                'font': mock_font,
                'camera': mock_camera,
            }

    def test_build_app_context_structure(self, mock_pygame, mock_dependencies):
        """build_app_context should return AppContext with required fields."""
        from game_init import build_app_context
        
        # Create mock screen and clock
        mock_screen = MagicMock()
        mock_clock = MagicMock()
        
        ctx = build_app_context(
            screen=mock_screen,
            clock=mock_clock,
            display_width=1920,
            display_height=1080,
            using_c_physics=False
        )
        
        # Verify structure
        assert ctx.screen is mock_screen
        assert ctx.clock is mock_clock
        assert ctx.display_width == 1920
        assert ctx.display_height == 1080
        assert ctx.config is not None
        assert ctx.event_bus is not None

    def test_world_dimensions_scaled(self, mock_pygame, mock_dependencies):
        """World dimensions should be scaled by world_scale."""
        from game_init import build_app_context
        
        mock_screen = MagicMock()
        mock_clock = MagicMock()
        
        ctx = build_app_context(
            screen=mock_screen,
            clock=mock_clock,
            display_width=1920,
            display_height=1080,
            using_c_physics=False
        )
        
        # World should be larger than display (scaled)
        assert ctx.width >= ctx.display_width
        assert ctx.height >= ctx.display_height


class TestBuildInitialGameState:
    """Tests for build_initial_game_state function (with mocking)."""

    @pytest.fixture
    def mock_ctx(self):
        """Create a mock AppContext."""
        ctx = MagicMock()
        ctx.width = 1920
        ctx.height = 1080
        ctx.run_started_at = "2024-01-01T00:00:00Z"
        return ctx

    @pytest.fixture
    def mock_level_deps(self):
        """Mock level building dependencies."""
        with patch('game_init.build_level_geometry') as mock_build, \
             patch('game_init.filter_blocks_no_overlap') as mock_filter, \
             patch('game_init.place_teleporter_pads') as mock_pads, \
             patch('game_init.pygame.mouse.set_visible') as mock_mouse, \
             patch('level_utils.make_level_context') as mock_level_ctx:
            
            # Create mock level with required attributes
            mock_level = MagicMock()
            mock_level.destructible_blocks = []
            mock_level.moveable_blocks = []
            mock_level.giant_blocks = []
            mock_level.super_giant_blocks = []
            mock_level.trapezoid_blocks = []
            mock_level.triangle_blocks = []
            
            mock_build.return_value = mock_level
            mock_filter.return_value = []
            mock_pads.return_value = []
            mock_level_ctx.return_value = {}
            
            yield {
                'build': mock_build,
                'filter': mock_filter,
                'pads': mock_pads,
                'level': mock_level,
            }

    def test_build_initial_game_state_structure(self, mock_ctx, mock_level_deps):
        """build_initial_game_state should return GameState with required fields."""
        from game_init import build_initial_game_state
        
        state = build_initial_game_state(mock_ctx)
        
        # Verify structure
        assert state.player_rect is not None
        assert state.current_screen is not None
        assert state.run_started_at == mock_ctx.run_started_at
        assert state.level is not None
        assert state.run_id is None  # Set when game starts

    def test_player_rect_centered(self, mock_ctx, mock_level_deps):
        """Player should start centered on screen."""
        from game_init import build_initial_game_state
        
        state = build_initial_game_state(mock_ctx)
        
        # Player should be roughly centered
        player = state.player_rect
        center_x = mock_ctx.width // 2
        center_y = mock_ctx.height // 2
        
        # Allow some tolerance for player size offset
        assert abs(player.centerx - center_x) < 20
        assert abs(player.centery - center_y) < 20
