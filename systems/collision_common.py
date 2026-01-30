"""Shared collision helpers: enemy damage flash, player damage application."""
from __future__ import annotations

from constants import STATE_GAME_OVER


def set_enemy_damage_flash(enemy: dict, ctx: dict) -> None:
    """Set enemy damage flash timer when config enables it (juice)."""
    if ctx.get("enable_damage_flash", True):
        enemy["damage_flash_timer"] = ctx.get("damage_flash_duration", 0.12)


def apply_player_damage(state, damage: int, ctx: dict) -> None:
    """Apply damage to player (overshield then HP); trigger death/game-over if needed.
    
    Player is invincible during dash (is_jumping=True) to reward quick movement.
    """
    if damage <= 0:
        return
    # Dash grants invincibility - incentivizes quick movement
    if getattr(state, "is_jumping", False):
        return
    if ctx.get("testing_mode") and ctx.get("invulnerability_mode"):
        return
    if state.overshield > 0:
        damage_to_overshield = min(damage, state.overshield)
        state.overshield = max(0, state.overshield - damage)
        damage = damage - damage_to_overshield
    if damage > 0:
        state.player_hp -= damage
        state.player_hp = max(0, state.player_hp)
        if ctx.get("enable_screen_flash", True):
            state.screen_damage_flash_timer = ctx.get("screen_flash_duration", 0.25)
        if ctx.get("enable_damage_wobble", False):
            state.damage_wobble_timer = 0.2  # short wobble duration
        pf = ctx.get("play_sfx")
        if callable(pf):
            pf("player_hit")
        # Play low health warning when HP drops below 25% (and not dead)
        max_hp = getattr(state, "player_max_hp", 100)
        if state.player_hp > 0 and state.player_hp <= max_hp * 0.25:
            # Only play if we just crossed the threshold
            prev_hp = state.player_hp + damage
            if prev_hp > max_hp * 0.25:
                from systems.audio_system import play_sfx
                play_sfx("LOW HEALTH")
    state.damage_taken += damage
    state.wave_damage_taken += damage
    if state.player_hp <= 0:
        reset = ctx.get("reset_after_death")
        player = state.player_rect
        lives_left = (state.lives - 1) if (state.lives > 0 and reset) else 0
        log_death = ctx.get("log_player_death")
        if callable(log_death) and player is not None:
            log_death(
                getattr(state, "run_time", 0.0),
                player.centerx,
                player.centery,
                lives_left,
                getattr(state, "wave_number", 0),
            )
        if state.lives > 0 and reset:
            state.lives -= 1
            reset(state)
        else:
            # Game over - store score and wave for game over screen
            state.final_score_for_high_score = state.score
            state.game_over_wave = getattr(state, "wave_number", 1)
            state.current_screen = STATE_GAME_OVER
            # Play player death sound
            from systems.audio_system import play_sfx
            play_sfx("PLAYER DEATH")
