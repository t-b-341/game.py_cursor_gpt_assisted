"""
HUD/UI rendering during gameplay.
Split into render_hud (health, score, metrics, cooldown bars) and render_overlays
(damage numbers, defeat/pickup messages, wave countdown). Read state only.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pygame

from constants import STATE_PLAYING, AIM_ARROWS
from rendering import RenderContext, draw_health_bar, draw_centered_text, render_hud_text
from systems.fps_tracker import get_average_fps, get_fps_history, get_stats

if TYPE_CHECKING:
    from state import GameState


# FPS graph colors
FPS_GRAPH_COLOR = (50, 255, 50)  # Green
FPS_TEXT_COLOR = (50, 255, 50)  # Green
FPS_GRAPH_BG = (20, 20, 20, 180)  # Semi-transparent dark
FPS_TARGET_LINE_COLOR = (255, 255, 100)  # Yellow for 60 FPS line
FPS_WARNING_COLOR = (255, 150, 50)  # Orange for low FPS


# Text surface cache to avoid re-rendering unchanged text each frame
# Key: (text, font_id, color) -> Surface
_text_cache: dict[tuple, pygame.Surface] = {}
_text_cache_max_size = 100


def _get_cached_text(font: pygame.font.Font, text: str, color: tuple) -> pygame.Surface:
    """Get a cached text surface, rendering only if text/color changed."""
    key = (text, id(font), color)
    if key not in _text_cache:
        # Evict oldest entries if cache is full
        if len(_text_cache) >= _text_cache_max_size:
            # Remove first 20 entries (simple LRU approximation)
            keys_to_remove = list(_text_cache.keys())[:20]
            for k in keys_to_remove:
                del _text_cache[k]
        _text_cache[key] = font.render(text, True, color)
    return _text_cache[key]


def render_hud(state: "GameState", ctx: dict, render_ctx: RenderContext) -> None:
    """Draw HUD layer: entity health bars, score, metrics, cooldown bars, and FPS graph."""
    if not ctx or not render_ctx:
        return
    screen = render_ctx.screen
    font, big_font, small_font = render_ctx.font, render_ctx.big_font, render_ctx.small_font
    WIDTH, HEIGHT = render_ctx.width, render_ctx.height
    ui_show_health_bars = ctx.get("ui_show_health_bars", True)
    ui_show_hud = ctx.get("ui_show_hud", True)
    ui_show_metrics = ctx.get("ui_show_metrics", True)
    ui_show_fps = ctx.get("ui_show_fps", True)  # FPS graph toggle
    if not font or not big_font or not small_font:
        return
    _draw_entity_health_bars(screen, state, ui_show_health_bars)
    if ui_show_hud:
        _draw_score(screen, state, big_font, WIDTH)
        if ui_show_metrics:
            _draw_metrics_and_bars(screen, state, ctx, font, small_font, WIDTH, HEIGHT)
    # Draw FPS graph in bottom-left corner
    if ui_show_fps:
        _draw_fps_graph(screen, small_font, WIDTH, HEIGHT)
    # Draw performance overlay if enabled (shows entity counts for debugging)
    ui_show_perf_overlay = ctx.get("ui_show_perf_overlay", False)
    if ui_show_perf_overlay:
        _draw_perf_overlay(screen, state, small_font, WIDTH, HEIGHT)


def render_overlays(state: "GameState", ctx: dict, render_ctx: RenderContext) -> None:
    """Draw overlay layer: damage numbers, defeat/pickup messages, wave countdown, wave-reset debug, juice (screen flash, wave banner)."""
    if not ctx or not render_ctx:
        return
    screen = render_ctx.screen
    font, big_font, small_font = render_ctx.font, render_ctx.big_font, render_ctx.small_font
    WIDTH, HEIGHT = render_ctx.width, render_ctx.height
    ui_show_metrics = ctx.get("ui_show_metrics", True)
    if not font or not small_font:
        return
    _draw_damage_numbers(screen, state, font, small_font)
    _draw_defeat_messages(screen, state, small_font, WIDTH, HEIGHT)
    _draw_weapon_pickup_messages(screen, state, font, WIDTH, HEIGHT)
    _draw_wave_countdown(screen, state, font, big_font, WIDTH, HEIGHT)
    if ui_show_metrics:
        _draw_wave_reset_debug(screen, state, small_font, WIDTH, HEIGHT)
    _draw_screen_damage_flash(screen, state, ctx, WIDTH, HEIGHT)
    _draw_wave_banner(screen, state, ctx, big_font, WIDTH, HEIGHT)


def _draw_screen_damage_flash(screen: pygame.Surface, state: "GameState", ctx: dict, WIDTH: int, HEIGHT: int) -> None:
    """Juice: brief red vignette when player takes damage. Magnitude/duration from config."""
    if not ctx.get("enable_screen_flash", True):
        return
    t = getattr(state, "screen_damage_flash_timer", 0.0)
    if t <= 0:
        return
    duration = ctx.get("screen_flash_duration", 0.25)
    max_alpha = min(255, max(0, ctx.get("screen_flash_max_alpha", 100)))
    alpha = int(max_alpha * (t / duration)) if duration > 0 else 0
    if alpha <= 0:
        return
    surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    surf.fill((255, 50, 50, alpha))
    screen.blit(surf, (0, 0))


def _draw_wave_banner(screen: pygame.Surface, state: "GameState", ctx: dict, big_font: Any, WIDTH: int, HEIGHT: int) -> None:
    """Juice: centered 'WAVE N' text when a wave starts. Duration from config."""
    if not ctx.get("enable_wave_banner", True):
        return
    t = getattr(state, "wave_banner_timer", 0.0)
    if t <= 0:
        return
    text = getattr(state, "wave_banner_text", "") or "WAVE"
    draw_centered_text(screen, big_font, big_font, WIDTH, text, HEIGHT // 2 - 30, (255, 255, 200), use_big=True)


def render(state: "GameState", screen: pygame.Surface, ctx: dict) -> None:
    """Draw all gameplay HUD/UI (HUD + overlays). Backward compat: builds RenderContext from (screen, ctx)."""
    if not ctx:
        return
    render_ctx = RenderContext.from_screen_and_ctx(screen, ctx)
    render_hud(state, ctx, render_ctx)
    render_overlays(state, ctx, render_ctx)


def _draw_fps_graph(screen: pygame.Surface, small_font: Any, WIDTH: int, HEIGHT: int) -> None:
    """Draw FPS graph with average in bottom-left corner."""
    # Graph dimensions and position
    graph_width = 120
    graph_height = 50
    padding = 8
    x = padding
    y = HEIGHT - 140 - graph_height  # Above health bar area
    
    # Get FPS data
    stats = get_stats()
    avg_fps = stats["avg_fps"]
    fps_history = get_fps_history(graph_width)
    
    if not fps_history:
        return
    
    # Create semi-transparent background
    bg_surf = pygame.Surface((graph_width + padding * 2, graph_height + 35), pygame.SRCALPHA)
    bg_surf.fill((20, 20, 20, 180))
    screen.blit(bg_surf, (x - padding, y - padding))
    
    # Draw FPS text
    if avg_fps >= 55:
        text_color = FPS_GRAPH_COLOR  # Green
    elif avg_fps >= 30:
        text_color = FPS_WARNING_COLOR  # Orange
    else:
        text_color = (255, 80, 80)  # Red
    
    fps_text = f"FPS: {int(avg_fps)}"  # Use int for better cache hits
    text_surf = _get_cached_text(small_font, fps_text, text_color)
    screen.blit(text_surf, (x, y - padding + 2))
    
    # Draw graph border
    graph_rect = pygame.Rect(x, y + 15, graph_width, graph_height)
    pygame.draw.rect(screen, (60, 60, 60), graph_rect, 1)
    
    # Dynamic scale based on max observed FPS (supports high refresh rate displays)
    max_scale = 200 if stats["max_fps"] > 120 else 120
    
    # Draw 60 FPS target line
    target_y = graph_rect.bottom - int((60 / max_scale) * graph_height)
    pygame.draw.line(screen, FPS_TARGET_LINE_COLOR, 
                     (graph_rect.left, target_y), (graph_rect.right, target_y), 1)
    
    # Draw 30 FPS warning line
    warn_y = graph_rect.bottom - int((30 / max_scale) * graph_height)
    pygame.draw.line(screen, (255, 80, 80), 
                     (graph_rect.left, warn_y), (graph_rect.right, warn_y), 1)
    
    # Draw FPS graph line - reuse points list to avoid allocation
    if len(fps_history) >= 2:
        # Get or create cached points list
        if not hasattr(_draw_fps_graph, '_points_cache'):
            _draw_fps_graph._points_cache = []
        points = _draw_fps_graph._points_cache
        points.clear()
        
        history_len_minus_1 = max(1, len(fps_history) - 1)
        graph_left = graph_rect.left
        graph_bottom = graph_rect.bottom
        
        for i, fps in enumerate(fps_history):
            # Map index to x position
            px = graph_left + int((i / history_len_minus_1) * (graph_width - 1))
            # Map FPS to y position (dynamic range, clamped)
            clamped_fps = max(0, min(max_scale, fps))
            py = graph_bottom - int((clamped_fps / max_scale) * graph_height)
            points.append((px, py))
        
        # Draw the line with anti-aliasing
        if len(points) >= 2:
            pygame.draw.lines(screen, FPS_GRAPH_COLOR, False, points, 2)
    
    # Draw min/max labels
    min_fps = stats["min_fps"]
    max_fps = stats["max_fps"]
    
    # Small labels for min/max
    min_text = small_font.render(f"min:{min_fps:.0f}", True, (150, 150, 150))
    max_text = small_font.render(f"max:{max_fps:.0f}", True, (150, 150, 150))
    screen.blit(min_text, (x, graph_rect.bottom + 2))
    screen.blit(max_text, (x + graph_width - max_text.get_width(), graph_rect.bottom + 2))


def _draw_perf_overlay(screen: pygame.Surface, state, small_font, WIDTH: int, HEIGHT: int) -> None:
    """Draw performance overlay with entity counts for debugging frame drops."""
    # Position in top-right corner
    x = WIDTH - 200
    y = 10
    line_height = 18
    
    # Gather entity counts
    counts = [
        ("Enemies", len(getattr(state, "enemies", []))),
        ("Player Bullets", len(getattr(state, "player_bullets", []))),
        ("Enemy Projectiles", len(getattr(state, "enemy_projectiles", []))),
        ("Friendly Projectiles", len(getattr(state, "friendly_projectiles", []))),
        ("Missiles", len(getattr(state, "missiles", []))),
        ("Explosions", len(getattr(state, "grenade_explosions", []))),
        ("Laser Beams", len(getattr(state, "laser_beams", []))),
        ("Damage Numbers", len(getattr(state, "damage_numbers", []))),
        ("Friendly AI", len(getattr(state, "friendly_ai", []))),
        ("Wave Beams", len(getattr(state, "wave_beams", []))),
    ]
    
    # Calculate total
    total = sum(c[1] for c in counts)
    
    # Draw background
    bg_height = (len(counts) + 2) * line_height + 10
    bg_surf = pygame.Surface((190, bg_height), pygame.SRCALPHA)
    bg_surf.fill((20, 20, 20, 200))
    screen.blit(bg_surf, (x - 5, y - 5))
    
    # Draw header
    header = _get_cached_text(small_font, "PERF OVERLAY", (255, 200, 50))
    screen.blit(header, (x, y))
    y += line_height + 5
    
    # Draw entity counts with color coding
    for name, count in counts:
        # Color code: green (low), yellow (medium), red (high)
        if count < 50:
            color = (100, 255, 100)
        elif count < 150:
            color = (255, 255, 100)
        else:
            color = (255, 100, 100)
        
        text = _get_cached_text(small_font, f"{name}: {count}", color)
        screen.blit(text, (x, y))
        y += line_height
    
    # Draw total
    y += 5
    total_color = (100, 255, 100) if total < 300 else (255, 255, 100) if total < 600 else (255, 100, 100)
    total_text = _get_cached_text(small_font, f"TOTAL: {total}", total_color)
    screen.blit(total_text, (x, y))


def _draw_entity_health_bars(screen: pygame.Surface, state, show: bool) -> None:
    if not show:
        return
    for friendly in getattr(state, "friendly_ai", []):
        if friendly.get("hp", 0) > 0:
            r = friendly.get("rect")
            if r:
                draw_health_bar(screen, r.x, r.y - 10, r.w, 5, friendly["hp"], friendly.get("max_hp", friendly["hp"]))
    for enemy in getattr(state, "enemies", []):
        if enemy.get("hp", 0) > 0:
            r = enemy.get("rect")
            if r:
                draw_health_bar(screen, r.x, r.y - 10, r.w, 5, enemy["hp"], enemy.get("max_hp", enemy["hp"]))


def _draw_score(screen: pygame.Surface, state, big_font, WIDTH: int) -> None:
    score_text = f"Score: {state.score}"
    # Use cached text surfaces to avoid re-rendering unchanged text
    score_surface = _get_cached_text(big_font, score_text, (255, 255, 0))
    outline_surface = _get_cached_text(big_font, score_text, (0, 0, 0))
    score_x = WIDTH // 2 - score_surface.get_width() // 2
    score_y = 10
    for dx, dy in [(-2, -2), (-2, 0), (-2, 2), (0, -2), (0, 2), (2, -2), (2, 0), (2, 2)]:
        screen.blit(outline_surface, (score_x + dx, score_y + dy))
    screen.blit(score_surface, (score_x, score_y))


def _draw_metrics_and_bars(
    screen: pygame.Surface, state, ctx: dict,
    font, small_font, WIDTH: int, HEIGHT: int,
) -> None:
    overshield_max = ctx.get("overshield_max", state.player_max_hp)
    grenade_cooldown = ctx.get("grenade_cooldown", 5.0)
    missile_cooldown = ctx.get("missile_cooldown", 8.0)
    ally_drop_cooldown = ctx.get("ally_drop_cooldown", 1.5)  # Fallback matches config/balance.py
    overshield_recharge_cooldown = ctx.get("overshield_recharge_cooldown", 60.0)
    shield_duration = ctx.get("shield_duration", 3.0)
    aiming_mode = ctx.get("aiming_mode", "MOUSE")
    current_state = ctx.get("current_state", "")

    y_pos = 10
    y_pos = render_hud_text(screen, font, f"HP: {state.player_hp}/{state.player_max_hp}", y_pos)
    # Armor/overshield is shown on the armor bar above the health bar; no extra line here
    y_pos = render_hud_text(screen, font, f"Wave: {state.wave_number} | Level: {state.current_level}", y_pos)
    minutes = int(state.survival_time // 60)
    seconds = int(state.survival_time % 60)
    y_pos = render_hud_text(screen, font, f"Time: {minutes:02d}:{seconds:02d}", y_pos)
    if current_state == STATE_PLAYING:
        y_pos = render_hud_text(screen, font, f"Lives: {state.lives}", y_pos)
    y_pos = render_hud_text(screen, font, f"Enemies: {len(state.enemies)}", y_pos)
    y_pos = render_hud_text(screen, font, f"Weapon: {state.current_weapon_mode.upper()}", y_pos)
    if state.shield_active:
        y_pos = render_hud_text(screen, font, "SHIELD ACTIVU", y_pos, (255, 100, 100))
    if state.random_damage_multiplier != 1.0:
        multiplier_color = (255, 255, 0) if state.random_damage_multiplier > 1.0 else (255, 150, 150)
        y_pos = render_hud_text(screen, font, f"DMG MULT: {state.random_damage_multiplier:.2f}x", y_pos, multiplier_color)

    health_bar_x = 10
    health_bar_y = HEIGHT - 80
    health_bar_height = 20
    health_bar_width = 300
    armor_health_gap = 6  # pixels between armor bar bottom and health bar top

    if state.overshield > 0:
        # Armor bar: same length (width) and height as health, placed slightly above
        armor_bar_y = health_bar_y - health_bar_height - armor_health_gap
        overshield_fill = int((state.overshield / max(1, overshield_max)) * health_bar_width)
        pygame.draw.rect(screen, (60, 60, 60), (health_bar_x, armor_bar_y, health_bar_width, health_bar_height))
        pygame.draw.rect(screen, (255, 150, 0), (health_bar_x, armor_bar_y, overshield_fill, health_bar_height))
        pygame.draw.rect(screen, (20, 20, 20), (health_bar_x, armor_bar_y, health_bar_width, health_bar_height), 2)
        overshield_text = _get_cached_text(small_font, f"Armor: {int(state.overshield)}/{int(overshield_max)}", (255, 255, 255))
        screen.blit(overshield_text, (health_bar_x + 5, armor_bar_y + 2))

    health_fill = int((state.player_hp / state.player_max_hp) * health_bar_width)
    pygame.draw.rect(screen, (60, 60, 60), (health_bar_x, health_bar_y, health_bar_width, health_bar_height))
    pygame.draw.rect(screen, (100, 255, 100), (health_bar_x, health_bar_y, health_fill, health_bar_height))
    pygame.draw.rect(screen, (20, 20, 20), (health_bar_x, health_bar_y, health_bar_width, health_bar_height), 2)
    health_text = _get_cached_text(small_font, f"HP: {int(state.player_hp)}/{int(state.player_max_hp)}", (255, 255, 255))
    screen.blit(health_text, (health_bar_x + 5, health_bar_y + 2))

    bar_y = HEIGHT - 30
    bar_height = 20
    bar_width = min(200, (WIDTH - 60) // 5)

    grenade_progress = min(1.0, state.grenade_time_since_used / grenade_cooldown)
    grenade_x = 10
    pygame.draw.rect(screen, (60, 60, 60), (grenade_x, bar_y, bar_width, bar_height))
    pygame.draw.rect(screen, (200, 100, 255) if grenade_progress >= 1.0 else (255, 50, 50),
                     (grenade_x, bar_y, int(bar_width * grenade_progress), bar_height))
    pygame.draw.rect(screen, (255, 255, 255), (grenade_x, bar_y, bar_width, bar_height), 2)
    screen.blit(_get_cached_text(small_font, "BOMB (E)", (255, 255, 255)), (grenade_x + 5, bar_y + 2))

    missile_progress = min(1.0, state.missile_time_since_used / missile_cooldown)
    missile_x = grenade_x + bar_width + 10
    pygame.draw.rect(screen, (60, 60, 60), (missile_x, bar_y, bar_width, bar_height))
    pygame.draw.rect(screen, (255, 200, 0) if missile_progress >= 1.0 else (100, 100, 100),
                     (missile_x, bar_y, int(bar_width * missile_progress), bar_height))
    pygame.draw.rect(screen, (255, 255, 255), (missile_x, bar_y, bar_width, bar_height), 2)
    screen.blit(_get_cached_text(small_font, "MISSILE (R)", (255, 255, 255)), (missile_x + 5, bar_y + 2))

    ally_progress = min(1.0, state.ally_drop_timer / ally_drop_cooldown)
    ally_x = missile_x + bar_width + 10
    pygame.draw.rect(screen, (60, 60, 60), (ally_x, bar_y, bar_width, bar_height))
    pygame.draw.rect(screen, (200, 100, 255) if ally_progress >= 1.0 else (100, 100, 100),
                     (ally_x, bar_y, int(bar_width * ally_progress), bar_height))
    pygame.draw.rect(screen, (255, 255, 255), (ally_x, bar_y, bar_width, bar_height), 2)
    screen.blit(_get_cached_text(small_font, "ALLY DROP (Q)", (255, 255, 255)), (ally_x + 5, bar_y + 2))

    overshield_progress = min(1.0, state.overshield_recharge_timer / overshield_recharge_cooldown)
    overshield_x = ally_x + bar_width + 10
    pygame.draw.rect(screen, (60, 60, 60), (overshield_x, bar_y, bar_width, bar_height))
    # Use cyan when ready so it’s distinct from the orange armor meter (current overshield)
    overshield_bar_color = (100, 220, 255) if overshield_progress >= 1.0 else (100, 100, 100)
    pygame.draw.rect(screen, overshield_bar_color,
                     (overshield_x, bar_y, int(bar_width * overshield_progress), bar_height))
    pygame.draw.rect(screen, (255, 255, 255), (overshield_x, bar_y, bar_width, bar_height), 2)
    screen.blit(_get_cached_text(small_font, "OVERSHIELD (TAB)", (255, 255, 255)), (overshield_x + 5, bar_y + 2))

    if state.shield_active:
        shield_progress = min(1.0, state.shield_duration_remaining / shield_duration)
    else:
        if getattr(state, "shield_recharge_cooldown", 0) > 0:
            shield_progress = min(1.0, state.shield_recharge_timer / state.shield_recharge_cooldown)
        else:
            shield_progress = 1.0
    shield_ready = shield_progress >= 1.0 and not state.shield_active
    shield_x = overshield_x + bar_width + 10
    pygame.draw.rect(screen, (60, 60, 60), (shield_x, bar_y, bar_width, bar_height))
    if state.shield_active:
        shield_color = (255, 255, 100)
    elif shield_ready:
        shield_color = (100, 200, 255)
    else:
        shield_color = (255, 50, 50)
    pygame.draw.rect(screen, shield_color, (shield_x, bar_y, int(bar_width * shield_progress), bar_height))
    pygame.draw.rect(screen, (255, 255, 255), (shield_x, bar_y, bar_width, bar_height), 2)
    screen.blit(_get_cached_text(small_font, "SHIELD (LALT)", (255, 255, 255)), (shield_x + 5, bar_y + 2))

    controls_y = HEIGHT - 10
    if aiming_mode == AIM_ARROWS:
        controls_text = "WASD: Move | Arrow Keys: Aim & Shoot | E: Bomb | R: Missile | Q: Ally Drop | TAB: Overshield | LALT: Shield | SPACE: Dash"
    else:
        controls_text = "WASD: Move | Mouse + Click: Aim & Shoot | E: Bomb | R: Missile | Q: Ally Drop | TAB: Overshield | LALT: Shield | SPACE: Dash"
    controls_surf = small_font.render(controls_text, True, (150, 150, 150))
    controls_rect = controls_surf.get_rect(center=(WIDTH // 2, controls_y))
    screen.blit(controls_surf, controls_rect)


def _draw_damage_numbers(screen: pygame.Surface, state, font, small_font) -> None:
    for dmg_num in getattr(state, "damage_numbers", []):
        if dmg_num.get("timer", 0) > 0:
            alpha = int(255 * (dmg_num["timer"] / 2.0))
            color = (*dmg_num["color"][:3], alpha) if len(dmg_num.get("color", (0, 0, 0))) > 3 else dmg_num.get("color", (255, 255, 255))
            if "value" in dmg_num:
                text_surf = font.render(dmg_num["value"], True, color[:3])
            else:
                text_surf = small_font.render(str(int(dmg_num.get("damage", 0))), True, color[:3])
            screen.blit(text_surf, (dmg_num["x"], dmg_num["y"]))


def _draw_defeat_messages(screen: pygame.Surface, state, small_font, WIDTH: int, HEIGHT: int) -> None:
    defeat_y_start = HEIGHT - 100
    messages = getattr(state, "enemy_defeat_messages", [])[-5:]
    for i, msg in enumerate(messages):
        if msg.get("timer", 0) > 0:
            enemy_type = msg.get("enemy_type", "enemy")
            text = f"{enemy_type.upper()} DEFEATED!"
            text_surf = small_font.render(text, True, (255, 200, 100))
            text_rect = text_surf.get_rect()
            x_pos = WIDTH - text_rect.width - 20
            y_pos = defeat_y_start - (i * 25)
            screen.blit(text_surf, (x_pos, y_pos))


def _draw_weapon_pickup_messages(screen: pygame.Surface, state, font, WIDTH: int, HEIGHT: int) -> None:
    messages = [m for m in getattr(state, "weapon_pickup_messages", []) if m.get("timer", 0) > 0]
    line_height = 28
    total_h = (len(messages) - 1) * line_height
    y_start = HEIGHT // 2 - total_h // 2
    for i, msg in enumerate(messages):
        alpha = int(255 * (msg["timer"] / 3.0))
        color = (*msg.get("color", (255, 255, 255))[:3], alpha) if len(msg.get("color", (0, 0, 0))) > 3 else msg.get("color", (255, 255, 255))
        text_surf = font.render(f"PICKED UP: {msg.get('weapon_name', '')}", True, color[:3])
        text_rect = text_surf.get_rect(center=(WIDTH // 2, y_start + i * line_height))
        screen.blit(text_surf, text_rect)


def _draw_wave_reset_debug(screen: pygame.Surface, state, font, WIDTH: int, HEIGHT: int) -> None:
    """Show last wave-reset events (trigger, wave_num, enemies_before) to debug spurious resets."""
    log = getattr(state, "wave_reset_log", None)
    if not log:
        return
    x = WIDTH - 420
    y = 10
    title = font.render("Wave resets (trigger | wave | enemies_before):", True, (255, 200, 100))
    screen.blit(title, (x, y))
    y += 18
    for entry in log[-5:]:  # last 5
        t = entry.get("trigger", "?")
        w = entry.get("wave_num", "?")
        e = entry.get("enemies_before", "?")
        rt = entry.get("run_time", 0)
        color = (255, 100, 100) if e and e > 0 else (150, 255, 150)
        line = font.render(f"  t={rt:.1f}s {t!r} wave={w} enemies_before={e}", True, color)
        screen.blit(line, (x, y))
        y += 16


def _draw_wave_countdown(screen: pygame.Surface, state, font, big_font, WIDTH: int, HEIGHT: int) -> None:
    if not (getattr(state, "wave_active", False) and len(getattr(state, "enemies", [])) == 0):
        return
    time_to_next = getattr(state, "time_to_next_wave", 0)
    if time_to_next >= 3.0:
        return
    countdown_number = max(1, min(3, 3 - int(time_to_next)))
    next_wave_num = state.wave_number + 1
    countdown_text = f"WAVE {next_wave_num} STARTING IN {countdown_number}"
    draw_centered_text(screen, font, big_font, WIDTH, countdown_text, HEIGHT // 2, (255, 255, 0), use_big=True)
