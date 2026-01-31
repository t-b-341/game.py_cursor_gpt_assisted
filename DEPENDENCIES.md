# Project Dependencies

This document lists all third-party Python packages required to run the project. These are not included in the Python 3.12.x standard library.

## Quick Install

```bash
pip install pygame numpy moderngl pytest
```

For full functionality (including telemetry visualization):

```bash
pip install pygame numpy moderngl pytest matplotlib pandas
```

---

## Required Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pygame` | >= 2.0.0 | Core game engine (graphics, audio, input) |
| `numpy` | >= 1.20.0 | Numerical operations, array handling |

```bash
pip install pygame numpy
```

---

## Optional Dependencies

### Shader System (Recommended)

| Package | Version | Purpose |
|---------|---------|---------|
| `moderngl` | >= 5.0.0 | OpenGL shader pipeline |
| `moderngl-window` | >= 2.0.0 | Window/context management for shaders |

```bash
pip install moderngl moderngl-window
```

> **Note:** Without these, the game runs in fallback mode without GPU shaders.

---

### Telemetry Visualization

| Package | Version | Purpose |
|---------|---------|---------|
| `matplotlib` | >= 3.5.0 | Plotting telemetry data |
| `pandas` | >= 1.4.0 | Data analysis for telemetry |

```bash
pip install matplotlib pandas
```

> **Note:** Only needed if you use `visualize.py` or `telemetry_viz/`.

---

### Development & Testing

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | >= 7.0.0 | Running unit tests |
| `setuptools` | >= 60.0.0 | Building C extensions |

```bash
pip install pytest setuptools
```

---

### Performance (Experimental)

| Package | Version | Purpose |
|---------|---------|---------|
| `numba` | >= 0.56.0 | JIT compilation for physics (alternative to C extension) |

```bash
pip install numba
```

> **Note:** This is experimental and not required. The C extension (`game_physics.c`) provides better performance.

---

## Full Installation

### Minimal (Game Only)

```bash
pip install pygame numpy
```

### Standard (With Shaders)

```bash
pip install pygame numpy moderngl moderngl-window
```

### Full (All Features)

```bash
pip install pygame numpy moderngl moderngl-window matplotlib pandas pytest
```

### Development (With Testing)

```bash
pip install pygame numpy moderngl moderngl-window matplotlib pandas pytest setuptools
```

---

## Version Compatibility

| Python Version | Status |
|----------------|--------|
| 3.12.x | Fully supported |
| 3.11.x | Fully supported |
| 3.10.x | Should work |
| < 3.10 | Not tested |

---

## Troubleshooting

### pygame installation fails on Windows

```bash
pip install pygame --pre
```

### moderngl requires OpenGL 3.3+

Check your graphics driver supports OpenGL 3.3. Integrated Intel graphics may have issues.

### numba installation is slow

Numba has many dependencies. Use conda for faster installation:

```bash
conda install numba
```

---

## requirements.txt

For pip-based installation, use the provided `requirements.txt`:

```bash
pip install -r requirements.txt
```
