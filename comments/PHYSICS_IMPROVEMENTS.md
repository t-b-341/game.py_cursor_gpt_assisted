# game_physics.c Improvements: Reasonable, Tested Steps

## Test baseline

Before changing `game_physics.c`, run the physics tests so C and Python behavior stay in sync:

```bash
pytest tests/test_physics_module.py -v
```

With Python fallback (no C extension):

```bash
python -c "from physics_loader import resolve_physics; resolve_physics(force_python=True)"
pytest tests/test_physics_module.py -v
```

## Completed steps (already in tree)

1. **find_dodge_threats_c** – Use squared time comparison (`dist_sq < T² * vel_len_sq`) to avoid `sqrt` in the hot path.
2. **find_in_radius_c** – Two-pass: count then pre-allocate list and fill (no `PyList_Append` reallocs).
3. **get_grid_cell_indices_for_rect_c** – Pre-allocate result with exact size, fill with `PyList_SET_ITEM`.
4. **check_bullet_collisions_c** – Cache all target rects in a C array once; inner loop uses cached rects (O(bullets + targets) Python calls instead of O(bullets × targets)).
5. **batch_rect_collisions_c** – Cache all B rects in a C array once; inner loop is pure C collision check.
6. **can_move_rect_c** – Early return when `other_rects_list` length is 0.

## Suggested next steps (one at a time, run tests after each)

- **can_move_rect flat API** – Add a new C function (e.g. `can_move_rect_batch_c`) that takes `(rect_x, rect_y, rect_w, rect_h, dx, dy, other_x_list, other_y_list, other_w_list, other_h_list, screen_w, screen_h)`. Python extracts rect data once and calls this; C does one pass over lists. Add tests in `test_physics_module.py` that call the new path and match `can_move_rect` behavior.
- **update_bullets_c** – Reduce Python attribute access: e.g. accept flat arrays (or a single list of 6-tuples) for position/velocity and write back positions only. Requires a small API change and tests for bullet update + offscreen removal.
- **Buffer protocol** – If the game ever passes numpy/array data for positions or rects, use `PyObject_GetBuffer` in C to iterate over contiguous memory and avoid per-element `PyList_GetItem`. Add tests that pass list inputs (unchanged) and optionally numpy inputs if supported.

## Workflow

1. Change one function or add one new function in `game_physics.c`.
2. Run `python setup.py build_ext --inplace`.
3. Run `pytest tests/test_physics_module.py tests/test_collision_system.py tests/test_movement_system_basic.py tests/test_spatial_grid.py -v`.
4. Commit when green.
