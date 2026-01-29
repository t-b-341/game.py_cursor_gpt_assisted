"""Scenes: gameplay, pause, high scores, name input, shader test, title, options, game over, save/load, quick launch. Driven by SceneStack in the game loop."""
from .base import Scene, SceneStack
from .gameplay import GameplayScene
from .high_scores import HighScoreScene
from .name_input import NameInputScene
from .options import OptionsScene
from .pause import PauseScene
from .shader_test import ShaderTestScene
from .shader_settings import ShaderSettingsScreen
from .title import TitleScene
from .game_over import GameOverScene
from .save_game import SaveGameScene
from .load_game import LoadGameScene
from .quick_launch import QuickLaunchScene
from .transitions import SceneTransition

__all__ = [
    "Scene",
    "SceneStack",
    "SceneTransition",
    "GameplayScene",
    "PauseScene",
    "HighScoreScene",
    "NameInputScene",
    "OptionsScene",
    "ShaderTestScene",
    "ShaderSettingsScreen",
    "TitleScene",
    "GameOverScene",
    "SaveGameScene",
    "LoadGameScene",
    "QuickLaunchScene",
]
