//! Exercise the real binary and telemetry without opening MIDI/audio hardware.
use std::{fs, process::Command};

#[test]
fn interface_and_routing_each_get_one_second_before_midi_starts() {
    let path = std::env::temp_dir().join(format!("lcu-startup-delay-{}.jsonl", std::process::id()));
    let output = Command::new(env!("CARGO_BIN_EXE_live-connection-util"))
        .args([
            "--demo",
            "--quarter-notes",
            "--headless",
            "--seconds",
            "3.4",
            "--jsonl",
        ])
        .arg(&path)
        .output()
        .unwrap();
    let data = fs::read_to_string(&path).unwrap();
    fs::remove_file(&path).unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let frames: Vec<serde_json::Value> = data
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .collect();
    let waiting: Vec<_> = frames
        .iter()
        .filter(|f| f["elapsed_seconds"].as_f64().unwrap() < 2.0)
        .collect();
    assert!(
        waiting.len() >= 40,
        "Telemetry must keep updating during the lead-in"
    );
    for frame in waiting {
        assert_eq!(frame["running"], true);
        if frame["elapsed_seconds"].as_f64().unwrap() < 1.0 {
            assert_eq!(frame["midi_routing"]["status"], "pending");
        }
        for voice in frame["voices"].as_array().unwrap() {
            assert_eq!(voice["notes_sent"], 0);
            assert_eq!(voice["note_on"], false);
            assert!(
                !voice["peak"].is_null(),
                "Valid input telemetry precedes note playback"
            );
        }
    }
    let first_note = frames
        .iter()
        .find(|f| f["voices"][0]["notes_sent"].as_u64().unwrap() > 0)
        .unwrap();
    assert!(first_note["elapsed_seconds"].as_f64().unwrap() >= 2.15);
    let routed = frames
        .iter()
        .find(|f| f["midi_routing"]["status"] == "ready")
        .unwrap();
    let routed_at = routed["elapsed_seconds"].as_f64().unwrap();
    assert!(
        (1.0..1.5).contains(&routed_at),
        "Routing should succeed after the first one-second pause"
    );
    assert!(
        first_note["elapsed_seconds"].as_f64().unwrap() - routed_at >= 1.0,
        "Routing must stay ready for a second before playback"
    );
    assert_eq!(
        routed["voices"][0]["notes_sent"], 0,
        "Routing is published before the first note"
    );
    let last = frames.last().unwrap();
    assert_eq!(last["running"], false);
    assert_eq!(
        last["skipped_beats"], 0,
        "Waiting must not consume or skip the score's opening notes"
    );
    for voice in last["voices"].as_array().unwrap() {
        assert!(voice["notes_sent"].as_u64().unwrap() >= 2);
        assert_eq!(voice["note_on"], false);
    }
}
