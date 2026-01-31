"""Shared threading utilities and pool management.

Provides centralized thread pool management to avoid creating
too many executor instances across the codebase.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional


# Global thread pool for I/O operations (file loading, saving, etc.)
_io_executor: Optional[ThreadPoolExecutor] = None
_io_lock = threading.Lock()

# Global thread pool for CPU-bound operations (pathfinding, etc.)
_compute_executor: Optional[ThreadPoolExecutor] = None
_compute_lock = threading.Lock()


def get_io_executor(max_workers: int = 2) -> ThreadPoolExecutor:
    """Get the shared I/O thread pool for file operations.
    
    Used for:
    - Map loading/saving
    - Asset preloading
    - Telemetry writes
    """
    global _io_executor
    with _io_lock:
        if _io_executor is None:
            _io_executor = ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix="io"
            )
        return _io_executor


def get_compute_executor(max_workers: int = 4) -> ThreadPoolExecutor:
    """Get the shared compute thread pool for CPU-bound operations.
    
    Used for:
    - Pathfinding
    - Other CPU-intensive calculations
    """
    global _compute_executor
    with _compute_lock:
        if _compute_executor is None:
            _compute_executor = ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix="compute"
            )
        return _compute_executor


def shutdown_all_executors(wait: bool = False) -> None:
    """Shutdown all shared thread pools.
    
    Call this during application cleanup.
    
    Args:
        wait: If True, wait for pending tasks to complete
    """
    global _io_executor, _compute_executor
    
    with _io_lock:
        if _io_executor is not None:
            _io_executor.shutdown(wait=wait)
            _io_executor = None
    
    with _compute_lock:
        if _compute_executor is not None:
            _compute_executor.shutdown(wait=wait)
            _compute_executor = None


def submit_io_task(fn, *args, **kwargs):
    """Submit a task to the I/O thread pool.
    
    Returns a Future that can be awaited or checked with .done()
    """
    return get_io_executor().submit(fn, *args, **kwargs)


def submit_compute_task(fn, *args, **kwargs):
    """Submit a task to the compute thread pool.
    
    Returns a Future that can be awaited or checked with .done()
    """
    return get_compute_executor().submit(fn, *args, **kwargs)
