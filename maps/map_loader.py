"""Map loading functionality."""
import json
from pathlib import Path
from typing import Optional

from game_logging import get_logger

from .map_grid import MapGrid
from .map_saver import get_maps_data_dir

_log = get_logger(__name__)

# Re-export for convenience
__all__ = ["load_map", "map_exists", "get_maps_data_dir"]


def load_map(filename: str) -> Optional[MapGrid]:
    """Load a map from JSON file.
    
    Args:
        filename: Filename (with or without .json extension)
        
    Returns:
        MapGrid instance, or None if loading failed
    """
    try:
        data_dir = get_maps_data_dir()
        
        # Ensure .json extension
        if not filename.endswith(".json"):
            filename = f"{filename}.json"
        
        filepath = data_dir / filename
        
        if not filepath.exists():
            _log.warning(f"Map file not found: {filepath}")
            return None
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return MapGrid.from_dict(data)
    except Exception as e:
        _log.error(f"Error loading map: {e}")
        return None


def map_exists(filename: str) -> bool:
    """Check if a map file exists.
    
    Args:
        filename: Filename (with or without .json extension)
        
    Returns:
        True if map file exists
    """
    data_dir = get_maps_data_dir()
    
    if not filename.endswith(".json"):
        filename = f"{filename}.json"
    
    return (data_dir / filename).exists()
