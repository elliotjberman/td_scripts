#![cfg(target_os = "macos")]
use midir::{MidiInput, os::unix::VirtualInput};
use std::{
    process::{Command, Stdio},
    sync::{Arc, Mutex},
    thread,
    time::{Duration, Instant},
};

type Messages = Arc<Mutex<Vec<(Instant, Vec<u8>)>>>;

#[test]
#[ignore = "requires CoreMIDI outside the sandbox; uses only a virtual port"]
fn missing_controller_waits_and_hotplug_resumes_without_restart() {
    use std::net::UdpSocket;
    let port = format!("LiveConnectionLatePort-{}", std::process::id());
    let telemetry = UdpSocket::bind("127.0.0.1:0").unwrap();
    telemetry
        .set_read_timeout(Some(Duration::from_secs(2)))
        .unwrap();
    let mut child = Command::new(env!("CARGO_BIN_EXE_live-connection-util"))
        .args([
            "--midi-only",
            "--quarter-notes",
            "--headless",
            "--seconds",
            "5",
            "--midi-port",
            &port,
            "--udp",
        ])
        .arg(telemetry.local_addr().unwrap().to_string())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let read = || {
        let mut bytes = [0; 8192];
        let size = telemetry.recv(&mut bytes).unwrap();
        serde_json::from_slice::<serde_json::Value>(&bytes[..size]).unwrap()
    };
    let mut waiting = 0;
    while waiting < 15 {
        let f = read();
        assert_eq!(f["running"], true);
        assert_eq!(f["voices"][0]["notes_sent"], 0);
        assert_eq!(f["voices"][1]["notes_sent"], 0);
        if f["midi_routing"]["status"] == "waiting" {
            waiting += 1;
        }
    }
    assert!(
        child.try_wait().unwrap().is_none(),
        "Missing controller must not exit the child"
    );
    let messages: Messages = Arc::new(Mutex::new(vec![]));
    let received = messages.clone();
    let _input = MidiInput::new("live-connection-late-test")
        .unwrap()
        .create_virtual(
            &port,
            move |_, b, _| received.lock().unwrap().push((Instant::now(), b.to_vec())),
            (),
        )
        .unwrap();
    let mut routed_before_notes = false;
    let mut routing_seen = None;
    loop {
        let f = read();
        assert_eq!(
            f["running"], true,
            "Hotplug must be discovered before timeout"
        );
        if f["midi_routing"]["status"] == "ready" {
            routing_seen.get_or_insert_with(Instant::now);
            assert_eq!(f["midi_routing"]["message"], port);
            if f["voices"][0]["notes_sent"] == 0 {
                routed_before_notes = true;
            }
        }
        if f["voices"][0]["note_on"] == true && f["voices"][1]["note_on"] == true {
            break;
        }
    }
    assert!(routed_before_notes);
    assert!(
        Command::new("/bin/kill")
            .args(["-INT", &child.id().to_string()])
            .status()
            .unwrap()
            .success()
    );
    let output = child.wait_with_output().unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    thread::sleep(Duration::from_millis(30));
    let data = messages.lock().unwrap();
    assert!(
        data[0].0.duration_since(routing_seen.unwrap()) >= Duration::from_millis(950),
        "Even bend and program messages must wait a second after routing; allow one telemetry frame of observation delay"
    );
    for ch in 0..2 {
        let on = data.iter().filter(|(_, b)| b[0] == 0x90 + ch).count();
        let off = data.iter().filter(|(_, b)| b[0] == 0x80 + ch).count();
        assert!(on > 0);
        assert_eq!(on, off, "Hotplug playback must clean up every note on exit");
    }
    drop(data);

    // The same executable also remains cancellable when the device never appears.
    let mut missing = Command::new(env!("CARGO_BIN_EXE_live-connection-util"))
        .args([
            "--midi-only",
            "--headless",
            "--seconds",
            "5",
            "--midi-port",
            &format!("{port}-absent"),
            "--udp",
        ])
        .arg(telemetry.local_addr().unwrap().to_string())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    loop {
        let f = read();
        if f["midi_routing"]["status"] == "waiting" {
            break;
        }
    }
    assert!(missing.try_wait().unwrap().is_none());
    assert!(
        Command::new("/bin/kill")
            .args(["-INT", &missing.id().to_string()])
            .status()
            .unwrap()
            .success()
    );
    let output = missing.wait_with_output().unwrap();
    assert!(output.status.success());
    let final_frame: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(final_frame["running"], false);
    assert_eq!(final_frame["voices"][0]["notes_sent"], 0);
    assert_eq!(final_frame["voices"][1]["notes_sent"], 0);
}

// Explicit opt-in: needs CoreMIDI access, but connects only to a temporary
// software destination. Never touches KeyStep, synths or audio devices.
#[test]
#[ignore = "requires CoreMIDI outside the sandbox; uses only a virtual port"]
fn midi_bytes_timing_programs_and_termination() {
    let port = format!("LiveConnectionUtilTest-{}", std::process::id());
    let messages: Messages = Arc::new(Mutex::new(vec![]));
    let callback_messages = messages.clone();
    let _input = MidiInput::new("live-connection-util-test")
        .unwrap()
        .create_virtual(
            &port,
            move |_, bytes, _| {
                callback_messages
                    .lock()
                    .unwrap()
                    .push((Instant::now(), bytes.to_vec()))
            },
            (),
        )
        .unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_live-connection-util"))
        .args([
            "--quarter-notes",
            "--midi-only",
            "--headless",
            "--seconds",
            "2.35",
            "--midi-port",
            &port,
            "--moog-program",
            "5",
            "--tetra-program",
            "17",
        ])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    thread::sleep(Duration::from_millis(30));
    {
        let data = messages.lock().unwrap();
        assert_eq!(data[0].1, [0xe0, 0x00, 0x40]);
        assert_eq!(data[1].1, [0xe1, 0x00, 0x40]);
        assert_eq!(data[2].1, [0xc0, 5]);
        assert_eq!(data[3].1, [0xb1, 32, 0]);
        assert_eq!(data[4].1, [0xc1, 17]);
        for channel in 0..2 {
            let ons: Vec<_> = data
                .iter()
                .filter(|(_, b)| b[0] == 0x90 + channel)
                .collect();
            let offs: Vec<_> = data
                .iter()
                .filter(|(_, b)| b[0] == 0x80 + channel)
                .collect();
            assert_eq!(ons.len(), 4);
            assert_eq!(
                offs.len(),
                4,
                "final active note must be released at timed stop"
            );
            for pair in ons.windows(2) {
                let ms = pair[1].0.duration_since(pair[0].0).as_secs_f64() * 1000.0;
                assert!(
                    (350.0..400.0).contains(&ms),
                    "quarter-note interval {ms} ms"
                );
            }
            for (on, off) in ons.iter().zip(offs.iter()) {
                assert_eq!(on.1, [0x90 + channel, 60, 96]);
                assert_eq!(off.1, [0x80 + channel, 60, 0]);
                assert!(off.0 > on.0);
            }
        }
        assert_eq!(
            data.len(),
            21,
            "only centered bends, Tetra bank, requested PCs, note-ons and note-offs"
        );
    }
    messages.lock().unwrap().clear();
    let mut child = Command::new(env!("CARGO_BIN_EXE_live-connection-util"))
        .args([
            "--quarter-notes",
            "--keep-programs",
            "--midi-only",
            "--headless",
            "--seconds",
            "5",
            "--midi-port",
            &port,
        ])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let deadline = Instant::now() + Duration::from_secs(3);
    while !messages.lock().unwrap().iter().any(|(_, b)| b[0] == 0x91) {
        if Instant::now() >= deadline {
            let _ = child.kill();
            panic!("no second-channel note received");
        }
        thread::sleep(Duration::from_millis(1));
    }
    assert!(
        Command::new("/bin/kill")
            .args(["-TERM", &child.id().to_string()])
            .status()
            .unwrap()
            .success()
    );
    assert!(child.wait_with_output().unwrap().status.success());
    thread::sleep(Duration::from_millis(30));
    let data = messages.lock().unwrap();
    let bytes: Vec<_> = data.iter().map(|(_, b)| b.clone()).collect();
    assert_eq!(
        bytes,
        vec![
            vec![0xe0, 0x00, 0x40],
            vec![0xe1, 0x00, 0x40],
            vec![0x90, 60, 96],
            vec![0x91, 60, 96],
            vec![0x80, 60, 0],
            vec![0x81, 60, 0]
        ]
    );
    println!(
        "Verified ch1/ch2 notes, requested PCs, 375 ms intervals, timed and SIGTERM note-offs."
    );
}

#[test]
#[ignore = "requires CoreMIDI outside the sandbox; uses only a virtual port"]
fn file_loop_routes_staves_and_releases_chords_at_stop() {
    use midly::{
        Format, Header, MetaMessage, MidiMessage, Smf, Timing, TrackEvent, TrackEventKind,
    };
    let midi = |delta: u32, message| TrackEvent {
        delta: delta.into(),
        kind: TrackEventKind::Midi {
            channel: 9.into(),
            message,
        },
    };
    let on = |key: u8, vel: u8| MidiMessage::NoteOn {
        key: key.into(),
        vel: vel.into(),
    };
    let end = |delta: u32| TrackEvent {
        delta: delta.into(),
        kind: TrackEventKind::Meta(MetaMessage::EndOfTrack),
    };
    let smf = Smf {
        header: Header::new(Format::Parallel, Timing::Metrical(480.into())),
        tracks: vec![
            vec![
                TrackEvent {
                    delta: 0.into(),
                    kind: TrackEventKind::Meta(MetaMessage::Tempo(500_000.into())),
                },
                midi(0, MidiMessage::ProgramChange { program: 99.into() }),
                midi(0, on(72, 80)),
                midi(0, on(76, 81)),
                midi(120, on(72, 0)),
                midi(0, on(76, 0)),
                end(360),
            ],
            vec![midi(240, on(48, 70)), midi(120, on(48, 0)), end(120)],
        ],
    };
    let path = std::env::temp_dir().join(format!("connection-loop-{}.mid", std::process::id()));
    smf.save(&path).unwrap();
    let port = format!("LiveConnectionLoopTest-{}", std::process::id());
    let messages: Messages = Arc::new(Mutex::new(vec![]));
    let received = messages.clone();
    let _input = MidiInput::new("live-connection-loop-test")
        .unwrap()
        .create_virtual(
            &port,
            move |_, b, _| {
                received.lock().unwrap().push((Instant::now(), b.to_vec()));
            },
            (),
        )
        .unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_live-connection-util"))
        .args([
            "--midi-only",
            "--headless",
            "--seconds",
            "2.24",
            "--midi-port",
            &port,
            "--midi-file",
        ])
        .arg(&path)
        .output();
    std::fs::remove_file(path).unwrap();
    let output = output.unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    thread::sleep(Duration::from_millis(30));
    let data = messages.lock().unwrap();
    assert_eq!(data[0].1, [0xe0, 0x00, 0x40]);
    assert_eq!(data[1].1, [0xe1, 0x00, 0x40]);
    assert_eq!(data[2].1, [0xc0, 24]);
    assert_eq!(data[3].1, [0xb1, 32, 0]);
    assert_eq!(data[4].1, [0xc1, 77]);
    assert!(
        data.iter()
            .skip(5)
            .all(|(_, b)| matches!(b[0], 0x80 | 0x81 | 0x90 | 0x91)),
        "file program change must be ignored"
    );
    let mut active = [[0i32; 128]; 2];
    let mut attacks = [0; 2];
    for (_, b) in data.iter().skip(5) {
        let voice = (b[0] & 0xf) as usize;
        if b[0] & 0xf0 == 0x90 {
            attacks[voice] += 1;
            assert!(if voice == 0 {
                b[1..] == [48, 70]
            } else {
                b[1..] == [72, 80] || b[1..] == [76, 81]
            });
            active[voice][b[1] as usize] += 1;
        } else {
            active[voice][b[1] as usize] -= 1;
        }
        assert!((0..=1).contains(&active[voice][b[1] as usize]));
    }
    assert_eq!(attacks, [2, 6]);
    assert_eq!(
        active, [[0; 128]; 2],
        "stop releases both pitches of the final chord"
    );
    let upper: Vec<_> = data
        .iter()
        .filter(|(_, b)| b.as_slice() == [0x91, 72, 80])
        .collect();
    for pair in upper.windows(2) {
        assert!((0.46..0.54).contains(&pair[1].0.duration_since(pair[0].0).as_secs_f64()));
    }
    let frame: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(frame["loops_completed"], 2);
    assert_eq!(frame["voices"][0]["note"], 48);
    assert_eq!(frame["voices"][1]["note"], 76);
    println!(
        "Verified staff remapping, score velocities, repeated loop timing, ignored file programs and chord cleanup."
    );
}
