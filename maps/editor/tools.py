"""Editor tools: undo/redo, eyedropper, flood fill, brush, save."""
from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING

import pygame

from .constants import (
    TileAction, ActionGroup, MAX_UNDO_HISTORY, 
    AUTOSAVE_INTERVAL, MAX_FLOOD_FILL, TILE_SIZE, PALETTE_WIDTH
)

if TYPE_CHECKING:
    from .core import MapEditor


class ToolsMixin:
    """Mixin providing editor tools: undo/redo, paint, fill, eyedropper."""
    
    # =========================================================================
    # SAVE
    # =========================================================================
    
    def _save_map(self: "MapEditor") -> None:
        """Save the current map (background thread for large maps)."""
        from ..map_saver import save_map, get_maps_data_dir
        
        filename = self.map_grid.name
        map_data = self.map_grid.to_dict()
        
        def save_task():
            try:
                data_dir = get_maps_data_dir()
                filepath = data_dir / f"{filename}.json"
                
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(map_data, f, indent=2)
                
                self._set_status(f"Saved: {filename}.json")
            except Exception as e:
                self._set_status(f"Error saving: {e}")
        
        if self.map_grid.width * self.map_grid.height > 500:
            self._set_status(f"Saving {filename}...")
            thread = threading.Thread(target=save_task, daemon=True)
            thread.start()
        else:
            if save_map(self.map_grid, filename):
                self._set_status(f"Saved: {filename}.json")
            else:
                self._set_status("Error saving map!")
    
    # =========================================================================
    # UNDO/REDO
    # =========================================================================
    
    def _place_tile_with_undo(self: "MapEditor", tx: int, ty: int, new_tile_id: str) -> bool:
        """Place a tile and record the action for undo."""
        old_tile_id = self.map_grid.get_tile_id(tx, ty)
        if old_tile_id is None or old_tile_id == new_tile_id:
            return False
        
        action = TileAction(x=tx, y=ty, old_tile_id=old_tile_id, new_tile_id=new_tile_id)
        self._current_stroke.append(action)
        self.map_grid.set_tile_id(tx, ty, new_tile_id)
        return True
    
    def _begin_stroke(self: "MapEditor") -> None:
        """Begin a new brush stroke."""
        if not self._is_painting:
            self._is_painting = True
            self._current_stroke = []
    
    def _end_stroke(self: "MapEditor") -> None:
        """End the current brush stroke and commit to undo stack."""
        if self._is_painting and self._current_stroke:
            group = ActionGroup(actions=self._current_stroke.copy())
            self._undo_stack.append(group)
            
            while len(self._undo_stack) > MAX_UNDO_HISTORY:
                self._undo_stack.pop(0)
            
            self._redo_stack.clear()
        
        self._current_stroke = []
        self._is_painting = False
    
    def _undo(self: "MapEditor") -> None:
        """Undo the last action group."""
        if not self._undo_stack:
            self._set_status("Nothing to undo")
            return
        
        group = self._undo_stack.pop()
        for action in reversed(group.actions):
            self.map_grid.set_tile_id(action.x, action.y, action.old_tile_id)
        self._redo_stack.append(group)
        self._set_status(f"Undo ({len(group.actions)} tiles)")
    
    def _redo(self: "MapEditor") -> None:
        """Redo the last undone action group."""
        if not self._redo_stack:
            self._set_status("Nothing to redo")
            return
        
        group = self._redo_stack.pop()
        for action in group.actions:
            self.map_grid.set_tile_id(action.x, action.y, action.new_tile_id)
        self._undo_stack.append(group)
        self._set_status(f"Redo ({len(group.actions)} tiles)")
    
    # =========================================================================
    # EYEDROPPER
    # =========================================================================
    
    def _eyedropper(self: "MapEditor", tx: int, ty: int) -> bool:
        """Pick the tile at the given coordinates."""
        tile_id = self.map_grid.get_tile_id(tx, ty)
        if tile_id:
            self.selected_tile_id = tile_id
            self._set_status(f"Picked: {tile_id}")
            return True
        return False
    
    # =========================================================================
    # FLOOD FILL
    # =========================================================================
    
    def _flood_fill_at_cursor(self: "MapEditor") -> None:
        """Flood fill at the current mouse position."""
        mx, my = pygame.mouse.get_pos()
        
        if mx >= self.screen_width - PALETTE_WIDTH:
            self._set_status("Move cursor to map area to fill")
            return
        
        world_x = mx + self.camera_x
        world_y = my + self.camera_y
        tx = int(world_x // TILE_SIZE)
        ty = int(world_y // TILE_SIZE)
        
        self._flood_fill(tx, ty, self.selected_tile_id)
    
    def _flood_fill(self: "MapEditor", start_x: int, start_y: int, fill_tile_id: str) -> None:
        """Flood fill starting from a position using BFS."""
        target_tile_id = self.map_grid.get_tile_id(start_x, start_y)
        
        if target_tile_id is None:
            return
        
        if target_tile_id == fill_tile_id:
            self._set_status("Already filled with this tile")
            return
        
        self._begin_stroke()
        
        visited = set()
        queue = [(start_x, start_y)]
        filled_count = 0
        
        while queue and filled_count < MAX_FLOOD_FILL:
            x, y = queue.pop(0)
            
            if (x, y) in visited:
                continue
            
            if x < 0 or x >= self.map_grid.width or y < 0 or y >= self.map_grid.height:
                continue
            
            current_tile = self.map_grid.get_tile_id(x, y)
            if current_tile != target_tile_id:
                continue
            
            visited.add((x, y))
            
            if self._place_tile_with_undo(x, y, fill_tile_id):
                filled_count += 1
            
            queue.append((x + 1, y))
            queue.append((x - 1, y))
            queue.append((x, y + 1))
            queue.append((x, y - 1))
        
        self._end_stroke()
        
        if filled_count > 0:
            self._set_status(f"Filled {filled_count} tiles")
        else:
            self._set_status("Nothing to fill")
    
    def _fill_map_with_undo(self: "MapEditor", tile_id: str) -> None:
        """Fill the entire map with a tile, recording for undo."""
        self._begin_stroke()
        for y in range(self.map_grid.height):
            for x in range(self.map_grid.width):
                self._place_tile_with_undo(x, y, tile_id)
        self._end_stroke()
    
    # =========================================================================
    # BRUSH
    # =========================================================================
    
    def _paint_with_brush(self: "MapEditor", center_tx: int, center_ty: int, tile_id: str) -> None:
        """Paint tiles using the current brush size."""
        if self.brush_size == 1:
            self._place_tile_with_undo(center_tx, center_ty, tile_id)
            return
        
        half = self.brush_size // 2
        for dy in range(-half, half + 1):
            for dx in range(-half, half + 1):
                tx = center_tx + dx
                ty = center_ty + dy
                self._place_tile_with_undo(tx, ty, tile_id)
    
    # =========================================================================
    # AUTOSAVE
    # =========================================================================
    
    def _update_autosave(self: "MapEditor", dt: float) -> None:
        """Check and perform autosave if needed."""
        self._autosave_timer -= dt
        
        if self._autosave_timer <= 0:
            self._autosave_timer = AUTOSAVE_INTERVAL
            
            current_action_count = len(self._undo_stack)
            if current_action_count > self._last_autosave_action_count:
                self._perform_autosave()
                self._last_autosave_action_count = current_action_count
    
    def _perform_autosave(self: "MapEditor") -> None:
        """Perform background autosave."""
        from ..map_saver import get_maps_data_dir
        
        filename = self.map_grid.name
        map_data = self.map_grid.to_dict()
        
        def autosave_task():
            try:
                data_dir = get_maps_data_dir()
                filepath = data_dir / f"{filename}.json"
                
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(map_data, f, indent=2)
                
                self._set_status(f"Autosaved: {filename}")
            except Exception as e:
                self._set_status(f"Autosave failed: {e}")
        
        thread = threading.Thread(target=autosave_task, daemon=True)
        thread.start()
