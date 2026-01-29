"""Save system for managing game save slots.

Supports 3 save slots, each storing:
- Player-chosen name for the save
- Last completed wave number (player restarts from the next wave)
- Difficulty, player class, and other config
- Timestamp when saved
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

SAVE_FILE_PATH = "saves.json"
MAX_SAVE_SLOTS = 3


@dataclass
class SaveSlot:
    """A single save slot."""
    slot_id: int  # 0, 1, or 2
    name: str  # Player-chosen name for this save
    wave_number: int  # Last completed wave (player starts from wave_number + 1, or wave_number if they want to retry)
    difficulty: str  # EASY, NORMAL, HARD
    player_class: str  # BALANCED, TANK, SPEEDSTER, SNIPER
    score: int  # Score at time of save
    timestamp: str  # ISO format datetime string
    
    @classmethod
    def from_dict(cls, data: dict) -> "SaveSlot":
        return cls(
            slot_id=data.get("slot_id", 0),
            name=data.get("name", ""),
            wave_number=data.get("wave_number", 1),
            difficulty=data.get("difficulty", "NORMAL"),
            player_class=data.get("player_class", "BALANCED"),
            score=data.get("score", 0),
            timestamp=data.get("timestamp", ""),
        )


def _get_save_file_path() -> str:
    """Get the full path to the save file."""
    return SAVE_FILE_PATH


def load_saves() -> dict[int, Optional[SaveSlot]]:
    """Load all save slots from disk. Returns dict mapping slot_id (0-2) to SaveSlot or None."""
    saves: dict[int, Optional[SaveSlot]] = {0: None, 1: None, 2: None}
    path = _get_save_file_path()
    
    if not os.path.exists(path):
        return saves
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, list):
            for slot_data in data:
                if isinstance(slot_data, dict):
                    slot = SaveSlot.from_dict(slot_data)
                    if 0 <= slot.slot_id < MAX_SAVE_SLOTS:
                        saves[slot.slot_id] = slot
    except (json.JSONDecodeError, IOError) as e:
        print(f"[SaveSystem] Error loading saves: {e}")
    
    return saves


def _write_saves(saves: dict[int, Optional[SaveSlot]]) -> bool:
    """Write save slots to disk. Returns True on success."""
    path = _get_save_file_path()
    
    # Convert to list of dicts, filtering out None slots
    data = [asdict(slot) for slot in saves.values() if slot is not None]
    
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except IOError as e:
        print(f"[SaveSystem] Error writing saves: {e}")
        return False


def save_game(
    slot_id: int,
    name: str,
    wave_number: int,
    difficulty: str,
    player_class: str,
    score: int,
) -> bool:
    """Save game to the specified slot. Returns True on success."""
    if not 0 <= slot_id < MAX_SAVE_SLOTS:
        print(f"[SaveSystem] Invalid slot_id: {slot_id}")
        return False
    
    saves = load_saves()
    
    saves[slot_id] = SaveSlot(
        slot_id=slot_id,
        name=name.strip() or f"Save {slot_id + 1}",
        wave_number=wave_number,
        difficulty=difficulty,
        player_class=player_class,
        score=score,
        timestamp=datetime.now().isoformat(),
    )
    
    return _write_saves(saves)


def delete_save(slot_id: int) -> bool:
    """Delete the save in the specified slot. Returns True on success."""
    if not 0 <= slot_id < MAX_SAVE_SLOTS:
        return False
    
    saves = load_saves()
    saves[slot_id] = None
    return _write_saves(saves)


def get_save_slot(slot_id: int) -> Optional[SaveSlot]:
    """Get a specific save slot. Returns None if slot is empty or invalid."""
    if not 0 <= slot_id < MAX_SAVE_SLOTS:
        return None
    saves = load_saves()
    return saves.get(slot_id)


def get_save_display_text(slot: Optional[SaveSlot]) -> str:
    """Get display text for a save slot (for menu rendering)."""
    if slot is None:
        return "[Empty Slot]"
    
    # Parse timestamp for display
    try:
        dt = datetime.fromisoformat(slot.timestamp)
        date_str = dt.strftime("%m/%d/%Y %H:%M")
    except (ValueError, TypeError):
        date_str = "Unknown"
    
    return f"{slot.name} - Wave {slot.wave_number} ({slot.difficulty}) - {date_str}"
