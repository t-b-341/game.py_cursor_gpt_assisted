"""Tests for systems/idle_enemy_animation.py"""
import pytest
import pygame

from systems.idle_enemy_animation import (
    IdleEnemy,
    ENEMY_COLORS,
    ENEMY_SHAPES,
    update_idle_enemies,
    render_idle_enemies,
    reset_idle_enemies,
    _create_idle_enemy,
    _idle_enemies,
    _idle_enemies_initialized,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset module state before each test."""
    reset_idle_enemies()
    yield
    reset_idle_enemies()


class TestIdleEnemy:
    """Tests for IdleEnemy dataclass."""

    def test_default_values(self):
        """IdleEnemy should have sensible defaults."""
        enemy = IdleEnemy(
            x=100, y=100, vx=10, vy=10,
            size=30, color=(255, 0, 0), shape="circle"
        )
        assert enemy.bob_offset == 0.0
        assert enemy.bob_speed == 2.0
        assert enemy.time_to_exit == 0.0
        assert enemy.exiting is False
        assert enemy.returning is False

    def test_custom_values(self):
        """IdleEnemy should accept custom values."""
        enemy = IdleEnemy(
            x=200, y=300, vx=5, vy=-5,
            size=40, color=(0, 255, 0), shape="square",
            bob_offset=1.5, bob_speed=3.0, time_to_exit=10.0,
            exiting=True, exit_target_x=500, exit_target_y=600
        )
        assert enemy.x == 200
        assert enemy.y == 300
        assert enemy.bob_offset == 1.5
        assert enemy.exiting is True


class TestCreateIdleEnemy:
    """Tests for _create_idle_enemy function."""

    def test_creates_enemy_with_valid_properties(self):
        """Created enemy should have valid properties."""
        enemy = _create_idle_enemy(800, 600, spawn_onscreen=True)
        
        assert isinstance(enemy, IdleEnemy)
        assert 20 <= enemy.size <= 45
        assert enemy.color in ENEMY_COLORS
        assert enemy.shape in ENEMY_SHAPES
        assert 5.0 <= enemy.time_to_exit <= 15.0

    def test_spawn_onscreen_within_bounds(self):
        """Onscreen spawn should be within screen bounds with margin."""
        width, height = 800, 600
        margin = 100
        
        for _ in range(20):  # Test multiple times due to randomness
            enemy = _create_idle_enemy(width, height, spawn_onscreen=True)
            assert margin <= enemy.x <= width - margin
            assert margin <= enemy.y <= height - margin

    def test_spawn_offscreen_outside_bounds(self):
        """Offscreen spawn should be outside screen bounds."""
        width, height = 800, 600
        
        for _ in range(20):  # Test multiple times due to randomness
            enemy = _create_idle_enemy(width, height, spawn_onscreen=False)
            # Should be off at least one edge
            is_offscreen = (
                enemy.x < 0 or enemy.x > width or
                enemy.y < 0 or enemy.y > height
            )
            assert is_offscreen

    def test_has_velocity(self):
        """Created enemy should have non-zero velocity."""
        enemy = _create_idle_enemy(800, 600)
        # Velocity magnitude should be between 20 and 60
        speed = (enemy.vx ** 2 + enemy.vy ** 2) ** 0.5
        assert 20 <= speed <= 60


class TestUpdateIdleEnemies:
    """Tests for update_idle_enemies function."""

    def test_initializes_on_first_call(self):
        """First call should initialize enemies."""
        reset_idle_enemies()
        update_idle_enemies(dt=0.016, width=800, height=600)
        
        # Module-level state should be initialized
        from systems.idle_enemy_animation import _idle_enemies, _idle_enemies_initialized
        assert _idle_enemies_initialized
        assert len(_idle_enemies) > 0

    def test_updates_bob_offset(self):
        """Update should increase bob_offset."""
        update_idle_enemies(dt=0.016, width=800, height=600)
        
        from systems.idle_enemy_animation import _idle_enemies
        initial_offsets = [e.bob_offset for e in _idle_enemies]
        
        update_idle_enemies(dt=0.1, width=800, height=600)
        
        for i, enemy in enumerate(_idle_enemies):
            assert enemy.bob_offset > initial_offsets[i]

    def test_reinitializes_on_size_change(self):
        """Should reinitialize when screen size changes."""
        update_idle_enemies(dt=0.016, width=800, height=600)
        
        from systems.idle_enemy_animation import _idle_enemies
        count1 = len(_idle_enemies)
        
        # Change screen size
        update_idle_enemies(dt=0.016, width=1920, height=1080)
        
        from systems.idle_enemy_animation import _idle_enemies
        # Should still have enemies (reinitialized)
        assert len(_idle_enemies) == count1


class TestRenderIdleEnemies:
    """Tests for render_idle_enemies function."""

    @pytest.fixture
    def screen(self):
        """Create a test screen surface."""
        pygame.display.init()
        return pygame.Surface((800, 600))

    def test_renders_without_error(self, screen):
        """Should render without raising exceptions."""
        update_idle_enemies(dt=0.016, width=800, height=600)
        
        # Should not raise
        render_idle_enemies(screen, run_time=0.0)

    def test_renders_all_shapes(self, screen):
        """Should handle all shape types."""
        update_idle_enemies(dt=0.016, width=800, height=600)
        
        from systems.idle_enemy_animation import _idle_enemies
        
        # Force different shapes for testing
        for i, enemy in enumerate(_idle_enemies[:3]):
            enemy.shape = ENEMY_SHAPES[i % len(ENEMY_SHAPES)]
        
        # Should not raise for any shape
        render_idle_enemies(screen, run_time=1.0)


class TestResetIdleEnemies:
    """Tests for reset_idle_enemies function."""

    def test_clears_initialized_flag(self):
        """Reset should clear the initialized flag."""
        update_idle_enemies(dt=0.016, width=800, height=600)
        
        from systems.idle_enemy_animation import _idle_enemies_initialized as init_before
        assert init_before
        
        reset_idle_enemies()
        
        from systems.idle_enemy_animation import _idle_enemies_initialized as init_after
        assert not init_after


class TestEnemyBehavior:
    """Integration tests for enemy behavior."""

    def test_enemies_move_over_time(self):
        """Enemies should move when updated."""
        update_idle_enemies(dt=0.016, width=800, height=600)
        
        from systems.idle_enemy_animation import _idle_enemies
        initial_positions = [(e.x, e.y) for e in _idle_enemies]
        
        # Update several times
        for _ in range(10):
            update_idle_enemies(dt=0.1, width=800, height=600)
        
        # At least some enemies should have moved
        moved = False
        for i, enemy in enumerate(_idle_enemies):
            if (enemy.x, enemy.y) != initial_positions[i]:
                moved = True
                break
        
        assert moved, "At least one enemy should have moved"

    def test_enemies_bounce_at_edges(self):
        """Enemies should bounce when hitting screen edges."""
        update_idle_enemies(dt=0.016, width=800, height=600)
        
        from systems.idle_enemy_animation import _idle_enemies
        
        # Force an enemy to the edge with velocity pointing outward
        enemy = _idle_enemies[0]
        enemy.x = 45  # Near left edge
        enemy.vx = -50  # Moving left
        enemy.exiting = False
        enemy.returning = False
        
        update_idle_enemies(dt=0.1, width=800, height=600)
        
        # Velocity should have reversed (bounced)
        assert enemy.vx > 0 or enemy.x >= 50
