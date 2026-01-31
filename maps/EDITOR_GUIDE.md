# Map Editor User Guide

A standalone tile-based map editor for creating and editing game maps.

## Quick Start

```bash
# Create a new map
python run_editor.py

# Edit an existing map
python run_editor.py my_map_name
```

---

## Interface Overview

```
┌─────────────────────────────────────────────────────────┬──────────────┐
│                                                         │   PALETTE    │
│                                                         │              │
│                     MAP CANVAS                          │  1: Floor    │
│                                                         │  2: Wall     │
│                  (click to paint)                       │  3: ...      │
│                                                         │              │
│                                                         │              │
│                                                         │              │
├─────────────────────────────────────────────────────────┴──────────────┤
│ Map: new_map | Size: 40x22 | Undo: 0 | Redo: 0                         │
└────────────────────────────────────────────────────────────────────────┘
```

- **Map Canvas** (left): The main editing area where you paint tiles
- **Palette** (right): Available tiles for the current theme
- **Status Bar** (bottom): Map info, undo/redo counts, and status messages

---

## Controls

### Tile Placement
| Action | Control |
|--------|---------|
| Place tile | Left-click (or hold and drag) |
| Erase tile (place floor) | Right-click (or hold and drag) |
| Select tile 1-9 | Number keys `1` through `9` |
| Click palette | Click a tile in the right panel |
| Eyedropper (pick tile) | `Alt+Click` or Middle-click |

### Brush Controls
| Action | Control |
|--------|---------|
| Decrease brush size | `[` (left bracket) |
| Increase brush size | `]` (right bracket) |
| Flood fill at cursor | `F` |

### Camera / Navigation
| Action | Control |
|--------|---------|
| Pan left | `←` Arrow |
| Pan right | `→` Arrow |
| Pan up | `↑` Arrow |
| Pan down | `↓` Arrow |

### Editing Operations
| Action | Control |
|--------|---------|
| Undo | `Ctrl+Z` |
| Redo | `Ctrl+Y` or `Ctrl+Shift+Z` |
| Fill entire map | `Ctrl+F` (uses selected tile) |

### File Operations
| Action | Control |
|--------|---------|
| Save map | `S` |
| Rename map | `N` |
| Quit | `ESC` |

### Display Options
| Action | Control |
|--------|---------|
| Toggle grid | `G` |
| Toggle help overlay | `H` |
| Cycle theme | `T` |

---

## Themes

The editor supports multiple tile themes. Press `T` to cycle through them:

| Theme | Tiles Available |
|-------|-----------------|
| **default** | Floor, Wall |
| **ocean** | Ocean Water, Ocean Rock, Floor, Wall |
| **lava** | Lava Floor, Lava Rock, Lava Pool, Wall |
| **desert** | Desert Sand, Desert Rock, Floor, Wall |

The theme is saved with the map and determines which tiles are available in the palette.

---

## Undo/Redo System

The editor tracks all tile changes for undo/redo:

- **Brush strokes are grouped**: Painting multiple tiles in one drag creates a single undo entry
- **Fill is undoable**: `Ctrl+F` can be undone in one step
- **History limit**: Maximum 100 undo steps (oldest are discarded)
- **Redo clears on new action**: Making a new edit after undo clears the redo stack

Check the status bar to see how many undo/redo actions are available.

---

## File Format

Maps are saved as JSON files in:
```
maps/data/<map_name>.json
```

Example structure:
```json
{
  "name": "my_map",
  "width": 40,
  "height": 22,
  "theme": "default",
  "tiles": [
    ["wall", "wall", "wall", ...],
    ["wall", "floor", "floor", ...],
    ...
  ]
}
```

---

## Default Map Size

New maps are created with:
- **Width**: 40 tiles
- **Height**: 22 tiles
- **Tile size**: 64x64 pixels
- **Default fill**: Floor tiles

---

## Tips

1. **Use grid mode** (`G`) for precise tile placement
2. **Paint in strokes** - drag to paint multiple tiles, release to commit
3. **Right-click to erase** - faster than selecting floor tile
4. **Save often** (`S`) - there's no auto-save
5. **Use themes** for visual variety - ocean for water levels, lava for fire areas
6. **Eyedropper** (`Alt+Click`) - quickly pick tiles from the map
7. **Flood fill** (`F`) - fill connected areas instantly
8. **Larger brush** (`]`) - paint faster with bigger brush sizes
9. **Rename maps** (`N`) - give your maps meaningful names before saving

---

## Troubleshooting

**Map doesn't load?**
- Check the filename exists in `maps/data/`
- Ensure `.json` extension (added automatically if omitted)

**Can't see map changes in game?**
- Press `F6` in-game to reload/cycle maps
- Check console for `[maps]` messages

**Tiles look wrong?**
- Tiles use color fallbacks (no sprites yet)
- Each tile type has a distinct color

---

## Example Workflow

1. **Start editor**: `python run_editor.py`
2. **Select wall tile**: Press `2`
3. **Draw border**: Click and drag around edges
4. **Add obstacles**: Paint wall clusters in the middle
5. **Switch theme**: Press `T` for different tile set
6. **Save**: Press `S`
7. **Test in game**: Run game and press `F6`
