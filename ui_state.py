"""UI state container for menu selections, UI visibility flags, and UI-only state."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UiState:
    """Container for all UI/menu-related state that doesn't affect gameplay logic.
    
    This includes menu selections, UI visibility flags, and UI-only timers.
    Separated from GameState to keep UI concerns separate from gameplay state.
    """
    # Menu navigation state
    menu_section: float = 0  # 0 = difficulty, 1.5 = character profile yes/no, 2 = profile type, 3 = HUD options, 3.5 = Telemetry, 4 = weapon, 4.5 = invuln, 5 = start, 6 = custom stats, 7 = class
    pause_selected: int = 0
    controls_selected: int = 0
    
    # Menu selection indices (pre-game menu)
    difficulty_selected: int = 1
    aiming_mode_selected: int = 0
    use_character_profile_selected: int = 0
    character_profile_selected: int = 0
    custom_profile_stat_selected: int = 0
    player_class_selected: int = 0
    ui_show_metrics_selected: int = 0
    beam_selection_selected: int = 3
    endurance_mode_selected: int = 0
    ui_telemetry_enabled_selected: int = 1
    shader_options_selected_row: int = 0  # main menu shader section (0..6)
    pause_shader_options_row: int = 0     # pause submenu shader row (0..4)
    pause_audio_options_row: int = 0      # pause submenu audio row (0..3)
    pause_submenu: str | None = None      # "shaders" or "audio" when in pause submenu, else None
    
    # UI visibility flags
    ui_show_hud: bool = True
    ui_show_health_bars: bool = True
    ui_show_stats: bool = True
    ui_show_all_ui: bool = True
    ui_show_block_health_bars: bool = False  # Health bars for destructible blocks
    ui_show_player_health_bar: bool = True  # Health bar above player character
    ui_show_metrics: bool = True  # Show metrics/stats in HUD - Default: Enabled
    
    # UI timers
    continue_blink_t: float = 0.0
    
    # Confirmation dialogs
    title_confirm_quit: bool = False
    menu_confirm_quit: bool = False
    
    # Game over menu state
    game_over_selected: int = 0  # 0=Try Again, 1=Save, 2=Quit
    
    # Save/Load menu state
    save_slot_selected: int = 0  # 0, 1, or 2
    save_name_input: str = ""  # Name input for save slot
    save_name_active: bool = False  # Whether name input is active
    load_slot_selected: int = 0  # 0, 1, or 2
    save_and_quit: bool = False  # If True, go to title after saving (from pause menu)
    
    # Profile management state
    saved_profile_selected: int = 0  # Selected profile in list
    profile_name_input: str = ""  # Name input when saving profile
    profile_name_active: bool = False  # Whether profile name input is active
