"""Test that key modules can be imported without errors.

These tests catch import-time errors that unit tests miss because they
use mocks/stubs instead of the real initialization path.
"""
import pytest


class TestCriticalImports:
    """Verify that modules with complex imports can be loaded."""

    def test_level_utils_imports(self):
        """level_utils.make_level_context should import without errors."""
        from level_utils import make_level_context
        assert callable(make_level_context)

    def test_level_utils_lazy_imports(self):
        """Verify lazy imports inside make_level_context are valid.
        
        make_level_context has internal lazy imports that only fail at runtime.
        This test imports the same modules to catch errors early.
        """
        # These are the lazy imports from make_level_context
        from geometry_utils import clamp_rect_to_screen, vec_toward, line_rect_intersection
        from hazards import check_point_in_hazard
        from allies import find_nearest_enemy, update_friendly_ai, spawn_friendly_projectile
        from enemies import find_nearest_threat
        from systems.collision_movement import move_player_with_push, move_enemy_with_push
        from pickups import apply_pickup_effect
        from systems.audio_system import play_sfx
        from systems.enemy_death import reset_after_death, kill_enemy
        from systems.projectile_spawning import (
            spawn_enemy_projectile,
            spawn_enemy_projectile_predictive,
            spawn_ally_missile,
        )
        from systems.spawn_helpers import random_spawn_position, create_pickup_collection_effect
        from telemetry import PlayerDeathEvent
        assert callable(check_point_in_hazard)
        assert callable(spawn_friendly_projectile)

    def test_game_module_imports(self):
        """game.py should import without errors."""
        import game
        assert hasattr(game, 'main')
        assert hasattr(game, '_create_app')

    def test_game_app_imports(self):
        """game_app.py should import without errors."""
        from game_app import GameApp
        assert callable(GameApp)

    def test_rendering_context_imports(self):
        """rendering/context.py should import without errors."""
        from rendering.context import RenderContext, build_gameplay_ctx
        assert callable(build_gameplay_ctx)

    def test_scene_transitions_imports(self):
        """scenes/transitions.py should import without errors."""
        from scenes.transitions import (
            SceneTransition,
            apply_scene_transition,
            create_scene_for_state,
        )
        assert callable(apply_scene_transition)
        assert callable(create_scene_for_state)

    def test_spawn_helpers_imports(self):
        """systems/spawn_helpers.py should import without errors."""
        from systems.spawn_helpers import (
            random_spawn_position,
            spawn_pickup,
            spawn_weapon_in_center,
            spawn_weapon_drop,
            create_pickup_collection_effect,
        )
        assert callable(random_spawn_position)

    def test_enemy_death_imports(self):
        """systems/enemy_death.py should import without errors."""
        from systems.enemy_death import kill_enemy, reset_after_death
        assert callable(kill_enemy)
        assert callable(reset_after_death)

    def test_engine_render_loop_imports(self):
        """engine/render_loop.py should import without errors."""
        from engine.render_loop import (
            get_current_state,
            render_current_scene,
        )
        assert callable(get_current_state)
        assert callable(render_current_scene)

    def test_engine_package_imports(self):
        """engine package should export all expected functions."""
        from engine import (
            poll_events,
            handle_global_events,
            handle_scene_events,
            handle_debug_keys,
            get_current_state,
            render_current_scene,
            start_new_run,
            restart_current_wave,
        )
        assert callable(poll_events)
        assert callable(render_current_scene)

    def test_collision_projectiles_helpers(self):
        """collision_projectiles helpers should be importable and work correctly."""
        from systems.collision_projectiles import _create_damage_number, _bulk_remove
        
        # Test _create_damage_number
        dmg = _create_damage_number(100, 200, 50)
        assert dmg["x"] == 100
        assert dmg["y"] == 200
        assert dmg["damage"] == 50
        assert dmg["timer"] == 2.0
        assert dmg["color"] == (255, 255, 100)
        
        # Test with custom color
        dmg2 = _create_damage_number(0, 0, 100, (255, 0, 0))
        assert dmg2["color"] == (255, 0, 0)
        
        # Test _bulk_remove
        items = [{"id": 1}, {"id": 2}, {"id": 3}]
        ids_to_remove = {id(items[1])}
        _bulk_remove(items, ids_to_remove)
        assert len(items) == 2
        assert items[0]["id"] == 1
        assert items[1]["id"] == 3

    def test_options_scene_imports(self):
        """scenes/options.py should import without errors."""
        from scenes.options import OptionsScene
        assert callable(OptionsScene)
        # Verify dispatcher methods exist
        scene = OptionsScene()
        assert hasattr(scene, '_handle_section_0_difficulty')
        assert hasattr(scene, '_render_section_0')
        assert hasattr(scene, 'handle_input')
        assert hasattr(scene, 'render')
