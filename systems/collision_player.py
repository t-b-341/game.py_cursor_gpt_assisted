"""Collisions that involve the player: enemy beams/projectiles, teleporter, health zone."""
from __future__ import annotations

from .collision_common import apply_player_damage


def handle_enemy_laser_beam_collisions(state, dt: float, ctx: dict) -> None:
    """Enemy laser beams damage the player. Beams have a deploy phase (deploy_timer) where they
    grow visually but deal no damage; after deploy, they deal damage for timer duration."""
    line_rect = ctx.get("line_rect_intersection")
    player = state.player_rect
    if not line_rect or player is None:
        return
    for beam in list(getattr(state, "enemy_laser_beams", [])):
        deploy_timer = beam.get("deploy_timer", 0.0)
        if deploy_timer > 0:
            beam["deploy_timer"] = deploy_timer - dt
            continue
        beam["timer"] = beam.get("timer", 0.2) - dt
        if beam["timer"] <= 0:
            state.enemy_laser_beams.remove(beam)
            continue
        damage_per_sec = beam.get("damage", 80 * 60)
        if line_rect(beam["start"], beam["end"], player):
            apply_player_damage(state, int(damage_per_sec * dt), ctx)


def handle_enemy_projectile_player_collisions(state, ctx: dict) -> None:
    """Enemy projectiles that hit the player apply damage and are removed."""
    player = state.player_rect
    if not player:
        return
    for proj in state.enemy_projectiles[:]:
        if not proj["rect"].colliderect(player):
            continue
        if state.shield_active:
            if proj in state.enemy_projectiles:
                state.enemy_projectiles.remove(proj)
            continue
        damage = proj.get("damage", 10)
        apply_player_damage(state, damage, ctx)
        if proj in state.enemy_projectiles:
            state.enemy_projectiles.remove(proj)


def handle_teleporter_player(state, ctx: dict) -> None:
    """Teleport player to linked pad when touching a teleporter. Cooldown prevents instant re-trigger."""
    player = state.player_rect
    pads = ctx.get("teleporter_pads", [])
    if not player or not pads:
        return
    if getattr(state, "teleporter_cooldown", 0) > 0:
        return
    for pad in pads:
        link = pad.get("linked_rect")
        if not link or not player.colliderect(pad["rect"]):
            continue
        player.center = link.center
        state.teleporter_cooldown = 0.5
        # Play teleporter sound
        from systems.audio_system import play_sfx
        play_sfx("TELEPORTER")
        break


def handle_health_zone_player_dt(state, dt: float, ctx: dict) -> None:
    """Moving health zone restores player HP while overlapping. Does not heal when dead (hp <= 0)."""
    player = state.player_rect
    lev = getattr(state, "level", None)
    zone = lev.moving_health_zone if lev else None
    if not player or not zone or not zone.get("rect"):
        return
    if state.player_hp <= 0:
        return  # Player is dead; do not revive
    if player.colliderect(zone["rect"]) and state.player_hp < state.player_max_hp:
        state.player_hp = min(state.player_max_hp, state.player_hp + 50 * dt)
