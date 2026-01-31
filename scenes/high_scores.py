"""HighScoreScene: high scores list. Wraps screens.high_scores handle_events and render."""
from __future__ import annotations

from constants import STATE_HIGH_SCORES, STATE_PLAYING
from rendering import RenderContext
from screens import high_scores as high_scores_screen
from scenes.base import BaseScene
from scenes.transitions import SceneTransition


class HighScoreScene(BaseScene):
    def state_id(self) -> str:
        return STATE_HIGH_SCORES

    def handle_input(self, events, game_state, ctx: dict) -> dict:
        return high_scores_screen.handle_events(events, game_state, ctx)

    def render(self, render_ctx: RenderContext, game_state, ctx: dict) -> None:
        high_scores_screen.render(render_ctx, game_state, ctx)
    
    def _get_screen_transition(self, screen: str, result: dict) -> SceneTransition:
        # Replay triggers a new game via game loop
        if result.get("replay"):
            return SceneTransition.replace(STATE_PLAYING)
        return SceneTransition.replace(screen)
