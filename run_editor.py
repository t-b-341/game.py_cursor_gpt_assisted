#!/usr/bin/env python3
"""
Standalone Map Editor

A separate executable for creating and editing tile-based maps.
This does NOT use the game's scene system or rendering pipeline.

Usage:
    python run_editor.py [map_name]
    
Controls:
    1-9: Select tile from palette
    T: Cycle themes (default, ocean, lava, desert)
    G: Toggle grid overlay
    S: Save map
    H: Toggle help
    F11: Toggle fullscreen
    Arrow keys: Pan camera
    Ctrl+F: Fill entire map with selected tile
    Left click: Place tile
    Right click: Erase (place floor)
    ESC: Quit
"""
import sys

import pygame

from maps.editor import MapEditor
from maps.map_loader import load_map


def main():
    """Run the map editor."""
    # Initialize pygame
    pygame.init()
    pygame.font.init()
    
    # Window setup - start windowed
    windowed_size = (1280, 720)
    screen_width, screen_height = windowed_size
    is_fullscreen = False
    
    screen = pygame.display.set_mode((screen_width, screen_height), pygame.RESIZABLE)
    pygame.display.set_caption("Map Editor - game.py")
    clock = pygame.time.Clock()
    
    # Create editor
    editor = MapEditor(
        screen_width=screen_width,
        screen_height=screen_height,
        map_width=40,
        map_height=22,
    )
    
    # Load map from command line argument if provided
    if len(sys.argv) > 1:
        map_name = sys.argv[1]
        loaded_map = load_map(map_name)
        if loaded_map:
            editor.map_grid = loaded_map
            print(f"Loaded map: {map_name}")
        else:
            print(f"Could not load map: {map_name}, starting with new map")
    
    def toggle_fullscreen():
        """Toggle between fullscreen and windowed mode."""
        nonlocal screen, is_fullscreen, screen_width, screen_height
        is_fullscreen = not is_fullscreen
        
        if is_fullscreen:
            # Get current display info for fullscreen resolution
            info = pygame.display.Info()
            screen_width, screen_height = info.current_w, info.current_h
            screen = pygame.display.set_mode((screen_width, screen_height), pygame.FULLSCREEN)
        else:
            screen_width, screen_height = windowed_size
            screen = pygame.display.set_mode((screen_width, screen_height), pygame.RESIZABLE)
        
        # Update editor dimensions
        editor.screen_width = screen_width
        editor.screen_height = screen_height
        return screen
    
    def handle_resize(new_width, new_height):
        """Handle window resize."""
        nonlocal screen_width, screen_height
        screen_width, screen_height = new_width, new_height
        editor.screen_width = screen_width
        editor.screen_height = screen_height
    
    # Main loop
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        
        # Handle events
        for event in pygame.event.get():
            # Handle fullscreen toggle before editor
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                screen = toggle_fullscreen()
                continue
            
            # Handle window resize
            if event.type == pygame.VIDEORESIZE and not is_fullscreen:
                handle_resize(event.w, event.h)
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                continue
            
            if editor.handle_event(event):
                running = False
        
        # Update
        editor.update(dt)
        
        # Render
        editor.render(screen)
        pygame.display.flip()
    
    pygame.quit()
    print("Editor closed.")


if __name__ == "__main__":
    main()
