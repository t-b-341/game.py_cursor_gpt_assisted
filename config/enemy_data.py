"""
Canonical enemy data: templates, spawn/scaling constants, friendly AI.
Used by config.enemy_defs; config_enemies.py is a compatibility shim that re-exports from enemy_defs.
"""

import pygame
import random

# Note: pygame.Rect is used here for initial positioning, but these are just templates.
# The actual rects will be created at runtime when enemies are spawned.

# ----------------------------
# Enemy Templates
# ----------------------------
# Base enemy definitions used to create enemy instances.
# These templates are cloned and modified at runtime (HP scaling, speed scaling, etc.)
# Size classes: basic = smallest (28), large = next (32–40), super_large = 4x large (128)
ENEMY_TEMPLATES: list[dict] = [
    {
        "type": "ambient",
        "rect": pygame.Rect(0, 0, 26, 26),
        "color": (150, 80, 200),  # Purple
        "hp": 40,
        "max_hp": 40,
        "shoot_cooldown": 6.0,  # Fires one rocket at player every 6s (dodgeable)
        "projectile_speed": 110,  # Slow enough to dodge (reduced by 0.5x)
        "projectile_color": (200, 100, 80),
        "projectile_shape": "circle",
        "speed": 0,  # Stationary
        "is_ambient": True,
        "rocket_cooldown": 0.0,
    },
    {
        "type": "suicide",
        "rect": pygame.Rect(200, 200, 48, 48),  # Twice as big (24*2 = 48)
        "color": (255, 50, 50),  # Bright red
        "hp": 30,
        "max_hp": 30,
        "shoot_cooldown": 999.0,  # Doesn't shoot
        "projectile_speed": 0,
        "projectile_color": (255, 0, 0),
        "projectile_shape": "circle",
        "speed": 90,  # 0.75x current speed (120 * 0.75 = 90)
        "is_suicide": True,  # Marks this as suicide enemy
        "explosion_range": 150,  # Range for grenade explosion
        "detonation_distance": 50,  # Distance from player to detonate (closer before exploding)
    },
    {
        "type": "grunt",
        "rect": pygame.Rect(120, 450, 28, 28),
        "color": (220, 80, 80),
        "hp": 60,
        "max_hp": 60,
        "shoot_cooldown": 0.9,
        "projectile_speed": 160,  # Reduced by 0.5x
        "projectile_color": (180, 220, 255),
        "projectile_shape": "square",
        "speed": 90,
        "enemy_size_class": "basic",
    },
    {
        "type": "heavy",
        "rect": pygame.Rect(650, 120, 32, 32),
        "color": (220, 120, 80),
        "hp": 80,
        "max_hp": 80,
        "shoot_cooldown": 1.2,
        "projectile_speed": 140,  # Reduced by 0.5x
        "projectile_color": (255, 190, 120),
        "projectile_shape": "circle",
        "speed": 70,
        "enemy_size_class": "large",
    },
    {
        "type": "bouncer",
        "rect": pygame.Rect(500, 500, 30, 30),
        "color": (255, 100, 100),
        "hp": 70,
        "max_hp": 70,
        "shoot_cooldown": 1.5,
        "projectile_speed": 175,  # Reduced by 0.5x
        "projectile_color": (255, 150, 150),
        "projectile_shape": "square",
        "speed": 85,
        "enemy_size_class": "large",
    },
    {
        "type": "shield enemy",
        "rect": pygame.Rect(300, 300, 32, 32),
        "color": (100, 150, 200),
        "hp": 100,
        "max_hp": 100,
        "shoot_cooldown": 1.0,
        "projectile_speed": 150,  # Reduced by 0.5x
        "projectile_color": (150, 200, 255),
        "projectile_shape": "circle",
        "speed": 60,
        "has_shield": True,  # Reflects shots with extra damage unless flanked
        "shield_angle": 0.0,
        "shield_length": 50,
        "reflect_damage_mult": 1.5,  # Extra damage when reflecting
        "enemy_size_class": "large",
    },
    {
        "type": "reflector",
        "rect": pygame.Rect(400, 400, 36, 36),
        "color": (200, 150, 100),
        "hp": 150,
        "max_hp": 150,
        "shoot_cooldown": 999.0,  # Doesn't shoot
        "projectile_speed": 0,
        "projectile_color": (255, 200, 100),
        "projectile_shape": "circle",
        "speed": 40,  # Slow turn speed
        "has_reflective_shield": True,  # Has reflective shield
        "shield_angle": 0.0,  # Direction shield is facing (radians)
        "shield_length": 60,  # Length of shield
        "shield_hp": 0,  # Damage absorbed by shield (fires back)
        "turn_speed": 0.5,
        "enemy_size_class": "large",
    },
    {
        "type": "spawner",
        "rect": pygame.Rect(500, 500, 40, 40),
        "color": (150, 50, 150),  # Purple
        "hp": 120,
        "max_hp": 120,
        "shoot_cooldown": 999.0,  # Doesn't shoot projectiles
        "projectile_speed": 0,
        "projectile_color": (150, 50, 150),
        "projectile_shape": "circle",
        "speed": 30,  # Slow movement
        "is_spawner": True,  # Marks this as a spawner enemy
        "spawn_cooldown": 5.0,  # Spawns enemies every 5 seconds
        "time_since_spawn": 0.0,
        "spawn_count": 0,  # Track how many enemies spawned
        "max_spawns": 3,
        "enemy_size_class": "large",
    },
    {
        "type": "queen",
        "name": "queen",  # Explicit name
        "rect": pygame.Rect(400, 400, 32, 32),
        "color": (100, 0, 0),  # Dark maroon (player clone)
        "hp": 5000,  # 5000 health (per GAME_IMPROVEMENTS.md line 60)
        "max_hp": 5000,
        "shoot_cooldown": 0.5,  # Increased rate of fire (reduced from 1.0s to 0.5s)
        "projectile_speed": 175,  # Reduced by 0.5x
        "projectile_color": (150, 0, 0),
        "projectile_shape": "circle",
        "speed": 240,  # 3x standard speed (80 * 3)
        "is_player_clone": True,  # Marks this as player clone
        "enemy_class": "queen",  # Enemy class identifier
        "has_shield": True,  # Queen has shield
        "shield_angle": 0.0,
        "shield_length": 60,
        "shield_active": False,  # Shield activation state
        "shield_timer": 0.0,  # Timer for shield activation/deactivation cycles
        "shield_phase_duration": random.uniform(10.0, 20.0),  # 10-20 seconds per phase
        "shield_active_duration": random.uniform(5.0, 10.0),  # 5-10 seconds when enabled
        "can_use_grenades": True,  # Queen can use grenades
        "grenade_cooldown": 5.0,  # Grenade cooldown for queen
        "time_since_grenade": 999.0,
        "can_use_missiles": True,  # Queen can use missiles
        "missile_cooldown": 6.67,  # Missile cooldown (increased fire rate by 1.5x: 10.0 / 1.5)
        "time_since_missile": 999.0,
        "damage_taken_since_rage": 0,  # Track damage for rage mode
        "rage_mode_active": False,  # Rage mode after 300-500 damage
        "rage_mode_timer": 0.0,  # Rage mode duration (5 seconds)
        "rage_damage_threshold": random.randint(300, 500),  # Random threshold between 300-500
        "predicts_player": True,  # Queen also predicts player position
    },
    {
        "type": "patrol",
        "rect": pygame.Rect(0, 0, 32, 32),
        "color": (150, 100, 200),  # Purple
        "hp": 150,
        "max_hp": 150,
        "shoot_cooldown": 0.5,
        "projectile_speed": 200,  # Reduced by 0.5x
        "projectile_color": (200, 150, 255),
        "projectile_shape": "circle",
        "speed": 100,
        "is_patrol": True,
        "patrol_side": 0,
        "patrol_progress": 0.0,
        "enemy_size_class": "large",
    },
    {
        "type": "flamethrower",
        "rect": pygame.Rect(0, 0, 30, 30),
        "color": (220, 100, 40),
        "hp": 55,
        "max_hp": 55,
        "shoot_cooldown": 0.15,
        "projectile_speed": 190,  # Reduced by 0.5x
        "projectile_color": (255, 120, 40),
        "projectile_shape": "circle",
        "speed": 70,
        "enemy_size_class": "basic",
        "is_flamethrower": True,
        "flame_damage": 8,
    },
    {
        "type": "super_large",
        "rect": pygame.Rect(0, 0, 128, 128),  # 4x large (32*4)
        "color": (80, 60, 100),
        "hp": 800,
        "max_hp": 800,
        "shoot_cooldown": 2.0,
        "projectile_speed": 175,  # Reduced by 0.5x
        "projectile_color": (180, 100, 150),
        "projectile_shape": "circle",
        "speed": 20,
        "enemy_size_class": "super_large",
        "fires_rockets": True,
        "rocket_cooldown": 0.0,
        "rocket_interval": 5.0,
        "can_use_grenades_player_allies_only": True,
        "grenade_cooldown": 8.0,
        "time_since_grenade": 999.0,
        "grenade_damage": 400,
        "grenade_radius": 120,
    },
    {
        "type": "large_laser",
        "rect": pygame.Rect(0, 0, 48, 48),
        "color": (120, 80, 180),
        "hp": 120,
        "max_hp": 120,
        "shoot_cooldown": 999.0,
        "projectile_speed": 0,
        "projectile_color": (180, 100, 255),
        "projectile_shape": "circle",
        "speed": 50,
        "enemy_size_class": "large",
        "fires_laser": True,
        "laser_cooldown": 0.0,
        "laser_interval": 3.0,
        "laser_duration": 0.4,
        "laser_deploy_time": 2.0,  # 50x slower deployment: beam grows over 2s before dealing damage
        "laser_damage": 80,
        "laser_length": 600,
    },
    {
        "type": "super_large_triple_laser",
        "rect": pygame.Rect(0, 0, 128, 128),
        "color": (60, 40, 120),
        "hp": 1000,
        "max_hp": 1000,
        "shoot_cooldown": 999.0,
        "projectile_speed": 0,
        "projectile_color": (200, 80, 255),
        "projectile_shape": "circle",
        "speed": 18,
        "enemy_size_class": "super_large",
        "fires_triple_laser": True,
        "laser_cooldown": 0.0,
        "laser_interval": 4.0,
        "laser_duration": 0.5,
        "laser_deploy_time": 2.0,  # 50x slower deployment: beams grow over 2s before dealing damage
        "laser_damage": 120,
        "laser_length": 700,
        "laser_spread_deg": 15,
    },
]

# ----------------------------
# Boss Enemy Template
# ----------------------------
# Special boss enemy template (spawned at specific waves)
# Note: rect position will be set at runtime (center of screen)
BOSS_TEMPLATE: dict = {
    "type": "FINAL_BOSS",
    "rect": pygame.Rect(0, 0, 100, 100),  # Size only, position set at runtime
    "color": (255, 0, 0),
    "hp": 3000,  # Note: This may be scaled at runtime
    "max_hp": 3000,
    "shoot_cooldown": 0.5,
    "projectile_speed": 200,  # Reduced by 0.5x
    "projectile_color": (255, 50, 50),
    "projectile_shape": "circle",
    "speed": 50,
    "is_boss": True,
    "phase": 1,  # Boss has 3 phases
    "phase_hp_thresholds": [0.66, 0.33],  # Phase 2 at 66% HP, Phase 3 at 33% HP
    "time_since_shot": 0.0,
}

# ----------------------------
# Enemy Spawn Configuration
# ----------------------------
BASE_ENEMIES_PER_WAVE = 12  # Base enemy count per wave (increased from 9)
MAX_ENEMIES_PER_WAVE = 72  # Maximum enemies per wave (increased from 54)
ENEMY_SPAWN_MULTIPLIER = 3.5  # Multiplier applied to base count (increased from 3.0x)

# ----------------------------
# Enemy Scaling Configuration
# ----------------------------
# These multipliers are applied when creating enemies from templates
ENEMY_HP_SCALE_MULTIPLIER = 1.1  # 110% health multiplier
ENEMY_SPEED_SCALE_MULTIPLIER = 1.1  # 110% speed multiplier
ENEMY_FIRE_RATE_MULTIPLIER = 7.5  # 5x fire rate (cooldown / 5; was 1.5 for 150%)
ENEMY_HP_CAP = 300  # Maximum HP for non-queen enemies

# Queen-specific constants (not affected by normal scaling)
QUEEN_FIXED_HP = 5000  # Queen has fixed HP (doesn't scale)
QUEEN_SPEED_MULTIPLIER = 3.0  # Queen moves 3x standard speed

# ----------------------------
# Friendly AI Templates
# ----------------------------
FRIENDLY_AI_TEMPLATES: list[dict] = [
    {
        "type": "scout",
        "rect": pygame.Rect(0, 0, 24, 24),
        "color": (100, 200, 255),  # Light blue
        "hp": 75,  # 50-100 health range (randomized at spawn)
        "max_hp": 75,
        "shoot_cooldown": 0.4,
        "projectile_speed": 300,  # Reduced by 0.5x
        "projectile_color": (150, 220, 255),
        "projectile_shape": "circle",
        "speed": 180,
        "behavior": "aggressive",  # Charges nearest enemy
        "damage": 15,
    },
    {
        "type": "guardian",
        "rect": pygame.Rect(0, 0, 28, 28),
        "color": (100, 255, 150),  # Light green
        "hp": 100,  # 50-100 health range (randomized at spawn)
        "max_hp": 100,
        "shoot_cooldown": 0.6,
        "projectile_speed": 250,  # Reduced by 0.5x
        "projectile_color": (150, 255, 200),
        "projectile_shape": "square",
        "speed": 120,
        "behavior": "defensive",  # Stays near player, attacks nearby enemies
        "damage": 20,
    },
    {
        "type": "sniper",
        "rect": pygame.Rect(0, 0, 22, 22),
        "color": (255, 200, 100),  # Orange
        "hp": 60,  # 50-100 health range (randomized at spawn)
        "max_hp": 60,
        "shoot_cooldown": 1.2,
        "projectile_speed": 400,  # Reduced by 0.5x
        "projectile_color": (255, 220, 150),
        "projectile_shape": "diamond",
        "speed": 100,
        "behavior": "ranged",  # Keeps distance, snipes enemies
        "damage": 35,
    },
    {
        "type": "tank",
        "rect": pygame.Rect(0, 0, 32, 32),
        "color": (200, 150, 255),  # Purple
        "hp": 100,  # 50-100 health range (randomized at spawn)
        "max_hp": 100,
        "shoot_cooldown": 0.8,
        "projectile_speed": 200,  # Reduced by 0.5x
        "projectile_color": (220, 180, 255),
        "projectile_shape": "square",
        "speed": 80,
        "behavior": "tank",  # Slow, high HP, draws enemy fire
        "damage": 25,
    },
    {
        "type": "striker",
        "rect": pygame.Rect(0, 0, 26, 26),
        "color": (255, 180, 100),  # Amber
        "hp": 70,
        "max_hp": 70,
        "shoot_cooldown": 2.0,
        "projectile_speed": 200,  # Reduced by 0.5x
        "projectile_color": (255, 200, 120),
        "projectile_shape": "diamond",
        "speed": 140,
        "behavior": "ranged",
        "damage": 20,
        "fires_missiles": True,
        "missile_burst_interval": 7.0,
        "missile_burst_count": 3,
        "missile_damage": 300,
        "missile_explosion_radius": 80,
    },
]
