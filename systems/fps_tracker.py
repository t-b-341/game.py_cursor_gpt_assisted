"""Real-time FPS tracker with rolling average and graph data.

Stores frame times for the last N seconds and provides:
- Current FPS
- Rolling average FPS
- Frame time history for graph rendering
"""
from __future__ import annotations

from collections import deque
from typing import List, Tuple

# Configuration
HISTORY_DURATION_S = 3.0  # Keep 3 seconds of history
MAX_SAMPLES = 300  # Max samples to store (at 60fps = 5 seconds, plenty of headroom)

# Frame time storage: (timestamp, dt) pairs
_frame_history: deque[Tuple[float, float]] = deque(maxlen=MAX_SAMPLES)
_current_time: float = 0.0


def record_frame(dt: float, game_time: float) -> None:
    """Record a frame's delta time.
    
    Args:
        dt: Frame delta time in seconds
        game_time: Current game time in seconds
    """
    global _current_time
    _current_time = game_time
    _frame_history.append((game_time, dt))
    
    # Prune old entries beyond HISTORY_DURATION_S
    cutoff = game_time - HISTORY_DURATION_S
    while _frame_history and _frame_history[0][0] < cutoff:
        _frame_history.popleft()


def get_current_fps() -> float:
    """Get instantaneous FPS from most recent frame."""
    if not _frame_history:
        return 0.0
    _, dt = _frame_history[-1]
    return 1.0 / dt if dt > 0 else 0.0


def get_average_fps() -> float:
    """Get average FPS over the history window."""
    if not _frame_history:
        return 0.0
    
    total_dt = sum(dt for _, dt in _frame_history)
    if total_dt <= 0:
        return 0.0
    
    return len(_frame_history) / total_dt


def get_fps_history(num_samples: int = 60) -> List[float]:
    """Get recent FPS values for graphing.
    
    Args:
        num_samples: Number of samples to return (evenly spaced from history)
    
    Returns:
        List of FPS values, oldest first
    """
    if not _frame_history:
        return []
    
    # Convert frame times to FPS values
    fps_values = [1.0 / dt if dt > 0 else 0.0 for _, dt in _frame_history]
    
    # If we have fewer samples than requested, return all
    if len(fps_values) <= num_samples:
        return fps_values
    
    # Downsample evenly
    step = len(fps_values) / num_samples
    result = []
    for i in range(num_samples):
        idx = int(i * step)
        result.append(fps_values[idx])
    
    return result


def get_stats() -> dict:
    """Get comprehensive FPS statistics.
    
    Returns:
        Dict with: current_fps, avg_fps, min_fps, max_fps, frame_count
    """
    if not _frame_history:
        return {
            "current_fps": 0.0,
            "avg_fps": 0.0,
            "min_fps": 0.0,
            "max_fps": 0.0,
            "frame_count": 0,
        }
    
    fps_values = [1.0 / dt if dt > 0 else 0.0 for _, dt in _frame_history]
    
    return {
        "current_fps": fps_values[-1] if fps_values else 0.0,
        "avg_fps": get_average_fps(),
        "min_fps": min(fps_values) if fps_values else 0.0,
        "max_fps": max(fps_values) if fps_values else 0.0,
        "frame_count": len(_frame_history),
    }


def clear() -> None:
    """Clear all stored frame data."""
    _frame_history.clear()
