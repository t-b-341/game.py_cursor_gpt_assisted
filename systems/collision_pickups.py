"""Player vs pickups: collection and effect application."""
from __future__ import annotations

from telemetry import PickupEvent


def handle_pickup_player_collisions(state, ctx: dict) -> None:
    """Collect pickups that overlap the player; run collection effect and apply effect."""
    player = state.player_rect
    create_effect = ctx.get("create_pickup_collection_effect")
    apply_effect = ctx.get("apply_pickup_effect")
    telemetry = ctx.get("telemetry")
    enable_telemetry = ctx.get("telemetry_enabled", False)
    
    if not player or not apply_effect or not state.pickups:
        return
    
    pickups_to_remove = set()
    
    for pickup in state.pickups:
        if id(pickup) in pickups_to_remove:
            continue
        if player.colliderect(pickup["rect"]):
            px, py = pickup["rect"].centerx, pickup["rect"].centery
            pickup_type = pickup["type"]
            
            # Create visual effect
            if create_effect:
                create_effect(px, py, pickup["color"], state)
            
            # Apply pickup effect
            apply_effect(pickup_type, state)
            
            # Log to telemetry
            if enable_telemetry and telemetry:
                telemetry.log_pickup(PickupEvent(
                    t=state.run_time,
                    pickup_type=pickup_type,
                    x=px,
                    y=py,
                    collected=True,
                ))
            
            pickups_to_remove.add(id(pickup))
    
    # O(n) bulk removal instead of O(n²) .remove() in loop
    if pickups_to_remove:
        state.pickups[:] = [p for p in state.pickups if id(p) not in pickups_to_remove]
