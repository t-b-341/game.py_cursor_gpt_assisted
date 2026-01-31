"""Basic tests for the spawn system: wave 1 spawns enemies, deterministic with seeded RNG.

Uses minimal GameState and level_context. No Pygame display; conftest sets SDL_VIDEODRIVER=dummy.
"""
from __future__ import annotations

import random
import pygame
import pytest

from config.enemy_defs import MAX_ENEMIES_PER_WAVE
from state import GameState
from systems.spawn_system import start_wave, update as spawn_update


def _make_deterministic_random_spawn():
    """Return a callable (size, state) -> Rect that places enemies at fixed positions."""
    positions = [(60 + (i % 15) * 70, 60 + (i // 15) * 70) for i in range(MAX_ENEMIES_PER_WAVE)]
    idx = [0]

    def random_spawn(size, state):
        i = idx[0] % len(positions)
        idx[0] += 1
        x, y = positions[i]
        return pygame.Rect(x, y, size[0], size[1])

    return random_spawn


@pytest.fixture
def spawn_ctx():
    """Minimal level_context for start_wave (wave 1): no telemetry, deterministic spawn positions."""
    w, h = 800, 600
    return {
        "width": w,
        "height": h,
        "difficulty": "NORMAL",
        "random_spawn_position": _make_deterministic_random_spawn(),
        "telemetry": None,
        "telemetry_enabled": False,
        "overshield_recharge_cooldown": 45.0,
        "ally_drop_cooldown": 30.0,
    }


@pytest.fixture
def game_state_wave1(spawn_ctx):
    """GameState at wave 1, no enemies, level_context set for spawning."""
    state = GameState()
    state.enemies = []
    state.wave_number = 1
    state.wave_in_level = 1
    state.current_level = 1
    state.max_level = 3
    state.lives = 3
    state.wave_start_reason = "test"
    state.run_time = 0.0
    state.level_context = spawn_ctx
    # Player rect so random_spawn can avoid it if needed (our deterministic positions don't use it)
    state.player_rect = pygame.Rect(400, 300, 40, 40)
    return state


class TestWave1SpawnsEnemies:
    """start_wave(1, state) spawns enemies according to early-wave rules."""

    def test_wave1_spawns_enemies(self, game_state_wave1, spawn_ctx):
        random.seed(42)
        state = game_state_wave1
        assert len(state.enemies) == 0

        start_wave(1, state)

        # Wave 1: regular wave + ambient (3–5). Total must be in [1, MAX_ENEMIES_PER_WAVE].
        assert 1 <= len(state.enemies) <= MAX_ENEMIES_PER_WAVE, (
            f"Wave 1 should spawn between 1 and {MAX_ENEMIES_PER_WAVE} enemies, got {len(state.enemies)}"
        )

    def test_spawned_enemies_have_required_fields(self, game_state_wave1):
        random.seed(123)
        state = game_state_wave1
        start_wave(1, state)

        for e in state.enemies:
            # Enemy entities are dict-like (e.get / e["key"])
            e_type = e.get("type")
            e_hp = e.get("hp", 0)
            e_rect = e.get("rect")
            assert e_type is not None, "enemy must have type"
            assert e_hp > 0, "enemy must have positive hp"
            assert e_rect is not None and isinstance(e_rect, pygame.Rect), "enemy must have rect"
            assert e_rect.w > 0 and e_rect.h > 0, "enemy rect must have positive size"

    def test_wave1_is_deterministic_with_same_seed(self, game_state_wave1, spawn_ctx):
        def run():
            st = GameState()
            st.enemies = []
            st.wave_number = 1
            st.wave_in_level = 1
            st.current_level = 1
            st.max_level = 3
            st.lives = 3
            st.wave_start_reason = "test"
            st.run_time = 0.0
            st.level_context = dict(spawn_ctx)
            st.level_context["random_spawn_position"] = _make_deterministic_random_spawn()
            st.player_rect = pygame.Rect(400, 300, 40, 40)
            random.seed(99)
            start_wave(1, st)
            return len(st.enemies), sorted(e.get("type", "") for e in st.enemies)

        random.seed(99)
        n1, types1 = run()
        n2, types2 = run()
        assert n1 == n2, "same seed should spawn same count"
        assert types1 == types2, "same seed should spawn same enemy types"


class TestSpawnUpdateNoCrash:
    """spawn_system.update(state, dt) does not crash when level_context is set and wave is active."""

    def test_update_with_no_enemies_and_wave_active(self, game_state_wave1):
        random.seed(1)
        start_wave(1, state=game_state_wave1)
        state = game_state_wave1
        state.enemies.clear()
        state.wave_active = True
        state.time_to_next_wave = 0.0

        # Should not raise; may start next-wave countdown or leave state unchanged
        spawn_update(state, 0.016)
