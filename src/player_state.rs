use crate::input_controller::InputState;
use crate::level_data::{is_wall, Level, Vec2};
use crate::visual_effects::{DAMAGE_TINT_CAP, DAMAGE_TINT_DECAY_PER_SEC};

pub const PLAYER_MAX_HEALTH: i32 = 100;
pub const PLAYER_AMMO_INITIAL: i32 = 12;
pub const PLAYER_AMMO_MAX: i32 = 30;
pub const PICKUP_HEALTH_AMOUNT: i32 = 25;
pub const PICKUP_AMMO_AMOUNT: i32 = 10;
pub const PLAYER_ARMOR_INITIAL: u8 = 0;
pub const PICKUP_ARMOR_GREEN_TARGET_POINTS: u8 = 100;
pub const PICKUP_ARMOR_BLUE_TARGET_POINTS: u8 = 200;
pub const ARMOR_GREEN_ABSORB_NUM: u32 = 1;
pub const ARMOR_GREEN_ABSORB_DEN: u32 = 3;
pub const ARMOR_BLUE_ABSORB_NUM: u32 = 1;
pub const ARMOR_BLUE_ABSORB_DEN: u32 = 2;
pub const PLAYER_TURN_SPEED: f32 = 2.0;
pub const THRUST_FACTOR: f32 = 10.0;
pub const FRICTION: f32 = 0.906;
pub const STOP_THRESHOLD: f32 = 0.0625;
pub const MAX_SPEED: f32 = 0.3;
pub const PLAYER_RADIUS_TILES: f32 = 0.4375;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ArmorTier {
    None,
    Green,
    Blue,
}

pub struct Player {
    pub pos: Vec2,
    pub vel: Vec2,
    pub facing: f32,
    pub health: i32,
    pub alive: bool,
    pub damage_count: f32,
    pub time_since_fire: f32,
    pub ammo: i32,
    pub armor: u8,
    pub armor_type: ArmorTier,
    pub weapon_rng: u64,
}

pub fn new(spawn: Vec2, weapon_rng_seed: u64) -> Player {
    Player {
        pos: spawn,
        vel: Vec2::default(),
        facing: 0.0,
        health: PLAYER_MAX_HEALTH,
        alive: true,
        damage_count: 0.0,
        time_since_fire: f32::INFINITY,
        ammo: PLAYER_AMMO_INITIAL,
        armor: PLAYER_ARMOR_INITIAL,
        armor_type: ArmorTier::None,
        weapon_rng: weapon_rng_seed,
    }
}

pub fn apply_input(player: &mut Player, input: &InputState, level: &Level, dt: f32) {
    // 1. Turn
    player.facing += input.turn * PLAYER_TURN_SPEED * dt;
    player.facing = player.facing.rem_euclid(std::f32::consts::TAU);

    // 2-3. Thrust
    let forward_thrust = input.forward * THRUST_FACTOR / 1000.0;
    let strafe_thrust = input.strafe * THRUST_FACTOR / 1000.0;

    let cos_f = player.facing.cos();
    let sin_f = player.facing.sin();

    let fv = Vec2::new(cos_f * forward_thrust, sin_f * forward_thrust);
    let sv = Vec2::new(-sin_f * strafe_thrust, cos_f * strafe_thrust);

    // 4. Apply thrust
    player.vel.x += fv.x + sv.x;
    player.vel.y += fv.y + sv.y;

    // 5. Friction
    player.vel.x *= FRICTION;
    player.vel.y *= FRICTION;

    // 6. Clamp to max speed
    player.vel.x = player.vel.x.clamp(-MAX_SPEED, MAX_SPEED);
    player.vel.y = player.vel.y.clamp(-MAX_SPEED, MAX_SPEED);

    // 7. Stop threshold
    let has_input = input.forward != 0.0 || input.strafe != 0.0;
    if !has_input && player.vel.length() < STOP_THRESHOLD * MAX_SPEED {
        player.vel = Vec2::default();
    }

    // 8. Move with axis-aligned slide
    let dx = player.vel.x * dt * 60.0;
    let dy = player.vel.y * dt * 60.0;

    let new_x = player.pos.x + dx;
    let new_y = player.pos.y + dy;

    let r = PLAYER_RADIUS_TILES;

    // Try x
    if !collides_with_wall(level, new_x, player.pos.y, r) {
        player.pos.x = new_x;
    }
    // Try y
    if !collides_with_wall(level, player.pos.x, new_y, r) {
        player.pos.y = new_y;
    }

    // 9. Increment time_since_fire
    player.time_since_fire += dt;
}

fn collides_with_wall(level: &Level, px: f32, py: f32, r: f32) -> bool {
    let corners = [
        (px - r, py - r),
        (px + r, py - r),
        (px - r, py + r),
        (px + r, py + r),
    ];
    for (cx, cy) in corners {
        if is_wall(level, cx.floor() as i32, cy.floor() as i32) {
            return true;
        }
    }
    false
}

pub fn take_damage(player: &mut Player, amount: i32) {
    let mut saved: u32 = 0;
    if player.armor_type != ArmorTier::None && player.armor > 0 {
        let (num, den) = match player.armor_type {
            ArmorTier::Green => (ARMOR_GREEN_ABSORB_NUM, ARMOR_GREEN_ABSORB_DEN),
            ArmorTier::Blue  => (ARMOR_BLUE_ABSORB_NUM,  ARMOR_BLUE_ABSORB_DEN),
            ArmorTier::None  => unreachable!(),
        };
        saved = (amount as u32) * num / den;
        if saved > player.armor as u32 {
            saved = player.armor as u32;
            player.armor_type = ArmorTier::None;
        }
        player.armor -= saved as u8;
    }
    let residual = amount - saved as i32;
    player.health -= residual;
    player.damage_count = (player.damage_count + residual as f32).min(DAMAGE_TINT_CAP);
    if player.health <= 0 {
        player.alive = false;
        player.health = 0;
    }
}

pub fn take_armor_pickup(player: &mut Player, tier: ArmorTier) {
    let target = match tier {
        ArmorTier::Green => PICKUP_ARMOR_GREEN_TARGET_POINTS,
        ArmorTier::Blue  => PICKUP_ARMOR_BLUE_TARGET_POINTS,
        ArmorTier::None  => return,
    };
    player.armor = target;
    player.armor_type = tier;
}

pub fn decay_damage_tint(player: &mut Player, dt: f32) {
    player.damage_count = (player.damage_count - DAMAGE_TINT_DECAY_PER_SEC * dt).max(0.0);
}

pub fn take_health_pickup(player: &mut Player, amount: i32) {
    player.health = (player.health + amount).min(PLAYER_MAX_HEALTH);
}

pub fn take_ammo_pickup(player: &mut Player, amount: i32) {
    player.ammo = (player.ammo + amount).min(PLAYER_AMMO_MAX);
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::level_data::build_default;

    #[test]
    fn test_new_player_initial_state() {
        let p = new(Vec2::new(2.5, 2.5), 0xDEADBEEF);
        assert_eq!(p.health, PLAYER_MAX_HEALTH);
        assert!(p.alive);
        assert_eq!(p.ammo, PLAYER_AMMO_INITIAL);
        assert!(p.time_since_fire.is_infinite());
    }

    #[test]
    fn test_take_damage_reduces_health() {
        let mut p = new(Vec2::new(2.5, 2.5), 0);
        take_damage(&mut p, 30);
        assert_eq!(p.health, 70);
        assert!(p.alive);
    }

    #[test]
    fn test_take_damage_kills_at_zero() {
        let mut p = new(Vec2::new(2.5, 2.5), 0);
        take_damage(&mut p, 200);
        assert!(!p.alive);
        assert_eq!(p.health, 0);
    }

    #[test]
    fn test_take_health_pickup_clamps() {
        let mut p = new(Vec2::new(2.5, 2.5), 0);
        p.health = 90;
        take_health_pickup(&mut p, PICKUP_HEALTH_AMOUNT);
        assert_eq!(p.health, PLAYER_MAX_HEALTH);
    }

    #[test]
    fn test_take_ammo_pickup_clamps() {
        let mut p = new(Vec2::new(2.5, 2.5), 0);
        p.ammo = 25;
        take_ammo_pickup(&mut p, PICKUP_AMMO_AMOUNT);
        assert_eq!(p.ammo, PLAYER_AMMO_MAX);
    }

    #[test]
    fn test_armor_absorbs_damage_green() {
        let mut p = new(Vec2::new(2.5, 2.5), 0);
        take_armor_pickup(&mut p, ArmorTier::Green);
        assert_eq!(p.armor, PICKUP_ARMOR_GREEN_TARGET_POINTS);
        assert_eq!(p.armor_type, ArmorTier::Green);
        take_damage(&mut p, 15);
        // saved = 15 * 1 / 3 = 5; residual = 10
        assert_eq!(p.armor, 95);
        assert_eq!(p.health, 90);
    }

    #[test]
    fn test_armor_depletes_clears_type() {
        let mut p = new(Vec2::new(2.5, 2.5), 0);
        p.armor = 2;
        p.armor_type = ArmorTier::Green;
        take_damage(&mut p, 15);
        // saved would be 5 > armor(2), so saved = 2, type cleared
        assert_eq!(p.armor, 0);
        assert_eq!(p.armor_type, ArmorTier::None);
        assert_eq!(p.health, PLAYER_MAX_HEALTH - 13);
    }

    #[test]
    fn test_take_armor_pickup_blue() {
        let mut p = new(Vec2::new(2.5, 2.5), 0);
        take_armor_pickup(&mut p, ArmorTier::Blue);
        assert_eq!(p.armor, PICKUP_ARMOR_BLUE_TARGET_POINTS);
        assert_eq!(p.armor_type, ArmorTier::Blue);
    }

    #[test]
    fn test_decay_damage_tint() {
        let mut p = new(Vec2::new(2.5, 2.5), 0);
        p.damage_count = 50.0;
        decay_damage_tint(&mut p, 1.0);
        assert!((p.damage_count - (50.0 - DAMAGE_TINT_DECAY_PER_SEC)).abs() < 0.01);
    }

    #[test]
    fn test_apply_input_forward_moves_player() {
        let level = build_default();
        let mut p = new(Vec2::new(2.5, 2.5), 0);
        let input = InputState { forward: 1.0, strafe: 0.0, turn: 0.0, fire: false, quit: false };
        let start = p.pos;
        apply_input(&mut p, &input, &level, 1.0 / 60.0);
        assert!(p.pos.distance_to(start) > 0.0);
    }

    #[test]
    fn test_apply_input_collides_with_wall() {
        let level = build_default();
        // Place player near west border wall (x=0 is wall)
        let mut p = new(Vec2::new(1.0, 7.0), 0);
        // Try to walk into west wall (facing west = PI)
        p.facing = std::f32::consts::PI;
        let input = InputState { forward: 1.0, strafe: 0.0, turn: 0.0, fire: false, quit: false };
        for _ in 0..100 {
            apply_input(&mut p, &input, &level, 1.0 / 60.0);
        }
        // Should not penetrate wall at x=0
        assert!(p.pos.x >= PLAYER_RADIUS_TILES);
    }
}
