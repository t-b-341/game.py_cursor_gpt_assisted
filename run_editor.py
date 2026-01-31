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
    
    # Window setup
    screen_width = 1280
    screen_height = 720
    
    screen = pygame.display.set_mode((screen_width, screen_height))
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
    
    # Main loop
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        
        # Handle events
        for event in pygame.event.get():
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
