"""Shared file operation utilities with consistent error handling.

Provides:
- safe_read_json: Read JSON files with error handling
- safe_write_json: Write JSON files with error handling
- ensure_directory: Create directory if it doesn't exist

All functions use the centralized logging system.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, TypeVar, Callable

from game_logging import get_logger

_log = get_logger(__name__)

T = TypeVar("T")


def safe_read_json(
    filepath: Path | str,
    default: T = None,
    *,
    log_not_found: bool = True,
) -> T | dict[str, Any]:
    """Read a JSON file with error handling.
    
    Args:
        filepath: Path to the JSON file
        default: Value to return if file doesn't exist or is invalid
        log_not_found: Whether to log a warning when file not found
        
    Returns:
        Parsed JSON data, or default if reading fails
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        if log_not_found:
            _log.warning(f"File not found: {filepath}")
        return default
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        _log.error(f"Invalid JSON in {filepath}: {e}")
        return default
    except OSError as e:
        _log.error(f"Error reading {filepath}: {e}")
        return default


def safe_write_json(
    filepath: Path | str,
    data: Any,
    *,
    indent: int = 2,
    ensure_dir: bool = True,
) -> bool:
    """Write data to a JSON file with error handling.
    
    Args:
        filepath: Path to the JSON file
        data: Data to serialize as JSON
        indent: JSON indentation (default 2)
        ensure_dir: Create parent directory if it doesn't exist
        
    Returns:
        True if write succeeded, False otherwise
    """
    filepath = Path(filepath)
    
    if ensure_dir:
        filepath.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent)
        _log.debug(f"Saved: {filepath}")
        return True
    except OSError as e:
        _log.error(f"Error writing {filepath}: {e}")
        return False
    except (TypeError, ValueError) as e:
        _log.error(f"Error serializing data for {filepath}: {e}")
        return False


def ensure_directory(path: Path | str) -> bool:
    """Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Path to the directory
        
    Returns:
        True if directory exists or was created, False on error
    """
    path = Path(path)
    
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError as e:
        _log.error(f"Error creating directory {path}: {e}")
        return False


def safe_file_operation(
    operation: Callable[[], T],
    default: T = None,
    *,
    description: str = "file operation",
) -> T:
    """Execute a file operation with error handling.
    
    Args:
        operation: Callable to execute
        default: Value to return on error
        description: Description for error messages
        
    Returns:
        Result of operation, or default on error
    """
    try:
        return operation()
    except OSError as e:
        _log.error(f"Error during {description}: {e}")
        return default
    except Exception as e:
        _log.error(f"Unexpected error during {description}: {e}")
        return default
