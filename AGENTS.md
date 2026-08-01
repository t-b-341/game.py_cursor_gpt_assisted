# AGENTS.md — Project Guide for Code-Reviewing Agents

> Purpose: give an AI agent (Claude, etc.) enough context to review changes to this
> codebase competently. It covers what the project is, how it is wired at runtime,
> where things live, the conventions/invariants to respect, and the known
> tech‑debt hotspots to watch for during review.
>
> This file is descriptive, not prescriptive. It is auto‑discovered by most coding
> agents because it is named `AGENTS.md`. Companion human docs: `README.md`,
> `ARCHITECTURE.md`, `dev.md`, `CONTRIBUTING.md`, and the `comments/` folder.

---

## 1. What this project is

**Bullet Hell Arena** — a fast‑paced, top‑down, wave‑based bullet‑hell shooter written
in **Python + Pygame**. Survive escalating waves of enemies, collect/unlock weapons,
command AI allies, fight bosses (e.g. the Queen), on procedurally‑built arenas or
custom tile maps. It has grown well beyond a toy: it includes a scene/state machine,
a fixed‑timestep simulation, a multi‑phase renderer, optional GPU shaders, SQLite
telemetry, an offline PyTorch‑based dynamic‑difficulty model, a standalone map editor,
and an optional C physics extension.

It is a solo/AI‑assisted learning project, so expect **pragmatic code, partial
refactors in flight, and several backward‑compat shims** (see §10). When reviewing,
distinguish "the live path" from "parallel/legacy code that still compiles."

---

## 2. How to run, build, and test

All commands run from the repo root. OS in use is Windows/PowerShell, but code targets
Linux too (CI runs on Ubuntu).

| Task | Command |
|------|---------|
| Run the game | `python game.py` (or `run_game.bat`) |
| Run the map editor | `python run_editor.py [map_name]` |
| Run tests | `pytest` (config in `pytest.ini`; verbose by default) |
| Build C physics extension (optional, faster) | `python setup.py build_ext --inplace` |
| Build a Windows executable (PyInstaller) | `build_game.bat` (uses `MyGame.spec`) |
| Profile ~N seconds of gameplay | `python profile_game.py [seconds]` → `profiling_results.prof/.txt` |
| Visualize telemetry | `python visualize.py` (needs matplotlib) |
| CUDA diagnostic | `python diagnose_cuda.py` |
| Safe mode (disable GPU/CUDA/telemetry) | `python game.py --safe-mode` or `GAME_SAFE_MODE=1` |
| Force Python physics | `python game.py --python-physics` or `USE_PYTHON_PHYSICS=1` |
| Enable dynamic difficulty (DDA) | `python game.py --dda` or `GAME_ENABLE_DDA=1` |

Useful env vars: `GAME_DEBUG_PERF=1` (frame ring buffer in `telemetry/perf.py`),
`GAME_PERF_TIMING=1` (per‑system timers in `systems/perf_timing.py`),
`SDL_VIDEODRIVER=dummy` (headless; set automatically in `tests/conftest.py`).

### Dependencies (`requirements.txt`)
- **Required:** `pygame>=2.0.0`, `numpy>=1.20.0`, `pytest>=7.0.0`
- **Optional (GPU shaders):** `moderngl>=5.0.0`, `moderngl-window>=2.0.0`
- **Optional (commented out):** `matplotlib`, `pandas` (telemetry viz), `numba` (JIT)
- **Not in requirements / not committed:** PyTorch (`torch`) is needed to *train/run* the
  DDA model; the CUDA `gpu_physics` module is external and **not present in the repo**;
  the C extension is built from `game_physics.c` (no compiled artifact is committed).
- CI (`.github/workflows/python-ci.yml`) runs `pytest` on **Python 3.10 and 3.12** and a
  syntax/import smoke check. It does **not** install torch/matplotlib/pandas or build the
  C extension, so tests must pass with core deps only.

---

## 3. Top‑level layout

```
game.py            # Thin entry point + event/transition/simulation coordinator functions
game_app.py        # GameApp: owns the main loop (process_events → update → render)
game_init.py       # create_app(): pygame init, AppContext/GameState/SceneStack construction
state.py           # GameState (all mutable per-run state) + tiny optional ECS registry
context.py         # AppContext (app-lifetime resources/config) + CtxHelper
constants.py       # STATE_* screen ids, DIFFICULTY_*, PLAYER_CLASS_*, AIM_*, themes, re-exports
simulation_systems.py  # Outer fixed-step pipeline (timers, hazards, entities, registry, camera…)
ecs_components.py  # Optional dataclass components (Position/Velocity/Health/AI/Collider…)
event_bus.py       # Minimal pub/sub EventBus

config/            # game_config.py (GameConfig), balance.py (tuning), enemy_data/defs, projectile_defs, shaders.json
engine/            # run_manager.py (start/restart/load runs), input_loop.py, render_loop.py
systems/           # Per-tick simulation + non-sim systems (see §6)
scenes/            # Scene stack screens + transitions (title, options=MENU, gameplay, pause, …)
screens/           # Imperative draw/input handlers reused by some scenes (gameplay 5-phase, pause, …)
rendering/         # RenderContext, world/ (terrain/entities/projectiles/textures), hud, overlays, shaders/
shader_effects/    # CPU PostProcessEffect stacks + GPU pipeline manager + registry
visual_effects.py  # Older, separate CPU effects (menu/gameplay/pause)
rendering_shaders.py, gpu_gl_utils.py  # GPU (moderngl) helpers + gameplay post-process shim
assets/            # fonts, images, music, sfx, shaders/*.frag, data/
maps/              # Tile map system + map editor (editor/ subpackage) + data/*.json
level_builder.py, level_state.py, level_utils.py, hazards.py  # Procedural arena geometry
enemies/, entities/, allies.py, pickups.py  # Entity factories/AI/wrappers (see §5)
telemetry/, telemetry_viz/  # SQLite event logging + matplotlib visualization
ml/                # Dynamic Difficulty Adjustment (PyTorch), offline training/eval, A/B test
game_physics.c, physics_loader.py, setup.py  # Optional C extension + resolver + build
tests/             # pytest suite (~30+ files) + conftest.py
comments/          # Design notes / status docs (many; some may be stale)
```

Naming note: **`scenes/options/core.py` (`OptionsScene`) is the state `MENU`** — the
main pre‑game menu. There is no separate "options" screen id.

---

## 4. Runtime architecture

### 4.1 Startup chain
`game.py:main()` → `GameApp()` (`game_app.py`) → `game._create_app()` →
`game_init.create_app()`. `create_app()` resolves the physics backend
(`physics_loader.resolve_physics`), inits pygame + mixer, creates a **fullscreen,
double‑buffered, vsync‑off** window, builds `AppContext` (with a `GameConfig`), builds the
initial `GameState` (with procedural level geometry + `level_context`), sets up resources,
registers telemetry event handlers, and pushes `TitleScene` onto a `SceneStack`. It returns
an `AppResult` bundle consumed by `GameApp`.

### 4.2 The main loop (`GameApp.run`)
Each frame:
1. `frame_tick`: `dt = clock.tick(target_fps)` — `target_fps` comes from config
   (default `0` = **uncapped**, uses `tick_busy_loop`).
2. `scaled_dt = dt * config.timescale` (game‑speed control; default 1.0).
3. `process_events()` → `game._handle_events(...)` (global QUIT, scene input, debug keys,
   and a large fallback that applies dict‑result flags like `start_game`/`try_again`).
4. `update(scaled_dt)`:
   - Only when current state is `PLAYING`/`ENDURANCE`: read keys once, run
     `systems.input_system.handle_gameplay_input`, then **fixed‑step** simulation.
   - `_step_simulation` accumulates `dt` and runs `_update_simulation(FIXED_DT=1/60, …)`
     **0..MAX_SIMULATION_STEPS(=8)** times. This is the authoritative sim tick rate (60 Hz),
     decoupled from render FPS.
   - Non‑gameplay states just call `scene.update(dt)` for animations/timers.
   - After sim, syncs scene stack if `current_screen` flipped to `GAME_OVER`/`VICTORY`.
5. `render()` → `engine.render_loop.render_current_scene(...)`; then optional world‑surface
   downscale (`world_scale`), then `pygame.display.flip()`.

**Two dt's:** render uses real `dt`; simulation always advances in fixed `1/60` steps.
`GameState.simulation_interpolation` is stored for future render interpolation (not yet used).

### 4.3 Core data objects (know these cold)
- **`AppContext`** (`context.py`) — app‑lifetime resources/config: `screen`, `world_surface`,
  `clock`, fonts, `display_width/height` vs world `width/height` (world can be larger via
  `world_scale`, default **1.33**), `config: GameConfig`, `controls`, `telemetry_client`
  (**None until a run starts**), `event_bus`, `map_manager`, `using_c_physics`.
- **`GameState`** (`state.py`) — all mutable per‑run state as a big `@dataclass`: entity
  **lists** (`enemies`, `player_bullets`, `enemy_projectiles`, `friendly_projectiles`,
  `friendly_ai`, `pickups`, `missiles`, `grenade_explosions`, `*_laser_beams`, `decoys`, …),
  player stats/timers, wave/level/score, run statistics (telemetry), `current_screen`,
  `ui: UiState`, `level: LevelState`, `level_context`, and an **optional ECS registry**
  (`ecs_entities`, `create_entity`, `get_entities_with`) that runs *in parallel* with the lists.
- **`GameConfig`** (`config/game_config.py`) — every difficulty/feel/juice/graphics toggle.
  Notable **dev defaults**: `enable_telemetry=True`, `testing_mode=True`, `enable_dda=False`
  (enable with `--dda`/`GAME_ENABLE_DDA=1`), `target_fps=0`, `world_scale=1.33`. `apply_safe_mode()` disables GPU/CUDA/telemetry.
- **`LevelState`** (`level_state.py`) — arena geometry: trapezoid/triangle walls,
  destructible/moveable/giant/super_giant blocks, `hazard_obstacles`, `moving_health_zone`.

### 4.4 Scene stack & screen flow
`SceneStack` (`scenes/base.py`) is a LIFO of scenes. The current scene drives
input/update/render. State ids are the `STATE_*` strings in `constants.py`:
`TITLE, MENU, QUICK_LAUNCH, PLAYING, PAUSED, ENDURANCE, GAME_OVER, SAVE_GAME, LOAD_GAME,
TELEMETRY_VIEWER, NAME_INPUT, HIGH_SCORES, VICTORY, MAP_TEST` (+ string‑literal
`"SHADER_TEST"`/`"SHADER_SETTINGS"` used by some scenes but not in `constants.py`).
`constants.py` also declares `STATE_CONTINUE/MODS/WAVE_BUILDER/CONTROLS`, but these have **no
scene in `create_scene_for_state`** and are otherwise unreferenced (declared, not yet wired).

Typical flow: `TITLE → MENU(OptionsScene) → PLAYING → (push) PAUSED → pop`, and on death/win
`PLAYING → GAME_OVER` or `PLAYING → VICTORY → NAME_INPUT → HIGH_SCORES`.

**Transitions are in migration (dual API):**
- Legacy: `Scene.handle_input()` returns a **dict** (`{"screen":..., "pop":True, "quit":True,
  "start_game":True, "try_again":True, "restart":True, ...}`).
- New: `handle_input_transition()` / `update_transition()` return a `SceneTransition`
  (`scenes/transitions.py`: kinds `NONE/PUSH/POP/REPLACE/QUIT_GAME`).
- `apply_scene_transition()` executes transitions; **`REPLACE` clears the whole stack** (not a
  top‑only swap). `game.py` has a big **fallback coordinator** that re‑reads the scene's
  `_last_input_result` and manually applies flags the transition path doesn't cover.

### 4.5 Simulation pipeline (two tiers — a common confusion)
`create_app` builds `_update_simulation(sim_dt, gs, app_ctx)` which iterates the **outer**
list `simulation_systems.SIMULATION_SYSTEMS` (signature `(gs, sim_dt, app_ctx)`):

```
player/ability timers → damage/message cleanup → shield/jump → hazards → entity.update() hooks →
defeat-message cleanup → pickup effects → REGISTRY SYSTEMS → juice timers → beam/limit cleanup →
enforce entity caps → camera follow
```

The "REGISTRY SYSTEMS" step runs the **inner** list `systems/registry.py:SIMULATION_SYSTEMS`
(signature `update(state, dt)`), whose **order is load‑bearing**:

```
movement_system → collision_system → spawn_system → ai_system
```

`systems/__init__.py` also exposes `GAMEPLAY_SYSTEMS = list(registry SIMULATION_SYSTEMS)`.
⚠️ There are therefore **two objects named `SIMULATION_SYSTEMS`** (outer in
`simulation_systems.py`, inner in `systems/registry.py`) plus `GAMEPLAY_SYSTEMS`. Do not
conflate them. Telemetry, input, and audio are **not** in either list — they run from the loop.

Systems are stateless; they read a big **`level_context`** dict (built in
`level_utils.make_level_context`) for geometry lists, callables (`move_player`, `move_enemy`,
`clamp`, `kill_enemy`, `spawn_enemy_projectile`, `apply_pickup_effect`, `update_friendly_ai`,
`telemetry`, `play_sfx`, …), and tuning. Anything a system needs should be threaded through
`state.level_context`, not imported globally.

### 4.6 Rendering pipeline
Dispatch: `engine/render_loop.py:render_current_scene(...)`.
- **Gameplay (`PLAYING`/`ENDURANCE`)**: builds/caches a `gameplay_ctx` dict + a
  `RenderContext` (`rendering/context.py`) and calls
  `render_gameplay_with_optional_shaders` (`rendering/shaders/pipeline.py`), which renders the
  **five‑phase pipeline** from `screens/gameplay.py`:
  1. background (theme fill, tile map, terrain, pickups) — `rendering/world/`
  2. entities (allies, enemies, player) — `rendering/world/entities.py`
  3. projectiles + particles + beams — `rendering/world/projectiles.py`
  4. HUD (health, score, cooldowns, FPS graph) — `systems/ui/core.py`
  5. overlays (damage numbers, wave banner, screen flash) — `systems/ui/core.py`
  Then optional CPU/GPU post‑process and a final blit; the world surface may be downscaled.
- **Menus/overlays**: `RenderContext.for_menu(ctx)` then `scene.render(...)`; pause can render a
  frozen gameplay frame under a shader/overlay.
- ⚠️ `scenes/gameplay.py:GameplayScene.render()` exists but the production path **bypasses it**
  (the render loop calls the shader wrapper directly). Debug‑overlay code inside it won't run in
  normal play.

---

## 5. Entities (dict‑first, with wrappers and an optional ECS)

There is **no single entity model**; three representations coexist:
1. **Plain dicts** — bullets, enemy/friendly projectiles, pickups, missiles, explosions,
   laser beams, decoys, hazards. This is the dominant runtime representation.
2. **Thin wrapper classes** — `entities/enemy.py:Enemy` and `entities/friendly.py:Friendly`
   wrap an inner dict, expose dict‑ and attribute‑access, cache hot fields; their
   `update()/draw()` are **no‑ops** (logic lives in systems). Enemies live in `gs.enemies`,
   allies in `gs.friendly_ai`.
3. **Optional ECS** — `ecs_components.py` dataclasses stored in `GameState.ecs_entities`,
   queried via `get_entities_with(...)`. Present but only lightly used; runs parallel to lists.

Because of this, you will see `isinstance(e, dict)` guards and functions annotated `dict` that
actually receive `Enemy`. Treat that as intentional duck typing during migration.

**Factories / definitions:**
- `enemies/factory.py:make_enemy_from_template(template, hp_scale, speed_scale) → Enemy`
  (boss sometimes built as a raw dict then wrapped).
- `allies.py:make_friendly_from_template(...) → Friendly`, plus `update_friendly_ai`.
- `pickups.py` — `PICKUP_HANDLERS` registry + `apply_pickup_effect(...)`.
- Data: `config/enemy_data.py` (`ENEMY_TEMPLATES`, `BOSS_TEMPLATE`, friendly templates),
  `config/enemy_defs.py` (`get_enemy_def(type_id)`; boss id is `"FINAL_BOSS"`),
  `config/projectile_defs.py` (`WEAPON_CONFIGS`, unlock order), `config/balance.py` (canonical
  numeric tuning — damage, cooldowns, speeds, aggro, scoring).

Module‑layout note: the old shadowed **`enemies.py` (root) has been deleted.** It was unreachable
anyway — Python resolves the `enemies/` package before a same‑named module, so `import enemies`
always loads `enemies/__init__.py`. Import factories/AI from the `enemies/` package.

---

## 6. `systems/` quick reference

**In the fixed‑step registry (order matters):**
- `movement_system.py` — player/enemy/bullet/projectile/missile motion; targeting‑slot cache;
  optional GPU bullet batch when `config.use_gpu_physics`.
- `collision_system.py` — orchestrator; builds a per‑frame block grid, then delegates to the
  `systems/collision/` package (projectile/hazard/explosion handlers + grid helpers) plus
  `collision_player.py` and `collision_pickups.py`; shared helpers live in `collision_common.py`.
  (The old monolithic `collision_projectiles.py` was consolidated into this package — see §10.)
- `spawn_system.py` — wave timers, spawner minions, next‑wave/victory; `start_wave(...)`;
  custom‑map spawns via `systems/spawning/map_spawn.py`.
- `ai_system.py` — enemy special behaviors + shooting; ally AI via `level_context`.

**Called outside the registry:** `input_system.py` (`handle_gameplay_input`),
`telemetry_system.py` (`update_telemetry`, `log_frame_time`), `audio_system.py`
(`play_sfx`/`play_music`), `ui_system.py` → `systems/ui/core.py` (HUD/overlays, read‑only),
`camera.py` (singleton via `get_camera()`), `spatial_grid.py` (frame‑cached grids for
collision), `projectile_spawning.py`, `enemy_death.py`, `fps_tracker.py`, `perf_timing.py`
(`perf_timer` context manager), `idle_enemy_animation.py` (decorative pause‑screen enemies).

Performance patterns used pervasively: spatial‑grid neighbor queries, surface/text caching,
`screen.blits()` batching, camera culling (`camera.is_visible`), bulk removal via `id()` sets +
slice reassignment (avoid `list.remove()` in loops), and per‑entity caps enforced each tick.

---

## 7. Supporting subsystems

- **Maps & editor (`maps/`)** — tile grid JSON (`maps/data/*.json`, `TILE_SIZE=64`), loaded via
  `map_loader`, converted to `LevelState.static_blocks` by `level_converter.map_to_level_state`,
  and spawned via `systems/spawning/map_spawn.py`. The **map editor** (`maps/editor/` mixins,
  launched by `run_editor.py`) is fully standalone (its own loop; not the scene system).
  Only *partially* integrated into gameplay: tile collision (`maps/collision.py`) and A*
  (`maps/pathfinding.py`) exist but are **not wired into the live movement/AI**.
- **Telemetry (`telemetry/`)** — SQLite `game_telemetry.db` (WAL). `writer.py` is the client
  (`Telemetry` / `NoOpTelemetry`), recreated **per run** in `engine/run_manager.py`.
  `systems/telemetry_system.py` samples position/run‑state/frame‑time from the main loop.
  `event_bus_handlers.py` wires a couple of `EventBus` events (`enemy_killed` → score).
  High scores use a **separate** `high_scores.db`. Viz: `telemetry_viz/` + `visualize.py`
  (matplotlib). See `telemetry/README.md` and `telemetry/sql/`.
- **DDA / ML (`ml/`)** — offline **PyTorch** model (`dda_model.py`, saved `dda_model.pt`) trained
  from telemetry `wave_summaries` (`features.py`, `train.py`, `evaluate.py`, `ab_test.py`).
  Runtime hook is gated by `config.enable_dda` (**default False**; enable with `--dda` or
  `GAME_ENABLE_DDA=1` — there is no in‑game menu toggle) and consumed in `spawn_system.py` via
  `ml/dda_integration.py`.
- **Physics (`physics_loader.py`)** — `resolve_physics()` picks the compiled C extension
  (`game_physics.c` via `setup.py build_ext --inplace`) or a pure‑Python fallback; sets
  `AppContext.using_c_physics`. Consumers use `get_physics()` for vec/distance/grid helpers.
  A separate CUDA `gpu_physics` path is referenced under `config.use_gpu_physics` but that
  module is **external and not in the repo**.
- **Shaders/effects** — two CPU effect systems coexist (`visual_effects.py` and
  `shader_effects/`), plus an optional **moderngl** GPU path (`gpu_gl_utils.py`,
  `rendering/shaders/pipeline.py`, `assets/shaders/*.frag`, `config/shaders.json`). The game runs
  fully with all shaders off (the default).

---

## 8. The many "context" objects (glossary)

This codebase passes several differently‑shaped context objects. Mixing them up is the
single easiest way to introduce a bug.

| Name | Type | Lifetime | Where built | Purpose |
|------|------|----------|-------------|---------|
| `AppContext` (`ctx`) | dataclass | app | `game_init` | Window, fonts, config, controls, telemetry, buses |
| `GameState` (`game_state`/`gs`) | dataclass | per run | `game_init` / `run_manager` | All mutable gameplay state + ECS |
| `GameConfig` (`config`) | dataclass | app (edited in menus) | `game_init` | Every toggle/tuning knob |
| `screen_ctx` | `dict` | app (reused) | `GameApp.__init__` | Menu/scene ctx: dims, fonts, high‑score callbacks, `app_ctx`, `scene_stack` |
| `gameplay_ctx` | `dict` | per frame (cached) | `rendering.context.build_gameplay_ctx` | Level lists + UI toggles for HUD/world render |
| `level_context` | `dict` | per run | `level_utils.make_level_context` | Geometry + callables threaded into simulation systems |
| `RenderContext` | class | per frame | `rendering/context.py` | screen/fonts/dims/camera + world↔screen helpers |
| `CtxHelper` | class | wraps a dict | `context.py` | Typed accessors over a `ctx` dict |

Rule of thumb: **simulation systems** read `game_state` + `state.level_context`;
**renderers** read `game_state` + `gameplay_ctx` + `RenderContext`; **scenes/menus** read
`screen_ctx` (which carries `app_ctx`).

---

## 9. Conventions & invariants to respect in review

- **Don't reorder** `systems/registry.py:SIMULATION_SYSTEMS` (movement→collision→spawn→ai) without
  understanding the data dependencies documented at the top of that file.
- **Simulation is fixed‑step (1/60).** Gameplay logic must scale by the `sim_dt` it receives, not
  by render `dt`. Rendering/animation may use real `dt`.
- **Renderers are read‑only** with respect to gameplay state (HUD/overlays in `systems/ui/core.py`
  must not mutate `GameState`).
- **Thread new system dependencies through `level_context`/`gameplay_ctx`**, not module globals.
- **Every active screen must have a scene on the stack** — `game.py` asserts this; simulation code
  that flips `game_state.current_screen` directly (game over / victory / name input) relies on the
  loop to resync the stack.
- **Prefer bulk/id‑based removal** over `list.remove()` in hot loops (existing pattern).
- **`GameState` is a dataclass with declared defaults — read fields directly.** Use
  `state.field`, not `getattr(state, "field", default)`. ~155 such defensive lookups already
  exist for fields that *are* declared; each converts a typo from an `AttributeError` into a
  silent default. Reserve `getattr` for the genuinely dynamic attributes
  (`_collision_frame_id`, `fire_pressed`, `dda_adjustment`, `custom_map`, render caches) — and
  prefer declaring those on the dataclass instead.
- **Use `game_logging.get_logger(__name__)`, not `print()`.** 363 `print()` calls across 44
  modules currently bypass the logging module that exists for exactly this. Don't add more.
- **Guard optional deps** (`moderngl`, `torch`, C ext, CUDA) behind try/except or config flags;
  the game and tests must run with core deps only (CI enforces this).
- **Keep the three *live* compat shims working** if you touch what they re‑export
  (`rendering_shaders.py`, `systems/ui_system.py`, `scenes/shader_settings.py` — see §10) — or
  update all call sites. **Do not create new compat shims.** If a module moves, update the
  importers. Re‑export modules are how this codebase ended up with three of several things.
- **Follow existing docstring style** (module‑level summary describing role + key functions) and
  avoid narrating obvious code in comments.

---

## 10. Known debt — removal work order

Treat this section as a **work order, not a field guide.** The duplication below is debt
scheduled for removal, not architecture to navigate around.

**Do not add to this list.** Do not introduce a fourth entity model, a third collision path, or a
new compat shim. If you find yourself writing a parallel implementation "for safety," delete the
old one instead.

✅ = verified against the tree. Unmarked items still need checking before acting.

**Duplicate / parallel implementations (dead‑vs‑live confusion):**
- ✅ **Collision consolidation — DONE.** The monolithic `systems/collision_projectiles.py` was
  merged into the `systems/collision/` package (`helpers/hazards/player_bullets/enemy_projectiles/
  friendly_projectiles/explosions.py`) and **deleted**. `collision_system.py` now delegates to
  that package (the live path) alongside `collision_player.py`/`collision_pickups.py`/
  `collision_common.py`; no parallel copy remains. `collision_movement.py` (wired via
  `level_context`) still holds `move_enemy_with_push`.
- **Live compat shims — keep these working:** `rendering_shaders.py`→`rendering/shaders/pipeline.py`
  (5 importers), `systems/ui_system.py`→`systems/ui/core.py` (2), `scenes/shader_settings.py`→
  split modules (3 importers). No name collision; these actually load.
- ✅ **Shadowed files — DELETED.** `enemies.py`, `rendering/world.py`, and `maps/editor.py`
  (each shadowed by a same‑named package, so never importable) have been removed, together with
  six other unreachable modules (`file_utils.py`, `threading_utils.py`, `gpu_integration_example.py`,
  `shader_effects/uniforms.py`, `telemetry/reader.py`, `test_gpu.py`).
- ✅ `enemies/movement.py:move_enemy_with_push_cached` (124 lines) has **zero call sites**;
  superseded by `collision_movement.move_enemy_with_push` (wired via `level_context`). Delete.
- ✅ `screens/__init__.py:SCREEN_HANDLERS` has **zero references repo‑wide** — a dead registry
  left from the pre‑scene‑stack state machine. Delete.
- Two CPU effect systems (`visual_effects.py` vs `shader_effects/`) with overlapping profiles;
  they can stack unintentionally. ✅ The `apply_pause_effects()` (`visual_effects.py`) flag bug —
  it gated on `enable_menu_shaders` instead of `enable_pause_shaders` — has been **fixed**.

**Wiring gaps:**
- The GPU `ShaderPipelineManager` built from `config/shaders.json`
  (`apply_shader_settings_to_pipeline`) is **populated but not executed** in the gameplay render
  path — those settings only affect `scenes/shader_test.py`. `use_gpu_shader_pipeline` actually
  toggles CPU muzzle/rocket glows, not the GPU chain (misleading name).
- `rendering/shaders/pipeline.py` calls `screens/gameplay.render` with a `RenderContext` where the
  function signature expects `app_ctx` first — works via duck typing but is fragile.
- Maps: tile collision + pathfinding are not used by the live game; `TILE_SIZE` is defined in
  several places; `map_spawn.py` couples to `maps.editor`.

**Telemetry/ML:**
- ✅ **Fixed:** `map_spawn.py` used to call a non‑existent `telemetry.log_wave_start(...)` inside
  `except Exception: pass`, so custom‑map wave starts were silently never recorded. It now calls
  `telemetry.log_wave(WaveEvent(..., event_type="start"))` and logs failures instead of swallowing
  them.
- ✅ `ml/ab_test.py:_enable_dda()` calls `dda.enable()` on the singleton but never sets
  `config.enable_dda`; `spawn_system.py:49` gates on that flag (default `False`; the real enable
  path is now the `--dda`/`GAME_ENABLE_DDA` flag), so the
  "DDA on" arm runs with DDA off. Any A/B results collected so far are a null comparison.
- Several other `log_*` methods and wave `"end"` events have schema/writer support but no live
  call sites, so some plots may show "no data".

**Config defaults that surprise reviewers:** `testing_mode=True` and `enable_telemetry=True` by
default in `game_init.build_app_context`; `world_scale=1.33`; `target_fps=0` (uncapped).

**Scene/transition edges:** dual input API + `game.py` fallback can double‑process or miss flags;
`REPLACE` clears the whole stack; simulation‑driven `current_screen` changes are only partially
synced back to the stack (game over/victory are; a name‑input path from `ai_system` may not be).

---

## 11. Where to make common changes

| Goal | Touch these |
|------|-------------|
| New enemy type | `config/enemy_data.py` (template) → `config/enemy_defs.py` (lookup) → behavior in `systems/ai_system.py` (+ `enemies/`) → `tests/test_enemy_behavior.py` |
| New weapon / projectile | `config/projectile_defs.py` (`WEAPON_CONFIGS`, unlock order) + `config/balance.py` (numbers) → spawn in `systems/projectile_spawning.py` → unlock in `pickups.py` |
| Tune difficulty/feel | `config/balance.py` (canonical numbers), `config/game_config.py` (toggles/feel profiles), `constants.py` (difficulty/class multipliers) |
| New scene/screen | add `STATE_*` in `constants.py`, create scene in `scenes/`, register in `scenes/transitions.py:create_scene_for_state`, wire a transition from an existing scene |
| New simulation system | add module in `systems/`, insert into `systems/registry.py` at the right position, thread deps via `level_context`, add a test |
| New render effect | CPU: `shader_effects/` (+ a `SHADER_PROFILES` entry) or `visual_effects.py`; GPU: `assets/shaders/*.frag` + `shader_effects/registry.py` + `config/shaders.json` |
| New pickup | `pickups.py` (`PICKUP_HANDLERS` + effect), spawn in `systems/spawn_helpers.py` |
| New map | edit with `python run_editor.py`; saved to `maps/data/*.json`; play via pause → Map Test |

---

## 12. Testing

- `pytest` (config `pytest.ini`: `testpaths=tests`, verbose). `tests/conftest.py` forces headless
  SDL and provides pygame fixtures.
- ~30+ test files grouped by area: systems (`test_collision_system`, `test_movement_system_basic`,
  `test_spawn_system_basic`, `test_spatial_grid`, `test_registry_order`, `test_input_system`),
  entities/data (`test_enemy_behavior`, `test_projectiles`, `test_pickups`, `test_defs`),
  scenes/UI (`test_scene_stack`, `test_integration`, `test_menu_input`, `test_menu_helpers`),
  maps (`test_maps`), telemetry (`test_telemetry_init`, `test_telemetry_enemy_killed_event`,
  `test_event_bus`), ML (`test_ml_dda`), effects (`test_visual_effects`, `test_shader_effects`),
  plus asset/audio/camera/respawn/save/import smoke tests.
- ⚠️ **Coverage is 36% overall and inverted:** the largest, riskiest modules are the least
  tested — `game_app.py` 5%, `systems/collision/explosions.py` 5%, `systems/ui/core.py` 8%
  (462 stmts), `rendering/shaders/pipeline.py` 9%, `scenes/options/core.py` 20% (513 stmts),
  and the `systems/collision/` package (projectile-collision code, formerly the
  `collision_projectiles.py` monolith). The suite is 439 fast unit tests over pure
  helpers; it will **not** catch a regression in collision, movement, or rendering. Do not
  treat green CI as proof a gameplay change is safe.
- **CI must stay green with core deps only** (no torch/matplotlib/moderngl guaranteed). New tests
  should skip gracefully when an optional dependency is missing.

---

## 13. Quick orientation checklist for a reviewer

1. Is the change in the **live path** or a parallel/legacy module (see §10)? Grep for call
   sites. If it lands in a parallel module, the correct fix is usually to **delete that module**,
   not to patch both copies.
2. Does it respect the **fixed‑step sim** (uses `sim_dt`) and the **system order**?
3. Does it thread new deps through `level_context`/`gameplay_ctx`/`screen_ctx` (not new globals)?
4. Does it keep **optional deps** guarded so `pytest` and `python game.py` work with core deps?
5. If it touches a **shim/re‑export**, are all call sites and the shim consistent?
6. Are **scene transitions** consistent across the dual API + `game.py` fallback?
7. Is there a relevant **test**, and will it pass on Python 3.10 and 3.12 headless?
```
