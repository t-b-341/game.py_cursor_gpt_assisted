"""Game state container for all mutable game state.
Level geometry in .level (LevelState); ECS in ecs_entities, create_entity, get_entities_with."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Optional, Type

import pygame

from level_state import LevelState
from ui_state import UiState


@dataclass
class GameState:
    """Container for all mutable game state.
    
    This centralizes all game state that changes during gameplay,
    replacing module-level globals for better organization and testability.
    """
    # Core game entity lists
    enemies: list = field(default_factory=list)
    player_bullets: list = field(default_factory=list)
    enemy_projectiles: list = field(default_factory=list)
    friendly_projectiles: list = field(default_factory=list)
    friendly_ai: list = field(default_factory=list)
    pickups: list = field(default_factory=list)
    grenade_explosions: list = field(default_factory=list)
    missiles: list = field(default_factory=list)
    laser_beams: list = field(default_factory=list)
    enemy_laser_beams: list = field(default_factory=list)
    wave_beams: list = field(default_factory=list)
    damage_numbers: list = field(default_factory=list)
    weapon_pickup_messages: list = field(default_factory=list)
    pickup_particles: list = field(default_factory=list)
    collection_effects: list = field(default_factory=list)
    enemy_defeat_messages: list = field(default_factory=list)
    decoys: list = field(default_factory=list)  # Distraction shots that draw enemy fire
    
    # Player state
    player_hp: int = 7500
    player_max_hp: int = 5625  # 7500 * 0.75
    player_speed: int = 450
    player_bullet_damage: int = 20
    player_shoot_cooldown: float = 0.12
    player_time_since_shot: float = 999.0
    player_bullet_shape_index: int = 0
    overshield: int = 0
    overshield_recharge_timer: float = 0.0
    armor_drain_timer: float = 0.0  # Accumulates dt; every 0.5s drains 50 armor until armor is 0
    shield_active: bool = False
    shield_duration_remaining: float = 0.0
    shield_cooldown: float = 10.0
    shield_cooldown_remaining: float = 0.0
    shield_recharge_timer: float = 0.0
    shield_recharge_cooldown: float = 10.0
    lives: int = 10
    player_health_regen_rate: float = 0.0
    player_current_zones: set = field(default_factory=set)
    
    # Player movement and abilities
    last_horizontal_key: Optional[int] = None
    last_vertical_key: Optional[int] = None
    last_move_velocity: pygame.Vector2 = field(default_factory=lambda: pygame.Vector2(0, 0))
    # Per-frame movement input (set by game loop before movement_system.update)
    move_input_x: int = 0
    move_input_y: int = 0
    speed_mult: float = 1.0
    jump_cooldown_timer: float = 0.0
    jump_velocity: pygame.Vector2 = field(default_factory=lambda: pygame.Vector2(0, 0))
    jump_timer: float = 0.0
    is_jumping: bool = False
    previous_boost_state: bool = False
    previous_slow_state: bool = False
    boost_meter: float = 100.0
    
    # Weapon and combat state
    current_weapon_mode: str = "giant"
    previous_weapon_mode: str = "giant"
    unlocked_weapons: set = field(default_factory=lambda: {"basic", "giant", "triple", "laser"})
    laser_time_since_shot: float = 999.0
    wave_beam_time_since_shot: float = 999.0
    wave_beam_pattern_index: int = 0
    grenade_time_since_used: float = 999.0
    missile_time_since_used: float = 999.0
    ally_drop_timer: float = 0.0
    dropped_ally: Optional[dict] = None
    ally_command_target: Optional[tuple[float, float]] = None  # Mouse position for "allies go here"
    ally_command_timer: float = 0.0  # Seconds until allies stop following command
    teleporter_cooldown: float = 0.0  # Seconds after teleport before can teleport again
    decoy_time_since_used: float = 999.0  # Cooldown timer for decoy shots

    # Player stat multipliers (from pickups)
    player_stat_multipliers: dict = field(default_factory=lambda: {
        "speed": 1.0,
        "firerate": 1.0,
        "bullet_size": 1.0,
        "bullet_speed": 1.0,
        "bullet_damage": 1.0,
        "bullet_knockback": 1.0,
        "bullet_penetration": 0,
        "bullet_explosion_radius": 0.0,
    })
    random_damage_multiplier: float = 1.0
    fire_rate_buff_t: float = 0.0
    
    # Game progression and scoring
    score: int = 0
    wave_number: int = 1
    wave_in_level: int = 1
    current_level: int = 1
    max_level: int = 3
    wave_active: bool = True
    time_to_next_wave: float = 0.0
    boss_active: bool = False
    pickup_spawn_timer: float = 0.0

    # Wave reset debugging: who started a wave and how many enemies were alive (to track spurious resets)
    wave_reset_log: list = field(default_factory=list)  # [{run_time, trigger, wave_num, enemies_before}, ...]
    wave_start_reason: str = ""  # Set by caller before start_wave; consumed and logged in _start_wave
    
    # Run statistics
    run_time: float = 0.0
    survival_time: float = 0.0
    shots_fired: int = 0
    hits: int = 0
    damage_taken: int = 0
    damage_dealt: int = 0
    enemies_spawned: int = 0
    enemies_killed: int = 0
    deaths: int = 0
    pos_timer: float = 0.0
    
    # Side quests
    side_quests: dict = field(default_factory=lambda: {
        "no_hit_wave": {
            "name": "Perfect Wave",
            "description": "Complete wave without getting hit",
            "bonus_points": 10000,
            "active": False,
            "completed": False,
        }
    })
    wave_damage_taken: int = 0
    
    # High score system
    player_name_input: str = ""
    name_input_active: bool = False
    final_score_for_high_score: int = 0

    # Game over state (wave where player died, for "try again" feature)
    game_over_wave: int = 1  # Wave number when game over occurred

    # Juice: timers for visual feedback (driven by config durations; decay in sim step)
    screen_damage_flash_timer: float = 0.0  # Seconds left for fullscreen damage vignette
    damage_wobble_timer: float = 0.0  # Seconds left for optional screen jitter (enable_damage_wobble)
    wave_banner_timer: float = 0.0
    wave_banner_text: str = ""

    # Player rect (position/size on screen; created in main() after display init)
    player_rect: Optional[pygame.Rect] = None

    # Screen/flow state (which UI state we're in: MENU, PLAYING, PAUSED, etc.)
    current_screen: str = "MENU"
    previous_screen: Optional[str] = None

    # UI state (menu selections, visibility flags, UI timers)
    ui: UiState = field(default_factory=UiState)
    
    # Controls rebinding state (gameplay-related, not pure UI)
    controls_rebinding: bool = False
    custom_profile_stats: dict = field(default_factory=lambda: {"hp_mult": 1.0, "speed_mult": 1.0, "damage_mult": 1.0, "firerate_mult": 1.0})
    beam_selection_pattern: str = "giant"

    # Level data: teleporter pads (set when level is built)
    teleporter_pads: list = field(default_factory=list)

    # Telemetry run tracking
    run_id: Any = None
    run_started_at: str = ""

    # Level geometry (set when level is built in main)
    level: Optional[LevelState] = None

    # Level context for systems (set by main/game loop): move_player, move_enemy, clamp, blocks, width, height, rect_offscreen, vec_toward, update_friendly_ai
    level_context: Any = None

    # Lightweight ECS registry (optional): entity_id -> {ComponentType: instance}
    # Coexists with enemies, player_bullets, etc. during migration.
    ecs_entities: dict[int, dict[Type[Any], Any]] = field(default_factory=dict)
    _ecs_next_id: int = 0

    def create_entity(self, components: list[Any]) -> int:
        """Create an entity with the given components. Returns entity id."""
        eid = self._ecs_next_id
        self._ecs_next_id += 1
        self.ecs_entities[eid] = {type(c): c for c in components}
        return eid

    def get_entities_with(self, *component_types: Type[Any]) -> Iterator[int]:
        """Yield entity ids that have all of the given component types."""
        for eid, comps in self.ecs_entities.items():
            if all(t in comps for t in component_types):
                yield eid

    def remove_entity(self, eid: int) -> None:
        """Remove an entity from the registry."""
        self.ecs_entities.pop(eid, None)

    def reset_run(self, ctx: Any = None, *, center_player: bool = False) -> None:
        """Reset the game state for a brand new run.
        Clears entities, bullets, projectiles; resets HP, lives, score, timers; resets wave/level and default weapons.
        If center_player is True and ctx has width/height, centers player_rect. Caller then typically calls spawn_system_start_wave(1, self).
        """
        self.enemies.clear()
        self.player_bullets.clear()
        self.enemy_projectiles.clear()
        self.friendly_projectiles.clear()
        self.friendly_ai.clear()
        self.grenade_explosions.clear()
        self.missiles.clear()
        self.enemy_laser_beams.clear()
        self.ecs_entities.clear()
        self._ecs_next_id = 0
        self.player_hp = self.player_max_hp
        self.lives = 3
        self.score = 0
        self.run_time = 0.0
        self.survival_time = 0.0
        self.unlocked_weapons = {"basic", "giant", "triple", "laser"}
        self.current_weapon_mode = "giant"
        self.reset_wave(1)
        if center_player and ctx is not None and self.player_rect is not None:
            w = getattr(ctx, "width", None) or (ctx.get("width") if isinstance(ctx, dict) else None)
            h = getattr(ctx, "height", None) or (ctx.get("height") if isinstance(ctx, dict) else None)
            if w is not None and h is not None:
                self.player_rect.center = (w // 2, h // 2)

    def reset_wave(self, wave: int = 1) -> None:
        """Reset wave-related fields, starting at the given wave."""
        self.wave_number = wave
        self.wave_in_level = wave if wave <= 3 else ((wave - 1) % 3) + 1
        self.current_level = max(1, (wave - 1) // 3 + 1) if wave >= 1 else 1
        self.wave_active = False
        self.time_to_next_wave = 0.0