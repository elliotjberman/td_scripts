//! Startup MIDI discovery runs on the worker, never on audio or telemetry callbacks.
use crate::config;
use anyhow::Result;
use midir::{MidiOutput, MidiOutputConnection};
use serde::Serialize;

#[derive(Clone, Copy, Debug, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
#[repr(u8)]
pub enum Status {
    Pending = 0,
    Waiting = 1,
    Ready = 2,
    Error = 3,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct Routing {
    pub status: Status,
    pub message: String,
}
impl Default for Routing {
    fn default() -> Self {
        Self {
            status: Status::Pending,
            message: "Waiting for audio interface lead-in".into(),
        }
    }
}

#[derive(Default)]
pub struct Discovery {
    output: Option<MidiOutput>,
}

impl Discovery {
    /// Keep a client alive while waiting, and service CoreMIDI's notification run
    /// loop on its creating thread. Without it, macOS retains a stale endpoint list.
    /// Never pick an arbitrary output if the requested name is ambiguous.
    pub fn connect(&mut self, query: &str) -> Result<(MidiOutputConnection, String), Routing> {
        let mut attempt = || -> Result<_> {
            if self.output.is_none() {
                self.output = Some(MidiOutput::new("live-connection-util")?);
            }
            #[cfg(target_os = "macos")]
            {
                use core_foundation::runloop::{CFRunLoop, kCFRunLoopDefaultMode};
                // SAFETY: CoreFoundation's immutable default-mode constant is valid.
                CFRunLoop::run_in_mode(
                    unsafe { kCFRunLoopDefaultMode },
                    std::time::Duration::from_millis(1),
                    false,
                );
            }
            let midi = self.output.as_ref().unwrap();
            let ports = midi.ports();
            let names = ports
                .iter()
                .map(|p| midi.port_name(p))
                .collect::<Result<Vec<_>, _>>()?;
            if !names
                .iter()
                .any(|n| n.to_lowercase().contains(&query.to_lowercase()))
            {
                return Ok(None);
            }
            let index = config::select_name(&names, query)?;
            let label = names[index].clone();
            let connection = self
                .output
                .take()
                .unwrap()
                .connect(&ports[index], "live-connection-util-output")
                .map_err(|e| anyhow::anyhow!("connect MIDI: {e}"))?;
            Ok(Some((connection, label)))
        };
        match attempt() {
            Ok(Some(connection)) => Ok(connection),
            Ok(None) => Err(Routing {
                status: Status::Waiting,
                message: format!("Waiting for {query} — plug it in; retrying automatically"),
            }),
            Err(error) => Err(Routing {
                status: Status::Error,
                message: format!("{error:#} — retrying automatically"),
            }),
        }
    }
}
