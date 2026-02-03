"""3D plots: player path (x, y, time), damage events, etc."""
from __future__ import annotations

import sqlite3

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

from telemetry_viz.db_utils import read_df, safe_numeric, table_exists


def _no_data_3d(ax: Axes3D, msg: str) -> None:
    """Show a message on 3D axes (Axes3D.text expects x, y, z, s)."""
    ax.text(0, 0, 0, msg)


def draw_player_path_3d(ax: Axes3D, conn: sqlite3.Connection, run_id: int) -> bool:
    """Player path in 3D: x, y, time."""
    if not table_exists(conn, "player_positions"):
        _no_data_3d(ax, "player_positions missing")
        return False

    df = read_df(
        conn,
        """
        SELECT t, x, y
        FROM player_positions
        WHERE run_id = ?
        ORDER BY t ASC
        LIMIT 50000;
        """,
        (run_id,),
    )
    if df.empty:
        _no_data_3d(ax, "No player_positions for this run")
        return False

    df["x"] = safe_numeric(df["x"], fill=0.0)
    df["y"] = safe_numeric(df["y"], fill=0.0)
    df["t"] = safe_numeric(df["t"], fill=0.0)

    ax.plot3D(df["x"], df["y"], df["t"], "b-", alpha=0.7, linewidth=0.8)
    ax.scatter3D(
        df["x"].iloc[0], df["y"].iloc[0], df["t"].iloc[0],
        color="green", s=40, label="start"
    )
    ax.scatter3D(
        df["x"].iloc[-1], df["y"].iloc[-1], df["t"].iloc[-1],
        color="red", s=40, label="end"
    )
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("Time (s)")
    return True


def draw_damage_events_3d(ax: Axes3D, conn: sqlite3.Connection, run_id: int) -> bool:
    """Damage events in 3D: player_x, player_y, time; point size by amount."""
    if not table_exists(conn, "player_damage"):
        _no_data_3d(ax, "player_damage missing")
        return False

    df = read_df(
        conn,
        """
        SELECT t, amount, player_x, player_y
        FROM player_damage
        WHERE run_id = ?
        ORDER BY t ASC;
        """,
        (run_id,),
    )
    if df.empty:
        _no_data_3d(ax, "No player_damage for this run")
        return False

    df["t"] = safe_numeric(df["t"], fill=0.0)
    df["amount"] = safe_numeric(df["amount"], fill=0.0)
    df["player_x"] = safe_numeric(df["player_x"], fill=0.0)
    df["player_y"] = safe_numeric(df["player_y"], fill=0.0)

    # Scale marker size for visibility (min size ~20, max ~200)
    s = (df["amount"].clip(1, 500) / 500.0 * 180 + 20).values
    ax.scatter3D(
        df["player_x"], df["player_y"], df["t"],
        c=df["amount"], cmap="Reds", s=s, alpha=0.8
    )
    ax.set_xlabel("player_x")
    ax.set_ylabel("player_y")
    ax.set_zlabel("Time (s)")
    return True
