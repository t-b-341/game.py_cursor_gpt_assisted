"""Menu rendering and interaction helpers.

Provides common functions for rendering menus with consistent styling,
handling menu navigation (keyboard + mouse), and calculating clickable regions.
"""
from __future__ import annotations

from typing import Callable, Sequence

import pygame

from .hud import draw_centered_text


# Menu text cache to avoid re-rendering unchanged text
_menu_text_cache: dict[tuple, pygame.Surface] = {}
_menu_text_cache_max = 50


def _get_cached_menu_text(font: pygame.font.Font, text: str, color: tuple) -> pygame.Surface:
    """Get cached menu text surface."""
    key = (text, id(font), color[:3])
    if key not in _menu_text_cache:
        if len(_menu_text_cache) >= _menu_text_cache_max:
            # Clear oldest half of cache
            keys_to_remove = list(_menu_text_cache.keys())[:_menu_text_cache_max // 2]
            for k in keys_to_remove:
                del _menu_text_cache[k]
        _menu_text_cache[key] = font.render(text, True, color[:3])
    return _menu_text_cache[key]


def get_menu_option_rects(
    width: int,
    height: int,
    y_start: int,
    num_options: int,
    line_height: int = 40,
    option_width: int = 400,
) -> list[pygame.Rect]:
    """Calculate clickable rectangles for centered menu options.
    
    Args:
        width: Screen width
        height: Screen height (unused but included for consistency)
        y_start: Y position of first option
        num_options: Number of menu options
        line_height: Vertical spacing between options
        option_width: Width of clickable region
        
    Returns:
        List of pygame.Rect for each option's clickable area
    """
    rects = []
    for i in range(num_options):
        y = y_start + i * line_height
        rect = pygame.Rect((width - option_width) // 2, y - line_height // 2, option_width, line_height)
        rects.append(rect)
    return rects


def render_menu_title(
    screen: pygame.Surface,
    font: pygame.font.Font,
    big_font: pygame.font.Font,
    width: int,
    title: str,
    y: int,
    color: tuple = (220, 220, 220),
) -> None:
    """Render a centered menu title."""
    draw_centered_text(screen, font, big_font, width, title, y, color, use_big=True)


def render_menu_options(
    screen: pygame.Surface,
    font: pygame.font.Font,
    big_font: pygame.font.Font,
    width: int,
    options: Sequence[str],
    selected_index: int,
    y_start: int,
    line_height: int = 40,
    selected_color: tuple = (255, 255, 0),
    unselected_color: tuple = (200, 200, 200),
    show_arrow: bool = True,
) -> list[pygame.Rect]:
    """Render a list of menu options with selection highlighting.
    
    Args:
        screen: Pygame surface to render to
        font: Regular font
        big_font: Large font (unused for options but included for consistency)
        width: Screen width for centering
        options: List of option text strings
        selected_index: Currently selected option index
        y_start: Y position of first option
        line_height: Vertical spacing between options
        selected_color: Color for selected option
        unselected_color: Color for unselected options
        show_arrow: Whether to show "->" arrow for selected option
        
    Returns:
        List of clickable rectangles for each option
    """
    rects = []
    option_width = 400
    
    for i, option in enumerate(options):
        is_selected = i == selected_index
        color = selected_color if is_selected else unselected_color
        
        # Build display text with optional arrow
        if show_arrow:
            display_text = f"-> {option}" if is_selected else f"   {option}"
        else:
            display_text = option
        
        y = y_start + i * line_height
        
        # Use cached text surface
        text_surf = _get_cached_menu_text(font, display_text, color)
        text_rect = text_surf.get_rect(center=(width // 2, y))
        screen.blit(text_surf, text_rect)
        
        # Calculate clickable rect
        click_rect = pygame.Rect((width - option_width) // 2, y - line_height // 2, option_width, line_height)
        rects.append(click_rect)
    
    return rects


def handle_menu_navigation(
    events: list,
    num_options: int,
    selected_index: int,
    option_rects: list[pygame.Rect] = None,
) -> tuple[int, bool, int]:
    """Handle keyboard and mouse navigation for a menu.
    
    Args:
        events: List of pygame events
        num_options: Total number of options
        selected_index: Currently selected option index
        option_rects: Optional list of clickable rectangles for mouse support
        
    Returns:
        Tuple of (new_selected_index, confirmed, clicked_index)
        - new_selected_index: Updated selection after arrow key navigation
        - confirmed: True if Enter/Return was pressed
        - clicked_index: Index that was clicked (-1 if no click)
    """
    new_index = selected_index
    confirmed = False
    clicked_index = -1
    
    for event in events:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                new_index = (selected_index - 1) % num_options
            elif event.key == pygame.K_DOWN:
                new_index = (selected_index + 1) % num_options
            elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                confirmed = True
        
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if option_rects:
                mouse_pos = event.pos
                for i, rect in enumerate(option_rects):
                    if rect.collidepoint(mouse_pos):
                        clicked_index = i
                        break
    
    return new_index, confirmed, clicked_index


def render_confirmation_dialog(
    screen: pygame.Surface,
    font: pygame.font.Font,
    big_font: pygame.font.Font,
    width: int,
    height: int,
    message: str,
    confirm_text: str = "Yes",
    cancel_text: str = "No",
) -> None:
    """Render a centered confirmation dialog overlay.
    
    Args:
        screen: Pygame surface to render to
        font: Regular font
        big_font: Large font
        width: Screen width
        height: Screen height
        message: Question/message to display
        confirm_text: Text for confirm option
        cancel_text: Text for cancel option
    """
    # Semi-transparent overlay
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))
    
    # Dialog box
    box_width, box_height = 500, 150
    box_x = (width - box_width) // 2
    box_y = (height - box_height) // 2
    pygame.draw.rect(screen, (40, 40, 50), (box_x, box_y, box_width, box_height))
    pygame.draw.rect(screen, (100, 100, 120), (box_x, box_y, box_width, box_height), 2)
    
    # Message
    draw_centered_text(screen, font, big_font, width, message, box_y + 40, (255, 255, 255))
    
    # Options
    options_text = f"({confirm_text}) / ({cancel_text})"
    draw_centered_text(screen, font, big_font, width, options_text, box_y + 90, (180, 180, 180))


def clear_menu_cache() -> None:
    """Clear the menu text cache. Call when fonts change."""
    _menu_text_cache.clear()
