"""Profile system for managing custom character profiles.

Supports saving and loading custom stat profiles with names.
Each profile stores HP, Speed, Damage, and Fire Rate multipliers.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

PROFILE_FILE_PATH = "profiles.json"
MAX_PROFILES = 10  # Maximum number of saved profiles


@dataclass
class CustomProfile:
    """A saved custom profile."""
    profile_id: int  # Unique ID for this profile
    name: str  # Player-chosen name for this profile
    hp_mult: float  # HP multiplier (0.5 - 3.0)
    speed_mult: float  # Speed multiplier (0.5 - 3.0)
    damage_mult: float  # Damage multiplier (0.5 - 3.0)
    firerate_mult: float  # Fire rate multiplier (0.5 - 3.0)
    timestamp: str  # ISO format datetime string when created/modified
    
    @classmethod
    def from_dict(cls, data: dict) -> "CustomProfile":
        return cls(
            profile_id=data.get("profile_id", 0),
            name=data.get("name", "Custom"),
            hp_mult=data.get("hp_mult", 1.0),
            speed_mult=data.get("speed_mult", 1.0),
            damage_mult=data.get("damage_mult", 1.0),
            firerate_mult=data.get("firerate_mult", 1.0),
            timestamp=data.get("timestamp", ""),
        )
    
    def to_stats_dict(self) -> dict:
        """Convert to the format used by game_state.custom_profile_stats."""
        return {
            "hp_mult": self.hp_mult,
            "speed_mult": self.speed_mult,
            "damage_mult": self.damage_mult,
            "firerate_mult": self.firerate_mult,
        }


def _get_profile_file_path() -> str:
    """Get the full path to the profile file."""
    return PROFILE_FILE_PATH


def load_profiles() -> list[CustomProfile]:
    """Load all saved profiles from disk. Returns list of CustomProfile."""
    profiles: list[CustomProfile] = []
    path = _get_profile_file_path()
    
    if not os.path.exists(path):
        return profiles
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, list):
            for profile_data in data:
                if isinstance(profile_data, dict):
                    profile = CustomProfile.from_dict(profile_data)
                    profiles.append(profile)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[ProfileSystem] Error loading profiles: {e}")
    
    return profiles


def _write_profiles(profiles: list[CustomProfile]) -> bool:
    """Write profiles to disk. Returns True on success."""
    path = _get_profile_file_path()
    
    # Convert to list of dicts
    data = [asdict(profile) for profile in profiles]
    
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except IOError as e:
        print(f"[ProfileSystem] Error writing profiles: {e}")
        return False


def _get_next_profile_id(profiles: list[CustomProfile]) -> int:
    """Get the next available profile ID."""
    if not profiles:
        return 0
    return max(p.profile_id for p in profiles) + 1


def save_profile(
    name: str,
    hp_mult: float,
    speed_mult: float,
    damage_mult: float,
    firerate_mult: float,
    profile_id: Optional[int] = None,
) -> bool:
    """Save a custom profile. If profile_id is provided, updates that profile; otherwise creates new.
    Returns True on success."""
    profiles = load_profiles()
    
    # Check if we're at max profiles (for new profile)
    if profile_id is None and len(profiles) >= MAX_PROFILES:
        print(f"[ProfileSystem] Maximum profiles ({MAX_PROFILES}) reached")
        return False
    
    new_profile = CustomProfile(
        profile_id=profile_id if profile_id is not None else _get_next_profile_id(profiles),
        name=name.strip() or "Custom Profile",
        hp_mult=round(hp_mult, 1),
        speed_mult=round(speed_mult, 1),
        damage_mult=round(damage_mult, 1),
        firerate_mult=round(firerate_mult, 1),
        timestamp=datetime.now().isoformat(),
    )
    
    if profile_id is not None:
        # Update existing profile
        for i, p in enumerate(profiles):
            if p.profile_id == profile_id:
                profiles[i] = new_profile
                break
        else:
            # ID not found, add as new
            profiles.append(new_profile)
    else:
        # Add new profile
        profiles.append(new_profile)
    
    return _write_profiles(profiles)


def delete_profile(profile_id: int) -> bool:
    """Delete the profile with the specified ID. Returns True on success."""
    profiles = load_profiles()
    
    for i, p in enumerate(profiles):
        if p.profile_id == profile_id:
            profiles.pop(i)
            return _write_profiles(profiles)
    
    return False  # Profile not found


def get_profile(profile_id: int) -> Optional[CustomProfile]:
    """Get a specific profile by ID. Returns None if not found."""
    profiles = load_profiles()
    for p in profiles:
        if p.profile_id == profile_id:
            return p
    return None


def get_profile_display_text(profile: CustomProfile) -> str:
    """Get display text for a profile (for menu rendering)."""
    return f"{profile.name} (HP:{profile.hp_mult:.1f}x Spd:{profile.speed_mult:.1f}x Dmg:{profile.damage_mult:.1f}x FR:{profile.firerate_mult:.1f}x)"


def get_profile_names() -> list[str]:
    """Get list of all saved profile names."""
    profiles = load_profiles()
    return [p.name for p in profiles]
