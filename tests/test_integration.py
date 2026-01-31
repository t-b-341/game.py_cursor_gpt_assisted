"""Integration tests for the main game loop and scene transitions.

These tests verify that the major components work together correctly.
"""
import pytest
import pygame

# Initialize pygame in dummy mode for tests
pygame.init()


class TestGameAppInitialization:
    """Test GameApp creation and initialization."""
    
    def test_game_app_imports(self):
        """GameApp can be imported without errors."""
        from game_app import GameApp
        assert GameApp is not None
    
    def test_game_init_functions(self):
        """game_init module functions are available."""
        from game_init import (
            build_app_context,
            build_initial_game_state,
            build_scene_stack,
            build_loop_params,
        )
        assert callable(build_app_context)
        assert callable(build_initial_game_state)
        assert callable(build_scene_stack)
        assert callable(build_loop_params)


class TestSceneTransitions:
    """Test scene stack transitions."""
    
    def test_scene_stack_push_pop(self):
        """Scene stack push and pop work correctly."""
        from scenes.base import SceneStack
        
        stack = SceneStack()
        
        # Use simple objects for testing
        scene1 = {"name": "scene1"}
        scene2 = {"name": "scene2"}
        
        stack.push(scene1)
        assert stack.current() == scene1
        
        stack.push(scene2)
        assert stack.current() == scene2
        assert len(stack) == 2
        
        stack.pop()
        assert stack.current() == scene1
        assert len(stack) == 1
    
    def test_scene_transition_kinds(self):
        """SceneTransition kinds are defined correctly."""
        from scenes.transitions import SceneTransition, KIND_NONE, KIND_PUSH, KIND_POP, KIND_REPLACE
        
        none_trans = SceneTransition.none()
        assert none_trans.kind == KIND_NONE
        
        pop_trans = SceneTransition.pop()
        assert pop_trans.kind == KIND_POP
        
        push_trans = SceneTransition.push("test")
        assert push_trans.kind == KIND_PUSH
        assert push_trans.scene_name == "test"
        
        replace_trans = SceneTransition.replace("test")
        assert replace_trans.kind == KIND_REPLACE
        assert replace_trans.scene_name == "test"


class TestGameplaySystems:
    """Test that gameplay systems can be run without errors."""
    
    def test_systems_registry_exists(self):
        """Systems registry is available."""
        from systems import registry
        assert registry is not None
    
    def test_spawn_system_update_no_crash_without_context(self):
        """spawn_system.update runs without crash when level_context is None."""
        from systems import spawn_system
        from state import GameState
        
        # Create minimal game state
        state = GameState()
        state.level_context = None
        
        # Should not crash even without level_context
        spawn_system.update(state, 0.016)
    
    def test_collision_package_imports(self):
        """Collision package can be imported."""
        from systems.collision import (
            handle_hazard_enemy_collisions,
            handle_laser_beam_collisions,
            handle_dead_enemies,
            handle_player_bullet_offscreen,
            handle_player_bullet_enemy_collisions,
            handle_grenade_explosion_damage,
            handle_missile_collisions,
        )
        
        assert callable(handle_hazard_enemy_collisions)
        assert callable(handle_laser_beam_collisions)
        assert callable(handle_dead_enemies)
        assert callable(handle_player_bullet_offscreen)
        assert callable(handle_player_bullet_enemy_collisions)
        assert callable(handle_grenade_explosion_damage)
        assert callable(handle_missile_collisions)


class TestRenderingPipeline:
    """Test that rendering components work together."""
    
    def test_world_rendering_imports(self):
        """World rendering package can be imported."""
        from rendering.world import (
            render_background,
            render_entities,
            render_projectiles,
            render_gameplay,
        )
        
        assert callable(render_background)
        assert callable(render_entities)
        assert callable(render_projectiles)
        assert callable(render_gameplay)
    
    def test_render_context_basic_creation(self):
        """RenderContext can be created with required args."""
        from rendering.context import RenderContext
        
        screen = pygame.Surface((800, 600))
        # Create with required attributes
        render_ctx = RenderContext(
            screen=screen,
            camera=None,
            font=None,
            big_font=None,
            small_font=None,
            width=800,
            height=600,
        )
        assert render_ctx is not None
        assert render_ctx.screen is screen
        assert render_ctx.width == 800
        assert render_ctx.height == 600


class TestRunManager:
    """Test run manager functionality."""
    
    def test_run_manager_imports(self):
        """Run manager can be imported."""
        from engine.run_manager import start_new_run
        assert callable(start_new_run)


class TestConfigLoading:
    """Test configuration loading."""
    
    def test_game_config_creation(self):
        """GameConfig can be created with defaults."""
        from config.game_config import GameConfig
        
        config = GameConfig()
        assert config is not None
        assert hasattr(config, 'difficulty')
        assert hasattr(config, 'player_class')
    
    def test_enemy_templates_exist(self):
        """Enemy templates are defined."""
        from config.enemy_data import ENEMY_TEMPLATES, FRIENDLY_AI_TEMPLATES
        
        assert len(ENEMY_TEMPLATES) > 0
        assert len(FRIENDLY_AI_TEMPLATES) > 0
    
    def test_all_allies_same_color(self):
        """All ally templates have the same purple color."""
        from config.enemy_data import FRIENDLY_AI_TEMPLATES, ALLY_COLOR
        
        for template in FRIENDLY_AI_TEMPLATES:
            assert template["color"] == ALLY_COLOR, f"Ally {template['type']} has wrong color"
    
    def test_all_allies_different_sizes(self):
        """All ally templates have unique sizes."""
        from config.enemy_data import FRIENDLY_AI_TEMPLATES
        
        sizes = set()
        for template in FRIENDLY_AI_TEMPLATES:
            size = (template["rect"].w, template["rect"].h)
            assert size not in sizes, f"Duplicate size {size} for {template['type']}"
            sizes.add(size)
