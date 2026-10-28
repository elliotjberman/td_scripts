//! Low-rate, one-way OSC health from the master. No TD command/execution server.
use anyhow::{Context, Result, bail, ensure};
use rosc::{OscPacket, OscType};
use serde::Serialize;
use std::{
    collections::HashMap,
    io,
    net::UdpSocket,
    path::{Path, PathBuf},
    thread,
    time::{Duration, Instant},
};

const ADDRESS: &str = "127.0.0.1:9013";
const STALE: Duration = Duration::from_secs(3);
const DISCOVERY: Duration = Duration::from_secs(2);
const STARTUP: Duration = Duration::from_secs(180);

#[derive(Clone, Debug, Serialize)]
pub struct Heartbeat {
    pub toe: PathBuf,
    pub session: String,
    pub pid: i32,
    pub sequence: i32,
    pub state: String,
    pub loaded: i32,
    pub total: i32,
    pub loading_visual: String,
    pub load_status: String,
    pub visual: String,
    pub bitwig_project: String,
    pub router_status: String,
    pub output_cooks: i32,
    pub output_frame: i32,
    pub width: i32,
    pub height: i32,
    pub visual_present: bool,
    pub perform_mode: bool,
}

impl Heartbeat {
    fn decode(bytes: &[u8]) -> Option<Self> {
        let (rest, OscPacket::Message(message)) = rosc::decoder::decode_udp(bytes).ok()? else {
            return None;
        };
        if !rest.is_empty() || message.addr != "/vs_set/td/heartbeat" {
            return None;
        }
        use OscType::{Int as I, String as S};
        let [
            I(1),
            S(toe),
            S(session),
            I(pid),
            I(sequence),
            S(state),
            I(loaded),
            I(total),
            S(loading_visual),
            S(load_status),
            S(visual),
            S(bitwig_project),
            S(router_status),
            I(output_cooks),
            I(output_frame),
            I(width),
            I(height),
            I(visual_present),
            I(perform_mode),
        ] = message.args.as_slice()
        else {
            return None;
        };
        if !Path::new(toe).is_absolute()
            || session.len() != 32
            || !session.bytes().all(|x| x.is_ascii_hexdigit())
            || *pid <= 0
            || *sequence <= 0
            || !["loading", "ready", "error"].contains(&state.as_str())
            || *loaded < 0
            || *total < *loaded
            || *output_cooks < 0
            || *width < 0
            || *height < 0
            || ![0, 1].contains(visual_present)
            || ![0, 1].contains(perform_mode)
        {
            return None;
        }
        Some(Self {
            toe: PathBuf::from(toe),
            session: session.clone(),
            pid: *pid,
            sequence: *sequence,
            state: state.clone(),
            loaded: *loaded,
            total: *total,
            loading_visual: loading_visual.clone(),
            load_status: load_status.clone(),
            visual: visual.clone(),
            bitwig_project: bitwig_project.clone(),
            router_status: router_status.clone(),
            output_cooks: *output_cooks,
            output_frame: *output_frame,
            width: *width,
            height: *height,
            visual_present: *visual_present == 1,
            perform_mode: *perform_mode == 1,
        })
    }

    fn ready(&self) -> bool {
        self.state == "ready"
            && self.total > 0
            && self.loaded == self.total
            && self.visual_present
            && self.output_cooks > 0
            && self.width > 0
            && self.height > 0
    }

    fn matches(&self, toe: &Path) -> bool {
        self.toe == toe || self.toe.canonicalize().is_ok_and(|path| path == toe)
    }
}

struct Peer {
    beat: Heartbeat,
    received: Instant,
    advancing: bool,
}

#[derive(Default)]
struct Peers(HashMap<String, Peer>);
impl Peers {
    fn receive(&mut self, beat: Heartbeat, now: Instant) {
        // Duplicate/out-of-order packets cannot keep a dead session alive.
        let old = self.0.get(&beat.session);
        if old.is_some_and(|p| beat.sequence <= p.beat.sequence || beat.pid != p.beat.pid) {
            return;
        }
        let advancing = old.is_some_and(|p| now.duration_since(p.received) < STALE);
        self.0.insert(
            beat.session.clone(),
            Peer {
                beat,
                received: now,
                advancing,
            },
        );
        // Bound discovery memory while retaining sequence history for recent sessions.
        self.0
            .retain(|_, p| now.duration_since(p.received) < STARTUP);
    }

    fn current(&self, toe: &Path, now: Instant) -> Result<Option<&Peer>> {
        let mut matches = self
            .0
            .values()
            .filter(|p| now.duration_since(p.received) < STALE && p.beat.matches(toe));
        let first = matches.next();
        ensure!(
            matches.next().is_none(),
            "Multiple TouchDesigner sessions report the master. No additional instance was opened; close the duplicate before continuing."
        );
        Ok(first)
    }

    fn wrong_project(&self, toe: &Path, now: Instant) -> Option<&Heartbeat> {
        self.0
            .values()
            .find(|p| now.duration_since(p.received) < STALE && !p.beat.matches(toe))
            .map(|p| &p.beat)
    }
}

pub struct Monitor {
    socket: UdpSocket,
    peers: Peers,
    toe: PathBuf,
    selected: Option<String>,
}

impl Monitor {
    pub fn bind(toe: &Path) -> Result<Self> {
        let socket = UdpSocket::bind(ADDRESS).context(
            "Listen for TD on 127.0.0.1:9013. Another launcher/status listener may already own this port")?;
        socket.set_nonblocking(true)?;
        Ok(Self {
            socket,
            peers: Peers::default(),
            toe: toe.to_owned(),
            selected: None,
        })
    }

    fn poll(&mut self) -> Result<()> {
        let mut data = [0; 4096];
        // Bounded work, even if another local sender floods this port.
        for _ in 0..64 {
            match self.socket.recv_from(&mut data) {
                Ok((size, from)) if from.ip().is_loopback() => {
                    if let Some(beat) = Heartbeat::decode(&data[..size]) {
                        self.peers.receive(beat, Instant::now());
                    }
                }
                Ok(_) => (),
                Err(e) if e.kind() == io::ErrorKind::WouldBlock => break,
                Err(e) => return Err(e.into()),
            }
        }
        Ok(())
    }

    fn listen(&mut self, duration: Duration) -> Result<()> {
        let until = Instant::now() + duration;
        while Instant::now() < until {
            super::check_cancelled()?;
            self.poll()?;
            thread::sleep(Duration::from_millis(50));
        }
        self.poll()
    }

    pub fn print_status(&mut self) -> Result<()> {
        self.listen(DISCOVERY)?;
        let now = Instant::now();
        let peers: Vec<_> = self
            .peers
            .0
            .values()
            .filter(|p| now.duration_since(p.received) < STALE)
            .map(|p| {
                serde_json::json!({"expected_master":p.beat.matches(&self.toe),
                "advancing":p.advancing,"heartbeat":p.beat})
            })
            .collect();
        println!("{}", serde_json::to_string_pretty(&peers)?);
        ensure!(
            !peers.is_empty(),
            "No TD heartbeat received. No apps were opened."
        );
        Ok(())
    }

    #[cfg(target_os = "macos")]
    pub fn prepare(&mut self) -> Result<()> {
        use super::macos;
        println!("Checking TouchDesigner heartbeat…");
        self.listen(DISCOVERY)?;
        let pids = macos::td_pids();
        let current = self.peers.current(&self.toe, Instant::now())?;
        if let Some(peer) = current {
            ensure!(
                pids.contains(&peer.beat.pid),
                "TD heartbeat belongs to a process that has exited. Run vs_set again."
            );
            println!(
                "Reusing TouchDesigner PID {}: {}",
                peer.beat.pid,
                peer.beat.toe.display()
            );
        } else if let Some(wrong) = self.peers.wrong_project(&self.toe, Instant::now()) {
            bail!(
                "TouchDesigner is reporting a different project: {}. No master was opened and that project was left untouched.",
                wrong.toe.display()
            );
        } else if pids.is_empty() {
            println!("Opening {}", self.toe.display());
            macos::open(macos::TD_APP, &self.toe)?;
        } else {
            println!(
                "TouchDesigner is already running but has not reported this master. Waiting; no duplicate will be opened. (Ctrl-C cancels.)"
            );
        }
        // Blocking imports/shader compilation can suspend heartbeats during startup.
        // Give both an existing loader and a new process the same bounded grace.
        let until = Instant::now() + STARTUP;
        let mut last = String::new();
        while Instant::now() < until {
            super::check_cancelled()?;
            self.poll()?;
            if let Some(peer) = self.peers.current(&self.toe, Instant::now())? {
                let beat = &peer.beat;
                ensure!(
                    beat.state != "error",
                    "TouchDesigner reports: {} · {}",
                    beat.load_status,
                    beat.router_status
                );
                let message = format!(
                    "TD {} · {}/{} · {}",
                    beat.state, beat.loaded, beat.total, beat.load_status
                );
                if message != last {
                    println!("{message}");
                    last = message;
                }
                if peer.advancing && beat.ready() {
                    ensure!(
                        macos::td_pids().contains(&beat.pid),
                        "The reporting TD process has exited; rerun vs_set."
                    );
                    self.selected = Some(beat.session.clone());
                    println!(
                        "Visuals ready · {} · {}×{}",
                        beat.visual, beat.width, beat.height
                    );
                    return Ok(());
                }
            } else if let Some(wrong) = self.peers.wrong_project(&self.toe, Instant::now()) {
                bail!(
                    "TouchDesigner opened a different project: {}. Startup stopped.",
                    wrong.toe.display()
                );
            }
            thread::sleep(Duration::from_millis(50));
        }
        bail!(
            "TouchDesigner did not confirm this master ready within 180 seconds. It may be loading, frozen, or running another project. No duplicate was opened; inspect TD before retrying."
        )
    }

    pub fn check_ready(&mut self) -> Result<()> {
        self.poll()?;
        let peer = self.peers.current(&self.toe, Instant::now())?.context(
            "TouchDesigner heartbeat stopped for 3 seconds. Startup stopped; no replacement was opened. Check TD, then rerun vs_set")?;
        ensure!(
            self.selected.as_ref() == Some(&peer.beat.session),
            "TouchDesigner changed sessions. Startup stopped; rerun vs_set to adopt the new session."
        );
        ensure!(
            peer.advancing && peer.beat.ready(),
            "TouchDesigner is no longer ready: {} · {}. Startup stopped.",
            peer.beat.load_status,
            peer.beat.router_status
        );
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn packet(sequence: i32, session: &str, toe: &str, state: &str) -> Vec<u8> {
        use OscType::{Int as I, String as S};
        rosc::encoder::encode(&OscPacket::Message(rosc::OscMessage {
            addr: "/vs_set/td/heartbeat".into(),
            args: vec![
                I(1),
                S(toe.into()),
                S(session.into()),
                I(123),
                I(sequence),
                S(state.into()),
                I(4),
                I(4),
                S("".into()),
                S("Ready".into()),
                S("screensaver".into()),
                S("".into()),
                S("DISCONNECTED: holding current visual".into()),
                I(100),
                I(120),
                I(1920),
                I(1080),
                I(1),
                I(1),
            ],
        }))
        .unwrap()
    }
    const SESSION: &str = "0123456789abcdef0123456789abcdef";

    #[test]
    fn midi_shutdown_latches_td_loss_until_child_exits() {
        use std::{
            io::Read,
            os::unix::process::CommandExt,
            process::{Command, Stdio},
        };

        let socket = UdpSocket::bind("127.0.0.1:0").unwrap();
        socket.set_nonblocking(true).unwrap();
        let destination = socket.local_addr().unwrap();
        let sender = UdpSocket::bind("127.0.0.1:0").unwrap();
        let mut monitor = Monitor {
            socket,
            peers: Peers::default(),
            toe: PathBuf::from("/master.toe"),
            selected: Some(SESSION.into()),
        };
        for seq in [1, 2] {
            sender
                .send_to(&packet(seq, SESSION, "/master.toe", "ready"), destination)
                .unwrap();
        }
        monitor.check_ready().unwrap();

        // A real child acknowledges its signal handler, then takes longer than
        // the heartbeat timeout to clean up. No TD or MIDI hardware is needed.
        let child = Command::new("/bin/sh")
            .args([
                "-c",
                "trap 'sleep 4; exit 0' INT; printf ready; while :; do sleep 0.05; done",
            ])
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .process_group(0)
            .spawn()
            .unwrap();
        let mut midi = super::super::MidiTest { child };
        let mut ready = [0; 5];
        midi.child
            .stdout
            .take()
            .unwrap()
            .read_exact(&mut ready)
            .unwrap();
        assert_eq!(&ready, b"ready");

        // These packets must be consumed during shutdown, not made fresh by
        // draining the socket only after the child has exited.
        for seq in [3, 4] {
            sender
                .send_to(&packet(seq, SESSION, "/master.toe", "ready"), destination)
                .unwrap();
        }
        let mut failed = false;
        let mut recovered = false;
        let error = midi
            .stop(|| {
                let health = monitor.check_ready();
                if health.is_err() && !failed {
                    failed = true;
                    // Even a recovery before cleanup finishes must not erase the
                    // startup failure or permit the subsequent Bitwig handoff.
                    for seq in [5, 6] {
                        sender
                            .send_to(&packet(seq, SESSION, "/master.toe", "ready"), destination)
                            .unwrap();
                    }
                } else if failed && health.is_ok() {
                    recovered = true;
                }
                health
            })
            .unwrap_err();
        assert!(error.to_string().contains("heartbeat stopped"));
        assert!(
            recovered,
            "Health polling must continue until cleanup finishes"
        );
        assert!(midi.child.try_wait().unwrap().unwrap().success());
        monitor.check_ready().unwrap();
    }

    /// Finite authoring check; explicitly invoked, bypasses the gig's display guard.
    /// Never starts audio/MIDI or Bitwig. The caller must arrange the TD fixture.
    #[test]
    #[ignore = "requires the local TouchDesigner lifecycle fixture"]
    #[cfg(target_os = "macos")]
    fn native_master_lifecycle() {
        let toe = Path::new(super::super::REPO)
            .join("live_bw/live_bw.toe")
            .canonicalize()
            .unwrap();
        let mut monitor = Monitor::bind(&toe).unwrap();
        let result = monitor.prepare();
        if std::env::var_os("VS_TD_EXPECT_REFUSAL").is_some() {
            assert!(
                result
                    .unwrap_err()
                    .to_string()
                    .contains("different project")
            );
        } else {
            result.unwrap();
            monitor.check_ready().unwrap();
            if std::env::var_os("VS_TD_FREEZE_CHECK").is_some() {
                let pid = monitor
                    .peers
                    .current(&toe, Instant::now())
                    .unwrap()
                    .unwrap()
                    .beat
                    .pid;
                let before = super::super::macos::td_pids();
                struct Resume(i32);
                impl Drop for Resume {
                    fn drop(&mut self) {
                        unsafe {
                            libc::kill(self.0, libc::SIGCONT);
                        }
                    }
                }
                // Only the identified fixture process; always resume it on failure.
                let resume = Resume(pid);
                assert_eq!(unsafe { libc::kill(pid, libc::SIGSTOP) }, 0);
                monitor.listen(Duration::from_millis(3300)).unwrap();
                assert!(
                    monitor
                        .check_ready()
                        .unwrap_err()
                        .to_string()
                        .contains("heartbeat stopped")
                );
                drop(monitor);
                // A new invocation sees the stopped process, waits, and adopts it
                // when responsive again instead of launching a second instance.
                let resumer = thread::spawn(move || {
                    thread::sleep(Duration::from_secs(3));
                    unsafe {
                        libc::kill(pid, libc::SIGCONT);
                    }
                });
                let mut next = Monitor::bind(&toe).unwrap();
                let prepared = next.prepare();
                resumer.join().unwrap();
                drop(resume);
                prepared.unwrap();
                next.check_ready().unwrap();
                let after = super::super::macos::td_pids();
                assert_eq!(before, after, "A duplicate TD process was opened");
                println!(
                    "Freeze → stale heartbeat → retry without duplicate → resumed same process: passed"
                );
            }
        }
    }

    #[test]
    fn loopback_guard_rejects_restart_loss_and_error() {
        let socket = UdpSocket::bind("127.0.0.1:0").unwrap();
        socket.set_nonblocking(true).unwrap();
        let destination = socket.local_addr().unwrap();
        let sender = UdpSocket::bind("127.0.0.1:0").unwrap();
        let mut monitor = Monitor {
            socket,
            peers: Peers::default(),
            toe: PathBuf::from("/master.toe"),
            selected: Some(SESSION.into()),
        };
        for seq in [1, 2] {
            sender
                .send_to(&packet(seq, SESSION, "/master.toe", "ready"), destination)
                .unwrap();
            monitor.listen(Duration::from_millis(10)).unwrap();
        }
        monitor.check_ready().unwrap();
        sender
            .send_to(&packet(3, SESSION, "/master.toe", "error"), destination)
            .unwrap();
        monitor.listen(Duration::from_millis(10)).unwrap();
        assert!(
            monitor
                .check_ready()
                .unwrap_err()
                .to_string()
                .contains("no longer ready")
        );
        monitor.peers.0.get_mut(SESSION).unwrap().received = Instant::now() - STALE;
        assert!(
            monitor
                .check_ready()
                .unwrap_err()
                .to_string()
                .contains("heartbeat stopped")
        );
        let restarted = "abcdef0123456789abcdef0123456789";
        sender
            .send_to(&packet(1, restarted, "/master.toe", "ready"), destination)
            .unwrap();
        monitor.listen(Duration::from_millis(10)).unwrap();
        assert!(
            monitor
                .check_ready()
                .unwrap_err()
                .to_string()
                .contains("changed sessions")
        );
    }

    #[test]
    fn loading_ready_duplicate_and_stale_lifecycle() {
        let mut peers = Peers::default();
        let now = Instant::now();
        let toe = Path::new("/master.toe");
        peers.receive(
            Heartbeat::decode(&packet(1, SESSION, "/master.toe", "loading")).unwrap(),
            now,
        );
        assert!(!peers.current(toe, now).unwrap().unwrap().beat.ready());
        peers.receive(
            Heartbeat::decode(&packet(2, SESSION, "/master.toe", "ready")).unwrap(),
            now + Duration::from_millis(500),
        );
        let p = peers
            .current(toe, now + Duration::from_secs(1))
            .unwrap()
            .unwrap();
        assert!(p.advancing && p.beat.ready());
        // Replayed packets and out-of-order delivery cannot renew freshness.
        for seq in [2, 1] {
            peers.receive(
                Heartbeat::decode(&packet(seq, SESSION, "/master.toe", "ready")).unwrap(),
                now + Duration::from_secs(3),
            );
        }
        assert!(
            peers
                .current(toe, now + Duration::from_secs(4))
                .unwrap()
                .is_none()
        );
    }

    #[test]
    fn wrong_project_and_duplicate_sessions_are_not_adopted() {
        let mut peers = Peers::default();
        let now = Instant::now();
        let toe = Path::new("/master.toe");
        peers.receive(
            Heartbeat::decode(&packet(1, SESSION, "/authoring.toe", "ready")).unwrap(),
            now,
        );
        assert!(peers.current(toe, now).unwrap().is_none());
        assert!(peers.wrong_project(toe, now).is_some());
        peers.receive(
            Heartbeat::decode(&packet(2, SESSION, "/master.toe", "ready")).unwrap(),
            now,
        );
        let restarted = "abcdef0123456789abcdef0123456789";
        peers.receive(
            Heartbeat::decode(&packet(1, restarted, "/master.toe", "ready")).unwrap(),
            now,
        );
        assert!(peers.current(toe, now).is_err());
        peers.receive(
            Heartbeat::decode(&packet(2, restarted, "/master.toe", "ready")).unwrap(),
            now + Duration::from_secs(4),
        );
        let p = peers
            .current(toe, now + Duration::from_secs(4))
            .unwrap()
            .unwrap();
        assert_eq!(p.beat.session, restarted);
        assert!(!p.advancing); // Need fresh advancing traffic after a gap.
    }

    #[test]
    fn wire_validation_and_readiness() {
        for invalid in [
            b"nonsense".as_slice(),
            &packet(0, SESSION, "/master.toe", "ready"),
            &packet(1, "bad", "/master.toe", "ready"),
            &packet(1, SESSION, "relative.toe", "ready"),
        ] {
            assert!(Heartbeat::decode(invalid).is_none());
        }
        let mut beat = Heartbeat::decode(&packet(1, SESSION, "/master.toe", "ready")).unwrap();
        assert!(beat.ready());
        beat.visual_present = false;
        assert!(!beat.ready());
        beat.visual_present = true;
        beat.state = "error".into();
        assert!(!beat.ready());
        beat.state = "ready".into();
        beat.output_cooks = 0;
        assert!(!beat.ready());
    }
}
