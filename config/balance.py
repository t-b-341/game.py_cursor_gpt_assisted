"""
Gameplay balance and tuning constants. Single source of truth for values
that are gameplay configuration; constants.py re-exports these for backward compatibility.
"""

# Weapon / player projectiles
player_bullet_shapes = ["circle", "square", "diamond"]
player_bullets_color = (10, 200, 200)
player_bullet_size = (8, 8)
player_bullet_speed = 450  # Reduced by 0.5x
player_bullet_damage = 150
player_shoot_cooldown = 0.12

# Laser
laser_length = 800
laser_damage = 50
laser_cooldown = 0.3

UNLOCKED_WEAPON_DAMAGE_MULT = 1.75

# Lives
LIVES_START = 10

# Dash/jump
jump_cooldown = 0.5
jump_speed = 600
jump_duration = 0.15

# Boost/slow
boost_meter_max = 100.0
boost_drain_per_s = 45.0
boost_regen_per_s = 25.0
boost_speed_mult = 1.7
slow_speed_mult = 0.45

# Fire rate buff
fire_rate_buff_duration = 10.0
fire_rate_mult = 0.55

# Shield
shield_duration = 5.0
shield_recharge_cooldown = 1.25  # 0.25x original (was 5.0 -> 2.5 -> 1.25)

# Overshield
overshield_max = 37
overshield_recharge_cooldown = 45.0

# Grenade
grenade_cooldown = 2.0
grenade_damage = 1500

# Missile / Rocket (same thing: player seeking missiles)
missile_cooldown = 0.1335  # 2x rate of fire (0.267 / 2)
missile_damage = 800
rocket_cooldown = missile_cooldown  # alias: missile = rocket
rocket_damage = missile_damage

# Ally drop
ally_drop_cooldown = 1.5

# Ally aggro/taunt system
ALLY_AGGRO_RADIUS = 250.0  # Base radius where allies draw enemy attention
ALLY_AGGRO_PRIORITY = 0.7  # Chance (0-1) that enemies in range target ally instead of player
DROPPED_ALLY_AGGRO_RADIUS = 400.0  # Dropped allies have larger aggro radius
DROPPED_ALLY_AGGRO_PRIORITY = 0.9  # Dropped allies are more likely to draw aggro

# Scoring
SCORE_BASE_POINTS = 100
SCORE_WAVE_MULTIPLIER = 50
SCORE_TIME_MULTIPLIER = 2

# Game timing / tuning
POS_SAMPLE_INTERVAL = 0.25
PICKUP_SPAWN_INTERVAL = 75.0  # 1/10th former rate (was 7.5)
PICKUP_BONUS_POINTS = 5000  # Points per bonus pickup
PICKUP_LIFETIME = 7.0  # Seconds before pickup despawns (encourages movement)
MAX_ENEMIES_TARGETING_PLAYER = 18

# Enemy appearance / projectiles
ENEMY_COLOR = (200, 50, 50)
ENEMY_PROJECTILE_SIZE = (10, 10)
ENEMY_PROJECTILE_DAMAGE = 11
ENEMY_PROJECTILES_COLOR = (200, 200, 200)
