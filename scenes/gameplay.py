"""GameplayScene: runs simulation (movement, collision, spawn, AI, telemetry) and renders the game world."""
from __future__ import annotations

import pygame

from constants import STATE_PLAYING, STATE_PAUSED
from rendering import render_debug_overlay
from screens import gameplay as gameplay_screen
from scenes.base import BaseScene
from scenes.transitions import SceneTransition


class GameplayScene(BaseScene):
    """Scene for STATE_PLAYING / STATE_ENDURANCE. update runs GAMEPLAY_SYSTEMS; render uses screens.gameplay."""

    def __init__(self, state_id: str = STATE_PLAYING) -> None:
        super().__init__()
        self._state_id = state_id

    def state_id(self) -> str:
        return self._state_id

    def handle_input(self, events, game_state, ctx: dict) -> dict:
        """Run gameplay input (movement, fire, abilities)."""
        out = {"screen": None, "quit": False, "restart": False, "restart_to_wave1": False, "replay": False}
        handle_gameplay_input = ctx.get("handle_gameplay_input")
        if handle_gameplay_input:
            handle_gameplay_input(events, game_state, ctx.get("gameplay_input_ctx") or ctx)
        return out

    def update(self, dt: float, game_state, ctx: dict) -> None:
        gameplay_screen.update(game_state, dt, ctx.get("gameplay_ctx") or {})

    def handle_input_transition(self, events, game_state, ctx: dict) -> SceneTransition:
        """Handle gameplay input and check for pause triggers (ESC/P)."""
        # First, process gameplay input (movement, fire, abilities)
        self.handle_input(events, game_state, ctx)
        
        # Check for pause triggers
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_p):
                    # Store previous screen for unpause
                    game_state.previous_screen = self._state_id
                    game_state.ui.pause_selected = 0
                    return SceneTransition.push(STATE_PAUSED)
        
        return SceneTransition.none()

    def render(self, render_ctx, game_state, ctx: dict) -> None:
        app_ctx = ctx.get("app_ctx")
        gameplay_ctx = ctx.get("gameplay_ctx")
        if app_ctx is not None and gameplay_ctx is not None:
            gameplay_screen.render(app_ctx, game_state, gameplay_ctx)
        config = getattr(app_ctx, "config", None) if app_ctx is not None else None
        if config and getattr(config, "debug_draw_overlay", False):
            extra_lines = []
            use_shaders = bool(getattr(config, "use_shaders", False))
            extra_lines.append(f"shaders: {'ON' if use_shaders else 'OFF'}")
            try:
                from gpu_physics import CUDA_AVAILABLE
                extra_lines.append(f"cuda_available: {CUDA_AVAILABLE}")
            except Exception:
                extra_lines.append("cuda_available: unavailable")
            use_gpu_physics = bool(getattr(config, "use_gpu_physics", False))
            extra_lines.append(f"gpu_physics: {'ON' if use_gpu_physics else 'OFF'}")
            render_debug_overlay(render_ctx, game_state, extra_lines=extra_lines)
