"""Save plots to PNG and run the single-window page-through viewer."""
from __future__ import annotations

import os
import sys
import sqlite3
from typing import List

import matplotlib.pyplot as plt

from telemetry_viz.db_utils import no_data
from telemetry_viz.core import Page


def save_pngs(
    conn: sqlite3.Connection,
    run_id: int,
    pages: List[Page],
    out_dir: str = "telemetry_plots",
) -> None:
    os.makedirs(out_dir, exist_ok=True)

    for p in pages:
        proj = getattr(p, "projection", None)
        if proj == "3d":
            fig = plt.figure()
            ax = fig.add_subplot(111, projection="3d")
        else:
            fig, ax = plt.subplots()
        try:
            ax.clear()
            ok = p.draw(ax, conn, run_id)
        except Exception as e:
            print(f"Error building plot {p.filename}: {e!r}")
            ok = False

        if not ok:
            plt.close(fig)
            print(f"Skipping (no data): {p.filename}")
            continue

        ax.set_title(f"{p.title} (run_id={run_id})")
        fig.tight_layout()
        out_path = os.path.join(out_dir, f"run_{run_id}__{p.filename}")
        fig.savefig(out_path, dpi=160)
        plt.close(fig)
        print(f"Wrote: {out_path}")


def run_single_popup(conn: sqlite3.Connection, run_id: int, pages: List[Page]) -> None:
    available: List[Page] = []
    for p in pages:
        proj = getattr(p, "projection", None) or "rectilinear"
        fig_probe = plt.figure()
        ax_probe = fig_probe.add_subplot(111, projection=proj)
        ok = False
        try:
            ax_probe.clear()
            ok = p.draw(ax_probe, conn, run_id)
        except Exception:
            ok = False
        plt.close(fig_probe)
        if ok:
            available.append(p)

    if not available:
        print("No plots available to show in popup.")
        return

    idx = 0
    quit_program: dict = {"flag": False}

    fig = plt.figure()
    try:
        fig.canvas.manager.set_window_title("Telemetry Viewer (single window)")
    except Exception:
        pass

    def render() -> None:
        nonlocal idx
        fig.clf()
        page = available[idx]
        proj = getattr(page, "projection", None) or "rectilinear"
        ax = fig.add_subplot(111, projection=proj)
        ok = False
        try:
            ok = page.draw(ax, conn, run_id)
        except Exception as e:
            no_data(ax, f"Error: {e!r}")
            ok = False

        ax.set_title(f"[{idx+1}/{len(available)}] {available[idx].title} (run_id={run_id})")

        fig.text(
            0.5, 0.01,
            "n/→ next   p/← prev   q/Esc quit",
            ha="center", va="bottom", fontsize=9
        )

        fig.tight_layout()
        fig.canvas.draw_idle()

    def set_index(new_idx: int) -> None:
        nonlocal idx
        idx = new_idx
        fig.texts.clear()
        render()

    def on_key(event) -> None:
        nonlocal idx
        if event.key in ("n", "right"):
            set_index((idx + 1) % len(available))
        elif event.key in ("p", "left"):
            set_index((idx - 1) % len(available))
        elif event.key in ("q", "escape"):
            quit_program["flag"] = True
            plt.close(fig)

    fig.canvas.mpl_connect("key_press_event", on_key)
    render()

    plt.show()

    if quit_program["flag"]:
        sys.exit(0)
