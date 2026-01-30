"""Engine package: core game loop infrastructure."""
from .input_loop import (
    poll_events,
    handle_global_events,
    handle_scene_events,
    handle_debug_keys,
    process_scene_transition,
)
from .run_manager import (
    RunManager,
    get_run_manager,
    start_new_run,
    restart_current_wave,
    restart_from_wave_one,
    replay,
    try_again,
    load_game,
)

__all__ = [
    # Input loop
    "poll_events",
    "handle_global_events",
    "handle_scene_events",
    "handle_debug_keys",
    "process_scene_transition",
    # Run manager
    "RunManager",
    "get_run_manager",
    "start_new_run",
    "restart_current_wave",
    "restart_from_wave_one",
    "replay",
    "try_again",
    "load_game",
]
