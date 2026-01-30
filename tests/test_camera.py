"""Tests for the camera/viewport system."""
import pytest
import pygame


@pytest.fixture(autouse=True)
def init_pygame():
    """Initialize pygame for tests."""
    pygame.init()
    yield
    pygame.quit()


class TestCamera:
    """Test Camera class functionality."""
    
    def test_camera_creation(self):
        """Camera initializes with correct dimensions."""
        from systems.camera import Camera
        
        camera = Camera(
            display_width=1920,
            display_height=1080,
            world_width=3840,
            world_height=2160
        )
        
        assert camera.display_width == 1920
        assert camera.display_height == 1080
        assert camera.world_width == 3840
        assert camera.world_height == 2160
    
    def test_camera_initial_centering(self):
        """Camera starts centered in the world."""
        from systems.camera import Camera
        
        camera = Camera(
            display_width=1920,
            display_height=1080,
            world_width=3840,
            world_height=2160
        )
        
        # Should be centered: (3840-1920)/2 = 960, (2160-1080)/2 = 540
        assert camera.x == 960
        assert camera.y == 540
    
    def test_camera_follow_player(self):
        """Camera follows player position."""
        from systems.camera import Camera
        
        camera = Camera(
            display_width=1920,
            display_height=1080,
            world_width=3840,
            world_height=2160,
            smoothing=0  # Instant follow for testing
        )
        
        # Create a player rect at (1000, 800)
        player = pygame.Rect(1000, 800, 50, 50)
        
        # Follow player
        camera.follow(player, 0.016)
        
        # Camera should center on player
        expected_x = player.centerx - camera.display_width // 2
        expected_y = player.centery - camera.display_height // 2
        
        assert camera.x == expected_x
        assert camera.y == expected_y
    
    def test_camera_clamping_to_world_bounds(self):
        """Camera stays within world bounds."""
        from systems.camera import Camera
        
        camera = Camera(
            display_width=1920,
            display_height=1080,
            world_width=3840,
            world_height=2160,
            smoothing=0
        )
        
        # Player at top-left corner
        player = pygame.Rect(0, 0, 50, 50)
        camera.follow(player, 0.016)
        
        # Camera should be clamped to (0, 0)
        assert camera.x >= 0
        assert camera.y >= 0
        
        # Player at bottom-right corner
        player = pygame.Rect(3800, 2100, 50, 50)
        camera.follow(player, 0.016)
        
        # Camera should be clamped to max bounds
        assert camera.x <= camera.world_width - camera.display_width
        assert camera.y <= camera.world_height - camera.display_height
    
    def test_world_to_screen_conversion(self):
        """World coordinates convert to screen coordinates correctly."""
        from systems.camera import Camera
        
        camera = Camera(
            display_width=1920,
            display_height=1080,
            world_width=3840,
            world_height=2160
        )
        camera.x = 500
        camera.y = 300
        
        # World point at (600, 400) should be at screen (100, 100)
        screen_x, screen_y = camera.world_to_screen(600, 400)
        
        assert screen_x == 100
        assert screen_y == 100
    
    def test_screen_to_world_conversion(self):
        """Screen coordinates convert to world coordinates correctly."""
        from systems.camera import Camera
        
        camera = Camera(
            display_width=1920,
            display_height=1080,
            world_width=3840,
            world_height=2160
        )
        camera.x = 500
        camera.y = 300
        
        # Screen point at (100, 100) should be at world (600, 400)
        world_x, world_y = camera.screen_to_world(100, 100)
        
        assert world_x == 600
        assert world_y == 400
    
    def test_viewport_rect(self):
        """Viewport rect is correct."""
        from systems.camera import Camera
        
        camera = Camera(
            display_width=1920,
            display_height=1080,
            world_width=3840,
            world_height=2160
        )
        camera.x = 500
        camera.y = 300
        
        viewport = camera.viewport
        
        assert viewport.x == 500
        assert viewport.y == 300
        assert viewport.width == 1920
        assert viewport.height == 1080
    
    def test_is_visible(self):
        """Visibility check works correctly."""
        from systems.camera import Camera
        
        camera = Camera(
            display_width=1920,
            display_height=1080,
            world_width=3840,
            world_height=2160,
            margin=64
        )
        camera.x = 500
        camera.y = 300
        
        # Rect inside viewport
        visible_rect = pygame.Rect(600, 400, 100, 100)
        assert camera.is_visible(visible_rect) is True
        
        # Rect completely outside viewport (far left)
        offscreen_rect = pygame.Rect(0, 400, 100, 100)
        assert camera.is_visible(offscreen_rect) is False
        
        # Rect at edge (within margin)
        edge_rect = pygame.Rect(450, 400, 100, 100)  # Overlaps margin
        assert camera.is_visible(edge_rect) is True
    
    def test_cull_entities(self):
        """Entity culling filters correctly."""
        from systems.camera import Camera
        
        camera = Camera(
            display_width=1920,
            display_height=1080,
            world_width=3840,
            world_height=2160,
            margin=64
        )
        camera.x = 500
        camera.y = 300
        
        entities = [
            {"rect": pygame.Rect(600, 400, 50, 50)},  # Visible
            {"rect": pygame.Rect(0, 0, 50, 50)},      # Off-screen
            {"rect": pygame.Rect(700, 500, 50, 50)},  # Visible
            {"rect": pygame.Rect(3800, 2100, 50, 50)},  # Off-screen
        ]
        
        visible = camera.cull_entities(entities)
        
        assert len(visible) == 2
        assert camera.entities_total == 4
        assert camera.entities_culled == 2
    
    def test_culling_stats(self):
        """Culling statistics are tracked correctly."""
        from systems.camera import Camera
        
        camera = Camera(
            display_width=1920,
            display_height=1080,
            world_width=3840,
            world_height=2160
        )
        camera.x = 0
        camera.y = 0
        
        entities = [
            {"rect": pygame.Rect(100, 100, 50, 50)},  # Visible
            {"rect": pygame.Rect(200, 200, 50, 50)},  # Visible
            {"rect": pygame.Rect(5000, 5000, 50, 50)},  # Off-screen
        ]
        
        camera.cull_entities(entities)
        stats = camera.get_culling_stats()
        
        assert stats["total"] == 3
        assert stats["visible"] == 2
        assert stats["culled"] == 1
        assert stats["cull_rate"] == pytest.approx(1/3)


class TestCameraModuleFunctions:
    """Test module-level camera functions."""
    
    def test_create_camera_sets_active(self):
        """create_camera sets the active camera."""
        from systems.camera import create_camera, get_camera, set_camera
        
        # Clear any existing camera
        set_camera(None)
        assert get_camera() is None
        
        # Create camera
        camera = create_camera(1920, 1080, 3840, 2160)
        
        # Should be active
        assert get_camera() is camera
    
    def test_get_camera_returns_none_when_not_set(self):
        """get_camera returns None when no camera is set."""
        from systems.camera import get_camera, set_camera
        
        set_camera(None)
        assert get_camera() is None


class TestCameraSmoothing:
    """Test camera smoothing behavior."""
    
    def test_smooth_follow_gradual(self):
        """Camera follows gradually with smoothing enabled."""
        from systems.camera import Camera
        
        camera = Camera(
            display_width=1920,
            display_height=1080,
            world_width=3840,
            world_height=2160,
            smoothing=5.0  # Moderate smoothing
        )
        
        # Start at center
        initial_x, initial_y = camera.x, camera.y
        
        # Target far away
        player = pygame.Rect(2000, 1500, 50, 50)
        
        # One frame of following
        camera.follow(player, 0.016)
        
        # Should have moved toward target, but not reached it
        assert camera.x != initial_x or camera.y != initial_y
        
        # Calculate expected target
        target_x = player.centerx - camera.display_width // 2
        target_y = player.centery - camera.display_height // 2
        
        # Should not have reached target yet (smoothing)
        # (unless initial position happened to be the target)
        if initial_x != target_x:
            assert camera.x != target_x
    
    def test_instant_follow_no_smoothing(self):
        """Camera follows instantly with smoothing=0."""
        from systems.camera import Camera
        
        camera = Camera(
            display_width=1920,
            display_height=1080,
            world_width=3840,
            world_height=2160,
            smoothing=0  # No smoothing
        )
        
        player = pygame.Rect(2000, 1500, 50, 50)
        camera.follow(player, 0.016)
        
        # Should be exactly at target (clamped)
        target_x = player.centerx - camera.display_width // 2
        target_y = player.centery - camera.display_height // 2
        target_x = max(0, min(target_x, camera.world_width - camera.display_width))
        target_y = max(0, min(target_y, camera.world_height - camera.display_height))
        
        assert camera.x == target_x
        assert camera.y == target_y
