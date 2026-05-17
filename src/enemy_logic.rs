use crate::level_data::{is_wall, Archetype, Level, Vec2};
use crate::player_state::{self, Player};
use crate::visual_effects::{
    spawn_blood_splat, spawn_enemy_corpse, spawn_enemy_death_fade, spawn_wall_puff, VisualEffects,
    ENEMY_DEATH_FADE_DURATION, ENEMY_PAIN_FLASH_DURATION,
};

// Shared constants (both archetypes)
pub const ENEMY_SPEED_TILES_PER_SEC: f32 = 2.0;
pub const ENEMY_RADIUS_TILES: f32 = 0.375;
pub const ENEMY_REACTION_DELAY: f32 = 0.23;
pub const ENEMY_PAIN_DURATION: f32 = 0.17;
pub const ENEMY_CONTACT_RANGE_TILES: f32 = 0.8125;
pub const ENEMY_ATTACK_RANGE_TILES: f32 = 64.0;
pub const ENEMY_ATTACK_SPREAD_RAD: f32 = 0.3839;
pub const ENEMY_ATTACK_WINDUP_SEC: f32 = 0.286;
pub const ENEMY_ATTACK_DAMAGE_VALUES: [i32; 5] = [3, 6, 9, 12, 15];

// Module-private per-archetype stats
#[derive(Clone, Copy, Debug)]
struct ArchetypeStats {
    max_health: i32,
    pain_chance: f32,
    pellet_count: u32,
    attack_sequence_sec: f32,
}

const BASIC_TROOPER_STATS: ArchetypeStats = ArchetypeStats {
    max_health: 20,
    pain_chance: 0.78,
    pellet_count: 1,
    attack_sequence_sec: 0.74,
};

const SHOTGUN_TROOPER_STATS: ArchetypeStats = ArchetypeStats {
    max_health: 30,
    pain_chance: 170.0 / 256.0,
    pellet_count: 3,
    attack_sequence_sec: 30.0 / 35.0,
};

fn archetype_stats(a: Archetype) -> &'static ArchetypeStats {
    match a {
        Archetype::BasicTrooper => &BASIC_TROOPER_STATS,
        Archetype::ShotgunTrooper => &SHOTGUN_TROOPER_STATS,
    }
}

const TRACE_STEP: f32 = 0.1;
const ENEMY_RNG_SEED: u64 = 0xCAFE_BABE_8765_4321;
const LCG_A: u64 = 6364136223846793005;
const LCG_C: u64 = 1442695040888963407;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum EnemyState {
    Idle,
    Chase,
    Attack,
    Pain,
    Dead,
}

pub struct Enemy {
    pub pos: Vec2,
    pub archetype: Archetype,
    pub health: i32,
    pub alive: bool,
    pub state: EnemyState,
    pub time_in_state: f32,
    pub pain_flash_remaining: f32,
    pub time_since_attack: f32,
    pub attack_fired_this_sequence: bool,
    pub death_fade_remaining: f32,
    pub corpse_spawned: bool,
    pub ammo_drop_spawned: bool,
    rng: u64,
}

pub fn new(spawn: Vec2, archetype: Archetype) -> Enemy {
    let stats = archetype_stats(archetype);
    Enemy {
        pos: spawn,
        archetype,
        health: stats.max_health,
        alive: true,
        state: EnemyState::Idle,
        time_in_state: 0.0,
        pain_flash_remaining: 0.0,
        time_since_attack: stats.attack_sequence_sec,
        attack_fired_this_sequence: false,
        death_fade_remaining: 0.0,
        corpse_spawned: false,
        ammo_drop_spawned: false,
        rng: ENEMY_RNG_SEED,
    }
}

pub fn update(
    enemy: &mut Enemy,
    player: &mut Player,
    level: &Level,
    fx: &mut VisualEffects,
    dt: f32,
) {
    let stats = archetype_stats(enemy.archetype);

    // Tick per-frame timers unconditionally
    enemy.time_in_state += dt;
    enemy.time_since_attack += dt;
    enemy.pain_flash_remaining = (enemy.pain_flash_remaining - dt).max(0.0);

    match enemy.state {
        EnemyState::Idle => {
            if enemy.time_in_state >= ENEMY_REACTION_DELAY {
                enemy.state = EnemyState::Chase;
                enemy.time_in_state = 0.0;
            }
        }
        EnemyState::Chase => {
            if !player.alive {
                return;
            }
            let dx = player.pos - enemy.pos;
            let dist = dx.length();
            if dist <= ENEMY_ATTACK_RANGE_TILES
                && enemy_has_los(enemy.pos, player.pos, level)
                && enemy.time_since_attack >= stats.attack_sequence_sec
            {
                enemy.state = EnemyState::Attack;
                enemy.time_in_state = 0.0;
                enemy.time_since_attack = 0.0;
                enemy.attack_fired_this_sequence = false;
                return;
            } else if dist > ENEMY_CONTACT_RANGE_TILES {
                let move_dist = ENEMY_SPEED_TILES_PER_SEC * dt;
                let nx = dx.x / dist;
                let ny = dx.y / dist;
                let new_x = enemy.pos.x + nx * move_dist;
                let new_y = enemy.pos.y + ny * move_dist;

                if !enemy_collides(level, new_x, enemy.pos.y) {
                    enemy.pos.x = new_x;
                }
                if !enemy_collides(level, enemy.pos.x, new_y) {
                    enemy.pos.y = new_y;
                }
            }
        }
        EnemyState::Attack => {
            if !player.alive {
                enemy.state = EnemyState::Chase;
                enemy.time_in_state = 0.0;
                return;
            }
            if !enemy.attack_fired_this_sequence && enemy.time_in_state >= ENEMY_ATTACK_WINDUP_SEC
            {
                // Compute base aim angle once; all pellets share it
                let dir_to_player = player.pos - enemy.pos;
                let base_angle = dir_to_player.y.atan2(dir_to_player.x);

                for _ in 0..stats.pellet_count {
                    let spread_a = lcg_f32(&mut enemy.rng);
                    let spread_b = lcg_f32(&mut enemy.rng);
                    let spread = (spread_a - spread_b) * ENEMY_ATTACK_SPREAD_RAD;
                    let aim_angle = base_angle + spread;
                    let dir = Vec2::new(aim_angle.cos(), aim_angle.sin());

                    let damage_idx = (lcg_next(&mut enemy.rng) % 5) as usize;
                    let dmg = ENEMY_ATTACK_DAMAGE_VALUES[damage_idx];

                    let mut t = 0.0_f32;
                    loop {
                        t += TRACE_STEP;
                        if t > ENEMY_ATTACK_RANGE_TILES {
                            break;
                        }
                        let step_pos =
                            Vec2::new(enemy.pos.x + dir.x * t, enemy.pos.y + dir.y * t);
                        if step_pos.distance_to(player.pos)
                            < crate::player_state::PLAYER_RADIUS_TILES
                        {
                            player_state::take_damage(player, dmg);
                            spawn_blood_splat(fx, player.pos);
                            break;
                        }
                        if is_wall(level, step_pos.x.floor() as i32, step_pos.y.floor() as i32) {
                            spawn_wall_puff(fx, step_pos);
                            break;
                        }
                    }
                }

                enemy.attack_fired_this_sequence = true;
            }
            if enemy.time_in_state >= stats.attack_sequence_sec {
                enemy.state = EnemyState::Chase;
                enemy.time_in_state = 0.0;
                enemy.attack_fired_this_sequence = false;
            }
        }
        EnemyState::Pain => {
            if enemy.time_in_state >= ENEMY_PAIN_DURATION {
                enemy.state = EnemyState::Chase;
                enemy.time_in_state = 0.0;
            }
        }
        EnemyState::Dead => {
            if !enemy.corpse_spawned && enemy.death_fade_remaining > 0.0 {
                enemy.death_fade_remaining = (enemy.death_fade_remaining - dt).max(0.0);
            }
            if !enemy.corpse_spawned && enemy.death_fade_remaining == 0.0 {
                spawn_enemy_corpse(fx, enemy.pos);
                enemy.corpse_spawned = true;
            }
        }
    }
}

pub fn take_damage(enemy: &mut Enemy, amount: i32, fx: &mut VisualEffects) {
    if !enemy.alive {
        return;
    }
    let stats = archetype_stats(enemy.archetype);
    enemy.health -= amount;
    if enemy.health <= 0 {
        enemy.health = 0;
        enemy.alive = false;
        enemy.state = EnemyState::Dead;
        enemy.time_in_state = 0.0;
        enemy.death_fade_remaining = ENEMY_DEATH_FADE_DURATION;
        spawn_enemy_death_fade(fx, enemy.pos);
    } else {
        let r = lcg_f32(&mut enemy.rng);
        if r < stats.pain_chance {
            enemy.state = EnemyState::Pain;
            enemy.time_in_state = 0.0;
            enemy.pain_flash_remaining = ENEMY_PAIN_FLASH_DURATION;
        }
    }
}

fn enemy_has_los(from: Vec2, to: Vec2, level: &Level) -> bool {
    let dx = to.x - from.x;
    let dy = to.y - from.y;
    let dist = (dx * dx + dy * dy).sqrt();
    if dist < 0.001 {
        return true;
    }
    let nx = dx / dist;
    let ny = dy / dist;
    let mut t = 0.0_f32;
    loop {
        t += TRACE_STEP;
        if t >= dist {
            return true;
        }
        let px = from.x + nx * t;
        let py = from.y + ny * t;
        if is_wall(level, px.floor() as i32, py.floor() as i32) {
            return false;
        }
    }
}

fn enemy_collides(level: &Level, px: f32, py: f32) -> bool {
    let r = ENEMY_RADIUS_TILES;
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

fn lcg_next(state: &mut u64) -> u64 {
    *state = state.wrapping_mul(LCG_A).wrapping_add(LCG_C);
    *state
}

fn lcg_f32(state: &mut u64) -> f32 {
    (lcg_next(state) >> 33) as f32 / (u32::MAX as f32)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::level_data::{build_default, Archetype};
    use crate::player_state;

    #[test]
    fn test_enemy_new_basic_trooper() {
        let e = new(Vec2::new(5.0, 5.0), Archetype::BasicTrooper);
        assert_eq!(e.health, BASIC_TROOPER_STATS.max_health);
        assert!(e.alive);
        assert_eq!(e.state, EnemyState::Idle);
        assert!(!e.attack_fired_this_sequence);
        assert!(!e.ammo_drop_spawned);
        assert_eq!(e.time_since_attack, BASIC_TROOPER_STATS.attack_sequence_sec);
        assert_eq!(e.archetype, Archetype::BasicTrooper);
    }

    #[test]
    fn test_enemy_new_shotgun_trooper() {
        let e = new(Vec2::new(5.0, 5.0), Archetype::ShotgunTrooper);
        assert_eq!(e.health, SHOTGUN_TROOPER_STATS.max_health);
        assert_eq!(e.archetype, Archetype::ShotgunTrooper);
        assert_eq!(e.time_since_attack, SHOTGUN_TROOPER_STATS.attack_sequence_sec);
    }

    #[test]
    fn test_enemy_idle_to_chase() {
        let level = build_default();
        let mut e = new(Vec2::new(5.0, 5.0), Archetype::BasicTrooper);
        let mut player = player_state::new(Vec2::new(2.5, 2.5), 0);
        let mut fx = crate::visual_effects::new();
        update(&mut e, &mut player, &level, &mut fx, ENEMY_REACTION_DELAY + 0.01);
        assert_eq!(e.state, EnemyState::Chase);
    }

    #[test]
    fn test_enemy_take_damage_kills() {
        let mut e = new(Vec2::new(5.0, 5.0), Archetype::BasicTrooper);
        let mut fx = crate::visual_effects::new();
        take_damage(&mut e, BASIC_TROOPER_STATS.max_health + 1, &mut fx);
        assert!(!e.alive);
        assert_eq!(e.state, EnemyState::Dead);
        assert!(!e.ammo_drop_spawned);
    }

    #[test]
    fn test_enemy_take_damage_no_op_when_dead() {
        let mut e = new(Vec2::new(5.0, 5.0), Archetype::BasicTrooper);
        let mut fx = crate::visual_effects::new();
        take_damage(&mut e, BASIC_TROOPER_STATS.max_health + 1, &mut fx);
        let health_before = e.health;
        take_damage(&mut e, 10, &mut fx);
        assert_eq!(e.health, health_before);
    }

    #[test]
    fn test_enemy_corpse_spawns_after_fade() {
        let level = build_default();
        let mut e = new(Vec2::new(5.0, 5.0), Archetype::BasicTrooper);
        let mut player = player_state::new(Vec2::new(2.5, 2.5), 0);
        let mut fx = crate::visual_effects::new();
        take_damage(&mut e, BASIC_TROOPER_STATS.max_health, &mut fx);
        update(&mut e, &mut player, &level, &mut fx, ENEMY_DEATH_FADE_DURATION + 0.01);
        let corpse_count = fx
            .effects
            .iter()
            .filter(|ef| ef.kind == crate::visual_effects::EffectKind::EnemyCorpse)
            .count();
        assert_eq!(corpse_count, 1);
        assert!(e.corpse_spawned);
    }

    #[test]
    fn test_enemy_pain_state_returns_to_chase() {
        let level = build_default();
        let mut e = new(Vec2::new(5.0, 5.0), Archetype::BasicTrooper);
        let mut player = player_state::new(Vec2::new(2.5, 2.5), 0);
        let mut fx = crate::visual_effects::new();
        e.state = EnemyState::Pain;
        e.time_in_state = 0.0;
        update(&mut e, &mut player, &level, &mut fx, ENEMY_PAIN_DURATION + 0.01);
        assert_eq!(e.state, EnemyState::Chase);
    }

    #[test]
    fn test_attack_state_fires_at_windup() {
        let level = build_default();
        let mut e = new(Vec2::new(5.0, 5.0), Archetype::BasicTrooper);
        let mut player = player_state::new(Vec2::new(5.0, 5.5), 0);
        let mut fx = crate::visual_effects::new();
        e.state = EnemyState::Attack;
        e.time_in_state = 0.0;
        e.attack_fired_this_sequence = false;
        update(&mut e, &mut player, &level, &mut fx, ENEMY_ATTACK_WINDUP_SEC + 0.01);
        assert!(e.attack_fired_this_sequence);
    }

    #[test]
    fn test_attack_state_transitions_to_chase_after_sequence() {
        let level = build_default();
        let mut e = new(Vec2::new(5.0, 5.0), Archetype::BasicTrooper);
        let mut player = player_state::new(Vec2::new(5.0, 5.5), 0);
        let mut fx = crate::visual_effects::new();
        e.state = EnemyState::Attack;
        // BasicTrooper attack_sequence_sec = 0.74
        e.time_in_state = 0.74_f32;
        e.attack_fired_this_sequence = true;
        update(&mut e, &mut player, &level, &mut fx, 0.001);
        assert_eq!(e.state, EnemyState::Chase);
        assert!(!e.attack_fired_this_sequence);
    }

    #[test]
    fn test_shotgun_trooper_fires_multiple_pellets() {
        // ShotgunTrooper should fire 3 pellets per salvo. Place enemy very close to player
        // so pellets are likely to hit (or at least LoS is clear). The test checks that the
        // attack_fired_this_sequence latch flips after a single Attack update.
        let level = build_default();
        let mut e = new(Vec2::new(5.0, 5.0), Archetype::ShotgunTrooper);
        let mut player = player_state::new(Vec2::new(5.0, 5.5), 0);
        let mut fx = crate::visual_effects::new();
        e.state = EnemyState::Attack;
        e.time_in_state = 0.0;
        e.attack_fired_this_sequence = false;
        update(&mut e, &mut player, &level, &mut fx, ENEMY_ATTACK_WINDUP_SEC + 0.01);
        assert!(e.attack_fired_this_sequence);
    }

    #[test]
    fn test_enemy_has_los_clear_path() {
        let level = build_default();
        let from = Vec2::new(2.5, 2.5);
        let to = Vec2::new(3.5, 2.5);
        assert!(enemy_has_los(from, to, &level));
    }

    #[test]
    fn test_enemy_has_los_blocked() {
        let level = build_default();
        // The border walls block LoS through them
        let from = Vec2::new(2.5, 2.5);
        let to = Vec2::new(2.5, -1.0); // through the north border wall
        assert!(!enemy_has_los(from, to, &level));
    }
}
