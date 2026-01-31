"""Render loop: scene rendering dispatch and frame composition.

This module handles rendering the current scene based on game state,
including gameplay rendering, menu rendering, and shader effects.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from context import AppContext
    from state import GameState
    from scenes import SceneStack

from constants import (
    STATE_ENDURANCE,
    STATE_GAME_OVER,
    STATE_HIGH_SCORES,
    STATE_LOAD_GAME,
    STATE_MAP_TEST,
    STATE_MENU,
    STATE_NAME_INPUT,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_QUICK_LAUNCH,
    STATE_SAVE_GAME,
    STATE_TELEMETRY_VIEWER,
    STATE_TITLE,
    STATE_VICTORY,
    level_themes,
)
from rendering import RenderContext, build_gameplay_ctx
from rendering_shaders import render_gameplay_with_optional_shaders, render_gameplay_frame_to_surface
from shader_effects import get_menu_shader_stack, get_pause_shader_stack
from visual_effects import apply_menu_effects, apply_pause_effects


def get_current_state(scene_stack: "SceneStack") -> str | None:
    """Get the current state ID from the top scene in the stack, or None if empty."""
    scene = scene_stack.current()
    if scene is None:
        return None
    return scene.state_id()


def render_current_scene(
    ctx: "AppContext",
    game_state: "GameState",
    scene_stack: "SceneStack",
    screen_ctx: dict,
    pause_shaders_enabled: bool = False,
    menu_shaders_enabled: bool = False,
) -> None:
    """Render the current scene based on game state.
    
    Args:
        ctx: Application context with screen, fonts, config
        game_state: Current game state
        scene_stack: Stack of active scenes
        screen_ctx: Screen context dictionary for scene rendering
        pause_shaders_enabled: Whether pause shader effects are enabled
        menu_shaders_enabled: Whether menu shader effects are enabled
    """
    current_state = get_current_state(scene_stack) or game_state.current_screen
    theme = level_themes.get(game_state.current_level, level_themes[1])
    if current_state not in (STATE_PLAYING, STATE_ENDURANCE):
        ctx.screen.fill(theme["bg_color"])

    if current_state == STATE_PLAYING or current_state == STATE_ENDURANCE:
        _render_gameplay(ctx, game_state, current_state)
    elif current_state in (
        STATE_TITLE, STATE_MENU, STATE_QUICK_LAUNCH, STATE_PAUSED,
        STATE_HIGH_SCORES, STATE_NAME_INPUT, STATE_GAME_OVER, STATE_VICTORY,
        STATE_SAVE_GAME, STATE_LOAD_GAME, STATE_TELEMETRY_VIEWER, STATE_MAP_TEST,
        "SHADER_TEST", "SHADER_SETTINGS"
    ):
        _render_menu_or_overlay(
            ctx, game_state, scene_stack, screen_ctx,
            current_state, pause_shaders_enabled, menu_shaders_enabled
        )
    # Note: STATE_VICTORY is handled in the elif block above (scene rendering)


def _render_gameplay(
    ctx: "AppContext",
    game_state: "GameState",
    current_state: str,
) -> None:
    """Render the main gameplay scene."""
    from systems.perf_timing import perf_timer
    
    # Build gameplay context (cached on game_state for performance)
    gameplay_ctx = getattr(game_state, "_cached_gameplay_ctx", None)
    if gameplay_ctx is None:
        gameplay_ctx = build_gameplay_ctx(ctx, game_state, current_state, level_themes)
        game_state._cached_gameplay_ctx = gameplay_ctx
    else:
        # Update only values that can change (config toggles and current state)
        gameplay_ctx["ui_show_hud"] = ctx.config.show_hud
        gameplay_ctx["ui_show_metrics"] = ctx.config.show_metrics
        gameplay_ctx["ui_show_health_bars"] = ctx.config.show_health_bars
        gameplay_ctx["ui_show_fps"] = ctx.config.show_fps
        gameplay_ctx["ui_show_perf_overlay"] = getattr(ctx.config, "show_perf_overlay", False)
        gameplay_ctx["current_state"] = current_state
        # Update level references if level changed
        lv = game_state.level
        if lv:
            gameplay_ctx["static_blocks"] = lv.static_blocks
            gameplay_ctx["trapezoid_blocks"] = lv.trapezoid_blocks
            gameplay_ctx["triangle_blocks"] = lv.triangle_blocks
            gameplay_ctx["destructible_blocks"] = lv.destructible_blocks
            gameplay_ctx["moveable_destructible_blocks"] = lv.moveable_blocks
            gameplay_ctx["giant_blocks"] = lv.giant_blocks
            gameplay_ctx["super_giant_blocks"] = lv.super_giant_blocks
            gameplay_ctx["hazard_obstacles"] = lv.hazard_obstacles
            gameplay_ctx["moving_health_zone"] = lv.moving_health_zone
        gameplay_ctx["teleporter_pads"] = game_state.teleporter_pads
    
    render_ctx = RenderContext.from_app_ctx(ctx)
    with perf_timer("render_gameplay"):
        render_gameplay_with_optional_shaders(
            render_ctx, game_state, {"app_ctx": ctx, "gameplay_ctx": gameplay_ctx}
        )
    
    # Clean up expired UI tokens using O(n) filter instead of O(n²) .remove()
    game_state.damage_numbers[:] = [d for d in game_state.damage_numbers if d["timer"] > 0]
    game_state.weapon_pickup_messages[:] = [m for m in game_state.weapon_pickup_messages if m["timer"] > 0]


def _render_menu_or_overlay(
    ctx: "AppContext",
    game_state: "GameState",
    scene_stack: "SceneStack",
    screen_ctx: dict,
    current_state: str,
    pause_shaders_enabled: bool,
    menu_shaders_enabled: bool,
) -> None:
    """Render menu screens and overlay scenes (pause, high scores, etc.)."""
    # Use display render context for menus (not world surface)
    render_ctx = RenderContext.for_menu(ctx)
    
    # When paused + enable_pause_shaders: render gameplay frame, apply pause stack, then draw UI on top
    if current_state == STATE_PAUSED and pause_shaders_enabled:
        _render_pause_with_shaders(ctx, game_state, current_state)
    
    # Render the current scene
    current_scene = scene_stack.current()
    if current_scene:
        current_scene.render(render_ctx, game_state, screen_ctx)
    # Note: All states should have scenes on the stack. If no scene exists, we skip rendering.
    # This is a safety fallback - scenes should always be present for PAUSED, HIGH_SCORES, NAME_INPUT, etc.
    
    # Config-based shader stacks and legacy lightweight effects
    if current_state == STATE_PAUSED and not pause_shaders_enabled:
        apply_pause_effects(render_ctx.screen, ctx)
    elif current_state in (STATE_TITLE, STATE_MENU, STATE_QUICK_LAUNCH):
        apply_menu_effects(render_ctx.screen, ctx)
    
    # Apply config-based menu shader stack when enable_menu_shaders and menu_shader_profile != "none"
    if current_state in (STATE_TITLE, STATE_MENU, STATE_QUICK_LAUNCH) and menu_shaders_enabled:
        _apply_menu_shader_stack(ctx, game_state, render_ctx)


def _render_pause_with_shaders(
    ctx: "AppContext",
    game_state: "GameState",
    current_state: str,
) -> None:
    """Render gameplay frame with pause shader effects applied."""
    # Use display dimensions for pause overlay
    display_w = getattr(ctx, 'display_width', ctx.width)
    display_h = getattr(ctx, 'display_height', ctx.height)
    gameplay_ctx_pause = build_gameplay_ctx(
        ctx, game_state, current_state, level_themes,
        width=display_w, height=display_h
    )
    # Use cached offscreen surface to avoid per-frame allocation
    offscreen = ctx.get_offscreen_surface(display_w, display_h)
    offscreen.fill((0, 0, 0, 255))
    render_gameplay_frame_to_surface(
        offscreen, display_w, display_h,
        ctx.font, ctx.big_font, ctx.small_font,
        game_state, {"app_ctx": ctx, "gameplay_ctx": gameplay_ctx_pause},
    )
    pause_stack = get_pause_shader_stack(ctx.config)
    surf = offscreen
    eff_ctx = {"time": time.perf_counter()}
    for eff in pause_stack:
        surf = eff.apply(surf, 0.016, eff_ctx)
    ctx.screen.blit(surf, (0, 0))


def _apply_menu_shader_stack(
    ctx: "AppContext",
    game_state: "GameState",
    render_ctx: RenderContext,
) -> None:
    """Apply the menu shader stack to the current frame."""
    try:
        menu_stack = get_menu_shader_stack(ctx.config)
        if menu_stack:
            display = render_ctx.screen
            surf = display
            eff_ctx = {"time": game_state.run_time}
            for eff in menu_stack:
                if surf is None:
                    break
                surf = eff.apply(surf, 0.016, eff_ctx)
            if surf is not None and surf is not display:
                display.blit(surf, (0, 0))
    except Exception as e:
        # If shader application fails, log and continue without shaders
        print(f"[Menu shader] Error applying shader stack: {e}")
        import traceback
        traceback.print_exc()
