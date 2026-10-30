#!/usr/bin/env python3
"""Exercise the real binary in demo mode: PTY controls, JSONL and UDP. No hardware."""
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import socket
import struct
import subprocess
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "target/release/live-connection-util"


def terminal_test(runs):
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))
    original = termios.tcgetattr(slave)
    path = runs / "terminal-demo.jsonl"
    environment = dict(os.environ, TERM="xterm-256color", COLORTERM="truecolor")
    environment.pop("NO_COLOR", None)
    child = subprocess.Popen(
        [str(BIN), "--quarter-notes", "--demo", "--seconds", "10", "--jsonl", str(path)],
        stdin=slave, stdout=slave, stderr=slave, env=environment,
    )
    captured = bytearray()

    def collect(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            ready, _, _ = select.select([master], [], [], min(0.02, max(0, end - time.monotonic())))
            if ready:
                captured.extend(os.read(master, 65536))

    try:
        collect(3.3)
        os.write(master, b" ")
        collect(0.6)
        os.write(master, b" ")
        collect(2.7)
        os.write(master, b"\x03")
        collect(0.2)
        assert child.wait(timeout=3) == 0
        assert termios.tcgetattr(slave) == original, "terminal mode was not restored"
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
        os.close(master)
        os.close(slave)
    text = captured.decode()
    for fragment in ["LIVE CONNECTION UTIL", "RUNNING", "PAUSED", "Moog", "Tetra", "GOOD", "LOW", "NO SIGNAL", "Latency -- (unmeasured)", "████", "\x1b[?1049h", "\x1b[?1049l", "\x1b[38;5;10m", "\x1b[38;5;9m", "\x1b[38;5;208m"]:
        assert fragment in text, repr(fragment)
    frames = [json.loads(line) for line in path.read_text().splitlines()]
    paused = [f for f in frames if f["paused"] and 3.5 < f["elapsed_seconds"] < 3.8]
    assert len(paused) > 2
    assert len({f["voices"][0]["notes_sent"] for f in paused}) == 1
    assert all(not v["note_on"] for f in paused for v in f["voices"])
    assert frames[-1]["voices"][0]["notes_sent"] > paused[-1]["voices"][0]["notes_sent"]
    assert not frames[-1]["running"] and all(not v["note_on"] for v in frames[-1]["voices"])
    print("PASS: real TUI render and green/red/orange colors, pause/resume/Ctrl-C, final telemetry and terminal restoration")


def telemetry_test(runs):
    path = runs / "telemetry-demo.jsonl"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(0.1)
        port = receiver.getsockname()[1]
        child = subprocess.Popen(
            [str(BIN), "--quarter-notes", "--demo", "--headless", "--seconds", "9.2", "--jsonl", str(path), "--udp", f"127.0.0.1:{port}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        received = []
        deadline = time.monotonic() + 15
        try:
            while time.monotonic() < deadline:
                try:
                    received.append(json.loads(receiver.recv(65536)))
                except socket.timeout:
                    if child.poll() is not None:
                        break
            stdout, stderr = child.communicate(timeout=2)
            assert child.returncode == 0, stderr.decode()
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
    frames = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(received) > 200
    assert len(frames) == len(received)
    assert {f["voices"][1]["status"] for f in frames} >= {"no_signal", "low", "good"}
    assert all(f["mode"] == "demo" and f["schema_version"] == 1 for f in frames)
    assert all(f["audio_frames"] == 0 for f in frames)
    assert all(v["latency"]["average_ms"] is None and v["latency"]["state"] == "unmeasured" for f in frames for v in f["voices"])
    assert not frames[-1]["running"]
    assert json.loads(stdout)["voices"][0]["notes_sent"] == 19
    print(f"PASS: {len(frames)} JSONL/UDP frames, all three meter colors, 19 pulses/channel after two 1s pauses at 160 BPM")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="lcu-runtime-") as folder:
        terminal_test(Path(folder))
        telemetry_test(Path(folder))
