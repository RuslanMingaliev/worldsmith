use crate::presentation::{WINDOW_HEIGHT, WINDOW_WIDTH};
use std::io::{BufWriter, Write};

pub struct FrameRecorder {
    file: BufWriter<std::fs::File>,
    pub frames_written: u64,
}

pub fn open(path: &str) -> std::io::Result<FrameRecorder> {
    let file = std::fs::File::create(path)?;
    let buf = BufWriter::with_capacity(WINDOW_WIDTH * WINDOW_HEIGHT * 4, file);
    Ok(FrameRecorder { file: buf, frames_written: 0 })
}

pub fn write_frame(rec: &mut FrameRecorder, framebuffer: &[u32]) -> std::io::Result<()> {
    assert_eq!(
        framebuffer.len(),
        WINDOW_WIDTH * WINDOW_HEIGHT,
        "framebuffer length mismatch: expected {} got {}",
        WINDOW_WIDTH * WINDOW_HEIGHT,
        framebuffer.len()
    );
    for &px in framebuffer {
        rec.file.write_all(&px.to_ne_bytes())?;
    }
    rec.frames_written += 1;
    Ok(())
}

pub fn close(mut rec: FrameRecorder) -> std::io::Result<()> {
    rec.file.flush()
}
