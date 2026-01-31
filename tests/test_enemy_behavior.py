"""Tests for enemy behavior: clamp, threat target, and template-based creation."""
import unittest
import pygame

from enemies import find_nearest_threat, make_enemy_from_template
from geometry_utils import clamp_rect_to_screen
from config_enemies import ENEMY_TEMPLATES


class TestClampRectToScreen(unittest.TestCase):
    def test_stays_in_bounds_when_already_inside(self):
        r = pygame.Rect(10, 20, 30, 40)
        clamp_rect_to_screen(r, 800, 600)
        assert r.x == 10 and r.y == 20

    def test_clamps_left_and_top(self):
        r = pygame.Rect(-5, -10, 30, 40)
        clamp_rect_to_screen(r, 800, 600)
        assert r.x == 0 and r.y == 0

    def test_clamps_right_and_bottom(self):
        r = pygame.Rect(780, 590, 30, 40)
        clamp_rect_to_screen(r, 800, 600)
        assert r.x == 770 and r.y == 560


class TestFindNearestThreat(unittest.TestCase):
    def test_none_when_no_player_and_no_friendlies(self):
        pos = pygame.Vector2(100, 100)
        assert find_nearest_threat(pos, None, []) is None

    def test_player_when_player_present(self):
        pos = pygame.Vector2(100, 100)
        player = pygame.Rect(200, 100, 32, 32)
        got = find_nearest_threat(pos, player, [])
        assert got is not None
        threat_pos, kind = got
        assert kind == "player"
        assert threat_pos.x == player.centerx and threat_pos.y == player.centery

    def test_nearest_friendly_when_no_player(self):
        pos = pygame.Vector2(100, 100)
        f1 = {"rect": pygame.Rect(300, 100, 24, 24), "hp": 50}
        f2 = {"rect": pygame.Rect(150, 100, 24, 24), "hp": 50}
        got = find_nearest_threat(pos, None, [f1, f2])
        assert got is not None
        _, kind = got
        assert kind == "friendly"
        assert got[0].x == 162 and got[0].y == 112  # center of f2 (150+12, 100+12)

    def test_dropped_ally_priority_within_radius(self):
        pos = pygame.Vector2(100, 100)
        player = pygame.Rect(50, 50, 32, 32)  # 50–82, 50–82
        dropped = {"rect": pygame.Rect(200, 100, 24, 24), "hp": 30, "is_dropped_ally": True}
        got = find_nearest_threat(pos, player, [dropped])
        assert got is not None
        _, kind = got
        # Dropped ally at (200,100) is within 350px of (100,100); player is closer but ally wins
        assert kind == "dropped_ally"

    def test_skips_dead_friendlies(self):
        pos = pygame.Vector2(100, 100)
        dead = {"rect": pygame.Rect(110, 110, 24, 24), "hp": 0}
        assert find_nearest_threat(pos, None, [dead]) is None


class TestMakeEnemyFromTemplate(unittest.TestCase):
    def test_pawn_template_returns_enemy_with_expected_fields(self):
        t = next(tmpl for tmpl in ENEMY_TEMPLATES if tmpl.get("type") == "grunt")
        assert t["type"] == "grunt"
        e = make_enemy_from_template(t, 1.0, 1.0)
        assert e["type"] == "grunt"
        assert e["rect"].w == 28 and e["rect"].h == 28
        assert e["hp"] > 0 and e["hp"] == e["max_hp"]
        assert e.get("speed") is not None

    def test_enemy_supports_dict_like_access(self):
        t = next(tmpl for tmpl in ENEMY_TEMPLATES if tmpl.get("type") == "grunt")
        e = make_enemy_from_template(t, 1.0, 1.0)
        assert e["type"] == "grunt"
        assert e.get("color") is not None
        assert e["rect"] is not None
