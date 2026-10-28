use anyhow::{Result, ensure};
use clap::Parser;
use std::{net::SocketAddr, path::PathBuf};

#[derive(Parser, Debug, Clone)]
#[command(version, about = "Looping MIDI connection test: Moog ch1 / Tetra ch2")]
pub struct Config {
    /// List MIDI outputs and audio inputs/outputs without opening streams
    #[arg(long)]
    pub list: bool,
    /// Case-insensitive port name (exact preferred, otherwise unique substring)
    #[arg(long, default_value = "KeyStep")]
    pub midi_port: String,
    #[arg(long, default_value = "Analog Four")]
    pub audio_device: String,
    /// One-based input channel: A4 Input R / Ext 2
    #[arg(long, default_value_t = 8)]
    pub moog_input: u16,
    /// One-based input channel: A4 Input L / Ext 1
    #[arg(long, default_value_t = 7)]
    pub tetra_input: u16,
    /// Disable the synth return mix to this interface's Main L/R (outputs 1/2)
    #[arg(long)]
    pub no_monitor: bool,
    /// Linear gain per synth in the centered main-output mix (0..1)
    #[arg(long, default_value_t = 1.0)]
    pub monitor_gain: f32,
    /// Target monitoring buffer in milliseconds, with at least two output blocks
    #[arg(long, default_value_t = 20.0)]
    pub monitor_buffer_ms: f64,
    /// Override playback tempo; bundled Invention defaults to 65, quarter notes to 160 BPM
    #[arg(long)]
    pub bpm: Option<f64>,
    /// Loop a two-staff MIDI file (first note track = upper/Tetra, second = lower/Moog)
    #[arg(long, conflicts_with = "quarter_notes")]
    pub midi_file: Option<PathBuf>,
    /// Use the original steady quarter-note test instead of the bundled Invention
    #[arg(long)]
    pub quarter_notes: bool,
    /// MIDI number is authoritative; 60 is labeled C3 using your octave convention
    #[arg(long, default_value_t = 60, value_parser = clap::value_parser!(u8).range(0..=127))]
    pub note: u8,
    #[arg(long, default_value_t = 96, value_parser = clap::value_parser!(u8).range(1..=127))]
    pub velocity: u8,
    /// Fraction of each quarter note held (0 < gate < 1)
    #[arg(long, default_value_t = 0.4)]
    pub gate: f64,
    /// Raw MIDI program 0..127; default 24 is the College Town Moog/Sirin patch
    #[arg(long, default_value = "24", value_parser = clap::value_parser!(u8).range(0..=127))]
    pub moog_program: Option<u8>,
    /// Raw MIDI program 0..127; default 77 selects Tetra display program 78
    #[arg(long, default_value = "77", value_parser = clap::value_parser!(u8).range(0..=127))]
    pub tetra_program: Option<u8>,
    /// Tetra display bank 1..4; sent as CC32 value 0..3 before its program
    #[arg(long, default_value_t = 1, value_parser = clap::value_parser!(u8).range(1..=4))]
    pub tetra_bank: u8,
    /// Skip startup bank/program selection, retaining the synths' current patches
    #[arg(long)]
    pub keep_programs: bool,
    /// Auto-stop after this many seconds; 0 runs until Ctrl-C
    #[arg(long, default_value_t = 0.0)]
    pub seconds: f64,
    /// Read inputs without starting MIDI until Space is pressed
    #[arg(long)]
    pub paused: bool,
    /// Simulated meters and notes. Opens no MIDI/audio devices
    #[arg(long, conflicts_with = "midi_only")]
    pub demo: bool,
    /// Send real MIDI without opening an audio reader; returns show UNMEASURED
    #[arg(long)]
    pub midi_only: bool,
    /// Print a final JSON report instead of drawing an interactive terminal
    #[arg(long)]
    pub headless: bool,
    /// Allow headless operation until SIGINT (used by the interactive vs_set launcher)
    #[arg(long, requires = "headless")]
    pub until_stopped: bool,
    /// Save versioned, 30 Hz JSON Lines telemetry (never raw audio)
    #[arg(long)]
    pub jsonl: Option<PathBuf>,
    /// Send the same JSON frames to a loopback UDP receiver, e.g. 127.0.0.1:9010
    #[arg(long)]
    pub udp: Option<SocketAddr>,
    /// Send native numeric OSC channels to TouchDesigner, e.g. 127.0.0.1:9012
    #[arg(long)]
    pub osc: Option<SocketAddr>,
    /// Below this peak dBFS is red / no signal
    #[arg(long, default_value_t = -60.0, allow_hyphen_values = true)]
    pub silence_db: f32,
    /// Between silence and this peak dBFS is orange / low signal
    #[arg(long, default_value_t = -36.0, allow_hyphen_values = true)]
    pub good_db: f32,
    /// Minimum new attack for latency, also requiring a 6 dB rise over the previous buffer
    #[arg(long, default_value_t = -48.0, allow_hyphen_values = true)]
    pub latency_threshold_db: f32,
}

impl Config {
    pub fn effective_bpm(&self) -> f64 {
        self.bpm.unwrap_or(160.0)
    }

    pub fn validate(&self) -> Result<()> {
        ensure!(
            self.bpm
                .is_none_or(|bpm| bpm.is_finite() && (20.0..=400.0).contains(&bpm)),
            "BPM must be 20..400"
        );
        ensure!(
            self.gate.is_finite() && self.gate > 0.0 && self.gate < 1.0,
            "gate must be between 0 and 1 (exclusive)"
        );
        ensure!(
            self.seconds.is_finite() && self.seconds >= 0.0 && self.seconds <= 86400.0,
            "seconds must be 0..86400"
        );
        ensure!(
            self.moog_input > 0 && self.tetra_input > 0 && self.moog_input != self.tetra_input,
            "Moog and Tetra need distinct one-based input channels"
        );
        ensure!(
            self.monitor_gain.is_finite() && (0.0..=1.0).contains(&self.monitor_gain),
            "monitor gain must be 0..1"
        );
        ensure!(
            self.monitor_buffer_ms.is_finite() && (5.0..=100.0).contains(&self.monitor_buffer_ms),
            "monitor buffer must be 5..100 ms"
        );
        ensure!(
            self.silence_db.is_finite()
                && self.good_db.is_finite()
                && self.silence_db >= -120.0
                && self.silence_db < self.good_db
                && self.good_db < -1.0,
            "thresholds require -120 <= silence < good < -1 dBFS"
        );
        ensure!(
            !self.midi_port.trim().is_empty() && !self.audio_device.trim().is_empty(),
            "device names cannot be empty"
        );
        ensure!(
            self.latency_threshold_db.is_finite()
                && (-100.0..0.0).contains(&self.latency_threshold_db),
            "latency threshold must be -100..0 dBFS (exclusive of 0)"
        );
        for addr in [self.udp, self.osc].into_iter().flatten() {
            ensure!(
                addr.ip().is_loopback() && addr.port() != 0,
                "telemetry destination must be a loopback address with nonzero port"
            );
        }
        ensure!(
            self.udp.is_none() || self.udp != self.osc,
            "JSON and OSC must use different destination ports"
        );
        ensure!(
            !self.headless || self.seconds > 0.0 || self.until_stopped,
            "--headless requires --seconds or explicit --until-stopped"
        );
        ensure!(
            !self.headless || !self.paused,
            "--paused requires an interactive terminal"
        );
        Ok(())
    }
}

pub fn select_name(names: &[String], query: &str) -> Result<usize> {
    let query = query.to_lowercase();
    let exact: Vec<_> = names
        .iter()
        .enumerate()
        .filter(|(_, n)| n.to_lowercase() == query)
        .map(|(i, _)| i)
        .collect();
    let matches = if exact.is_empty() {
        names
            .iter()
            .enumerate()
            .filter(|(_, n)| n.to_lowercase().contains(&query))
            .map(|(i, _)| i)
            .collect()
    } else {
        exact
    };
    ensure!(
        matches.len() == 1,
        "device name {query:?} matched {} devices; use --list and specify a unique name. Available: {}",
        matches.len(),
        names.join(", ")
    );
    Ok(matches[0])
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn never_pick_arbitrary_hardware() {
        let n = vec!["KeyStep".into(), "KeyStep 37".into()];
        assert_eq!(select_name(&n, "keystep").unwrap(), 0);
        assert!(select_name(&n, "key").is_err());
        assert!(select_name(&n, "Missing").is_err());
    }
    #[test]
    fn reject_invalid_timing_and_channel_aliases() {
        let mut c = Config::parse_from(["test"]);
        assert!(c.validate().is_ok());
        c.bpm = Some(f64::NAN);
        assert!(c.validate().is_err());
        c.bpm = Some(160.0);
        c.tetra_input = c.moog_input;
        assert!(c.validate().is_err());
    }
}
