"""Enemy movement and collision functions."""
import pygame

from geometry_utils import clamp_rect_to_screen


def move_enemy_with_push_cached(
    enemy_rect: pygame.Rect,
    move_x: int,
    move_y: int,
    block_list: list[dict],
    cached_moveable_destructible_rects: list,
    cached_trapezoid_rects: list,
    cached_triangle_rects: list,
    destructible_blocks: list[dict],
    giant_blocks: list[dict],
    super_giant_blocks: list[dict],
    pickups: list[dict],
    friendly_ai: list[dict],
    enemies: list[dict],
    player: pygame.Rect,
    moving_health_zone: dict,
    width: int,
    height: int,
):
    """Optimized enemy movement - enemies cannot go through objects and must navigate around them."""
    # Cache rects for performance
    block_rects = [b["rect"] for b in block_list]
    cached_destructible_rects = [b["rect"] for b in destructible_blocks]
    cached_giant_rects = [gb["rect"] for gb in giant_blocks]
    cached_super_giant_rects = [sgb["rect"] for sgb in super_giant_blocks]
    cached_pickup_rects = [p["rect"] for p in pickups]
    cached_friendly_rects = [f["rect"] for f in friendly_ai if f.get("hp", 1) > 0]
    cached_enemy_rects = [e["rect"] for e in enemies if e["rect"] is not enemy_rect]

    for axis_dx, axis_dy in [(move_x, 0), (0, move_y)]:
        if axis_dx == 0 and axis_dy == 0:
            continue

        enemy_rect.x += axis_dx
        enemy_rect.y += axis_dy

        # Check collisions with all objects - enemies cannot pass through anything
        collision = False
        
        # Check regular blocks
        for rect in block_rects:
            if enemy_rect.colliderect(rect):
                collision = True
                break
        
        # Check destructible blocks
        if not collision:
            for rect in cached_destructible_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break
        
        # Check moveable destructible blocks
        if not collision:
            for rect in cached_moveable_destructible_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break
        
        # Check giant blocks (unmovable)
        if not collision:
            for rect in cached_giant_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break
        
        # Check super giant blocks (unmovable)
        if not collision:
            for rect in cached_super_giant_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break
        
        # Check trapezoid blocks
        if not collision:
            for rect in cached_trapezoid_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break
        
        # Check triangle blocks
        if not collision:
            for rect in cached_triangle_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break
        
        # Check pickups
        if not collision:
            for rect in cached_pickup_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break
        
        # Check health zone
        if not collision:
            if enemy_rect.colliderect(moving_health_zone["rect"]):
                collision = True
        
        # Check player
        if not collision:
            if enemy_rect.colliderect(player):
                collision = True
        
        # Check friendly AI
        if not collision:
            for rect in cached_friendly_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break
        
        # Check other enemies (prevent enemy stacking)
        if not collision:
            for rect in cached_enemy_rects:
                if enemy_rect.colliderect(rect):
                    collision = True
                    break

        # If collision detected, revert movement
        if collision:
            enemy_rect.x -= axis_dx
            enemy_rect.y -= axis_dy

    clamp_rect_to_screen(enemy_rect, width, height)
