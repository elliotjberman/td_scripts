//! MIDI-send to audio-callback delivery estimate, including synth attack and buffering.
use serde::Serialize;
use std::{
    sync::atomic::{AtomicU64, Ordering},
    time::Instant,
};

const WINDOW: usize = 8;
const TIME_MASK: u64 = (1 << 24) - 1;

#[derive(Clone, Copy, Debug, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
#[repr(u8)]
pub enum State {
    Unmeasured,
    Waiting,
    Detected,
    NoOnset,
}

#[derive(Clone, Copy, Debug, Serialize)]
pub struct Reading {
    pub average_ms: Option<f32>,
    pub last_ms: Option<f32>,
    pub samples: u8,
    pub state: State,
}

pub struct Timing {
    origin: Instant,
    pub sent_us: [AtomicU64; 2],
    readings: [AtomicU64; 2],
}
impl Timing {
    pub fn new() -> Self {
        Self {
            origin: Instant::now(),
            sent_us: std::array::from_fn(|_| AtomicU64::new(0)),
            readings: std::array::from_fn(|_| AtomicU64::new(0)),
        }
    }
    pub fn now_us(&self) -> u64 {
        self.origin.elapsed().as_micros() as u64 + 1
    }
    pub fn note_sent(&self, voice: usize) {
        self.sent_us[voice].store(self.now_us(), Ordering::Release);
    }
    pub fn reading(&self, voice: usize) -> Reading {
        let bits = self.readings[voice].load(Ordering::Acquire);
        let samples = ((bits >> 48) & 15) as u8;
        Reading {
            average_ms: (samples > 0).then_some((bits & TIME_MASK) as f32 / 1000.0),
            last_ms: (samples > 0).then_some(((bits >> 24) & TIME_MASK) as f32 / 1000.0),
            samples,
            state: match bits >> 52 {
                1 => State::Waiting,
                2 => State::Detected,
                3 => State::NoOnset,
                _ => State::Unmeasured,
            },
        }
    }
    fn publish(&self, voice: usize, rolling: &Rolling, state: State) {
        // One atomic snapshot: two 24-bit microsecond values (up to 16 s),
        // 4-bit sample count, 4-bit state. Actual timeout is <=250 ms.
        let bits = rolling.mean()
            | (rolling.last << 24)
            | ((rolling.len as u64) << 48)
            | ((state as u64) << 52);
        self.readings[voice].store(bits, Ordering::Release);
    }
}

#[derive(Default)]
struct Rolling {
    values: [u64; WINDOW],
    next: usize,
    len: usize,
    last: u64,
}
impl Rolling {
    fn push(&mut self, us: u64) {
        self.values[self.next] = us;
        self.next = (self.next + 1) % WINDOW;
        self.len = (self.len + 1).min(WINDOW);
        self.last = us;
    }
    fn mean(&self) -> u64 {
        if self.len == 0 {
            0
        } else {
            self.values.iter().sum::<u64>() / self.len as u64
        }
    }
}

/// Owned by the audio callback. No locks/allocations and no reliance on UI cadence.
pub struct Detector {
    seen_us: u64,
    previous_peak: f32,
    threshold: f32,
    floor: f32,
    window_us: u64,
    pending: bool,
    rolling: Rolling,
}
impl Detector {
    pub fn new(bpm: f64, threshold_db: f32) -> Self {
        Self {
            seen_us: 0,
            previous_peak: 0.0,
            threshold: 0.0,
            floor: 10.0_f32.powf(threshold_db / 20.0),
            window_us: (60_000_000.0 / bpm * 0.9).min(250_000.0) as u64,
            pending: false,
            rolling: Rolling::default(),
        }
    }
    pub fn process(&mut self, peak: f32, received_us: u64, timing: &Timing, voice: usize) {
        let sent_us = timing.sent_us[voice].load(Ordering::Acquire);
        // A note can be sent while this callback is scanning samples; don't
        // associate that earlier buffer with the new note.
        if sent_us > self.seen_us && sent_us <= received_us {
            self.seen_us = sent_us;
            self.threshold = self.floor.max(self.previous_peak * 2.0);
            self.pending = true;
            timing.publish(voice, &self.rolling, State::Waiting);
        }
        if self.pending {
            let elapsed = received_us.saturating_sub(self.seen_us);
            if elapsed > self.window_us {
                self.pending = false;
                timing.publish(voice, &self.rolling, State::NoOnset);
            } else if peak >= self.threshold {
                self.rolling.push(elapsed);
                self.pending = false;
                timing.publish(voice, &self.rolling, State::Detected);
            }
        }
        self.previous_peak = peak;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn separate_returns_get_separate_delivery_latencies() {
        let t = Timing::new();
        let mut d = [Detector::new(160.0, -48.0), Detector::new(160.0, -48.0)];
        for (i, detector) in d.iter_mut().enumerate() {
            t.sent_us[i].store(100_000, Ordering::Release);
            detector.process(0.0, 110_000, &t, i);
        }
        d[0].process(0.2, 120_000, &t, 0);
        d[1].process(0.1, 135_000, &t, 1);
        assert_eq!(t.reading(0).last_ms, Some(20.0));
        assert_eq!(t.reading(1).last_ms, Some(35.0));
        d[0].process(0.3, 140_000, &t, 0);
        assert_eq!(t.reading(0).samples, 1, "only one attack per note");
    }
    #[test]
    fn sustained_audio_and_silence_do_not_become_fake_onsets() {
        for baseline in [0.0, 0.1] {
            let t = Timing::new();
            let mut d = Detector::new(160.0, -48.0);
            d.process(baseline, 90_000, &t, 0);
            t.sent_us[0].store(100_000, Ordering::Release);
            d.process(baseline, 120_000, &t, 0);
            assert_eq!(t.reading(0).state, State::Waiting);
            d.process(baseline, 360_000, &t, 0);
            assert_eq!(t.reading(0).state, State::NoOnset);
            assert_eq!(t.reading(0).average_ms, None);
        }
    }
    #[test]
    fn ringing_tail_requires_a_new_rise_and_old_buffers_are_excluded() {
        let t = Timing::new();
        let mut d = Detector::new(160.0, -48.0);
        d.process(0.02, 90_000, &t, 0);
        t.sent_us[0].store(100_000, Ordering::Release);
        d.process(0.02, 99_000, &t, 0);
        assert_eq!(t.reading(0).state, State::Unmeasured);
        d.process(0.03, 110_000, &t, 0);
        assert_eq!(t.reading(0).state, State::Waiting);
        d.process(0.05, 130_000, &t, 0);
        assert_eq!(t.reading(0).last_ms, Some(30.0));
    }
    #[test]
    fn rolling_window_evicts_old_values_without_ui_updates() {
        let t = Timing::new();
        let mut d = Detector::new(160.0, -48.0);
        for n in 1..=10 {
            let sent = n * 400_000;
            d.process(0.0, sent - 10_000, &t, 0);
            t.sent_us[0].store(sent, Ordering::Release);
            d.process(0.2, sent + n * 1000, &t, 0);
        }
        let r = t.reading(0);
        assert_eq!(r.samples, 8);
        assert_eq!(r.average_ms, Some(6.5));
        assert_eq!(r.last_ms, Some(10.0));
    }
}
