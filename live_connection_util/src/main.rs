mod audio;
mod config;
mod latency;
mod meter;
mod midi;
mod monitor;
mod osc;
mod routing;
mod sequence;
mod ui;

use anyhow::{Context, Result, ensure};
use clap::Parser;
use config::Config;
use cpal::traits::{DeviceTrait, HostTrait};
use meter::{AudioLevels, Meter, Status};
use midi::Transport;
use midir::MidiOutput;
use serde::Serialize;
use std::{
    fs::File,
    io::{BufWriter, IsTerminal, Write},
    net::{SocketAddr, UdpSocket},
    sync::{Arc, atomic::Ordering, mpsc},
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

#[derive(Serialize)]
pub struct VoiceFrame {
    name: &'static str,
    midi_channel: u8,
    input_channel: u16,
    note_on: bool,
    note: u8,
    velocity: u8,
    notes_sent: u64,
    peak: Option<f32>,
    peak_dbfs: Option<f32>,
    held_dbfs: Option<f32>,
    max_dbfs: Option<f32>,
    status: Status,
    latency: latency::Reading,
}
#[derive(Serialize)]
pub struct Frame {
    schema_version: u8,
    mode: &'static str,
    elapsed_seconds: f64,
    unix_ms: u128,
    running: bool,
    paused: bool,
    bpm: f64,
    note: u8,
    velocity: u8,
    skipped_beats: u64,
    loops_completed: u64,
    audio_frames: u64,
    midi_routing: routing::Routing,
    voices: [VoiceFrame; 2],
    monitor: Option<monitor::Reading>,
}

struct Telemetry {
    file: Option<BufWriter<File>>,
    udp: Option<UdpSocket>,
    osc: Option<(UdpSocket, osc::Encoder)>,
}
impl Telemetry {
    fn new(c: &Config) -> Result<Self> {
        let file = c
            .jsonl
            .as_ref()
            .map(|p| File::create(p).map(BufWriter::new))
            .transpose()
            .context("create telemetry file")?;
        let udp = c.udp.map(connect_udp).transpose()?;
        let osc = c
            .osc
            .map(|addr| Ok::<_, anyhow::Error>((connect_udp(addr)?, osc::Encoder::new())))
            .transpose()?;
        Ok(Self { file, udp, osc })
    }
    fn write(&mut self, frame: &Frame) -> Result<()> {
        if self.file.is_some() || self.udp.is_some() {
            let bytes = serde_json::to_vec(frame)?;
            if let Some(f) = &mut self.file {
                f.write_all(&bytes)?;
                f.write_all(b"\n")?;
            }
            if let Some(s) = &self.udp {
                send_datagram(s, &bytes)?;
            }
        }
        if let Some((socket, encoder)) = &mut self.osc {
            send_datagram(socket, encoder.encode(frame))?;
        }
        Ok(())
    }
    fn flush(&mut self) -> Result<()> {
        if let Some(f) = &mut self.file {
            f.flush()?;
        }
        Ok(())
    }
}

fn connect_udp(addr: SocketAddr) -> Result<UdpSocket> {
    let socket = UdpSocket::bind(if addr.is_ipv4() {
        "127.0.0.1:0"
    } else {
        "[::1]:0"
    })?;
    socket.connect(addr)?;
    socket.set_nonblocking(true)?;
    Ok(socket)
}

fn send_datagram(socket: &UdpSocket, bytes: &[u8]) -> Result<()> {
    match socket.send(bytes) {
        Ok(_) => Ok(()),
        Err(e)
            if matches!(
                e.kind(),
                std::io::ErrorKind::WouldBlock | std::io::ErrorKind::ConnectionRefused
            ) =>
        {
            Ok(())
        } // Receiver can stop/start independently; don't queue stale state.
        Err(e) => Err(e.into()),
    }
}

/// Join the MIDI worker on every return path, including UI/telemetry errors.
struct Worker {
    state: Arc<Transport>,
    thread: Option<thread::JoinHandle<Result<()>>>,
}
impl Worker {
    fn finish(&mut self) -> Result<()> {
        self.state.stop.store(true, Ordering::Relaxed);
        if let Some(t) = self.thread.take() {
            t.join()
                .map_err(|_| anyhow::anyhow!("MIDI worker panicked"))??;
        }
        Ok(())
    }
}
impl Drop for Worker {
    fn drop(&mut self) {
        let _ = self.finish();
    }
}

fn list() -> Result<()> {
    let midi = MidiOutput::new("live-connection-util-discovery")?;
    println!("MIDI outputs:");
    for port in midi.ports() {
        println!("  {}", midi.port_name(&port)?);
    }
    println!("Audio input devices (no streams opened):");
    for device in cpal::default_host().input_devices()? {
        let name = audio::name(&device)?;
        match device.default_input_config() {
            Ok(c) => println!(
                "  {name}: {} channels, {} Hz, {:?}",
                c.channels(),
                c.sample_rate(),
                c.sample_format()
            ),
            Err(e) => println!("  {name}: unavailable ({e})"),
        }
    }
    println!("Audio output devices (no streams opened):");
    for device in cpal::default_host().output_devices()? {
        let name = audio::name(&device)?;
        match device.default_output_config() {
            Ok(c) => println!(
                "  {name}: {} channels, {} Hz, {:?}",
                c.channels(),
                c.sample_rate(),
                c.sample_format()
            ),
            Err(e) => println!("  {name}: unavailable ({e})"),
        }
    }
    Ok(())
}

fn run(mut c: Config) -> Result<()> {
    if c.list {
        return list();
    }
    c.validate()?;
    ensure!(
        c.headless || (std::io::stdout().is_terminal() && std::io::stdin().is_terminal()),
        "interactive mode needs a terminal; use --headless --seconds 10 for a bounded test"
    );
    let sequence = sequence::Sequence::load(&c)?;
    c.bpm = Some(sequence.initial_bpm);
    let state = Arc::new(Transport::new(&c));
    let signal = state.clone();
    ctrlc::set_handler(move || signal.stop.store(true, Ordering::Relaxed))?;
    let levels = Arc::new(AudioLevels::default());
    let (errors_tx, errors_rx) = mpsc::channel::<String>();
    let mut telemetry = Telemetry::new(&c)?;
    let (stream, audio_label) = if c.demo || c.midi_only {
        (
            None,
            if c.demo {
                "SIMULATED — no audio devices".into()
            } else {
                "UNMEASURED — audio reader disabled".into()
            },
        )
    } else {
        let (s, label) = audio::start(&c, levels.clone(), state.timing.clone(), errors_tx.clone())?;
        // Verify callbacks before sending a single MIDI message.
        let deadline = Instant::now() + Duration::from_secs(3);
        while levels.frames.load(Ordering::Acquire) == 0 || !s.output_ready() {
            if let Ok(error) = errors_rx.try_recv() {
                anyhow::bail!("audio input: {error}");
            }
            ensure!(
                Instant::now() < deadline,
                "audio streams opened but callbacks did not start; check input permission and device availability"
            );
            if state.stop.load(Ordering::Relaxed) {
                return Ok(());
            }
            thread::sleep(Duration::from_millis(10));
        }
        (Some(s), label)
    };
    let mut terminal = if c.headless {
        None
    } else {
        Some(ui::Terminal::new()?)
    };
    let worker_state = state.clone();
    let worker_config = c.clone();
    let thread = thread::spawn(move || {
        let result = midi::run(worker_config, worker_state.clone(), sequence);
        if let Err(e) = &result {
            let _ = errors_tx.send(e.to_string());
            worker_state.stop.store(true, Ordering::Relaxed);
        }
        result
    });
    let mut worker = Worker {
        state: state.clone(),
        thread: Some(thread),
    };
    let start = Instant::now();
    let mut last = start;
    let mut last_audio = start;
    let mut last_output = start;
    let mut output_frames = 0;
    let mut audio_frames = levels.frames.load(Ordering::Acquire);
    let mut meters = [Meter::default(), Meter::default()];
    let mode = if c.demo {
        "demo"
    } else if c.midi_only {
        "midi_only"
    } else {
        "hardware"
    };
    let mut last_frame;
    let mut midi_start_at = None;
    let mut reported_routing = None;
    loop {
        let now = Instant::now();
        let elapsed = start.elapsed().as_secs_f64();
        let dt = now.duration_since(last).as_secs_f32();
        last = now;
        if let Ok(error) = errors_rx.try_recv() {
            anyhow::bail!("device error: {error}");
        }
        let count = levels.frames.load(Ordering::Acquire);
        if count != audio_frames {
            last_audio = now;
            audio_frames = count;
        }
        ensure!(
            stream.is_none() || now.duration_since(last_audio) < Duration::from_secs(1),
            "audio callbacks stopped; ending MIDI test to avoid presenting stale levels"
        );
        let monitor = stream.as_ref().and_then(audio::Streams::monitor);
        if let Some(reading) = &monitor {
            if reading.output_frames != output_frames {
                output_frames = reading.output_frames;
                last_output = now;
            }
            ensure!(
                now.duration_since(last_output) < Duration::from_secs(1),
                "main output callbacks stopped; ending test"
            );
        }
        let paused = state.paused.load(Ordering::Relaxed);
        let on: [bool; 2] = std::array::from_fn(|i| state.note_on[i].load(Ordering::Relaxed));
        let peaks = if c.demo {
            // Tetra cycles silence / low / good so all meter colors can be inspected.
            [
                if on[0] { 0.22 } else { 0.0 },
                if on[1] {
                    [0.0, 0.004, 0.13][(elapsed / 3.0) as usize % 3]
                } else {
                    0.0
                },
            ]
        } else {
            levels.take()
        };
        for i in 0..2 {
            meters[i].update(peaks[i], elapsed, dt);
        }
        let measured = !c.midi_only;
        let voices = std::array::from_fn(|i| VoiceFrame {
            name: ["Moog", "Tetra"][i],
            midi_channel: (i + 1) as u8,
            input_channel: [c.moog_input, c.tetra_input][i],
            note_on: on[i],
            note: state.pitch[i].load(Ordering::Relaxed),
            velocity: state.velocity[i].load(Ordering::Relaxed),
            notes_sent: state.notes[i].load(Ordering::Relaxed),
            peak: measured.then_some(peaks[i]),
            peak_dbfs: measured.then_some(meter::db(peaks[i])),
            held_dbfs: measured.then_some(meters[i].held_db),
            max_dbfs: measured.then_some(meters[i].max_db),
            status: if measured {
                meter::classify(meters[i].held_db, c.silence_db, c.good_db)
            } else {
                Status::Unmeasured
            },
            latency: state.timing.reading(i),
        });
        let finished =
            state.stop.load(Ordering::Relaxed) || (c.seconds > 0.0 && elapsed >= c.seconds);
        let frame = Frame {
            schema_version: 1,
            mode,
            elapsed_seconds: elapsed,
            unix_ms: SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis(),
            running: !finished,
            paused,
            bpm: f64::from_bits(state.bpm.load(Ordering::Relaxed)),
            note: c.note,
            velocity: c.velocity,
            skipped_beats: state.skipped_beats.load(Ordering::Relaxed),
            loops_completed: state.loops_completed.load(Ordering::Relaxed),
            audio_frames,
            midi_routing: state.routing.lock().unwrap().clone(),
            voices,
            monitor,
        };
        if c.headless && reported_routing.as_ref() != Some(&frame.midi_routing) {
            eprintln!("MIDI Routing: {}", frame.midi_routing.message);
            reported_routing = Some(frame.midi_routing.clone());
        }
        if let Some(t) = &mut terminal {
            t.draw(&frame, &c, &audio_label)?;
        }
        telemetry.write(&frame)?;
        last_frame = frame;
        if finished {
            break;
        }
        // Audio callbacks are already verified. Give the interface's first
        // published healthy frame a one-second lead over MIDI routing, while metering,
        // callback watchdogs, OSC and cancellation all keep running normally.
        let deadline = midi_start_at.get_or_insert_with(|| {
            Instant::now()
                + if c.midi_only {
                    Duration::ZERO
                } else {
                    Duration::from_secs(1)
                }
        });
        if Instant::now() >= *deadline {
            state.start_midi.store(true, Ordering::Release);
        }
        if terminal.is_some() {
            ui::input(&state, Duration::from_millis(33))?;
        } else {
            thread::sleep(Duration::from_millis(33));
        }
    }
    worker.finish()?;
    for voice in &mut last_frame.voices {
        voice.note_on = false;
    }
    last_frame.running = false;
    telemetry.write(&last_frame)?;
    telemetry.flush()?;
    drop(stream);
    drop(terminal);
    if c.headless {
        println!("{}", serde_json::to_string_pretty(&last_frame)?);
    } else {
        println!(
            "Stopped after {:.1}s ({mode}); notes released.",
            last_frame.elapsed_seconds
        );
        for voice in &last_frame.voices {
            let peak = voice
                .max_dbfs
                .map_or_else(|| "unmeasured".into(), |db| format!("peak {db:.1} dBFS"));
            println!(
                "  {}: {} notes, return {}",
                voice.name, voice.notes_sent, peak
            );
        }
        if let Some(path) = &c.jsonl {
            println!("Telemetry: {}", path.display());
        }
    }
    Ok(())
}

fn main() {
    if let Err(e) = run(Config::parse()) {
        eprintln!("live-connection-util: {e:#}");
        std::process::exit(1);
    }
}
