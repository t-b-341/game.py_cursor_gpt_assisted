# Contributing Guide

Thank you for your interest in contributing to Bullet Hell Arena!

## Getting Started

### Prerequisites

- Python 3.10+ (3.12 recommended)
- Git

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/game.py_cursor_gpt.git
cd game.py_cursor_gpt

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Verify setup
python -m pytest tests/ -q
```

## Development Workflow

### Running the Game

```bash
python game.py
```

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_collision_system.py

# Run specific test
pytest tests/test_collision_system.py::TestPlayerBulletVsEnemy
```

### Code Style

- Follow PEP 8 guidelines
- Use type hints for function signatures
- Add docstrings to public functions and classes
- Keep functions focused and under 50 lines when possible

### Project Structure

```
game.py_cursor_gpt/
├── game.py              # Entry point
├── game_app.py          # Main game loop
├── scenes/              # Game screens (title, gameplay, pause, etc.)
├── systems/             # Game systems (collision, spawning, UI)
├── rendering/           # Rendering modules
├── maps/                # Map system and editor
├── config/              # Configuration and balance
├── tests/               # Test suite
└── engine/              # Core engine utilities
```

### Key Concepts

1. **Scenes** — Each screen (title, gameplay, pause) is a Scene with `handle_input()`, `update()`, and `render()` methods
2. **Systems** — Game logic is organized into systems (collision, spawning, movement, UI)
3. **GameState** — Mutable game state passed to scenes and systems
4. **AppContext** — Immutable app-level resources (fonts, config, telemetry)

## Making Changes

### Before You Start

1. Check existing issues and discussions
2. For large changes, open an issue first to discuss the approach
3. Create a branch for your changes

### Commit Guidelines

- Write clear, concise commit messages
- Use present tense ("Add feature" not "Added feature")
- Reference issues when applicable

### Pull Request Process

1. Ensure all tests pass: `pytest`
2. Add tests for new functionality
3. Update documentation if needed
4. Create a pull request with a clear description

## Testing Guidelines

### Writing Tests

- Place tests in `tests/` directory
- Name test files `test_*.py`
- Use descriptive test function names: `test_player_bullet_hits_enemy_removes_bullet`
- Use fixtures from `tests/conftest.py` for common setup

### Test Categories

- **Unit tests** — Test individual functions/classes in isolation
- **Integration tests** — Test system interactions
- **Regression tests** — Prevent fixed bugs from returning

## Common Tasks

### Adding a New Enemy Type

1. Add template to `config/enemy_data.py` in `ENEMY_TEMPLATES`
2. Add behavior logic in `systems/enemy_behavior.py` if needed
3. Add tests in `tests/test_enemy_behavior.py`

### Adding a New Pickup

1. Add handler function in `pickups.py`
2. Register in `PICKUP_HANDLERS` dict
3. Add tests in `tests/test_pickups.py`

### Adding a New Scene

1. Create scene class in `scenes/` inheriting from `BaseScene` or `BaseMenuScene`
2. Implement `handle_input()`, `update()`, `render()`
3. Register state ID in `constants.py`
4. Add transition logic where needed

## Resources

- `dev.md` — Developer setup and architecture overview
- `ROADMAP.txt` — Feature backlog and plans
- `comments/` — Detailed documentation on specific systems

## Questions?

Open an issue or check existing documentation in the `comments/` directory.
