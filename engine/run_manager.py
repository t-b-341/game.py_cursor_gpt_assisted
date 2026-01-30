"""Run and wave lifecycle management.

This module centralizes all run/wave lifecycle logic:
- Starting new runs (from menu, quick launch)
- Starting waves
- Handling restarts (current wave, wave 1, replay)
- Handling try-again from game over
- Loading games from save slots
- Telemetry integration for run metadata
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, Any

if TYPE_CHECKING:
    from state import GameState
    from context import AppContext
    from scenes import SceneStack


class RunManager:
    """Manages run and wave lifecycle, centralizing restart/wave logic."""
    
    def __init__(self) -> None:
        pass
    
    def start_new_run(
        self,
        ctx: "AppContext",
        game_state: "GameState",
        scene_stack: "SceneStack",
        *,
        endurance_mode: bool = False,
        initial_wave: int = 1,
    ) -> None:
        """
        Start a new run from the menu.
        
        Sets up telemetry, player stats, and starts at the specified wave.
        
        Args:
            ctx: Application context with config and telemetry client
            game_state: Game state to modify
            scene_stack: Scene stack to update
            endurance_mode: Whether to start in endurance mode
            initial_wave: Starting wave number (default 1)
        """
        from constants import STATE_PLAYING, STATE_ENDURANCE, player_class_stats
        from systems.audio_system import stop_music, play_music
        from systems.spawn_system import start_wave as spawn_system_start_wave
        from scenes import GameplayScene
        from telemetry import Telemetry, NoOpTelemetry
        
        # Stop menu music, start gameplay music
        stop_music()
        play_music("in-game", loop=True)
        
        # Set up telemetry
        if ctx.config.enable_telemetry:
            ctx.telemetry_client = Telemetry(
                db_path="game_telemetry.db",
                flush_interval_s=0.5,
                max_buffer=700,
            )
        else:
            ctx.telemetry_client = NoOpTelemetry()
        
        # Apply player class stats
        stats = player_class_stats[ctx.config.player_class]
        game_state.player_max_hp = int(1000 * stats["hp_mult"] * 0.75)
        game_state.player_hp = game_state.player_max_hp
        game_state.player_speed = int(ctx.config.player_base_speed * stats["speed_mult"])
        game_state.player_bullet_damage = int(ctx.config.player_base_damage * stats["damage_mult"])
        game_state.player_shoot_cooldown = ctx.config.player_base_shoot_cooldown / stats["firerate_mult"]
        
        # Set up game mode
        if endurance_mode:
            game_state.lives = 999
            game_state.current_screen = STATE_ENDURANCE
            game_state.previous_screen = STATE_ENDURANCE
            scene_stack.clear()
            scene_stack.push(GameplayScene(STATE_ENDURANCE))
        else:
            game_state.current_screen = STATE_PLAYING
            game_state.previous_screen = STATE_PLAYING
            scene_stack.clear()
            scene_stack.push(GameplayScene(STATE_PLAYING))
        
        # Update level context with telemetry and config
        if game_state.level_context:
            game_state.level_context["telemetry"] = ctx.telemetry_client
            game_state.level_context["telemetry_enabled"] = ctx.config.enable_telemetry
            game_state.level_context["difficulty"] = ctx.config.difficulty
            game_state.level_context["testing_mode"] = ctx.config.testing_mode
            game_state.level_context["invulnerability_mode"] = ctx.config.invulnerability_mode
        
        # Start telemetry run
        if ctx.config.enable_telemetry:
            game_state.run_id = ctx.telemetry_client.start_run(
                game_state.run_started_at,
                game_state.player_max_hp,
            )
        else:
            game_state.run_id = None
        
        ctx.last_telemetry_sample_t = -1.0
        
        # Clear wave reset log and set start reason
        game_state.wave_reset_log.clear()
        game_state.wave_start_reason = "menu_start"
        
        # Set wave number and start wave
        game_state.wave_number = initial_wave
        spawn_system_start_wave(initial_wave, game_state)
    
    def restart_current_wave(
        self,
        ctx: "AppContext",
        game_state: "GameState",
    ) -> None:
        """
        Restart the current wave (from pause menu restart option).
        
        Resets the run but keeps the current wave number.
        """
        game_state.reset_run(ctx)
        game_state.ui.menu_section = 0
    
    def restart_from_wave_one(
        self,
        ctx: "AppContext",
        game_state: "GameState",
        scene_stack: "SceneStack",
    ) -> None:
        """
        Restart from wave 1 (from pause menu or other contexts).
        
        Resets the entire run and starts at wave 1.
        """
        from constants import STATE_PLAYING
        from systems.audio_system import play_music
        from systems.spawn_system import start_wave as spawn_system_start_wave
        from scenes import GameplayScene
        
        game_state.reset_run(ctx, center_player=True)
        spawn_system_start_wave(1, game_state)
        scene_stack.clear()
        scene_stack.push(GameplayScene(STATE_PLAYING))
        game_state.current_screen = STATE_PLAYING
        play_music("in-game", loop=True)
    
    def replay(
        self,
        ctx: "AppContext",
        game_state: "GameState",
        scene_stack: "SceneStack",
    ) -> None:
        """
        Replay the game (from high scores or victory screen).
        
        Same as restart_from_wave_one but used in replay contexts.
        """
        self.restart_from_wave_one(ctx, game_state, scene_stack)
    
    def try_again(
        self,
        ctx: "AppContext",
        game_state: "GameState",
        scene_stack: "SceneStack",
    ) -> None:
        """
        Try again from the game over screen.
        
        Restarts at the wave where the player died.
        """
        from constants import STATE_PLAYING
        from systems.audio_system import play_music
        from systems.spawn_system import start_wave as spawn_system_start_wave
        from scenes import GameplayScene
        
        wave_to_restart = getattr(game_state, "game_over_wave", 1)
        game_state.reset_run(ctx)
        game_state.wave_start_reason = "try_again"
        spawn_system_start_wave(wave_to_restart, game_state)
        scene_stack.clear()
        scene_stack.push(GameplayScene(STATE_PLAYING))
        game_state.current_screen = STATE_PLAYING
        play_music("in-game", loop=True)
    
    def load_game(
        self,
        ctx: "AppContext",
        game_state: "GameState",
        scene_stack: "SceneStack",
        save_slot: Any,
    ) -> None:
        """
        Load a game from a save slot.
        
        Applies saved config (difficulty, player class) and restarts at saved wave.
        
        Args:
            save_slot: Save slot object with wave_number, score, difficulty, player_class
        """
        from constants import STATE_PLAYING
        from systems.audio_system import play_music
        from systems.spawn_system import start_wave as spawn_system_start_wave
        from scenes import GameplayScene
        
        # Apply saved config
        if hasattr(ctx, "config"):
            ctx.config.difficulty = save_slot.difficulty
            ctx.config.player_class = save_slot.player_class
        
        # Reset and start at saved wave
        game_state.reset_run(ctx)
        game_state.wave_start_reason = "load_game"
        spawn_system_start_wave(save_slot.wave_number, game_state)
        game_state.score = save_slot.score
        scene_stack.clear()
        scene_stack.push(GameplayScene(STATE_PLAYING))
        game_state.current_screen = STATE_PLAYING
        play_music("in-game", loop=True)


# Global singleton instance
_run_manager: Optional[RunManager] = None


def get_run_manager() -> RunManager:
    """Get the global RunManager instance."""
    global _run_manager
    if _run_manager is None:
        _run_manager = RunManager()
    return _run_manager


def start_new_run(
    ctx: "AppContext",
    game_state: "GameState",
    scene_stack: "SceneStack",
    *,
    endurance_mode: bool = False,
    initial_wave: int = 1,
) -> None:
    """Convenience function to start a new run."""
    get_run_manager().start_new_run(
        ctx, game_state, scene_stack,
        endurance_mode=endurance_mode,
        initial_wave=initial_wave,
    )


def restart_current_wave(ctx: "AppContext", game_state: "GameState") -> None:
    """Convenience function to restart current wave."""
    get_run_manager().restart_current_wave(ctx, game_state)


def restart_from_wave_one(
    ctx: "AppContext",
    game_state: "GameState",
    scene_stack: "SceneStack",
) -> None:
    """Convenience function to restart from wave 1."""
    get_run_manager().restart_from_wave_one(ctx, game_state, scene_stack)


def replay(
    ctx: "AppContext",
    game_state: "GameState",
    scene_stack: "SceneStack",
) -> None:
    """Convenience function for replay."""
    get_run_manager().replay(ctx, game_state, scene_stack)


def try_again(
    ctx: "AppContext",
    game_state: "GameState",
    scene_stack: "SceneStack",
) -> None:
    """Convenience function for try-again."""
    get_run_manager().try_again(ctx, game_state, scene_stack)


def load_game(
    ctx: "AppContext",
    game_state: "GameState",
    scene_stack: "SceneStack",
    save_slot: Any,
) -> None:
    """Convenience function to load game."""
    get_run_manager().load_game(ctx, game_state, scene_stack, save_slot)
