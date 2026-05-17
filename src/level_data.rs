pub const TILE_SIZE: f32 = 32.0;
pub const GRID_WIDTH: usize = 20;
pub const GRID_HEIGHT: usize = 15;
pub const EXIT_RADIUS: f32 = 1.0;
pub const PICKUP_RADIUS_TILES: f32 = 1.0;

#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct Vec2 {
    pub x: f32,
    pub y: f32,
}

impl Vec2 {
    pub fn new(x: f32, y: f32) -> Self {
        Vec2 { x, y }
    }

    pub fn length(self) -> f32 {
        (self.x * self.x + self.y * self.y).sqrt()
    }

    pub fn distance_to(self, other: Vec2) -> f32 {
        (self - other).length()
    }

    #[cfg(test)]
    pub fn normalize(self) -> Vec2 {
        let len = self.length();
        if len < 1e-6 {
            Vec2::default()
        } else {
            Vec2::new(self.x / len, self.y / len)
        }
    }
}

impl std::ops::Sub for Vec2 {
    type Output = Vec2;
    fn sub(self, other: Vec2) -> Vec2 {
        Vec2::new(self.x - other.x, self.y - other.y)
    }
}

impl std::ops::Add for Vec2 {
    type Output = Vec2;
    fn add(self, other: Vec2) -> Vec2 {
        Vec2::new(self.x + other.x, self.y + other.y)
    }
}

impl std::ops::Mul<f32> for Vec2 {
    type Output = Vec2;
    fn mul(self, s: f32) -> Vec2 {
        Vec2::new(self.x * s, self.y * s)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Tile {
    Floor,
    Wall,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PickupKind {
    Health,
    Ammo,
    ArmorGreen,
    ArmorBlue,
}

#[derive(Clone, Copy, Debug)]
pub struct Pickup {
    pub kind: PickupKind,
    pub pos: Vec2,
    pub active: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Archetype {
    BasicTrooper,
    ShotgunTrooper,
}

#[derive(Clone, Copy, Debug)]
pub struct EnemySpawn {
    pub pos: Vec2,
    pub archetype: Archetype,
}

pub struct Level {
    pub width: usize,
    pub height: usize,
    pub tiles: Vec<Vec<Tile>>,
    pub player_spawn: Vec2,
    pub enemy_spawns: Vec<EnemySpawn>,
    pub exit: Vec2,
    pub pickups: Vec<Pickup>,
}

pub fn build_default() -> Level {
    let mut tiles = vec![vec![Tile::Floor; GRID_WIDTH]; GRID_HEIGHT];

    // Border walls
    for x in 0..GRID_WIDTH {
        tiles[0][x] = Tile::Wall;
        tiles[GRID_HEIGHT - 1][x] = Tile::Wall;
    }
    for y in 0..GRID_HEIGHT {
        tiles[y][0] = Tile::Wall;
        tiles[y][GRID_WIDTH - 1] = Tile::Wall;
    }

    // Vertical central divider: x=10, y=3..7 (inclusive)
    for y in 3..=7 {
        tiles[y][10] = Tile::Wall;
    }

    // Mid-left horizontal: y=7, x=4..8 (half-open 4..9 means x=4,5,6,7,8)
    for x in 4..9 {
        tiles[7][x] = Tile::Wall;
    }

    // SE pocket cover: y=10, x=13..14 (half-open: x=13, 14)
    tiles[10][13] = Tile::Wall;
    tiles[10][14] = Tile::Wall;

    Level {
        width: GRID_WIDTH,
        height: GRID_HEIGHT,
        tiles,
        player_spawn: Vec2::new(2.5, 2.5),
        enemy_spawns: vec![
            EnemySpawn { pos: Vec2::new(17.5, 12.5), archetype: Archetype::BasicTrooper },
            EnemySpawn { pos: Vec2::new(4.5, 11.5),  archetype: Archetype::BasicTrooper },
        ],
        exit: Vec2::new(17.5, 2.5),
        pickups: vec![
            Pickup { kind: PickupKind::Health,     pos: Vec2::new(5.5,  12.5), active: true },
            Pickup { kind: PickupKind::Health,     pos: Vec2::new(12.5,  4.5), active: true },
            Pickup { kind: PickupKind::Ammo,       pos: Vec2::new(15.5,  7.5), active: true },
            Pickup { kind: PickupKind::ArmorGreen, pos: Vec2::new(8.5,  12.5), active: true },
            Pickup { kind: PickupKind::ArmorBlue,  pos: Vec2::new(3.5,   4.5), active: true },
        ],
    }
}

pub fn is_wall(level: &Level, tile_x: i32, tile_y: i32) -> bool {
    if tile_x < 0 || tile_y < 0 {
        return true;
    }
    let tx = tile_x as usize;
    let ty = tile_y as usize;
    if tx >= level.width || ty >= level.height {
        return true;
    }
    level.tiles[ty][tx] == Tile::Wall
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_vec2_distance() {
        let a = Vec2::new(0.0, 0.0);
        let b = Vec2::new(3.0, 4.0);
        assert!((a.distance_to(b) - 5.0).abs() < 1e-5);
    }

    #[test]
    fn test_vec2_normalize_zero() {
        let v = Vec2::new(0.0, 0.0);
        let n = v.normalize();
        assert_eq!(n, Vec2::default());
    }

    #[test]
    fn test_is_wall_border() {
        let level = build_default();
        assert!(is_wall(&level, 0, 0));
        assert!(is_wall(&level, 19, 0));
        assert!(is_wall(&level, -1, 5));
        assert!(is_wall(&level, 5, -1));
        assert!(is_wall(&level, 20, 5));
    }

    #[test]
    fn test_is_wall_interior_floor() {
        let level = build_default();
        assert!(!is_wall(&level, 5, 5));
        assert!(!is_wall(&level, 15, 10));
    }

    #[test]
    fn test_build_default_spawn() {
        let level = build_default();
        assert_eq!(level.player_spawn, Vec2::new(2.5, 2.5));
        assert_eq!(level.exit, Vec2::new(17.5, 2.5));
        assert_eq!(level.enemy_spawns.len(), 2);
    }

    #[test]
    fn test_build_default_enemy_archetypes() {
        let level = build_default();
        assert_eq!(level.enemy_spawns[0].archetype, Archetype::BasicTrooper);
        assert_eq!(level.enemy_spawns[1].archetype, Archetype::BasicTrooper);
        assert_eq!(level.enemy_spawns[0].pos, Vec2::new(17.5, 12.5));
        assert_eq!(level.enemy_spawns[1].pos, Vec2::new(4.5, 11.5));
    }

    #[test]
    fn test_build_default_pickups() {
        let level = build_default();
        assert_eq!(level.pickups.len(), 5);
        assert!(level.pickups[2].kind == PickupKind::Ammo);
        assert!(level.pickups[3].kind == PickupKind::ArmorGreen);
        assert!(level.pickups[4].kind == PickupKind::ArmorBlue);
    }
}
