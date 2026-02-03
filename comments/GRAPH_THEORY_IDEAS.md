# Incorporating Graph Theory Into the Project

Graph theory is already used implicitly in several places. Below are ways to make it explicit and add new graph-based features.

---

## Where You Already Use Graphs

- **Pathfinding** (`maps/pathfinding.py`): A* on an implicit graph—nodes are tile cells `(x, y)`, edges are walkable neighbor links (4- or 8-directional). `PathNode` is the search node; neighbors are generated on the fly from the grid.
- **Map editor flood fill** (`maps/editor/tools.py`): BFS over the grid—nodes are cells, edges are same-tile adjacency. Used to fill connected regions.

So the **map grid is already an implicit graph**. Making that explicit can enable more algorithms and reuse.

---

## Concrete Ideas

### 1. Explicit navigation graph (waypoints / regions)

**Idea:** Build a graph where nodes are:
- **Option A:** Walkable tiles (same as now, but precompute adjacency once).
- **Option B:** “Regions” or “rooms” (e.g. from a level layout), with edges = door/corridor connections.
- **Option C:** Waypoints (e.g. spawn points, health zone, key tiles); edges = paths between them (from A*).

**Use:**  
- Faster pathfinding (search on a small graph instead of full grid).  
- “High-level” AI: move between regions first, then path within region.  
- Spawn logic: e.g. only spawn in regions that have a path to the player (reachability).

**Where in code:**  
- Add a small module (e.g. `maps/nav_graph.py` or under `maps/`) that builds the graph from `MapGrid` (and optionally from `spawn_points`, `player_spawn`, health zone).  
- Pathfinding can stay in `pathfinding.py` but accept either grid or graph + heuristic.

---

### 2. Spawn / wave dependency graph (DAG)

**Idea:** Model wave progression as a directed acyclic graph (DAG):  
- Nodes = waves or “milestones” (e.g. wave 1, wave 5 boss, wave 10).  
- Edges = “unlocks after” (e.g. wave 5 unlocks after wave 4).  
- Optional: nodes = spawn points with `wave_min`/`wave_max`; edges = “this spawn is available after that wave.”

**Use:**  
- Clear definition of progression and branching (e.g. different difficulty paths).  
- Validation: no cycles, all waves reachable from start.  
- Tooling: visualize or balance “wave tree.”

**Where in code:**  
- `maps/spawn_point.py` and wave logic (e.g. in `config/enemy_data.py` or spawn system) already have `wave_min`/`wave_max`. A small `WaveGraph` or `SpawnDependencyGraph` could wrap that and expose predecessors/successors.

---

### 3. Threat / aggro as a graph

**Idea:**  
- Nodes = entities (player, allies, decoys, enemies).  
- Directed edges = “is currently targeting” or “is in aggro range of.”  
- Weights = distance or priority (you already have aggro priority in `enemies/ai.py`).

**Use:**  
- “Who is targeting the player?” → in-neighbors of player.  
- “Threat chain”: which enemies are distracted by decoys/allies (graph traversal).  
- Analytics: distribution of in-degree (how often one entity is focused by many).

**Where in code:**  
- `enemies/ai.py` already computes “nearest threat.” You could add a lightweight `ThreatGraph` that updates each frame or when targets change, and expose it for AI or telemetry.

---

### 4. Level connectivity (reachability)

**Idea:**  
- One node per tile (or per “room” if you add regions).  
- Edges = walkable adjacency.  
- Use BFS/DFS from player spawn to compute “reachable set” or “distance field.”

**Use:**  
- Spawn only in reachable cells (so enemies don’t spawn behind one-way walls).  
- Map editor: “Is the whole level connected?” (one component?).  
- Optional: “distance from player spawn” per tile for difficulty or pacing.

**Where in code:**  
- `MapGrid` in `maps/map_grid.py` plus tile walkability from registry. A function like `reachable_from(map_grid, start_xy)` or `connected_components(map_grid)` in `maps/pathfinding.py` or `maps/nav_graph.py` would fit.

---

### 5. State machines as graphs (enemy / game state)

**Idea:**  
- Nodes = states (e.g. “idle”, “chase”, “flee”, “attack”).  
- Edges = allowed transitions (with optional conditions).  
- This is the standard “state machine as directed graph.”

**Use:**  
- Clear visualization and debugging of AI behavior.  
- Validation: no dead states, no unreachable states.  
- Same idea for game state (menu → play → pause → game over).

**Where in code:**  
- Enemy behavior is currently logic in `enemies/ai.py` and movement. A small explicit state graph (e.g. dict of state → list of (condition, next_state)) could sit beside it and drive or document behavior.

---

### 6. Telemetry / analytics

**Idea:**  
- **Cause–effect:** “death events” as nodes; edges = “likely caused by” (e.g. last damage source, last wave).  
- **Session as path:** nodes = “game states” (e.g. wave number + HP bucket); edges = transitions between them.  
- **Flow:** “pressure” from spawn points toward player as flow on a graph (nodes = regions, edges = movement direction).

**Use:**  
- Understand failure modes; which sources of damage lead to death.  
- Session replay or clustering of “similar runs” by path through state space.

**Where in code:**  
- `telemetry/` already has events (e.g. `player_damage`, `player_deaths`). Post-processing or a small script could build a graph from run data and run centrality or path analysis.

---

## Suggested starting points

1. **Reachability / connectivity**  
   Add `reachable_from(map_grid, start_xy)` (BFS) and optionally `connected_components(map_grid)`. Use it in the map editor (“is map connected?”) and in spawn logic (“spawn only in reachable tiles”). Small change, clear graph concept.

2. **Explicit nav graph**  
   Add a thin layer that, from `MapGrid`, builds an adjacency structure (e.g. `dict[(x,y)] -> list[(x,y)]`) for walkable tiles, and optionally a waypoint graph from spawn points + player spawn. Then pathfinding can work over that graph instead of recomputing neighbors every time.

3. **Wave DAG**  
   If you add more complex wave rules (e.g. “wave 3 only if player cleared wave 2 in under 60s”), a small `WaveGraph` (nodes = waves, edges = prerequisites) keeps logic clear and testable.

If you tell me which of these you want to implement first (e.g. reachability, nav graph, or wave DAG), I can outline concrete types and function signatures for your codebase.
