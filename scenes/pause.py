"""PauseScene: pause overlay and menu. Wraps screens.pause handle_events and render."""
from __future__ import annotations

from constants import STATE_PAUSED, STATE_PLAYING, STATE_ENDURANCE, STATE_MENU, STATE_SAVE_GAME
from rendering import RenderContext
from screens import pause as pause_screen
from screens.pause import update_idle_enemies, reset_idle_enemies
from scenes.transitions import SceneTransition


class PauseScene:
    def state_id(self) -> str:
        return STATE_PAUSED

    def handle_input(self, events, game_state, ctx: dict) -> dict:
        return pause_screen.handle_events(events, game_state, ctx)

    def update(self, dt: float, game_state, ctx: dict) -> None:
        # Update idle enemy animations
        width = ctx.get("width", 1920)
        height = ctx.get("height", 1080)
        update_idle_enemies(dt, width, height)

    def handle_input_transition(self, events, game_state, ctx: dict) -> SceneTransition:
        """Call existing handle_input logic and process the result. Return transition if needed."""
        # Always process input - this updates pause_selected and handles shader submenu
        result = self.handle_input(events, game_state, ctx)
        # Store result for game loop to retrieve (for restart handling)
        self._last_input_result = result
        # Process result to handle screen changes, quit, restart, etc.
        if result.get("quit"):
            return SceneTransition.quit_game()
        if result.get("restart") or result.get("restart_to_wave1"):
            # Restart handled separately via result dict, return NONE so fallback can process it
            return SceneTransition.none()
        if result.get("screen") is not None:
            # Map screen changes to transitions
            screen = result["screen"]
            if screen in (STATE_PLAYING, STATE_ENDURANCE):
                # Resume game - pop pause scene
                return SceneTransition.pop()
            elif screen == STATE_MENU:
                return SceneTransition.replace(STATE_MENU)
            elif screen == STATE_SAVE_GAME:
                # Save & Quit - open save screen
                return SceneTransition.push(STATE_SAVE_GAME)
            elif screen == "SHADER_SETTINGS":
                # Open shader settings screen
                return SceneTransition.push("SHADER_SETTINGS")
        # Return NONE - pause menu navigation and shader submenu handled in handle_input
        # The state (pause_selected, pause_shader_options_row) was updated in handle_input above
        return SceneTransition.none()

    def update_transition(self, dt: float, game_state, ctx: dict) -> SceneTransition:
        """Stub: call existing logic; return NONE. Used by future scene-driven loop."""
        self.update(dt, game_state, ctx)
        return SceneTransition.none()

    def render(self, render_ctx: RenderContext, game_state, ctx: dict) -> None:
        pause_screen.render(render_ctx, game_state, ctx)

    def on_enter(self, game_state, ctx: dict) -> None:
        # Reset idle enemies when entering pause screen
        reset_idle_enemies()

    def on_exit(self, game_state, ctx: dict) -> None:
        # Reset idle enemies when leaving pause screen
        reset_idle_enemies()
