"""TelemetryViewerScene: In-game visualization of telemetry graphs."""
from __future__ import annotations

import os
import sqlite3
from io import BytesIO
from typing import TYPE_CHECKING, Optional

import pygame

from constants import STATE_TELEMETRY_VIEWER
from rendering import RenderContext, draw_centered_text
from scenes.transitions import SceneTransition

if TYPE_CHECKING:
    from state import GameState

# Default telemetry database path
DB_PATH = "game_telemetry.db"


def _matplotlib_available() -> bool:
    """Check if matplotlib is available."""
    try:
        import matplotlib
        return True
    except ImportError:
        return False


def _render_plot_to_surface(
    page,
    conn: sqlite3.Connection,
    run_id: int,
    width: int,
    height: int,
) -> Optional[pygame.Surface]:
    """Render a matplotlib plot to a pygame surface.
    
    Returns None if the plot has no data or an error occurs.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
        from telemetry_viz.db_utils import no_data
        
        # Create figure with appropriate DPI for the target size
        dpi = 100
        fig_width = width / dpi
        fig_height = height / dpi
        
        fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)
        
        try:
            ax.clear()
            ok = page.draw(ax, conn, run_id)
        except Exception as e:
            no_data(ax, f"Error: {e!r}")
            ok = False
        
        if not ok:
            plt.close(fig)
            return None
        
        ax.set_title(page.title)
        fig.tight_layout()
        
        # Render to buffer
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=dpi, facecolor='#1a1a2e', edgecolor='none')
        plt.close(fig)
        
        # Load as pygame surface
        buf.seek(0)
        surface = pygame.image.load(buf, "plot.png")
        buf.close()
        
        return surface
        
    except Exception as e:
        print(f"[TelemetryViewer] Error rendering plot: {e}")
        return None


class TelemetryViewerScene:
    """In-game telemetry visualization viewer.
    
    Shows matplotlib plots rendered to pygame surfaces.
    Navigate with LEFT/RIGHT arrows or A/D keys.
    Press ESC to return to the previous screen.
    """
    
    def __init__(self):
        self._pages = []
        self._current_index = 0
        self._conn: Optional[sqlite3.Connection] = None
        self._run_id: Optional[int] = None
        self._cached_surfaces: dict[int, Optional[pygame.Surface]] = {}
        self._loading = False
        self._error_message: Optional[str] = None
        self._available_pages: list[int] = []  # Indices of pages with data
        
    def state_id(self) -> str:
        return STATE_TELEMETRY_VIEWER
    
    def _load_pages(self) -> None:
        """Load the list of available plot pages."""
        try:
            from telemetry_viz.core import get_pages
            self._pages = get_pages()
        except ImportError as e:
            self._error_message = f"Missing telemetry_viz module: {e}"
            self._pages = []
    
    def _connect_db(self) -> bool:
        """Connect to the telemetry database. Returns True on success."""
        if not os.path.exists(DB_PATH):
            self._error_message = f"No telemetry database found at {DB_PATH}"
            return False
        
        try:
            self._conn = sqlite3.connect(DB_PATH)
            return True
        except Exception as e:
            self._error_message = f"Database error: {e}"
            return False
    
    def _get_latest_run_id(self) -> Optional[int]:
        """Get the most recent run_id from the database."""
        if self._conn is None:
            return None
        
        try:
            from telemetry_viz.db_utils import get_latest_run_id
            return get_latest_run_id(self._conn)
        except Exception as e:
            self._error_message = f"Error getting run_id: {e}"
            return None
    
    def _render_current_plot(self, width: int, height: int) -> Optional[pygame.Surface]:
        """Render the current plot (with caching)."""
        if not self._pages or self._conn is None or self._run_id is None:
            return None
        
        idx = self._current_index
        
        # Check cache
        if idx in self._cached_surfaces:
            return self._cached_surfaces[idx]
        
        # Render and cache
        page = self._pages[idx]
        # Leave some margin for UI
        plot_width = width - 40
        plot_height = height - 120
        
        surface = _render_plot_to_surface(page, self._conn, self._run_id, plot_width, plot_height)
        self._cached_surfaces[idx] = surface
        
        return surface
    
    def _navigate(self, direction: int) -> None:
        """Navigate to next/previous plot."""
        if not self._pages:
            return
        
        self._current_index = (self._current_index + direction) % len(self._pages)
    
    def handle_input(self, events, game_state: "GameState", ctx: dict) -> dict:
        out = {
            "screen": None,
            "quit": False,
            "pop": False,
        }
        
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            
            if event.key == pygame.K_ESCAPE:
                out["pop"] = True
                return out
            
            if event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_n):
                self._navigate(1)
            elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_p):
                self._navigate(-1)
            elif event.key == pygame.K_HOME:
                self._current_index = 0
            elif event.key == pygame.K_END:
                if self._pages:
                    self._current_index = len(self._pages) - 1
            elif event.key == pygame.K_r:
                # Refresh: clear cache and re-render
                self._cached_surfaces.clear()
        
        return out
    
    def handle_input_transition(self, events, game_state: "GameState", ctx: dict) -> SceneTransition:
        result = self.handle_input(events, game_state, ctx)
        self._last_input_result = result
        
        if result.get("pop"):
            return SceneTransition.pop()
        
        return SceneTransition.none()
    
    def update(self, dt: float, game_state: "GameState", ctx: dict) -> None:
        pass
    
    def update_transition(self, dt: float, game_state: "GameState", ctx: dict) -> SceneTransition:
        self.update(dt, game_state, ctx)
        return SceneTransition.none()
    
    def render(self, render_ctx: RenderContext, game_state: "GameState", ctx: dict) -> None:
        screen = render_ctx.screen
        w, h = render_ctx.width, render_ctx.height
        font, big_font = render_ctx.font, render_ctx.big_font
        
        # Dark background
        screen.fill((26, 26, 46))  # #1a1a2e
        
        # Check for matplotlib
        if not _matplotlib_available():
            draw_centered_text(screen, font, big_font, w, "TELEMETRY VIEWER", h // 4, color=(100, 200, 255), use_big=True)
            draw_centered_text(screen, font, big_font, w, "matplotlib is required but not installed", h // 2, color=(255, 100, 100))
            draw_centered_text(screen, font, big_font, w, "Install with: pip install matplotlib", h // 2 + 40, color=(180, 180, 180))
            draw_centered_text(screen, font, big_font, w, "Press ESC to go back", h - 60, color=(150, 150, 150))
            return
        
        # Check for errors
        if self._error_message:
            draw_centered_text(screen, font, big_font, w, "TELEMETRY VIEWER", h // 4, color=(100, 200, 255), use_big=True)
            draw_centered_text(screen, font, big_font, w, self._error_message, h // 2, color=(255, 100, 100))
            draw_centered_text(screen, font, big_font, w, "Press ESC to go back", h - 60, color=(150, 150, 150))
            return
        
        # Check if no pages
        if not self._pages:
            draw_centered_text(screen, font, big_font, w, "TELEMETRY VIEWER", h // 4, color=(100, 200, 255), use_big=True)
            draw_centered_text(screen, font, big_font, w, "No plots available", h // 2, color=(255, 200, 100))
            draw_centered_text(screen, font, big_font, w, "Press ESC to go back", h - 60, color=(150, 150, 150))
            return
        
        # Title bar
        page = self._pages[self._current_index]
        title = f"[{self._current_index + 1}/{len(self._pages)}] {page.title}"
        draw_centered_text(screen, font, big_font, w, title, 30, color=(100, 200, 255))
        
        # Render plot
        plot_surface = self._render_current_plot(w, h)
        
        if plot_surface is not None:
            # Center the plot
            plot_x = (w - plot_surface.get_width()) // 2
            plot_y = 60
            screen.blit(plot_surface, (plot_x, plot_y))
        else:
            # No data for this plot
            draw_centered_text(screen, font, big_font, w, "No data for this plot", h // 2, color=(180, 180, 180))
            draw_centered_text(screen, font, big_font, w, "(Try playing a game with telemetry enabled)", h // 2 + 40, color=(120, 120, 120))
        
        # Navigation hints
        draw_centered_text(
            screen, font, big_font, w,
            "LEFT/RIGHT: Navigate | R: Refresh | HOME/END: First/Last | ESC: Back",
            h - 30, color=(150, 150, 150)
        )
        
        # Run info
        if self._run_id is not None:
            run_info = f"Run ID: {self._run_id}"
            draw_centered_text(screen, font, big_font, w, run_info, h - 60, color=(100, 100, 100))
    
    def on_enter(self, game_state: "GameState", ctx: dict) -> None:
        """Called when entering the scene."""
        self._error_message = None
        self._cached_surfaces.clear()
        self._current_index = 0
        
        # Load plot pages
        self._load_pages()
        if self._error_message:
            return
        
        # Connect to database
        if not self._connect_db():
            return
        
        # Get latest run
        self._run_id = self._get_latest_run_id()
        if self._run_id is None:
            self._error_message = "No telemetry runs found in database"
    
    def on_exit(self, game_state: "GameState", ctx: dict) -> None:
        """Called when leaving the scene."""
        # Close database connection
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
        
        # Clear cached surfaces to free memory
        self._cached_surfaces.clear()
