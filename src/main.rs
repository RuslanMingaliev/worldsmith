mod autopilot;
mod enemy_logic;
mod frame_recorder;
mod game_loop;
mod input_controller;
mod level_data;
mod level_generator;
mod player_state;
mod presentation;
mod raycaster;
mod renderer;
mod visual_effects;
mod weapon_system;

use autopilot::{BotProgress, BotState};
use minifb::{Window, WindowOptions};
use presentation::{DELTA_TIME_CAP, TARGET_FPS, WINDOW_HEIGHT, WINDOW_WIDTH};

#[derive(Clone, Copy)]
enum RenderMode {
    Topdown,
    Raycaster,
}

fn print_usage() {
    eprintln!(
        "Usage: worldsmith-game [--autopilot <path>] [--record-frames <path>] [--render-mode <topdown|raycaster>]"
    );
}

fn main() {
    let args: Vec<String> = std::env::args().collect();

    let mut autopilot_path: Option<String> = None;
    let mut record_path: Option<String> = None;
    let mut render_mode = RenderMode::Raycaster;

    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--autopilot" => {
                i += 1;
                if i >= args.len() {
                    eprintln!("--autopilot requires a path argument");
                    print_usage();
                    std::process::exit(2);
                }
                autopilot_path = Some(args[i].clone());
            }
            "--record-frames" => {
                i += 1;
                if i >= args.len() {
                    eprintln!("--record-frames requires a path argument");
                    print_usage();
                    std::process::exit(2);
                }
                record_path = Some(args[i].clone());
            }
            "--render-mode" => {
                i += 1;
                if i >= args.len() {
                    eprintln!("--render-mode requires an argument (topdown|raycaster)");
                    print_usage();
                    std::process::exit(2);
                }
                render_mode = match args[i].as_str() {
                    "topdown" => RenderMode::Topdown,
                    "raycaster" => RenderMode::Raycaster,
                    other => {
                        eprintln!("Unknown render mode: {}", other);
                        print_usage();
                        std::process::exit(2);
                    }
                };
            }
            flag => {
                eprintln!("Unknown flag: {}", flag);
                print_usage();
                std::process::exit(2);
            }
        }
        i += 1;
    }

    // Parse scenario if autopilot mode
    let scenario = autopilot_path.as_ref().map(|path| {
        let yaml = std::fs::read_to_string(path).expect("scenario file readable");
        autopilot::parse_scenario(&yaml)
    });

    // Pick level
    let level = match scenario.as_ref().and_then(|s| s.level) {
        Some(kind) => level_generator::build(kind),
        None => level_data::build_default(),
    };

    let mut game = game_loop::new(level);

    // Open window
    let mut window = Window::new(
        "Worldsmith Game",
        WINDOW_WIDTH,
        WINDOW_HEIGHT,
        WindowOptions::default(),
    )
    .expect("window creation failed");

    window.set_target_fps(TARGET_FPS as usize);

    let mut framebuffer = renderer::make_framebuffer();

    // Frame recorder
    let mut recorder = record_path.as_ref().map(|path| {
        frame_recorder::open(path).expect("frame recorder open failed")
    });

    // Bot state (if autopilot mode)
    let mut bot = scenario.as_ref().map(|_| BotState::new());

    let mut last_time = std::time::Instant::now();

    while game.running && window.is_open() {
        // ESC always quits
        if window.is_key_down(minifb::Key::Escape) {
            break;
        }

        // dt
        let dt = if scenario.is_some() {
            autopilot::BOT_FRAME_TIME
        } else {
            let now = std::time::Instant::now();
            let elapsed = now.duration_since(last_time).as_secs_f32();
            last_time = now;
            elapsed.min(DELTA_TIME_CAP)
        };

        // Input
        let input = if let (Some(sc), Some(ref mut b)) = (scenario.as_ref(), bot.as_mut()) {
            let (inp, progress) = autopilot::bot_step(&game, sc, b);
            match progress {
                BotProgress::Running => {}
                BotProgress::AllObjectivesComplete => {
                    game.running = false;
                }
                BotProgress::Failed(msg) => {
                    eprintln!("autopilot failed: {}", msg);
                    game.running = false;
                }
            }
            inp
        } else {
            input_controller::poll(&window)
        };

        game_loop::update(&mut game, &input, dt);

        // Render
        let game_over: Option<bool> = if game.game_over_at.is_some() {
            Some(game.won)
        } else {
            None
        };

        match render_mode {
            RenderMode::Topdown => {
                renderer::draw(
                    &mut framebuffer,
                    &game.level,
                    &game.player,
                    &game.enemies,
                    &game.fx,
                    game_over,
                );
            }
            RenderMode::Raycaster => {
                raycaster::draw(
                    &mut framebuffer,
                    &game.level,
                    &game.player,
                    &game.enemies,
                    &game.fx,
                );
                renderer::draw_hud_fps(&mut framebuffer, &game.player);
                if let Some(won) = game_over {
                    renderer::draw_game_over_border(&mut framebuffer, won);
                }
            }
        }

        window
            .update_with_buffer(&framebuffer, WINDOW_WIDTH, WINDOW_HEIGHT)
            .expect("window update failed");

        // Record frame
        if let Some(ref mut rec) = recorder {
            frame_recorder::write_frame(rec, &framebuffer).expect("frame write failed");
        }
    }

    // Close recorder and print stats
    if let Some(rec) = recorder {
        let frames = rec.frames_written;
        let path = record_path.as_deref().unwrap_or("");
        frame_recorder::close(rec).expect("frame recorder close failed");
        eprintln!("recorded {} frames to {}", frames, path);
    }
}
