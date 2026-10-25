use crate::{
    Frame,
    config::Config,
    latency::{Reading, State},
    meter::Status,
    midi::Transport,
};
use anyhow::Result;
use crossterm::{
    cursor::{Hide, MoveTo, Show},
    event::{self, Event, KeyCode, KeyEventKind, KeyModifiers},
    execute, queue,
    style::{Color, Print, ResetColor, SetForegroundColor},
    terminal::{self, Clear, ClearType, EnterAlternateScreen, LeaveAlternateScreen},
};
use std::{
    io::{Stdout, Write, stdout},
    sync::atomic::Ordering,
    time::Duration,
};

pub struct Terminal {
    out: Stdout,
}
impl Terminal {
    pub fn new() -> Result<Self> {
        terminal::enable_raw_mode()?;
        let mut t = Self { out: stdout() };
        execute!(t.out, EnterAlternateScreen, Hide)?;
        Ok(t)
    }
    fn line(&mut self, y: u16, text: &str, color: Color, width: u16) -> Result<()> {
        let clipped: String = text
            .chars()
            .take(width.saturating_sub(1) as usize)
            .collect();
        queue!(
            self.out,
            MoveTo(0, y),
            Clear(ClearType::CurrentLine),
            SetForegroundColor(color),
            Print(clipped),
            ResetColor
        )?;
        Ok(())
    }
    pub fn draw(&mut self, f: &Frame, c: &Config, audio: &str) -> Result<()> {
        let (width, height) = terminal::size()?;
        queue!(self.out, MoveTo(0, 0))?;
        if width < 65 || height < 15 {
            execute!(self.out, Clear(ClearType::All))?;
            self.line(
                0,
                "Resize terminal to at least 65 x 15. Ctrl-C to exit.",
                Color::Yellow,
                width,
            )?;
            self.out.flush()?;
            return Ok(());
        }
        let phase = if f.paused { "PAUSED" } else { "RUNNING" };
        self.line(
            0,
            &format!(
                "LIVE CONNECTION UTIL  |  {phase}  |  {}",
                f.mode.to_uppercase()
            ),
            Color::Cyan,
            width,
        )?;
        self.line(
            1,
            &if c.quarter_notes {
                format!(
                    "{:.0} BPM / quarter notes / MIDI {} ({}) / vel {}",
                    f.bpm,
                    c.note,
                    note_name(c.note),
                    c.velocity
                )
            } else {
                let name = c
                    .midi_file
                    .as_ref()
                    .and_then(|p| p.file_name())
                    .map(|n| n.to_string_lossy())
                    .unwrap_or_else(|| "Invention — Berman".into());
                format!(
                    "{:.0} BPM / {} / LOOP {}",
                    f.bpm,
                    name,
                    f.loops_completed + 1
                )
            },
            Color::White,
            width,
        )?;
        let routing_color = match f.midi_routing.status {
            crate::routing::Status::Ready => Color::Green,
            crate::routing::Status::Pending => Color::DarkGrey,
            crate::routing::Status::Waiting | crate::routing::Status::Error => Color::Red,
        };
        self.line(
            2,
            &format!("MIDI ROUTING  {}", f.midi_routing.message),
            routing_color,
            width,
        )?;
        self.line(3, &format!("AUDIO {audio}"), Color::DarkGrey, width)?;
        let output = f.monitor.as_ref().map_or_else(String::new, |m| {
            format!(
                "OUT   Main L/R / mix {:.0}% each / queue {:.1} ms / underruns {}",
                c.monitor_gain * 100.0,
                m.queue_ms,
                m.underruns
            )
        });
        self.line(4, &output, Color::DarkGrey, width)?;
        let bar_width = (width as usize).saturating_sub(36).clamp(12, 44);
        for (i, v) in f.voices.iter().enumerate() {
            let y = 5 + i as u16 * 3;
            let color = match v.status {
                Status::Good => Color::Green,
                Status::Low => Color::AnsiValue(208),
                Status::NoSignal | Status::Clip => Color::Red,
                Status::Unmeasured => Color::DarkGrey,
            };
            let status = match v.status {
                Status::Good => "GOOD",
                Status::Low => "LOW",
                Status::NoSignal => "NO SIGNAL",
                Status::Clip => "CLIP",
                Status::Unmeasured => "UNMEASURED",
            };
            let pc = if c.keep_programs {
                "current patch".into()
            } else {
                [c.moog_program, c.tetra_program][i].map_or_else(
                    || "current patch".into(),
                    |n| {
                        if i == 1 {
                            format!("bank {} / program {}", c.tetra_bank, u16::from(n) + 1)
                        } else {
                            format!("program {n} (raw)")
                        }
                    },
                )
            };
            self.line(
                y,
                &format!(
                    "{}   ch {} -> input {}   |   NOTE {} {}   |   {}",
                    v.name,
                    v.midi_channel,
                    v.input_channel,
                    v.note,
                    note_name(v.note),
                    pc
                ),
                color,
                width,
            )?;
            let count = v.held_dbfs.map_or(0, |db| {
                (((db + 60.0) / 60.0).clamp(0.0, 1.0) * bar_width as f32).round() as usize
            });
            let bar = format!("[{}{}]", "█".repeat(count), " ".repeat(bar_width - count));
            let level = v.held_dbfs.map_or_else(
                || "   --".into(),
                |db| {
                    if db <= -120.0 {
                        " -inf".into()
                    } else {
                        format!("{db:5.1}")
                    }
                },
            );
            self.line(
                y + 1,
                &format!("      {bar} {level} dB  {status}"),
                color,
                width,
            )?;
            // One solid rectangle is the note lamp, independent of measured return color.
            queue!(
                self.out,
                MoveTo(0, y + 1),
                SetForegroundColor(if v.note_on {
                    Color::Cyan
                } else {
                    Color::DarkGrey
                }),
                Print(if v.note_on {
                    "████"
                } else {
                    "░░░░"
                }),
                ResetColor
            )?;
            self.line(y + 2, &latency_text(v.latency), Color::White, width)?;
        }
        self.line(
            11,
            &format!(
                "{:6.1}s   audio frames {}   skipped notes {}",
                f.elapsed_seconds, f.audio_frames, f.skipped_beats
            ),
            Color::DarkGrey,
            width,
        )?;
        self.line(
            12,
            "Space pause/resume   Ctrl-C to exit",
            Color::White,
            width,
        )?;
        self.line(
            13,
            if c.demo {
                "DEMO: simulated notes and returns; no hardware opened."
            } else {
                ""
            },
            Color::DarkGrey,
            width,
        )?;
        queue!(self.out, MoveTo(0, 14), Clear(ClearType::FromCursorDown))?;
        self.out.flush()?;
        Ok(())
    }
}
impl Drop for Terminal {
    fn drop(&mut self) {
        let _ = execute!(self.out, ResetColor, Show, LeaveAlternateScreen);
        let _ = terminal::disable_raw_mode();
    }
}
pub fn input(state: &Transport, timeout: Duration) -> Result<()> {
    if event::poll(timeout)?
        && let Event::Key(key) = event::read()?
        && key.kind != KeyEventKind::Release
    {
        match key.code {
            KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                state.stop.store(true, Ordering::Relaxed)
            }
            KeyCode::Char(' ') => {
                state.paused.fetch_xor(true, Ordering::Relaxed);
            }
            _ => (),
        }
    }
    Ok(())
}
fn note_name(note: u8) -> String {
    let names = [
        "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
    ];
    format!("{}{}", names[(note % 12) as usize], note as i16 / 12 - 2)
}

fn latency_text(r: Reading) -> String {
    match (r.state, r.average_ms, r.last_ms) {
        (State::Unmeasured, _, _) => "Latency -- (unmeasured)".into(),
        (State::NoOnset, _, _) => "Latency -- (no fresh attack)".into(),
        (State::Waiting, Some(avg), _) => format!("Latency ~{avg:.1} ms"),
        (_, Some(avg), Some(last)) => format!("Latency ~{avg:.1} ms  |  last {last:.1} ms"),
        _ => "Latency --".into(),
    }
}
