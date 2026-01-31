# Map Editor - Recommended Features Roadmap

Future enhancements for the map editor, organized by priority and complexity.

---

## High Priority (Quick Wins)

### 1. ✅ Map Naming Dialog (IMPLEMENTED)
**Status**: Complete
- Press `N` to rename map
- Text input overlay with cursor
- Enter to confirm, ESC to cancel

### 2. ✅ Map Resize Tool (IMPLEMENTED)
**Status**: Complete
- `Ctrl+R` opens resize dialog
- Input fields for width (1-200) and height (1-200)
- Anchor options: top_left, center, top_right, bottom_left, bottom_right
- TAB to switch between fields, arrows to change anchor
- Preserves existing tiles where possible

### 3. Copy/Paste Selection
**Current**: No way to duplicate patterns.
**Enhancement**: 
- `Ctrl+C` to copy selected region
- `Ctrl+V` to paste at cursor
- Selection via click-drag rectangle

### 4. ✅ Eyedropper Tool (IMPLEMENTED)
**Status**: Complete
- `Alt+Click` or Middle-click to pick tile under cursor
- Visual indicator (cyan border) when Alt is held

### 5. ✅ Spawn Point System (IMPLEMENTED)
**Status**: Complete
- Press `M` to toggle spawn mode
- Left-click to place/edit spawn points
- Right-click to remove spawn points
- Press `P` to set player spawn location
- Click spawn point to edit enemy pool
- Spawn pools support multiple enemy types
- Test maps via "Test Map" option in pause menu

---

## Medium Priority (Quality of Life)

### 5. ✅ Brush Size Options (IMPLEMENTED)
**Status**: Complete
- `[` / `]` to decrease/increase brush size (1-5)
- Yellow brush preview shown at cursor
- Square brush shape

### 6. Zoom Controls
**Current**: Fixed zoom, pan only.
**Enhancement**:
- Mouse wheel to zoom in/out
- `+` / `-` keys for zoom
- Minimap in corner

### 7. Layer System
**Current**: Single tile layer.
**Enhancement**:
- Background layer (decorative)
- Collision layer (gameplay)
- Object layer (spawn points, items)
- Toggle layer visibility

### 8. Recent Files Menu
**Current**: Must type filename in command line.
**Enhancement**:
- `Ctrl+O` opens file browser
- Show recent maps on startup
- Quick-switch between open maps

### 9. Autosave
**Current**: Manual save only.
**Enhancement**:
- Autosave every 2 minutes to `<name>_autosave.json`
- Recover prompt on startup if autosave exists

---

## Lower Priority (Advanced Features)

### 10. Tile Sprites
**Current**: Solid color rectangles.
**Enhancement**:
- Load PNG sprites from `assets/tiles/`
- Sprite picker in palette
- Animated tile support (water, lava)

### 11. Symmetry Painting
**Current**: No symmetry support.
**Enhancement**:
- Mirror mode (horizontal/vertical)
- Radial symmetry for circular arenas
- Toggle with `M` key

### 12. ✅ Flood Fill Tool (IMPLEMENTED)
**Status**: Complete
- `F` key for bucket fill at cursor position
- Uses BFS to fill connected same-tile regions
- Fully undoable as single action
- Safety limit of 10,000 tiles

### 13. Custom Tile Definitions
**Current**: Tiles defined in code.
**Enhancement**:
- Load tile definitions from JSON
- Create custom tiles in editor
- Set walkable/damage/shader flags per tile

### 14. Map Templates
**Current**: Blank map only.
**Enhancement**:
- Arena template (walled rectangle)
- Maze template (random walls)
- Island template (water border)
- Load template on new map

### 15. Multi-Map Connections
**Current**: Maps are standalone.
**Enhancement**:
- Define exit points to other maps
- Place teleporter tiles
- Preview connected maps

---

## Technical Improvements

### 16. Performance Optimization
- Dirty rect rendering (only redraw changed tiles)
- Chunked map loading for large maps
- Sprite batching

### 17. Plugin System
- Load custom tools from `maps/plugins/`
- Custom tile types
- Export formats (Tiled, LDTK)

### 18. Command History Log
- Show last N actions in sidebar
- Click to jump to any undo state
- Named checkpoints/snapshots

### 19. Keyboard Shortcuts Config
- Rebindable shortcuts
- Load from `maps/editor_controls.json`
- Preset profiles (Photoshop-like, Aseprite-like)

---

## Integration Features

### 20. Live Preview
- Split view: editor + game preview
- See player collision with walls
- Test enemy pathing

### 21. Export Options
- Export as PNG image
- Export collision mask only
- Export spawn point data

### 22. Version Control Integration
- Show git diff of map changes
- Commit from editor
- Branch selector

---

## Implementation Notes

### Estimated Complexity

| Feature | Complexity | Time Estimate |
|---------|------------|---------------|
| Map Naming Dialog | Low | 1-2 hours |
| Eyedropper Tool | Low | 30 min |
| Brush Size | Medium | 2-3 hours |
| Copy/Paste | Medium | 3-4 hours |
| Layer System | High | 1-2 days |
| Tile Sprites | Medium | 3-4 hours |
| Flood Fill | Medium | 2-3 hours |
| Zoom Controls | Medium | 2-3 hours |

### Dependencies

Some features require other features first:
- **Layers** → enables **Object Layer** → enables **Spawn Points**
- **Tile Sprites** → enables **Animated Tiles**
- **Copy/Paste** → enables **Templates**

---

## Suggested Implementation Order

1. **Quick wins**: Eyedropper, Map Naming, Flood Fill
2. **Core editing**: Brush Size, Copy/Paste, Zoom
3. **Visual**: Tile Sprites, Minimap
4. **Advanced**: Layers, Templates, Live Preview

---

## Community Requests

Track feature requests here as they come in:

- [ ] _No requests yet_

---

## References

Similar tools for inspiration:
- **Tiled** (mapeditor.org) - Industry standard, complex
- **LDtk** (ldtk.io) - Modern, game-focused
- **Aseprite** - Pixel art, good UX patterns
- **RPG Maker** - Tile-based, layer system
