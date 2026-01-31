"""
Enemy module - behavior, AI, movement, and factory functions.

This package contains:
- movement.py: Enemy collision and movement
- ai.py: Threat detection and evasion
- factory.py: Enemy creation and telemetry logging
"""
from .movement import move_enemy_with_push_cached
from .ai import find_nearest_threat, find_threats_in_dodge_range
from .factory import make_enemy_from_template, log_enemy_spawns

__all__ = [
    "move_enemy_with_push_cached",
    "find_nearest_threat",
    "find_threats_in_dodge_range",
    "make_enemy_from_template",
    "log_enemy_spawns",
]
