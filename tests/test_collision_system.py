"""Focused pytest tests for collision logic: player bullets vs enemies, enemy projectiles vs player, pickups.

Uses minimal GameState and level_context. No Pygame display; conftest sets SDL_VIDEODRIVER=dummy.
"""
from __future__ import annotations

import pygame
import pytest

from constants import STATE_GAME_OVER
from level_state import LevelState
from state import GameState
from systems.collision_system import update as collision_update
from systems import collision_pickups
from systems import collision as collision_projectiles


def _make_kill_enemy():
    """Return (callable, list of killed enemies). Callable removes enemy from state.enemies and appends to list."""
    killed = []

    def kill(enemy, state):
        if enemy in state.enemies:
            state.enemies.remove(enemy)
        killed.append(enemy)

    return kill, killed


def _ctx_bullets_and_enemies(width=800, height=600):
    """Minimal ctx for player-bullet vs enemy and dead-enemy paths."""
    kill, killed = _make_kill_enemy()
    return {
        "kill_enemy": kill,
        "killed_list": killed,
        "rect_offscreen": lambda r: r.right < 0 or r.left > width or r.bottom < 0 or r.top > height,
        "config": None,
    }


@pytest.fixture
def state_with_player():
    """GameState with player_rect set, no level_context (for no-op tests)."""
    s = GameState()
    s.player_rect = pygame.Rect(100, 100, 40, 40)
    s.player_hp = 1000
    s.player_max_hp = 1000
    s.player_bullet_damage = 50
    return s


def _empty_level():
    """LevelState with no geometry, for collision tests that only need block lists to exist."""
    return LevelState(
        static_blocks=[],
        trapezoid_blocks=[],
        triangle_blocks=[],
        destructible_blocks=[],
        moveable_blocks=[],
        giant_blocks=[],
        super_giant_blocks=[],
        hazard_obstacles=[],
    )


@pytest.fixture
def state_for_collisions(state_with_player):
    """GameState with player and a level_context suitable for bullet/enemy/pickup tests."""
    s = state_with_player
    ctx = _ctx_bullets_and_enemies()
    s.level_context = ctx
    s.level = _empty_level()
    return s


class TestCollisionEntrypointNoOp:
    """update() does nothing when level_context or player_rect is missing."""

    def test_no_op_when_level_context_is_none(self, state_with_player):
        state_with_player.level_context = None
        state_with_player.enemies.append({
            "rect": pygame.Rect(200, 200, 30, 30),
            "hp": 100,
            "type": "basic",
        })
        before = len(state_with_player.enemies)

        collision_update(state_with_player, 0.016)

        assert len(state_with_player.enemies) == before

    def test_no_op_when_player_rect_is_none(self, state_for_collisions):
        state_for_collisions.player_rect = None
        state_for_collisions.enemies.append({
            "rect": pygame.Rect(200, 200, 30, 30),
            "hp": 100,
            "type": "basic",
        })
        state_for_collisions.player_bullets.append({
            "rect": pygame.Rect(200, 200, 8, 8),
            "damage": 50,
        })
        before_enemies = len(state_for_collisions.enemies)
        before_bullets = len(state_for_collisions.player_bullets)

        collision_update(state_for_collisions, 0.016)

        assert len(state_for_collisions.enemies) == before_enemies
        assert len(state_for_collisions.player_bullets) == before_bullets


class TestPlayerBulletVsEnemy:
    """Player bullets that hit an enemy deal damage and are removed (no penetration)."""

    def test_bullet_hits_enemy_enemy_dies_bullet_removed(self, state_for_collisions):
        w, h = 800, 600
        state = state_for_collisions
        kill, killed = _make_kill_enemy()
        state.level_context["kill_enemy"] = kill
        state.level_context["killed_list"] = killed
        enemy = {"rect": pygame.Rect(150, 100, 30, 30), "hp": 40, "type": "basic"}
        state.enemies.append(enemy)
        bullet_rect = pygame.Rect(145, 108, 8, 8)
        state.player_bullets.append({"rect": bullet_rect, "damage": 50})

        collision_update(state, 0.016)

        assert enemy not in state.enemies
        assert len([b for b in state.player_bullets if b["rect"] == bullet_rect]) == 0
        assert enemy in killed or enemy["hp"] <= 0

    def test_bullet_offscreen_removed(self, state_for_collisions):
        state = state_for_collisions
        offscreen_rect = pygame.Rect(-20, -20, 8, 8)
        state.player_bullets.append({"rect": offscreen_rect, "damage": 50})

        collision_update(state, 0.016)

        assert len(state.player_bullets) == 0


class TestDeadEnemiesRemoved:
    """Enemies with hp <= 0 are removed by dead-enemy handling when kill_enemy is in ctx."""

    def test_dead_enemy_removed_by_collision_update(self, state_for_collisions):
        kill, killed = _make_kill_enemy()
        state_for_collisions.level_context["kill_enemy"] = kill
        enemy = {"rect": pygame.Rect(200, 200, 30, 30), "hp": 0, "type": "basic"}
        state_for_collisions.enemies.append(enemy)

        collision_update(state_for_collisions, 0.016)

        assert enemy not in state_for_collisions.enemies
        assert enemy in killed


class TestEnemyProjectileVsPlayer:
    """Enemy projectiles that hit the player deal damage and are removed."""

    def test_enemy_projectile_hits_player_damage_and_removed(self, state_for_collisions):
        state = state_for_collisions
        state.level_context["reset_after_death"] = None
        state.level_context["log_player_death"] = None
        hp_before = state.player_hp
        proj = {"rect": pygame.Rect(100, 100, 12, 12), "damage": 25}
        state.enemy_projectiles.append(proj)

        collision_update(state, 0.016)

        assert state.player_hp == hp_before - 25
        assert proj not in state.enemy_projectiles

    def test_enemy_projectile_blocked_by_shield(self, state_for_collisions):
        state = state_for_collisions
        state.shield_active = True
        hp_before = state.player_hp
        proj = {"rect": pygame.Rect(100, 100, 12, 12), "damage": 25}
        state.enemy_projectiles.append(proj)

        collision_update(state, 0.016)

        assert state.player_hp == hp_before
        assert proj not in state.enemy_projectiles

    def test_enemy_laser_beam_blocked_by_shield(self, state_for_collisions):
        """Shield should block enemy laser beams (no damage while shield active)."""
        state = state_for_collisions
        state.shield_active = True
        hp_before = state.player_hp
        # Beam passes through player position (100, 100 is player center)
        beam = {
            "start": (50, 100),
            "end": (150, 100),
            "timer": 1.0,
            "deploy_timer": 0.0,  # Already deployed
            "damage": 80 * 60,  # High damage per second
        }
        state.enemy_laser_beams.append(beam)

        collision_update(state, 0.016)

        assert state.player_hp == hp_before, "Shield should block enemy laser beam damage"

    def test_dash_grants_invincibility(self, state_for_collisions):
        """Player should take no damage from projectiles while dashing (is_jumping=True)."""
        state = state_for_collisions
        state.is_jumping = True  # Dashing
        hp_before = state.player_hp
        proj = {"rect": pygame.Rect(100, 100, 12, 12), "damage": 50}
        state.enemy_projectiles.append(proj)

        collision_update(state, 0.016)

        assert state.player_hp == hp_before, "Dash should grant invincibility"
        # Projectile is still removed on collision (it hit, but no damage dealt)
        assert proj not in state.enemy_projectiles


class TestPickupCollection:
    """Player overlapping a pickup collects it and apply_effect is called."""

    def test_pickup_collected_and_removed(self, state_for_collisions):
        state = state_for_collisions
        applied = []

        def apply_effect(pickup_type, st):
            applied.append((pickup_type, st))

        state.level_context["apply_pickup_effect"] = apply_effect
        state.level_context["create_pickup_collection_effect"] = None
        pickup = {"rect": pygame.Rect(100, 100, 24, 24), "type": "health", "color": (0, 255, 0)}
        state.pickups.append(pickup)

        collision_update(state, 0.016)

        assert pickup not in state.pickups
        assert applied == [("health", state)]


class TestDeathWhenHealthReachesZero:
    """When player HP reaches zero, death mechanic runs: respawn (if lives + reset) or game over."""

    def test_health_reaches_zero_with_lives_triggers_respawn(self, state_for_collisions):
        state = state_for_collisions
        state.player_hp = 25
        state.player_max_hp = 1000
        state.lives = 1
        reset_calls = []

        def mock_reset(s):
            reset_calls.append(s)
            s.player_hp = s.player_max_hp

        state.level_context["reset_after_death"] = mock_reset
        state.level_context["log_player_death"] = None
        proj = {"rect": pygame.Rect(100, 100, 12, 12), "damage": 25}
        state.enemy_projectiles.append(proj)

        collision_update(state, 0.016)

        assert len(reset_calls) == 1
        assert reset_calls[0] is state
        assert state.player_hp == state.player_max_hp
        assert state.lives == 0

    def test_health_reaches_zero_no_lives_transitions_to_game_over(self, state_for_collisions):
        state = state_for_collisions
        state.player_hp = 25
        state.player_max_hp = 1000
        state.lives = 0
        state.score = 5000
        state.wave_number = 3  # Track which wave player died on
        state.level_context["reset_after_death"] = None
        state.level_context["log_player_death"] = None
        proj = {"rect": pygame.Rect(100, 100, 12, 12), "damage": 25}
        state.enemy_projectiles.append(proj)

        collision_update(state, 0.016)

        assert state.player_hp <= 0
        assert state.current_screen == STATE_GAME_OVER
        assert state.final_score_for_high_score == 5000
        assert state.game_over_wave == 3  # Should store the wave where player died


class TestModuleLevelPlayerBulletOffscreen:
    """Direct call to handle_player_bullet_offscreen for targeted behavior."""

    def test_offscreen_bullet_removed(self):
        state = GameState()
        state.player_rect = pygame.Rect(100, 100, 40, 40)
        state.player_bullets = [{"rect": pygame.Rect(-50, 300, 8, 8), "damage": 10}]
        ctx = {"rect_offscreen": lambda r: r.right < 0 or r.left > 800 or r.bottom < 0 or r.top > 600}

        collision_projectiles.handle_player_bullet_offscreen(state, ctx)

        assert len(state.player_bullets) == 0
