#!/usr/bin/env python3
"""Ghostty-friendly live-set launch and heartbeat dashboard."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

try:
    from live_set import launch_live_set
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from live_set import launch_live_set


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CURRENT_SONG_FILE = Path("/tmp/td_live_set_song_slug")
DEFAULT_SETLIST_FILES = (
    Path.home() / "setlist_manager" / "setlist.json",
    Path.home() / "setlist_manager" / "current_setlist.json",
    Path.home() / "setlist_manager" / "live_set.json",
    REPO_ROOT.parent / "setlist_manager" / "setlist.json",
    REPO_ROOT / "live_set" / "setlist.json",
)
DEFAULT_STATUS_URLS = (
    "http://127.0.0.1:8000/status",
    "http://127.0.0.1:5000/status",
    "http://127.0.0.1:3000/status",
    "http://127.0.0.1:8765/status",
)
SPINNER = ("|", "/", "-", "\\")


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    server_proc: subprocess.Popen[bytes] | None = None
    launch_error = ""

    if args.launch_stack:
        try:
            server_proc = launch_stack(args)
        except launch_live_set.LaunchError as exc:
            launch_error = str(exc)

    try:
        run_dashboard(args, server_proc, launch_error)
    except KeyboardInterrupt:
        print("\nDashboard stopped. Live apps were left running.")
    return 0 if not launch_error else 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show live-set launch status and current setlist position.")
    parser.add_argument("--launch-stack", action="store_true", help="Start server, TouchDesigner, and Ableton.")
    parser.add_argument("--once", action="store_true", help="Render one dashboard frame and exit.")
    parser.add_argument("--interval", type=float, default=1.0, help="Refresh interval in seconds.")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors.")
    parser.add_argument(
        "--status-url",
        default=os.environ.get("LIVE_SET_STATUS_URL") or os.environ.get("LIVE_SET_SERVER_STATUS_URL"),
        help="Server status JSON URL. This is the primary source for setlist/current song.",
    )
    parser.add_argument(
        "--setlist-url",
        default=os.environ.get("LIVE_SET_SETLIST_URL"),
        help="Fallback JSON URL for the actual setlist when status JSON does not include it.",
    )
    parser.add_argument(
        "--setlist",
        default=os.environ.get("LIVE_SET_SETLIST", ""),
        help="Fallback setlist JSON/TSV file. Not used when server status provides a setlist.",
    )
    parser.add_argument("--current-song", default=os.environ.get("LIVE_SET_CURRENT_SONG"))
    parser.add_argument(
        "--current-song-file",
        default=os.environ.get("LIVE_SET_CURRENT_SONG_FILE", str(DEFAULT_CURRENT_SONG_FILE)),
        help="File containing the current song slug. Missing files are ignored.",
    )
    parser.add_argument(
        "--current-song-url",
        default=os.environ.get("LIVE_SET_CURRENT_SONG_URL"),
        help="Optional URL returning the current song as text or JSON.",
    )
    parser.add_argument(
        "--td-project",
        default=os.environ.get("LIVE_SET_TD_PROJECT", str(launch_live_set.DEFAULT_TD_PROJECT)),
    )
    parser.add_argument("--touchdesigner-app", default=os.environ.get("LIVE_SET_TOUCHDESIGNER_APP"))
    parser.add_argument("--ableton-set", default=os.environ.get("LIVE_SET_ABLETON_SET"))
    parser.add_argument("--ableton-app", default=os.environ.get("LIVE_SET_ABLETON_APP"))
    parser.add_argument("--server-command", default=os.environ.get("LIVE_SET_SERVER_COMMAND"))
    parser.add_argument("--server-cwd", default=os.environ.get("LIVE_SET_SERVER_CWD"))
    parser.add_argument("--server-ready-url", default=os.environ.get("LIVE_SET_SERVER_READY_URL"))
    parser.add_argument(
        "--server-host",
        default=os.environ.get("LIVE_SET_SERVER_HOST", launch_live_set.DEFAULT_SERVER_HOST),
    )
    parser.add_argument(
        "--server-wait",
        type=float,
        default=float(os.environ.get("LIVE_SET_SERVER_WAIT", "4")),
    )
    parser.add_argument(
        "--server-log",
        default=os.environ.get("LIVE_SET_SERVER_LOG", str(launch_live_set.DEFAULT_LOG)),
    )
    parser.add_argument("--skip-server", action="store_true")
    parser.add_argument("--skip-touchdesigner", action="store_true")
    parser.add_argument("--skip-ableton", action="store_true")
    parser.add_argument("--touchdesigner-process", default=os.environ.get("LIVE_SET_TD_PROCESS", "TouchDesigner"))
    parser.add_argument("--ableton-process", default=os.environ.get("LIVE_SET_ABLETON_PROCESS", "Ableton Live"))
    return parser.parse_args(argv)


def launch_stack(args: argparse.Namespace) -> subprocess.Popen[bytes] | None:
    td_project = launch_live_set.expand_path(args.td_project)
    ableton_set = launch_live_set.expand_path(args.ableton_set) if args.ableton_set else None
    server_cwd = launch_live_set.resolve_server_cwd(args.server_cwd)
    server_command = args.server_command or launch_live_set.infer_server_command(server_cwd)

    if not args.skip_touchdesigner:
        launch_live_set.require_file(td_project, "TouchDesigner project")
    if ableton_set is not None and not args.skip_ableton:
        launch_live_set.require_file(ableton_set, "Ableton set")

    server_proc: subprocess.Popen[bytes] | None = None
    if not args.skip_server:
        if not server_command:
            raise launch_live_set.LaunchError(
                "No server command configured. Pass --server-command or set LIVE_SET_SERVER_COMMAND.",
            )
        if not launch_live_set.server_is_ready(args.server_ready_url, server_cwd, args.server_host):
            server_proc = launch_live_set.start_server(
                server_command,
                server_cwd,
                launch_live_set.expand_path(args.server_log),
            )
            launch_live_set.wait_for_server(args.server_ready_url, args.server_wait, server_cwd, args.server_host)
            if server_proc.poll() is not None:
                raise launch_live_set.LaunchError(
                    f"Server exited early with code {server_proc.returncode}. Check {args.server_log}.",
                )

    if not args.skip_touchdesigner:
        td_app = args.touchdesigner_app or launch_live_set.detect_touchdesigner_app()
        launch_live_set.open_with_app(td_app, td_project)
    if not args.skip_ableton:
        ableton_app = args.ableton_app or launch_live_set.detect_ableton_app()
        launch_live_set.open_with_app(ableton_app, ableton_set)

    return server_proc


def run_dashboard(
    args: argparse.Namespace,
    server_proc: subprocess.Popen[bytes] | None,
    launch_error: str,
) -> None:
    frame = 0
    while True:
        server_snapshot = read_server_snapshot(args)
        setlist, setlist_source = current_setlist(args, server_snapshot)
        current_slug = current_song_slug(args, server_snapshot, setlist)
        statuses = [
            server_status(args, server_proc, server_snapshot),
            process_status("TouchDesigner", args.touchdesigner_process, args.skip_touchdesigner),
            process_status("Ableton", args.ableton_process, args.skip_ableton),
        ]
        render(frame, statuses, setlist, current_slug, setlist_source, launch_error, args.no_color)
        if args.once:
            return
        frame += 1
        time.sleep(max(args.interval, 0.1))


def server_status(
    args: argparse.Namespace,
    server_proc: subprocess.Popen[bytes] | None,
    server_snapshot: dict[str, object],
) -> dict[str, str]:
    if args.skip_server:
        return status("Server", "skip", "skipped")
    if server_proc is not None and server_proc.poll() is not None:
        return status("Server", "fail", f"exited {server_proc.returncode}")
    if server_snapshot.get("data") is not None:
        data = server_snapshot.get("data")
        if isinstance(data, dict) and data.get("ok") is False:
            detail = first_text(data, ("error", "message")) or f"status {server_snapshot.get('url')}"
            if is_default_server_port_notice(detail):
                port = data.get("serverPort") or launch_live_set.DEFAULT_SETLIST_SERVER_PORT
                return status("Server", "ok", f"default port {port}")
            return status("Server", "fail", detail)
        return status("Server", "ok", f"status {server_snapshot.get('url')}")
    if args.server_ready_url:
        ok, detail = check_url(args.server_ready_url)
        if ok:
            return status("Server", "ok", detail)
        if server_proc is not None:
            return status("Server", "wait", detail)
        return status("Server", "fail", detail)
    if server_proc is not None:
        detail = server_snapshot.get("error") or f"pid {server_proc.pid}"
        return status("Server", "wait", str(detail))
    detail = server_snapshot.get("error") or "status unavailable"
    return status("Server", "wait", str(detail))


def process_status(label: str, process_pattern: str, skipped: bool) -> dict[str, str]:
    if skipped:
        return status(label, "skip", "skipped")
    process = find_process(process_pattern)
    if process:
        return status(label, "ok", process)
    return status(label, "wait", f"waiting for {process_pattern}")


def status(resource: str, state: str, detail: str) -> dict[str, str]:
    return {"resource": resource, "state": state, "detail": detail}


def is_default_server_port_notice(detail: str) -> bool:
    return "serverPort missing" in detail


def check_url(url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=0.8) as response:
            if 200 <= response.status < 400:
                return True, f"HTTP {response.status}"
            return False, f"HTTP {response.status}"
    except (urllib.error.URLError, TimeoutError) as exc:
        detail = exc.reason if isinstance(exc, urllib.error.URLError) else exc
        return False, str(detail)


def find_process(pattern: str) -> str:
    for command in (["pgrep", "-xlf", pattern], ["pgrep", "-fl", pattern]):
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return " ".join(result.stdout.splitlines()[0].split()[:3])
    return ""


def current_song_slug(
    args: argparse.Namespace,
    server_snapshot: dict[str, object],
    setlist: list[dict[str, str]],
) -> str:
    slug = current_song_from_status(server_snapshot.get("data"), setlist)
    if slug:
        return slug
    for value in (
        args.current_song,
        read_current_song_url(args.current_song_url),
        read_current_song_file(args.current_song_file),
    ):
        slug = parse_song_slug(value)
        if slug:
            return slug
    return ""


def current_setlist(
    args: argparse.Namespace,
    server_snapshot: dict[str, object],
) -> tuple[list[dict[str, str]], str]:
    rows = setlist_from_status(server_snapshot.get("data"))
    if rows:
        return rows, f"server status {server_snapshot.get('url')}"
    if args.setlist_url:
        rows = read_setlist_url(args.setlist_url)
        if rows:
            return rows, args.setlist_url
    fallback = fallback_setlist_path(args.setlist)
    if fallback is not None:
        rows = read_setlist(fallback)
        if rows:
            return rows, str(fallback)
    if server_snapshot.get("url"):
        return [], f"server status {server_snapshot.get('url')}"
    return [], "server status"


def read_server_snapshot(args: argparse.Namespace) -> dict[str, object]:
    urls = status_urls(args)
    last_error = "no status URL configured"
    for url in urls:
        payload, error = read_json_url(url)
        if error:
            last_error = f"{url}: {error}"
            continue
        return {"url": url, "data": payload, "error": ""}
    return {"url": urls[0] if urls else "", "data": None, "error": last_error}


def status_urls(args: argparse.Namespace) -> list[str]:
    urls = []
    for url in (args.status_url, args.server_ready_url, *DEFAULT_STATUS_URLS):
        if url and url not in urls:
            urls.append(url)
    return urls


def read_json_url(url: str) -> tuple[object | None, str]:
    try:
        with urllib.request.urlopen(url, timeout=0.8) as response:
            payload = response.read().decode("utf-8", errors="replace").strip()
            if not 200 <= response.status < 400:
                return None, f"HTTP {response.status}"
    except (urllib.error.URLError, TimeoutError) as exc:
        detail = exc.reason if isinstance(exc, urllib.error.URLError) else exc
        return None, str(detail)
    if not payload:
        return None, "empty response"
    try:
        return json.loads(payload), ""
    except json.JSONDecodeError:
        return None, "response was not JSON"


def read_current_song_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        with urllib.request.urlopen(url, timeout=0.8) as response:
            payload = response.read().decode("utf-8", errors="replace").strip()
    except (urllib.error.URLError, TimeoutError):
        return ""
    if not payload:
        return ""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return payload
    if not isinstance(data, dict):
        return str(data)
    for key in ("song_slug", "slug", "song", "song_name", "current_song", "name"):
        value = data.get(key)
        if value:
            return str(value)
    return ""


def read_current_song_file(path_text: str | None) -> str:
    if not path_text:
        return ""
    path = Path(path_text).expanduser()
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def read_setlist(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".json":
        return read_setlist_json(path)
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file, delimiter="\t")
        rows = []
        for index, row in enumerate(reader, start=1):
            song_name = row.get("song_name") or row.get("song") or row.get("slug") or ""
            slug = parse_song_slug(song_name)
            rows.append({"index": str(index), "slug": slug, "name": song_name or slug})
        return rows


def read_setlist_json(path: Path) -> list[dict[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return setlist_from_value(data)


def read_setlist_url(url: str) -> list[dict[str, str]]:
    data, error = read_json_url(url)
    if error:
        return []
    return setlist_from_value(data)


def fallback_setlist_path(configured: str) -> Path | None:
    if configured:
        path = launch_live_set.expand_path(configured)
        return path if path.exists() else None
    for path in DEFAULT_SETLIST_FILES:
        if path.exists():
            return path
    return None


def setlist_from_status(data: object) -> list[dict[str, str]]:
    if data is None:
        return []
    if isinstance(data, list):
        return setlist_from_value(data)
    if not isinstance(data, dict):
        return []
    for key in ("setlist", "live_set", "liveSet", "sets", "queue", "songs", "tracks", "items"):
        rows = setlist_from_value(data.get(key))
        if rows:
            return rows
    for key in ("status", "state", "show"):
        rows = setlist_from_status(data.get(key))
        if rows:
            return rows
    return []


def setlist_from_value(value: object) -> list[dict[str, str]]:
    if value is None:
        return []
    if isinstance(value, dict):
        for key in ("sets", "songs", "tracks", "items", "setlist", "entries"):
            rows = setlist_from_value(value.get(key))
            if rows:
                return rows
        return []
    if not isinstance(value, list):
        return []
    rows = []
    for index, item in enumerate(value, start=1):
        row = setlist_row(item, index)
        if row["slug"] or row["name"]:
            rows.append(row)
    return rows


def setlist_row(item: object, index: int) -> dict[str, str]:
    if isinstance(item, str):
        slug = parse_song_slug(item)
        return {"index": str(index), "slug": slug, "name": item, "interlude": ""}
    if not isinstance(item, dict):
        text = str(item)
        return {"index": str(index), "slug": parse_song_slug(text), "name": text, "interlude": ""}

    song = item.get("song")
    merged = dict(item)
    if isinstance(song, dict):
        merged.update({key: value for key, value in song.items() if key not in merged})
    elif isinstance(song, str) and not merged.get("name"):
        merged["name"] = song

    name = first_text(
        merged,
        ("display_name", "displayName", "title", "name", "song_name", "songName", "label", "path"),
    )
    slug = first_text(merged, ("slug", "song_slug", "songSlug", "key"))
    if not slug:
        slug = name
    display = display_name_from_value(name or slug)
    row_index = first_text(merged, ("position", "order", "index", "scene", "scene_number", "sceneNumber")) or str(index)
    interlude = first_text(
        merged,
        (
            "interlude",
            "interlude_name",
            "interludeName",
            "between",
            "between_song",
            "betweenSong",
            "transition",
            "transition_name",
            "transitionName",
        ),
    )
    return {
        "index": str(row_index),
        "slug": parse_song_slug(display_name_from_value(slug)),
        "name": str(display),
        "interlude": interlude,
    }


def current_song_from_status(data: object, setlist: list[dict[str, str]]) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return parse_song_slug(data)
    if isinstance(data, list):
        return ""
    if not isinstance(data, dict):
        return parse_song_slug(data)

    for key in (
        "current_song",
        "currentSong",
        "active_song",
        "activeSong",
        "selected_song",
        "selectedSong",
        "now_playing",
        "nowPlaying",
        "current",
        "current_path",
        "currentPath",
    ):
        slug = slug_from_song_value(data.get(key))
        if slug:
            return slug
    index = current_index_from_status(data)
    if index is not None and 0 <= index < len(setlist):
        return setlist[index]["slug"]
    for key in ("status", "state", "show", "playback"):
        slug = current_song_from_status(data.get(key), setlist)
        if slug:
            return slug
    return ""


def slug_from_song_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return parse_song_slug(
            first_text(value, ("slug", "song_slug", "songSlug", "key", "name", "song_name", "songName", "title", "path")),
        )
    return parse_song_slug(display_name_from_value(value))


def current_index_from_status(data: dict[str, object]) -> int | None:
    for key in ("current_index", "currentIndex", "selected_index", "selectedIndex", "song_index", "songIndex"):
        value = data.get(key)
        if value is None:
            continue
        try:
            index = int(value)
        except (TypeError, ValueError):
            continue
        return index
    return None


def first_text(data: dict[str, object], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return ""


def parse_song_slug(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    marker = "[td:"
    marker_start = text.find(marker)
    if marker_start >= 0:
        marker_end = text.find("]", marker_start)
        if marker_end >= 0:
            return normalize_song_slug(text[marker_start + len(marker):marker_end])
    if text.startswith("td:"):
        return normalize_song_slug(text[3:])
    return normalize_song_slug(text)


def normalize_song_slug(value: object) -> str:
    text = str(value).strip().lower()
    return "_".join(text.split())


def display_name_from_value(value: object) -> str:
    text = str(value).strip()
    if not text:
        return ""
    path = Path(text.replace("\\", "/"))
    name = path.name or text
    if name.endswith(".als"):
        name = name[:-4]
    return name


def render(
    frame: int,
    statuses: list[dict[str, str]],
    setlist: list[dict[str, str]],
    current_slug: str,
    setlist_source: str,
    launch_error: str,
    no_color: bool,
) -> None:
    sys.stdout.write("\033[2J\033[H")
    heartbeat = SPINNER[frame % len(SPINNER)]
    print(colorize(f"LIVE SET CONTROL {heartbeat}", Color.BOLD + Color.CYAN, no_color))
    print(time.strftime("%Y-%m-%d %H:%M:%S"))
    if launch_error:
        print(colorize(f"Launch warning: {launch_error}", Color.RED, no_color))
    print()
    print_resource_table(statuses, no_color)
    print()
    print_setlist_table(setlist, current_slug, setlist_source, no_color)
    sys.stdout.flush()


def print_resource_table(statuses: list[dict[str, str]], no_color: bool) -> None:
    rows = []
    for item in statuses:
        label, color = state_label(item["state"])
        rows.append((item["resource"], colorize(label, color, no_color), item["detail"]))
    print_table(("Resource", "Beat", "Detail"), rows)


def print_setlist_table(
    setlist: list[dict[str, str]],
    current_slug: str,
    setlist_source: str,
    no_color: bool,
) -> None:
    rows = []
    current_index = current_setlist_index(setlist, current_slug)
    for index, song in enumerate(setlist):
        marker = " "
        state = ""
        row_color = ""
        if current_index is not None and index == current_index:
            marker = ">"
            state = "NOW"
            row_color = Color.GREEN
        elif current_index is not None and index < current_index:
            state = "done"
            row_color = Color.DIM
        elif current_index is not None:
            state = "next"
        values = (marker, song["index"], song["name"], state)
        rows.append(tuple(colorize(value, row_color, no_color) for value in values))
        interlude = song.get("interlude", "")
        if interlude:
            interlude_values = ("", "", f"  interlude: {interlude}", "")
            rows.append(tuple(colorize(value, Color.DIM, no_color) for value in interlude_values))

    if not rows:
        print(colorize(f"No actual setlist rows found from {setlist_source}.", Color.YELLOW, no_color))
        return
    print(colorize(f"Setlist source: {setlist_source}", Color.DIM, no_color))
    if not current_slug:
        print(colorize("Current song: unknown", Color.YELLOW, no_color))
    elif current_index is None:
        print(colorize(f"Current song {current_slug!r} is not in the setlist.", Color.YELLOW, no_color))
    else:
        print(colorize(f"Current song: {current_slug}", Color.GREEN, no_color))
    print_table(("", "#", "Song", "State"), rows)


def current_setlist_index(setlist: list[dict[str, str]], current_slug: str) -> int | None:
    if not current_slug:
        return None
    for index, song in enumerate(setlist):
        if song["slug"] == current_slug:
            return index
    return None


def state_label(state: str) -> tuple[str, str]:
    if state == "ok":
        return "[ OK ]", Color.GREEN
    if state == "fail":
        return "[FAIL]", Color.RED
    if state == "skip":
        return "[SKIP]", Color.DIM
    return "[WAIT]", Color.YELLOW


def print_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    widths = [len(strip_ansi(header)) for header in headers]
    for row in rows:
        widths = [max(width, len(strip_ansi(value))) for width, value in zip(widths, row)]
    divider = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
    print(divider)
    print("| " + " | ".join(header.ljust(width) for header, width in zip(headers, widths)) + " |")
    print(divider)
    for row in rows:
        print("| " + " | ".join(pad_ansi(value, width) for value, width in zip(row, widths)) + " |")
    print(divider)


def pad_ansi(value: str, width: int) -> str:
    return value + " " * max(width - len(strip_ansi(value)), 0)


def strip_ansi(value: str) -> str:
    output = []
    index = 0
    while index < len(value):
        if value[index:index + 2] == "\033[":
            index += 2
            while index < len(value) and value[index] != "m":
                index += 1
            index += 1
        else:
            output.append(value[index])
            index += 1
    return "".join(output)


def colorize(value: object, color: str, no_color: bool) -> str:
    text = str(value)
    if no_color or not color:
        return text
    return f"{color}{text}{Color.RESET}"


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.default_int_handler)
    raise SystemExit(main())
