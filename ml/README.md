# Machine Learning Module

Dynamic Difficulty Adjustment (DDA) using neural networks.

## Overview

This module provides ML-based difficulty adjustment that learns from player behavior:

1. **Data Collection**: Wave performance metrics are logged to the `wave_summaries` table
2. **Feature Extraction**: Metrics are normalized into ML-ready features
3. **Model Training**: PyTorch neural network learns optimal difficulty settings
4. **Real-time Inference**: Difficulty is adjusted between waves based on player performance

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ML DDA SYSTEM                                     │
│                                                                          │
│   TRAINING (offline)                                                     │
│   ──────────────────                                                     │
│   wave_summaries table → features.py → train.py → models/dda_model.pt   │
│                                                                          │
│   INFERENCE (in-game)                                                    │
│   ───────────────────                                                    │
│   wave_tracker.py → dda_integration.py → spawn_system.py                │
│        ↓                     ↓                   ↓                       │
│   [Track events]     [Predict difficulty]  [Apply multipliers]          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Enable Telemetry (required for data collection)

1. Go to **Options > Telemetry > Enabled**
2. Play games normally - wave data is logged automatically

### Check Available Training Data

```bash
python -c "from ml.features import get_training_stats; print(get_training_stats())"
```

### Train the Model

```bash
# Basic training
python -m ml.train

# With GPU (recommended for your 4080 Super!)
python -m ml.train --gpu

# Custom settings
python -m ml.train --epochs 500 --lr 0.001 --gpu
```

### The model activates automatically

Once `ml/models/dda_model.pt` exists, the game will use ML predictions.
Without it, a heuristic fallback is used.

## Features Tracked (14 total)

| Feature | Description | Normalization |
|---------|-------------|---------------|
| combat_effectiveness | Kills / total attacks (weapon-agnostic) | 0-1 |
| kills_per_second | Kill rate | 0-5 → 0-1 |
| damage_per_second | DPS output | 0-1000 → 0-1 |
| damage_taken_rate | Incoming damage/sec | 0-200 → 0-1 |
| deaths_this_wave | Deaths during wave | 0-3 → 0-1 |
| pickups_per_minute | Resource collection | 0-10 → 0-1 |
| abilities_per_minute | Ability usage rate | 0-30 → 0-1 |
| wave_duration_sec | Wave length | 0-120 → 0-1 |
| current_hp_scale | Applied HP mult | 0-2 → 0-1 |
| current_speed_scale | Applied speed mult | 0-2 → 0-1 |
| enemies_spawned | Wave enemy count | 0-50 → 0-1 |
| hp_pct_at_start | Starting HP% | 0-1 |
| **rocket_preference** | Rockets / (rockets + shots) | 0-1 (0=all shots, 1=all rockets) |
| **grenade_usage_rate** | Grenades per minute | 0-10 → 0-1 |

### Weapon-Specific Tracking

The system tracks your weapon preferences to accurately assess performance:

```
Regular shots (left-click):  shots_fired, shots_hit
Rockets (R key):             rockets_fired, rockets_hit, rocket_kills  
Grenades (E key):            grenades_thrown, grenade_kills
Laser (weapon mode):         laser_time, laser_kills
```

**Combat Effectiveness** is weapon-agnostic - it measures kills per offensive action
regardless of whether you prefer rockets, grenades, or regular shots. This ensures
the DDA works correctly for all playstyles.

## Difficulty Outputs

| Parameter | Range | Description |
|-----------|-------|-------------|
| hp_mult | 0.8-1.6 | Enemy HP multiplier |
| speed_mult | 0.8-1.4 | Enemy speed multiplier |
| spawn_mult | 0.7-1.5 | Spawn count multiplier |
| projectile_speed_mult | 0.8-1.3 | Projectile speed multiplier |

## Outcome Labels

The model targets a "challenged" outcome (player survives with 20-50% HP):

| Outcome | HP% Range | Target |
|---------|-----------|--------|
| dominated | >80% | Increase difficulty |
| comfortable | 50-80% | Slightly harder |
| challenged | 20-50% | **Ideal - maintain** |
| struggled | 1-20% | Slightly easier |
| died | 0% | Decrease difficulty |

## Files

- `wave_tracker.py` - Per-wave statistics tracking
- `features.py` - Feature extraction and normalization
- `dda_model.py` - PyTorch model architecture
- `dda_integration.py` - Game integration hooks
- `train.py` - Training script (CLI)
- `models/dda_model.pt` - Trained model weights (generated)

## Requirements

- **Required**: Python 3.10+
- **Optional**: PyTorch (for training and ML inference)

Install PyTorch with GPU support:

```bash
# For CUDA 12.1 (RTX 4080 Super)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

## Integration Points

The DDA system integrates with `systems/spawn_system.py`:

1. **Wave Start**: `dda.on_wave_start()` begins tracking
2. **During Wave**: Events like `on_damage_taken()`, `on_enemy_killed()` update stats
3. **Wave End**: `dda.on_wave_end()` calculates adjustment for next wave
4. **Next Wave**: DDA adjustment is applied to hp_scale, speed_scale, spawn count
