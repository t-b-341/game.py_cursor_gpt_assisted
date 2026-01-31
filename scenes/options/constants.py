"""Options menu constants and navigation helpers."""
from __future__ import annotations

import pygame

# Navigation key mappings
NAV_UP = (pygame.K_UP, pygame.K_w)
NAV_DOWN = (pygame.K_DOWN, pygame.K_s)
NAV_LEFT = (pygame.K_LEFT, pygame.K_a)
NAV_RIGHT = (pygame.K_RIGHT, pygame.K_d)
NAV_CONFIRM = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
NAV_CONFIRM_RIGHT = NAV_RIGHT + NAV_CONFIRM


def cycle_selection(current: int, delta: int, num_options: int) -> int:
    """Cycle selection index with wraparound."""
    return (current + delta) % num_options


def get_menu_option_rects(width: int, height: int, y_start: int, num_options: int, line_height: int = 40) -> list[pygame.Rect]:
    """Calculate clickable rectangles for centered menu options."""
    rects = []
    option_width = 400
    for i in range(num_options):
        y = y_start + i * line_height
        rect = pygame.Rect((width - option_width) // 2, y - 15, option_width, line_height)
        rects.append(rect)
    return rects
