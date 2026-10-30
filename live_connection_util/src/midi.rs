use crate::{
    config::Config,
    latency::Timing,
    routing::{self, Routing},
    sequence::{Action, Sequence},
};
use anyhow::{Context, Result};
use midir::MidiOutputConnection;
use std::{
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, AtomicU8, AtomicU64, Ordering},
    },
    thread,
    time::{Duration, Instant},
};

pub struct Transport {
    pub timing: Arc<Timing>,
    pub stop: AtomicBool,
    pub start_midi: AtomicBool,
    pub routing: Mutex<Routing>,
    pub paused: AtomicBool,
    pub note_on: [AtomicBool; 2],
    pub pitch: [AtomicU8; 2],
    pub velocity: [AtomicU8; 2],
    pub notes: [AtomicU64; 2],
    pub bpm: AtomicU64,
    pub loops_completed: AtomicU64,
    pub skipped_beats: AtomicU64,
}
impl Transport {
    pub fn new(config: &Config) -> Self {
        Self {
            timing: Arc::new(Timing::new()),
            stop: AtomicBool::new(false),
            start_midi: AtomicBool::new(false),
            routing: Mutex::new(Routing::default()),
            paused: AtomicBool::new(config.paused),
            note_on: std::array::from_fn(|_| AtomicBool::new(false)),
            pitch: std::array::from_fn(|_| AtomicU8::new(config.note)),
            velocity: std::array::from_fn(|_| AtomicU8::new(config.velocity)),
            notes: std::array::from_fn(|_| AtomicU64::new(0)),
            bpm: AtomicU64::new(config.effective_bpm().to_bits()),
            loops_completed: AtomicU64::new(0),
            skipped_beats: AtomicU64::new(0),
        }
    }
}

trait MidiSink {
    fn send(&mut self, bytes: &[u8]) -> Result<()>;
}
impl MidiSink for Option<MidiOutputConnection> {
    fn send(&mut self, bytes: &[u8]) -> Result<()> {
        if let Some(c) = self {
            c.send(bytes).context("MIDI send failed")?;
        }
        Ok(())
    }
}

/// Own every pitch this app starts, including chords and uncertain sends.
struct Notes<S: MidiSink> {
    sink: S,
    active: [[bool; 128]; 2],
}
impl<S: MidiSink> Notes<S> {
    fn on(&mut self, voice: usize, key: u8, velocity: u8) -> Result<()> {
        self.off(voice, key, 0)?; // Retrigger overlapping unisons without leaving a held note.
        self.active[voice][key as usize] = true;
        self.sink.send(&[0x90 + voice as u8, key, velocity])
    }
    fn off(&mut self, voice: usize, key: u8, velocity: u8) -> Result<()> {
        if self.active[voice][key as usize] {
            self.sink.send(&[0x80 + voice as u8, key, velocity])?;
            self.active[voice][key as usize] = false;
        }
        Ok(())
    }
    fn release_all(&mut self) -> Result<()> {
        let mut error = None;
        for voice in 0..2 {
            for key in 0..128 {
                if let Err(e) = self.off(voice, key, 0) {
                    error = Some(e);
                }
            }
        }
        match error {
            Some(e) => Err(e),
            None => Ok(()),
        }
    }
    fn publish_gates(&self, state: &Transport) {
        for (voice, pitches) in self.active.iter().enumerate() {
            state.note_on[voice].store(pitches.iter().any(|on| *on), Ordering::Relaxed);
        }
    }
}
impl<S: MidiSink> Drop for Notes<S> {
    fn drop(&mut self) {
        let _ = self.release_all();
    }
}

pub fn run(config: Config, state: Arc<Transport>, sequence: Sequence) -> Result<()> {
    let mut discovery = routing::Discovery::default();
    let connection = wait_for_route(&state, || {
        if config.demo {
            Ok((None, "SIMULATED — no MIDI sent".into()))
        } else {
            discovery
                .connect(&config.midi_port)
                .map(|(port, label)| (Some(port), label))
        }
    });
    let Some(connection) = connection else {
        return Ok(());
    };
    play(connection, &config, &state, &sequence)
}

fn wait_for_route<T>(
    state: &Transport,
    mut connect: impl FnMut() -> Result<(T, String), Routing>,
) -> Option<T> {
    let mut next_attempt = Instant::now();
    while !state.stop.load(Ordering::Relaxed) {
        if state.start_midi.load(Ordering::Acquire) && Instant::now() >= next_attempt {
            match connect() {
                Ok((connection, label)) => {
                    *state.routing.lock().unwrap() = Routing {
                        status: routing::Status::Ready,
                        message: label,
                    };
                    return Some(connection);
                }
                Err(waiting) => {
                    *state.routing.lock().unwrap() = waiting;
                    next_attempt = Instant::now() + Duration::from_millis(500);
                }
            }
        }
        thread::sleep(Duration::from_millis(10));
    }
    None
}

fn play<S: MidiSink>(
    sink: S,
    config: &Config,
    state: &Transport,
    sequence: &Sequence,
) -> Result<()> {
    // Routing is already marked ready. Let that check show for one second
    // before any bend, patch or note messages; telemetry continues on main.
    let midi_start_at = Instant::now() + Duration::from_secs(1);
    while Instant::now() < midi_start_at {
        if state.stop.load(Ordering::Relaxed) {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(2));
    }
    if state.stop.load(Ordering::Relaxed) {
        return Ok(());
    }
    let mut notes = Notes {
        sink,
        active: [[false; 128]; 2],
    };
    // Neutral pitch bend is the 14-bit center (8192), not the raw minimum (0).
    for voice in 0..2 {
        notes.sink.send(&[0xe0 + voice, 0x00, 0x40])?;
    }
    if !config.keep_programs {
        if let Some(program) = config.moog_program {
            // College Town's source leaves both Moog bank bytes unset.
            notes.sink.send(&[0xc0, program])?;
        }
        if let Some(program) = config.tetra_program {
            notes.sink.send(&[0xb1, 32, config.tetra_bank - 1])?;
            notes.sink.send(&[0xc1, program])?;
        }
    }
    let mut origin = Instant::now() + Duration::from_millis(150);
    let mut index = 0;
    let mut pause_start = None;
    let result = (|| -> Result<()> {
        while !state.stop.load(Ordering::Relaxed) {
            let now = Instant::now();
            if state.paused.load(Ordering::Relaxed) {
                if pause_start.is_none() {
                    pause_start = Some(now);
                    notes.release_all()?;
                    notes.publish_gates(state);
                }
                thread::sleep(Duration::from_millis(2));
                continue;
            }
            if let Some(start) = pause_start.take() {
                origin += now - start;
            }
            if now >= origin + sequence.duration {
                notes.release_all()?;
                notes.publish_gates(state);
                let loops =
                    (now.duration_since(origin).as_nanos() / sequence.duration.as_nanos()) as u64;
                origin += sequence.duration.mul_f64(loops as f64);
                index = 0;
                state.loops_completed.fetch_add(loops, Ordering::Relaxed);
                state
                    .bpm
                    .store(sequence.initial_bpm.to_bits(), Ordering::Relaxed);
            }
            while let Some(event) = sequence.events.get(index) {
                let deadline = origin + event.at;
                if deadline > now {
                    break;
                }
                match event.action {
                    Action::Tempo(bpm) => state.bpm.store(bpm.to_bits(), Ordering::Relaxed),
                    Action::Note {
                        voice,
                        key,
                        velocity,
                        on,
                    } => {
                        // Discard missed attacks after a stall instead of replaying a burst.
                        if on
                            && now.saturating_duration_since(deadline) <= Duration::from_millis(50)
                        {
                            state.timing.note_sent(voice);
                            notes.on(voice, key, velocity)?;
                            state.pitch[voice].store(key, Ordering::Relaxed);
                            state.velocity[voice].store(velocity, Ordering::Relaxed);
                            state.notes[voice].fetch_add(1, Ordering::Relaxed);
                        } else if on {
                            state.skipped_beats.fetch_add(1, Ordering::Relaxed);
                        } else {
                            notes.off(voice, key, velocity)?;
                        }
                    }
                }
                index += 1;
            }
            notes.publish_gates(state);
            let next = origin
                + sequence
                    .events
                    .get(index)
                    .map_or(sequence.duration, |e| e.at);
            thread::sleep(
                next.saturating_duration_since(Instant::now())
                    .min(Duration::from_millis(2)),
            );
        }
        Ok(())
    })();
    let cleanup = notes.release_all();
    notes.publish_gates(state);
    result.and(cleanup)
}

#[cfg(test)]
mod tests {
    use super::*;
    use clap::Parser;
    use std::{cell::RefCell, rc::Rc};
    struct Mock {
        sent: Rc<RefCell<Vec<Vec<u8>>>>,
        fail_second_on: bool,
    }
    impl MidiSink for Mock {
        fn send(&mut self, b: &[u8]) -> Result<()> {
            self.sent.borrow_mut().push(b.to_vec());
            if self.fail_second_on && b[0] == 0x91 {
                anyhow::bail!("disconnected")
            }
            Ok(())
        }
    }
    #[test]
    fn partial_send_failure_still_releases_every_pitch() {
        let sent = Rc::new(RefCell::new(vec![]));
        {
            let mut n = Notes {
                sink: Mock {
                    sent: sent.clone(),
                    fail_second_on: true,
                },
                active: [[false; 128]; 2],
            };
            n.on(0, 48, 90).unwrap();
            n.on(0, 55, 90).unwrap();
            assert!(n.on(1, 77, 90).is_err());
        }
        assert_eq!(
            *sent.borrow(),
            vec![
                vec![0x90, 48, 90],
                vec![0x90, 55, 90],
                vec![0x91, 77, 90],
                vec![0x80, 48, 0],
                vec![0x80, 55, 0],
                vec![0x81, 77, 0]
            ]
        );
    }
    #[test]
    fn missing_route_can_appear_without_restarting_the_worker() {
        let state = Transport::new(&Config::parse_from(["test"]));
        state.start_midi.store(true, Ordering::Release);
        let mut attempts = 0;
        let port = wait_for_route(&state, || {
            attempts += 1;
            if attempts == 1 {
                Err(Routing {
                    status: routing::Status::Waiting,
                    message: "Plug in KeyStep".into(),
                })
            } else {
                assert_eq!(
                    state.routing.lock().unwrap().status,
                    routing::Status::Waiting
                );
                assert!(state.notes.iter().all(|n| n.load(Ordering::Relaxed) == 0));
                Ok((42, "KeyStep".into()))
            }
        });
        assert_eq!(port, Some(42));
        assert_eq!(attempts, 2);
        assert_eq!(state.routing.lock().unwrap().status, routing::Status::Ready);
    }

    #[test]
    fn cancellation_while_missing_does_not_wait_for_another_retry() {
        let state = Transport::new(&Config::parse_from(["test"]));
        state.start_midi.store(true, Ordering::Release);
        let start = Instant::now();
        let port: Option<()> = wait_for_route(&state, || {
            state.stop.store(true, Ordering::Relaxed);
            Err(Routing {
                status: routing::Status::Waiting,
                message: "Missing".into(),
            })
        });
        assert_eq!(port, None);
        assert!(start.elapsed() < Duration::from_millis(250));
    }

    #[test]
    fn route_discovery_waits_for_audio_lead_in() {
        let state = Transport::new(&Config::parse_from(["test"]));
        thread::scope(|scope| {
            scope.spawn(|| {
                thread::sleep(Duration::from_millis(30));
                state.stop.store(true, Ordering::Relaxed);
            });
            let port: Option<()> =
                wait_for_route(&state, || panic!("Discovery ran before audio gate"));
            assert_eq!(port, None);
        });
    }

    #[test]
    fn stopping_during_routing_lead_in_sends_no_midi() {
        let config = Config::parse_from(["test", "--quarter-notes"]);
        let state = Transport::new(&config);
        let sequence = Sequence::load(&config).unwrap();
        let sent = Rc::new(RefCell::new(vec![]));
        thread::scope(|scope| {
            scope.spawn(|| {
                thread::sleep(Duration::from_millis(30));
                state.stop.store(true, Ordering::Relaxed);
            });
            play(
                Mock {
                    sent: sent.clone(),
                    fail_second_on: false,
                },
                &config,
                &state,
                &sequence,
            )
            .unwrap();
        });
        assert!(
            sent.borrow().is_empty(),
            "Cancellation during routing confirmation must send nothing"
        );
    }
}
