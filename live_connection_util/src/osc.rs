use crate::{Frame, VoiceFrame, latency::State, meter::Status};
use rosc::{OscBundle, OscMessage, OscPacket, OscType};

const COUNTER_MOD: u64 = 1 << 24; // Exact integer representation in a float CHOP channel.
const GLOBAL: &[&str] = &[
    "version",
    "heartbeat",
    "running",
    "paused",
    "demo",
    "bpm",
    "note",
    "velocity",
    "loops_completed",
    "midi_routing",
];
const VOICE: &[&str] = &[
    "send",
    "notes_sent",
    "level",
    "level_db",
    "meter_db",
    "level_valid",
    "status",
    "latency_ms",
    "latency_last_ms",
    "latency_valid",
    "latency_state",
    "latency_samples",
    "midi_channel",
    "input_channel",
    "note",
    "velocity",
];

/// Allocate OSC addresses/arguments once, then reuse the packet and output buffer.
/// One immediate bundle per snapshot; all serialization stays off audio/MIDI threads.
pub struct Encoder {
    bundle: OscPacket,
    bytes: Vec<u8>,
    heartbeat: u64,
}

impl Encoder {
    pub fn new() -> Self {
        let addresses = GLOBAL.iter().map(|name| format!("/lcu/{name}")).chain(
            ["moog", "tetra"]
                .into_iter()
                .flat_map(|voice| VOICE.iter().map(move |name| format!("/lcu/{voice}/{name}"))),
        );
        let content = addresses
            .map(|addr| {
                OscPacket::Message(OscMessage {
                    addr,
                    args: vec![OscType::Float(0.0)],
                })
            })
            .collect();
        Self {
            bundle: OscPacket::Bundle(OscBundle {
                timetag: (0, 1).into(),
                content,
            }),
            bytes: Vec::with_capacity(2048),
            heartbeat: 0,
        }
    }

    pub fn encode(&mut self, frame: &Frame) -> &[u8] {
        self.heartbeat = (self.heartbeat + 1) % COUNTER_MOD;
        let globals = [
            1.0,
            self.heartbeat as f32,
            flag(frame.running),
            flag(frame.paused),
            flag(frame.mode == "demo"),
            frame.bpm as f32,
            frame.note as f32,
            frame.velocity as f32,
            (frame.loops_completed % COUNTER_MOD) as f32,
            frame.midi_routing.status as u8 as f32,
        ];
        let values = globals
            .into_iter()
            .chain(frame.voices.iter().flat_map(voice_values));
        let OscPacket::Bundle(bundle) = &mut self.bundle else {
            unreachable!()
        };
        for (message, value) in bundle.content.iter_mut().zip(values) {
            let OscPacket::Message(message) = message else {
                unreachable!()
            };
            message.args[0] = OscType::Float(value);
        }
        self.bytes.clear();
        // Vec's encoder Output is infallible; reuse its allocation each frame.
        rosc::encoder::encode_into(&self.bundle, &mut self.bytes)
            .expect("OSC Vec encoding is infallible");
        &self.bytes
    }
}

fn flag(value: bool) -> f32 {
    if value { 1.0 } else { 0.0 }
}

fn voice_values(v: &VoiceFrame) -> [f32; 16] {
    let latency_valid = v.latency.average_ms.is_some()
        && matches!(v.latency.state, State::Detected | State::Waiting);
    [
        flag(v.note_on),
        (v.notes_sent % COUNTER_MOD) as f32,
        v.peak.unwrap_or(0.0),
        v.peak_dbfs.unwrap_or(-120.0),
        v.held_dbfs.unwrap_or(-120.0),
        flag(v.peak.is_some()),
        match v.status {
            Status::Unmeasured => 0.0,
            Status::NoSignal => 1.0,
            Status::Low => 2.0,
            Status::Good => 3.0,
            Status::Clip => 4.0,
        },
        if latency_valid {
            v.latency.average_ms.unwrap_or(-1.0)
        } else {
            -1.0
        },
        if latency_valid {
            v.latency.last_ms.unwrap_or(-1.0)
        } else {
            -1.0
        },
        flag(latency_valid),
        v.latency.state as u8 as f32,
        v.latency.samples as f32,
        v.midi_channel as f32,
        v.input_channel as f32,
        v.note as f32,
        v.velocity as f32,
    ]
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    fn fixture() -> Frame {
        Frame {
            schema_version: 1,
            mode: "hardware",
            elapsed_seconds: 1.0,
            unix_ms: 1,
            running: true,
            paused: false,
            bpm: 160.0,
            note: 60,
            velocity: 96,
            skipped_beats: 0,
            loops_completed: 0,
            audio_frames: 48000,
            midi_routing: crate::routing::Routing {
                status: crate::routing::Status::Ready,
                message: "KeyStep".into(),
            },
            monitor: None,
            voices: std::array::from_fn(|i| VoiceFrame {
                name: ["Moog", "Tetra"][i],
                midi_channel: i as u8 + 1,
                input_channel: [8, 7][i],
                note_on: i == 0,
                note: [65, 77][i],
                velocity: 90,
                notes_sent: 4,
                peak: Some(0.1),
                peak_dbfs: Some(-20.0),
                held_dbfs: Some(-18.0),
                max_dbfs: Some(-15.0),
                status: Status::Good,
                latency: crate::latency::Reading {
                    average_ms: Some(20.0),
                    last_ms: Some(22.0),
                    samples: 4,
                    state: State::Detected,
                },
            }),
        }
    }
    fn decode(bytes: &[u8]) -> HashMap<String, f32> {
        let (rest, packet) = rosc::decoder::decode_udp(bytes).unwrap();
        assert!(rest.is_empty());
        let OscPacket::Bundle(bundle) = packet else {
            panic!("not a bundle")
        };
        assert_eq!(bundle.timetag, (0, 1).into());
        bundle
            .content
            .into_iter()
            .map(|p| {
                let OscPacket::Message(m) = p else {
                    panic!("not a message")
                };
                let [OscType::Float(value)] = m.args.as_slice() else {
                    panic!("not one numeric argument")
                };
                (m.addr, *value)
            })
            .collect()
    }
    #[test]
    fn native_channels_and_unknown_states_survive_packet_reuse() {
        let mut e = Encoder::new();
        let mut f = fixture();
        let first = decode(e.encode(&f));
        assert_eq!(first.len(), GLOBAL.len() + VOICE.len() * 2);
        assert_eq!(first["/lcu/moog/send"], 1.0);
        assert_eq!(first["/lcu/midi_routing"], 2.0);
        assert_eq!(first["/lcu/moog/note"], 65.0);
        assert_eq!(first["/lcu/tetra/note"], 77.0);
        assert_eq!(first["/lcu/tetra/send"], 0.0);
        assert_eq!(first["/lcu/moog/input_channel"], 8.0);
        assert_eq!(first["/lcu/tetra/latency_ms"], 20.0);
        f.running = false;
        f.midi_routing.status = crate::routing::Status::Waiting;
        f.voices[0].note_on = false;
        f.voices[1].peak = None;
        f.voices[1].latency.state = State::NoOnset;
        let second = decode(e.encode(&f));
        assert_eq!(second["/lcu/heartbeat"], 2.0);
        assert_eq!(second["/lcu/running"], 0.0);
        assert_eq!(second["/lcu/midi_routing"], 1.0);
        assert_eq!(second["/lcu/moog/send"], 0.0);
        assert_eq!(second["/lcu/tetra/level_valid"], 0.0);
        assert_eq!(second["/lcu/tetra/latency_valid"], 0.0);
        assert_eq!(second["/lcu/tetra/latency_ms"], -1.0);
        e.heartbeat = COUNTER_MOD - 1;
        assert_eq!(decode(e.encode(&f))["/lcu/heartbeat"], 0.0);
    }
}
