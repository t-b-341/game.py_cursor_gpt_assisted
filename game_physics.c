/* High-performance physics and collision detection module for game.py
 * Compile with: python setup.py build_ext --inplace
 *
 * Efficiency: hot paths avoid sqrt where possible (e.g. find_dodge_threats uses
 * squared time comparison). Batch functions pre-allocate result lists or cache
 * rect/position arrays to reduce Python API calls and list reallocs.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>
#include <stdbool.h>
#include <stdlib.h>

/* Vector2 structure for efficient calculations */
typedef struct {
    double x, y;
} Vector2;

/* Rect structure matching pygame.Rect */
typedef struct {
    int x, y, w, h;
} Rect;

/* Helper: Normalize a vector */
static void normalize_vector(Vector2 *v) {
    double len = sqrt(v->x * v->x + v->y * v->y);
    if (len > 0.0001) {
        v->x /= len;
        v->y /= len;
    }
}

/* Helper: Calculate vector from point A to point B (normalized) */
static Vector2 vec_toward_internal(double ax, double ay, double bx, double by) {
    Vector2 result;
    result.x = bx - ax;
    result.y = by - ay;
    normalize_vector(&result);
    return result;
}

/* Fast rect-rect collision detection */
static bool rect_collide(const Rect *a, const Rect *b) {
    return !(a->x + a->w < b->x || b->x + b->w < a->x ||
             a->y + a->h < b->y || b->y + b->h < a->y);
}

/* Check if a rect can move without colliding with a list of rects */
static PyObject* can_move_rect_c(PyObject* self, PyObject* args) {
    int rect_x, rect_y, rect_w, rect_h, dx, dy;
    PyObject* other_rects_list;
    int screen_width, screen_height;
    
    if (!PyArg_ParseTuple(args, "iiiiiiOii", 
                          &rect_x, &rect_y, &rect_w, &rect_h,
                          &dx, &dy, &other_rects_list,
                          &screen_width, &screen_height)) {
        return NULL;
    }
    
    // Test rect after movement
    Rect test_rect;
    test_rect.x = rect_x + dx;
    test_rect.y = rect_y + dy;
    test_rect.w = rect_w;
    test_rect.h = rect_h;
    
    if (test_rect.x < 0 || test_rect.x + test_rect.w > screen_width ||
        test_rect.y < 0 || test_rect.y + test_rect.h > screen_height) {
        Py_RETURN_FALSE;
    }

    Py_ssize_t len = PyList_Size(other_rects_list);
    if (len == 0)
        Py_RETURN_TRUE;
    for (Py_ssize_t i = 0; i < len; i++) {
        PyObject* other_rect = PyList_GetItem(other_rects_list, i);
        if (!other_rect) continue;
        
        // Extract rect attributes (assuming pygame.Rect object)
        PyObject* x_attr = PyObject_GetAttrString(other_rect, "x");
        PyObject* y_attr = PyObject_GetAttrString(other_rect, "y");
        PyObject* w_attr = PyObject_GetAttrString(other_rect, "w");
        PyObject* h_attr = PyObject_GetAttrString(other_rect, "h");
        
        if (!x_attr || !y_attr || !w_attr || !h_attr) {
            Py_XDECREF(x_attr);
            Py_XDECREF(y_attr);
            Py_XDECREF(w_attr);
            Py_XDECREF(h_attr);
            continue;
        }
        
        Rect other;
        other.x = (int)PyLong_AsLong(x_attr);
        other.y = (int)PyLong_AsLong(y_attr);
        other.w = (int)PyLong_AsLong(w_attr);
        other.h = (int)PyLong_AsLong(h_attr);
        
        Py_DECREF(x_attr);
        Py_DECREF(y_attr);
        Py_DECREF(w_attr);
        Py_DECREF(h_attr);
        
        if (rect_collide(&test_rect, &other)) {
            Py_RETURN_FALSE;
        }
    }
    
    Py_RETURN_TRUE;
}

/* Fast vector toward calculation */
static PyObject* vec_toward_c(PyObject* self, PyObject* args) {
    double ax, ay, bx, by;
    
    if (!PyArg_ParseTuple(args, "dddd", &ax, &ay, &bx, &by)) {
        return NULL;
    }
    
    Vector2 v = vec_toward_internal(ax, ay, bx, by);
    
    // Return as tuple (x, y)
    return Py_BuildValue("(dd)", v.x, v.y);
}

/* Batch update bullet positions */
static PyObject* update_bullets_c(PyObject* self, PyObject* args) {
    PyObject* bullets_list;
    double dt;
    int screen_width, screen_height;
    
    if (!PyArg_ParseTuple(args, "Odii", &bullets_list, &dt, 
                          &screen_width, &screen_height)) {
        return NULL;
    }
    
    Py_ssize_t len = PyList_Size(bullets_list);
    PyObject* result = PyList_New(0);
    if (!result) return NULL;
    
    for (Py_ssize_t i = 0; i < len; i++) {
        PyObject* bullet = PyList_GetItem(bullets_list, i);
        if (!bullet) continue;
        
        // Get rect and velocity
        PyObject* rect = PyObject_GetAttrString(bullet, "rect");
        PyObject* vel = PyObject_GetAttrString(bullet, "vel");
        
        if (!rect || !vel) {
            Py_XDECREF(rect);
            Py_XDECREF(vel);
            continue;
        }
        
        // Get velocity components
        PyObject* vel_x = PyObject_GetAttrString(vel, "x");
        PyObject* vel_y = PyObject_GetAttrString(vel, "y");
        
        if (!vel_x || !vel_y) {
            Py_XDECREF(rect);
            Py_DECREF(vel);
            Py_XDECREF(vel_x);
            Py_XDECREF(vel_y);
            continue;
        }
        
        double vx = PyFloat_AsDouble(vel_x);
        double vy = PyFloat_AsDouble(vel_y);
        
        // Get rect position
        PyObject* rect_x = PyObject_GetAttrString(rect, "x");
        PyObject* rect_y = PyObject_GetAttrString(rect, "y");
        
        if (!rect_x || !rect_y) {
            Py_XDECREF(rect);
            Py_DECREF(vel);
            Py_DECREF(vel_x);
            Py_DECREF(vel_y);
            Py_XDECREF(rect_x);
            Py_XDECREF(rect_y);
            continue;
        }
        
        int x = (int)PyLong_AsLong(rect_x);
        int y = (int)PyLong_AsLong(rect_y);
        
        // Update position
        x += (int)(vx * dt);
        y += (int)(vy * dt);
        
        // Check if offscreen
        PyObject* rect_w = PyObject_GetAttrString(rect, "w");
        PyObject* rect_h = PyObject_GetAttrString(rect, "h");
        
        if (rect_w && rect_h) {
            int w = (int)PyLong_AsLong(rect_w);
            int h = (int)PyLong_AsLong(rect_h);
            
            bool offscreen = (x + w < 0 || x > screen_width ||
                             y + h < 0 || y > screen_height);
            
            if (!offscreen) {
                // Update rect position - properly manage new references
                PyObject* new_x = PyLong_FromLong(x);
                PyObject* new_y = PyLong_FromLong(y);
                if (new_x && new_y) {
                    PyObject_SetAttrString(rect, "x", new_x);
                    PyObject_SetAttrString(rect, "y", new_y);
                    PyList_Append(result, bullet);
                }
                Py_XDECREF(new_x);
                Py_XDECREF(new_y);
            }
            
            Py_DECREF(rect_w);
            Py_DECREF(rect_h);
        }
        
        Py_DECREF(rect);
        Py_DECREF(vel);
        Py_DECREF(vel_x);
        Py_DECREF(vel_y);
        Py_DECREF(rect_x);
        Py_DECREF(rect_y);
    }
    
    return result;
}

/* Fast distance calculation */
static PyObject* distance_c(PyObject* self, PyObject* args) {
    double x1, y1, x2, y2;
    
    if (!PyArg_ParseTuple(args, "dddd", &x1, &y1, &x2, &y2)) {
        return NULL;
    }
    
    double dx = x2 - x1;
    double dy = y2 - y1;
    double dist = sqrt(dx * dx + dy * dy);
    
    return PyFloat_FromDouble(dist);
}

/* Fast distance squared (avoids sqrt) */
static PyObject* distance_squared_c(PyObject* self, PyObject* args) {
    double x1, y1, x2, y2;
    
    if (!PyArg_ParseTuple(args, "dddd", &x1, &y1, &x2, &y2)) {
        return NULL;
    }
    
    double dx = x2 - x1;
    double dy = y2 - y1;
    double dist_sq = dx * dx + dy * dy;
    
    return PyFloat_FromDouble(dist_sq);
}

/* Helper: Extract rect components from a Python object with "rect" attribute.
 * Returns true on success, false on failure (with refs cleaned up). */
static bool extract_rect_components(PyObject* obj, Rect* out) {
    PyObject* rect = PyObject_GetAttrString(obj, "rect");
    if (!rect) return false;
    
    PyObject* x_attr = PyObject_GetAttrString(rect, "x");
    PyObject* y_attr = PyObject_GetAttrString(rect, "y");
    PyObject* w_attr = PyObject_GetAttrString(rect, "w");
    PyObject* h_attr = PyObject_GetAttrString(rect, "h");
    
    bool success = (x_attr && y_attr && w_attr && h_attr);
    
    if (success) {
        out->x = (int)PyLong_AsLong(x_attr);
        out->y = (int)PyLong_AsLong(y_attr);
        out->w = (int)PyLong_AsLong(w_attr);
        out->h = (int)PyLong_AsLong(h_attr);
    }
    
    Py_XDECREF(x_attr);
    Py_XDECREF(y_attr);
    Py_XDECREF(w_attr);
    Py_XDECREF(h_attr);
    Py_DECREF(rect);
    
    return success;
}

/* Batch collision check between bullets and targets.
 * Caches target rects once to avoid O(bullets * targets) Python attribute lookups. */
static PyObject* check_bullet_collisions_c(PyObject* self, PyObject* args) {
    PyObject* bullets_list;
    PyObject* targets_list;

    if (!PyArg_ParseTuple(args, "OO", &bullets_list, &targets_list)) {
        return NULL;
    }

    Py_ssize_t bullets_len = PyList_Size(bullets_list);
    Py_ssize_t targets_len = PyList_Size(targets_list);

    PyObject* collisions = PyList_New(0);
    if (!collisions) return NULL;

    if (targets_len <= 0) return collisions;

    /* Cache all target rects once (invalid entries use .w = -1) */
    Rect* target_rects = (Rect*)malloc((size_t)targets_len * sizeof(Rect));
    if (!target_rects) {
        Py_DECREF(collisions);
        return PyErr_NoMemory();
    }
    for (Py_ssize_t j = 0; j < targets_len; j++) {
        PyObject* target = PyList_GetItem(targets_list, j);
        if (!target || !extract_rect_components(target, &target_rects[j])) {
            PyErr_Clear();
            target_rects[j].w = -1;
        }
    }

    for (Py_ssize_t i = 0; i < bullets_len; i++) {
        PyObject* bullet = PyList_GetItem(bullets_list, i);
        if (!bullet) continue;

        Rect bullet_r;
        if (!extract_rect_components(bullet, &bullet_r)) {
            PyErr_Clear();
            continue;
        }

        for (Py_ssize_t j = 0; j < targets_len; j++) {
            if (target_rects[j].w < 0) continue;
            if (rect_collide(&bullet_r, &target_rects[j])) {
                PyObject* target = PyList_GetItem(targets_list, j);
                PyObject* collision = Py_BuildValue("(OO)", bullet, target);
                if (collision) {
                    PyList_Append(collisions, collision);
                    Py_DECREF(collision);
                }
                break;
            }
        }
    }

    free(target_rects);
    return collisions;
}

/* Batch distance squared: compute squared distances from one point to many targets.
 * Args: (center_x, center_y, targets_x_list, targets_y_list)
 * Returns: list of squared distances */
static PyObject* batch_distance_squared_c(PyObject* self, PyObject* args) {
    double cx, cy;
    PyObject* targets_x;
    PyObject* targets_y;
    
    if (!PyArg_ParseTuple(args, "ddOO", &cx, &cy, &targets_x, &targets_y)) {
        return NULL;
    }
    
    Py_ssize_t len = PyList_Size(targets_x);
    Py_ssize_t len_y = PyList_Size(targets_y);
    if (len != len_y) {
        PyErr_SetString(PyExc_ValueError, "targets_x and targets_y must have same length");
        return NULL;
    }
    
    PyObject* result = PyList_New(len);
    if (!result) return NULL;
    
    for (Py_ssize_t i = 0; i < len; i++) {
        double tx = PyFloat_AsDouble(PyList_GetItem(targets_x, i));
        double ty = PyFloat_AsDouble(PyList_GetItem(targets_y, i));
        double dx = tx - cx;
        double dy = ty - cy;
        double dist_sq = dx * dx + dy * dy;
        PyList_SET_ITEM(result, i, PyFloat_FromDouble(dist_sq));
    }
    
    return result;
}

/* Find entities within radius (squared).
 * Args: (center_x, center_y, radius_squared, entities_x_list, entities_y_list)
 * Returns: list of indices of entities within radius */
static PyObject* find_in_radius_c(PyObject* self, PyObject* args) {
    double cx, cy, r_sq;
    PyObject* entities_x;
    PyObject* entities_y;
    
    if (!PyArg_ParseTuple(args, "dddOO", &cx, &cy, &r_sq, &entities_x, &entities_y)) {
        return NULL;
    }
    
    Py_ssize_t len = PyList_Size(entities_x);
    if (len == 0) {
        return PyList_New(0);
    }

    /* First pass: count how many are in radius */
    Py_ssize_t count = 0;
    for (Py_ssize_t i = 0; i < len; i++) {
        double ex = PyFloat_AsDouble(PyList_GetItem(entities_x, i));
        double ey = PyFloat_AsDouble(PyList_GetItem(entities_y, i));
        double dx = ex - cx;
        double dy = ey - cy;
        if (dx * dx + dy * dy <= r_sq)
            count++;
    }

    PyObject* result = PyList_New(count);
    if (!result) return NULL;

    /* Second pass: fill pre-allocated list (no realloc) */
    Py_ssize_t out = 0;
    for (Py_ssize_t i = 0; i < len && out < count; i++) {
        double ex = PyFloat_AsDouble(PyList_GetItem(entities_x, i));
        double ey = PyFloat_AsDouble(PyList_GetItem(entities_y, i));
        double dx = ex - cx;
        double dy = ey - cy;
        if (dx * dx + dy * dy <= r_sq) {
            PyObject* idx = PyLong_FromSsize_t(i);
            if (idx) {
                PyList_SET_ITEM(result, out, idx);
                out++;
            }
        }
    }
    return result;
}

/* Get grid cell index for a point.
 * Args: (x, y, cell_size, cols)
 * Returns: cell index */
static PyObject* get_grid_cell_index_c(PyObject* self, PyObject* args) {
    int x, y, cell_size, cols;
    
    if (!PyArg_ParseTuple(args, "iiii", &x, &y, &cell_size, &cols)) {
        return NULL;
    }
    
    int col = x / cell_size;
    int row = y / cell_size;
    int idx = row * cols + col;
    
    return PyLong_FromLong(idx);
}

/* Get grid cell indices for a rect (all cells the rect overlaps).
 * Args: (rect_x, rect_y, rect_w, rect_h, cell_size, cols, rows)
 * Returns: list of cell indices */
static PyObject* get_grid_cell_indices_for_rect_c(PyObject* self, PyObject* args) {
    int rx, ry, rw, rh, cell_size, cols, rows;

    if (!PyArg_ParseTuple(args, "iiiiiii", &rx, &ry, &rw, &rh, &cell_size, &cols, &rows)) {
        return NULL;
    }

    if (cell_size <= 0 || cols <= 0 || rows <= 0 || rw <= 0 || rh <= 0) {
        return PyList_New(0);
    }

    int min_col = rx / cell_size;
    int max_col = (rx + rw) / cell_size;
    int min_row = ry / cell_size;
    int max_row = (ry + rh) / cell_size;

    if (min_col < 0) min_col = 0;
    if (max_col >= cols) max_col = cols - 1;
    if (min_row < 0) min_row = 0;
    if (max_row >= rows) max_row = rows - 1;

    int row_count = max_row - min_row + 1;
    int col_count = max_col - min_col + 1;
    if (row_count <= 0 || col_count <= 0) {
        return PyList_New(0);
    }
    Py_ssize_t total = (Py_ssize_t)row_count * (Py_ssize_t)col_count;

    PyObject* result = PyList_New(total);
    if (!result) return NULL;

    Py_ssize_t k = 0;
    for (int row = min_row; row <= max_row; row++) {
        for (int col = min_col; col <= max_col; col++) {
            int idx = row * cols + col;
            PyObject* py_idx = PyLong_FromLong((long)idx);
            if (!py_idx) {
                Py_DECREF(result);
                return NULL;
            }
            PyList_SET_ITEM(result, k, py_idx);
            k++;
        }
    }
    return result;
}

/* Rotate a 2D vector by angle (radians).
 * Args: (x, y, angle_radians)
 * Returns: (rotated_x, rotated_y) tuple */
static PyObject* rotate_vector_c(PyObject* self, PyObject* args) {
    double x, y, angle;
    
    if (!PyArg_ParseTuple(args, "ddd", &x, &y, &angle)) {
        return NULL;
    }
    
    double cos_a = cos(angle);
    double sin_a = sin(angle);
    double rx = x * cos_a - y * sin_a;
    double ry = x * sin_a + y * cos_a;
    
    return Py_BuildValue("(dd)", rx, ry);
}

/* Find nearest entity index from a list of positions.
 * Args: (center_x, center_y, positions_x_list, positions_y_list)
 * Returns: index of nearest entity, or -1 if empty */
static PyObject* find_nearest_index_c(PyObject* self, PyObject* args) {
    double cx, cy;
    PyObject* positions_x;
    PyObject* positions_y;
    
    if (!PyArg_ParseTuple(args, "ddOO", &cx, &cy, &positions_x, &positions_y)) {
        return NULL;
    }
    
    Py_ssize_t len = PyList_Size(positions_x);
    if (len == 0) {
        return PyLong_FromLong(-1);
    }
    
    double min_dist_sq = 1e30;
    Py_ssize_t nearest_idx = -1;
    
    for (Py_ssize_t i = 0; i < len; i++) {
        double ex = PyFloat_AsDouble(PyList_GetItem(positions_x, i));
        double ey = PyFloat_AsDouble(PyList_GetItem(positions_y, i));
        double dx = ex - cx;
        double dy = ey - cy;
        double dist_sq = dx * dx + dy * dy;
        
        if (dist_sq < min_dist_sq) {
            min_dist_sq = dist_sq;
            nearest_idx = i;
        }
    }
    
    return PyLong_FromSsize_t(nearest_idx);
}

/* Find threats in dodge range - checks bullets that could hit within time threshold.
 * Args: (enemy_x, enemy_y, dodge_range_sq, time_threshold,
 *        bullets_x, bullets_y, bullets_vx, bullets_vy)
 * Returns: list of bullet indices that are threats */
static PyObject* find_dodge_threats_c(PyObject* self, PyObject* args) {
    double ex, ey, dodge_range_sq, time_threshold;
    PyObject *bx_list, *by_list, *vx_list, *vy_list;
    
    if (!PyArg_ParseTuple(args, "ddddOOOO", 
                          &ex, &ey, &dodge_range_sq, &time_threshold,
                          &bx_list, &by_list, &vx_list, &vy_list)) {
        return NULL;
    }
    
    Py_ssize_t len = PyList_Size(bx_list);
    PyObject* result = PyList_New(0);
    if (!result) return NULL;
    
    /* Avoid sqrt: time_to_reach < T  <=>  dist/vel_len < T  <=>  dist_sq < T^2 * vel_len_sq */
    const double t_sq = time_threshold * time_threshold;
    const double eps_sq = 0.0001;

    for (Py_ssize_t i = 0; i < len; i++) {
        double bx = PyFloat_AsDouble(PyList_GetItem(bx_list, i));
        double by = PyFloat_AsDouble(PyList_GetItem(by_list, i));
        double dx = bx - ex;
        double dy = by - ey;
        double dist_sq = dx * dx + dy * dy;

        if (dist_sq >= dodge_range_sq)
            continue;

        double vx = PyFloat_AsDouble(PyList_GetItem(vx_list, i));
        double vy = PyFloat_AsDouble(PyList_GetItem(vy_list, i));
        double vel_len_sq = vx * vx + vy * vy;

        if (vel_len_sq <= eps_sq)
            continue;

        if (dist_sq < t_sq * vel_len_sq) {
            PyObject* idx = PyLong_FromSsize_t(i);
            if (idx) {
                PyList_Append(result, idx);
                Py_DECREF(idx);
            }
        }
    }

    return result;
}

/* Batch rect-rect collision check.
 * Caches B rects once to avoid repeated PyList_GetItem in inner loop.
 * Args: (rects_a_x, rects_a_y, rects_a_w, rects_a_h,
 *        rects_b_x, rects_b_y, rects_b_w, rects_b_h)
 * Returns: list of (a_idx, b_idx) tuples for colliding pairs */
static PyObject* batch_rect_collisions_c(PyObject* self, PyObject* args) {
    PyObject *ax_list, *ay_list, *aw_list, *ah_list;
    PyObject *bx_list, *by_list, *bw_list, *bh_list;

    if (!PyArg_ParseTuple(args, "OOOOOOOO",
                          &ax_list, &ay_list, &aw_list, &ah_list,
                          &bx_list, &by_list, &bw_list, &bh_list)) {
        return NULL;
    }

    Py_ssize_t len_a = PyList_Size(ax_list);
    Py_ssize_t len_b = PyList_Size(bx_list);

    PyObject* result = PyList_New(0);
    if (!result) return NULL;

    if (len_b <= 0) return result;

    /* Cache all B rects once */
    Rect* rb_cache = (Rect*)malloc((size_t)len_b * sizeof(Rect));
    if (!rb_cache) {
        Py_DECREF(result);
        return PyErr_NoMemory();
    }
    for (Py_ssize_t j = 0; j < len_b; j++) {
        rb_cache[j].x = (int)PyLong_AsLong(PyList_GetItem(bx_list, j));
        rb_cache[j].y = (int)PyLong_AsLong(PyList_GetItem(by_list, j));
        rb_cache[j].w = (int)PyLong_AsLong(PyList_GetItem(bw_list, j));
        rb_cache[j].h = (int)PyLong_AsLong(PyList_GetItem(bh_list, j));
    }

    for (Py_ssize_t i = 0; i < len_a; i++) {
        Rect ra;
        ra.x = (int)PyLong_AsLong(PyList_GetItem(ax_list, i));
        ra.y = (int)PyLong_AsLong(PyList_GetItem(ay_list, i));
        ra.w = (int)PyLong_AsLong(PyList_GetItem(aw_list, i));
        ra.h = (int)PyLong_AsLong(PyList_GetItem(ah_list, i));

        for (Py_ssize_t j = 0; j < len_b; j++) {
            if (rect_collide(&ra, &rb_cache[j])) {
                PyObject* pair = Py_BuildValue("(nn)", (Py_ssize_t)i, j);
                if (pair) {
                    PyList_Append(result, pair);
                    Py_DECREF(pair);
                }
            }
        }
    }

    free(rb_cache);
    return result;
}

/* Normalize a vector (Python interface).
 * Args: (x, y)
 * Returns: (normalized_x, normalized_y) tuple */
static PyObject* normalize_c(PyObject* self, PyObject* args) {
    double x, y;
    
    if (!PyArg_ParseTuple(args, "dd", &x, &y)) {
        return NULL;
    }
    
    double len = sqrt(x * x + y * y);
    if (len < 0.0001) {
        return Py_BuildValue("(dd)", 1.0, 0.0);  // Default to right
    }
    
    return Py_BuildValue("(dd)", x / len, y / len);
}

/* Method definitions */
static PyMethodDef GamePhysicsMethods[] = {
    {"can_move_rect", can_move_rect_c, METH_VARARGS, 
     "Check if a rect can move without collision"},
    {"vec_toward", vec_toward_c, METH_VARARGS,
     "Calculate normalized vector from point A to B"},
    {"update_bullets", update_bullets_c, METH_VARARGS,
     "Batch update bullet positions"},
    {"distance", distance_c, METH_VARARGS,
     "Calculate distance between two points"},
    {"distance_squared", distance_squared_c, METH_VARARGS,
     "Calculate squared distance (faster, no sqrt)"},
    {"check_bullet_collisions", check_bullet_collisions_c, METH_VARARGS,
     "Batch check collisions between bullets and targets"},
    {"batch_distance_squared", batch_distance_squared_c, METH_VARARGS,
     "Compute squared distances from one point to many targets"},
    {"find_in_radius", find_in_radius_c, METH_VARARGS,
     "Find indices of entities within radius (uses radius squared)"},
    {"get_grid_cell_index", get_grid_cell_index_c, METH_VARARGS,
     "Get grid cell index for a point"},
    {"get_grid_cell_indices_for_rect", get_grid_cell_indices_for_rect_c, METH_VARARGS,
     "Get all grid cell indices a rect overlaps"},
    {"rotate_vector", rotate_vector_c, METH_VARARGS,
     "Rotate a 2D vector by angle (radians)"},
    {"find_nearest_index", find_nearest_index_c, METH_VARARGS,
     "Find index of nearest entity from position lists"},
    {"find_dodge_threats", find_dodge_threats_c, METH_VARARGS,
     "Find bullet indices that are threats within dodge range"},
    {"batch_rect_collisions", batch_rect_collisions_c, METH_VARARGS,
     "Batch check rect-rect collisions, return colliding pairs"},
    {"normalize", normalize_c, METH_VARARGS,
     "Normalize a 2D vector"},
    {NULL, NULL, 0, NULL}
};

/* Module definition */
static struct PyModuleDef game_physics_module = {
    PyModuleDef_HEAD_INIT,
    "game_physics",
    "High-performance physics and collision detection",
    -1,
    GamePhysicsMethods
};

/* Module initialization */
PyMODINIT_FUNC PyInit_game_physics(void) {
    return PyModule_Create(&game_physics_module);
}
