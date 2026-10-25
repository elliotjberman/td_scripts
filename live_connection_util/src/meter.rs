use serde::Serialize;
use std::sync::atomic::{AtomicU32, AtomicU64, Ordering};

#[derive(Default)]
pub struct AudioLevels {
    pub peaks: [AtomicU32; 2],
    pub frames: AtomicU64,
}

impl AudioLevels {
    /// Called by the audio callback: no locks, allocation, file or terminal I/O.
    pub fn capture(&self, data: &[f32], channels: usize, inputs: [usize; 2]) -> [f32; 2] {
        let mut peaks = [0.0_f32; 2];
        for frame in data.chunks_exact(channels) {
            for i in 0..2 {
                let value = frame[inputs[i]];
                if value.is_finite() {
                    peaks[i] = peaks[i].max(value.abs());
                }
            }
        }
        for (peak, value) in self.peaks.iter().zip(peaks) {
            // Nonnegative f32 values have the same bit ordering as u32 values.
            peak.fetch_max(value.to_bits(), Ordering::Relaxed);
        }
        self.frames
            .fetch_add((data.len() / channels) as u64, Ordering::Release);
        peaks
    }
    pub fn take(&self) -> [f32; 2] {
        std::array::from_fn(|i| f32::from_bits(self.peaks[i].swap(0, Ordering::Relaxed)))
    }
}

pub fn db(peak: f32) -> f32 {
    if peak > 0.000001 {
        (20.0 * peak.log10()).max(-120.0)
    } else {
        -120.0
    }
}

#[derive(Debug, Clone, Copy, Serialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum Status {
    NoSignal,
    Low,
    Good,
    Clip,
    Unmeasured,
}

pub fn classify(db: f32, silence: f32, good: f32) -> Status {
    if db >= -1.0 {
        Status::Clip
    } else if db >= good {
        Status::Good
    } else if db >= silence {
        Status::Low
    } else {
        Status::NoSignal
    }
}

pub struct Meter {
    pub held_db: f32,
    pub max_db: f32,
    hold_until: f64,
}
impl Default for Meter {
    fn default() -> Self {
        Self {
            held_db: -120.0,
            max_db: -120.0,
            hold_until: 0.0,
        }
    }
}
impl Meter {
    pub fn update(&mut self, peak: f32, now: f64, dt: f32) {
        let raw = db(peak);
        self.max_db = self.max_db.max(raw);
        if raw >= self.held_db {
            self.held_db = raw;
            self.hold_until = now + 0.15;
        } else if now >= self.hold_until {
            self.held_db = (self.held_db - 32.0 * dt).max(raw);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn capture_uses_distinct_correct_channels_and_absolute_peaks() {
        let m = AudioLevels::default();
        m.capture(&[0.1, 0.2, -0.8, 0.01, 0.4, 0.3, 0.1, -0.5], 4, [3, 2]);
        assert_eq!(m.take(), [0.5, 0.8]);
        assert_eq!(m.take(), [0.0, 0.0]);
        assert_eq!(m.frames.load(Ordering::Relaxed), 2);
    }
    #[test]
    fn real_silence_low_good_and_clipping_are_distinct() {
        assert_eq!(classify(db(0.0), -60.0, -36.0), Status::NoSignal);
        assert_eq!(classify(db(0.005), -60.0, -36.0), Status::Low);
        assert_eq!(classify(db(0.1), -60.0, -36.0), Status::Good);
        assert_eq!(classify(db(1.0), -60.0, -36.0), Status::Clip);
        let mut m = Meter::default();
        m.update(0.1, 0.0, 0.0);
        m.update(0.0, 0.1, 0.1);
        assert!((m.held_db + 20.0).abs() < 0.01);
        m.update(0.0, 1.0, 0.9);
        assert!(m.held_db < -40.0);
    }
}
