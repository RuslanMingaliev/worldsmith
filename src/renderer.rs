use crate::enemy_logic::Enemy;
use crate::level_data::{Level, PickupKind, TILE_SIZE};
use crate::player_state::{ArmorTier, Player, PLAYER_MAX_HEALTH};
use crate::presentation::{WINDOW_HEIGHT, WINDOW_WIDTH};
use crate::visual_effects::{
    EffectKind, VisualEffects, DAMAGE_TINT_CAP, DAMAGE_TINT_LEVELS, ENEMY_CORPSE_RADIUS,
    PICKUP_TINT_CAP, PICKUP_TINT_LEVEL_COUNT,
};

// Color constants
pub const COLOR_WALL: u32 = 0x404040;
pub const COLOR_FLOOR: u32 = 0x808080;
pub const COLOR_PLAYER: u32 = 0x00FF00;
pub const COLOR_ENEMY: u32 = 0xFF0000;
pub const COLOR_EXIT: u32 = 0x00FFFF;
pub const COLOR_DIRECTION_LINE: u32 = 0xFFFF00;
pub const COLOR_MUZZLE_FLASH: u32 = 0xFFFF80;
pub const COLOR_TRACER: u32 = 0xFFFFC0;
pub const COLOR_PUFF: u32 = 0xB0B0B0;
pub const COLOR_BLOOD: u32 = 0xC00000;
pub const COLOR_PAIN_FLASH: u32 = 0xFFFFFF;
pub const COLOR_CORPSE: u32 = 0x602020;
pub const COLOR_DAMAGE_TINT: u32 = 0xFF0000;
pub const COLOR_PICKUP_TINT: u32 = 0xFFCC00;

pub const PLAYER_RADIUS_PX: i32 = 14;
pub const ENEMY_RADIUS_PX: i32 = 12;
pub const EXIT_MARKER_SIZE_PX: i32 = 20;
pub const DIRECTION_LINE_LEN_PX: i32 = 20;
pub const GAME_OVER_BORDER_PX: i32 = 10;
pub const DAMAGE_TINT_MAX_ALPHA_PCT: u32 = 50;

// Pickup sprite constants
pub const PICKUP_HEALTH_SIZE_PX: i32 = 12;
pub const PICKUP_HEALTH_OUTER_COLOR: u32 = 0xFFFFFF;
pub const PICKUP_HEALTH_INNER_COLOR: u32 = 0xFF2020;
pub const PICKUP_HEALTH_INNER_THICKNESS_PX: i32 = 4;
pub const PICKUP_AMMO_SIZE_PX: i32 = 10;
pub const PICKUP_AMMO_COLOR: u32 = 0xFFFF00;
pub const PICKUP_ARMOR_SIZE_PX: i32 = 12;
pub const PICKUP_ARMOR_GREEN_COLOR: u32 = 0x20C020;
pub const PICKUP_ARMOR_BLUE_COLOR: u32 = 0x2060E0;

// HUD constants (topdown)
pub const HUD_PANE_GAP_PX: i32 = 4;
pub const HUD_AMMO_ICON_PX: i32 = 8;
pub const HUD_AMMO_COLOR: u32 = 0xFFFF00;
pub const HUD_ARMOR_ICON_PX: i32 = 8;
pub const HUD_ARMOR_COLOR_GREEN: u32 = 0x20C020;
pub const HUD_ARMOR_COLOR_BLUE: u32 = 0x2060E0;
pub const HUD_ARMOR_COLOR_NONE: u32 = 0x606060;

// FPS HUD strip constants
pub const RAYCASTER_HUD_STRIP_HEIGHT_PX: i32 = 80;
pub const RAYCASTER_HUD_STRIP_COLOR: u32 = 0x585050;
pub const RAYCASTER_HUD_DIGIT_PIXEL_SIZE: i32 = 4;
pub const RAYCASTER_HUD_PANE_X_HEALTH: i32 = 32;
pub const RAYCASTER_HUD_PANE_X_AMMO: i32 = 256;
pub const RAYCASTER_HUD_PANE_X_ARMOR: i32 = 384;
pub const RAYCASTER_HUD_PANE_X_WEAPON: i32 = 480;
pub const RAYCASTER_HUD_HEALTH_COLOR: u32 = 0xD00000;
pub const RAYCASTER_HUD_AMMO_COLOR: u32 = 0xFFFF00;
pub const RAYCASTER_HUD_ARMOR_COLOR_NONE: u32 = 0x606060;
pub const RAYCASTER_HUD_ARMOR_COLOR_GREEN: u32 = 0x20C020;
pub const RAYCASTER_HUD_ARMOR_COLOR_BLUE: u32 = 0x2060E0;
pub const RAYCASTER_HUD_ARMOR_ICON_PX: i32 = 16;
pub const RAYCASTER_HUD_WEAPON_COLOR: u32 = 0xB0B0B0;
pub const RAYCASTER_HUD_HEALTH_ICON_PX: i32 = 16;
pub const RAYCASTER_HUD_HEALTH_ICON_THICKNESS_PX: i32 = 4;
pub const RAYCASTER_HUD_AMMO_ICON_PX: i32 = 16;
pub const RAYCASTER_HUD_WEAPON_ICON_W_PX: i32 = 48;
pub const RAYCASTER_HUD_WEAPON_ICON_H_PX: i32 = 16;

// Topdown HUD internal constants
const HUD_MARGIN: i32 = 4;
const HUD_BAR_WIDTH: i32 = 100;
const HUD_BAR_HEIGHT: i32 = 10;
const HUD_DIGIT_WIDTH: i32 = 3;
const HUD_DIGIT_HEIGHT: i32 = 5;
const HUD_DIGIT_PIXEL_SIZE: i32 = 2;
const HUD_DIGIT_KERN: i32 = 1;
const HUD_HEALTH_BAND_HIGH: f32 = 0.66;
const HUD_HEALTH_BAND_LOW: f32 = 0.33;
const HUD_HEALTH_COLOR_HIGH: u32 = 0x00C000;
const HUD_HEALTH_COLOR_MID: u32 = 0xC0C000;
const HUD_HEALTH_COLOR_LOW: u32 = 0xC00000;
const HUD_BAR_BG_COLOR: u32 = 0x303030;
const PICKUP_TINT_MAX_ALPHA_PCT: u32 = 30;

// 3x5 pixel bitmap font for digits 0-9
// Each row is a bitmask of 3 bits (MSB = leftmost pixel)
const HUD_DIGIT_GLYPHS: [[u8; 5]; 10] = [
    [0b111, 0b101, 0b101, 0b101, 0b111], // 0
    [0b010, 0b110, 0b010, 0b010, 0b111], // 1
    [0b111, 0b001, 0b111, 0b100, 0b111], // 2
    [0b111, 0b001, 0b011, 0b001, 0b111], // 3
    [0b101, 0b101, 0b111, 0b001, 0b001], // 4
    [0b111, 0b100, 0b111, 0b001, 0b111], // 5
    [0b111, 0b100, 0b111, 0b101, 0b111], // 6
    [0b111, 0b001, 0b001, 0b001, 0b001], // 7
    [0b111, 0b101, 0b111, 0b101, 0b111], // 8
    [0b111, 0b101, 0b111, 0b001, 0b111], // 9
];

pub fn make_framebuffer() -> Vec<u32> {
    vec![0u32; WINDOW_WIDTH * WINDOW_HEIGHT]
}

fn set_pixel(fb: &mut Vec<u32>, x: i32, y: i32, color: u32) {
    if x >= 0 && y >= 0 && (x as usize) < WINDOW_WIDTH && (y as usize) < WINDOW_HEIGHT {
        fb[y as usize * WINDOW_WIDTH + x as usize] = color;
    }
}

fn fill_rect(fb: &mut Vec<u32>, x: i32, y: i32, w: i32, h: i32, color: u32) {
    for dy in 0..h {
        for dx in 0..w {
            set_pixel(fb, x + dx, y + dy, color);
        }
    }
}

fn draw_circle(fb: &mut Vec<u32>, cx: i32, cy: i32, r: i32, color: u32) {
    for dy in -r..=r {
        for dx in -r..=r {
            if dx * dx + dy * dy <= r * r {
                set_pixel(fb, cx + dx, cy + dy, color);
            }
        }
    }
}

fn draw_line(fb: &mut Vec<u32>, x0: i32, y0: i32, x1: i32, y1: i32, color: u32) {
    let dx = (x1 - x0).abs();
    let dy = (y1 - y0).abs();
    let sx = if x0 < x1 { 1 } else { -1 };
    let sy = if y0 < y1 { 1 } else { -1 };
    let mut err = dx - dy;
    let mut x = x0;
    let mut y = y0;
    loop {
        set_pixel(fb, x, y, color);
        if x == x1 && y == y1 {
            break;
        }
        let e2 = 2 * err;
        if e2 > -dy {
            err -= dy;
            x += sx;
        }
        if e2 < dx {
            err += dx;
            y += sy;
        }
    }
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

fn apply_tint_overlay(fb: &mut Vec<u32>, tint: u32, alpha_pct: u32) {
    for px in fb.iter_mut() {
        *px = blend_pixel(*px, tint, alpha_pct);
    }
}

fn draw_digit(fb: &mut Vec<u32>, digit: usize, x: i32, y: i32, scale: i32, color: u32) {
    if digit > 9 {
        return;
    }
    let glyph = &HUD_DIGIT_GLYPHS[digit];
    for (row, &bits) in glyph.iter().enumerate() {
        for col in 0..3 {
            if bits & (1 << (2 - col)) != 0 {
                fill_rect(
                    fb,
                    x + col * scale,
                    y + row as i32 * scale,
                    scale,
                    scale,
                    color,
                );
            }
        }
    }
}

fn draw_number(fb: &mut Vec<u32>, value: i32, x: i32, y: i32, scale: i32, kern: i32, color: u32) {
    let val = value.max(0);
    let digits_str = format!("{}", val);
    let mut cx = x;
    for ch in digits_str.chars() {
        let d = (ch as u8 - b'0') as usize;
        draw_digit(fb, d, cx, y, scale, color);
        cx += HUD_DIGIT_WIDTH * scale + kern;
    }
}

fn health_band_color(health: i32, max_health: i32) -> u32 {
    let frac = health as f32 / max_health as f32;
    if frac >= HUD_HEALTH_BAND_HIGH {
        HUD_HEALTH_COLOR_HIGH
    } else if frac >= HUD_HEALTH_BAND_LOW {
        HUD_HEALTH_COLOR_MID
    } else {
        HUD_HEALTH_COLOR_LOW
    }
}

pub fn draw_hud(fb: &mut Vec<u32>, player: &Player) {
    let mx = HUD_MARGIN;
    let my = HUD_MARGIN;

    // Health bar background
    fill_rect(fb, mx, my, HUD_BAR_WIDTH, HUD_BAR_HEIGHT, HUD_BAR_BG_COLOR);

    // Health bar foreground
    let frac = (player.health as f32 / PLAYER_MAX_HEALTH as f32).clamp(0.0, 1.0);
    let fg_w = (frac * HUD_BAR_WIDTH as f32).round() as i32;
    let band_color = health_band_color(player.health, PLAYER_MAX_HEALTH);
    if fg_w > 0 {
        fill_rect(fb, mx, my, fg_w, HUD_BAR_HEIGHT, band_color);
    }

    // Health digits
    let digits_x = mx + HUD_BAR_WIDTH + HUD_PANE_GAP_PX;
    let digits_y = my;
    let health_val = player.health.max(0);
    draw_number(
        fb,
        health_val,
        digits_x,
        digits_y,
        HUD_DIGIT_PIXEL_SIZE,
        HUD_DIGIT_KERN,
        band_color,
    );

    // Ammo pane below health pane
    let ammo_y = my + HUD_BAR_HEIGHT + HUD_PANE_GAP_PX;

    // Ammo icon (small filled square)
    fill_rect(fb, mx, ammo_y, HUD_AMMO_ICON_PX, HUD_AMMO_ICON_PX, HUD_AMMO_COLOR);

    // Ammo digits
    let ammo_digits_x = mx + HUD_AMMO_ICON_PX + HUD_PANE_GAP_PX;
    let ammo_digits_y = ammo_y + (HUD_AMMO_ICON_PX - HUD_DIGIT_HEIGHT * HUD_DIGIT_PIXEL_SIZE) / 2;
    draw_number(
        fb,
        player.ammo,
        ammo_digits_x,
        ammo_digits_y,
        HUD_DIGIT_PIXEL_SIZE,
        HUD_DIGIT_KERN,
        HUD_AMMO_COLOR,
    );

    // Armor pane below ammo pane
    let armor_y = ammo_y + HUD_AMMO_ICON_PX + HUD_PANE_GAP_PX;
    let armor_color = match player.armor_type {
        ArmorTier::None  => HUD_ARMOR_COLOR_NONE,
        ArmorTier::Green => HUD_ARMOR_COLOR_GREEN,
        ArmorTier::Blue  => HUD_ARMOR_COLOR_BLUE,
    };
    fill_rect(fb, mx, armor_y, HUD_ARMOR_ICON_PX, HUD_ARMOR_ICON_PX, armor_color);
    let armor_digits_x = mx + HUD_ARMOR_ICON_PX + HUD_PANE_GAP_PX;
    let armor_digits_y = armor_y + (HUD_ARMOR_ICON_PX - HUD_DIGIT_HEIGHT * HUD_DIGIT_PIXEL_SIZE) / 2;
    draw_number(
        fb,
        player.armor as i32,
        armor_digits_x,
        armor_digits_y,
        HUD_DIGIT_PIXEL_SIZE,
        HUD_DIGIT_KERN,
        armor_color,
    );
}

fn draw_cross_icon(fb: &mut Vec<u32>, cx: i32, cy: i32, size: i32, thickness: i32, color: u32) {
    // Horizontal bar
    let h_x = cx - size / 2;
    let h_y = cy - thickness / 2;
    fill_rect(fb, h_x, h_y, size, thickness, color);
    // Vertical bar
    let v_x = cx - thickness / 2;
    let v_y = cy - size / 2;
    fill_rect(fb, v_x, v_y, thickness, size, color);
}

pub fn draw_hud_fps(fb: &mut Vec<u32>, player: &Player) {
    let strip_top = WINDOW_HEIGHT as i32 - RAYCASTER_HUD_STRIP_HEIGHT_PX;
    let scale = RAYCASTER_HUD_DIGIT_PIXEL_SIZE;
    let digit_h = HUD_DIGIT_HEIGHT * scale;
    let text_y = strip_top + (RAYCASTER_HUD_STRIP_HEIGHT_PX - digit_h) / 2;

    // 1. Strip background
    fill_rect(
        fb,
        0,
        strip_top,
        WINDOW_WIDTH as i32,
        RAYCASTER_HUD_STRIP_HEIGHT_PX,
        RAYCASTER_HUD_STRIP_COLOR,
    );

    // 2. Health pane
    let icon_size = RAYCASTER_HUD_HEALTH_ICON_PX;
    let icon_thickness = RAYCASTER_HUD_HEALTH_ICON_THICKNESS_PX;
    let icon_cx = RAYCASTER_HUD_PANE_X_HEALTH + icon_size / 2;
    let icon_cy = strip_top + RAYCASTER_HUD_STRIP_HEIGHT_PX / 2;
    draw_cross_icon(fb, icon_cx, icon_cy, icon_size, icon_thickness, RAYCASTER_HUD_HEALTH_COLOR);

    let health_digits_x = RAYCASTER_HUD_PANE_X_HEALTH + icon_size + HUD_PANE_GAP_PX;
    draw_number(
        fb,
        player.health.max(0),
        health_digits_x,
        text_y,
        scale,
        HUD_DIGIT_KERN,
        RAYCASTER_HUD_HEALTH_COLOR,
    );

    // 3. Ammo pane
    let ammo_icon_size = RAYCASTER_HUD_AMMO_ICON_PX;
    let ammo_icon_x = RAYCASTER_HUD_PANE_X_AMMO;
    let ammo_icon_y = strip_top + (RAYCASTER_HUD_STRIP_HEIGHT_PX - ammo_icon_size) / 2;
    fill_rect(
        fb,
        ammo_icon_x,
        ammo_icon_y,
        ammo_icon_size,
        ammo_icon_size,
        RAYCASTER_HUD_AMMO_COLOR,
    );

    let ammo_digits_x = ammo_icon_x + ammo_icon_size + HUD_PANE_GAP_PX;
    draw_number(
        fb,
        player.ammo,
        ammo_digits_x,
        text_y,
        scale,
        HUD_DIGIT_KERN,
        RAYCASTER_HUD_AMMO_COLOR,
    );

    // 3.5. Armor pane
    let armor_icon_size = RAYCASTER_HUD_ARMOR_ICON_PX;
    let armor_icon_x = RAYCASTER_HUD_PANE_X_ARMOR;
    let armor_icon_y = strip_top + (RAYCASTER_HUD_STRIP_HEIGHT_PX - armor_icon_size) / 2;
    let armor_color = match player.armor_type {
        ArmorTier::None  => RAYCASTER_HUD_ARMOR_COLOR_NONE,
        ArmorTier::Green => RAYCASTER_HUD_ARMOR_COLOR_GREEN,
        ArmorTier::Blue  => RAYCASTER_HUD_ARMOR_COLOR_BLUE,
    };
    fill_rect(fb, armor_icon_x, armor_icon_y, armor_icon_size, armor_icon_size, armor_color);
    let armor_digits_x = armor_icon_x + armor_icon_size + HUD_PANE_GAP_PX;
    draw_number(
        fb,
        player.armor as i32,
        armor_digits_x,
        text_y,
        scale,
        HUD_DIGIT_KERN,
        armor_color,
    );

    // 4. Weapon icon (pistol silhouette: barrel + grip)
    let wx = RAYCASTER_HUD_PANE_X_WEAPON;
    let wy = strip_top + (RAYCASTER_HUD_STRIP_HEIGHT_PX - RAYCASTER_HUD_WEAPON_ICON_H_PX) / 2;
    fill_rect(
        fb,
        wx,
        wy,
        RAYCASTER_HUD_WEAPON_ICON_W_PX,
        RAYCASTER_HUD_WEAPON_ICON_H_PX,
        RAYCASTER_HUD_WEAPON_COLOR,
    );
}

pub fn draw_game_over_border(fb: &mut Vec<u32>, won: bool) {
    let color = if won { 0x00FF80u32 } else { 0xFF4040u32 };
    let b = GAME_OVER_BORDER_PX;
    let w = WINDOW_WIDTH as i32;
    let h = WINDOW_HEIGHT as i32;

    fill_rect(fb, 0, 0, w, b, color);
    fill_rect(fb, 0, h - b, w, b, color);
    fill_rect(fb, 0, 0, b, h, color);
    fill_rect(fb, w - b, 0, b, h, color);
}

pub fn draw(
    fb: &mut Vec<u32>,
    level: &Level,
    player: &Player,
    enemies: &[Enemy],
    fx: &VisualEffects,
    game_over: Option<bool>,
) {
    // 1. Floor + walls
    for ty in 0..level.height {
        for tx in 0..level.width {
            let tile = level.tiles[ty][tx];
            let color = match tile {
                crate::level_data::Tile::Wall => COLOR_WALL,
                crate::level_data::Tile::Floor => COLOR_FLOOR,
            };
            let px = (tx as f32 * TILE_SIZE) as i32;
            let py = (ty as f32 * TILE_SIZE) as i32;
            fill_rect(fb, px, py, TILE_SIZE as i32, TILE_SIZE as i32, color);
        }
    }

    // 2. Exit marker (cyan X)
    let ex = (level.exit.x * TILE_SIZE) as i32;
    let ey = (level.exit.y * TILE_SIZE) as i32;
    let half = EXIT_MARKER_SIZE_PX / 2;
    draw_line(fb, ex - half, ey - half, ex + half, ey + half, COLOR_EXIT);
    draw_line(fb, ex + half, ey - half, ex - half, ey + half, COLOR_EXIT);

    // 2. Corpses
    for eff in &fx.effects {
        if eff.kind == EffectKind::EnemyCorpse {
            let cx = (eff.pos.x * TILE_SIZE) as i32;
            let cy = (eff.pos.y * TILE_SIZE) as i32;
            let r = ENEMY_CORPSE_RADIUS as i32 / 2;
            draw_circle(fb, cx, cy, r, COLOR_CORPSE);
        }
    }

    // 2.5. Active pickups
    for pickup in &level.pickups {
        if !pickup.active {
            continue;
        }
        let px = (pickup.pos.x * TILE_SIZE) as i32;
        let py = (pickup.pos.y * TILE_SIZE) as i32;
        match pickup.kind {
            PickupKind::Health => {
                let s = PICKUP_HEALTH_SIZE_PX;
                fill_rect(fb, px - s / 2, py - s / 2, s, s, PICKUP_HEALTH_OUTER_COLOR);
                let t = PICKUP_HEALTH_INNER_THICKNESS_PX;
                // Horizontal bar of cross
                fill_rect(fb, px - s / 2, py - t / 2, s, t, PICKUP_HEALTH_INNER_COLOR);
                // Vertical bar of cross
                fill_rect(fb, px - t / 2, py - s / 2, t, s, PICKUP_HEALTH_INNER_COLOR);
            }
            PickupKind::Ammo => {
                let s = PICKUP_AMMO_SIZE_PX;
                fill_rect(fb, px - s / 2, py - s / 2, s, s, PICKUP_AMMO_COLOR);
            }
            PickupKind::ArmorGreen => {
                let s = PICKUP_ARMOR_SIZE_PX;
                fill_rect(fb, px - s / 2, py - s / 2, s, s, PICKUP_ARMOR_GREEN_COLOR);
            }
            PickupKind::ArmorBlue => {
                let s = PICKUP_ARMOR_SIZE_PX;
                fill_rect(fb, px - s / 2, py - s / 2, s, s, PICKUP_ARMOR_BLUE_COLOR);
            }
        }
    }

    // 3. Blood splats and wall puffs
    for eff in &fx.effects {
        match eff.kind {
            EffectKind::BloodSplat => {
                let cx = (eff.pos.x * TILE_SIZE) as i32;
                let cy = (eff.pos.y * TILE_SIZE) as i32;
                draw_circle(fb, cx, cy, crate::visual_effects::BLOOD_RADIUS as i32 / 2, COLOR_BLOOD);
            }
            EffectKind::WallPuff => {
                let cx = (eff.pos.x * TILE_SIZE) as i32;
                let cy = (eff.pos.y * TILE_SIZE) as i32;
                draw_circle(fb, cx, cy, crate::visual_effects::PUFF_RADIUS as i32 / 2, COLOR_PUFF);
            }
            _ => {}
        }
    }

    // 4. Tracer lines
    for eff in &fx.effects {
        if eff.kind == EffectKind::Tracer {
            let x0 = (eff.pos.x * TILE_SIZE) as i32;
            let y0 = (eff.pos.y * TILE_SIZE) as i32;
            let x1 = (eff.end_pos.x * TILE_SIZE) as i32;
            let y1 = (eff.end_pos.y * TILE_SIZE) as i32;
            draw_line(fb, x0, y0, x1, y1, COLOR_TRACER);
        }
    }

    // 5. Muzzle flashes
    for eff in &fx.effects {
        if eff.kind == EffectKind::MuzzleFlash {
            let cx = (eff.pos.x * TILE_SIZE) as i32;
            let cy = (eff.pos.y * TILE_SIZE) as i32;
            draw_circle(fb, cx, cy, crate::visual_effects::MUZZLE_FLASH_RADIUS as i32 / 2, COLOR_MUZZLE_FLASH);
        }
    }

    // 6. Live enemies
    for eff in &fx.effects {
        if eff.kind == EffectKind::EnemyDeathFade {
            let cx = (eff.pos.x * TILE_SIZE) as i32;
            let cy = (eff.pos.y * TILE_SIZE) as i32;
            let r = ENEMY_RADIUS_PX / 2;
            draw_circle(fb, cx, cy, r, COLOR_CORPSE);
        }
    }
    for enemy in enemies {
        if !enemy.alive {
            continue;
        }
        let cx = (enemy.pos.x * TILE_SIZE) as i32;
        let cy = (enemy.pos.y * TILE_SIZE) as i32;
        let color = if enemy.pain_flash_remaining > 0.0 {
            COLOR_PAIN_FLASH
        } else {
            COLOR_ENEMY
        };
        draw_circle(fb, cx, cy, ENEMY_RADIUS_PX, color);
    }

    // 7. Player
    let px = (player.pos.x * TILE_SIZE) as i32;
    let py = (player.pos.y * TILE_SIZE) as i32;
    draw_circle(fb, px, py, PLAYER_RADIUS_PX, COLOR_PLAYER);
    let dl = DIRECTION_LINE_LEN_PX;
    let dlx = px + (player.facing.cos() * dl as f32) as i32;
    let dly = py + (player.facing.sin() * dl as f32) as i32;
    draw_line(fb, px, py, dlx, dly, COLOR_DIRECTION_LINE);

    // 8. Player damage tint overlay
    if player.damage_count > 0.0 {
        let level_u = ((player.damage_count * DAMAGE_TINT_LEVELS as f32) / DAMAGE_TINT_CAP)
            .ceil() as u32;
        let level_u = level_u.min(DAMAGE_TINT_LEVELS);
        if level_u > 0 {
            let alpha_pct = (DAMAGE_TINT_MAX_ALPHA_PCT * level_u) / DAMAGE_TINT_LEVELS;
            apply_tint_overlay(fb, COLOR_DAMAGE_TINT, alpha_pct);
        }
    }

    // 8.5. Pickup tint overlay
    if fx.pickup_tint_count > 0.0 {
        let pickup_level = ((fx.pickup_tint_count * PICKUP_TINT_LEVEL_COUNT as f32)
            / PICKUP_TINT_CAP)
            .ceil() as u32;
        let pickup_level = pickup_level.min(PICKUP_TINT_LEVEL_COUNT);
        if pickup_level > 0 {
            let alpha_pct = (PICKUP_TINT_MAX_ALPHA_PCT * pickup_level) / PICKUP_TINT_LEVEL_COUNT;
            apply_tint_overlay(fb, COLOR_PICKUP_TINT, alpha_pct);
        }
    }

    // 9. HUD
    draw_hud(fb, player);

    // 10. Game-over border
    if let Some(won) = game_over {
        draw_game_over_border(fb, won);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::level_data::{build_default, Vec2};
    use crate::player_state;
    use crate::visual_effects;

    #[test]
    fn test_make_framebuffer() {
        let fb = make_framebuffer();
        assert_eq!(fb.len(), WINDOW_WIDTH * WINDOW_HEIGHT);
    }

    #[test]
    fn test_draw_does_not_panic() {
        let level = build_default();
        let player = player_state::new(Vec2::new(2.5, 2.5), 0);
        let enemies = vec![];
        let fx = visual_effects::new();
        let mut fb = make_framebuffer();
        draw(&mut fb, &level, &player, &enemies, &fx, None);
    }

    #[test]
    fn test_draw_game_over_border_win() {
        let mut fb = make_framebuffer();
        draw_game_over_border(&mut fb, true);
        // Top-left corner pixel should be win color
        assert_eq!(fb[0], 0x00FF80);
    }

    #[test]
    fn test_draw_game_over_border_lose() {
        let mut fb = make_framebuffer();
        draw_game_over_border(&mut fb, false);
        assert_eq!(fb[0], 0xFF4040);
    }

    #[test]
    fn test_draw_hud_does_not_panic() {
        let player = player_state::new(Vec2::new(2.5, 2.5), 0);
        let mut fb = make_framebuffer();
        draw_hud(&mut fb, &player);
    }

    #[test]
    fn test_draw_hud_fps_does_not_panic() {
        let player = player_state::new(Vec2::new(2.5, 2.5), 0);
        let mut fb = make_framebuffer();
        draw_hud_fps(&mut fb, &player);
    }

    #[test]
    fn test_draw_with_game_over_some() {
        let level = build_default();
        let player = player_state::new(Vec2::new(2.5, 2.5), 0);
        let enemies = vec![];
        let fx = visual_effects::new();
        let mut fb = make_framebuffer();
        draw(&mut fb, &level, &player, &enemies, &fx, Some(true));
        // Border pixel should be win color
        assert_eq!(fb[0], 0x00FF80);
    }
}
