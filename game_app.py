"""
GameApp: owns the main loop, GameState, AppContext, and SceneStack.
game.py remains the thin entrypoint that creates GameApp() and calls app.run().
"""
from __future__ import annotations

import pygame


class GameApp:
    """Owns game state, context/config, scene stack, and the Pygame main loop."""

    def __init__(self) -> None:
        # Import here to avoid circular import (game imports GameApp, GameApp uses game)
        import game as game_module
        r = game_module._create_app()
        self.ctx = r.ctx
        self.game_state = r.game_state
        self.scene_stack = r.scene_stack
        self.fps = r.fps
        self.fixed_dt = r.fixed_dt
        self.max_sim_steps = r.max_sim_steps
        self.update_simulation = r.update_simulation
        self.simulation_accumulator = r.simulation_accumulator
        
        # Create reusable screen_ctx once (only update mutable values per frame)
        # Use display dimensions for menus, not world dimensions
        display_w = getattr(self.ctx, 'display_width', self.ctx.width)
        display_h = getattr(self.ctx, 'display_height', self.ctx.height)
        self.screen_ctx = {
            "WIDTH": display_w,
            "HEIGHT": display_h,
            "font": self.ctx.font,
            "big_font": self.ctx.big_font,
            "small_font": self.ctx.small_font,
            "get_high_scores": game_module.get_high_scores,
            "save_high_score": game_module.save_high_score,
            "difficulty": self.ctx.config.difficulty,
            "app_ctx": self.ctx,
        }
        
        # Pre-check telemetry/shader flags to avoid repeated attribute lookups
        self.telemetry_enabled = self.ctx.config.enable_telemetry
        self.pause_shaders_enabled = getattr(self.ctx.config, "enable_pause_shaders", False)
        self.menu_shaders_enabled = getattr(self.ctx.config, "enable_menu_shaders", False)
        
        # Local state for loop (written back to game_state at end of frame)
        # Initialize from game_state
        self._previous_game_state = self.game_state.previous_screen
        self._pause_selected = self.game_state.ui.pause_selected
        self._controls_selected = self.game_state.ui.controls_selected
        self._controls_rebinding = getattr(self.game_state, "controls_rebinding", False)
        self._continue_blink_t = self.game_state.ui.continue_blink_t
        
        # Store events from process_events() for use in update()
        self._current_events: list = []

    def process_events(self) -> bool:
        """Process all input events. Returns False if the game should stop running."""
        import game as game_module
        
        # Read current state from game_state at start of frame (single source of truth)
        self._previous_game_state = self.game_state.previous_screen
        self._pause_selected = self.game_state.ui.pause_selected
        self._controls_selected = self.game_state.ui.controls_selected
        self._controls_rebinding = getattr(self.game_state, "controls_rebinding", False)
        self._continue_blink_t = self.game_state.ui.continue_blink_t
        
        # Update screen_ctx mutable values (width/height shouldn't change, but difficulty might)
        self.screen_ctx["difficulty"] = self.ctx.config.difficulty
        
        # Event handling
        events = game_module._poll_events()
        # Store events for use in update() for gameplay input
        self._current_events = events
        running, self._previous_game_state, self._pause_selected, self._controls_selected, self._controls_rebinding = game_module._handle_events(
            events, self.ctx, self.game_state, self.scene_stack, self.screen_ctx,
            self._previous_game_state, self._pause_selected, self._controls_selected, self._controls_rebinding
        )
        
        return running

    def update(self, dt: float) -> bool:
        """Run simulation updates. Returns False if the game should stop running."""
        import game as game_module
        from constants import STATE_PLAYING, STATE_ENDURANCE, STATE_GAME_OVER, STATE_VICTORY
        
        # Update run time
        self.game_state.run_time += dt
        self.game_state.survival_time += dt
        
        # Game state updates (only when playing)
        current_state = game_module._get_current_state(self.scene_stack) or self.game_state.current_screen
        if current_state == STATE_PLAYING or current_state == STATE_ENDURANCE:
            # Get key state once per frame (used by multiple systems)
            keys_pressed = pygame.key.get_pressed()
            
            # Gameplay input: movement, fire, weapons, abilities (handled in input_system)
            def _try_spawn_bullet():
                if not getattr(self.game_state, "fire_pressed", False):
                    return
                from constants import fire_rate_mult, fire_rate_buff_duration
                eff = self.game_state.player_shoot_cooldown * (
                    fire_rate_mult if self.game_state.fire_rate_buff_t < fire_rate_buff_duration else 1.0
                )
                if self.game_state.player_time_since_shot >= eff:
                    game_module.spawn_player_bullet_and_log(self.game_state, self.ctx)
                    self.game_state.player_time_since_shot = 0.0

            def _try_laser():
                from constants import laser_cooldown, AIM_ARROWS, laser_length, laser_damage, UNLOCKED_WEAPON_DAMAGE_MULT
                from geometry_utils import vec_toward
                if self.game_state.current_weapon_mode != "laser" or self.game_state.laser_time_since_shot < laser_cooldown:
                    return
                pl = self.game_state.player_rect
                if not pl:
                    return
                if self.ctx.config.aim_mode == AIM_ARROWS:
                    # Use pre-fetched keys_pressed instead of calling get_pressed() again
                    dx = (1 if keys_pressed[pygame.K_RIGHT] else 0) - (1 if keys_pressed[pygame.K_LEFT] else 0)
                    dy = (1 if keys_pressed[pygame.K_DOWN] else 0) - (1 if keys_pressed[pygame.K_UP] else 0)
                    if dx == 0 and dy == 0:
                        direction = (
                            self.game_state.last_move_velocity.normalize()
                            if self.game_state.last_move_velocity.length_squared() > 0
                            else pygame.Vector2(1, 0)
                        )
                    else:
                        direction = pygame.Vector2(dx, dy).normalize()
                else:
                    # Get mouse position in world coordinates
                    mx, my = self.ctx.get_world_mouse_pos()
                    direction = vec_toward(pl.centerx, pl.centery, mx, my)
                end_pos = pygame.Vector2(pl.center) + direction * laser_length
                laser_dmg = int(laser_damage * UNLOCKED_WEAPON_DAMAGE_MULT) if "laser" in self.game_state.unlocked_weapons else laser_damage
                self.game_state.laser_beams.append({
                    "start": pygame.Vector2(pl.center), "end": end_pos,
                    "color": (255, 50, 50), "width": 5, "damage": laser_dmg, "timer": 0.1,
                })
                self.game_state.laser_time_since_shot = 0.0
                # Play laser sound
                from systems.audio_system import play_sfx
                play_sfx("LAZER")

            # Get events for gameplay input (movement, abilities, etc.)
            # Use events from process_events() (stored in self._current_events)
            # Note: handle_gameplay_input will call _try_spawn_bullet and _try_laser via callbacks
            events = self._current_events
            from systems.input_system import handle_gameplay_input
            from constants import (
                overshield_recharge_cooldown, shield_duration, grenade_cooldown,
                missile_cooldown, ally_drop_cooldown, boost_meter_max,
                boost_drain_per_s, boost_regen_per_s, boost_speed_mult, slow_speed_mult
            )
            gameplay_input_ctx = {
                "controls": self.ctx.controls,
                "aiming_mode": self.ctx.config.aim_mode,
                "width": self.ctx.width,
                "height": self.ctx.height,
                "dt": dt,
                "spawn_player_bullet": _try_spawn_bullet,
                "spawn_laser_beam": _try_laser,
                "overshield_recharge_cooldown": overshield_recharge_cooldown,
                "shield_duration": shield_duration,
                "grenade_cooldown": grenade_cooldown,
                "missile_cooldown": missile_cooldown,
                "ally_drop_cooldown": ally_drop_cooldown,
                "boost_meter_max": boost_meter_max,
                "boost_drain_per_s": boost_drain_per_s,
                "boost_regen_per_s": boost_regen_per_s,
                "boost_speed_mult": boost_speed_mult,
                "slow_speed_mult": slow_speed_mult,
                "world_scale": getattr(self.ctx.config, 'world_scale', 1.0),
            }
            handle_gameplay_input(events, self.game_state, gameplay_input_ctx)

            # Fixed-step simulation: run one or more steps with FIXED_DT
            self.simulation_accumulator, should_quit = game_module._step_simulation(
                self.simulation_accumulator, dt, self.fixed_dt, self.max_sim_steps,
                self.update_simulation, self.ctx, self.game_state, self.scene_stack, self.screen_ctx
            )
            if should_quit:
                return False
            # Optional: for future render interpolation (smooth between steps)
            setattr(self.game_state, "simulation_interpolation", self.simulation_accumulator / self.fixed_dt if self.fixed_dt else 0.0)
            # Only update telemetry if enabled (function already has guard, but avoid call overhead)
            if self.telemetry_enabled:
                game_module.update_telemetry(self.game_state, dt, self.ctx)
                # Log frame time for performance analysis
                from systems.telemetry_system import log_frame_time
                log_frame_time(self.game_state, dt, self.ctx)
            self._continue_blink_t = self.game_state.ui.continue_blink_t
        
        else:
            # For non-gameplay states (menus), still call scene update for animations/timers
            current_scene = self.scene_stack.current()
            if current_scene and hasattr(current_scene, 'update'):
                current_scene.update(dt, self.game_state, self.screen_ctx)
        
        # Check if current_screen changed to GAME_OVER during simulation (player death)
        # If so, sync the scene stack
        if self.game_state.current_screen == STATE_GAME_OVER:
            scene_state = game_module._get_current_state(self.scene_stack)
            if scene_state != STATE_GAME_OVER:
                # Player died - push game over scene
                from scenes.game_over import GameOverScene
                self.scene_stack.clear()
                self.scene_stack.push(GameOverScene())
        
        # Check if current_screen changed to VICTORY during simulation (beat all levels)
        # If so, sync the scene stack
        if self.game_state.current_screen == STATE_VICTORY:
            scene_state = game_module._get_current_state(self.scene_stack)
            if scene_state != STATE_VICTORY:
                # Player won - push victory scene
                from scenes.victory import VictoryScene
                self.scene_stack.clear()
                self.scene_stack.push(VictoryScene())
        
        return True

    def render(self) -> None:
        """Render the current scene."""
        import game as game_module
        from constants import STATE_PLAYING, STATE_ENDURANCE
        
        # Determine if we're in gameplay (needs world surface scaling)
        current_state = game_module._get_current_state(self.scene_stack) or self.game_state.current_screen
        is_gameplay = current_state in (STATE_PLAYING, STATE_ENDURANCE)
        
        # Render the current scene
        game_module._render_current_scene(
            self.ctx, self.game_state, self.scene_stack, self.screen_ctx,
            self.pause_shaders_enabled, self.menu_shaders_enabled
        )
        
        # Scale world surface to display only for gameplay (world_scale > 1.0)
        # Skip scaling when camera is active (camera renders directly to display)
        from systems.camera import get_camera
        camera = get_camera()
        world_scale = getattr(self.ctx.config, 'world_scale', 1.0)
        
        # Only scale if:
        # 1. In gameplay
        # 2. World scale > 1.0
        # 3. Camera is NOT active (camera renders directly to display, no scaling needed)
        # 4. World surface exists
        if is_gameplay and world_scale > 1.0 and camera is None and self.ctx.world_surface is not None:
            # Scale down the world surface to fit the display
            # Use scale() instead of smoothscale() for better performance
            # The visual difference at 1.33x is minimal
            pygame.transform.scale(
                self.ctx.world_surface,
                (self.ctx.display_width, self.ctx.display_height),
                self.ctx.screen  # Render directly to screen (avoids creating new surface)
            )
        
        pygame.display.flip()
        
        # Write flow state back to GameState after this iteration
        # Update current_screen from scene stack if it changed
        scene_state = game_module._get_current_state(self.scene_stack)
        if scene_state:
            self.game_state.current_screen = scene_state
        self.game_state.previous_screen = self._previous_game_state
        # pause_selected is updated directly by pause handler, so don't overwrite it
        # game_state.ui.pause_selected = pause_selected  # Removed - handler updates directly
        self.game_state.ui.continue_blink_t = self._continue_blink_t
        self.game_state.ui.controls_selected = self._controls_selected
        self.game_state.controls_rebinding = self._controls_rebinding

    def run(self) -> None:
        """Run the main loop (event handling, update, render)."""
        import game as game_module
        from systems.fps_tracker import record_frame as fps_record_frame
        
        running = True
        
        try:
            while running:
                # Use config's target_fps (allows dynamic changes via pause menu)
                # 0 = uncapped (max FPS)
                target_fps = getattr(self.ctx.config, 'target_fps', 0)
                if target_fps > 0:
                    dt = self.ctx.clock.tick(target_fps) / 1000.0
                else:
                    # Uncapped: use tick_busy_loop for more accurate timing at high FPS
                    dt = self.ctx.clock.tick_busy_loop() / 1000.0
                game_module._perf_record_frame(dt)  # no-op unless GAME_DEBUG_PERF=1
                
                # Record frame time for FPS graph (always active)
                game_time = getattr(self.game_state, 'run_time', 0.0)
                fps_record_frame(dt, game_time)
                
                # Process events
                running = self.process_events()
                if not running:
                    break
                
                # Update simulation
                running = self.update(dt)
                if not running:
                    break
                
                # Render
                self.render()
                
                # Store simulation accumulator back to app
                # (This is needed because _step_simulation modifies it)
                # Actually, it's already stored in self.simulation_accumulator, so we're good

        except KeyboardInterrupt:
            print("Interrupted by user (Ctrl+C). Saving run...")
        
        except Exception as e:
            print("Unhandled exception:", repr(e))
            raise
        
        finally:
            game_module._handle_exit(self.ctx, self.game_state)
