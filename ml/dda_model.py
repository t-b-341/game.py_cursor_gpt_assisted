"""Dynamic Difficulty Adjustment (DDA) neural network model.

Uses PyTorch to predict optimal difficulty parameters based on player performance.
Falls back gracefully if PyTorch is not installed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, TYPE_CHECKING

# Try to import PyTorch
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None

from .features import FEATURE_NAMES, extract_wave_features, FEATURE_NORMS

# Model file location
MODEL_DIR = Path(__file__).parent / "models"
DEFAULT_MODEL_PATH = MODEL_DIR / "dda_model.pt"


class DDAModel:
    """Dynamic Difficulty Adjustment predictor.
    
    Predicts optimal difficulty parameters for the next wave based on
    player performance in previous waves.
    
    Output parameters (all in range 0-1, scale to actual values):
    - hp_mult: Enemy HP multiplier (0.8 to 1.6)
    - speed_mult: Enemy speed multiplier (0.8 to 1.4)
    - spawn_mult: Spawn count multiplier (0.7 to 1.5)
    - projectile_speed: Projectile speed multiplier (0.8 to 1.3)
    """
    
    def __init__(self, model_path: Optional[Path] = None):
        """Initialize DDA model.
        
        Args:
            model_path: Path to saved model weights. If None, uses default.
        """
        self._model = None
        self._model_path = model_path or DEFAULT_MODEL_PATH
        self._fallback_mode = not TORCH_AVAILABLE
        
        if TORCH_AVAILABLE:
            self._model = self._create_model()
            if self._model_path.exists():
                self._load_model()
    
    def _create_model(self) -> "nn.Module":
        """Create the neural network architecture.
        
        Input: 14 features (combat_effectiveness, kills_per_second, etc.)
        Output: 4 difficulty parameters (hp_mult, speed_mult, spawn_mult, proj_speed)
        """
        if not TORCH_AVAILABLE:
            return None
        
        input_size = len(FEATURE_NAMES)  # 14 features
        return nn.Sequential(
            nn.Linear(input_size, 32),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 4),
            nn.Sigmoid(),  # Output in range [0, 1]
        )
    
    def _load_model(self) -> bool:
        """Load model weights from file."""
        if not TORCH_AVAILABLE or self._model is None:
            return False
        
        try:
            state_dict = torch.load(self._model_path, map_location="cpu")
            self._model.load_state_dict(state_dict)
            self._model.eval()
            return True
        except Exception as e:
            print(f"[DDA] Failed to load model: {e}")
            return False
    
    def save_model(self, path: Optional[Path] = None) -> bool:
        """Save model weights to file."""
        if not TORCH_AVAILABLE or self._model is None:
            return False
        
        save_path = path or self._model_path
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            torch.save(self._model.state_dict(), save_path)
            return True
        except Exception as e:
            print(f"[DDA] Failed to save model: {e}")
            return False
    
    def predict(self, wave_stats: dict) -> dict:
        """Predict optimal difficulty for next wave.
        
        Args:
            wave_stats: Dictionary with wave performance data
        
        Returns:
            Dictionary with difficulty parameters:
            - hp_mult: 0.8 to 1.6
            - speed_mult: 0.8 to 1.4
            - spawn_mult: 0.7 to 1.5
            - projectile_speed_mult: 0.8 to 1.3
        """
        if self._fallback_mode or self._model is None:
            return self._fallback_predict(wave_stats)
        
        # Extract features
        features = extract_wave_features(wave_stats)
        
        # Run inference
        with torch.no_grad():
            x = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
            output = self._model(x).squeeze(0).numpy()
        
        # Scale outputs to actual ranges
        return {
            "hp_mult": 0.8 + output[0] * 0.8,      # 0.8 to 1.6
            "speed_mult": 0.8 + output[1] * 0.6,   # 0.8 to 1.4
            "spawn_mult": 0.7 + output[2] * 0.8,   # 0.7 to 1.5
            "projectile_speed_mult": 0.8 + output[3] * 0.5,  # 0.8 to 1.3
        }
    
    def _fallback_predict(self, wave_stats: dict) -> dict:
        """Simple heuristic fallback when PyTorch not available."""
        outcome = wave_stats.get("outcome", "comfortable")
        hp_pct = wave_stats.get("player_hp_pct_end", 0.5) or 0.5
        
        # Simple heuristic based on outcome
        if outcome == "died" or hp_pct < 0.1:
            # Much easier
            return {
                "hp_mult": 0.85,
                "speed_mult": 0.85,
                "spawn_mult": 0.8,
                "projectile_speed_mult": 0.85,
            }
        elif outcome == "struggled" or hp_pct < 0.3:
            # Easier
            return {
                "hp_mult": 0.95,
                "speed_mult": 0.95,
                "spawn_mult": 0.9,
                "projectile_speed_mult": 0.95,
            }
        elif outcome == "dominated" or hp_pct > 0.9:
            # Harder
            return {
                "hp_mult": 1.2,
                "speed_mult": 1.15,
                "spawn_mult": 1.2,
                "projectile_speed_mult": 1.1,
            }
        elif outcome == "comfortable" or hp_pct > 0.7:
            # Slightly harder
            return {
                "hp_mult": 1.1,
                "speed_mult": 1.05,
                "spawn_mult": 1.05,
                "projectile_speed_mult": 1.0,
            }
        else:
            # Maintain current difficulty
            return {
                "hp_mult": 1.0,
                "speed_mult": 1.0,
                "spawn_mult": 1.0,
                "projectile_speed_mult": 1.0,
            }
    
    def get_model(self) -> Optional["nn.Module"]:
        """Get the underlying PyTorch model (for training)."""
        return self._model
    
    @property
    def is_trained(self) -> bool:
        """Check if model has been trained (weights file exists)."""
        return self._model_path.exists()
    
    @property
    def is_fallback(self) -> bool:
        """Check if using fallback heuristic mode."""
        return self._fallback_mode


def get_dda_model() -> DDAModel:
    """Get or create the singleton DDA model instance."""
    global _dda_model
    if "_dda_model" not in globals() or _dda_model is None:
        _dda_model = DDAModel()
    return _dda_model

_dda_model: Optional[DDAModel] = None
