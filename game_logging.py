"""Centralized logging configuration for the game.

Usage:
    from game_logging import get_logger
    
    logger = get_logger(__name__)
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")

Log levels can be controlled via environment variables:
    GAME_LOG_LEVEL=DEBUG  # Show all messages
    GAME_LOG_LEVEL=INFO   # Show info and above (default)
    GAME_LOG_LEVEL=WARNING # Show warnings and errors only
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Optional

# Module-level flag to track if logging has been configured
_logging_configured = False

# Default format with category tags
LOG_FORMAT = "[%(name)s] %(message)s"
LOG_FORMAT_DEBUG = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"


def configure_logging(
    level: Optional[str] = None,
    debug_mode: bool = False,
) -> None:
    """Configure logging for the game.
    
    Call once at startup (e.g., in game.py before other imports).
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Default from env or INFO.
        debug_mode: If True, use verbose format with timestamps.
    """
    global _logging_configured
    
    if _logging_configured:
        return
    
    # Get level from argument, environment, or default
    if level is None:
        level = os.environ.get("GAME_LOG_LEVEL", "INFO")
    
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Choose format based on debug mode
    log_format = LOG_FORMAT_DEBUG if debug_mode else LOG_FORMAT
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        stream=sys.stdout,
        force=True,  # Override any existing config
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger("pygame").setLevel(logging.WARNING)
    logging.getLogger("OpenGL").setLevel(logging.WARNING)
    
    _logging_configured = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger for the given module name.
    
    Args:
        name: Usually __name__ from the calling module
        
    Returns:
        Configured Logger instance
    """
    # Auto-configure with defaults if not already done
    if not _logging_configured:
        configure_logging()
    
    # Shorten common prefixes for cleaner output
    short_name = name
    for prefix in ("systems.", "rendering.", "scenes.", "maps.", "engine."):
        if name.startswith(prefix):
            short_name = name.replace(prefix, "", 1)
            break
    
    return logging.getLogger(short_name)
