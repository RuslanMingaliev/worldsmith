use crate::level_data::{Archetype, EnemySpawn, Level, Pickup, PickupKind, Tile, Vec2, GRID_HEIGHT, GRID_WIDTH};

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DemoLevelKind {
    LocalChaseObstacle,
    KiteMelee,
    RangedStandoff,
    ShotgunStandoff,
    ArmorAbsorption,
}

pub fn build(kind: DemoLevelKind) -> Level {
    match kind {
        DemoLevelKind::LocalChaseObstacle => build_local_chase_obstacle(),
        DemoLevelKind::KiteMelee => build_kite_melee(),
        DemoLevelKind::RangedStandoff => build_ranged_standoff(),
        DemoLevelKind::ShotgunStandoff => build_shotgun_standoff(),
        DemoLevelKind::ArmorAbsorption => build_armor_absorption(),
    }
}

fn build_local_chase_obstacle() -> Level {
    let mut tiles = vec![vec![Tile::Floor; GRID_WIDTH]; GRID_HEIGHT];

    for x in 0..GRID_WIDTH {
        tiles[0][x] = Tile::Wall;
        tiles[GRID_HEIGHT - 1][x] = Tile::Wall;
    }
    for y in 0..GRID_HEIGHT {
        tiles[y][0] = Tile::Wall;
        tiles[y][GRID_WIDTH - 1] = Tile::Wall;
    }

    // Vertical divider: x=10, y=4..=10
    for y in 4..=10 {
        tiles[y][10] = Tile::Wall;
    }

    Level {
        width: GRID_WIDTH,
        height: GRID_HEIGHT,
        tiles,
        player_spawn: Vec2::new(3.5, 7.5),
        enemy_spawns: vec![
            EnemySpawn { pos: Vec2::new(16.5, 7.5), archetype: Archetype::BasicTrooper },
        ],
        exit: Vec2::new(1.5, 1.5),
        pickups: vec![],
    }
}

fn build_kite_melee() -> Level {
    let mut tiles = vec![vec![Tile::Floor; GRID_WIDTH]; GRID_HEIGHT];

    for x in 0..GRID_WIDTH {
        tiles[0][x] = Tile::Wall;
        tiles[GRID_HEIGHT - 1][x] = Tile::Wall;
    }
    for y in 0..GRID_HEIGHT {
        tiles[y][0] = Tile::Wall;
        tiles[y][GRID_WIDTH - 1] = Tile::Wall;
    }

    Level {
        width: GRID_WIDTH,
        height: GRID_HEIGHT,
        tiles,
        player_spawn: Vec2::new(4.5, 7.5),
        enemy_spawns: vec![
            EnemySpawn { pos: Vec2::new(6.0, 7.5), archetype: Archetype::BasicTrooper },
        ],
        exit: Vec2::new(1.5, 1.5),
        pickups: vec![],
    }
}

fn build_ranged_standoff() -> Level {
    let mut tiles = vec![vec![Tile::Floor; GRID_WIDTH]; GRID_HEIGHT];

    for x in 0..GRID_WIDTH {
        tiles[0][x] = Tile::Wall;
        tiles[GRID_HEIGHT - 1][x] = Tile::Wall;
    }
    for y in 0..GRID_HEIGHT {
        tiles[y][0] = Tile::Wall;
        tiles[y][GRID_WIDTH - 1] = Tile::Wall;
    }

    Level {
        width: GRID_WIDTH,
        height: GRID_HEIGHT,
        tiles,
        player_spawn: Vec2::new(4.5, 7.5),
        enemy_spawns: vec![
            EnemySpawn { pos: Vec2::new(12.5, 7.5), archetype: Archetype::BasicTrooper },
        ],
        exit: Vec2::new(1.5, 1.5),
        pickups: vec![],
    }
}

fn build_shotgun_standoff() -> Level {
    let mut tiles = vec![vec![Tile::Floor; GRID_WIDTH]; GRID_HEIGHT];

    for x in 0..GRID_WIDTH {
        tiles[0][x] = Tile::Wall;
        tiles[GRID_HEIGHT - 1][x] = Tile::Wall;
    }
    for y in 0..GRID_HEIGHT {
        tiles[y][0] = Tile::Wall;
        tiles[y][GRID_WIDTH - 1] = Tile::Wall;
    }

    Level {
        width: GRID_WIDTH,
        height: GRID_HEIGHT,
        tiles,
        player_spawn: Vec2::new(4.5, 7.5),
        enemy_spawns: vec![
            EnemySpawn { pos: Vec2::new(8.5, 7.5), archetype: Archetype::ShotgunTrooper },
        ],
        exit: Vec2::new(1.5, 1.5),
        pickups: vec![],
    }
}

fn build_armor_absorption() -> Level {
    let mut tiles = vec![vec![Tile::Floor; GRID_WIDTH]; GRID_HEIGHT];

    for x in 0..GRID_WIDTH {
        tiles[0][x] = Tile::Wall;
        tiles[GRID_HEIGHT - 1][x] = Tile::Wall;
    }
    for y in 0..GRID_HEIGHT {
        tiles[y][0] = Tile::Wall;
        tiles[y][GRID_WIDTH - 1] = Tile::Wall;
    }

    Level {
        width: GRID_WIDTH,
        height: GRID_HEIGHT,
        tiles,
        player_spawn: Vec2::new(4.5, 7.5),
        enemy_spawns: vec![
            EnemySpawn { pos: Vec2::new(12.5, 7.5), archetype: Archetype::BasicTrooper },
        ],
        exit: Vec2::new(1.5, 1.5),
        pickups: vec![
            Pickup { kind: PickupKind::ArmorGreen, pos: Vec2::new(4.5, 7.5), active: true },
        ],
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::level_data::{is_wall, Archetype};

    #[test]
    fn test_build_local_chase_obstacle() {
        let level = build(DemoLevelKind::LocalChaseObstacle);
        assert_eq!(level.enemy_spawns.len(), 1);
        assert_eq!(level.pickups.len(), 0);
        // Check divider wall at x=10, y=7
        assert!(is_wall(&level, 10, 7));
        assert!(!is_wall(&level, 9, 7));
        assert_eq!(level.enemy_spawns[0].archetype, Archetype::BasicTrooper);
    }

    #[test]
    fn test_build_kite_melee() {
        let level = build(DemoLevelKind::KiteMelee);
        assert_eq!(level.enemy_spawns.len(), 1);
        assert_eq!(level.pickups.len(), 0);
        // No interior walls
        assert!(!is_wall(&level, 10, 7));
        assert_eq!(level.enemy_spawns[0].archetype, Archetype::BasicTrooper);
    }

    #[test]
    fn test_build_ranged_standoff() {
        let level = build(DemoLevelKind::RangedStandoff);
        assert_eq!(level.enemy_spawns.len(), 1);
        assert_eq!(level.pickups.len(), 0);
        // Border-only: no interior walls at mid-level
        assert!(!is_wall(&level, 10, 7));
        assert_eq!(level.player_spawn, Vec2::new(4.5, 7.5));
        assert_eq!(level.enemy_spawns[0].pos, Vec2::new(12.5, 7.5));
        assert_eq!(level.enemy_spawns[0].archetype, Archetype::BasicTrooper);
    }

    #[test]
    fn test_build_shotgun_standoff() {
        let level = build(DemoLevelKind::ShotgunStandoff);
        assert_eq!(level.enemy_spawns.len(), 1);
        assert_eq!(level.pickups.len(), 0);
        assert_eq!(level.player_spawn, Vec2::new(4.5, 7.5));
        assert_eq!(level.enemy_spawns[0].pos, Vec2::new(8.5, 7.5));
        assert_eq!(level.enemy_spawns[0].archetype, Archetype::ShotgunTrooper);
    }

    #[test]
    fn test_build_deterministic() {
        let l1 = build(DemoLevelKind::LocalChaseObstacle);
        let l2 = build(DemoLevelKind::LocalChaseObstacle);
        assert_eq!(l1.player_spawn, l2.player_spawn);
        assert_eq!(l1.tiles[7][10], l2.tiles[7][10]);
    }

    #[test]
    fn test_build_armor_absorption() {
        let level = build(DemoLevelKind::ArmorAbsorption);
        assert_eq!(level.player_spawn, Vec2::new(4.5, 7.5));
        assert_eq!(level.enemy_spawns.len(), 1);
        assert_eq!(level.enemy_spawns[0].pos, Vec2::new(12.5, 7.5));
        assert_eq!(level.enemy_spawns[0].archetype, Archetype::BasicTrooper);
        assert_eq!(level.pickups.len(), 1);
        assert_eq!(level.pickups[0].kind, PickupKind::ArmorGreen);
        assert_eq!(level.pickups[0].pos, Vec2::new(4.5, 7.5));
    }
}
