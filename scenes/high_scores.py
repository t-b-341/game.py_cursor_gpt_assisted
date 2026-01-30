"""HighScoreScene: high scores list. Wraps screens.high_scores handle_events and render."""
from __future__ import annotations

from constants import STATE_HIGH_SCORES, STATE_PLAYING
from rendering import RenderContext
from screens import high_scores as high_scores_screen
from scenes.transitions import SceneTransition


class HighScoreScene:
    def __init__(self):
        self._last_result = None
    
    def state_id(self) -> str:
        return STATE_HIGH_SCORES

    def handle_input(self, events, game_state, ctx: dict) -> dict:
        return high_scores_screen.handle_events(events, game_state, ctx)

    def update(self, dt: float, game_state, ctx: dict) -> None:
        pass

    def handle_input_transition(self, events, game_state, ctx: dict) -> SceneTransition:
        """Process high scores input and return appropriate transition."""
        result = self.handle_input(events, game_state, ctx)
        self._last_result = result  # Store for game loop to check replay flag
        
        if result.get("quit"):
            return SceneTransition.quit_game()
        
        if result.get("replay"):
            # Replay triggers a new game - handled by game loop via result dict
            # Return a replace transition with a marker that game loop will process
            return SceneTransition.replace(STATE_PLAYING)
        
        return SceneTransition.none()

    def update_transition(self, dt: float, game_state, ctx: dict) -> SceneTransition:
        """Update logic; return NONE."""
        self.update(dt, game_state, ctx)
        return SceneTransition.none()

    def render(self, render_ctx: RenderContext, game_state, ctx: dict) -> None:
        high_scores_screen.render(render_ctx, game_state, ctx)

    def on_enter(self, game_state, ctx: dict) -> None:
        pass

    def on_exit(self, game_state, ctx: dict) -> None:
        pass
