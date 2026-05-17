#[derive(Clone, Copy, Debug, Default)]
pub struct InputState {
    pub forward: f32,
    pub strafe: f32,
    pub turn: f32,
    pub fire: bool,
    pub quit: bool,
}

pub fn poll(window: &minifb::Window) -> InputState {
    use minifb::Key;
    let forward = (if window.is_key_down(Key::W) { 1.0 } else { 0.0 })
        + (if window.is_key_down(Key::S) { -1.0 } else { 0.0 });
    let strafe = (if window.is_key_down(Key::D) { 1.0 } else { 0.0 })
        + (if window.is_key_down(Key::A) { -1.0 } else { 0.0 });
    let turn = (if window.is_key_down(Key::Right) { 1.0 } else { 0.0 })
        + (if window.is_key_down(Key::Left) { -1.0 } else { 0.0 });
    InputState {
        forward,
        strafe,
        turn,
        fire: window.is_key_down(Key::Space),
        quit: window.is_key_down(Key::Escape),
    }
}
