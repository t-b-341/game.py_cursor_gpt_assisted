"""NameInputScene: enter name for high score. Wraps screens.name_input handle_events and render."""
from __future__ import annotations

from constants import STATE_NAME_INPUT, STATE_HIGH_SCORES
from rendering import RenderContext
from screens import name_input as name_input_screen
from scenes.transitions import SceneTransition


class NameInputScene:
    def state_id(self) -> str:
        return STATE_NAME_INPUT

    def handle_input(self, events, game_state, ctx: dict) -> dict:
        return name_input_screen.handle_events(events, game_state, ctx)

    def update(self, dt: float, game_state, ctx: dict) -> None:
        pass

    def handle_input_transition(self, events, game_state, ctx: dict) -> SceneTransition:
        """Process name input and return transition to high scores when done."""
        result = self.handle_input(events, game_state, ctx)
        
        # Check if we should transition to high scores
        if result.get("screen") == STATE_HIGH_SCORES:
            # Pop this scene and push high scores
            return SceneTransition.replace(STATE_HIGH_SCORES)
        
        return SceneTransition.none()

    def update_transition(self, dt: float, game_state, ctx: dict) -> SceneTransition:
        """Update logic; return NONE."""
        self.update(dt, game_state, ctx)
        return SceneTransition.none()

    def render(self, render_ctx: RenderContext, game_state, ctx: dict) -> None:
        name_input_screen.render(render_ctx, game_state, ctx)

    def on_enter(self, game_state, ctx: dict) -> None:
        pass

    def on_exit(self, game_state, ctx: dict) -> None:
        pass
