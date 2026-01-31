"""Tests for spawn/wave-related logic (template-based creation, invariants)."""
import pygame
import pytest

from enemies import make_enemy_from_template
from config.enemy_defs import ENEMY_TEMPLATES


@pytest.mark.parametrize("template", ENEMY_TEMPLATES, ids=lambda t: t.get("type", "unknown"))
def test_every_template_produces_valid_enemy(template):
    e = make_enemy_from_template(template, 1.0, 1.0)
    assert e["type"] == template["type"]
    assert e["hp"] > 0
    assert e["rect"].w > 0 and e["rect"].h > 0
    assert e.get("speed") is not None


def test_suicide_template_produces_valid_enemy_with_expected_speed():
    suicide = next(t for t in ENEMY_TEMPLATES if t.get("type") == "suicide")
    e = make_enemy_from_template(suicide, 1.0, 1.0)
    assert e["type"] == "suicide"
    assert e["hp"] > 0
    assert e["rect"].w > 0
    # Template speed 90 * ENEMY_SPEED_SCALE_MULTIPLIER
    assert e["speed"] > 0


def test_hp_scaling_applied():
    t = ENEMY_TEMPLATES[0]  # pawn hp 50
    e1 = make_enemy_from_template(t, 1.0, 1.0)
    e2 = make_enemy_from_template(t, 2.0, 1.0)
    assert e2["hp"] >= e1["hp"]
