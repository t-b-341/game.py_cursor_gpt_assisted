"""
Scene base and SceneStack for the gameplay screen flow.

Scenes manage a single screen (gameplay, pause, high scores, name input). The game loop
delegates handle_input, update, and render to the current scene. Transitions are expressed
via the return value of handle_input (e.g. pop, push, quit, restart).

Order of operations in the loop: handle_input -> apply transitions -> update -> render.
"""
from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

import pygame

from scenes.transitions import SceneTransition


@runtime_checkable
class Scene(Protocol):
    """Protocol for a scene. handle_input returns a transition dict; update/render mutate nothing except via game_state/ctx."""

    def state_id(self) -> str:
        """Identifier used for game_state.current_screen when this scene is active (e.g. 'PLAYING', 'PAUSED')."""
        ...

    def handle_input(self, events: list, game_state: Any, ctx: dict) -> dict:
        """
        Process input events. Return a transition dict with any of:
          screen: str — set current_screen and stack will be synced (e.g. 'MENU' to exit to menu)
          pop: bool — pop this scene (resume / back)
          push: Scene — push another scene (e.g. push PauseScene)
          quit: bool, restart: bool, restart_to_wave1: bool, replay: bool — interpreted by the loop
        """
        ...

    def update(self, dt: float, game_state: Any, ctx: dict) -> None:
        """Update this scene for this frame (e.g. run gameplay systems, or no-op for static menus)."""
        ...

    def render(self, render_ctx: Any, game_state: Any, ctx: dict) -> None:
        """Draw this scene. render_ctx provides screen, fonts, dimensions."""
        ...

    def on_enter(self, game_state: Any, ctx: dict) -> None:
        """Called when this scene becomes current (after push or when replacing). Optional no-op by default."""
        ...

    def on_exit(self, game_state: Any, ctx: dict) -> None:
        """Called when this scene is replaced or popped. Optional no-op by default."""
        ...


class BaseScene:
    """Base class for scenes with common functionality.
    
    Provides default implementations for:
    - update_transition: calls update() and returns SceneTransition.none()
    - on_enter/on_exit: no-op defaults
    - _last_input_result storage for game loop compatibility
    - result_to_transition: helper to convert result dicts to SceneTransition
    
    Subclasses should override:
    - state_id(): return the scene's state identifier
    - handle_input(): process input and return result dict
    - update(): update scene state
    - render(): draw the scene
    - handle_input_transition(): (optional) override for custom transition logic
    """
    
    def __init__(self) -> None:
        self._last_input_result: dict = {}
    
    def state_id(self) -> str:
        """Override in subclass to return scene identifier."""
        raise NotImplementedError("Subclass must implement state_id()")
    
    def handle_input(self, events: list, game_state: Any, ctx: dict) -> dict:
        """Override in subclass to handle input. Return transition dict."""
        return {}
    
    def update(self, dt: float, game_state: Any, ctx: dict) -> None:
        """Override in subclass to update scene state."""
        pass
    
    def render(self, render_ctx: Any, game_state: Any, ctx: dict) -> None:
        """Override in subclass to render scene."""
        pass
    
    def on_enter(self, game_state: Any, ctx: dict) -> None:
        """Called when scene becomes active. Override for custom setup."""
        pass
    
    def on_exit(self, game_state: Any, ctx: dict) -> None:
        """Called when scene is deactivated. Override for custom cleanup."""
        pass
    
    def update_transition(self, dt: float, game_state: Any, ctx: dict) -> SceneTransition:
        """Update and return transition. Default: update() + return none()."""
        self.update(dt, game_state, ctx)
        return SceneTransition.none()
    
    def handle_input_transition(self, events: list, game_state: Any, ctx: dict) -> SceneTransition:
        """Handle input and return transition. Default implementation.
        
        Override this for custom transition logic, or override
        _get_screen_transition() for simple screen->transition mapping.
        """
        result = self.handle_input(events, game_state, ctx)
        self._last_input_result = result
        return self.result_to_transition(result)
    
    def result_to_transition(self, result: dict) -> SceneTransition:
        """Convert a result dict to a SceneTransition.
        
        Handles common patterns:
        - quit: True -> quit_game()
        - pop: True -> pop()
        - screen: str -> _get_screen_transition(screen, result)
        - restart/restart_to_wave1/replay -> none() (handled by game loop)
        
        Override _get_screen_transition() for custom screen->transition mapping.
        """
        if result.get("quit"):
            return SceneTransition.quit_game()
        
        if result.get("pop"):
            return SceneTransition.pop()
        
        screen = result.get("screen")
        if screen is not None:
            return self._get_screen_transition(screen, result)
        
        return SceneTransition.none()
    
    def _get_screen_transition(self, screen: str, result: dict) -> SceneTransition:
        """Convert a screen name to a transition. Override for custom mapping.
        
        Default: replace(screen) for most screens.
        Common overrides:
        - Push for modal screens (name input, load game, etc.)
        - Custom logic for restart/try_again flags
        """
        # Default behavior: replace to new screen
        return SceneTransition.replace(screen)
    
    def get_last_result(self) -> dict:
        """Get the last input result for game loop compatibility."""
        return self._last_input_result


class BaseMenuScene(BaseScene):
    """Base class for menu scenes with shared navigation and rendering.
    
    Provides:
    - Automatic menu option navigation (keyboard + mouse)
    - Common menu rendering helpers
    - Selection state management
    
    Subclasses should:
    - Set _options list in __init__
    - Override state_id()
    - Override _on_option_selected(index) to handle menu selection
    - Override render() for custom layout (can call render helpers)
    """
    
    def __init__(self) -> None:
        super().__init__()
        self._options: list[str] = []
        self._option_rects: list[pygame.Rect] = []
        self._selected_index: int = 0
    
    @property
    def options(self) -> list[str]:
        """Get list of menu options. Override for dynamic options."""
        return self._options
    
    @property
    def selected_index(self) -> int:
        return self._selected_index
    
    @selected_index.setter
    def selected_index(self, value: int) -> None:
        self._selected_index = max(0, min(value, len(self.options) - 1))
    
    def handle_input(self, events: list, game_state: Any, ctx: dict) -> dict:
        """Handle menu navigation input."""
        from rendering.menu_helpers import handle_menu_navigation
        import pygame
        
        out = {"screen": None, "quit": False, "pop": False}
        
        # Handle navigation
        new_idx, confirmed, clicked_idx = handle_menu_navigation(
            events, len(self.options),
            self._selected_index,
            self._option_rects
        )
        self._selected_index = new_idx
        
        # Handle selection
        if confirmed or clicked_idx >= 0:
            selected = clicked_idx if clicked_idx >= 0 else self._selected_index
            result = self._on_option_selected(selected, game_state, ctx)
            if result:
                out.update(result)
                return out
        
        # Handle escape
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                escape_result = self._on_escape(game_state, ctx)
                if escape_result:
                    out.update(escape_result)
                return out
        
        return out
    
    def _on_option_selected(self, index: int, game_state: Any, ctx: dict) -> Optional[dict]:
        """Handle menu option selection. Override in subclass.
        
        Args:
            index: Selected option index
            game_state: Game state
            ctx: Context dict
            
        Returns:
            Dict with screen/pop/quit flags, or None to stay on menu
        """
        return None
    
    def _on_escape(self, game_state: Any, ctx: dict) -> Optional[dict]:
        """Handle escape key. Default: pop scene. Override for custom behavior."""
        return {"pop": True}
    
    def render_menu(
        self,
        render_ctx: Any,
        title: str,
        y_title: int,
        y_options: int,
        line_height: int = 45,
        show_instructions: bool = True,
        instructions: str = "UP/DOWN: Select | ENTER: Confirm | ESC: Back",
    ) -> None:
        """Render standard menu layout with title, options, and instructions.
        
        Stores option rects in self._option_rects for click detection.
        """
        from rendering import draw_centered_text
        from rendering.menu_helpers import render_menu_options, render_menu_title
        
        screen = render_ctx.screen
        w, h = render_ctx.width, render_ctx.height
        font, big_font = render_ctx.font, render_ctx.big_font
        
        # Title
        render_menu_title(screen, font, big_font, w, title, y_title)
        
        # Options
        self._option_rects = render_menu_options(
            screen, font, big_font, w, self.options,
            self._selected_index, y_options, line_height
        )
        
        # Instructions
        if show_instructions:
            draw_centered_text(screen, font, big_font, w, instructions, h - 60, (150, 150, 150))
    
    def on_enter(self, game_state: Any, ctx: dict) -> None:
        """Reset selection when entering menu."""
        self._selected_index = 0


class SceneStack:
    """
    Stack of scenes. The top scene is the current one; input/update/render go to current().
    Used for: gameplay -> pause (push) -> resume (pop); gameplay -> name input -> high scores (push/pop).
    """

    __slots__ = ("_stack",)

    def __init__(self) -> None:
        self._stack: list[Scene] = []

    def push(self, scene: Scene) -> None:
        self._stack.append(scene)

    def pop(self) -> Scene | None:
        if not self._stack:
            return None
        return self._stack.pop()

    def current(self) -> Scene | None:
        if not self._stack:
            return None
        return self._stack[-1]

    def clear(self) -> None:
        self._stack.clear()

    def __len__(self) -> int:
        return len(self._stack)
