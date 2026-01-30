"""Per-system performance timing for debugging frame drops.

Usage:
    from systems.perf_timing import perf_timer, get_timing_stats, reset_timings

    with perf_timer("collision_system"):
        # do collision work
        pass
    
    # At end of frame or periodically:
    stats = get_timing_stats()
    # stats = {"collision_system": {"total_ms": 5.2, "calls": 60, "avg_ms": 0.087}, ...}

Enable/disable via GAME_PERF_TIMING=1 environment variable.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Generator

# Enable via environment variable (default: disabled for zero overhead in production)
_ENABLED = os.environ.get("GAME_PERF_TIMING", "0").strip() == "1"

# Timing data: system_name -> {"total_ns": int, "calls": int}
_timings: dict[str, dict] = defaultdict(lambda: {"total_ns": 0, "calls": 0})

# Per-frame timings for current frame
_frame_timings: dict[str, float] = {}


def is_enabled() -> bool:
    """Check if performance timing is enabled."""
    return _ENABLED


def enable() -> None:
    """Enable performance timing at runtime."""
    global _ENABLED
    _ENABLED = True


def disable() -> None:
    """Disable performance timing at runtime."""
    global _ENABLED
    _ENABLED = False


@contextmanager
def perf_timer(system_name: str) -> Generator[None, None, None]:
    """Context manager for timing a system.
    
    Args:
        system_name: Name of the system being timed (e.g., "collision", "rendering")
    """
    if not _ENABLED:
        yield
        return
    
    start = time.perf_counter_ns()
    try:
        yield
    finally:
        elapsed_ns = time.perf_counter_ns() - start
        _timings[system_name]["total_ns"] += elapsed_ns
        _timings[system_name]["calls"] += 1
        _frame_timings[system_name] = elapsed_ns / 1_000_000  # Convert to ms


def get_timing_stats() -> dict[str, dict]:
    """Get accumulated timing statistics for all systems.
    
    Returns:
        Dict mapping system name to {"total_ms": float, "calls": int, "avg_ms": float}
    """
    result = {}
    for name, data in _timings.items():
        total_ms = data["total_ns"] / 1_000_000
        calls = data["calls"]
        avg_ms = total_ms / calls if calls > 0 else 0.0
        result[name] = {
            "total_ms": round(total_ms, 2),
            "calls": calls,
            "avg_ms": round(avg_ms, 4),
        }
    return result


def get_frame_timings() -> dict[str, float]:
    """Get timing data for the current frame only.
    
    Returns:
        Dict mapping system name to time in milliseconds for this frame
    """
    return dict(_frame_timings)


def clear_frame_timings() -> None:
    """Clear per-frame timing data (call at start of each frame)."""
    _frame_timings.clear()


def reset_timings() -> None:
    """Reset all accumulated timing data."""
    _timings.clear()
    _frame_timings.clear()


def get_slowest_systems(top_n: int = 5) -> list[tuple[str, float]]:
    """Get the N slowest systems by average time.
    
    Returns:
        List of (system_name, avg_ms) tuples, sorted by avg_ms descending
    """
    stats = get_timing_stats()
    sorted_systems = sorted(
        [(name, data["avg_ms"]) for name, data in stats.items()],
        key=lambda x: x[1],
        reverse=True
    )
    return sorted_systems[:top_n]


def format_timing_report() -> str:
    """Format a human-readable timing report.
    
    Returns:
        Multi-line string with timing statistics
    """
    stats = get_timing_stats()
    if not stats:
        return "No timing data collected."
    
    lines = ["System Timing Report", "=" * 50]
    
    # Sort by total time
    sorted_stats = sorted(
        stats.items(),
        key=lambda x: x[1]["total_ms"],
        reverse=True
    )
    
    for name, data in sorted_stats:
        lines.append(
            f"{name:25} | Total: {data['total_ms']:8.2f}ms | "
            f"Calls: {data['calls']:6} | Avg: {data['avg_ms']:6.4f}ms"
        )
    
    return "\n".join(lines)
