"""Map saving functionality."""
import json
import os
from pathlib import Path

from .map_grid import MapGrid


def get_maps_data_dir() -> Path:
    """Get the maps/data directory path, creating it if needed.
    
    Returns:
        Path to the maps/data directory
    """
    # Get the directory where this module is located
    maps_dir = Path(__file__).parent
    data_dir = maps_dir / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


def save_map(map_grid: MapGrid, filename: str) -> bool:
    """Save a map to JSON file.
    
    Args:
        map_grid: The MapGrid to save
        filename: Filename (with or without .json extension)
        
    Returns:
        True if save was successful, False otherwise
    """
    try:
        data_dir = get_maps_data_dir()
        
        # Ensure .json extension
        if not filename.endswith(".json"):
            filename = f"{filename}.json"
        
        filepath = data_dir / filename
        
        # Convert to dict and save
        data = map_grid.to_dict()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        
        return True
    except Exception as e:
        print(f"[maps] Error saving map: {e}")
        return False


def list_saved_maps() -> list[str]:
    """List all saved map files.
    
    Returns:
        List of map filenames (without .json extension)
    """
    try:
        data_dir = get_maps_data_dir()
        maps = []
        for file in data_dir.glob("*.json"):
            maps.append(file.stem)
        return sorted(maps)
    except Exception:
        return []
