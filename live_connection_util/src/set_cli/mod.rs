#[cfg(target_os = "macos")]
mod macos;
mod projects;
mod td;

use anyhow::{Context, Result, bail, ensure};
use clap::{Args, Parser, Subcommand};
use crossterm::{
    event::{self, Event, KeyCode, KeyEventKind, KeyModifiers},
    terminal,
};
use std::{
    fs::{self, File},
    io::{self, IsTerminal, Write},
    os::{fd::AsRawFd, unix::process::CommandExt},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::atomic::{AtomicBool, Ordering},
    thread,
    time::{Duration, Instant},
};

static CANCELLED: AtomicBool = AtomicBool::new(false);
const REPO: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/..");

#[derive(Parser)]
#[command(
    name = "vs_set",
    about = "Open the visuals, Enter for MIDI test, Enter for the Bitwig set"
)]
struct Cli {
    #[command(subcommand)]
    command: Option<Action>,
    #[command(flatten)]
    set: SetArgs,
}

#[derive(Subcommand)]
enum Action {
    /// Open or reuse just the visual master and wait for its readiness heartbeat
    Visuals,
    /// Read TD heartbeats for two seconds; opens no apps or audio/MIDI devices
    TdStatus,
    /// Open just the Bitwig projects in setlist order (the bwset alias)
    Bwset {
        /// Optional setlist, compatible with the former bwset command
        setlist: Option<PathBuf>,
        #[command(flatten)]
        options: SetArgs,
    },
}

#[derive(Args)]
struct SetArgs {
    /// External setlist shared with TouchDesigner
    #[arg(long, default_value = concat!(env!("CARGO_MANIFEST_DIR"), "/../live_bw/setlist.json"))]
    setlist_file: PathBuf,
    /// Search here for exact .bwproject filenames
    #[arg(long)]
    projects_root: Option<PathBuf>,
    /// Seconds between Bitwig project opens, after application startup
    #[arg(long, default_value_t = 5.0)]
    delay: f64,
    /// Resolve everything and print the plan without opening apps or devices
    #[arg(long)]
    dry_run: bool,
}

pub fn cancelled() -> bool {
    CANCELLED.load(Ordering::Relaxed)
}

fn check_cancelled() -> Result<()> {
    ensure!(!cancelled(), "Cancelled; no further stages will start.");
    Ok(())
}

fn delay(seconds: f64) -> Result<()> {
    let until = Instant::now() + Duration::from_secs_f64(seconds);
    while Instant::now() < until {
        check_cancelled()?;
        thread::sleep(
            Duration::from_millis(50).min(until.saturating_duration_since(Instant::now())),
        );
    }
    Ok(())
}

/// Retain an advisory lock for the entire session, so two launchers cannot race.
fn session_lock() -> Result<File> {
    let home = std::env::var_os("HOME").context("HOME is not set")?;
    let folder = PathBuf::from(home).join("Library/Caches/VS Electronic Music");
    fs::create_dir_all(&folder)?;
    let file = File::options()
        .create(true)
        .truncate(false)
        .write(true)
        .open(folder.join("vs_set.lock"))?;
    let status = unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) };
    ensure!(
        status == 0,
        "Another vs_set or bwset session is already running."
    );
    Ok(file)
}

struct RawInput;
impl Drop for RawInput {
    fn drop(&mut self) {
        let _ = terminal::disable_raw_mode();
    }
}

fn wait_for_enter(
    prompt: &str,
    mut midi: Option<&mut MidiTest>,
    td: &mut td::Monitor,
) -> Result<()> {
    println!("{prompt}");
    io::stdout().flush()?;
    terminal::enable_raw_mode()?;
    let _raw = RawInput;
    // Discard typeahead from the preceding stage, including a held Enter key.
    while event::poll(Duration::ZERO)? {
        let _ = event::read()?;
    }
    loop {
        check_cancelled()?;
        td.check_ready()?;
        if let Some(test) = midi.as_mut()
            && let Some(status) = test.child.try_wait()?
        {
            bail!("MIDI test exited before you advanced ({status}); Bitwig was not opened.");
        }
        if event::poll(Duration::from_millis(100))?
            && let Event::Key(key) = event::read()?
        {
            if key.kind != KeyEventKind::Press {
                continue;
            }
            if key.code == KeyCode::Char('c') && key.modifiers.contains(KeyModifiers::CONTROL) {
                CANCELLED.store(true, Ordering::Relaxed);
                check_cancelled()?;
            }
            if key.code == KeyCode::Enter {
                return Ok(());
            }
        }
    }
}

struct MidiTest {
    child: Child,
}
impl MidiTest {
    fn start(binary: &Path, demo: bool) -> Result<Self> {
        let mut command = Command::new(binary);
        command
            .args(["--headless", "--until-stopped"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::inherit())
            .process_group(0);
        if demo {
            command.arg("--demo");
        } else {
            command.args(["--osc", "127.0.0.1:9012"]);
        }
        Ok(Self {
            child: command.spawn().context("Start the MIDI/audio test")?,
        })
    }

    fn stop(&mut self) -> Result<()> {
        if let Some(status) = self.child.try_wait()? {
            ensure!(
                status.success(),
                "MIDI test failed ({status}); Bitwig was not opened."
            );
            return Ok(());
        }
        // Only the child we own. Its handler releases notes and drops both audio streams.
        let result = unsafe { libc::kill(self.child.id() as i32, libc::SIGINT) };
        ensure!(
            result == 0,
            "Could not stop MIDI test: {}",
            io::Error::last_os_error()
        );
        let until = Instant::now() + Duration::from_secs(10);
        while Instant::now() < until {
            if let Some(status) = self.child.try_wait()? {
                ensure!(
                    status.success(),
                    "MIDI shutdown failed ({status}); Bitwig was not opened."
                );
                return Ok(());
            }
            thread::sleep(Duration::from_millis(50));
        }
        bail!(
            "MIDI test PID {} has not exited; Bitwig was not opened. Stop that test before continuing.",
            self.child.id()
        )
    }
}
impl Drop for MidiTest {
    fn drop(&mut self) {
        if let Err(error) = self.stop() {
            eprintln!("{error:#}");
        }
    }
}

#[cfg(target_os = "macos")]
fn open_set(projects: &[PathBuf], seconds: f64) -> Result<()> {
    for (index, path) in projects.iter().enumerate() {
        check_cancelled()?;
        println!("[{}/{}] {}", index + 1, projects.len(), path.display());
        macos::open(macos::BITWIG_APP, path)?;
        if index + 1 < projects.len() {
            if index == 0 {
                println!("Waiting for Bitwig to finish starting…");
                macos::wait_for_bitwig()?;
            }
            delay(seconds)?;
        }
    }
    Ok(())
}

pub fn run() -> Result<()> {
    let cli = Cli::parse();
    if matches!(cli.command, Some(Action::Visuals | Action::TdStatus)) {
        let toe = Path::new(REPO).join("live_bw/live_bw.toe").canonicalize()?;
        ctrlc::set_handler(|| CANCELLED.store(true, Ordering::Relaxed))?;
        if cli.set.dry_run {
            println!(
                "TouchDesigner heartbeat: 127.0.0.1:9013 · {}",
                toe.display()
            );
            return Ok(());
        }
        let mut monitor = td::Monitor::bind(&toe)?;
        if matches!(cli.command, Some(Action::TdStatus)) {
            return monitor.print_status();
        }
        #[cfg(target_os = "macos")]
        {
            let _lock = session_lock()?;
            ensure!(
                macos::external_displays()? > 0,
                "Connect the external display/projector before starting the visuals."
            );
            return monitor.prepare();
        }
        #[cfg(not(target_os = "macos"))]
        bail!("App launching requires macOS.");
    }
    let dry_run = cli.set.dry_run;
    let (mut args, only_bitwig, positional) = match cli.command {
        Some(Action::Bwset { setlist, options }) => (options, true, setlist),
        None => (cli.set, false, None),
        _ => unreachable!(),
    };
    args.dry_run |= dry_run;
    if let Some(path) = positional {
        args.setlist_file = path;
    }
    if !only_bitwig {
        ensure!(
            args.setlist_file.canonicalize()?
                == Path::new(REPO)
                    .join("live_bw/setlist.json")
                    .canonicalize()?,
            "vs_set uses live_bw/setlist.json shared with the saved master. Edit that file; bwset accepts alternate setlists."
        );
    }
    ensure!(
        args.delay.is_finite() && (0.0..=3600.0).contains(&args.delay),
        "--delay must be a finite number from 0 to 3600 seconds"
    );
    let home = PathBuf::from(std::env::var_os("HOME").context("HOME is not set")?);
    let projects_root = args
        .projects_root
        .unwrap_or_else(|| home.join("Documents/Bitwig Studio/Projects"));
    let projects = projects::resolve(&args.setlist_file, &projects_root)?;
    let mut toe = Path::new(REPO).join("live_bw/live_bw.toe");
    if !only_bitwig {
        toe = toe
            .canonicalize()
            .context("Locate the TouchDesigner master")?;
    }
    let binary = std::env::current_exe()?.with_file_name("live-connection-util");
    if !only_bitwig {
        ensure!(
            binary.is_file(),
            "Missing MIDI binary: {}. Rebuild with cargo build --release --bins.",
            binary.display()
        );
    }
    if args.dry_run {
        if !only_bitwig {
            println!(
                "1. Open/reuse TouchDesigner: {}\n   Confirm heartbeat + readiness. Saved external-display fullscreen, 1920×1080 output.",
                toe.display()
            );
            println!(
                "2. Enter → {} --headless --until-stopped --osc 127.0.0.1:9012",
                binary.display()
            );
            println!(
                "3. Enter → SIGINT, wait for clean exit, then Bitwig ({:.1}s between projects):",
                args.delay
            );
        }
        for (i, path) in projects.iter().enumerate() {
            println!("  [{}/{}] {}", i + 1, projects.len(), path.display());
        }
        #[cfg(target_os = "macos")]
        println!(
            "External displays: {} · Bitwig running: {}",
            macos::external_displays()?,
            macos::running("com.bitwig.studio")
        );
        return Ok(());
    }
    #[cfg(not(target_os = "macos"))]
    bail!("App launching requires macOS; --dry-run is available for path checks.");
    #[cfg(target_os = "macos")]
    {
        ensure!(
            Path::new(macos::BITWIG_APP).is_dir(),
            "Bitwig is not installed at {}",
            macos::BITWIG_APP
        );
        let _lock = session_lock()?;
        ctrlc::set_handler(|| CANCELLED.store(true, Ordering::Relaxed))?;
        if !only_bitwig {
            ensure!(
                io::stdin().is_terminal() && io::stdout().is_terminal(),
                "Run vs_set in an interactive terminal."
            );
            ensure!(
                Path::new(macos::TD_APP).is_dir(),
                "TouchDesigner is not installed at {}",
                macos::TD_APP
            );
            ensure!(
                macos::external_displays()? > 0,
                "Connect the external display/projector before starting vs_set."
            );
            ensure!(
                !macos::running("com.bitwig.studio"),
                "Quit Bitwig before the audio test, then run vs_set again."
            );
            let mut td = td::Monitor::bind(&toe)?;
            td.prepare()?;
            wait_for_enter(
                "Visuals are ready. Press Enter to start the MIDI test. (Ctrl-C cancels.)",
                None,
                &mut td,
            )?;
            check_cancelled()?;
            // Check again: the audio interface must not be shared with Bitwig.
            ensure!(
                !macos::running("com.bitwig.studio"),
                "Bitwig is open; MIDI test was not started."
            );
            let mut midi = MidiTest::start(&binary, false)?;
            wait_for_enter(
                "MIDI test: 65 BPM · Tetra + Moog → Analog Four L/R. Press Enter when ready to stop it and open the set.",
                Some(&mut midi),
                &mut td,
            )?;
            println!("Stopping MIDI and releasing the audio interface…");
            midi.stop()?;
            drop(midi);
            td.check_ready()?;
            println!("MIDI test has exited. Opening the Bitwig set.");
        }
        open_set(&projects, args.delay)?;
        println!("Set opened in order. TouchDesigner remains running.");
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn demo_child_releases_cleanly_before_handoff() {
        let binary =
            Path::new(env!("CARGO_MANIFEST_DIR")).join("target/release/live-connection-util");
        let mut midi = MidiTest::start(&binary, true).unwrap();
        thread::sleep(Duration::from_millis(500));
        assert!(midi.child.try_wait().unwrap().is_none());
        midi.stop().unwrap();
        assert!(midi.child.try_wait().unwrap().unwrap().success());
    }

    #[test]
    fn failed_child_prevents_handoff() {
        let child = Command::new("/usr/bin/false").spawn().unwrap();
        let mut midi = MidiTest { child };
        midi.child.wait().unwrap();
        assert!(midi.stop().is_err());
    }
}
