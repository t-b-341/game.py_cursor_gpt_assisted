"""Tests that respawn does not restart the wave (no spawn_system_start_wave on death)."""
import os
import pytest


# Source check avoids importing game (which may init display). We only need the contract.
# reset_after_death was moved from game.py to systems/enemy_death.py
ENEMY_DEATH_PY = os.path.join(os.path.dirname(__file__), "..", "systems", "enemy_death.py")


def _get_reset_after_death_source() -> str:
    """Return the source of reset_after_death from systems/enemy_death.py without importing."""
    with open(ENEMY_DEATH_PY, "r", encoding="utf-8") as f:
        text = f.read()
    start = text.find("def reset_after_death(")
    if start == -1:
        raise LookupError("reset_after_death not found in systems/enemy_death.py")
    # End at next top-level "def " or end of file.
    search_from = start + 22
    candidates = []
    for marker in ("\ndef ",):
        j = text.find(marker, search_from)
        if j != -1:
            candidates.append(j)
    end = min(candidates) if candidates else len(text)
    return text[start:end]


class TestRespawnDoesNotRestartWave:
    """Ensure respawn keeps current wave and enemies (no map reset)."""

    def test_reset_after_death_does_not_call_spawn_system_start_wave(self):
        """Regression: respawn must not call start_wave or clear enemies/friendly_ai."""
        src = _get_reset_after_death_source()
        assert "spawn_system_start_wave" not in src, (
            "reset_after_death must not call spawn_system_start_wave; respawn should keep wave and enemies."
        )
        assert "state.enemies.clear()" not in src, (
            "reset_after_death must not clear enemies on respawn."
        )
        assert "state.friendly_ai.clear()" not in src, (
            "reset_after_death must not clear friendly_ai on respawn."
        )
        assert "Do not clear friendly_ai or call start_wave" in src, (
            "Expected comment documenting no-wave-restart behavior."
        )
