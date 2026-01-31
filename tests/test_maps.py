"""Tests for the maps package."""
import pytest
import pygame

from maps import (
    Tile,
    MapGrid,
    MapManager,
    save_map,
    load_map,
    world_to_tile,
    is_tile_blocking,
    resolve_entity_map_collision,
)
from maps.registry import (
    get_tile,
    list_tiles,
    list_themes,
    get_theme_tiles,
    clear_registry,
    _register_default_tiles,
)


class TestTile:
    """Tests for Tile dataclass."""
    
    def test_tile_creation(self):
        """Tiles can be created with required fields."""
        tile = Tile(id="test", name="Test Tile")
        assert tile.id == "test"
        assert tile.name == "Test Tile"
        assert tile.walkable is True  # Default
    
    def test_tile_walkable_false(self):
        """Tiles can be marked as not walkable."""
        tile = Tile(id="wall", name="Wall", walkable=False)
        assert tile.walkable is False
    
    def test_tile_hash_and_eq(self):
        """Tiles hash and compare by ID."""
        t1 = Tile(id="floor", name="Floor")
        t2 = Tile(id="floor", name="Different Name")
        t3 = Tile(id="wall", name="Wall")
        
        assert t1 == t2  # Same ID
        assert t1 != t3  # Different ID
        assert hash(t1) == hash(t2)


class TestRegistry:
    """Tests for tile registry."""
    
    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset registry before each test."""
        clear_registry()
        _register_default_tiles()
    
    def test_default_tiles_registered(self):
        """Default tiles should be registered on import."""
        tiles = list_tiles()
        tile_ids = [t.id for t in tiles]
        assert "floor" in tile_ids
        assert "wall" in tile_ids
    
    def test_get_tile(self):
        """get_tile returns the correct tile."""
        floor = get_tile("floor")
        assert floor is not None
        assert floor.id == "floor"
        assert floor.walkable is True
        
        wall = get_tile("wall")
        assert wall is not None
        assert wall.walkable is False
    
    def test_get_tile_missing(self):
        """get_tile returns None for unknown tiles."""
        assert get_tile("nonexistent") is None
    
    def test_themes_registered(self):
        """Themes should be registered."""
        themes = list_themes()
        assert "default" in themes
        assert "ocean" in themes
        assert "lava" in themes
        assert "desert" in themes
    
    def test_get_theme_tiles(self):
        """Theme tiles can be retrieved."""
        default_tiles = get_theme_tiles("default")
        assert len(default_tiles) >= 2
        tile_ids = [t.id for t in default_tiles]
        assert "floor" in tile_ids
        assert "wall" in tile_ids


class TestMapGrid:
    """Tests for MapGrid class."""
    
    def test_create_default_grid(self):
        """MapGrid creates with default size and floor tiles."""
        grid = MapGrid(name="test", width=10, height=5)
        assert grid.name == "test"
        assert grid.width == 10
        assert grid.height == 5
        assert grid.theme == "default"
        assert grid.get_tile_id(0, 0) == "floor"
    
    def test_get_set_tile(self):
        """Tiles can be get/set by coordinates."""
        grid = MapGrid(width=10, height=10)
        
        assert grid.set_tile_id(5, 5, "wall") is True
        assert grid.get_tile_id(5, 5) == "wall"
        
        # Out of bounds
        assert grid.get_tile_id(-1, 0) is None
        assert grid.get_tile_id(0, 100) is None
        assert grid.set_tile_id(-1, 0, "wall") is False
    
    def test_fill(self):
        """fill() sets all tiles to a single type."""
        grid = MapGrid(width=5, height=5)
        grid.fill("wall")
        
        for y in range(5):
            for x in range(5):
                assert grid.get_tile_id(x, y) == "wall"
    
    def test_fill_rect(self):
        """fill_rect() fills a rectangular region."""
        grid = MapGrid(width=10, height=10)
        grid.fill_rect(2, 2, 5, 5, "wall")
        
        assert grid.get_tile_id(1, 1) == "floor"  # Outside
        assert grid.get_tile_id(2, 2) == "wall"   # Inside
        assert grid.get_tile_id(5, 5) == "wall"   # Inside
        assert grid.get_tile_id(6, 6) == "floor"  # Outside
    
    def test_to_dict_and_from_dict(self):
        """MapGrid can be serialized and deserialized."""
        grid = MapGrid(name="test", width=5, height=5, theme="ocean")
        grid.set_tile_id(2, 2, "wall")
        
        data = grid.to_dict()
        assert data["name"] == "test"
        assert data["theme"] == "ocean"
        
        restored = MapGrid.from_dict(data)
        assert restored.name == "test"
        assert restored.width == 5
        assert restored.height == 5
        assert restored.theme == "ocean"
        assert restored.get_tile_id(2, 2) == "wall"


class TestSaveLoad:
    """Tests for map saving and loading."""
    
    def test_save_and_load(self, tmp_path, monkeypatch):
        """Maps can be saved and loaded."""
        # Redirect data directory to temp
        from maps import map_saver
        monkeypatch.setattr(map_saver, "get_maps_data_dir", lambda: tmp_path)
        from maps import map_loader
        monkeypatch.setattr(map_loader, "get_maps_data_dir", lambda: tmp_path)
        
        grid = MapGrid(name="save_test", width=10, height=10)
        grid.set_tile_id(3, 3, "wall")
        
        assert save_map(grid, "save_test") is True
        
        loaded = load_map("save_test")
        assert loaded is not None
        assert loaded.name == "save_test"
        assert loaded.get_tile_id(3, 3) == "wall"
    
    def test_load_nonexistent(self, tmp_path, monkeypatch):
        """Loading nonexistent map returns None."""
        from maps import map_saver
        monkeypatch.setattr(map_saver, "get_maps_data_dir", lambda: tmp_path)
        from maps import map_loader
        monkeypatch.setattr(map_loader, "get_maps_data_dir", lambda: tmp_path)
        
        assert load_map("nonexistent") is None


class TestMapManager:
    """Tests for MapManager class."""
    
    def test_create_manager(self):
        """MapManager can be created."""
        manager = MapManager()
        assert manager.current_map is None
        assert manager.tile_size == 64
    
    def test_set_current_map(self):
        """Current map can be set directly."""
        manager = MapManager()
        grid = MapGrid(name="test")
        
        manager.set_current_map(grid)
        assert manager.current_map is grid
        assert manager.get_current_map() is grid
    
    def test_render_no_crash(self):
        """render() doesn't crash with or without a map."""
        pygame.display.init()
        surface = pygame.Surface((800, 600))
        manager = MapManager()
        
        # No map
        manager.render(surface)  # Should not crash
        
        # With map
        manager.set_current_map(MapGrid(width=10, height=10))
        manager.render(surface)  # Should not crash


class TestEditorUndoRedo:
    """Tests for map editor undo/redo functionality."""
    
    def test_undo_single_tile(self):
        """Undo reverts a single tile placement."""
        from maps.editor import MapEditor
        editor = MapEditor(map_width=10, map_height=10)
        
        # Place a wall tile
        editor._begin_stroke()
        editor._place_tile_with_undo(5, 5, "wall")
        editor._end_stroke()
        
        assert editor.map_grid.get_tile_id(5, 5) == "wall"
        
        # Undo
        editor._undo()
        assert editor.map_grid.get_tile_id(5, 5) == "floor"
    
    def test_redo_single_tile(self):
        """Redo re-applies an undone tile placement."""
        from maps.editor import MapEditor
        editor = MapEditor(map_width=10, map_height=10)
        
        # Place and undo
        editor._begin_stroke()
        editor._place_tile_with_undo(5, 5, "wall")
        editor._end_stroke()
        editor._undo()
        
        assert editor.map_grid.get_tile_id(5, 5) == "floor"
        
        # Redo
        editor._redo()
        assert editor.map_grid.get_tile_id(5, 5) == "wall"
    
    def test_undo_stroke_groups_multiple_tiles(self):
        """A brush stroke groups multiple tiles into one undo."""
        from maps.editor import MapEditor
        editor = MapEditor(map_width=10, map_height=10)
        
        # Place multiple tiles in one stroke
        editor._begin_stroke()
        editor._place_tile_with_undo(1, 1, "wall")
        editor._place_tile_with_undo(2, 2, "wall")
        editor._place_tile_with_undo(3, 3, "wall")
        editor._end_stroke()
        
        assert editor.map_grid.get_tile_id(1, 1) == "wall"
        assert editor.map_grid.get_tile_id(2, 2) == "wall"
        assert editor.map_grid.get_tile_id(3, 3) == "wall"
        
        # Single undo reverts all three
        editor._undo()
        assert editor.map_grid.get_tile_id(1, 1) == "floor"
        assert editor.map_grid.get_tile_id(2, 2) == "floor"
        assert editor.map_grid.get_tile_id(3, 3) == "floor"
    
    def test_new_action_clears_redo_stack(self):
        """New actions after undo clear the redo stack."""
        from maps.editor import MapEditor
        editor = MapEditor(map_width=10, map_height=10)
        
        # Place, undo, then place again
        editor._begin_stroke()
        editor._place_tile_with_undo(5, 5, "wall")
        editor._end_stroke()
        
        editor._undo()
        assert len(editor._redo_stack) == 1
        
        # New action clears redo
        editor._begin_stroke()
        editor._place_tile_with_undo(6, 6, "wall")
        editor._end_stroke()
        
        assert len(editor._redo_stack) == 0
    
    def test_undo_nothing_shows_message(self):
        """Undoing with empty stack shows message."""
        from maps.editor import MapEditor
        editor = MapEditor(map_width=10, map_height=10)
        
        editor._undo()
        assert "Nothing to undo" in editor.status_message
    
    def test_redo_nothing_shows_message(self):
        """Redoing with empty stack shows message."""
        from maps.editor import MapEditor
        editor = MapEditor(map_width=10, map_height=10)
        
        editor._redo()
        assert "Nothing to redo" in editor.status_message
    
    def test_fill_map_is_undoable(self):
        """Fill map operation can be undone."""
        from maps.editor import MapEditor
        editor = MapEditor(map_width=5, map_height=5)
        
        # Fill with walls
        editor._fill_map_with_undo("wall")
        
        for y in range(5):
            for x in range(5):
                assert editor.map_grid.get_tile_id(x, y) == "wall"
        
        # Undo
        editor._undo()
        
        for y in range(5):
            for x in range(5):
                assert editor.map_grid.get_tile_id(x, y) == "floor"


class TestCollision:
    """Tests for collision helpers."""
    
    @pytest.fixture
    def grid_with_walls(self):
        """Create a grid with walls around the edge."""
        grid = MapGrid(width=10, height=10)
        for x in range(10):
            grid.set_tile_id(x, 0, "wall")
            grid.set_tile_id(x, 9, "wall")
        for y in range(10):
            grid.set_tile_id(0, y, "wall")
            grid.set_tile_id(9, y, "wall")
        return grid
    
    def test_world_to_tile(self):
        """world_to_tile converts coordinates correctly."""
        assert world_to_tile(0, 0) == (0, 0)
        assert world_to_tile(64, 64) == (1, 1)
        assert world_to_tile(100, 100) == (1, 1)  # Same tile
        assert world_to_tile(128, 128) == (2, 2)
    
    def test_is_tile_blocking(self, grid_with_walls):
        """is_tile_blocking detects wall tiles."""
        # Walls at edges
        assert is_tile_blocking(grid_with_walls, 0, 0) is True
        assert is_tile_blocking(grid_with_walls, 9 * 64, 0) is True
        
        # Floor in middle
        assert is_tile_blocking(grid_with_walls, 5 * 64, 5 * 64) is False
        
        # Out of bounds
        assert is_tile_blocking(grid_with_walls, -10, -10) is True
    
    def test_resolve_entity_map_collision(self, grid_with_walls):
        """resolve_entity_map_collision stops at walls."""
        # Entity at (2, 2) in tile space = (128, 128) in world
        rect = pygame.Rect(128, 128, 32, 32)
        
        # Move into floor (should work)
        new_rect, new_vel = resolve_entity_map_collision(
            rect, (32, 32), grid_with_walls
        )
        assert new_rect.x == 160
        assert new_rect.y == 160
        
        # Move toward wall (should stop)
        rect = pygame.Rect(128, 128, 32, 32)
        new_rect, new_vel = resolve_entity_map_collision(
            rect, (-200, 0), grid_with_walls  # Move left into wall
        )
        # Should have reverted X movement
        assert new_rect.x == 128
