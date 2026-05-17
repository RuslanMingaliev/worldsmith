use crate::enemy_logic::{take_damage as enemy_take_damage, Enemy, ENEMY_RADIUS_TILES};
use crate::level_data::{is_wall, Level, Vec2};
use crate::player_state::Player;
use crate::visual_effects::{
    spawn_blood_splat, spawn_muzzle_flash, spawn_tracer, spawn_wall_puff, VisualEffects,
    MUZZLE_OFFSET,
};

pub const PISTOL_FIRE_CYCLE: f32 = 0.54;
pub const PISTOL_RANGE_TILES: f32 = 64.0;
pub const PISTOL_REFIRE_SPREAD_RAD: f32 = 0.0977;
pub const IDLE_THRESHOLD_SEC: f32 = 1.0;
pub const TRACE_STEP: f32 = 0.1;

// LCG constants (Numerical Recipes)
const LCG_A: u64 = 6364136223846793005;
const LCG_C: u64 = 1442695040888963407;

fn lcg_next(state: &mut u64) -> u64 {
    *state = state.wrapping_mul(LCG_A).wrapping_add(LCG_C);
    *state
}

fn lcg_f32(state: &mut u64) -> f32 {
    (lcg_next(state) >> 33) as f32 / (u32::MAX as f32)
}

pub fn fire(
    player: &mut Player,
    enemies: &mut [Enemy],
    level: &Level,
    fx: &mut VisualEffects,
) {
    // 1. Cooldown gate
    if player.time_since_fire < PISTOL_FIRE_CYCLE {
        return;
    }
    // 2. Ammo gate
    if player.ammo == 0 {
        return;
    }

    // 3. Compute aim angle
    let aim_angle = if player.time_since_fire >= IDLE_THRESHOLD_SEC {
        player.facing
    } else {
        let spread = (lcg_f32(&mut player.weapon_rng) - lcg_f32(&mut player.weapon_rng))
            * PISTOL_REFIRE_SPREAD_RAD;
        player.facing + spread
    };

    // 4. Reset fire timer
    player.time_since_fire = 0.0;

    // 5. Muzzle position
    let muzzle_pos = Vec2::new(
        player.pos.x + aim_angle.cos() * MUZZLE_OFFSET,
        player.pos.y + aim_angle.sin() * MUZZLE_OFFSET,
    );

    // 6. Spawn muzzle flash
    spawn_muzzle_flash(fx, muzzle_pos);

    // 7. Ray-march
    let dir = Vec2::new(aim_angle.cos(), aim_angle.sin());
    let mut t = 0.0_f32;
    loop {
        t += TRACE_STEP;
        if t > PISTOL_RANGE_TILES {
            let endpoint = Vec2::new(
                muzzle_pos.x + dir.x * PISTOL_RANGE_TILES,
                muzzle_pos.y + dir.y * PISTOL_RANGE_TILES,
            );
            spawn_tracer(fx, muzzle_pos, endpoint);
            break;
        }
        let step_pos = Vec2::new(muzzle_pos.x + dir.x * t, muzzle_pos.y + dir.y * t);

        // Check enemy hit
        let mut hit_enemy = false;
        for enemy in enemies.iter_mut() {
            if !enemy.alive {
                continue;
            }
            if enemy.pos.distance_to(step_pos) < ENEMY_RADIUS_TILES {
                let dmg = pistol_damage_roll_with_rng(&mut player.weapon_rng);
                enemy_take_damage(enemy, dmg, fx);
                spawn_tracer(fx, muzzle_pos, step_pos);
                spawn_blood_splat(fx, step_pos);
                hit_enemy = true;
                break;
            }
        }
        if hit_enemy {
            break;
        }

        // Check wall hit
        if is_wall(level, step_pos.x.floor() as i32, step_pos.y.floor() as i32) {
            spawn_tracer(fx, muzzle_pos, step_pos);
            spawn_wall_puff(fx, step_pos);
            break;
        }
    }

    // 8. Decrement ammo
    player.ammo -= 1;
}

fn pistol_damage_roll_with_rng(rng: &mut u64) -> i32 {
    let r = lcg_next(rng);
    5 * ((r % 3) as i32 + 1)
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pistol_damage_roll_values() {
        let mut rng: u64 = 42;
        for _ in 0..100 {
            let dmg = pistol_damage_roll_with_rng(&mut rng);
            assert!(dmg == 5 || dmg == 10 || dmg == 15);
        }
    }

    #[test]
    fn test_fire_cooldown_gate() {
        use crate::level_data::build_default;
        use crate::player_state;
        let level = build_default();
        let mut player = player_state::new(Vec2::new(2.5, 2.5), 0);
        player.time_since_fire = 0.1; // below PISTOL_FIRE_CYCLE
        let mut enemies = vec![];
        let mut fx = crate::visual_effects::new();
        let ammo_before = player.ammo;
        fire(&mut player, &mut enemies, &level, &mut fx);
        assert_eq!(player.ammo, ammo_before); // no shot
    }

    #[test]
    fn test_fire_ammo_gate() {
        use crate::level_data::build_default;
        use crate::player_state;
        let level = build_default();
        let mut player = player_state::new(Vec2::new(2.5, 2.5), 0);
        player.time_since_fire = f32::INFINITY;
        player.ammo = 0;
        let mut enemies = vec![];
        let mut fx = crate::visual_effects::new();
        fire(&mut player, &mut enemies, &level, &mut fx);
        assert_eq!(fx.effects.len(), 0); // nothing spawned
    }

    #[test]
    fn test_fire_spawns_tracer() {
        use crate::level_data::build_default;
        use crate::player_state;
        use crate::visual_effects::EffectKind;
        let level = build_default();
        let mut player = player_state::new(Vec2::new(2.5, 2.5), 0);
        player.time_since_fire = f32::INFINITY;
        let mut enemies = vec![];
        let mut fx = crate::visual_effects::new();
        fire(&mut player, &mut enemies, &level, &mut fx);
        let has_tracer = fx.effects.iter().any(|e| e.kind == EffectKind::Tracer);
        assert!(has_tracer);
    }

    #[test]
    fn test_fire_consumes_ammo() {
        use crate::level_data::build_default;
        use crate::player_state;
        let level = build_default();
        let mut player = player_state::new(Vec2::new(2.5, 2.5), 0);
        player.time_since_fire = f32::INFINITY;
        let ammo_before = player.ammo;
        let mut enemies = vec![];
        let mut fx = crate::visual_effects::new();
        fire(&mut player, &mut enemies, &level, &mut fx);
        assert_eq!(player.ammo, ammo_before - 1);
    }

    #[test]
    fn test_fire_spawns_muzzle_flash() {
        use crate::level_data::build_default;
        use crate::player_state;
        use crate::visual_effects::EffectKind;
        let level = build_default();
        let mut player = player_state::new(Vec2::new(2.5, 2.5), 0);
        player.time_since_fire = f32::INFINITY;
        let mut enemies = vec![];
        let mut fx = crate::visual_effects::new();
        fire(&mut player, &mut enemies, &level, &mut fx);
        let has_flash = fx.effects.iter().any(|e| e.kind == EffectKind::MuzzleFlash);
        assert!(has_flash);
    }
}
