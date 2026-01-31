"""Spawning system package.

This package contains:
- Core wave management (in main spawn_system module)
- Custom map spawning (in map_spawn module)

For backward compatibility, import from systems.spawn_system directly.
"""

from .map_spawn import spawn_enemies_from_map, start_wave_from_map

__all__ = [
    "spawn_enemies_from_map",
    "start_wave_from_map",
]
