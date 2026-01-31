"""Machine Learning module for Dynamic Difficulty Adjustment (DDA).

This module provides:
- Wave summary tracking and logging
- Feature extraction from telemetry data
- DDA model architecture (PyTorch)
- Training utilities
- Real-time inference for difficulty adjustment

Requires: torch (optional, only for training/inference)

Quick Start:
    from ml import dda
    
    # Track wave events
    dda.on_wave_start(state, wave_num, hp_scale, speed_scale, enemies)
    dda.on_shot_fired()
    dda.on_enemy_killed()
    
    # Get difficulty for next wave
    adjustment = dda.on_wave_end(state, telemetry)
    # adjustment = {"hp_mult": 1.1, "speed_mult": 1.05, ...}
"""

from .wave_tracker import WaveTracker, calculate_outcome
from .features import extract_wave_features, FEATURE_NAMES
from .dda_integration import DDAIntegration, get_dda, dda

__all__ = [
    "WaveTracker",
    "calculate_outcome",
    "extract_wave_features",
    "FEATURE_NAMES",
    "DDAIntegration",
    "get_dda",
    "dda",
]
