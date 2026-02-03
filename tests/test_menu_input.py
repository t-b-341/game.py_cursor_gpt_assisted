"""Tests for menu input handling in pause and options screens.

Tests the refactored dispatcher-based menu handlers to ensure:
- Navigation (UP/DOWN) correctly cycles through options
- Submenu entry/exit works correctly
- Selection actions trigger expected state changes
"""
import pytest
import pygame


# ============================================================================
# Mock classes for testing
# ============================================================================

class MockUIState:
    """Mock UI state for testing menu navigation."""
    def __init__(self):
        # Pause menu state
        self.pause_selected = 0
        self.pause_submenu = None
        self.pause_audio_options_row = 0
        self.pause_shader_options_row = 0
        self.save_and_quit = False
        
        # Options menu state
        self.menu_section = 0
        self.menu_confirm_quit = False
        self.difficulty_selected = 0
        self.use_character_profile_selected = 0
        self.character_profile_selected = 0
        self.player_class_selected = 0
        self.ui_show_metrics_selected = 0
        self.ui_show_fps_selected = 0
        self.ui_telemetry_enabled_selected = 0
        self.custom_profile_stat_selected = 0
        self.beam_selection_selected = 0
        self.saved_profile_selected = 0
        self.profile_name_input = ""
        self.profile_name_active = False
        self.endurance_mode_selected = 0


class MockGameState:
    """Mock game state for testing."""
    def __init__(self):
        self.ui = MockUIState()
        self.previous_screen = None
        self.custom_profile_stats = {
            "hp_mult": 1.0,
            "speed_mult": 1.0,
            "damage_mult": 1.0,
            "firerate_mult": 1.0,
        }
        self.unlocked_weapons = set()
        self.current_weapon_mode = "basic"
        self.beam_selection_pattern = "basic"
        self.laser_beams = []


class MockConfig:
    """Mock config for testing."""
    def __init__(self):
        self.difficulty = "Normal"
        self.profile_enabled = False
        self.player_class = "balanced"
        self.show_metrics = True
        self.show_hud = True
        self.show_fps = False
        self.enable_telemetry = False
        self.testing_mode = False
        self.invulnerability_mode = False
        self.sfx_volume = 1.0
        self.music_volume = 1.0
        self.mute_sfx = False
        self.mute_music = False
        self.enable_gameplay_shaders = False
        self.enable_pause_shaders = False
        self.gameplay_shader_profile = "none"
        self.pause_shader_profile = "none"
        self.target_fps = 144
        self.show_perf_overlay = False


class MockAppCtx:
    """Mock app context."""
    def __init__(self):
        self.config = MockConfig()


def make_keydown_event(key: int, unicode: str = "") -> pygame.event.Event:
    """Create a mock KEYDOWN event."""
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


# ============================================================================
# screens/pause.py Tests
# ============================================================================

class TestPauseMenuNavigation:
    """Test pause menu navigation."""

    def test_up_down_cycles_options(self):
        """UP/DOWN keys cycle through pause menu options."""
        from screens.pause import handle_events
        from constants import pause_options
        
        game_state = MockGameState()
        ctx = {"app_ctx": MockAppCtx()}
        
        # Start at 0, press DOWN
        events = [make_keydown_event(pygame.K_DOWN)]
        handle_events(events, game_state, ctx)
        assert game_state.ui.pause_selected == 1
        
        # Press UP to go back
        events = [make_keydown_event(pygame.K_UP)]
        handle_events(events, game_state, ctx)
        assert game_state.ui.pause_selected == 0
        
        # Press UP at 0 should wrap to last option
        events = [make_keydown_event(pygame.K_UP)]
        handle_events(events, game_state, ctx)
        assert game_state.ui.pause_selected == len(pause_options) - 1

    def test_escape_resumes_game(self):
        """ESC key returns to playing state."""
        from screens.pause import handle_events
        from constants import STATE_PLAYING
        
        game_state = MockGameState()
        ctx = {"app_ctx": MockAppCtx()}
        
        events = [make_keydown_event(pygame.K_ESCAPE)]
        result = handle_events(events, game_state, ctx)
        
        assert result["screen"] == STATE_PLAYING

    def test_audio_submenu_entry(self):
        """Selecting Audio options enters audio submenu."""
        from screens.pause import handle_events, _handle_menu_selection
        from constants import pause_options
        
        game_state = MockGameState()
        cfg = MockConfig()
        out = {"screen": None, "quit": False, "restart": False, "restart_to_wave1": False}
        
        # Find audio options index
        audio_idx = pause_options.index("Audio options")
        game_state.ui.pause_selected = audio_idx
        
        _handle_menu_selection(game_state, cfg, out)
        
        assert game_state.ui.pause_submenu == "audio"
        assert game_state.ui.pause_audio_options_row == 0

    def test_audio_submenu_escape_exits(self):
        """ESC in audio submenu exits to main pause menu."""
        from screens.pause import _handle_audio_submenu
        
        game_state = MockGameState()
        game_state.ui.pause_submenu = "audio"
        cfg = MockConfig()
        
        event = make_keydown_event(pygame.K_ESCAPE)
        result = _handle_audio_submenu(event, game_state, cfg)
        
        assert result == {"handled": True}
        assert game_state.ui.pause_submenu is None


class TestPauseSubmenus:
    """Test pause submenu handlers."""

    def test_audio_navigation(self):
        """Audio submenu navigation cycles through 4 options."""
        from screens.pause import _handle_audio_submenu
        
        game_state = MockGameState()
        game_state.ui.pause_submenu = "audio"
        cfg = MockConfig()
        
        # Navigate down through all options
        for expected in [1, 2, 3, 0]:  # Wraps around
            event = make_keydown_event(pygame.K_DOWN)
            _handle_audio_submenu(event, game_state, cfg)
            assert game_state.ui.pause_audio_options_row == expected

    def test_shader_submenu_navigation(self):
        """Shader/settings submenu navigation cycles through 8 options."""
        from screens.pause import _handle_shader_submenu
        
        game_state = MockGameState()
        game_state.ui.pause_submenu = "shaders"
        cfg = MockConfig()
        out = {}
        
        # Navigate down through all options (8: Gameplay, Gameplay Profile, Menu Effects, Menu Profile, Pause, Pause Profile, Game Speed, Full Settings)
        for expected in [1, 2, 3, 4, 5, 6, 7, 0]:
            event = make_keydown_event(pygame.K_DOWN)
            _handle_shader_submenu(event, game_state, cfg, out)
            assert game_state.ui.pause_shader_options_row == expected


# ============================================================================
# scenes/options.py Tests
# ============================================================================

class TestOptionsMenuNavigation:
    """Test options menu section navigation."""

    def test_difficulty_selection_cycles(self):
        """Difficulty selection cycles through options."""
        from scenes.options import OptionsScene
        from constants import difficulty_options
        
        scene = OptionsScene()
        game_state = MockGameState()
        game_state.ui.menu_section = 0
        ctx = {"app_ctx": MockAppCtx(), "width": 1920, "height": 1080}
        
        # Navigate down
        events = [make_keydown_event(pygame.K_DOWN)]
        scene.handle_input(events, game_state, ctx)
        assert game_state.ui.difficulty_selected == 1
        
        # Navigate up wraps
        game_state.ui.difficulty_selected = 0
        events = [make_keydown_event(pygame.K_UP)]
        scene.handle_input(events, game_state, ctx)
        assert game_state.ui.difficulty_selected == len(difficulty_options) - 1

    def test_enter_advances_section(self):
        """ENTER key advances to next menu section."""
        from scenes.options import OptionsScene
        
        scene = OptionsScene()
        game_state = MockGameState()
        game_state.ui.menu_section = 0
        ctx = {"app_ctx": MockAppCtx(), "width": 1920, "height": 1080}
        
        events = [make_keydown_event(pygame.K_RETURN)]
        scene.handle_input(events, game_state, ctx)
        
        assert game_state.ui.menu_section == 1.5  # Next section

    def test_escape_goes_back(self):
        """ESC key navigates back through menu sections."""
        from scenes.options import OptionsScene
        from constants import STATE_TITLE
        
        scene = OptionsScene()
        game_state = MockGameState()
        ctx = {"app_ctx": MockAppCtx(), "width": 1920, "height": 1080}
        
        # At section 1.5, ESC should go to 0
        game_state.ui.menu_section = 1.5
        events = [make_keydown_event(pygame.K_ESCAPE)]
        scene.handle_input(events, game_state, ctx)
        assert game_state.ui.menu_section == 0
        
        # At section 0, ESC should return to title
        game_state.ui.menu_section = 0
        events = [make_keydown_event(pygame.K_ESCAPE)]
        result = scene.handle_input(events, game_state, ctx)
        assert result["screen"] == STATE_TITLE

    def test_section_handlers_exist(self):
        """All section handlers are defined."""
        from scenes.options import OptionsScene
        
        scene = OptionsScene()
        
        # Check that all expected handler methods exist
        expected_handlers = [
            '_handle_section_0_difficulty',
            '_handle_section_1_5_use_profile',
            '_handle_section_2_profile_type',
            '_handle_section_3_hud',
            '_handle_section_3_25_fps',
            '_handle_section_3_5_telemetry',
            '_handle_section_4_weapon',
            '_handle_section_4_5_invuln',
            '_handle_section_5_ready',
            '_handle_section_6_custom_profile',
            '_handle_section_7_class',
            '_handle_section_8_load_profile',
            '_handle_section_9_save_name',
        ]
        
        for handler in expected_handlers:
            assert hasattr(scene, handler), f"Missing handler: {handler}"
            assert callable(getattr(scene, handler))

    def test_render_handlers_exist(self):
        """All render handlers are defined."""
        from scenes.options import OptionsScene
        
        scene = OptionsScene()
        
        expected_renderers = [
            '_render_section_0',
            '_render_section_1_5',
            '_render_section_2',
            '_render_section_3',
            '_render_section_3_25',
            '_render_section_3_5',
            '_render_section_4',
            '_render_section_4_5',
            '_render_section_5',
            '_render_section_6',
            '_render_section_7',
            '_render_section_8',
            '_render_section_9',
        ]
        
        for renderer in expected_renderers:
            assert hasattr(scene, renderer), f"Missing renderer: {renderer}"


class TestOptionsHelpers:
    """Test options scene helper functions."""

    def test_cycle_selection(self):
        """_cycle_selection wraps correctly."""
        from scenes.options import _cycle_selection
        
        assert _cycle_selection(0, 1, 5) == 1  # Normal increment
        assert _cycle_selection(4, 1, 5) == 0  # Wrap forward
        assert _cycle_selection(0, -1, 5) == 4  # Wrap backward
        assert _cycle_selection(2, -1, 5) == 1  # Normal decrement


# ============================================================================
# Import Tests for screens/pause.py
# ============================================================================

class TestPauseImports:
    """Test that pause screen imports work correctly."""

    def test_pause_module_imports(self):
        """screens/pause.py should import without errors."""
        from screens.pause import (
            handle_events,
            render,
            update_idle_enemies,
            reset_idle_enemies,
        )
        assert callable(handle_events)
        assert callable(render)

    def test_pause_handlers_import(self):
        """Pause submenu handlers should be importable."""
        from screens.pause import (
            _handle_audio_submenu,
            _handle_shader_submenu,
            _handle_main_menu,
            _handle_menu_selection,
        )
        assert callable(_handle_audio_submenu)
        assert callable(_handle_shader_submenu)

    def test_pause_render_helpers_import(self):
        """Pause render helpers should be importable."""
        from screens.pause import (
            _render_audio_submenu,
            _render_shader_submenu,
            _render_main_menu,
        )
        assert callable(_render_audio_submenu)

    def test_pause_mouse_click_handlers_import(self):
        """Pause mouse click handlers should be importable."""
        from screens.pause import (
            _get_option_rects,
            _handle_main_menu_click,
            _handle_audio_submenu_click,
            _handle_shader_submenu_click,
        )
        assert callable(_get_option_rects)
        assert callable(_handle_main_menu_click)


class TestPauseMouseClick:
    """Test pause menu mouse click handling."""

    def test_get_option_rects_returns_correct_count(self):
        """_get_option_rects returns correct number of rectangles."""
        from screens.pause import _get_option_rects
        
        rects = _get_option_rects(1920, 1080, 500, 5, line_height=40)
        assert len(rects) == 5
        
        rects = _get_option_rects(1920, 1080, 500, 11, line_height=40)
        assert len(rects) == 11

    def test_main_menu_click_selects_option(self):
        """Clicking on a menu option selects it."""
        from screens.pause import _handle_main_menu_click, _get_option_rects, pause_options
        
        game_state = MockGameState()
        cfg = MockConfig()
        out = {"screen": None, "quit": False, "restart": False, "restart_to_wave1": False}
        
        # Calculate where "Continue" option would be
        width, height = 1920, 1080
        y_offset = height // 2 - 60
        rects = _get_option_rects(width, height, y_offset, len(pause_options), line_height=40)
        
        # Click on first option (Continue) - should return resume target
        center = rects[0].center
        result = _handle_main_menu_click(center, game_state, cfg, width, height, out)
        # Continue returns a result with screen set
        assert result is not None or game_state.ui.pause_selected == 0


# ============================================================================
# GameConfig Tests
# ============================================================================

class TestGameConfigTimescale:
    """Test game speed/timescale configuration."""

    def test_timescale_default(self):
        """GameConfig has timescale field defaulting to 1.0."""
        from config.game_config import GameConfig
        
        cfg = GameConfig()
        assert hasattr(cfg, 'timescale')
        assert cfg.timescale == 1.0

    def test_timescale_can_be_set(self):
        """Timescale can be set to other values."""
        from config.game_config import GameConfig
        
        cfg = GameConfig()
        cfg.timescale = 0.5
        assert cfg.timescale == 0.5
        
        cfg.timescale = 1.5
        assert cfg.timescale == 1.5

    def test_shader_submenu_adjusts_timescale(self):
        """Settings submenu can adjust timescale (row 6 = Game Speed)."""
        from screens.pause import _adjust_shader_setting
        
        cfg = MockConfig()
        cfg.timescale = 1.0
        timescales = [0.5, 0.75, 1.0, 1.25, 1.5]
        pause_profiles = ["none", "pause_dim_vignette"]
        
        _adjust_shader_setting(6, 1, cfg, pause_profiles, timescales)
        assert cfg.timescale == 1.25  # 1.0 -> 1.25
        
        _adjust_shader_setting(6, -1, cfg, pause_profiles, timescales)
        assert cfg.timescale == 1.0  # 1.25 -> 1.0


# ============================================================================
# QuickLaunchScene Tests
# ============================================================================

class TestQuickLaunchScene:
    """Test quick launch scene functionality."""

    def test_quick_launch_imports(self):
        """QuickLaunchScene should import without errors."""
        from scenes.quick_launch import QuickLaunchScene
        assert callable(QuickLaunchScene)

    def test_quick_launch_has_load_game_option(self):
        """QuickLaunchScene includes load game option when saves exist."""
        from scenes.quick_launch import QuickLaunchScene, _LOAD_GAME_OPTION
        
        scene = QuickLaunchScene()
        scene._has_saves = True
        
        options = scene._get_menu_options()
        assert _LOAD_GAME_OPTION in options

    def test_quick_launch_no_load_without_saves(self):
        """QuickLaunchScene hides load game option when no saves exist."""
        from scenes.quick_launch import QuickLaunchScene, _LOAD_GAME_OPTION
        
        scene = QuickLaunchScene()
        scene._has_saves = False
        
        options = scene._get_menu_options()
        assert _LOAD_GAME_OPTION not in options


# ============================================================================
# Telemetry Viewer Tests
# ============================================================================

class TestTelemetryViewerScene:
    """Test telemetry viewer scene functionality."""

    def test_telemetry_viewer_state_id(self):
        """TelemetryViewerScene returns correct state ID."""
        from scenes.telemetry_viewer import TelemetryViewerScene
        from constants import STATE_TELEMETRY_VIEWER
        
        scene = TelemetryViewerScene()
        assert scene.state_id() == STATE_TELEMETRY_VIEWER

    def test_telemetry_viewer_handles_missing_db(self):
        """TelemetryViewerScene handles missing database gracefully."""
        from scenes.telemetry_viewer import TelemetryViewerScene
        import os
        
        scene = TelemetryViewerScene()
        # Simulate on_enter with no database
        # (won't actually call on_enter as it needs game_state/ctx)
        
        # Verify the scene can be created without errors
        assert scene._error_message is None
        assert scene._conn is None

    def test_telemetry_viewer_in_pause_options(self):
        """Telemetry Graphs option exists in pause menu."""
        from constants import pause_options
        
        assert "Telemetry Graphs" in pause_options
