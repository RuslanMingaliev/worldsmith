use crate::enemy_logic::{Enemy, ENEMY_RADIUS_TILES};
use crate::level_data::{is_wall, Level, PickupKind, Vec2, TILE_SIZE};
use crate::player_state::Player;
use crate::presentation::{WINDOW_HEIGHT, WINDOW_WIDTH};
use crate::renderer::{
    COLOR_BLOOD, COLOR_CORPSE, COLOR_DAMAGE_TINT, COLOR_ENEMY, COLOR_MUZZLE_FLASH,
    COLOR_PAIN_FLASH, COLOR_PICKUP_TINT, COLOR_PUFF, COLOR_TRACER, DAMAGE_TINT_MAX_ALPHA_PCT,
    PICKUP_AMMO_COLOR, PICKUP_AMMO_SIZE_PX, PICKUP_ARMOR_BLUE_COLOR, PICKUP_ARMOR_GREEN_COLOR,
    PICKUP_ARMOR_SIZE_PX, PICKUP_HEALTH_OUTER_COLOR, PICKUP_HEALTH_SIZE_PX,
    RAYCASTER_HUD_STRIP_HEIGHT_PX,
};
use crate::visual_effects::{
    EffectKind, VisualEffects, BLOOD_RADIUS, DAMAGE_TINT_CAP, DAMAGE_TINT_LEVELS,
    ENEMY_CORPSE_RADIUS, ENEMY_DEATH_FADE_DURATION, MUZZLE_OFFSET, PICKUP_TINT_CAP,
    PICKUP_TINT_LEVEL_COUNT, PUFF_DURATION, PUFF_RADIUS,
};

pub const RAYCASTER_FOV_RADIANS: f32 = std::f32::consts::FRAC_PI_2;
pub const HORIZON_Y: usize =
    (WINDOW_HEIGHT - RAYCASTER_HUD_STRIP_HEIGHT_PX as usize) / 2;
pub const WALL_HEIGHT_TILES: f32 = 1.0;
pub const EYE_HEIGHT_FRACTION: f32 = 41.0 / 128.0;
pub const RAYCASTER_MAX_DEPTH: f32 = 32.0;
pub const RAYCASTER_NSEW_DARKEN_FACTOR: f32 = 0.75;
pub const RAYCASTER_WALL_COLOR_NEAR: u32 = 0xC0C0C0;
pub const RAYCASTER_WALL_COLOR_FAR: u32 = 0x101010;
pub const RAYCASTER_FLOOR_COLOR: u32 = 0x404040;
pub const RAYCASTER_CEILING_COLOR: u32 = 0x202020;
pub const RAYCASTER_SPRITE_NEAR_PLANE: f32 = 0.1;
pub const RAYCASTER_SPRITE_SIDE_CONE_FACTOR: f32 = 4.0;
pub const RAYCASTER_SPRITE_DEPTH_FADE_FACTOR: f32 = 0.7;
pub const RAYCASTER_SPRITE_MIN_PROJ_DIST: f32 = 1.0;
pub const RAYCASTER_EXTRA_LIGHT_SHADE_DELTA: f32 = 0.0625;
pub const RAYCASTER_MUZZLE_FLASH_CENTER_X: usize = WINDOW_WIDTH / 2;
pub const RAYCASTER_MUZZLE_FLASH_CENTER_Y: usize = WINDOW_HEIGHT * 3 / 4;
pub const RAYCASTER_MUZZLE_FLASH_RADIUS_PX: i32 = 24;
pub const RAYCASTER_TRACER_THICKNESS_PX: i32 = 1;
pub const RAYCASTER_PUFF_FULL_BRIGHT_FRACTION: f32 = 0.5;

const PICKUP_TINT_MAX_ALPHA_PCT: u32 = 30;

fn lerp_rgb(near: u32, far: u32, t: f32) -> u32 {
    let nr = (near >> 16) & 0xFF;
    let ng = (near >> 8) & 0xFF;
    let nb = near & 0xFF;
    let fr = (far >> 16) & 0xFF;
    let fg = (far >> 8) & 0xFF;
    let fb_c = far & 0xFF;
    let r = (nr as f32 + (fr as f32 - nr as f32) * t) as u32;
    let g = (ng as f32 + (fg as f32 - ng as f32) * t) as u32;
    let b = (nb as f32 + (fb_c as f32 - nb as f32) * t) as u32;
    (r << 16) | (g << 8) | b
}

fn scale_rgb(color: u32, factor: f32) -> u32 {
    let r = ((color >> 16) & 0xFF) as f32 * factor;
    let g = ((color >> 8) & 0xFF) as f32 * factor;
    let b = (color & 0xFF) as f32 * factor;
    ((r as u32) << 16) | ((g as u32) << 8) | (b as u32)
}

fn blend_pixel(src: u32, tint: u32, alpha_pct: u32) -> u32 {
    let sr = (src >> 16) & 0xFF;
    let sg = (src >> 8) & 0xFF;
    let sb = src & 0xFF;
    let tr = (tint >> 16) & 0xFF;
    let tg = (tint >> 8) & 0xFF;
    let tb = tint & 0xFF;
    let r = (alpha_pct * tr + (100 - alpha_pct) * sr) / 100;
    let g = (alpha_pct * tg + (100 - alpha_pct) * sg) / 100;
    let b = (alpha_pct * tb + (100 - alpha_pct) * sb) / 100;
    (r << 16) | (g << 8) | b
}

struct SpriteCandidate {
    world_half_w: f32,
    world_half_h: f32,
    color: u32,
    full_bright: bool,
    forward_dist: f32,
    right_offset: f32,
}

pub fn draw(
    framebuffer: &mut Vec<u32>,
    level: &Level,
    player: &Player,
    enemies: &[Enemy],
    fx: &VisualEffects,
) {
    let focal_px = (WINDOW_WIDTH as f32 / 2.0) / (RAYCASTER_FOV_RADIANS / 2.0).tan();

    // Precompute angle offsets
    let mut col_angles = [0f32; 640];
    for x in 0..WINDOW_WIDTH {
        col_angles[x] = ((x as f32 - WINDOW_WIDTH as f32 / 2.0) / focal_px).atan();
    }

    // Once-per-frame derived state: is any muzzle flash active?
    let firing_active = fx.effects.iter().any(|e| {
        e.kind == EffectKind::MuzzleFlash && e.lifetime_remaining > 0.0
    });

    let cos_f = player.facing.cos();
    let sin_f = player.facing.sin();

    let mut wall_depth = [RAYCASTER_MAX_DEPTH; 640];

    // ---- Pass 1: wall pass ----
    for x in 0..WINDOW_WIDTH {
        let theta = player.facing + col_angles[x];
        let ray_cos = theta.cos();
        let ray_sin = theta.sin();

        // Grid DDA
        let (perp_dist, ew_wall) = dda_raycast(level, player.pos, ray_cos, ray_sin, col_angles[x]);

        wall_depth[x] = perp_dist;

        let column_h_unclamped = ((WALL_HEIGHT_TILES * focal_px) / perp_dist).max(1.0);

        let mut shade_t = (perp_dist / RAYCASTER_MAX_DEPTH).clamp(0.0, 1.0);
        if firing_active {
            shade_t = (shade_t - RAYCASTER_EXTRA_LIGHT_SHADE_DELTA).clamp(0.0, 1.0);
        }
        let mut wall_color = lerp_rgb(RAYCASTER_WALL_COLOR_NEAR, RAYCASTER_WALL_COLOR_FAR, shade_t);
        if ew_wall {
            wall_color = scale_rgb(wall_color, RAYCASTER_NSEW_DARKEN_FACTOR);
        }

        let horizon = HORIZON_Y as f32;
        let ceiling_top = (horizon - (1.0 - EYE_HEIGHT_FRACTION) * column_h_unclamped)
            .clamp(0.0, WINDOW_HEIGHT as f32) as usize;
        let floor_top = (horizon + EYE_HEIGHT_FRACTION * column_h_unclamped)
            .clamp(0.0, WINDOW_HEIGHT as f32) as usize;

        for y in 0..WINDOW_HEIGHT {
            let color = if y < ceiling_top {
                RAYCASTER_CEILING_COLOR
            } else if y < floor_top {
                wall_color
            } else {
                RAYCASTER_FLOOR_COLOR
            };
            framebuffer[y * WINDOW_WIDTH + x] = color;
        }
    }

    // ---- Pass 2: sprite pass ----
    let mut candidates: Vec<SpriteCandidate> = Vec::with_capacity(32);

    // Live enemies
    for enemy in enemies {
        if !enemy.alive {
            continue;
        }
        let (fwd, right) = camera_transform(player.pos, enemy.pos, cos_f, sin_f);
        if fwd < RAYCASTER_SPRITE_NEAR_PLANE {
            continue;
        }
        if right.abs() > fwd * RAYCASTER_SPRITE_SIDE_CONE_FACTOR {
            continue;
        }
        let color = if enemy.pain_flash_remaining > 0.0 {
            COLOR_PAIN_FLASH
        } else {
            COLOR_ENEMY
        };
        candidates.push(SpriteCandidate {
            world_half_w: ENEMY_RADIUS_TILES,
            world_half_h: ENEMY_RADIUS_TILES,
            color,
            full_bright: false,
            forward_dist: fwd,
            right_offset: right,
        });
    }

    // Death fades
    for eff in &fx.effects {
        if eff.kind != EffectKind::EnemyDeathFade {
            continue;
        }
        let (fwd, right) = camera_transform(player.pos, eff.pos, cos_f, sin_f);
        if fwd < RAYCASTER_SPRITE_NEAR_PLANE {
            continue;
        }
        if right.abs() > fwd * RAYCASTER_SPRITE_SIDE_CONE_FACTOR {
            continue;
        }
        let fade_t = 1.0 - eff.lifetime_remaining / ENEMY_DEATH_FADE_DURATION;
        let half = lerp_f32(ENEMY_RADIUS_TILES, ENEMY_CORPSE_RADIUS / TILE_SIZE, fade_t);
        let color = lerp_rgb(COLOR_ENEMY, COLOR_CORPSE, fade_t);
        candidates.push(SpriteCandidate {
            world_half_w: half,
            world_half_h: half,
            color,
            full_bright: false,
            forward_dist: fwd,
            right_offset: right,
        });
    }

    // Corpses
    for eff in &fx.effects {
        if eff.kind != EffectKind::EnemyCorpse {
            continue;
        }
        let (fwd, right) = camera_transform(player.pos, eff.pos, cos_f, sin_f);
        if fwd < RAYCASTER_SPRITE_NEAR_PLANE {
            continue;
        }
        if right.abs() > fwd * RAYCASTER_SPRITE_SIDE_CONE_FACTOR {
            continue;
        }
        let half = ENEMY_CORPSE_RADIUS / TILE_SIZE;
        candidates.push(SpriteCandidate {
            world_half_w: half,
            world_half_h: half,
            color: COLOR_CORPSE,
            full_bright: false,
            forward_dist: fwd,
            right_offset: right,
        });
    }

    // Blood splats
    for eff in &fx.effects {
        if eff.kind != EffectKind::BloodSplat {
            continue;
        }
        let (fwd, right) = camera_transform(player.pos, eff.pos, cos_f, sin_f);
        if fwd < RAYCASTER_SPRITE_NEAR_PLANE {
            continue;
        }
        if right.abs() > fwd * RAYCASTER_SPRITE_SIDE_CONE_FACTOR {
            continue;
        }
        let half = BLOOD_RADIUS / TILE_SIZE;
        candidates.push(SpriteCandidate {
            world_half_w: half,
            world_half_h: half,
            color: COLOR_BLOOD,
            full_bright: false,
            forward_dist: fwd,
            right_offset: right,
        });
    }

    // Wall puffs
    for eff in &fx.effects {
        if eff.kind != EffectKind::WallPuff {
            continue;
        }
        let (fwd, right) = camera_transform(player.pos, eff.pos, cos_f, sin_f);
        if fwd < RAYCASTER_SPRITE_NEAR_PLANE {
            continue;
        }
        if right.abs() > fwd * RAYCASTER_SPRITE_SIDE_CONE_FACTOR {
            continue;
        }
        let half = PUFF_RADIUS / TILE_SIZE;
        let full_bright = eff.lifetime_remaining / PUFF_DURATION > RAYCASTER_PUFF_FULL_BRIGHT_FRACTION;
        candidates.push(SpriteCandidate {
            world_half_w: half,
            world_half_h: half,
            color: COLOR_PUFF,
            full_bright,
            forward_dist: fwd,
            right_offset: right,
        });
    }

    // Active pickups
    for pickup in &level.pickups {
        if !pickup.active {
            continue;
        }
        let (fwd, right) = camera_transform(player.pos, pickup.pos, cos_f, sin_f);
        if fwd < RAYCASTER_SPRITE_NEAR_PLANE {
            continue;
        }
        if right.abs() > fwd * RAYCASTER_SPRITE_SIDE_CONE_FACTOR {
            continue;
        }
        let (half, color) = match pickup.kind {
            PickupKind::Health => {
                (PICKUP_HEALTH_SIZE_PX as f32 / 2.0 / TILE_SIZE, PICKUP_HEALTH_OUTER_COLOR)
            }
            PickupKind::Ammo => {
                (PICKUP_AMMO_SIZE_PX as f32 / 2.0 / TILE_SIZE, PICKUP_AMMO_COLOR)
            }
            PickupKind::ArmorGreen => {
                (PICKUP_ARMOR_SIZE_PX as f32 / 2.0 / TILE_SIZE, PICKUP_ARMOR_GREEN_COLOR)
            }
            PickupKind::ArmorBlue => {
                (PICKUP_ARMOR_SIZE_PX as f32 / 2.0 / TILE_SIZE, PICKUP_ARMOR_BLUE_COLOR)
            }
        };
        candidates.push(SpriteCandidate {
            world_half_w: half,
            world_half_h: half,
            color,
            full_bright: false,
            forward_dist: fwd,
            right_offset: right,
        });
    }

    // Sort back-to-front (farthest first)
    candidates.sort_by(|a, b| {
        b.forward_dist
            .partial_cmp(&a.forward_dist)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    // Draw sprites
    for cand in &candidates {
        let shaded_color = if cand.full_bright {
            cand.color
        } else {
            let mut sprite_shade_t =
                (cand.forward_dist / RAYCASTER_MAX_DEPTH).clamp(0.0, 1.0) * RAYCASTER_SPRITE_DEPTH_FADE_FACTOR;
            if firing_active {
                sprite_shade_t =
                    (sprite_shade_t - RAYCASTER_EXTRA_LIGHT_SHADE_DELTA).clamp(0.0, 1.0);
            }
            lerp_rgb(cand.color, RAYCASTER_WALL_COLOR_FAR, sprite_shade_t)
        };

        let xscale = focal_px / cand.forward_dist.max(RAYCASTER_SPRITE_MIN_PROJ_DIST);
        let screen_x_center = WINDOW_WIDTH as f32 / 2.0 + cand.right_offset * xscale;
        let half_w_px = cand.world_half_w * xscale;
        let half_h_px = cand.world_half_h * xscale;

        let x1 = (screen_x_center - half_w_px)
            .round()
            .clamp(0.0, (WINDOW_WIDTH as i32 - 1) as f32) as usize;
        let x2 = (screen_x_center + half_w_px)
            .round()
            .clamp(0.0, (WINDOW_WIDTH as i32 - 1) as f32) as usize;
        if x2 < x1 {
            continue;
        }

        let screen_y_center = HORIZON_Y as f32
            + (EYE_HEIGHT_FRACTION - cand.world_half_h) * xscale;
        let y1 = (screen_y_center - half_h_px)
            .round()
            .clamp(0.0, WINDOW_HEIGHT as f32) as usize;
        let y2 = (screen_y_center + half_h_px)
            .round()
            .clamp(0.0, WINDOW_HEIGHT as f32) as usize;

        for x in x1..=x2 {
            if cand.forward_dist < wall_depth[x] {
                for y in y1..y2 {
                    framebuffer[y * WINDOW_WIDTH + x] = shaded_color;
                }
            }
        }
    }

    // ---- Pass 3: effects pass ----

    // Layer 3: tracer lines (world-occluded)
    for eff in &fx.effects {
        if eff.kind != EffectKind::Tracer || eff.lifetime_remaining <= 0.0 {
            continue;
        }

        let tr_end = eff.end_pos - player.pos;
        let forward_dist_end = tr_end.x * cos_f + tr_end.y * sin_f;
        let right_offset_end = tr_end.y * cos_f - tr_end.x * sin_f;

        if forward_dist_end < RAYCASTER_SPRITE_NEAR_PLANE {
            continue;
        }

        let screen_x_end = (WINDOW_WIDTH as f32 / 2.0)
            + right_offset_end * (focal_px / forward_dist_end);
        let x_end_int = screen_x_end
            .round()
            .clamp(0.0, (WINDOW_WIDTH as i32 - 1) as f32) as i32;
        let x_start_int = RAYCASTER_MUZZLE_FLASH_CENTER_X as i32;
        let y_start_int = RAYCASTER_MUZZLE_FLASH_CENTER_Y as i32;
        let y_end_int = HORIZON_Y as i32;

        // Bresenham line from (x_start, y_start) to (x_end, y_end)
        let dx = (x_end_int - x_start_int).abs();
        let dy = (y_end_int - y_start_int).abs();
        let sx = if x_start_int < x_end_int { 1i32 } else { -1i32 };
        let sy = if y_start_int < y_end_int { 1i32 } else { -1i32 };
        let mut err = dx - dy;
        let mut lx = x_start_int;
        let mut ly = y_start_int;
        loop {
            if lx >= 0 && ly >= 0 && (lx as usize) < WINDOW_WIDTH && (ly as usize) < WINDOW_HEIGHT {
                let depth = if x_start_int == x_end_int {
                    forward_dist_end
                } else {
                    lerp_f32(
                        MUZZLE_OFFSET,
                        forward_dist_end,
                        (lx - x_start_int) as f32 / (x_end_int - x_start_int) as f32,
                    )
                };
                if depth < wall_depth[lx as usize] {
                    for thick in 0..RAYCASTER_TRACER_THICKNESS_PX {
                        let ty = ly + thick;
                        if ty >= 0 && (ty as usize) < WINDOW_HEIGHT {
                            framebuffer[ty as usize * WINDOW_WIDTH + lx as usize] = COLOR_TRACER;
                        }
                    }
                }
            }
            if lx == x_end_int && ly == y_end_int {
                break;
            }
            let e2 = 2 * err;
            if e2 > -dy {
                err -= dy;
                lx += sx;
            }
            if e2 < dx {
                err += dx;
                ly += sy;
            }
        }
    }

    // Layer 4: muzzle flash overlay (screen-space)
    if firing_active {
        let cx = RAYCASTER_MUZZLE_FLASH_CENTER_X as i32;
        let cy = RAYCASTER_MUZZLE_FLASH_CENTER_Y as i32;
        let r = RAYCASTER_MUZZLE_FLASH_RADIUS_PX;
        for fy in (cy - r)..(cy + r) {
            for fx2 in (cx - r)..(cx + r) {
                if fx2 >= 0
                    && fy >= 0
                    && (fx2 as usize) < WINDOW_WIDTH
                    && (fy as usize) < WINDOW_HEIGHT
                    && (fx2 - cx).pow(2) + (fy - cy).pow(2) <= r.pow(2)
                {
                    framebuffer[fy as usize * WINDOW_WIDTH + fx2 as usize] = COLOR_MUZZLE_FLASH;
                }
            }
        }
    }

    // Layer 5: damage tint overlay
    if player.damage_count > 0.0 {
        let lvl = ((player.damage_count * DAMAGE_TINT_LEVELS as f32) / DAMAGE_TINT_CAP)
            .ceil() as u32;
        let lvl = lvl.min(DAMAGE_TINT_LEVELS);
        if lvl > 0 {
            let alpha_pct = (DAMAGE_TINT_MAX_ALPHA_PCT * lvl) / DAMAGE_TINT_LEVELS;
            for px in framebuffer.iter_mut() {
                *px = blend_pixel(*px, COLOR_DAMAGE_TINT, alpha_pct);
            }
        }
    }

    // Layer 6: pickup tint overlay
    if fx.pickup_tint_count > 0.0 {
        let pickup_level = ((fx.pickup_tint_count * PICKUP_TINT_LEVEL_COUNT as f32)
            / PICKUP_TINT_CAP)
            .ceil() as u32;
        let pickup_level = pickup_level.min(PICKUP_TINT_LEVEL_COUNT);
        if pickup_level > 0 {
            let alpha_pct = (PICKUP_TINT_MAX_ALPHA_PCT * pickup_level) / PICKUP_TINT_LEVEL_COUNT;
            for px in framebuffer.iter_mut() {
                *px = blend_pixel(*px, COLOR_PICKUP_TINT, alpha_pct);
            }
        }
    }
}

fn camera_transform(player_pos: Vec2, sprite_pos: Vec2, cos_f: f32, sin_f: f32) -> (f32, f32) {
    let tr = sprite_pos - player_pos;
    let forward_dist = tr.x * cos_f + tr.y * sin_f;
    let right_offset = tr.y * cos_f - tr.x * sin_f;
    (forward_dist, right_offset)
}

fn dda_raycast(level: &Level, origin: Vec2, ray_cos: f32, ray_sin: f32, col_angle_offset: f32) -> (f32, bool) {
    let step_x_sign = if ray_cos >= 0.0 { 1.0_f32 } else { -1.0_f32 };
    let step_y_sign = if ray_sin >= 0.0 { 1.0_f32 } else { -1.0_f32 };

    let mut map_x = origin.x.floor() as i32;
    let mut map_y = origin.y.floor() as i32;

    let delta_dist_x = if ray_cos.abs() < 1e-10 {
        f32::INFINITY
    } else {
        (1.0 / ray_cos).abs()
    };
    let delta_dist_y = if ray_sin.abs() < 1e-10 {
        f32::INFINITY
    } else {
        (1.0 / ray_sin).abs()
    };

    let mut side_dist_x = if ray_cos < 0.0 {
        (origin.x - map_x as f32) * delta_dist_x
    } else {
        (map_x as f32 + 1.0 - origin.x) * delta_dist_x
    };
    let mut side_dist_y = if ray_sin < 0.0 {
        (origin.y - map_y as f32) * delta_dist_y
    } else {
        (map_y as f32 + 1.0 - origin.y) * delta_dist_y
    };

    let step_ix = step_x_sign as i32;
    let step_iy = step_y_sign as i32;

    let (hit_dist, ew_wall) = loop {
        let (t, hit_ew) = if side_dist_x < side_dist_y {
            let t = side_dist_x;
            side_dist_x += delta_dist_x;
            map_x += step_ix;
            (t, false) // crossing vertical grid line = EW wall
        } else {
            let t = side_dist_y;
            side_dist_y += delta_dist_y;
            map_y += step_iy;
            (t, true) // crossing horizontal grid line = NS wall
        };

        if t >= RAYCASTER_MAX_DEPTH {
            break (RAYCASTER_MAX_DEPTH, hit_ew);
        }

        if is_wall(level, map_x, map_y) {
            break (t, hit_ew);
        }
    };

    // Fisheye correction: perpendicular distance
    let perp_dist = hit_dist * col_angle_offset.cos();
    let perp_dist = perp_dist.max(0.01);
    (perp_dist, ew_wall)
}

fn lerp_f32(a: f32, b: f32, t: f32) -> f32 {
    a + (b - a) * t
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::level_data::build_default;
    use crate::player_state;
    use crate::visual_effects;

    #[test]
    fn test_draw_does_not_panic() {
        let level = build_default();
        let player = player_state::new(Vec2::new(2.5, 2.5), 0);
        let enemies = vec![];
        let fx = visual_effects::new();
        let mut fb = vec![0u32; WINDOW_WIDTH * WINDOW_HEIGHT];
        draw(&mut fb, &level, &player, &enemies, &fx);
    }

    #[test]
    fn test_draw_fills_framebuffer() {
        let level = build_default();
        let player = player_state::new(Vec2::new(2.5, 2.5), 0);
        let enemies = vec![];
        let fx = visual_effects::new();
        let mut fb = vec![0u32; WINDOW_WIDTH * WINDOW_HEIGHT];
        draw(&mut fb, &level, &player, &enemies, &fx);
        // At least some pixels should be non-zero (walls/floor/ceiling were drawn)
        let nonzero = fb.iter().filter(|&&p| p != 0).count();
        assert!(nonzero > 0);
    }

    #[test]
    fn test_horizon_y_value() {
        assert_eq!(HORIZON_Y, (WINDOW_HEIGHT - RAYCASTER_HUD_STRIP_HEIGHT_PX as usize) / 2);
    }

    #[test]
    fn test_draw_with_enemy() {
        let level = build_default();
        let player = player_state::new(Vec2::new(2.5, 2.5), 0);
        let enemies = vec![crate::enemy_logic::new(Vec2::new(5.0, 2.5), crate::level_data::Archetype::BasicTrooper)];
        let fx = visual_effects::new();
        let mut fb = vec![0u32; WINDOW_WIDTH * WINDOW_HEIGHT];
        draw(&mut fb, &level, &player, &enemies, &fx);
    }

    #[test]
    fn test_draw_with_muzzle_flash() {
        let level = build_default();
        let player = player_state::new(Vec2::new(2.5, 2.5), 0);
        let enemies = vec![];
        let mut fx = visual_effects::new();
        crate::visual_effects::spawn_muzzle_flash(&mut fx, Vec2::new(2.5, 2.5));
        let mut fb = vec![0u32; WINDOW_WIDTH * WINDOW_HEIGHT];
        draw(&mut fb, &level, &player, &enemies, &fx);
    }

    #[test]
    fn test_draw_with_tracer() {
        let level = build_default();
        let player = player_state::new(Vec2::new(2.5, 2.5), 0);
        let enemies = vec![];
        let mut fx = visual_effects::new();
        crate::visual_effects::spawn_tracer(&mut fx, Vec2::new(2.5, 2.5), Vec2::new(5.0, 2.5));
        let mut fb = vec![0u32; WINDOW_WIDTH * WINDOW_HEIGHT];
        draw(&mut fb, &level, &player, &enemies, &fx);
    }
}
