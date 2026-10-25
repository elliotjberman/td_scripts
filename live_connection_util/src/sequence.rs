//! Parse once before opening hardware. Only notes and timing enter the playback plan.
use crate::config::Config;
use anyhow::{Context, Result, bail, ensure};
use midly::{Format, MetaMessage, MidiMessage, Smf, Timing, TrackEventKind};
use std::{fs, time::Duration};

const INVENTION: &[u8] = include_bytes!("../midi/Invention_Berman_separate_staves.mid");

#[derive(Clone, Copy, Debug)]
pub enum Action {
    Note {
        voice: usize,
        key: u8,
        velocity: u8,
        on: bool,
    },
    Tempo(f64),
}

#[derive(Clone, Copy, Debug)]
pub struct Event {
    pub at: Duration,
    pub action: Action,
}

pub struct Sequence {
    pub events: Vec<Event>,
    pub duration: Duration,
    pub initial_bpm: f64,
}

impl Sequence {
    pub fn load(config: &Config) -> Result<Self> {
        if config.quarter_notes {
            let duration = Duration::from_secs_f64(60.0 / config.effective_bpm());
            let mut events = Vec::new();
            for (at, on) in [
                (Duration::ZERO, true),
                (duration.mul_f64(config.gate), false),
            ] {
                for voice in 0..2 {
                    events.push(Event {
                        at,
                        action: Action::Note {
                            voice,
                            key: config.note,
                            velocity: if on { config.velocity } else { 0 },
                            on,
                        },
                    });
                }
            }
            return Ok(Self {
                events,
                duration,
                initial_bpm: config.effective_bpm(),
            });
        }
        if let Some(path) = &config.midi_file {
            Self::parse(
                &fs::read(path).with_context(|| format!("read MIDI file {}", path.display()))?,
                config.bpm,
            )
            .with_context(|| format!("parse MIDI file {}", path.display()))
        } else {
            Self::parse(INVENTION, Some(config.bpm.unwrap_or(65.0)))
        }
    }

    fn parse(bytes: &[u8], override_bpm: Option<f64>) -> Result<Self> {
        let smf = Smf::parse(bytes).context("invalid MIDI file")?;
        ensure!(
            smf.header.format != Format::Sequential,
            "sequential MIDI files are unsupported; use simultaneous staff tracks"
        );
        let Timing::Metrical(ticks_per_beat) = smf.header.timing else {
            bail!("MIDI file must use musical ticks per beat, not SMPTE timing");
        };
        ensure!(
            ticks_per_beat.as_int() > 0,
            "MIDI ticks per beat must be positive"
        );
        let note_tracks: Vec<_> = smf.tracks.iter().enumerate().filter(|(_, track)| track.iter().any(|e|
            matches!(e.kind, TrackEventKind::Midi { message: MidiMessage::NoteOn { vel, .. }, .. } if vel.as_int() > 0)
        )).map(|(i, _)| i).collect();
        ensure!(
            note_tracks.len() == 2,
            "expected exactly two note tracks (upper, lower); found {}",
            note_tracks.len()
        );
        let mut raw = Vec::new();
        let mut end_tick = 0u64;
        for (track_index, track) in smf.tracks.iter().enumerate() {
            let mut tick = 0u64;
            for event in track {
                tick += u64::from(event.delta.as_int());
                match event.kind {
                    TrackEventKind::Meta(MetaMessage::Tempo(us)) if override_bpm.is_none() => {
                        ensure!(us.as_int() > 0, "MIDI tempo must be positive");
                        raw.push((tick, Action::Tempo(60_000_000.0 / f64::from(us.as_int()))));
                    }
                    TrackEventKind::Midi { message, .. } => {
                        let note = match message {
                            MidiMessage::NoteOn { key, vel } => {
                                Some((key.as_int(), vel.as_int(), vel.as_int() > 0))
                            }
                            MidiMessage::NoteOff { key, vel } => {
                                Some((key.as_int(), vel.as_int(), false))
                            }
                            _ => None, // Preserve synth patches: ignore PCs, controllers, clock and SysEx.
                        };
                        if let Some((key, velocity, on)) = note
                            && let Some(staff) = note_tracks.iter().position(|i| *i == track_index)
                        {
                            raw.push((
                                tick,
                                Action::Note {
                                    voice: 1 - staff,
                                    key,
                                    velocity,
                                    on,
                                },
                            ));
                        }
                    }
                    _ => {}
                }
            }
            end_tick = end_tick.max(tick);
        }
        raw.sort_by_key(|(tick, _)| *tick); // Stable: keep note-off/retrigger order at the same tick.
        let mut bpm = override_bpm.unwrap_or(120.0);
        let mut initial_bpm = bpm;
        let mut previous_tick = 0;
        let mut seconds = 0.0;
        let mut events = Vec::with_capacity(raw.len());
        for (tick, action) in raw {
            seconds +=
                (tick - previous_tick) as f64 / f64::from(ticks_per_beat.as_int()) * 60.0 / bpm;
            previous_tick = tick;
            if let Action::Tempo(value) = action {
                bpm = value;
                if tick == 0 {
                    initial_bpm = value;
                }
            }
            events.push(Event {
                at: Duration::from_secs_f64(seconds),
                action,
            });
        }
        seconds +=
            (end_tick - previous_tick) as f64 / f64::from(ticks_per_beat.as_int()) * 60.0 / bpm;
        ensure!(
            seconds > 0.0 && seconds <= 86400.0,
            "MIDI loop must be longer than zero and at most one day"
        );
        Ok(Self {
            events,
            duration: Duration::from_secs_f64(seconds),
            initial_bpm,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use clap::Parser;

    #[test]
    fn default_invention_uses_65_bpm_and_pulse_mode_keeps_160() {
        let score = Sequence::load(&Config::parse_from(["test"])).unwrap();
        assert_eq!(score.initial_bpm, 65.0);
        assert!((score.duration.as_secs_f64() - 88.0 * 60.0 / 65.0).abs() < 1e-6);
        let pulse = Sequence::load(&Config::parse_from(["test", "--quarter-notes"])).unwrap();
        assert_eq!(pulse.initial_bpm, 160.0);
    }
    #[test]
    fn invention_staff_routing_timing_and_override() {
        let s = Sequence::parse(INVENTION, None).unwrap();
        assert_eq!(s.duration, Duration::from_secs(44));
        assert_eq!(s.initial_bpm, 120.0);
        for (voice, count, first_time, first_key) in [(0, 173, 2.25, 65), (1, 251, 0.25, 77)] {
            let notes: Vec<_> = s
                .events
                .iter()
                .filter(
                    |e| matches!(e.action, Action::Note { voice: v, on: true, .. } if v == voice),
                )
                .collect();
            assert_eq!(notes.len(), count);
            assert_eq!(notes[0].at, Duration::from_secs_f64(first_time));
            assert!(
                matches!(notes[0].action, Action::Note { key, velocity: 90, .. } if key == first_key)
            );
            let mut active = [0i32; 128];
            for e in &s.events {
                if let Action::Note {
                    voice: v, key, on, ..
                } = e.action
                    && v == voice
                {
                    active[key as usize] += if on { 1 } else { -1 };
                    assert!(active[key as usize] >= 0);
                }
            }
            assert_eq!(active, [0; 128], "all score notes have releases");
        }
        let faster = Sequence::parse(INVENTION, Some(160.0)).unwrap();
        assert_eq!(faster.duration, Duration::from_secs(33));
        assert_eq!(faster.initial_bpm, 160.0);
    }
}
