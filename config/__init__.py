"""Game configuration. GameConfig holds difficulty, player class, options toggles, feel, juice."""
from .game_config import (
    GameConfig,
    apply_feel_profile,
    apply_safe_mode,
    log_startup_config,
    FEEL_PROFILE_ARCADE,
    FEEL_PROFILE_CASUAL,
    FEEL_PROFILES,
)

__all__ = [
    "GameConfig",
    "apply_feel_profile",
    "apply_safe_mode",
    "log_startup_config",
    "FEEL_PROFILE_ARCADE",
    "FEEL_PROFILE_CASUAL",
    "FEEL_PROFILES",
]
