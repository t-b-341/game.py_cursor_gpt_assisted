"""Performance visualization plots: frame time, FPS, and correlation with entity counts."""
from __future__ import annotations

import sqlite3
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


def draw_fps_over_time(ax: plt.Axes, conn: sqlite3.Connection, run_id: int) -> bool:
    """Draw FPS over time with target FPS line."""
    rows = conn.execute(
        "SELECT t, fps FROM frame_times WHERE run_id = ? ORDER BY t;",
        (run_id,),
    ).fetchall()
    if not rows:
        ax.text(0.5, 0.5, "No frame time data", ha="center", va="center", transform=ax.transAxes)
        return False
    
    times = [r[0] for r in rows]
    fps_vals = [r[1] for r in rows]
    
    ax.plot(times, fps_vals, linewidth=0.8, alpha=0.8, label="FPS")
    ax.axhline(y=60, color='green', linestyle='--', alpha=0.7, label="Target (60 FPS)")
    ax.axhline(y=30, color='orange', linestyle='--', alpha=0.7, label="Minimum (30 FPS)")
    
    # Highlight drops below 30 FPS
    for i, (t, fps) in enumerate(zip(times, fps_vals)):
        if fps < 30:
            ax.axvspan(t - 0.025, t + 0.025, color='red', alpha=0.3)
    
    ax.set_xlabel("Game Time (s)")
    ax.set_ylabel("FPS")
    ax.set_title("Frame Rate Over Time")
    ax.legend(loc="upper right")
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.3)
    return True


def draw_frame_time_distribution(ax: plt.Axes, conn: sqlite3.Connection, run_id: int) -> bool:
    """Draw histogram of frame times to show distribution."""
    rows = conn.execute(
        "SELECT frame_time_ms FROM frame_times WHERE run_id = ?;",
        (run_id,),
    ).fetchall()
    if not rows:
        ax.text(0.5, 0.5, "No frame time data", ha="center", va="center", transform=ax.transAxes)
        return False
    
    frame_times = [r[0] for r in rows]
    
    # Create histogram with log scale for better visibility of outliers
    ax.hist(frame_times, bins=50, edgecolor='black', alpha=0.7)
    
    # Add vertical lines for targets
    ax.axvline(x=16.67, color='green', linestyle='--', label="60 FPS (16.7ms)")
    ax.axvline(x=33.33, color='orange', linestyle='--', label="30 FPS (33.3ms)")
    
    # Statistics
    avg = np.mean(frame_times)
    p95 = np.percentile(frame_times, 95)
    p99 = np.percentile(frame_times, 99)
    
    ax.axvline(x=avg, color='blue', linestyle='-', alpha=0.7, label=f"Mean: {avg:.1f}ms")
    ax.axvline(x=p95, color='purple', linestyle=':', alpha=0.7, label=f"95th: {p95:.1f}ms")
    
    ax.set_xlabel("Frame Time (ms)")
    ax.set_ylabel("Count")
    ax.set_title(f"Frame Time Distribution (99th: {p99:.1f}ms)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)
    return True


def draw_fps_vs_projectiles(ax: plt.Axes, conn: sqlite3.Connection, run_id: int) -> bool:
    """Scatter plot of FPS vs total projectile count to identify correlation."""
    rows = conn.execute(
        """SELECT fps, player_bullets + enemy_projectiles + friendly_projectiles as total_projectiles
           FROM frame_times WHERE run_id = ?;""",
        (run_id,),
    ).fetchall()
    if not rows:
        ax.text(0.5, 0.5, "No frame time data", ha="center", va="center", transform=ax.transAxes)
        return False
    
    fps_vals = [r[0] for r in rows]
    projectiles = [r[1] for r in rows]
    
    # Scatter with alpha for density visualization
    ax.scatter(projectiles, fps_vals, alpha=0.3, s=10)
    
    # Add trend line if enough data
    if len(rows) > 10:
        z = np.polyfit(projectiles, fps_vals, 1)
        p = np.poly1d(z)
        x_line = np.linspace(min(projectiles), max(projectiles), 100)
        ax.plot(x_line, p(x_line), "r--", alpha=0.8, label=f"Trend (slope: {z[0]:.2f})")
    
    ax.axhline(y=60, color='green', linestyle='--', alpha=0.5, label="60 FPS")
    ax.axhline(y=30, color='orange', linestyle='--', alpha=0.5, label="30 FPS")
    
    ax.set_xlabel("Total Projectiles")
    ax.set_ylabel("FPS")
    ax.set_title("FPS vs Projectile Count")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)
    return True


def draw_fps_vs_enemies(ax: plt.Axes, conn: sqlite3.Connection, run_id: int) -> bool:
    """Scatter plot of FPS vs enemy count to identify correlation."""
    rows = conn.execute(
        "SELECT fps, enemies FROM frame_times WHERE run_id = ?;",
        (run_id,),
    ).fetchall()
    if not rows:
        ax.text(0.5, 0.5, "No frame time data", ha="center", va="center", transform=ax.transAxes)
        return False
    
    fps_vals = [r[0] for r in rows]
    enemies = [r[1] for r in rows]
    
    ax.scatter(enemies, fps_vals, alpha=0.3, s=10)
    
    if len(rows) > 10:
        z = np.polyfit(enemies, fps_vals, 1)
        p = np.poly1d(z)
        x_line = np.linspace(min(enemies), max(enemies), 100)
        ax.plot(x_line, p(x_line), "r--", alpha=0.8, label=f"Trend (slope: {z[0]:.2f})")
    
    ax.axhline(y=60, color='green', linestyle='--', alpha=0.5, label="60 FPS")
    ax.axhline(y=30, color='orange', linestyle='--', alpha=0.5, label="30 FPS")
    
    ax.set_xlabel("Enemy Count")
    ax.set_ylabel("FPS")
    ax.set_title("FPS vs Enemy Count")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)
    return True


def draw_entity_counts_over_time(ax: plt.Axes, conn: sqlite3.Connection, run_id: int) -> bool:
    """Draw entity counts (projectiles, enemies) over time."""
    rows = conn.execute(
        """SELECT t, player_bullets, enemy_projectiles, friendly_projectiles, enemies
           FROM frame_times WHERE run_id = ? ORDER BY t;""",
        (run_id,),
    ).fetchall()
    if not rows:
        ax.text(0.5, 0.5, "No frame time data", ha="center", va="center", transform=ax.transAxes)
        return False
    
    times = [r[0] for r in rows]
    player_bullets = [r[1] for r in rows]
    enemy_projectiles = [r[2] for r in rows]
    friendly_projectiles = [r[3] for r in rows]
    enemies = [r[4] for r in rows]
    
    ax.plot(times, player_bullets, label="Player Bullets", alpha=0.8)
    ax.plot(times, enemy_projectiles, label="Enemy Projectiles", alpha=0.8)
    ax.plot(times, friendly_projectiles, label="Friendly Projectiles", alpha=0.8)
    ax.plot(times, enemies, label="Enemies", alpha=0.8, linewidth=2)
    
    ax.set_xlabel("Game Time (s)")
    ax.set_ylabel("Count")
    ax.set_title("Entity Counts Over Time")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)
    return True


def draw_frame_drops_analysis(ax: plt.Axes, conn: sqlite3.Connection, run_id: int) -> bool:
    """Analyze frame drops: when they occur and what entity counts were present."""
    rows = conn.execute(
        """SELECT t, fps, player_bullets, enemy_projectiles, friendly_projectiles, enemies
           FROM frame_times WHERE run_id = ? AND fps < 45 ORDER BY fps ASC;""",
        (run_id,),
    ).fetchall()
    
    if not rows:
        ax.text(0.5, 0.5, "No significant frame drops detected!\n(All frames >= 45 FPS)", 
                ha="center", va="center", transform=ax.transAxes, fontsize=12)
        ax.set_title("Frame Drop Analysis")
        return True
    
    # Show worst frame drops as a table-like visualization
    times = [r[0] for r in rows[:20]]  # Top 20 worst
    fps_vals = [r[1] for r in rows[:20]]
    total_proj = [r[2] + r[3] + r[4] for r in rows[:20]]
    enemies = [r[5] for r in rows[:20]]
    
    x = range(len(times))
    width = 0.35
    
    bars1 = ax.bar([i - width/2 for i in x], total_proj, width, label='Total Projectiles', alpha=0.7)
    bars2 = ax.bar([i + width/2 for i in x], enemies, width, label='Enemies', alpha=0.7)
    
    # Add FPS labels on top
    for i, (fp, proj, en) in enumerate(zip(fps_vals, total_proj, enemies)):
        ax.annotate(f'{fp:.0f}fps', (i, max(proj, en) + 2), ha='center', fontsize=7, color='red')
    
    ax.set_xlabel("Frame Drop Instances (sorted by severity)")
    ax.set_ylabel("Entity Count")
    ax.set_title(f"Worst {len(times)} Frame Drops - Entity Counts")
    ax.legend(loc="upper right")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{t:.1f}s" for t in times], rotation=45, fontsize=7)
    ax.grid(True, alpha=0.3, axis='y')
    return True


def draw_performance_summary(ax: plt.Axes, conn: sqlite3.Connection, run_id: int) -> bool:
    """Summary statistics and performance overview."""
    rows = conn.execute(
        """SELECT fps, frame_time_ms, player_bullets, enemy_projectiles, friendly_projectiles, enemies
           FROM frame_times WHERE run_id = ?;""",
        (run_id,),
    ).fetchall()
    
    if not rows:
        ax.text(0.5, 0.5, "No frame time data", ha="center", va="center", transform=ax.transAxes)
        return False
    
    fps_vals = [r[0] for r in rows]
    frame_times = [r[1] for r in rows]
    total_proj = [r[2] + r[3] + r[4] for r in rows]
    enemies = [r[5] for r in rows]
    
    # Calculate statistics
    stats = {
        "Total Frames Sampled": len(rows),
        "Avg FPS": f"{np.mean(fps_vals):.1f}",
        "Min FPS": f"{np.min(fps_vals):.1f}",
        "Max FPS": f"{np.max(fps_vals):.1f}",
        "Std Dev FPS": f"{np.std(fps_vals):.1f}",
        "": "",  # Spacer
        "Avg Frame Time": f"{np.mean(frame_times):.2f}ms",
        "95th % Frame Time": f"{np.percentile(frame_times, 95):.2f}ms",
        "99th % Frame Time": f"{np.percentile(frame_times, 99):.2f}ms",
        "Max Frame Time": f"{np.max(frame_times):.2f}ms",
        " ": "",  # Spacer
        "Frames < 60 FPS": f"{sum(1 for f in fps_vals if f < 60)} ({100*sum(1 for f in fps_vals if f < 60)/len(fps_vals):.1f}%)",
        "Frames < 30 FPS": f"{sum(1 for f in fps_vals if f < 30)} ({100*sum(1 for f in fps_vals if f < 30)/len(fps_vals):.1f}%)",
        "  ": "",  # Spacer
        "Max Projectiles": f"{max(total_proj)}",
        "Max Enemies": f"{max(enemies)}",
        "Avg Projectiles": f"{np.mean(total_proj):.1f}",
        "Avg Enemies": f"{np.mean(enemies):.1f}",
    }
    
    # Display as text
    ax.axis('off')
    text = "\n".join([f"{k}: {v}" if v else "" for k, v in stats.items()])
    ax.text(0.1, 0.95, "PERFORMANCE SUMMARY", fontsize=14, fontweight='bold', 
            transform=ax.transAxes, verticalalignment='top')
    ax.text(0.1, 0.85, text, fontsize=10, transform=ax.transAxes, 
            verticalalignment='top', family='monospace')
    
    # Performance grade
    avg_fps = np.mean(fps_vals)
    drops_pct = 100 * sum(1 for f in fps_vals if f < 30) / len(fps_vals)
    
    if avg_fps >= 58 and drops_pct < 1:
        grade, color = "EXCELLENT", "green"
    elif avg_fps >= 50 and drops_pct < 5:
        grade, color = "GOOD", "blue"
    elif avg_fps >= 40 and drops_pct < 10:
        grade, color = "FAIR", "orange"
    else:
        grade, color = "NEEDS OPTIMIZATION", "red"
    
    ax.text(0.9, 0.95, grade, fontsize=16, fontweight='bold', color=color,
            transform=ax.transAxes, verticalalignment='top', ha='right')
    
    return True
