# Architecture Overview

This document describes the high-level architecture of Bullet Hell Arena.

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ENTRY POINT                                     │
│                                                                              │
│    game.py  ──────►  GameApp  ──────►  Main Loop                            │
│                      (game_app.py)     (process_events, update, render)     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CORE DATA                                       │
│                                                                              │
│   ┌──────────────┐                    ┌──────────────┐                      │
│   │  AppContext  │                    │  GameState   │                      │
│   │  (context.py)│                    │  (state.py)  │                      │
│   ├──────────────┤                    ├──────────────┤                      │
│   │ • screen     │                    │ • player_rect│                      │
│   │ • fonts      │                    │ • enemies    │                      │
│   │ • config     │                    │ • bullets    │                      │
│   │ • clock      │                    │ • score      │                      │
│   │ • telemetry  │                    │ • wave_number│                      │
│   │ • controls   │                    │ • pickups    │                      │
│   └──────────────┘                    └──────────────┘                      │
│        │                                    │                                │
│        │  Immutable (app lifetime)          │  Mutable (per-run)            │
│        └────────────────┬───────────────────┘                                │
│                         ▼                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SCENE STACK                                     │
│                           (scenes/base.py)                                   │
│                                                                              │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐          │
│   │  Title  │  │Gameplay │  │  Pause  │  │ Options │  │GameOver │          │
│   └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘          │
│                                                                              │
│   Each scene implements:                                                     │
│   • handle_input(events, game_state, ctx) → dict                            │
│   • update(dt, game_state, ctx)                                             │
│   • render(screen, game_state, ctx)                                         │
│                                                                              │
│   Transitions: push, pop, replace, swap                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SYSTEMS                                         │
│                         (systems/ directory)                                 │
│                                                                              │
│   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                │
│   │   Movement     │  │   Collision    │  │    Spawning    │                │
│   │  (movement.py) │  │(collision_*.py)│  │(spawn_system.py│                │
│   └────────────────┘  └────────────────┘  └────────────────┘                │
│                                                                              │
│   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                │
│   │     Input      │  │     Audio      │  │       UI       │                │
│   │ (input_system) │  │ (audio_system) │  │  (ui_system)   │                │
│   └────────────────┘  └────────────────┘  └────────────────┘                │
│                                                                              │
│   Systems are registered in systems/registry.py                              │
│   Called in order each frame during gameplay                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              RENDERING                                       │
│                        (rendering/ directory)                                │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                        Five-Phase Pipeline                            │  │
│   │                                                                       │  │
│   │   1. Background  ──►  2. Terrain  ──►  3. Entities  ──►              │  │
│   │                                                                       │  │
│   │   4. Projectiles/Effects  ──►  5. HUD/Overlays                       │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   rendering/world/     - World rendering (terrain, entities, projectiles)   │
│   rendering/hud.py     - Health bars, score, wave info                       │
│   rendering/overlays.py - Debug overlay, damage numbers                      │
│   rendering/shaders/   - GPU shader pipeline (optional)                      │
└─────────────────────────────────────────────────────────────────────────────┘

```

## Directory Structure

```
game.py_cursor_gpt/
├── game.py              # Entry point - calls GameApp().run()
├── game_app.py          # Main game loop class
├── state.py             # GameState - mutable game data
├── context.py           # AppContext - immutable app resources
│
├── config/              # Configuration and balance
│   ├── game_config.py   # Difficulty, options, feel tuning
│   ├── enemy_data.py    # Enemy templates
│   ├── enemy_defs.py    # Enemy definition lookup
│   ├── projectile_defs.py # Projectile definitions
│   └── balance.py       # Scoring, cooldowns, damage
│
├── scenes/              # Full-screen scenes
│   ├── base.py          # BaseScene, BaseMenuScene, SceneStack
│   ├── title.py         # Title screen
│   ├── gameplay.py      # Main gameplay
│   ├── pause.py         # Pause menu
│   ├── options/         # Options menu (split into submodules)
│   ├── game_over.py     # Game over screen
│   ├── high_scores.py   # High scores display
│   └── transitions.py   # Scene transition types
│
├── systems/             # Per-frame game systems
│   ├── registry.py      # System registration and order
│   ├── movement_system.py
│   ├── collision/       # Collision detection (split)
│   ├── spawn_system.py  # Wave spawning
│   ├── input_system.py  # Input handling
│   ├── audio_system.py  # Sound effects and music
│   └── ui/              # HUD and UI rendering
│
├── rendering/           # Drawing and visuals
│   ├── context.py       # RenderContext, camera helpers
│   ├── world/           # World rendering (terrain, entities)
│   ├── hud.py           # Health bars, text
│   ├── overlays.py      # Debug overlays
│   └── shaders/         # GPU shader pipeline
│
├── maps/                # Custom map system
│   ├── map_grid.py      # MapGrid data structure
│   ├── map_manager.py   # Map loading/saving
│   ├── editor/          # Map editor (split)
│   └── level_converter.py # Convert maps to game geometry
│
├── engine/              # Core engine utilities
│   ├── run_manager.py   # Start/restart runs
│   └── render_loop.py   # Render orchestration
│
├── shader_effects/      # CPU post-process effects
│   ├── base.py          # Effect base class
│   ├── color_effects.py # Vignette, color grading
│   └── distort_effects.py # CRT, distortion
│
├── telemetry/           # Gameplay data collection
│   ├── writer.py        # SQLite event writer
│   └── sql/             # Query templates
│
└── tests/               # Test suite (pytest)
```

## Data Flow

```
                    User Input (keyboard, mouse)
                              │
                              ▼
┌─────────────────────────────────────────────────┐
│               GameApp.process_events()          │
│   • Pygame event queue                          │
│   • Scene.handle_input() → SceneTransition      │
└─────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────┐
│               GameApp.update(dt)                │
│   • Scene.update() for current scene            │
│   • For gameplay: run all systems in order      │
│     - Movement system                           │
│     - Collision system                          │
│     - Spawn system                              │
│     - etc.                                      │
└─────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────┐
│               GameApp.render()                  │
│   • Scene.render() for current scene            │
│   • For gameplay: five-phase pipeline           │
│   • Apply shader effects if enabled             │
│   • pygame.display.flip()                       │
└─────────────────────────────────────────────────┘
```

## Key Patterns

### Scene Transitions

Scenes communicate via `SceneTransition` objects:

```python
# Push a new scene on top (e.g., pause)
return SceneTransition.push(STATE_PAUSE)

# Pop current scene (e.g., unpause)
return SceneTransition.pop()

# Replace current scene (e.g., game over)
return SceneTransition.replace(STATE_GAME_OVER)
```

### System Registration

Systems are registered with priority and run in order:

```python
# In systems/registry.py
GAMEPLAY_SYSTEMS = [
    ("input", input_system.update, 100),
    ("movement", movement_system.update, 200),
    ("collision", collision_system.update, 300),
    ("spawn", spawn_system.update, 400),
    ("ui", ui_system.update, 900),
]
```

### Context Pattern

Two context objects flow through the system:

- **AppContext** — Immutable app resources (fonts, config, screen dimensions)
- **GameState** — Mutable game data (player, enemies, score)

```python
def update(dt: float, game_state: GameState, ctx: dict) -> None:
    # ctx contains AppContext fields
    # game_state is modified in place
    pass
```

### Render Context

Rendering uses `RenderContext` for camera and culling:

```python
render_ctx = RenderContext.from_screen_and_ctx(screen, ctx)
render_background(state, ctx, render_ctx)
render_entities(state, ctx, render_ctx)
```

## Performance Considerations

- **Spatial Grid** — Collision uses spatial partitioning for O(1) neighbor lookups
- **Surface Caching** — Projectile and texture surfaces are cached
- **Batch Blitting** — Similar projectiles are batched with `screen.blits()`
- **Culling** — Off-screen entities are culled before rendering
- **C Extension** — Optional `game_physics` module for faster physics

## Extension Points

### Adding a New Enemy

1. Add template to `config/enemy_data.py`
2. Add behavior in `systems/enemy_behavior.py`
3. Add tests in `tests/test_enemy_behavior.py`

### Adding a New Scene

1. Create class in `scenes/` extending `BaseScene`
2. Register state ID in `constants.py`
3. Add transition from existing scenes

### Adding a New System

1. Create module in `systems/`
2. Register in `systems/registry.py` with appropriate priority
3. Add tests in `tests/`

## See Also

- `dev.md` — Developer setup guide
- `CONTRIBUTING.md` — Contribution guidelines
- `ROADMAP.txt` — Feature backlog
