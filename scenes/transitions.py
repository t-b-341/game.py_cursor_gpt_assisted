"""
Explicit scene transition type for a scene-driven main loop.

Scenes may eventually return SceneTransition from handle_input/update instead of
a transition dict. For now, transition-returning methods are stubs used only in tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .base import Scene, SceneStack
    from state import GameState


# Kind names for SceneTransition.kind
KIND_NONE = "NONE"
KIND_PUSH = "PUSH"
KIND_POP = "POP"
KIND_REPLACE = "REPLACE"
KIND_QUIT_GAME = "QUIT_GAME"


@dataclass(frozen=True)
class SceneTransition:
    """Lightweight descriptor for a requested scene transition.

    kind: one of NONE, PUSH, POP, REPLACE, QUIT_GAME.
    scene_name: optional; used when kind is PUSH or REPLACE (e.g. "PAUSED", "MENU").
    """
    kind: str
    scene_name: Optional[str] = None

    @classmethod
    def none(cls) -> "SceneTransition":
        return cls(kind=KIND_NONE)

    @classmethod
    def push(cls, scene_name: str) -> "SceneTransition":
        return cls(kind=KIND_PUSH, scene_name=scene_name)

    @classmethod
    def pop(cls) -> "SceneTransition":
        return cls(kind=KIND_POP)

    @classmethod
    def replace(cls, scene_name: str) -> "SceneTransition":
        return cls(kind=KIND_REPLACE, scene_name=scene_name)

    @classmethod
    def quit_game(cls) -> "SceneTransition":
        return cls(kind=KIND_QUIT_GAME)


# State constants (imported here to avoid circular imports in game.py)
STATE_PLAYING = "PLAYING"
STATE_ENDURANCE = "ENDURANCE"
STATE_PAUSED = "PAUSED"
STATE_MENU = "MENU"
STATE_TITLE = "TITLE"
STATE_NAME_INPUT = "NAME_INPUT"
STATE_HIGH_SCORES = "HIGH_SCORES"
STATE_GAME_OVER = "GAME_OVER"
STATE_VICTORY = "VICTORY"
STATE_SAVE_GAME = "SAVE_GAME"
STATE_LOAD_GAME = "LOAD_GAME"
STATE_QUICK_LAUNCH = "QUICK_LAUNCH"


def create_scene_for_state(scene_name: str) -> "Scene | None":
    """Create a Scene instance for the given state name.
    
    Returns None if the scene_name is not recognized.
    """
    # Lazy imports to avoid circular dependencies
    from .gameplay import GameplayScene
    from .pause import PauseScene
    from .options import OptionsScene
    from .quick_launch import QuickLaunchScene
    from .title import TitleScene
    from .name_input import NameInputScene
    from .high_scores import HighScoreScene
    from .game_over import GameOverScene
    from .victory import VictoryScene
    from .save_game import SaveGameScene
    from .load_game import LoadGameScene
    from .shader_test import ShaderTestScene
    from .shader_settings import ShaderSettingsScreen

    scene_map = {
        STATE_PAUSED: lambda: PauseScene(),
        STATE_MENU: lambda: OptionsScene(),
        STATE_QUICK_LAUNCH: lambda: QuickLaunchScene(),
        STATE_TITLE: lambda: TitleScene(),
        STATE_NAME_INPUT: lambda: NameInputScene(),
        STATE_HIGH_SCORES: lambda: HighScoreScene(),
        STATE_GAME_OVER: lambda: GameOverScene(),
        STATE_VICTORY: lambda: VictoryScene(),
        STATE_SAVE_GAME: lambda: SaveGameScene(),
        STATE_LOAD_GAME: lambda: LoadGameScene(),
        STATE_PLAYING: lambda: GameplayScene(STATE_PLAYING),
        STATE_ENDURANCE: lambda: GameplayScene(STATE_ENDURANCE),
        "SHADER_TEST": lambda: ShaderTestScene(),
        "SHADER_SETTINGS": lambda: ShaderSettingsScreen(),
    }
    
    factory = scene_map.get(scene_name)
    return factory() if factory else None


def apply_scene_transition(
    transition: SceneTransition,
    scene_stack: "SceneStack",
    game_state: "GameState",
) -> bool:
    """Apply a SceneTransition to the scene stack and game state.
    
    Returns True if the transition should cause the loop to exit (QUIT_GAME).
    For PUSH/REPLACE, scene_name should be a state constant like STATE_PAUSED, STATE_MENU, etc.
    """
    if transition.kind == KIND_NONE:
        return False
    
    if transition.kind == KIND_QUIT_GAME:
        return True
    
    if transition.kind == KIND_POP:
        scene_stack.pop()
        state = game_state.previous_screen or STATE_PLAYING
        game_state.current_screen = state
        return False
    
    if transition.kind == KIND_PUSH:
        scene = create_scene_for_state(transition.scene_name)
        if scene:
            scene_stack.push(scene)
        if transition.scene_name:
            game_state.current_screen = transition.scene_name
        return False
    
    if transition.kind == KIND_REPLACE:
        scene_stack.clear()
        scene = create_scene_for_state(transition.scene_name)
        if scene:
            scene_stack.push(scene)
        if transition.scene_name:
            game_state.current_screen = transition.scene_name
        return False
    
    return False
