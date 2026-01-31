"""
Main game entry point and event coordinator.

Initialization logic is in game_init.py. This file handles:
- Event polling and dispatch
- Scene transitions  
- Simulation stepping
- Exit cleanup
"""
import logging
from datetime import datetime, timezone

import pygame

# -----------------------------------------------------------------------------
# Essential imports for event handling and gameplay
# -----------------------------------------------------------------------------
from constants import (
    STATE_ENDURANCE,
    STATE_GAME_OVER,
    STATE_HIGH_SCORES,
    STATE_LOAD_GAME,
    STATE_MENU,
    STATE_NAME_INPUT,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_QUICK_LAUNCH,
    STATE_SAVE_GAME,
    STATE_TELEMETRY_VIEWER,
    STATE_TITLE,
    STATE_VICTORY,
)
from context import AppContext
from state import GameState
from scenes import SceneStack
from scenes.transitions import SceneTransition, KIND_NONE, apply_scene_transition
from shader_effects import get_menu_shader_stack, get_pause_shader_stack, get_gameplay_shader_stack
from engine.run_manager import (
    start_new_run,
    restart_current_wave,
    restart_from_wave_one,
    replay as run_replay,
    try_again as run_try_again,
    load_game as run_load_game,
)
from systems.audio_system import play_music
from systems.telemetry_system import update_telemetry
from systems.projectile_spawning import spawn_player_bullet_and_log

# Performance recording (no-op unless GAME_DEBUG_PERF=1)
try:
    from telemetry.perf import record_frame as _perf_record_frame
except ImportError:
    _perf_record_frame = lambda _dt: None


# -----------------------------------------------------------------------------
# INITIALIZATION - delegated to game_init.py
# -----------------------------------------------------------------------------
from game_init import create_app as _create_app


def _print_active_shader_profiles(config) -> None:
    """Debug-only: print currently active shader profile names and stack lengths. Does not change config."""
    if config is None:
        return
    try:
        menu = get_menu_shader_stack(config)
        pause = get_pause_shader_stack(config)
        gameplay = get_gameplay_shader_stack(config)
        mp = getattr(config, "menu_shader_profile", "none")
        pp = getattr(config, "pause_shader_profile", "none")
        gp = getattr(config, "gameplay_shader_profile", "none")
        print(f"[Shader profiles] menu={mp} (len={len(menu)}) pause={pp} (len={len(pause)}) gameplay={gp} (len={len(gameplay)})")
    except Exception as e:
        print(f"[Shader profiles] could not report: {e}")


def _get_current_scene(scene_stack: SceneStack):
    """Return the current scene from the stack, or None if empty."""
    return scene_stack.current()


# _get_current_state imported from engine.render_loop

# Scene transition logic is now in scenes/transitions.py (apply_scene_transition)


# -----------------------------------------------------------------------------
# EVENT POLLING AND INPUT DISPATCH (delegated to engine/input_loop)
# -----------------------------------------------------------------------------
from engine.input_loop import (
    poll_events as _engine_poll_events,
    handle_global_events as _engine_handle_global_events,
    handle_scene_events as _engine_handle_scene_events,
    handle_debug_keys as _engine_handle_debug_keys,
)
from engine.render_loop import (
    get_current_state as _get_current_state,
    render_current_scene as _render_current_scene,
)


def _poll_events() -> list:
    """Poll pygame events and return them. Delegates to engine.input_loop."""
    return _engine_poll_events()


def handle_global_events(events: list, ctx: AppContext, game_state: GameState, ui_state, scene_stack: SceneStack, screen_ctx: dict) -> bool:
    """Handle global events (QUIT). Delegates to engine.input_loop."""
    return _engine_handle_global_events(events)


def handle_scene_events(events: list, ctx: AppContext, game_state: GameState, ui_state, scene_stack: SceneStack, screen_ctx: dict, previous_game_state: str | None) -> SceneTransition | None:
    """Delegate events to the active scene. Delegates to engine.input_loop."""
    return _engine_handle_scene_events(events, game_state, scene_stack, screen_ctx)


def handle_debug_keys(events: list, ctx: AppContext) -> None:
    """Handle debug keys (F3). Delegates to engine.input_loop."""
    _engine_handle_debug_keys(events, ctx.config)


# -----------------------------------------------------------------------------
# EVENT HANDLING - _handle_events is the coordinator
# Core input logic is in engine/input_loop.py. This file provides thin wrappers
# and the coordinator function that processes transitions and updates game state.
# -----------------------------------------------------------------------------

def _handle_events(
    events: list,
    ctx: AppContext,
    game_state: GameState,
    scene_stack: SceneStack,
    screen_ctx: dict,
    previous_game_state: str | None,
    pause_selected: int,
    controls_selected: int,
    controls_rebinding: bool,
) -> tuple[bool, str | None, int, int, bool]:
    """
    Handle all input events. Returns (running, previous_game_state, pause_selected, controls_selected, controls_rebinding).
    
    This function is the COORDINATOR for input handling. It delegates to:
    1. handle_global_events: Handles truly global events (QUIT, etc.)
    2. handle_scene_events: Delegates to the scene system
    3. handle_debug_keys: Handles debug shortcuts (F3 for shader profiles)
    
    All screen states are now represented as scenes. Input flows through the scene stack.
    
    Future: Move the helper functions into a dedicated input routing module and keep this
    function as a thin coordinator in game.py.
    """
    # Step 1: Handle global events (QUIT, etc.)
    running = handle_global_events(events, ctx, game_state, game_state.ui, scene_stack, screen_ctx)
    if not running:
        return False, previous_game_state, pause_selected, controls_selected, controls_rebinding
    
    # Step 2: Try scene-driven input handling
    handled_by_screen = False
    scene_result = None
    current_scene = _get_current_scene(scene_stack)
    current_state = _get_current_state(scene_stack) or game_state.current_screen
    
    transition = handle_scene_events(events, ctx, game_state, game_state.ui, scene_stack, screen_ctx, previous_game_state)
    
    if transition is not None:
        # Get the result from handle_input to check for flags like start_game, try_again, load_game, restart_to_wave1
        # handle_input_transition calls handle_input internally and stores result in _last_input_result.
        # We retrieve that stored result to avoid calling handle_input twice (which would process events twice).
        if current_state in ("SHADER_SETTINGS", STATE_GAME_OVER, STATE_SAVE_GAME, STATE_LOAD_GAME, STATE_TELEMETRY_VIEWER, STATE_QUICK_LAUNCH, STATE_MENU, STATE_PAUSED):
            scene_result = getattr(current_scene, "_last_input_result", None) if current_scene else None
        
        if transition.kind != KIND_NONE:
            should_quit = apply_scene_transition(transition, scene_stack, game_state)
            if should_quit:
                return False, previous_game_state, pause_selected, controls_selected, controls_rebinding
            handled_by_screen = True
        else:
            # Transition is NONE, but handle_input was called (config changes applied)
            # For PAUSED and SHADER_SETTINGS, the input was handled, so mark as handled
            if current_state in (STATE_MENU, STATE_QUICK_LAUNCH):
                handled_by_screen = False  # Let fallback process start_game
            elif current_state == "SHADER_SETTINGS":
                # Check if start_game was requested from shader settings
                if scene_result and scene_result.get("start_game"):
                    handled_by_screen = False  # Let fallback process start_game
                else:
                    handled_by_screen = True  # Scene handled its own input
            elif current_state == STATE_PAUSED:
                # Check if restart was requested - needs fallback processing
                if scene_result and (scene_result.get("restart") or scene_result.get("restart_to_wave1")):
                    handled_by_screen = False  # Let fallback process restart
                else:
                    handled_by_screen = True  # Scene handled its own input
            elif current_state in (STATE_HIGH_SCORES, STATE_NAME_INPUT, "SHADER_TEST", STATE_TITLE, STATE_TELEMETRY_VIEWER):
                handled_by_screen = True  # Scene handled its own input
            elif current_state in (STATE_GAME_OVER, STATE_SAVE_GAME, STATE_LOAD_GAME):
                # These scenes return SceneTransition.none() for actions like "try_again" or "load_game"
                # that need to be processed by the fallback handler, so don't mark as handled
                handled_by_screen = False
    
    # Fallback to old input handling if scene path didn't handle it
    current_state = _get_current_state(scene_stack) or game_state.current_screen
    if not handled_by_screen and current_state in (STATE_PAUSED, STATE_HIGH_SCORES, STATE_NAME_INPUT, "SHADER_TEST", "SHADER_SETTINGS", STATE_TITLE, STATE_MENU, STATE_QUICK_LAUNCH, STATE_GAME_OVER, STATE_VICTORY, STATE_SAVE_GAME, STATE_LOAD_GAME, STATE_TELEMETRY_VIEWER):
        # Use scene_result if we already got it, otherwise get it now
        if scene_result is not None:
            result = scene_result
        elif current_scene:
            result = current_scene.handle_input(events, game_state, screen_ctx)
        else:
            # INVARIANT: All states must have a scene on the stack.
            # If we reach here, it's a bug - the scene stack should always have the appropriate scene.
            logging.getLogger(__name__).error(
                f"No scene on stack for state '{current_state}'. This is a bug - all states should have scenes."
            )
            assert False, f"Missing scene for state '{current_state}'. Scene migration is incomplete."
        
        if result.get("quit"):
            return False, previous_game_state, pause_selected, controls_selected, controls_rebinding
        if result.get("pop"):
            scene_stack.pop()
            current_state = _get_current_state(scene_stack) or STATE_PLAYING
            game_state.current_screen = current_state
        # Handle restart/replay/wave1 restart - delegate to RunManager
        if result.get("restart") or result.get("restart_to_wave1") or result.get("replay"):
            if result.get("restart"):
                restart_current_wave(ctx, game_state)
            elif result.get("restart_to_wave1"):
                restart_from_wave_one(ctx, game_state, scene_stack)
            elif result.get("replay"):
                run_replay(ctx, game_state, scene_stack)
        
        # Handle start_game from menu - delegate to RunManager
        if result.get("start_game") and result.get("screen") == STATE_PLAYING:
            endurance_mode = game_state.ui.endurance_mode_selected == 1
            start_new_run(ctx, game_state, scene_stack, endurance_mode=endurance_mode)
        
        current_state = _get_current_state(scene_stack) or game_state.current_screen
        # Sync pause_selected from game_state (handler may have updated it)
        if current_state == STATE_PAUSED:
            pause_selected = game_state.ui.pause_selected
        
        # Handle "try_again" from game over screen - delegate to RunManager
        if result.get("try_again"):
            run_try_again(ctx, game_state, scene_stack)
        # Handle "load_game" from load game screen - delegate to RunManager
        elif result.get("load_game") and result.get("load_slot"):
            run_load_game(ctx, game_state, scene_stack, result["load_slot"])
        elif result.get("screen") is not None and not result.get("start_game"):
            new_screen = result["screen"]
            game_state.current_screen = new_screen
            # Play ambient music for menu screens
            if new_screen in (STATE_MENU, STATE_QUICK_LAUNCH):
                play_music("ambient2", loop=True)
            # Determine if we should clear or just push
            clear_first = new_screen in (STATE_MENU, STATE_QUICK_LAUNCH, STATE_TITLE, STATE_GAME_OVER, STATE_VICTORY)
            pop_if_paused = new_screen in (STATE_PLAYING, STATE_ENDURANCE) and current_state == STATE_PAUSED
            if pop_if_paused:
                scene_stack.pop()
            else:
                if clear_first:
                    scene_stack.clear()
                from scenes.transitions import create_scene_for_state
                scene = create_scene_for_state(new_screen)
                if scene:
                    scene_stack.push(scene)
        handled_by_screen = True
    
    # Step 4: Handle debug keys (F3 for shader profile info)
    handle_debug_keys(events, ctx)
    
    return True, previous_game_state, pause_selected, controls_selected, controls_rebinding


def _step_simulation(
    simulation_accumulator: float,
    dt: float,
    FIXED_DT: float,
    MAX_SIMULATION_STEPS: int,
    _update_simulation,
    ctx: AppContext,
    game_state: GameState,
    scene_stack: SceneStack,
    screen_ctx: dict,
) -> tuple[float, bool]:
    """Run fixed-step simulation updates. Returns (new_accumulator, should_quit)."""
    simulation_accumulator += dt
    steps = 0
    should_quit = False
    while simulation_accumulator >= FIXED_DT and steps < MAX_SIMULATION_STEPS:
        # Try scene-driven update first
        current_scene = _get_current_scene(scene_stack)
        if current_scene is not None:
            try:
                transition = current_scene.update_transition(FIXED_DT, game_state, screen_ctx)
                if transition.kind != KIND_NONE:
                    should_quit = apply_scene_transition(transition, scene_stack, game_state)
                    if should_quit:
                        break
            except AttributeError:
                # Scene doesn't have update_transition, fall through to old path
                pass
        
        # Run simulation update (for gameplay scenes)
        _update_simulation(FIXED_DT, game_state, ctx)
        simulation_accumulator -= FIXED_DT
        steps += 1
    return simulation_accumulator, should_quit


# _render_current_scene imported from engine.render_loop


def _handle_exit(ctx: AppContext, game_state: GameState) -> None:
    """Handle cleanup and telemetry when exiting the game."""
    run_ended_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if ctx.config.enable_telemetry and ctx.telemetry_client:
        ctx.telemetry_client.end_run(
            ended_at_iso=run_ended_at,
            seconds_survived=game_state.run_time,
            player_hp_end=game_state.player_hp,
            shots_fired=game_state.shots_fired,
            hits=game_state.hits,
            damage_taken=game_state.damage_taken,
            damage_dealt=game_state.damage_dealt,
            enemies_spawned=game_state.enemies_spawned,
            enemies_killed=game_state.enemies_killed,
            deaths=game_state.deaths,
            max_wave=game_state.wave_number,
        )
        ctx.telemetry_client.close()
        print(f"Saved run_id={game_state.run_id} to game_telemetry.db")
    pygame.quit()


def _run_loop(app):
    """
    DEPRECATED: This function is now a thin wrapper around GameApp.run().
    The main loop logic has been moved into GameApp methods (process_events, update, render, run).
    This wrapper is kept for backward compatibility but will be removed in the future.
    """
    # GameApp.run() now contains the full loop logic
    app.run()


def main():
    """Thin entrypoint: create GameApp and run the main loop."""
    from game_app import GameApp
    GameApp().run()


if __name__ == "__main__":
    main()
