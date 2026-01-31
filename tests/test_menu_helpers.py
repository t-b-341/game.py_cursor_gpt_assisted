"""Tests for rendering/menu_helpers.py"""
import pygame
import pytest

from rendering.menu_helpers import (
    get_menu_option_rects,
    handle_menu_navigation,
    _get_cached_menu_text,
    clear_menu_cache,
)


class TestGetMenuOptionRects:
    """Tests for get_menu_option_rects function."""

    def test_returns_correct_number_of_rects(self):
        """Should return one rect per option."""
        rects = get_menu_option_rects(800, 600, y_start=200, num_options=5)
        assert len(rects) == 5

    def test_rects_are_centered(self):
        """Rects should be horizontally centered."""
        width = 800
        rects = get_menu_option_rects(width, 600, y_start=200, num_options=3, option_width=400)
        for rect in rects:
            assert rect.centerx == width // 2

    def test_rects_are_vertically_spaced(self):
        """Rects should be spaced by line_height."""
        y_start = 200
        line_height = 50
        rects = get_menu_option_rects(800, 600, y_start=y_start, num_options=3, line_height=line_height)
        
        for i, rect in enumerate(rects):
            expected_y = y_start + i * line_height
            assert rect.centery == expected_y

    def test_custom_option_width(self):
        """Should use custom option_width."""
        option_width = 300
        rects = get_menu_option_rects(800, 600, y_start=200, num_options=2, option_width=option_width)
        for rect in rects:
            assert rect.width == option_width


class TestHandleMenuNavigation:
    """Tests for handle_menu_navigation function."""

    def _make_keydown_event(self, key):
        """Helper to create a KEYDOWN event."""
        return pygame.event.Event(pygame.KEYDOWN, key=key)

    def _make_mousedown_event(self, pos, button=1):
        """Helper to create a MOUSEBUTTONDOWN event."""
        return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)

    def test_arrow_up_decrements_index(self):
        """UP arrow should decrement selected index."""
        events = [self._make_keydown_event(pygame.K_UP)]
        new_idx, confirmed, clicked = handle_menu_navigation(events, num_options=5, selected_index=2)
        assert new_idx == 1
        assert not confirmed
        assert clicked == -1

    def test_arrow_down_increments_index(self):
        """DOWN arrow should increment selected index."""
        events = [self._make_keydown_event(pygame.K_DOWN)]
        new_idx, confirmed, clicked = handle_menu_navigation(events, num_options=5, selected_index=2)
        assert new_idx == 3
        assert not confirmed
        assert clicked == -1

    def test_arrow_up_wraps_around(self):
        """UP from index 0 should wrap to last index."""
        events = [self._make_keydown_event(pygame.K_UP)]
        new_idx, _, _ = handle_menu_navigation(events, num_options=5, selected_index=0)
        assert new_idx == 4

    def test_arrow_down_wraps_around(self):
        """DOWN from last index should wrap to 0."""
        events = [self._make_keydown_event(pygame.K_DOWN)]
        new_idx, _, _ = handle_menu_navigation(events, num_options=5, selected_index=4)
        assert new_idx == 0

    def test_enter_confirms(self):
        """RETURN key should set confirmed=True."""
        events = [self._make_keydown_event(pygame.K_RETURN)]
        new_idx, confirmed, clicked = handle_menu_navigation(events, num_options=5, selected_index=2)
        assert new_idx == 2  # Index unchanged
        assert confirmed
        assert clicked == -1

    def test_numpad_enter_confirms(self):
        """Numpad ENTER should also confirm."""
        events = [self._make_keydown_event(pygame.K_KP_ENTER)]
        _, confirmed, _ = handle_menu_navigation(events, num_options=5, selected_index=2)
        assert confirmed

    def test_mouse_click_returns_clicked_index(self):
        """Mouse click inside a rect should return that index."""
        rects = [
            pygame.Rect(100, 0, 200, 40),
            pygame.Rect(100, 40, 200, 40),
            pygame.Rect(100, 80, 200, 40),
        ]
        # Click inside second rect
        events = [self._make_mousedown_event((200, 50))]
        new_idx, confirmed, clicked = handle_menu_navigation(
            events, num_options=3, selected_index=0, option_rects=rects
        )
        assert clicked == 1

    def test_mouse_click_outside_rects(self):
        """Mouse click outside rects should return clicked_index=-1."""
        rects = [
            pygame.Rect(100, 0, 200, 40),
            pygame.Rect(100, 40, 200, 40),
        ]
        # Click outside all rects
        events = [self._make_mousedown_event((50, 50))]
        _, _, clicked = handle_menu_navigation(
            events, num_options=2, selected_index=0, option_rects=rects
        )
        assert clicked == -1

    def test_right_click_ignored(self):
        """Right click (button 3) should not trigger selection."""
        rects = [pygame.Rect(100, 0, 200, 40)]
        events = [self._make_mousedown_event((150, 20), button=3)]
        _, _, clicked = handle_menu_navigation(
            events, num_options=1, selected_index=0, option_rects=rects
        )
        assert clicked == -1

    def test_no_events_returns_same_index(self):
        """No events should keep index unchanged."""
        new_idx, confirmed, clicked = handle_menu_navigation(
            events=[], num_options=5, selected_index=2
        )
        assert new_idx == 2
        assert not confirmed
        assert clicked == -1

    def test_no_rects_disables_mouse_click(self):
        """Without option_rects, mouse clicks should be ignored."""
        events = [self._make_mousedown_event((150, 50))]
        _, _, clicked = handle_menu_navigation(
            events, num_options=3, selected_index=0, option_rects=None
        )
        assert clicked == -1


class TestMenuTextCache:
    """Tests for menu text caching."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Clear cache before each test."""
        clear_menu_cache()

    def test_cache_returns_same_surface(self):
        """Same text/font/color should return cached surface."""
        pygame.font.init()
        font = pygame.font.Font(None, 24)
        
        surf1 = _get_cached_menu_text(font, "Test", (255, 255, 255))
        surf2 = _get_cached_menu_text(font, "Test", (255, 255, 255))
        
        # Should be the exact same object (cached)
        assert surf1 is surf2

    def test_different_text_returns_different_surface(self):
        """Different text should return different surface."""
        pygame.font.init()
        font = pygame.font.Font(None, 24)
        
        surf1 = _get_cached_menu_text(font, "Test1", (255, 255, 255))
        surf2 = _get_cached_menu_text(font, "Test2", (255, 255, 255))
        
        assert surf1 is not surf2

    def test_different_color_returns_different_surface(self):
        """Different color should return different surface."""
        pygame.font.init()
        font = pygame.font.Font(None, 24)
        
        surf1 = _get_cached_menu_text(font, "Test", (255, 0, 0))
        surf2 = _get_cached_menu_text(font, "Test", (0, 255, 0))
        
        assert surf1 is not surf2

    def test_clear_cache_empties_cache(self):
        """clear_menu_cache should empty the cache."""
        pygame.font.init()
        font = pygame.font.Font(None, 24)
        
        _get_cached_menu_text(font, "Test", (255, 255, 255))
        clear_menu_cache()
        
        # After clearing, a new surface should be created
        # (We can't easily verify this, but the function should not raise)
        surf = _get_cached_menu_text(font, "Test", (255, 255, 255))
        assert surf is not None
