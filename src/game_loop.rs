use crate::enemy_logic::{self, Enemy};
use crate::input_controller::InputState;
use crate::level_data::{Level, PickupKind, EXIT_RADIUS, PICKUP_RADIUS_TILES};
use crate::player_state::{self, ArmorTier, Player, PLAYER_MAX_HEALTH};
use crate::visual_effects::{self, VisualEffects};
use crate::weapon_system;

// Module-private RNG seed constants
const WEAPON_RNG_SEED: u64 = 0xDEAD_BEEF_1234_5678;
const GAME_OVER_HOLD_SEC: f32 = 2.0;

pub struct GameState {
    pub level: Level,
    pub player: Player,
    pub enemies: Vec<Enemy>,
    pub fx: VisualEffects,
    pub running: bool,
    pub won: bool,
    pub elapsed: f32,
    pub game_over_at: Option<f32>,
    #[cfg(test)]
    pub frames: u64,
}

pub fn new(level: Level) -> GameState {
    let player = player_state::new(level.player_spawn, WEAPON_RNG_SEED);
    let enemies = level.enemy_spawns.iter().map(|s| enemy_logic::new(s.pos, s.archetype)).collect();
    let fx = visual_effects::new();
    GameState {
        level,
        player,
        enemies,
        fx,
        running: true,
        won: false,
        elapsed: 0.0,
        game_over_at: None,
        #[cfg(test)]
        frames: 0,
    }
}

pub fn update(state: &mut GameState, input: &InputState, dt: f32) {
    if input.quit {
        state.running = false;
        return;
    }

    state.elapsed += dt;

    // Player movement
    player_state::apply_input(&mut state.player, input, &state.level, dt);

    // Pickup collision check
    for pickup in &mut state.level.pickups {
        if !pickup.active {
            continue;
        }
        let dist = state.player.pos.distance_to(pickup.pos);
        if dist < PICKUP_RADIUS_TILES {
            match pickup.kind {
                PickupKind::Health => {
                    if state.player.health < PLAYER_MAX_HEALTH {
                        pickup.active = false;
                        player_state::take_health_pickup(
                            &mut state.player,
                            crate::player_state::PICKUP_HEALTH_AMOUNT,
                        );
                        visual_effects::increment_pickup_tint(&mut state.fx);
                    }
                }
                PickupKind::Ammo => {
                    if state.player.ammo < crate::player_state::PLAYER_AMMO_MAX {
                        pickup.active = false;
                        player_state::take_ammo_pickup(
                            &mut state.player,
                            crate::player_state::PICKUP_AMMO_AMOUNT,
                        );
                        visual_effects::increment_pickup_tint(&mut state.fx);
                    }
                }
                PickupKind::ArmorGreen => {
                    if state.player.armor < player_state::PICKUP_ARMOR_GREEN_TARGET_POINTS {
                        pickup.active = false;
                        player_state::take_armor_pickup(
                            &mut state.player,
                            ArmorTier::Green,
                        );
                        visual_effects::increment_pickup_tint(&mut state.fx);
                    }
                }
                PickupKind::ArmorBlue => {
                    if state.player.armor < player_state::PICKUP_ARMOR_BLUE_TARGET_POINTS {
                        pickup.active = false;
                        player_state::take_armor_pickup(
                            &mut state.player,
                            ArmorTier::Blue,
                        );
                        visual_effects::increment_pickup_tint(&mut state.fx);
                    }
                }
            }
        }
    }

    // Enemy AI
    for i in 0..state.enemies.len() {
        // Safety: we need to borrow enemies[i] mut and player mut simultaneously
        // Use split_at_mut pattern
        let (left, right) = state.enemies.split_at_mut(i);
        let (enemy_slice, _) = right.split_at_mut(1);
        let enemy = &mut enemy_slice[0];
        let _ = left; // unused
        enemy_logic::update(enemy, &mut state.player, &state.level, &mut state.fx, dt);
    }

    // Weapon fire
    if input.fire && state.player.alive {
        weapon_system::fire(
            &mut state.player,
            &mut state.enemies,
            &state.level,
            &mut state.fx,
        );
    }

    // Enemy death drops: spawn ammo pickup at each newly-dead enemy's position
    let mut drop_positions: Vec<crate::level_data::Vec2> = vec![];
    for enemy in &mut state.enemies {
        if !enemy.alive && !enemy.ammo_drop_spawned {
            drop_positions.push(enemy.pos);
            enemy.ammo_drop_spawned = true;
        }
    }
    for pos in drop_positions {
        state.level.pickups.push(crate::level_data::Pickup {
            kind: crate::level_data::PickupKind::Ammo,
            pos,
            active: true,
        });
    }

    // Damage tint decay
    player_state::decay_damage_tint(&mut state.player, dt);

    // Visual effects tick
    visual_effects::tick(&mut state.fx, dt);

    // Game over: player died
    if !state.player.alive && state.game_over_at.is_none() {
        state.game_over_at = Some(state.elapsed);
    }

    // Game over: win (reach exit)
    if state.player.pos.distance_to(state.level.exit) < EXIT_RADIUS
        && state.game_over_at.is_none()
    {
        state.won = true;
        state.game_over_at = Some(state.elapsed);
    }

    // Exit action after hold
    if let Some(t0) = state.game_over_at {
        if state.elapsed - t0 >= GAME_OVER_HOLD_SEC {
            state.running = false;
        }
    }

    #[cfg(test)]
    {
        state.frames += 1;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::level_data::build_default;

    #[test]
    fn test_new_game_state() {
        let level = build_default();
        let state = new(level);
        assert!(state.running);
        assert!(!state.won);
        assert_eq!(state.enemies.len(), 2);
        assert!(state.player.alive);
    }

    #[test]
    fn test_quit_input_stops_loop() {
        let level = build_default();
        let mut state = new(level);
        let input = InputState { quit: true, ..Default::default() };
        update(&mut state, &input, 1.0 / 60.0);
        assert!(!state.running);
    }

    #[test]
    fn test_frames_increment() {
        let level = build_default();
        let mut state = new(level);
        let input = InputState::default();
        update(&mut state, &input, 1.0 / 60.0);
        assert_eq!(state.frames, 1);
    }

    #[test]
    fn test_win_when_reaching_exit() {
        let level = build_default();
        let mut state = new(level);
        // Teleport player to exit
        state.player.pos = state.level.exit;
        let input = InputState::default();
        update(&mut state, &input, 1.0 / 60.0);
        assert!(state.won);
        assert!(state.game_over_at.is_some());
    }
}
