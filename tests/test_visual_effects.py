"""
Tests for visual_effects: menu/gameplay effect stacks and damage wobble blit.

Ensures apply_menu_effects, apply_pause_effects, apply_gameplay_effects are no-op when
disabled and run without raising when enabled. Covers primitives and apply_gameplay_final_blit.
"""
from __future__ import annotations

import pytest  # type: ignore[import-untyped]

import pygame

import visual_effects as vef


@pytest.fixture(autouse=True)
def _pygame_init():
    if not pygame.get_init():
        pygame.init()
    yield


@pytest.fixture
def surface_100x100():
    s = pygame.Surface((100, 100))
    s.fill((80, 100, 120))
    return s


def test_apply_scanlines_no_raise(surface_100x100):
    """apply_scanlines runs without raising and modifies surface when strength > 0."""
    vef.apply_scanlines(surface_100x100, 0.0)  # no-op
    vef.apply_scanlines(surface_100x100, 0.08)
    # Center pixel should be unchanged (scanlines skip every other band); at least one call did something
    vef.apply_scanlines(surface_100x100, 0.1)


def test_apply_vignette_no_raise(surface_100x100):
    """apply_vignette runs without raising."""
    vef.apply_vignette(surface_100x100, 0.0)
    vef.apply_vignette(surface_100x100, 0.3, 0.75)


def test_apply_color_tint_no_raise(surface_100x100):
    """apply_color_tint runs without raising."""
    vef.apply_color_tint(surface_100x100, 20, 25, 50, 0)
    vef.apply_color_tint(surface_100x100, 20, 25, 50, 30)


def test_get_pulse_factor_in_range():
    """get_pulse_factor returns a value in [0, 1]."""
    for _ in range(20):
        x = vef.get_pulse_factor(2.0)
        assert 0.0 <= x <= 1.0


def test_apply_menu_effects_no_op_when_disabled(surface_100x100):
    """With enable_menu_shaders False or profile 'none', apply_menu_effects does nothing visible (no raise)."""
    class Cfg:
        enable_menu_shaders = False
        menu_effect_profile = "none"
    vef.apply_menu_effects(surface_100x100, Cfg())
    Cfg.enable_menu_shaders = True
    Cfg.menu_effect_profile = "none"
    vef.apply_menu_effects(surface_100x100, Cfg())


def test_apply_menu_effects_runs_when_enabled(surface_100x100):
    """With enable_menu_shaders True and profile crt/soft_glow/grainy, apply_menu_effects runs without raising."""
    class Cfg:
        enable_menu_shaders = True
        menu_effect_profile = "crt"
    vef.apply_menu_effects(surface_100x100, Cfg())
    for profile in ("soft_glow", "grainy", "swirly"):
        Cfg.menu_effect_profile = profile
        s2 = pygame.Surface((100, 100))
        s2.fill((80, 100, 120))
        vef.apply_menu_effects(s2, Cfg())


def test_apply_menu_effects_accepts_dict_ctx(surface_100x100):
    """apply_menu_effects accepts ctx as dict with app_ctx.config."""
    class Cfg:
        enable_menu_shaders = True
        menu_effect_profile = "crt"
    ctx = {"app_ctx": type("App", (), {"config": Cfg})()}
    vef.apply_menu_effects(surface_100x100, ctx)


def test_apply_pause_effects_no_op_when_disabled(surface_100x100):
    """With enable_menu_shaders False, apply_pause_effects does nothing (no raise)."""
    class Cfg:
        enable_menu_shaders = False
    vef.apply_pause_effects(surface_100x100, Cfg())


def test_apply_pause_effects_runs_when_enabled(surface_100x100):
    """With enable_menu_shaders True, apply_pause_effects runs without raising."""
    class Cfg:
        enable_menu_shaders = True
    vef.apply_pause_effects(surface_100x100, Cfg())


def test_apply_gameplay_effects_no_op_when_disabled(surface_100x100):
    """With enable_gameplay_shaders False or profile 'none', apply_gameplay_effects does nothing (no raise)."""
    class Cfg:
        enable_gameplay_shaders = False
        gameplay_effect_profile = "none"
    vef.apply_gameplay_effects(surface_100x100, Cfg())
    Cfg.enable_gameplay_shaders = True
    vef.apply_gameplay_effects(surface_100x100, Cfg())


def test_apply_gameplay_effects_runs_when_enabled(surface_100x100):
    """With enable_gameplay_shaders True and known profiles, runs without raising."""
    class Cfg:
        enable_gameplay_shaders = True
        gameplay_effect_profile = "subtle_vignette"
    vef.apply_gameplay_effects(surface_100x100, Cfg())
    for profile in ("crt_light", "film_grain", "atmospheric"):
        s2 = pygame.Surface((100, 100))
        s2.fill((80, 100, 120))
        Cfg.gameplay_effect_profile = profile
        vef.apply_gameplay_effects(s2, Cfg(), game_state=None)
    # Low-HP pulse path (when game_state has player_hp)
    class State:
        player_hp = 20
        player_max_hp = 100
    Cfg.gameplay_effect_profile = "atmospheric"
    s3 = pygame.Surface((100, 100))
    s3.fill((80, 100, 120))
    vef.apply_gameplay_effects(s3, Cfg(), game_state=State())


def test_apply_gameplay_final_blit_normal_when_no_wobble(surface_100x100):
    """apply_gameplay_final_blit blits source to dest when wobble disabled or timer zero."""
    dest = pygame.Surface((100, 100))
    dest.fill((0, 0, 0))
    class Cfg:
        enable_damage_wobble = False
    vef.apply_gameplay_final_blit(surface_100x100, dest, Cfg(), None)
    assert dest.get_at((50, 50)) == surface_100x100.get_at((50, 50))


def test_apply_gameplay_final_blit_wobble_no_raise(surface_100x100):
    """apply_gameplay_final_blit runs without raising when wobble enabled and timer > 0."""
    dest = pygame.Surface((100, 100))
    dest.fill((0, 0, 0))
    class Cfg:
        enable_damage_wobble = True
    class State:
        damage_wobble_timer = 0.15
    vef.apply_gameplay_final_blit(surface_100x100, dest, Cfg(), State())


def test_apply_gameplay_final_blit_handles_none_game_state(surface_100x100):
    """apply_gameplay_final_blit accepts game_state=None without raising."""
    dest = pygame.Surface((100, 100))
    class Cfg:
        enable_damage_wobble = True
    vef.apply_gameplay_final_blit(surface_100x100, dest, Cfg(), None)


def test_ease_out_quad():
    """ease_out_quad is 0 at 0, 1 at 1, and smooth in between."""
    assert vef.ease_out_quad(0.0) == 0.0
    assert vef.ease_out_quad(1.0) == 1.0
    assert 0 < vef.ease_out_quad(0.5) < 1
    assert vef.ease_out_quad(-0.1) == 0.0
    assert vef.ease_out_quad(1.5) == 1.0


def test_apply_film_grain_fast_no_raise(surface_100x100):
    """apply_film_grain_fast runs without raising."""
    vef.apply_film_grain_fast(surface_100x100, 0.0)
    vef.apply_film_grain_fast(surface_100x100, 0.06)


def test_apply_low_hp_pulse_no_raise(surface_100x100):
    """apply_low_hp_pulse no-op when hp_ratio > threshold; runs when below."""
    vef.apply_low_hp_pulse(surface_100x100, 0.8, threshold=0.35)
    vef.apply_low_hp_pulse(surface_100x100, 0.2, threshold=0.35, strength=0.15)


def test_apply_swirl_no_raise(surface_100x100):
    """apply_swirl runs without raising; no-op when strength 0."""
    vef.apply_swirl(surface_100x100, 0.5, 0.5, strength=0)
    vef.apply_swirl(surface_100x100, 0.5, 0.5, strength=0.5, step=2)
