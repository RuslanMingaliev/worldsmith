use crate::game_loop::GameState;
use crate::input_controller::InputState;
use crate::level_data::{is_wall, Vec2};
use crate::player_state::PLAYER_MAX_HEALTH;

pub const BOT_FRAME_TIME: f32 = 0.01666667;
pub const BOT_MAX_FRAMES: u32 = 18000;
pub const BOT_REACH_DISTANCE: f32 = 1.0;
pub const BOT_APPROACH_DISTANCE: f32 = 8.0;
pub const BOT_STUCK_FRAMES: u32 = 30;
pub const BOT_REVERSE_STRAFE_FRAMES: u32 = 60;
pub const BOT_FACING_THRESHOLD: f32 = 0.3;
pub const BOT_TURN_THRESHOLD: f32 = 0.05;
pub const BOT_KITE_RANGE: f32 = 2.0;
pub const BOT_FIRE_MAX_RANGE: f32 = 10.0;
pub const BOT_FIRE_LOS_RAY_STEP: f32 = 0.1;
pub const BOT_PATH_REPLAN_FRAMES: u32 = 30;
pub const BOT_HEALTH_PICKUP_THRESHOLD: f32 = 0.5;
pub const BOT_PICKUP_DETOUR_BUDGET: u32 = 4;
pub const BOT_WAYPOINT_REACHED_TILES: f32 = 0.7;
pub const BOT_STUCK_MOVE_EPSILON: f32 = 0.02;
pub const BOT_RNG_SEED: u64 = 0xC0FFEE;

const LCG_A: u64 = 6364136223846793005;
const LCG_C: u64 = 1442695040888963407;

fn lcg_next(state: &mut u64) -> u64 {
    *state = state.wrapping_mul(LCG_A).wrapping_add(LCG_C);
    *state
}

fn lcg_f32(state: &mut u64) -> f32 {
    (lcg_next(state) >> 33) as f32 / (u32::MAX as f32)
}

#[derive(Debug, serde::Deserialize)]
pub struct Scenario {
    #[cfg(test)]
    pub scenario: String,
    #[serde(default)]
    pub level: Option<crate::level_generator::DemoLevelKind>,
    pub objectives: Vec<Objective>,
    #[cfg(test)]
    #[serde(default)]
    pub assertions: Vec<Assertion>,
}

#[derive(Debug)]
pub enum Objective {
    Kill(String),
    Reach(String),
    Approach(String),
    Wait(u32),
}

impl<'de> serde::Deserialize<'de> for Objective {
    fn deserialize<D: serde::Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        struct ObjectiveVisitor;

        impl<'de> serde::de::Visitor<'de> for ObjectiveVisitor {
            type Value = Objective;

            fn expecting(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
                formatter.write_str("a single-key map: kill/reach/approach/wait")
            }

            fn visit_map<A: serde::de::MapAccess<'de>>(
                self,
                mut map: A,
            ) -> Result<Objective, A::Error> {
                use serde::de::Error;
                let key: String = map
                    .next_key()?
                    .ok_or_else(|| A::Error::custom("empty objective map"))?;
                match key.as_str() {
                    "kill" => {
                        let v: String = map.next_value()?;
                        Ok(Objective::Kill(v))
                    }
                    "reach" => {
                        let v: String = map.next_value()?;
                        Ok(Objective::Reach(v))
                    }
                    "approach" => {
                        let v: String = map.next_value()?;
                        Ok(Objective::Approach(v))
                    }
                    "wait" => {
                        let v: u32 = map.next_value()?;
                        Ok(Objective::Wait(v))
                    }
                    other => Err(A::Error::unknown_field(
                        other,
                        &["kill", "reach", "approach", "wait"],
                    )),
                }
            }
        }

        deserializer.deserialize_map(ObjectiveVisitor)
    }
}

#[derive(Debug, Clone)]
pub enum BotProgress {
    Running,
    AllObjectivesComplete,
    Failed(String),
}

pub struct BotState {
    frame_count: u32,
    objective_index: usize,
    stuck_counter: u32,
    strafe_dir: f32,
    stuck_strafe_remaining: u32,
    rng: u64,
    path: Vec<(usize, usize)>,
    path_target: Option<(usize, usize)>,
    replan_countdown: u32,
    last_pos: Vec2,
    wait_frames_remaining: u32,
}

impl BotState {
    pub fn new() -> Self {
        BotState {
            frame_count: 0,
            objective_index: 0,
            stuck_counter: 0,
            strafe_dir: 1.0,
            stuck_strafe_remaining: 0,
            rng: BOT_RNG_SEED,
            path: vec![],
            path_target: None,
            replan_countdown: 0,
            last_pos: Vec2::default(),
            wait_frames_remaining: 0,
        }
    }
}

pub fn parse_scenario(yaml: &str) -> Scenario {
    serde_yaml::from_str(yaml).expect("valid scenario YAML")
}

pub fn bot_step(
    game: &GameState,
    scenario: &Scenario,
    bot: &mut BotState,
) -> (InputState, BotProgress) {
    bot.frame_count += 1;

    if bot.frame_count > BOT_MAX_FRAMES {
        return (
            InputState::default(),
            BotProgress::Failed("timeout".to_string()),
        );
    }

    if !game.player.alive {
        return (
            InputState::default(),
            BotProgress::Failed("player_died".to_string()),
        );
    }

    if bot.objective_index >= scenario.objectives.len() {
        return (InputState::default(), BotProgress::AllObjectivesComplete);
    }

    let objective = &scenario.objectives[bot.objective_index];

    // Check current objective completion
    if check_objective_complete(game, objective) {
        bot.objective_index += 1;
        bot.path.clear();
        bot.path_target = None;
        bot.replan_countdown = 0;
        if bot.objective_index >= scenario.objectives.len() {
            return (InputState::default(), BotProgress::AllObjectivesComplete);
        }
    }

    let objective = &scenario.objectives[bot.objective_index];

    // Handle Wait objective
    if let Objective::Wait(frames) = objective {
        if bot.wait_frames_remaining == 0 {
            bot.wait_frames_remaining = *frames;
        }
        if bot.wait_frames_remaining > 0 {
            bot.wait_frames_remaining -= 1;
        }
        if bot.wait_frames_remaining == 0 {
            bot.objective_index += 1;
            bot.path.clear();
        }
        return (InputState::default(), BotProgress::Running);
    }

    let target_pos = resolve_target_pos(game, objective);

    // Detect movement for stuck detection
    let moved = game.player.pos.distance_to(bot.last_pos);
    bot.last_pos = game.player.pos;

    if moved < BOT_STUCK_MOVE_EPSILON {
        bot.stuck_counter += 1;
    } else {
        bot.stuck_counter = 0;
    }

    // Strafe escape when stuck
    if bot.stuck_strafe_remaining > 0 {
        bot.stuck_strafe_remaining -= 1;
        if bot.stuck_strafe_remaining == 0 {
            bot.strafe_dir = if lcg_f32(&mut bot.rng) > 0.5 {
                1.0
            } else {
                -1.0
            };
        }
        let steer = target_pos.map_or(game.player.pos, |p| p);
        let turn = turn_toward(game.player.pos, game.player.facing, steer);
        let input = InputState {
            forward: 1.0,
            strafe: bot.strafe_dir,
            turn,
            fire: false,
            quit: false,
        };
        return (input, BotProgress::Running);
    }

    if bot.stuck_counter >= BOT_STUCK_FRAMES {
        bot.stuck_counter = 0;
        bot.stuck_strafe_remaining = BOT_REVERSE_STRAFE_FRAMES;
    }

    // Kite mode: if targeting an enemy and any alive enemy is in range + LoS
    let kite_mode = match objective {
        Objective::Kill(_) | Objective::Approach(_) => game.enemies.iter().any(|e| {
            e.alive
                && game.player.pos.distance_to(e.pos) < BOT_KITE_RANGE
                && has_line_of_sight(game.player.pos, e.pos, game)
        }),
        _ => false,
    };

    // Fire decision
    let should_fire = matches!(objective, Objective::Kill(_))
        && game.enemies.iter().any(|e| {
            e.alive
                && game.player.pos.distance_to(e.pos) < BOT_FIRE_MAX_RANGE
                && has_line_of_sight(game.player.pos, e.pos, game)
                && angle_diff(
                    angle_to(game.player.pos, e.pos),
                    game.player.facing,
                )
                .abs()
                    < BOT_FACING_THRESHOLD
        });

    let turn_target = target_pos.unwrap_or(game.player.pos);
    let base_turn = turn_toward(game.player.pos, game.player.facing, turn_target);

    if kite_mode {
        let input = InputState {
            forward: -1.0,
            strafe: 0.0,
            turn: base_turn,
            fire: should_fire,
            quit: false,
        };
        return (input, BotProgress::Running);
    }

    // Path-follow mode
    let needs_replan = bot.replan_countdown == 0 || path_stale(game, bot, target_pos);
    if needs_replan {
        let dest_tile = target_pos.map(|tp| pos_to_tile(tp));

        // Pickup-seeking modifiers
        let effective_dest = dest_tile.map(|d| {
            // HP-threshold health routing
            if game.player.health
                < (BOT_HEALTH_PICKUP_THRESHOLD * PLAYER_MAX_HEALTH as f32) as i32
            {
                if let Some(hp) = find_nearest_active_health_pickup(game) {
                    return pos_to_tile(hp);
                }
            }
            // Ammo opportunism
            if game.player.ammo == 0 {
                if let Some(ap) = find_nearest_active_ammo_pickup(game) {
                    let target_dist = target_pos
                        .map_or(f32::INFINITY, |tp| game.player.pos.distance_to(tp));
                    let pickup_dist = game.player.pos.distance_to(ap);
                    if pickup_dist <= target_dist + BOT_PICKUP_DETOUR_BUDGET as f32 {
                        return pos_to_tile(ap);
                    }
                }
            }
            d
        });

        let from_tile = pos_to_tile(game.player.pos);
        if let Some(dst) = effective_dest {
            bot.path = find_path(from_tile, dst, game);
            bot.path_target = Some(dst);
        } else {
            bot.path.clear();
            bot.path_target = None;
        }
        bot.replan_countdown = BOT_PATH_REPLAN_FRAMES;
    } else {
        bot.replan_countdown -= 1;
    }

    // Consume reached waypoints
    while !bot.path.is_empty() {
        let wp = tile_to_pos(bot.path[0]);
        if game.player.pos.distance_to(wp) < BOT_WAYPOINT_REACHED_TILES {
            bot.path.remove(0);
        } else {
            break;
        }
    }

    // When a killable enemy is in range+LoS, face it directly so the fire
    // threshold can be met regardless of which BFS waypoint direction is.
    let fire_target = if matches!(objective, Objective::Kill(_)) {
        game.enemies
            .iter()
            .filter(|e| {
                e.alive
                    && game.player.pos.distance_to(e.pos) < BOT_FIRE_MAX_RANGE
                    && has_line_of_sight(game.player.pos, e.pos, game)
            })
            .min_by(|a, b| {
                game.player
                    .pos
                    .distance_to(a.pos)
                    .partial_cmp(&game.player.pos.distance_to(b.pos))
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
            .map(|e| e.pos)
    } else {
        None
    };

    // Steer toward fire target when available, else next waypoint or direct target
    let steer_target = fire_target.unwrap_or_else(|| {
        if !bot.path.is_empty() {
            tile_to_pos(bot.path[0])
        } else {
            target_pos.unwrap_or(game.player.pos)
        }
    });

    let turn = turn_toward(game.player.pos, game.player.facing, steer_target);
    let forward = if turn.abs() < BOT_FACING_THRESHOLD {
        1.0_f32
    } else {
        0.5
    };

    let input = InputState {
        forward,
        strafe: 0.0,
        turn,
        fire: should_fire,
        quit: false,
    };

    (input, BotProgress::Running)
}

fn turn_toward(player_pos: Vec2, facing: f32, target: Vec2) -> f32 {
    let target_angle = angle_to(player_pos, target);
    let diff = angle_diff(target_angle, facing);
    if diff.abs() < BOT_TURN_THRESHOLD {
        0.0
    } else if diff > 0.0 {
        1.0
    } else {
        -1.0
    }
}

fn check_objective_complete(game: &GameState, objective: &Objective) -> bool {
    match objective {
        Objective::Kill(_) => game.enemies.iter().all(|e| !e.alive),
        Objective::Reach(target) => {
            let tp = resolve_named_target(game, target);
            tp.map_or(true, |p| game.player.pos.distance_to(p) < BOT_REACH_DISTANCE)
        }
        Objective::Approach(target) => {
            if target == "enemy" {
                let nearest = game
                    .enemies
                    .iter()
                    .filter(|e| e.alive)
                    .min_by(|a, b| {
                        game.player
                            .pos
                            .distance_to(a.pos)
                            .partial_cmp(&game.player.pos.distance_to(b.pos))
                            .unwrap_or(std::cmp::Ordering::Equal)
                    });
                nearest.map_or(true, |e| {
                    game.player.pos.distance_to(e.pos) < BOT_APPROACH_DISTANCE
                })
            } else {
                let tp = resolve_named_target(game, target);
                tp.map_or(true, |p| game.player.pos.distance_to(p) < BOT_APPROACH_DISTANCE)
            }
        }
        Objective::Wait(_) => false,
    }
}

fn resolve_target_pos(game: &GameState, objective: &Objective) -> Option<Vec2> {
    match objective {
        Objective::Kill(target) | Objective::Approach(target) => {
            if target == "enemy" {
                nearest_alive_enemy(game)
            } else {
                resolve_named_target(game, target)
            }
        }
        Objective::Reach(target) => resolve_named_target(game, target),
        Objective::Wait(_) => None,
    }
}

fn resolve_named_target(game: &GameState, name: &str) -> Option<Vec2> {
    match name {
        "exit" => Some(game.level.exit),
        "pickup_health" => game
            .level
            .pickups
            .iter()
            .find(|p| p.active && p.kind == crate::level_data::PickupKind::Health)
            .map(|p| p.pos),
        "pickup_ammo" => game
            .level
            .pickups
            .iter()
            .find(|p| p.active && p.kind == crate::level_data::PickupKind::Ammo)
            .map(|p| p.pos),
        "enemy" => nearest_alive_enemy(game),
        _ => None,
    }
}

fn nearest_alive_enemy(game: &GameState) -> Option<Vec2> {
    game.enemies
        .iter()
        .filter(|e| e.alive)
        .min_by(|a, b| {
            game.player
                .pos
                .distance_to(a.pos)
                .partial_cmp(&game.player.pos.distance_to(b.pos))
                .unwrap_or(std::cmp::Ordering::Equal)
        })
        .map(|e| e.pos)
}

fn find_nearest_active_health_pickup(game: &GameState) -> Option<Vec2> {
    game.level
        .pickups
        .iter()
        .filter(|p| p.active && p.kind == crate::level_data::PickupKind::Health)
        .min_by(|a, b| {
            game.player
                .pos
                .distance_to(a.pos)
                .partial_cmp(&game.player.pos.distance_to(b.pos))
                .unwrap_or(std::cmp::Ordering::Equal)
        })
        .map(|p| p.pos)
}

fn find_nearest_active_ammo_pickup(game: &GameState) -> Option<Vec2> {
    game.level
        .pickups
        .iter()
        .filter(|p| p.active && p.kind == crate::level_data::PickupKind::Ammo)
        .min_by(|a, b| {
            game.player
                .pos
                .distance_to(a.pos)
                .partial_cmp(&game.player.pos.distance_to(b.pos))
                .unwrap_or(std::cmp::Ordering::Equal)
        })
        .map(|p| p.pos)
}

fn has_line_of_sight(from: Vec2, to: Vec2, game: &GameState) -> bool {
    let dx = to.x - from.x;
    let dy = to.y - from.y;
    let dist = (dx * dx + dy * dy).sqrt();
    if dist < 1e-6 {
        return true;
    }
    let steps = (dist / BOT_FIRE_LOS_RAY_STEP).ceil() as usize;
    for i in 1..steps {
        let t = i as f32 / steps as f32;
        let sx = from.x + dx * t;
        let sy = from.y + dy * t;
        if is_wall(&game.level, sx.floor() as i32, sy.floor() as i32) {
            return false;
        }
    }
    true
}

fn angle_to(from: Vec2, to: Vec2) -> f32 {
    let dx = to.x - from.x;
    let dy = to.y - from.y;
    dy.atan2(dx)
}

fn angle_diff(a: f32, b: f32) -> f32 {
    let mut d = a - b;
    while d > std::f32::consts::PI {
        d -= std::f32::consts::TAU;
    }
    while d < -std::f32::consts::PI {
        d += std::f32::consts::TAU;
    }
    d
}

fn pos_to_tile(pos: Vec2) -> (usize, usize) {
    (pos.x.floor() as usize, pos.y.floor() as usize)
}

fn tile_to_pos(tile: (usize, usize)) -> Vec2 {
    Vec2::new(tile.0 as f32 + 0.5, tile.1 as f32 + 0.5)
}

fn path_stale(_game: &GameState, bot: &BotState, target_pos: Option<Vec2>) -> bool {
    if let Some(tp) = target_pos {
        let dest_tile = pos_to_tile(tp);
        bot.path_target != Some(dest_tile)
    } else {
        bot.path_target.is_some()
    }
}

fn find_path(
    from: (usize, usize),
    to: (usize, usize),
    game: &GameState,
) -> Vec<(usize, usize)> {
    use std::collections::{HashMap, VecDeque};

    if from == to {
        return vec![];
    }

    let w = game.level.width;
    let h = game.level.height;

    let mut queue: VecDeque<(usize, usize)> = VecDeque::new();
    let mut came_from: HashMap<(usize, usize), (usize, usize)> = HashMap::new();

    queue.push_back(from);
    came_from.insert(from, from);

    // Fixed neighbor order N/E/S/W for determinism
    // Using wrapping arithmetic for boundary cases (usize::MAX means -1)
    while let Some(current) = queue.pop_front() {
        if current == to {
            let mut path = vec![];
            let mut node = to;
            while node != from {
                path.push(node);
                node = *came_from.get(&node).unwrap();
            }
            path.reverse();
            return path;
        }

        let (cx, cy) = current;
        let neighbors: [(i32, i32); 4] = [(0, -1), (1, 0), (0, 1), (-1, 0)];
        for &(dx, dy) in &neighbors {
            let nx = cx as i32 + dx;
            let ny = cy as i32 + dy;
            if nx < 0 || ny < 0 || nx as usize >= w || ny as usize >= h {
                continue;
            }
            let next = (nx as usize, ny as usize);
            if came_from.contains_key(&next) {
                continue;
            }
            if is_wall(&game.level, nx, ny) {
                continue;
            }
            came_from.insert(next, current);
            queue.push_back(next);
        }
    }

    vec![]
}

// ---- cfg(test) types and batch driver ----

#[cfg(test)]
#[derive(Debug)]
pub struct Assertion {
    pub field: String,
    pub op: AssertOp,
    pub value: AssertValue,
}

#[cfg(test)]
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum AssertOp {
    Eq,
    Gt,
    Lt,
    Gte,
    Lte,
}

#[cfg(test)]
#[derive(Debug)]
pub enum AssertValue {
    Bool(bool),
    Number(f32),
}

#[cfg(test)]
pub struct ScenarioResult {
    pub passed: bool,
    pub failures: Vec<String>,
}

#[cfg(test)]
impl<'de> serde::Deserialize<'de> for Assertion {
    fn deserialize<D: serde::Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        struct AssertionVisitor;
        impl<'de> serde::de::Visitor<'de> for AssertionVisitor {
            type Value = Assertion;
            fn expecting(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
                f.write_str("assertion map")
            }
            fn visit_map<A: serde::de::MapAccess<'de>>(
                self,
                mut map: A,
            ) -> Result<Assertion, A::Error> {
                use serde::de::Error;
                let field: String = map
                    .next_key()?
                    .ok_or_else(|| A::Error::custom("empty assertion map"))?;
                let raw: String = map.next_value()?;
                let (op, value) = parse_assert_value(&raw).ok_or_else(|| {
                    A::Error::custom(format!("cannot parse assertion value: {}", raw))
                })?;
                Ok(Assertion { field, op, value })
            }
        }
        deserializer.deserialize_map(AssertionVisitor)
    }
}

#[cfg(test)]
fn parse_assert_value(s: &str) -> Option<(AssertOp, AssertValue)> {
    let s = s.trim();
    if s == "true" {
        return Some((AssertOp::Eq, AssertValue::Bool(true)));
    }
    if s == "false" {
        return Some((AssertOp::Eq, AssertValue::Bool(false)));
    }
    let (op, rest) = if let Some(r) = s.strip_prefix(">= ") {
        (AssertOp::Gte, r)
    } else if let Some(r) = s.strip_prefix("<= ") {
        (AssertOp::Lte, r)
    } else if let Some(r) = s.strip_prefix("> ") {
        (AssertOp::Gt, r)
    } else if let Some(r) = s.strip_prefix("< ") {
        (AssertOp::Lt, r)
    } else if let Some(r) = s.strip_prefix("== ") {
        (AssertOp::Eq, r)
    } else {
        (AssertOp::Eq, s)
    };
    if let Ok(n) = rest.trim().parse::<f32>() {
        Some((op, AssertValue::Number(n)))
    } else if rest.trim() == "true" {
        Some((op, AssertValue::Bool(true)))
    } else if rest.trim() == "false" {
        Some((op, AssertValue::Bool(false)))
    } else {
        None
    }
}

#[cfg(test)]
pub fn run_scenario(scenario: &Scenario) -> ScenarioResult {
    use crate::level_data::build_default;
    use crate::level_generator;

    let level = match scenario.level {
        Some(kind) => level_generator::build(kind),
        None => build_default(),
    };
    let mut state = crate::game_loop::new(level);
    let mut bot = BotState::new();

    loop {
        let (input, progress) = bot_step(&state, scenario, &mut bot);
        crate::game_loop::update(&mut state, &input, BOT_FRAME_TIME);
        if !matches!(progress, BotProgress::Running) {
            break;
        }
    }

    let mut failures = vec![];
    for assertion in &scenario.assertions {
        if let Some(val) = get_field_value(&state, &assertion.field) {
            if !eval_assertion(&val, &assertion.op, &assertion.value) {
                failures.push(format!(
                    "assertion failed: {} {:?} {:?} (got {:?})",
                    assertion.field, assertion.op, assertion.value, val
                ));
            }
        } else {
            failures.push(format!("unknown field: {}", assertion.field));
        }
    }

    ScenarioResult {
        passed: failures.is_empty(),
        failures,
    }
}

#[cfg(test)]
fn get_field_value(state: &GameState, field: &str) -> Option<AssertValue> {
    match field {
        "player.alive" => Some(AssertValue::Bool(state.player.alive)),
        "player.health" => Some(AssertValue::Number(state.player.health as f32)),
        "player.ammo" => Some(AssertValue::Number(state.player.ammo as f32)),
        "player.armor" => Some(AssertValue::Number(state.player.armor as f32)),
        "game.won" => Some(AssertValue::Bool(state.won)),
        "enemy.alive" => {
            let alive = state.enemies.iter().any(|e| e.alive);
            Some(AssertValue::Bool(alive))
        }
        _ => None,
    }
}

#[cfg(test)]
fn eval_assertion(actual: &AssertValue, op: &AssertOp, expected: &AssertValue) -> bool {
    match (actual, expected) {
        (AssertValue::Bool(a), AssertValue::Bool(e)) => match op {
            AssertOp::Eq => a == e,
            _ => false,
        },
        (AssertValue::Number(a), AssertValue::Number(e)) => match op {
            AssertOp::Eq => (a - e).abs() < 0.001,
            AssertOp::Gt => a > e,
            AssertOp::Lt => a < e,
            AssertOp::Gte => a >= e,
            AssertOp::Lte => a <= e,
        },
        _ => false,
    }
}

#[cfg(test)]
fn run_all_scenarios_impl() {
    use std::path::Path;

    let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let tests_dir = manifest_dir
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .join("tests");

    fn collect_yaml(dir: &Path) -> Vec<std::path::PathBuf> {
        let mut paths = vec![];
        if let Ok(entries) = std::fs::read_dir(dir) {
            let mut sorted: Vec<_> = entries.flatten().collect();
            sorted.sort_by_key(|e| e.path());
            for entry in sorted {
                let p = entry.path();
                if p.is_dir() {
                    paths.extend(collect_yaml(&p));
                } else if p.extension().map_or(false, |e| e == "yaml") {
                    paths.push(p);
                }
            }
        }
        paths
    }

    let yaml_files = collect_yaml(&tests_dir);
    let mut all_passed = true;

    for path in &yaml_files {
        let yaml = std::fs::read_to_string(path).expect("readable yaml");
        let scenario: Scenario = parse_scenario(&yaml);
        eprintln!("Running scenario: {}", scenario.scenario);
        let result = run_scenario(&scenario);
        if !result.passed {
            all_passed = false;
            for failure in &result.failures {
                eprintln!("  FAIL: {}", failure);
            }
        }
    }

    assert!(all_passed, "one or more scenarios failed");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_run_all_scenarios() {
        run_all_scenarios_impl();
    }

    #[test]
    fn test_parse_scenario_kill_enemy() {
        let yaml = "
scenario: test
objectives:
  - kill: enemy
assertions: []
";
        let s = parse_scenario(yaml);
        assert_eq!(s.objectives.len(), 1);
        assert!(matches!(s.objectives[0], Objective::Kill(_)));
    }

    #[test]
    fn test_parse_scenario_reach() {
        let yaml = "
scenario: test
objectives:
  - reach: exit
assertions: []
";
        let s = parse_scenario(yaml);
        assert!(matches!(s.objectives[0], Objective::Reach(_)));
    }

    #[test]
    fn test_bot_state_new() {
        let bot = BotState::new();
        assert_eq!(bot.frame_count, 0);
        assert_eq!(bot.objective_index, 0);
    }

    #[test]
    fn test_bot_times_out() {
        use crate::level_data::build_default;
        let level = build_default();
        let game = crate::game_loop::new(level);
        let scenario = parse_scenario(
            "
scenario: timeout_test
objectives:
  - kill: enemy
assertions: []
",
        );
        let mut bot = BotState::new();
        bot.frame_count = BOT_MAX_FRAMES + 1;
        let (_, progress) = bot_step(&game, &scenario, &mut bot);
        assert!(matches!(progress, BotProgress::Failed(_)));
    }

    #[test]
    fn test_has_line_of_sight_open() {
        use crate::level_data::build_default;
        let game = crate::game_loop::new(build_default());
        let a = Vec2::new(2.5, 2.5);
        let b = Vec2::new(5.0, 2.5);
        assert!(has_line_of_sight(a, b, &game));
    }

    #[test]
    fn test_find_path_simple() {
        use crate::level_data::build_default;
        let game = crate::game_loop::new(build_default());
        let from = (2, 2);
        let to = (5, 5);
        let path = find_path(from, to, &game);
        // Should find a path or they may be in walls — just check no panic
        let _ = path;
    }
}
