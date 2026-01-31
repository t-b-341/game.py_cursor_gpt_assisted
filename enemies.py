"""Enemy behavior and helper functions.

This module re-exports functions from the enemies package for backwards compatibility.
New code should import directly from the submodules:
- enemies.movement: move_enemy_with_push_cached
- enemies.ai: find_nearest_threat, find_threats_in_dodge_range
- enemies.factory: make_enemy_from_template, log_enemy_spawns
"""
from enemies import (
    move_enemy_with_push_cached,
    find_nearest_threat,
    find_threats_in_dodge_range,
    make_enemy_from_template,
    log_enemy_spawns,
)

__all__ = [
    "move_enemy_with_push_cached",
    "find_nearest_threat",
    "find_threats_in_dodge_range",
    "make_enemy_from_template",
    "log_enemy_spawns",
]
