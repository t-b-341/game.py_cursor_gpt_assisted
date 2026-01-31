"""
Event polling and high-level input dispatch.

This module handles:
- Polling pygame events
- Global event handling (QUIT, debug keys)
- Delegating input to the active scene via the SceneStack
- Processing scene transitions

The game loop calls these functions via _handle_events in game.py,
which acts as the coordinator for all input handling.
"""
from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from context import AppContext
    from state import GameState
    from scenes.base import SceneStack
    from scenes.transitions import SceneTransition


def poll_events() -> list:
    """Poll pygame events and return them as a list."""
    return pygame.event.get()


def handle_global_events(events: list) -> bool:
    """
    Handle events that apply globally, regardless of which scene is active.
    
    Returns False if the game should stop running (e.g., QUIT event), True otherwise.
    This function is PURELY about "does the game keep running?" and truly global shortcuts.
    """
    for event in events:
        if event.type == pygame.QUIT:
            return False
    return True


def handle_scene_events(
    events: list,
    game_state: "GameState",
    scene_stack: "SceneStack",
    screen_ctx: dict,
) -> "SceneTransition | None":
    """
    Delegate events to the active scene via the SceneStack.
    
    Returns a SceneTransition object (or None) describing what should happen
    (push, pop, quit, replace, none). All game states are represented as scenes;
    input flows through handle_input_transition().
    """
    current_scene = scene_stack.current()
    if current_scene is None:
        return None
    
    try:
        transition = current_scene.handle_input_transition(events, game_state, screen_ctx)
        return transition
    except AttributeError:
        # Scene doesn't have handle_input_transition
        return None
    except Exception as e:
        print(f"[handle_scene_events] Error in scene handle_input_transition: {e}")
        traceback.print_exc()
        return None


def handle_debug_keys(events: list, config, ctx=None) -> None:
    """Handle global debug keys (F3 for shader profile info, F6 for map cycling)."""
    for event in events:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F3:
                _print_active_shader_profiles(config)
            elif event.key == pygame.K_F6 and ctx is not None:
                _cycle_map(ctx)


def _print_active_shader_profiles(config) -> None:
    """Debug-only: print currently active shader profile names and stack lengths."""
    if config is None:
        return
    try:
        from shader_effects import get_menu_shader_stack, get_pause_shader_stack, get_gameplay_shader_stack
        menu = get_menu_shader_stack(config)
        pause = get_pause_shader_stack(config)
        gameplay = get_gameplay_shader_stack(config)
        mp = getattr(config, "menu_shader_profile", "none")
        pp = getattr(config, "pause_shader_profile", "none")
        gp = getattr(config, "gameplay_shader_profile", "none")
        print(f"[Shader profiles] menu={mp} (len={len(menu)}) pause={pp} (len={len(pause)}) gameplay={gp} (len={len(gameplay)})")
    except Exception as e:
        print(f"[Shader profiles] could not report: {e}")


def _cycle_map(ctx) -> None:
    """Debug-only: cycle to the next available map."""
    if ctx is None or ctx.map_manager is None:
        print("[maps] Map manager not available")
        return
    try:
        new_map = ctx.map_manager.cycle_map()
        if new_map:
            print(f"[maps] Switched to map: {new_map}")
        else:
            print("[maps] No maps available to cycle")
    except Exception as e:
        print(f"[maps] Error cycling map: {e}")


def process_scene_transition(
    transition: "SceneTransition",
    scene_stack: "SceneStack",
    game_state: "GameState",
) -> bool:
    """
    Apply a scene transition and update game state accordingly.
    
    Returns True if the game should quit, False otherwise.
    This is a simplified version - the full transition logic with screen_ctx
    and result processing remains in game.py for now.
    """
    from scenes.transitions import KIND_NONE, KIND_PUSH, KIND_POP, KIND_REPLACE, KIND_QUIT_GAME
    
    if transition.kind == KIND_NONE:
        return False
    
    if transition.kind == KIND_QUIT_GAME:
        return True
    
    if transition.kind == KIND_POP:
        scene_stack.pop()
        # Update current_screen from scene stack
        current = scene_stack.current()
        if current is not None:
            game_state.current_screen = current.state_id()
        return False
    
    if transition.kind == KIND_PUSH:
        # The actual scene creation and push happens in game.py
        # since it needs access to scene class imports
        pass
    
    if transition.kind == KIND_REPLACE:
        # The actual scene creation and stack replacement happens in game.py
        # since it needs access to scene class imports
        pass
    
    return False
