# Bullet Hell Arena

A fast-paced top-down bullet hell shooter built with Python and Pygame. Survive waves of increasingly difficult enemies, collect powerful weapons, and command AI allies in your fight for survival.

## Features

- **Wave-based survival** — Fight through escalating waves of diverse enemy types
- **Multiple enemy types** — Grunts, heavies, spawners, laser enemies, suiciders, the Queen boss, and more
- **AI allies** — Spawn and command friendly units (scout, sniper, striker, guardian, tank)
- **Weapon variety** — Grenades, missiles, lasers, and special abilities
- **Custom maps** — Built-in map editor for creating your own arenas
- **Shader effects** — Optional GPU-accelerated visual effects (CRT, vignette, glow)
- **Save system** — Save and load your progress
- **Telemetry** — Track gameplay data and visualize statistics

## Quick Start

### Requirements

- Python 3.10+ (3.12 recommended)
- Pygame 2.0+

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/game.py_cursor_gpt.git
cd game.py_cursor_gpt

# Install dependencies
pip install -r requirements.txt

# Run the game
python game.py
```

### Optional: Build executable

```bash
# Windows
build_game.bat
```

## Controls

| Action | Key |
|--------|-----|
| Move | WASD |
| Shoot | Mouse (aim) + auto-fire |
| Dash | Space |
| Grenade | E |
| Missile | R |
| Overshield | Tab |
| Spawn/Command Ally | Q (spawn) / Right-click (command) |
| Boost | Left Shift |
| Slow | Left Ctrl |
| Pause | Escape |

## Game Mechanics

### Enemies

| Type | Behavior |
|------|----------|
| Grunt | Basic shooter, chases player |
| Heavy | Slower, tankier, harder hitting |
| Suicide | Rushes player and explodes |
| Spawner | Summons additional enemies |
| Patrol | Circles the arena edges |
| Laser | Fires deadly beam attacks |
| Evasive | Fast, dodges projectiles |
| Queen | Boss enemy with shields, grenades, and missiles |

### Allies

All allies appear as purple units with different sizes:
- **Scout** (smallest) — Fast, aggressive
- **Sniper** — Long-range precision shots
- **Striker** — Fires missile bursts
- **Guardian** — Defensive, stays near player
- **Tank** (largest) — High HP, draws fire

Command allies with right-click to send them to a location. They'll explode on contact with enemies when commanded.

### Pickups

Defeated enemies drop various pickups: health, ammo, weapon upgrades, and more.

## Map Editor

Create custom maps with the built-in editor:

```bash
python run_editor.py
```

### Editor Controls

| Action | Key |
|--------|-----|
| Place/remove tile | Left-click / Right-click |
| Pan view | Middle-click drag |
| Cycle tiles | Mouse wheel |
| Quick save | S |
| Save as | Ctrl+S |
| Load | L |
| New map | N |
| Resize | Ctrl+R |
| Spawn mode | P |
| Undo/Redo | Ctrl+Z / Ctrl+Y |
| Help | H |

## Project Structure

```
game.py_cursor_gpt/
├── game.py              # Main entry point
├── game_app.py          # Game loop and initialization
├── scenes/              # Game screens (title, gameplay, pause, etc.)
├── systems/             # Game systems (collision, spawning, UI, audio)
├── rendering/           # Rendering modules (world, HUD, shaders)
├── maps/                # Map system and editor
├── config/              # Game configuration and balance
├── tests/               # Test suite (pytest)
├── assets/              # Game assets (fonts, sounds, shaders)
└── telemetry/           # Gameplay data collection
```

## Development

### Running Tests

```bash
pytest
```

### Profiling

```bash
python profile_game.py
```

### Optional Performance Enhancements

**C Extension** (faster physics):
```bash
python setup.py build_ext --inplace
```

**GPU Physics** (CUDA):
Enable in Options menu if CUDA is available. See `comments/CUDA_INSTALLATION_GUIDE.md`.

## Configuration

Game settings are in `config/game_config.py`:
- Difficulty presets (Easy, Normal, Hard)
- Player classes
- Visual effect toggles
- Performance options

## Documentation

- `dev.md` — Developer setup and architecture guide
- `ROADMAP.txt` — Feature backlog and plans
- `comments/` — Detailed documentation on specific systems

## Credits

Built with AI assistance (GPT, Claude, Cursor) as a learning project that evolved into a full game.

## License

This project is for personal/educational use.
