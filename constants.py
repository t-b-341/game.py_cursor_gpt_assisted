"""
Game constants - immutable configuration values.
These are extracted from game.py for better organization.
"""

# ----------------------------
# File paths (relative to project root; controls live under assets/data/)
# ----------------------------
CONTROLS_PATH = "assets/data/controls.json"
HIGH_SCORES_DB = "high_scores.db"

# ----------------------------
# Default controls
# ----------------------------
# Sentinel for "right mouse button" in direct_allies binding (not a pygame key)
MOUSE_BUTTON_RIGHT = -1

DEFAULT_CONTROLS = {
    "move_left": "a",
    "move_right": "d",
    "move_up": "w",
    "move_down": "s",
    "boost": "left shift",
    "slow": "left ctrl",
    "dash": "space",
    "ally_drop": "q",
    "direct_allies": "right mouse",
}

# ----------------------------
# Game state constants
# ----------------------------
STATE_TITLE = "TITLE"
STATE_MENU = "MENU"
STATE_QUICK_LAUNCH = "QUICK_LAUNCH"
STATE_PLAYING = "PLAYING"
STATE_PAUSED = "PAUSED"
STATE_CONTINUE = "CONTINUE"
STATE_ENDURANCE = "ENDURANCE"
STATE_GAME_OVER = "GAME_OVER"
STATE_SAVE_GAME = "SAVE_GAME"
STATE_LOAD_GAME = "LOAD_GAME"
STATE_NAME_INPUT = "NAME_INPUT"
STATE_HIGH_SCORES = "HIGH_SCORES"
STATE_VICTORY = "VICTORY"
STATE_MODS = "MODS"
STATE_WAVE_BUILDER = "WAVE_BUILDER"
STATE_CONTROLS = "CONTROLS"

# ----------------------------
# Difficulty constants
# ----------------------------
DIFFICULTY_EASY = "EASY"
DIFFICULTY_NORMAL = "NORMAL"
DIFFICULTY_HARD = "HARD"

difficulty_options = [DIFFICULTY_EASY, DIFFICULTY_NORMAL, DIFFICULTY_HARD]

difficulty_multipliers = {
    DIFFICULTY_EASY: {"enemy_hp": 0.7, "enemy_speed": 0.8, "enemy_spawn": 0.8, "pickup_spawn": 1.3},
    DIFFICULTY_NORMAL: {"enemy_hp": 1.0, "enemy_speed": 1.0, "enemy_spawn": 1.0, "pickup_spawn": 1.0},
    DIFFICULTY_HARD: {"enemy_hp": 1.5, "enemy_speed": 1.3, "enemy_spawn": 1.5, "pickup_spawn": 0.7},
}

# ----------------------------
# Aiming mode constants
# ----------------------------
AIM_MOUSE = "MOUSE"
AIM_ARROWS = "ARROWS"

# ----------------------------
# Player class constants
# ----------------------------
PLAYER_CLASS_TANK = "TANK"
PLAYER_CLASS_SPEEDSTER = "SPEEDSTER"
PLAYER_CLASS_SNIPER = "SNIPER"
PLAYER_CLASS_BALANCED = "BALANCED"

player_class_options = [PLAYER_CLASS_BALANCED, PLAYER_CLASS_TANK, PLAYER_CLASS_SPEEDSTER, PLAYER_CLASS_SNIPER]

player_class_stats = {
    PLAYER_CLASS_BALANCED: {"hp_mult": 1.0, "speed_mult": 1.0, "damage_mult": 1.0, "firerate_mult": 1.0},
    PLAYER_CLASS_TANK: {"hp_mult": 2.0, "speed_mult": 0.7, "damage_mult": 1.2, "firerate_mult": 0.8},
    PLAYER_CLASS_SPEEDSTER: {"hp_mult": 0.7, "speed_mult": 1.5, "damage_mult": 0.9, "firerate_mult": 1.3},
    PLAYER_CLASS_SNIPER: {"hp_mult": 0.8, "speed_mult": 0.9, "damage_mult": 1.5, "firerate_mult": 0.7},
}

# ----------------------------
# Level system
# ----------------------------
level_themes = {
    1: {"name": "Forest", "bg_color": (20, 60, 20), "block_color_shift": (0, 0, 0)},
    2: {"name": "Desert", "bg_color": (60, 50, 20), "block_color_shift": (20, 10, -10)},
    3: {"name": "Ice", "bg_color": (20, 40, 60), "block_color_shift": (-20, -10, 20)},
    4: {"name": "Volcano", "bg_color": (60, 20, 20), "block_color_shift": (30, -10, -20)},
    5: {"name": "Void", "bg_color": (10, 10, 20), "block_color_shift": (-30, -30, 10)},
}

# ----------------------------
# Character profile constants
# ----------------------------
character_profile_options = ["Premade Profiles", "Create Custom Profile"]
custom_profile_stats_list = ["HP Multiplier", "Speed Multiplier", "Damage Multiplier", "Fire Rate Multiplier"]
custom_profile_stats_keys = ["hp_mult", "speed_mult", "damage_mult", "firerate_mult"]

# ----------------------------
# UI constants
# ----------------------------
pause_options = ["Continue", "Restart (Wave 1)", "Shader options", "Save & Quit", "Exit to main menu", "Quit"]
controls_actions = ["move_left", "move_right", "move_up", "move_down", "boost", "slow", "dash", "ally_drop", "direct_allies"]

# ----------------------------
# Weapon constants
# ----------------------------
weapon_selection_options = ["laser", "triple", "giant", "basic"]

# Note: WEAPON_KEY_MAP uses pygame constants and must remain in game.py

# Balance/tuning: re-export from config.balance (single source of truth)
from config.balance import (
    LIVES_START,
    SCORE_BASE_POINTS,
    SCORE_TIME_MULTIPLIER,
    SCORE_WAVE_MULTIPLIER,
    ENEMY_COLOR,
    ENEMY_PROJECTILE_DAMAGE,
    ENEMY_PROJECTILE_SIZE,
    ENEMY_PROJECTILES_COLOR,
    MAX_ENEMIES_TARGETING_PLAYER,
    PICKUP_BONUS_POINTS,
    PICKUP_LIFETIME,
    PICKUP_SPAWN_INTERVAL,
    POS_SAMPLE_INTERVAL,
    UNLOCKED_WEAPON_DAMAGE_MULT,
    ALLY_AGGRO_RADIUS,
    ALLY_AGGRO_PRIORITY,
    DROPPED_ALLY_AGGRO_RADIUS,
    DROPPED_ALLY_AGGRO_PRIORITY,
    ally_drop_cooldown,
    boost_drain_per_s,
    boost_meter_max,
    boost_regen_per_s,
    boost_speed_mult,
    fire_rate_buff_duration,
    fire_rate_mult,
    grenade_cooldown,
    grenade_damage,
    jump_cooldown,
    jump_duration,
    jump_speed,
    laser_cooldown,
    laser_damage,
    laser_length,
    missile_cooldown,
    missile_damage,
    rocket_cooldown,
    rocket_damage,
    overshield_max,
    overshield_recharge_cooldown,
    player_bullet_damage,
    player_bullet_shapes,
    player_bullet_size,
    player_bullet_speed,
    player_bullets_color,
    player_shoot_cooldown,
    shield_duration,
    shield_recharge_cooldown,
    slow_speed_mult,
)
