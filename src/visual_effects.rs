use crate::level_data::Vec2;

pub const MUZZLE_FLASH_DURATION: f32 = 0.10;
pub const MUZZLE_FLASH_RADIUS: f32 = 6.0;
pub const MUZZLE_OFFSET: f32 = 0.5;

pub const TRACER_DURATION: f32 = 0.06;
// Tracer thickness = 1 px (single-pixel Bresenham lines; no runtime constant needed)

pub const PUFF_DURATION: f32 = 0.30;
pub const PUFF_RADIUS: f32 = 4.0;

pub const BLOOD_DURATION: f32 = 0.50;
pub const BLOOD_RADIUS: f32 = 6.0;

pub const ENEMY_PAIN_FLASH_DURATION: f32 = 0.10;

pub const DAMAGE_TINT_CAP: f32 = 100.0;
pub const DAMAGE_TINT_DECAY_PER_SEC: f32 = 35.0;
pub const DAMAGE_TINT_LEVELS: u32 = 8;

pub const ENEMY_DEATH_FADE_DURATION: f32 = 0.40;
pub const ENEMY_CORPSE_RADIUS: f32 = 8.0;

pub const PICKUP_TINT_PER_PICKUP: f32 = 6.0;
pub const PICKUP_TINT_LEVEL_COUNT: u32 = 4;
pub const PICKUP_TINT_CAP: f32 = 6.0;
pub const PICKUP_TINT_DECAY_PER_SEC: f32 = 35.0;

pub const EFFECT_LIST_INITIAL_CAPACITY: usize = 16;
pub const PERSISTENT_LIFETIME: f32 = f32::INFINITY;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum EffectKind {
    MuzzleFlash,
    Tracer,
    WallPuff,
    BloodSplat,
    EnemyDeathFade,
    EnemyCorpse,
}

pub struct Effect {
    pub kind: EffectKind,
    pub pos: Vec2,
    pub end_pos: Vec2,
    pub lifetime_remaining: f32,
}

pub struct VisualEffects {
    pub effects: Vec<Effect>,
    pub pickup_tint_count: f32,
}

pub fn new() -> VisualEffects {
    VisualEffects {
        effects: Vec::with_capacity(EFFECT_LIST_INITIAL_CAPACITY),
        pickup_tint_count: 0.0,
    }
}

pub fn spawn_muzzle_flash(fx: &mut VisualEffects, muzzle_pos: Vec2) {
    fx.effects.push(Effect {
        kind: EffectKind::MuzzleFlash,
        pos: muzzle_pos,
        end_pos: Vec2::default(),
        lifetime_remaining: MUZZLE_FLASH_DURATION,
    });
}

pub fn spawn_tracer(fx: &mut VisualEffects, start: Vec2, end: Vec2) {
    fx.effects.push(Effect {
        kind: EffectKind::Tracer,
        pos: start,
        end_pos: end,
        lifetime_remaining: TRACER_DURATION,
    });
}

pub fn spawn_wall_puff(fx: &mut VisualEffects, pos: Vec2) {
    fx.effects.push(Effect {
        kind: EffectKind::WallPuff,
        pos,
        end_pos: Vec2::default(),
        lifetime_remaining: PUFF_DURATION,
    });
}

pub fn spawn_blood_splat(fx: &mut VisualEffects, pos: Vec2) {
    fx.effects.push(Effect {
        kind: EffectKind::BloodSplat,
        pos,
        end_pos: Vec2::default(),
        lifetime_remaining: BLOOD_DURATION,
    });
}

pub fn spawn_enemy_death_fade(fx: &mut VisualEffects, pos: Vec2) {
    fx.effects.push(Effect {
        kind: EffectKind::EnemyDeathFade,
        pos,
        end_pos: Vec2::default(),
        lifetime_remaining: ENEMY_DEATH_FADE_DURATION,
    });
}

pub fn spawn_enemy_corpse(fx: &mut VisualEffects, pos: Vec2) {
    fx.effects.push(Effect {
        kind: EffectKind::EnemyCorpse,
        pos,
        end_pos: Vec2::default(),
        lifetime_remaining: PERSISTENT_LIFETIME,
    });
}

pub fn increment_pickup_tint(fx: &mut VisualEffects) {
    fx.pickup_tint_count = (fx.pickup_tint_count + PICKUP_TINT_PER_PICKUP).min(PICKUP_TINT_CAP);
}

pub fn tick(fx: &mut VisualEffects, dt: f32) {
    for eff in &mut fx.effects {
        if eff.lifetime_remaining.is_finite() {
            eff.lifetime_remaining -= dt;
        }
    }
    fx.effects.retain(|e| !e.lifetime_remaining.is_finite() || e.lifetime_remaining > 0.0);
    fx.pickup_tint_count = (fx.pickup_tint_count - PICKUP_TINT_DECAY_PER_SEC * dt).max(0.0);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_spawn_muzzle_flash() {
        let mut fx = new();
        spawn_muzzle_flash(&mut fx, Vec2::new(1.0, 2.0));
        assert_eq!(fx.effects.len(), 1);
        assert_eq!(fx.effects[0].kind, EffectKind::MuzzleFlash);
    }

    #[test]
    fn test_spawn_tracer() {
        let mut fx = new();
        spawn_tracer(&mut fx, Vec2::new(0.0, 0.0), Vec2::new(5.0, 5.0));
        assert_eq!(fx.effects[0].kind, EffectKind::Tracer);
        assert_eq!(fx.effects[0].end_pos, Vec2::new(5.0, 5.0));
    }

    #[test]
    fn test_tick_removes_expired() {
        let mut fx = new();
        spawn_muzzle_flash(&mut fx, Vec2::default());
        tick(&mut fx, MUZZLE_FLASH_DURATION + 0.01);
        assert_eq!(fx.effects.len(), 0);
    }

    #[test]
    fn test_corpse_persists() {
        let mut fx = new();
        spawn_enemy_corpse(&mut fx, Vec2::default());
        tick(&mut fx, 1000.0);
        assert_eq!(fx.effects.len(), 1);
        assert_eq!(fx.effects[0].kind, EffectKind::EnemyCorpse);
    }

    #[test]
    fn test_increment_pickup_tint_caps() {
        let mut fx = new();
        increment_pickup_tint(&mut fx);
        increment_pickup_tint(&mut fx);
        assert!(fx.pickup_tint_count <= PICKUP_TINT_CAP);
    }

    #[test]
    fn test_pickup_tint_decays() {
        let mut fx = new();
        increment_pickup_tint(&mut fx);
        let before = fx.pickup_tint_count;
        tick(&mut fx, 0.1);
        assert!(fx.pickup_tint_count < before);
    }

    #[test]
    fn test_damage_tint_constants() {
        assert!(DAMAGE_TINT_CAP > 0.0);
        assert!(DAMAGE_TINT_DECAY_PER_SEC > 0.0);
        assert!(DAMAGE_TINT_LEVELS > 0);
    }
}
