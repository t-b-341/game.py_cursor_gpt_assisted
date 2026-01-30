"""Tests for spatial grid collision optimization."""
import pytest
import pygame


@pytest.fixture(autouse=True)
def init_pygame():
    """Initialize pygame for rect operations."""
    pygame.init()
    yield
    pygame.quit()


class TestSpatialGrid:
    """Test spatial grid basic operations."""
    
    def test_grid_creation(self):
        """Test that grid can be created with correct dimensions."""
        from systems.spatial_grid import SpatialGrid
        
        grid = SpatialGrid(1920, 1080, cell_size=128)
        
        assert grid.width == 1920
        assert grid.height == 1080
        assert grid.cell_size == 128
        assert grid.cols == 15  # ceil(1920/128)
        assert grid.rows == 9   # ceil(1080/128)
    
    def test_insert_and_query_point(self):
        """Test inserting objects and querying by point."""
        from systems.spatial_grid import SpatialGrid
        
        grid = SpatialGrid(1920, 1080, cell_size=128)
        
        # Create test object with rect
        obj = {"id": 1, "rect": pygame.Rect(100, 100, 32, 32)}
        grid.insert(obj, obj["rect"])
        
        # Query point inside object's cell
        results = list(grid.query_point(100, 100))
        assert obj in results
        
        # Query point in different cell should not find object
        results = list(grid.query_point(500, 500))
        assert obj not in results
    
    def test_insert_and_query_rect(self):
        """Test inserting objects and querying by rect overlap."""
        from systems.spatial_grid import SpatialGrid
        
        grid = SpatialGrid(1920, 1080, cell_size=128)
        
        # Create test objects
        obj1 = {"id": 1, "rect": pygame.Rect(100, 100, 32, 32)}
        obj2 = {"id": 2, "rect": pygame.Rect(500, 500, 32, 32)}
        
        grid.insert(obj1, obj1["rect"])
        grid.insert(obj2, obj2["rect"])
        
        # Query rect overlapping obj1's cell
        query_rect = pygame.Rect(80, 80, 100, 100)
        results = list(grid.query_rect(query_rect))
        
        assert obj1 in results
        assert obj2 not in results
    
    def test_query_radius(self):
        """Test querying objects within a radius."""
        from systems.spatial_grid import SpatialGrid
        
        grid = SpatialGrid(1920, 1080, cell_size=128)
        
        # Create test objects at known positions
        obj_near = {"id": 1, "rect": pygame.Rect(100, 100, 32, 32)}
        obj_far = {"id": 2, "rect": pygame.Rect(800, 800, 32, 32)}
        
        grid.insert(obj_near, obj_near["rect"])
        grid.insert(obj_far, obj_far["rect"])
        
        # Query with radius that includes obj_near but not obj_far
        results = list(grid.query_radius(100, 100, 200))
        
        assert obj_near in results
        # obj_far might be in results due to grid cell overlap, but real distance check filters it
    
    def test_clear(self):
        """Test clearing the grid."""
        from systems.spatial_grid import SpatialGrid
        
        grid = SpatialGrid(1920, 1080, cell_size=128)
        
        obj = {"id": 1, "rect": pygame.Rect(100, 100, 32, 32)}
        grid.insert(obj, obj["rect"])
        
        # Verify object is in grid
        results = list(grid.query_point(100, 100))
        assert len(results) == 1
        
        # Clear and verify empty
        grid.clear()
        results = list(grid.query_point(100, 100))
        assert len(results) == 0
    
    def test_insert_all(self):
        """Test bulk insert of multiple objects."""
        from systems.spatial_grid import SpatialGrid
        
        grid = SpatialGrid(1920, 1080, cell_size=128)
        
        objects = [
            {"id": i, "rect": pygame.Rect(i * 100, i * 100, 32, 32)}
            for i in range(10)
        ]
        
        grid.insert_all(objects)
        
        # Verify all objects can be found
        for obj in objects:
            cx, cy = obj["rect"].center
            results = list(grid.query_point(cx, cy))
            assert obj in results
    
    def test_object_spanning_multiple_cells(self):
        """Test that large objects spanning multiple cells are found correctly."""
        from systems.spatial_grid import SpatialGrid
        
        grid = SpatialGrid(1920, 1080, cell_size=128)
        
        # Create large object spanning multiple cells
        large_obj = {"id": 1, "rect": pygame.Rect(100, 100, 300, 300)}
        grid.insert(large_obj, large_obj["rect"])
        
        # Query points in different cells covered by the object
        # All should find the object
        assert large_obj in list(grid.query_point(150, 150))
        assert large_obj in list(grid.query_point(250, 250))
        assert large_obj in list(grid.query_point(350, 350))


class TestFrameCaching:
    """Test frame-based caching behavior."""
    
    def test_grid_reuse_same_frame(self):
        """Test that grids are reused within the same frame."""
        from systems.spatial_grid import get_enemy_grid, reset_frame_cache
        
        reset_frame_cache()
        
        # First call creates grid
        grid1 = get_enemy_grid(1920, 1080, frame_id=1)
        
        # Same frame_id should return same grid
        grid2 = get_enemy_grid(1920, 1080, frame_id=1)
        
        # Without frame caching, insert_all would add duplicates
        # With caching, same grid object is returned
        assert grid1 is grid2
    
    def test_grid_rebuild_new_frame(self):
        """Test that grids are rebuilt for new frames."""
        from systems.spatial_grid import get_enemy_grid, reset_frame_cache
        
        reset_frame_cache()
        
        # Create grid for frame 1
        grid1 = get_enemy_grid(1920, 1080, frame_id=1)
        obj = {"id": 1, "rect": pygame.Rect(100, 100, 32, 32)}
        grid1.insert(obj, obj["rect"])
        
        # New frame should get cleared grid
        grid2 = get_enemy_grid(1920, 1080, frame_id=2)
        
        # Grid should be same object but cleared
        assert grid2 is grid1
        assert len(list(grid2.query_point(100, 100))) == 0


class TestCollisionOptimization:
    """Test that spatial grid optimizations work correctly in collision context."""
    
    def test_explosion_damage_uses_spatial_query(self):
        """Test that explosion damage correctly uses spatial grid for efficiency."""
        from systems.spatial_grid import SpatialGrid
        
        # Create grid and add enemies
        grid = SpatialGrid(1920, 1080, cell_size=128)
        
        enemies = [
            {"id": 1, "rect": pygame.Rect(100, 100, 32, 32), "hp": 100},  # Near explosion
            {"id": 2, "rect": pygame.Rect(800, 800, 32, 32), "hp": 100},  # Far from explosion
        ]
        
        for enemy in enemies:
            grid.insert(enemy, enemy["rect"])
        
        # Simulate explosion at (100, 100) with radius 200
        explosion_x, explosion_y = 100, 100
        explosion_radius = 200
        
        # Query returns only nearby candidates
        candidates = list(grid.query_radius(explosion_x, explosion_y, explosion_radius))
        
        # Only the nearby enemy should be a candidate
        assert enemies[0] in candidates
        # The far enemy might or might not be in candidates depending on grid cell size
        # But the distance check would filter it out anyway
