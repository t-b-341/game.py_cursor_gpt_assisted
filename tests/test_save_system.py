"""Tests for save_system.py - save slot management."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import patch

import pytest

from save_system import (
    SaveSlot,
    load_saves,
    save_game,
    delete_save,
    get_save_slot,
    get_save_display_text,
    MAX_SAVE_SLOTS,
    _write_saves,
)


class TestSaveSlot:
    """Tests for SaveSlot dataclass."""
    
    def test_save_slot_creation(self):
        """SaveSlot can be created with all fields."""
        slot = SaveSlot(
            slot_id=0,
            name="Test Save",
            wave_number=5,
            difficulty="NORMAL",
            player_class="BALANCED",
            score=1000,
            timestamp="2024-01-15T10:30:00",
        )
        assert slot.slot_id == 0
        assert slot.name == "Test Save"
        assert slot.wave_number == 5
        assert slot.difficulty == "NORMAL"
        assert slot.player_class == "BALANCED"
        assert slot.score == 1000
        assert slot.timestamp == "2024-01-15T10:30:00"
    
    def test_from_dict_complete(self):
        """SaveSlot.from_dict works with complete data."""
        data = {
            "slot_id": 1,
            "name": "My Save",
            "wave_number": 10,
            "difficulty": "HARD",
            "player_class": "TANK",
            "score": 5000,
            "timestamp": "2024-01-20T15:00:00",
        }
        slot = SaveSlot.from_dict(data)
        assert slot.slot_id == 1
        assert slot.name == "My Save"
        assert slot.wave_number == 10
        assert slot.difficulty == "HARD"
        assert slot.player_class == "TANK"
        assert slot.score == 5000
    
    def test_from_dict_defaults(self):
        """SaveSlot.from_dict uses defaults for missing fields."""
        slot = SaveSlot.from_dict({})
        assert slot.slot_id == 0
        assert slot.name == ""
        assert slot.wave_number == 1
        assert slot.difficulty == "NORMAL"
        assert slot.player_class == "BALANCED"
        assert slot.score == 0
        assert slot.timestamp == ""


class TestLoadSaves:
    """Tests for load_saves function."""
    
    def test_load_saves_file_not_exists(self):
        """load_saves returns empty slots when file doesn't exist."""
        with patch("save_system._get_save_file_path", return_value="/nonexistent/path.json"):
            saves = load_saves()
        
        assert len(saves) == 3
        assert saves[0] is None
        assert saves[1] is None
        assert saves[2] is None
    
    def test_load_saves_valid_file(self):
        """load_saves correctly loads valid save data."""
        save_data = [
            {"slot_id": 0, "name": "Save 1", "wave_number": 3, "difficulty": "EASY", 
             "player_class": "SPEEDSTER", "score": 500, "timestamp": "2024-01-01T00:00:00"},
            {"slot_id": 2, "name": "Save 3", "wave_number": 7, "difficulty": "HARD",
             "player_class": "SNIPER", "score": 2000, "timestamp": "2024-02-01T12:00:00"},
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(save_data, f)
            temp_path = f.name
        
        try:
            with patch("save_system._get_save_file_path", return_value=temp_path):
                saves = load_saves()
            
            assert saves[0] is not None
            assert saves[0].name == "Save 1"
            assert saves[0].wave_number == 3
            
            assert saves[1] is None  # Slot 1 was not in the file
            
            assert saves[2] is not None
            assert saves[2].name == "Save 3"
            assert saves[2].difficulty == "HARD"
        finally:
            os.unlink(temp_path)
    
    def test_load_saves_invalid_json(self):
        """load_saves handles corrupted JSON gracefully."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            temp_path = f.name
        
        try:
            with patch("save_system._get_save_file_path", return_value=temp_path):
                saves = load_saves()
            
            # Should return empty slots, not crash
            assert saves[0] is None
            assert saves[1] is None
            assert saves[2] is None
        finally:
            os.unlink(temp_path)


class TestSaveGame:
    """Tests for save_game function."""
    
    def test_save_game_success(self):
        """save_game creates a new save successfully."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([], f)
            temp_path = f.name
        
        try:
            with patch("save_system._get_save_file_path", return_value=temp_path):
                result = save_game(
                    slot_id=0,
                    name="Test Save",
                    wave_number=5,
                    difficulty="NORMAL",
                    player_class="BALANCED",
                    score=1500,
                )
                
                assert result is True
                
                # Verify it was saved
                saves = load_saves()
                assert saves[0] is not None
                assert saves[0].name == "Test Save"
                assert saves[0].wave_number == 5
                assert saves[0].score == 1500
        finally:
            os.unlink(temp_path)
    
    def test_save_game_empty_name_gets_default(self):
        """save_game uses default name if empty string provided."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([], f)
            temp_path = f.name
        
        try:
            with patch("save_system._get_save_file_path", return_value=temp_path):
                save_game(slot_id=1, name="  ", wave_number=1, 
                          difficulty="EASY", player_class="TANK", score=0)
                
                saves = load_saves()
                assert saves[1].name == "Save 2"  # Default name for slot 1
        finally:
            os.unlink(temp_path)
    
    def test_save_game_invalid_slot(self):
        """save_game rejects invalid slot IDs."""
        with patch("save_system._get_save_file_path", return_value="/tmp/test.json"):
            result = save_game(slot_id=-1, name="Test", wave_number=1,
                               difficulty="NORMAL", player_class="BALANCED", score=0)
            assert result is False
            
            result = save_game(slot_id=3, name="Test", wave_number=1,
                               difficulty="NORMAL", player_class="BALANCED", score=0)
            assert result is False
    
    def test_save_game_overwrites_existing(self):
        """save_game overwrites an existing save in the same slot."""
        initial_data = [
            {"slot_id": 0, "name": "Old Save", "wave_number": 1, "difficulty": "EASY",
             "player_class": "BALANCED", "score": 100, "timestamp": "2024-01-01T00:00:00"},
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(initial_data, f)
            temp_path = f.name
        
        try:
            with patch("save_system._get_save_file_path", return_value=temp_path):
                save_game(slot_id=0, name="New Save", wave_number=10,
                          difficulty="HARD", player_class="SNIPER", score=5000)
                
                saves = load_saves()
                assert saves[0].name == "New Save"
                assert saves[0].wave_number == 10
                assert saves[0].score == 5000
        finally:
            os.unlink(temp_path)


class TestDeleteSave:
    """Tests for delete_save function."""
    
    def test_delete_save_success(self):
        """delete_save removes a save from the specified slot."""
        initial_data = [
            {"slot_id": 0, "name": "Save 1", "wave_number": 5, "difficulty": "NORMAL",
             "player_class": "BALANCED", "score": 1000, "timestamp": "2024-01-01T00:00:00"},
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(initial_data, f)
            temp_path = f.name
        
        try:
            with patch("save_system._get_save_file_path", return_value=temp_path):
                # Verify save exists
                saves = load_saves()
                assert saves[0] is not None
                
                # Delete it
                result = delete_save(0)
                assert result is True
                
                # Verify it's gone
                saves = load_saves()
                assert saves[0] is None
        finally:
            os.unlink(temp_path)
    
    def test_delete_save_invalid_slot(self):
        """delete_save rejects invalid slot IDs."""
        result = delete_save(-1)
        assert result is False
        
        result = delete_save(MAX_SAVE_SLOTS)
        assert result is False


class TestGetSaveSlot:
    """Tests for get_save_slot function."""
    
    def test_get_save_slot_exists(self):
        """get_save_slot returns the save when it exists."""
        save_data = [
            {"slot_id": 1, "name": "My Save", "wave_number": 8, "difficulty": "HARD",
             "player_class": "TANK", "score": 3000, "timestamp": "2024-01-15T10:00:00"},
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(save_data, f)
            temp_path = f.name
        
        try:
            with patch("save_system._get_save_file_path", return_value=temp_path):
                slot = get_save_slot(1)
                assert slot is not None
                assert slot.name == "My Save"
                assert slot.wave_number == 8
        finally:
            os.unlink(temp_path)
    
    def test_get_save_slot_empty(self):
        """get_save_slot returns None for empty slot."""
        with patch("save_system._get_save_file_path", return_value="/nonexistent.json"):
            slot = get_save_slot(0)
            assert slot is None
    
    def test_get_save_slot_invalid(self):
        """get_save_slot returns None for invalid slot ID."""
        slot = get_save_slot(-1)
        assert slot is None
        
        slot = get_save_slot(999)
        assert slot is None


class TestGetSaveDisplayText:
    """Tests for get_save_display_text function."""
    
    def test_display_text_empty_slot(self):
        """get_save_display_text shows placeholder for empty slot."""
        text = get_save_display_text(None)
        assert text == "[Empty Slot]"
    
    def test_display_text_valid_save(self):
        """get_save_display_text formats save info correctly."""
        slot = SaveSlot(
            slot_id=0,
            name="Hero Run",
            wave_number=15,
            difficulty="HARD",
            player_class="SNIPER",
            score=10000,
            timestamp="2024-06-15T14:30:00",
        )
        text = get_save_display_text(slot)
        
        assert "Hero Run" in text
        assert "Wave 15" in text
        assert "HARD" in text
        assert "06/15/2024" in text
    
    def test_display_text_invalid_timestamp(self):
        """get_save_display_text handles invalid timestamp gracefully."""
        slot = SaveSlot(
            slot_id=0,
            name="Test",
            wave_number=1,
            difficulty="NORMAL",
            player_class="BALANCED",
            score=0,
            timestamp="not-a-date",
        )
        text = get_save_display_text(slot)
        
        assert "Test" in text
        assert "Unknown" in text  # Fallback for invalid date
