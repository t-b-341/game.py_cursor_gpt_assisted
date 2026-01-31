"""Tests for telemetry schema initialization (in-memory DB, no display)."""
import sqlite3
import pytest

from telemetry.schema import table_exists, get_columns, init_schema


@pytest.fixture
def memory_db():
    """Create an in-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


def test_init_schema_creates_runs_table(memory_db):
    init_schema(memory_db)
    assert table_exists(memory_db, "runs")


def test_init_schema_creates_enemy_spawns_and_shots(memory_db):
    init_schema(memory_db)
    assert table_exists(memory_db, "enemy_spawns")
    assert table_exists(memory_db, "shots")


def test_runs_table_has_expected_columns(memory_db):
    init_schema(memory_db)
    cols = get_columns(memory_db, "runs")
    assert "id" in cols
    assert "started_at" in cols
    assert "player_max_hp" in cols
    assert "seconds_survived" in cols


def test_init_schema_idempotent(memory_db):
    init_schema(memory_db)
    init_schema(memory_db)
    assert table_exists(memory_db, "runs")
    cols = get_columns(memory_db, "runs")
    assert "id" in cols
