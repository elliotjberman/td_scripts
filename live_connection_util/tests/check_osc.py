#!/usr/bin/env python3
"""Validate OSC with an independent decoder and receiver restarts. No hardware."""
import json
import math
from pathlib import Path
import socket
import struct
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "target/release/live-connection-util"


def decode(packet):
    assert packet[:16] == b"#bundle\0" + struct.pack(">II", 0, 1)
    channels = {}
    offset = 16
    while offset < len(packet):
        size, = struct.unpack_from(">I", packet, offset)
        offset += 4
        message = packet[offset:offset + size]
        offset += size
        assert len(message) == size
        end = message.index(0)
        address = message[:end].decode("ascii")
        value_offset = (end + 4) & ~3
        assert message[value_offset:value_offset + 4] == b",f\0\0"
        assert len(message) == value_offset + 8
        value, = struct.unpack_from(">f", message, value_offset + 4)
        assert math.isfinite(value) and address not in channels
        channels[address] = value
    assert offset == len(packet)
    assert len(channels) == 42
    assert channels["/lcu/version"] == 1
    assert channels["/lcu/demo"] == 1
    for voice, midi, audio in [("moog", 1, 8), ("tetra", 2, 7)]:
        prefix = f"/lcu/{voice}/"
        assert channels[prefix + "midi_channel"] == midi
        assert channels[prefix + "input_channel"] == audio
        assert channels[prefix + "send"] in (0, 1)
        assert channels[prefix + "level_valid"] == 1
        assert channels[prefix + "latency_valid"] == 0
        assert channels[prefix + "latency_ms"] == -1
    return channels


def receiver(port=0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", port))
    sock.settimeout(0.15)
    return sock


def collect(sock, child, seconds):
    frames = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            packet = sock.recv(65536)
            frames.append((time.monotonic(), len(packet), decode(packet)))
        except socket.timeout:
            if child.poll() is not None:
                break
    return frames


def main():
    with receiver() as probe:
        port = probe.getsockname()[1]
    # No receiver at startup. The sender must survive ICMP port-unreachable errors.
    child = subprocess.Popen(
        [str(BIN), "--quarter-notes", "--demo", "--headless", "--seconds", "4",
         "--osc", f"127.0.0.1:{port}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        time.sleep(0.4)
        with receiver(port) as sock:
            first = collect(sock, child, 0.9)
        time.sleep(0.4)
        with receiver(port) as sock:
            second = collect(sock, child, 4)
        stdout, stderr = child.communicate(timeout=2)
        assert child.returncode == 0, stderr.decode()
        assert len(first) >= 15 and len(second) >= 40
        assert second[0][2]["/lcu/heartbeat"] > first[-1][2]["/lcu/heartbeat"] + 1
        assert all(f[2]["/lcu/moog/notes_sent"] == f[2]["/lcu/tetra/notes_sent"] == 0 for f in first)
        assert second[-1][2]["/lcu/moog/notes_sent"] > first[-1][2]["/lcu/moog/notes_sent"]
        frames = first + second
        for voice in ("moog", "tetra"):
            assert {f[2][f"/lcu/{voice}/send"] for f in frames} == {0, 1}
            assert second[-1][2][f"/lcu/{voice}/send"] == 0
        assert second[-1][2]["/lcu/running"] == 0
        assert json.loads(stdout)["voices"][0]["notes_sent"] == 5
        rate = (len(first) - 1) / (first[-1][0] - first[0][0])
        assert 25 <= rate <= 35, rate
        sizes = {f[1] for f in frames}
        assert len(sizes) == 1
        summary = {"frames_received": len(frames), "channels": len(frames[-1][2]),
                   "bytes_per_bundle": sizes.pop(), "observed_hz": round(rate, 2),
                   "receiver_absent_at_start": "passed", "receiver_restart": "passed",
                   "final_notes_off": "passed", "hardware_opened": False}
        (ROOT / "runs").mkdir(exist_ok=True)
        (ROOT / "runs/osc-demo-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


if __name__ == "__main__":
    main()
