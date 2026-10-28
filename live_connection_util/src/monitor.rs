//! One bounded, allocation-free SPSC queue between CoreAudio's input/output callbacks.
use rtrb::{Consumer, Producer, RingBuffer};
use serde::Serialize;
use std::sync::{
    Arc,
    atomic::{AtomicU32, AtomicU64, Ordering},
};

#[derive(Default)]
pub struct Stats {
    pub output_frames: AtomicU64,
    mixed_frames: AtomicU64,
    underruns: AtomicU64,
    dropped_frames: AtomicU64,
    queued_frames: AtomicU64,
    max_peak: AtomicU32,
}

#[derive(Serialize)]
pub struct Reading {
    pub output_frames: u64,
    pub mixed_frames: u64,
    pub underruns: u64,
    pub dropped_frames: u64,
    pub queue_ms: f64,
    pub max_peak_dbfs: f32,
}

impl Stats {
    pub fn reading(&self, sample_rate: u32) -> Reading {
        Reading {
            output_frames: self.output_frames.load(Ordering::Relaxed),
            mixed_frames: self.mixed_frames.load(Ordering::Relaxed),
            underruns: self.underruns.load(Ordering::Relaxed),
            dropped_frames: self.dropped_frames.load(Ordering::Relaxed),
            queue_ms: self.queued_frames.load(Ordering::Relaxed) as f64 * 1000.0
                / f64::from(sample_rate),
            max_peak_dbfs: crate::meter::db(f32::from_bits(self.max_peak.load(Ordering::Relaxed))),
        }
    }
}

pub struct Input {
    queue: Producer<f32>,
    inputs: [usize; 2],
    gain: f32,
    stats: Arc<Stats>,
}

pub struct Output {
    queue: Consumer<f32>,
    target: usize,
    primed: bool,
    stats: Arc<Stats>,
}

pub fn pair(
    sample_rate: u32,
    buffer_ms: f64,
    inputs: [usize; 2],
    gain: f32,
) -> (Input, Output, Arc<Stats>) {
    let target = (f64::from(sample_rate) * buffer_ms / 1000.0).ceil() as usize;
    // Enough space for driver block-size variation, but never an unbounded backlog.
    let capacity = (target * 4).max(sample_rate as usize / 4);
    let (producer, consumer) = RingBuffer::new(capacity);
    let stats = Arc::new(Stats::default());
    (
        Input {
            queue: producer,
            inputs,
            gain,
            stats: stats.clone(),
        },
        Output {
            queue: consumer,
            target,
            primed: false,
            stats: stats.clone(),
        },
        stats,
    )
}

impl Input {
    pub fn capture(&mut self, data: &[f32], channels: usize) {
        let mut dropped = 0;
        for frame in data.chunks_exact(channels) {
            let finite = |s: f32| if s.is_finite() { s } else { 0.0 };
            let mix = ((finite(frame[self.inputs[0]]) + finite(frame[self.inputs[1]])) * self.gain)
                .clamp(-1.0, 1.0);
            if self.queue.push(mix).is_err() {
                dropped += 1;
            }
        }
        self.stats
            .dropped_frames
            .fetch_add(dropped, Ordering::Relaxed);
    }
}

impl Output {
    pub fn render(&mut self, data: &mut [f32], channels: usize) {
        data.fill(0.0); // Synth-track outputs 3–6 always stay silent.
        let frames = data.len() / channels;
        self.stats
            .output_frames
            .fetch_add(frames as u64, Ordering::Relaxed);
        let target = self
            .target
            .max(frames * 2)
            .min(self.queue.buffer().capacity() / 2);
        let available = self.queue.slots();
        if available > target + frames * 2 {
            // After a scheduling stall, catch up to fresh audio instead of increasing delay.
            let discard = available - target;
            for _ in 0..discard {
                let _ = self.queue.pop();
            }
            self.stats
                .dropped_frames
                .fetch_add(discard as u64, Ordering::Relaxed);
        }
        if !self.primed {
            self.primed = self.queue.slots() >= target;
        }
        let mut mixed = 0;
        let mut peak = 0.0f32;
        if self.primed {
            for frame in data.chunks_exact_mut(channels) {
                match self.queue.pop() {
                    Ok(sample) => {
                        frame[0] = sample;
                        frame[1] = sample;
                        peak = peak.max(sample.abs());
                        mixed += 1;
                    }
                    Err(_) => {
                        self.stats.underruns.fetch_add(1, Ordering::Relaxed);
                        self.primed = false;
                        break;
                    }
                }
            }
        }
        self.stats.mixed_frames.fetch_add(mixed, Ordering::Relaxed);
        self.stats
            .queued_frames
            .store(self.queue.slots() as u64, Ordering::Relaxed);
        self.stats
            .max_peak
            .fetch_max(peak.to_bits(), Ordering::Relaxed);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn only_external_inputs_reach_main_stereo_pair() {
        let (mut input, mut output, stats) = pair(1000, 5.0, [7, 6], 0.5);
        let mut data = vec![0.0; 8 * 8];
        for frame in data.as_chunks_mut::<8>().0 {
            frame[0] = 1.0;
            frame[6] = 0.2;
            frame[7] = 0.6;
        }
        input.capture(&data, 8);
        let mut out = [1.0; 4 * 6];
        output.render(&mut out, 6);
        for frame in out.as_chunks::<6>().0 {
            assert_eq!(*frame, [0.4, 0.4, 0.0, 0.0, 0.0, 0.0]);
        }
        assert_eq!(stats.reading(1000).mixed_frames, 4);
    }
    #[test]
    fn missing_input_stays_silent_and_overflow_is_bounded() {
        let (mut input, mut output, stats) = pair(1000, 5.0, [0, 1], 0.5);
        let mut out = [1.0; 8];
        output.render(&mut out, 2);
        assert_eq!(out, [0.0; 8]);
        input.capture(&vec![1.0; 2000], 2);
        output.render(&mut out, 2);
        assert_eq!(out, [1.0; 8]);
        assert!(stats.reading(1000).dropped_frames > 0);
        assert!(stats.reading(1000).queue_ms <= 8.0);
        output.render(&mut out, 2);
        output.render(&mut out, 2);
        assert_eq!(out, [0.0; 8]);
        assert_eq!(stats.reading(1000).underruns, 1);
    }
}
