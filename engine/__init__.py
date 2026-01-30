"""Engine package: core game loop infrastructure."""
from .input_loop import (
    poll_events,
    handle_global_events,
    handle_scene_events,
    handle_debug_keys,
    process_scene_transition,
)

__all__ = [
    "poll_events",
    "handle_global_events",
    "handle_scene_events",
    "handle_debug_keys",
    "process_scene_transition",
]
