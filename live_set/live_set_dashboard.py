#!/usr/bin/env python3
"""Ghostty-friendly live-set launch and heartbeat dashboard."""

from __future__ import annotations

import argparse
import contextlib
import csv
import curses
from dataclasses import dataclass
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
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
LOAD_SET_TIMEOUT_SECONDS = 10.0
CURSES_GREEN = 1
CURSES_YELLOW = 2
CURSES_ORANGE = 3
CURSES_RED = 4
CURSES_CYAN = 5


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    ORANGE = "\033[38;5;208m"
    RED = "\033[31m"
    CYAN = "\033[36m"


@dataclass(frozen=True)
class Segment:
    text: str
    style: str = ""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    server_proc: subprocess.Popen[bytes] | None = None
    launch_error = ""
    launch_warnings: list[str] = []

    if args.launch_stack:
        try:
            server_proc, launch_warnings = launch_stack(args)
        except launch_live_set.LaunchError as exc:
            launch_error = str(exc)

    try:
        run_dashboard(args, server_proc, launch_error, launch_warnings)
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
        default=float(os.environ.get("LIVE_SET_SERVER_WAIT", "10")),
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


def launch_stack(
    args: argparse.Namespace,
) -> tuple[subprocess.Popen[bytes] | None, list[str]]:
    td_project = launch_live_set.expand_path(args.td_project)
    server_cwd = launch_live_set.resolve_server_cwd(args.server_cwd)
    ableton_set = launch_live_set.expand_path(args.ableton_set) if args.ableton_set else None
    server_command = args.server_command or launch_live_set.infer_server_command(server_cwd)

    if not args.skip_touchdesigner:
        launch_live_set.require_file(td_project, "TouchDesigner project")
    if ableton_set is not None and not args.skip_ableton:
        launch_live_set.require_file(ableton_set, "Ableton set")

    server_proc: subprocess.Popen[bytes] | None = None
    launch_warnings: list[str] = []
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
            try:
                launch_live_set.wait_for_server(args.server_ready_url, args.server_wait, server_cwd, args.server_host)
            except launch_live_set.LaunchError as exc:
                if server_proc.poll() is not None:
                    raise launch_live_set.LaunchError(
                        f"Server exited early with code {server_proc.returncode}. Check {args.server_log}.",
                    ) from exc
                launch_warnings.append(str(exc))
            if server_proc.poll() is not None:
                raise launch_live_set.LaunchError(
                    f"Server exited early with code {server_proc.returncode}. Check {args.server_log}.",
                )

    if not args.skip_touchdesigner:
        td_app = args.touchdesigner_app or launch_live_set.detect_touchdesigner_app()
        launch_live_set.open_with_app(td_app, td_project)
    if not args.skip_ableton and ableton_set is not None:
        ableton_app = args.ableton_app or launch_live_set.detect_ableton_app()
        launch_live_set.open_with_app(ableton_app, ableton_set)

    return server_proc, launch_warnings


def run_dashboard(
    args: argparse.Namespace,
    server_proc: subprocess.Popen[bytes] | None,
    launch_error: str,
    launch_warnings: list[str],
) -> None:
    if not args.once and sys.stdin.isatty():
        curses.wrapper(lambda screen: run_dashboard_loop(args, server_proc, launch_error, launch_warnings, screen))
        return
    run_dashboard_loop(args, server_proc, launch_error, launch_warnings, None)


def run_dashboard_loop(
    args: argparse.Namespace,
    server_proc: subprocess.Popen[bytes] | None,
    launch_error: str,
    launch_warnings: list[str],
    screen: curses.window | None,
) -> None:
    frame = 0
    selected_index: int | None = None
    selection_mode = ""
    keyboard_enabled = screen is not None
    configure_curses(screen, args.interval)

    while True:
        server_snapshot = read_server_snapshot(args)
        setlist = current_setlist(args, server_snapshot)[0]
        current_slug = current_song_slug(args, server_snapshot, setlist)
        selected_index = normalize_selection(selected_index, setlist, current_slug)
        statuses = [
            server_status(args, server_proc, server_snapshot),
            process_status("TouchDesigner", args.touchdesigner_process, args.skip_touchdesigner),
            process_status("Ableton", args.ableton_process, args.skip_ableton),
        ]
        actions = available_actions(args, statuses, selection_mode)
        launch_notice = visible_launch_notice(statuses, launch_error, launch_warnings)

        if screen is None:
            render(
                frame,
                statuses,
                setlist,
                current_slug,
                selected_index,
                selection_mode,
                launch_notice,
                actions,
                keyboard_enabled,
                args.no_color,
            )
        else:
            render_curses(
                screen,
                frame,
                statuses,
                setlist,
                current_slug,
                selected_index,
                selection_mode,
                launch_notice,
                actions,
                args.no_color,
            )

        if args.once:
            return
        key = read_dashboard_key(screen, max(args.interval, 0.1))
        if key:
            selected_index, selection_mode, should_quit = handle_dashboard_key(
                args,
                key,
                setlist,
                current_slug,
                selected_index,
                selection_mode,
                actions,
            )
            if should_quit:
                return
        frame += 1


def handle_dashboard_key(
    args: argparse.Namespace,
    key: str,
    setlist: list[dict[str, str]],
    current_slug: str,
    selected_index: int | None,
    selection_mode: str,
    actions: list[dict[str, str]],
) -> tuple[int | None, str, bool]:
    if selection_mode == "ableton":
        return handle_ableton_selection_key(args, key, setlist, selected_index, selection_mode)
    if key == "q":
        return selected_index, selection_mode, True
    action = action_for_key(actions, key)
    if action and action["resource"] == "AbletonSelect":
        return normalize_selection(selected_index, setlist, current_slug), "ableton", False
    if action:
        run_launch_action(args, action)
    return selected_index, selection_mode, False


def handle_ableton_selection_key(
    args: argparse.Namespace,
    key: str,
    setlist: list[dict[str, str]],
    selected_index: int | None,
    selection_mode: str,
) -> tuple[int | None, str, bool]:
    if key == "up":
        return move_selection(selected_index, setlist, -1), selection_mode, False
    if key == "down":
        return move_selection(selected_index, setlist, 1), selection_mode, False
    if key == "enter":
        action = ableton_launch_action(args, setlist, selected_index)
        if action is not None:
            run_launch_action(args, action)
            selection_mode = ""
        return selected_index, selection_mode, False
    if key == "escape":
        return selected_index, "", False
    if key == "q":
        return selected_index, selection_mode, True
    return selected_index, selection_mode, False


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


def configure_curses(screen: curses.window | None, interval: float) -> None:
    if screen is None:
        return
    screen.keypad(True)
    screen.timeout(int(max(interval, 0.1) * 1000))
    configure_curses_colors()
    with contextlib.suppress(curses.error):
        curses.curs_set(0)


def configure_curses_colors() -> None:
    if not curses.has_colors():
        return
    with contextlib.suppress(curses.error):
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(CURSES_GREEN, curses.COLOR_GREEN, -1)
        curses.init_pair(CURSES_YELLOW, curses.COLOR_YELLOW, -1)
        curses.init_pair(CURSES_ORANGE, 208 if curses.COLORS > 208 else curses.COLOR_YELLOW, -1)
        curses.init_pair(CURSES_RED, curses.COLOR_RED, -1)
        curses.init_pair(CURSES_CYAN, curses.COLOR_CYAN, -1)


def read_dashboard_key(screen: curses.window | None, timeout: float) -> str:
    if screen is None:
        time.sleep(timeout)
        return ""
    key = screen.getch()
    if key == -1:
        return ""
    if key == curses.KEY_UP:
        return "up"
    if key == curses.KEY_DOWN:
        return "down"
    if key in (curses.KEY_ENTER, 10, 13):
        return "enter"
    if key == 27:
        return "escape"
    if 0 <= key <= 255:
        return chr(key).lower()
    return ""


def normalize_selection(
    selected_index: int | None,
    setlist: list[dict[str, str]],
    current_slug: str,
) -> int | None:
    if not setlist:
        return None
    if selected_index is None:
        current_index = current_setlist_index(setlist, current_slug)
        return current_index if current_index is not None else 0
    return min(max(selected_index, 0), len(setlist) - 1)


def move_selection(
    selected_index: int | None,
    setlist: list[dict[str, str]],
    offset: int,
) -> int | None:
    if not setlist:
        return None
    base = selected_index if selected_index is not None else 0
    return (base + offset) % len(setlist)


def available_actions(
    args: argparse.Namespace,
    statuses: list[dict[str, str]],
    selection_mode: str,
) -> list[dict[str, str]]:
    by_resource = {item["resource"]: item for item in statuses}
    actions = []
    touchdesigner = by_resource.get("TouchDesigner")
    if touchdesigner and should_offer_launch(touchdesigner, args.skip_touchdesigner):
        td_project = launch_live_set.expand_path(args.td_project)
        actions.append(
            {
                "key": "t",
                "resource": "TouchDesigner",
                "label": "Launch TouchDesigner",
                "target": str(td_project),
                "target_label": td_project.name,
            },
        )
    ableton = by_resource.get("Ableton")
    if selection_mode != "ableton" and ableton and should_offer_launch(ableton, args.skip_ableton):
        actions.append(
            {
                "key": "a",
                "resource": "AbletonSelect",
                "label": "Select Ableton song",
                "target": "",
                "target_label": "",
            },
        )
    return actions


def should_offer_launch(status_item: dict[str, str], skipped: bool) -> bool:
    return not skipped and status_item["state"] in {"fail", "wait"}


def action_for_key(actions: list[dict[str, str]], key: str) -> dict[str, str] | None:
    for action in actions:
        if action["key"] == key:
            return action
    return None


def run_launch_action(args: argparse.Namespace, action: dict[str, str]) -> str:
    try:
        if action["resource"] == "TouchDesigner":
            return launch_touchdesigner(args, action.get("target", ""))
        if action["resource"] == "Ableton":
            return launch_ableton(args, action)
    except launch_live_set.LaunchError as exc:
        return f"{action['label']} failed: {exc}"
    return f"Unknown action: {action['label']}"


def ableton_launch_action(
    args: argparse.Namespace,
    setlist: list[dict[str, str]],
    selected_index: int | None,
) -> dict[str, str] | None:
    ableton_set = selected_ableton_set(args, setlist, selected_index)
    if ableton_set is None:
        return None
    return {
        "key": "enter",
        "resource": "Ableton",
        "label": "Launch Ableton",
        "target": str(ableton_set),
        "target_label": selected_song_label(setlist, selected_index) or ableton_set.name,
        "setlist_index": str(selected_index) if selected_index is not None else "",
    }


def launch_touchdesigner(args: argparse.Namespace, target: str) -> str:
    if find_process(args.touchdesigner_process):
        return "TouchDesigner is already running."
    td_project = launch_live_set.expand_path(target or args.td_project)
    launch_live_set.require_file(td_project, "TouchDesigner project")
    td_app = args.touchdesigner_app or launch_live_set.detect_touchdesigner_app()
    launch_live_set.open_with_app(td_app, td_project)
    return f"Launched TouchDesigner: {td_project.name}."


def launch_ableton(args: argparse.Namespace, action: dict[str, str]) -> str:
    target = action.get("target", "")
    target_label = action.get("target_label") or Path(target).stem or "selected set"
    setlist_index = parse_optional_int(action.get("setlist_index", ""))
    if setlist_index is not None:
        ok, reached, detail = request_setlist_server_load(args, {"index": setlist_index})
        if ok:
            return f"Requested Ableton via setlist server: {target_label}."
        if reached:
            raise launch_live_set.LaunchError(f"setlist server load failed: {detail}")

    ableton_set = launch_live_set.expand_path(target) if target else None
    if ableton_set is not None:
        if setlist_index is None:
            ok, reached, detail = request_setlist_server_load(args, {"path": str(ableton_set)})
            if ok:
                return f"Requested Ableton via setlist server: {target_label}."
            if reached:
                raise launch_live_set.LaunchError(f"setlist server load failed: {detail}")
        launch_live_set.require_file(ableton_set, "Ableton set")
    ableton_app = args.ableton_app or launch_live_set.detect_ableton_app()
    launch_live_set.open_with_app(ableton_app, ableton_set)
    if ableton_set is None:
        return "Launched Ableton."
    return f"Launched Ableton: {ableton_set.stem}."


def selected_ableton_set(
    args: argparse.Namespace,
    setlist: list[dict[str, str]],
    selected_index: int | None,
) -> Path | None:
    if selected_index is not None and 0 <= selected_index < len(setlist):
        ableton_path = setlist[selected_index].get("ableton_path", "")
        if ableton_path:
            return launch_live_set.expand_path(ableton_path)
    if args.ableton_set:
        return launch_live_set.expand_path(args.ableton_set)
    return None


def selected_song_label(setlist: list[dict[str, str]], selected_index: int | None) -> str:
    if selected_index is None or not 0 <= selected_index < len(setlist):
        return ""
    return setlist[selected_index].get("name", "")


def parse_optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def visible_launch_notice(
    statuses: list[dict[str, str]],
    launch_error: str,
    launch_warnings: list[str],
) -> str:
    if launch_error:
        return launch_error
    if not launch_warnings:
        return ""
    if any(item["resource"] == "Server" and item["state"] == "ok" for item in statuses):
        return ""
    return "; ".join(launch_warnings)


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


def load_set_urls(args: argparse.Namespace) -> list[str]:
    urls = []
    for url in status_urls(args):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        candidate = urllib.parse.urlunparse(
            parsed._replace(path="/load-set", params="", query="", fragment=""),
        )
        if candidate not in urls:
            urls.append(candidate)
    return urls


def request_setlist_server_load(args: argparse.Namespace, payload: dict[str, object]) -> tuple[bool, bool, str]:
    errors = []
    reached = False
    for url in load_set_urls(args):
        ok, did_reach, detail = post_json_url(url, payload)
        if ok:
            return True, True, ""
        if did_reach and "timed out" in detail:
            return False, True, f"{url}: {detail}"
        reached = reached or did_reach
        if detail:
            errors.append(f"{url}: {detail}")
    if errors:
        return False, reached, "; ".join(errors)
    return False, reached, "no setlist server load URL configured"


def post_json_url(url: str, payload: dict[str, object]) -> tuple[bool, bool, str]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=LOAD_SET_TIMEOUT_SECONDS) as response:
            response_body = response.read().decode("utf-8", errors="replace").strip()
            if not 200 <= response.status < 400:
                return False, True, http_error_detail(response.status, response_body)
            if not response_body:
                return True, True, ""
            try:
                data = json.loads(response_body)
            except json.JSONDecodeError:
                return True, True, ""
            if isinstance(data, dict) and data.get("ok") is False:
                return False, True, first_text(data, ("error", "message")) or f"HTTP {response.status}"
            return True, True, ""
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace").strip()
        return False, True, http_error_detail(exc.code, response_body)
    except socket.timeout:
        return False, True, "timed out waiting for setlist server response"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        detail = exc.reason if isinstance(exc, urllib.error.URLError) else exc
        return False, False, str(detail)


def http_error_detail(status_code: int, response_body: str) -> str:
    if response_body:
        try:
            data = json.loads(response_body)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            detail = first_text(data, ("error", "message"))
            if detail:
                return detail
        return f"HTTP {status_code}: {response_body}"
    return f"HTTP {status_code}"


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
            ableton_path = row.get("ableton_path") or row.get("ableton_set") or row.get("path") or ""
            slug = parse_song_slug(song_name)
            rows.append(
                {
                    "index": str(index),
                    "slug": slug,
                    "name": song_name or slug,
                    "interlude": row.get("interlude", ""),
                    "ableton_path": ableton_path,
                },
            )
        return rows


def read_setlist_json(path: Path) -> list[dict[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return setlist_from_value(data, "", path.parent)


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


def setlist_from_status(data: object, base_path: str = "") -> list[dict[str, str]]:
    if data is None:
        return []
    if isinstance(data, list):
        return setlist_from_value(data, base_path)
    if not isinstance(data, dict):
        return []
    base_path = base_path_from_mapping(data, base_path)
    for key in ("setlist", "live_set", "liveSet", "sets", "queue", "songs", "tracks", "items"):
        rows = setlist_from_value(data.get(key), base_path)
        if rows:
            return rows
    for key in ("status", "state", "show"):
        rows = setlist_from_status(data.get(key), base_path)
        if rows:
            return rows
    return []


def setlist_from_value(
    value: object,
    base_path: str = "",
    config_dir: Path | None = None,
) -> list[dict[str, str]]:
    if value is None:
        return []
    if isinstance(value, dict):
        base_path = base_path_from_mapping(value, base_path, config_dir)
        for key in ("sets", "songs", "tracks", "items", "setlist", "entries"):
            rows = setlist_from_value(value.get(key), base_path, config_dir)
            if rows:
                return rows
        return []
    if not isinstance(value, list):
        return []
    rows = []
    for index, item in enumerate(value, start=1):
        row = setlist_row(item, index, base_path)
        if row["slug"] or row["name"]:
            rows.append(row)
    return rows


def setlist_row(item: object, index: int, base_path: str = "") -> dict[str, str]:
    if isinstance(item, str):
        slug = parse_song_slug(item)
        return {"index": str(index), "slug": slug, "name": item, "interlude": "", "ableton_path": ""}
    if not isinstance(item, dict):
        text = str(item)
        return {"index": str(index), "slug": parse_song_slug(text), "name": text, "interlude": "", "ableton_path": ""}

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
    ableton_path = resolve_set_path(
        first_text(
            merged,
            ("ableton_path", "abletonPath", "ableton_set", "abletonSet", "als_path", "alsPath", "path", "file"),
        ),
        base_path,
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
        "ableton_path": ableton_path,
    }


def base_path_from_mapping(
    data: dict[str, object],
    fallback: str = "",
    config_dir: Path | None = None,
) -> str:
    base_path = first_text(data, ("basePath", "base_path", "root", "rootPath"))
    if not base_path:
        return fallback
    path = Path(base_path).expanduser()
    if not path.is_absolute() and config_dir is not None:
        path = config_dir / path
    return str(path.resolve())


def resolve_set_path(path_text: str, base_path: str = "") -> str:
    if not path_text:
        return ""
    path = Path(path_text).expanduser()
    if path.is_absolute() or not base_path:
        return str(path.resolve())
    return str((Path(base_path).expanduser() / path).resolve())


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
    selected_index: int | None,
    selection_mode: str,
    launch_error: str,
    actions: list[dict[str, str]],
    keyboard_enabled: bool,
    no_color: bool,
) -> None:
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.write(
        render_text(
            frame,
            statuses,
            setlist,
            current_slug,
            selected_index,
            selection_mode,
            launch_error,
            actions,
            keyboard_enabled,
            no_color,
        ),
    )
    sys.stdout.flush()


def render_curses(
    screen: curses.window,
    frame: int,
    statuses: list[dict[str, str]],
    setlist: list[dict[str, str]],
    current_slug: str,
    selected_index: int | None,
    selection_mode: str,
    launch_error: str,
    actions: list[dict[str, str]],
    no_color: bool,
) -> None:
    lines = build_dashboard_lines(
        frame,
        statuses,
        setlist,
        current_slug,
        selected_index,
        selection_mode,
        launch_error,
        actions,
        True,
    )
    screen.erase()
    draw_curses_lines(screen, lines, no_color)
    screen.refresh()


def draw_curses_lines(screen: curses.window, lines: list[list[Segment]], no_color: bool) -> None:
    height, width = screen.getmaxyx()
    for row, line in enumerate(lines):
        if row >= height:
            break
        draw_curses_line(screen, row, line, width)


def draw_curses_line(screen: curses.window, row: int, line: list[Segment], width: int) -> None:
    column = 0
    for segment in line:
        attr = curses_attr_for_style(segment.style, no_color)
        column = add_curses_segment(screen, row, column, segment.text, width, attr)


def add_curses_segment(
    screen: curses.window,
    row: int,
    column: int,
    segment: str,
    width: int,
    attr: int,
) -> int:
    if not segment or column >= width - 1:
        return column
    available = max(width - column - 1, 0)
    with contextlib.suppress(curses.error):
        screen.addnstr(row, column, segment, available, attr)
    return column + min(len(segment), available)


def curses_attr_for_style(style: str, no_color: bool) -> int:
    if not style:
        return 0
    if no_color or not curses.has_colors():
        if style == "title":
            return curses.A_BOLD
        if style in {"dim", "last", "skip"}:
            return curses.A_DIM
        if style == "selected":
            return curses.A_BOLD
        return 0
    return {
        "title": curses.A_BOLD | curses.color_pair(CURSES_CYAN),
        "ok": curses.color_pair(CURSES_GREEN),
        "current": curses.color_pair(CURSES_GREEN),
        "wait": curses.color_pair(CURSES_YELLOW),
        "warn": curses.color_pair(CURSES_YELLOW),
        "selected": curses.A_BOLD | curses.color_pair(CURSES_ORANGE),
        "fail": curses.color_pair(CURSES_RED),
        "error": curses.color_pair(CURSES_RED),
        "notice": curses.color_pair(CURSES_CYAN),
        "dim": curses.A_DIM,
        "last": curses.A_DIM,
        "skip": curses.A_DIM,
    }.get(style, 0)


def render_text(
    frame: int,
    statuses: list[dict[str, str]],
    setlist: list[dict[str, str]],
    current_slug: str,
    selected_index: int | None,
    selection_mode: str,
    launch_error: str,
    actions: list[dict[str, str]],
    keyboard_enabled: bool,
    no_color: bool,
) -> str:
    lines = build_dashboard_lines(
        frame,
        statuses,
        setlist,
        current_slug,
        selected_index,
        selection_mode,
        launch_error,
        actions,
        keyboard_enabled,
    )
    return "\n".join(render_ansi_line(line, no_color) for line in lines) + "\n"


def build_dashboard_lines(
    frame: int,
    statuses: list[dict[str, str]],
    setlist: list[dict[str, str]],
    current_slug: str,
    selected_index: int | None,
    selection_mode: str,
    launch_error: str,
    actions: list[dict[str, str]],
    keyboard_enabled: bool,
) -> list[list[Segment]]:
    heartbeat = SPINNER[frame % len(SPINNER)]
    lines = [
        text_line(f"LIVE SET CONTROL {heartbeat}", "title"),
        text_line(time.strftime("%Y-%m-%d %H:%M:%S")),
    ]
    if launch_error:
        lines.append(text_line(f"Launch warning: {launch_error}", "error"))
    lines.append([])
    lines.extend(resource_table_lines(statuses))
    lines.append([])
    ableton_state = resource_state(statuses, "Ableton")
    lines.extend(setlist_table_lines(setlist, current_slug, selected_index, selection_mode, ableton_state))
    lines.extend(action_table_lines(actions, selection_mode, keyboard_enabled))
    return lines


def resource_table_lines(statuses: list[dict[str, str]]) -> list[list[Segment]]:
    rows = []
    for item in statuses:
        label, style = state_label(item["state"])
        rows.append((cell(item["resource"]), cell(label, style), cell(item["detail"])))
    return table_lines(("Resource", "Beat", "Detail"), rows)


def action_table_lines(
    actions: list[dict[str, str]],
    selection_mode: str,
    keyboard_enabled: bool,
) -> list[list[Segment]]:
    rows = []
    if keyboard_enabled:
        if selection_mode == "ableton":
            rows.append((cell("Up/Down"), cell("Select Ableton song")))
            rows.append((cell("Enter"), cell("Launch selected song")))
            rows.append((cell("[q]"), cell("Quit dashboard")))
        else:
            for action in actions:
                label = action["label"]
                target_label = action.get("target_label", "")
                if target_label:
                    label = f"{label}: {target_label}"
                rows.append((cell(f"[{action['key']}]"), cell(label)))
            rows.append((cell("[q]"), cell("Quit dashboard")))
    if not rows:
        return []
    lines = [[]]
    lines.extend(table_lines(("Key", "Action"), rows))
    return lines


def setlist_table_lines(
    setlist: list[dict[str, str]],
    current_slug: str,
    selected_index: int | None,
    selection_mode: str,
    ableton_state: str,
) -> list[list[Segment]]:
    rows = []
    current_index = current_setlist_index(setlist, current_slug)
    ableton_running = ableton_state == "ok"
    for index, song in enumerate(setlist):
        marker = " "
        state = ""
        row_color = ""
        is_current = current_index is not None and index == current_index
        is_selected = selection_mode == "ableton" and selected_index is not None and index == selected_index
        if is_selected:
            marker = ">"
            row_color = "selected"
        if is_current:
            state = "NOW" if ableton_running else "last"
            if not is_selected:
                row_color = "current" if ableton_running else "last"
        elif current_index is not None and index < current_index:
            state = "done"
            if not is_selected:
                row_color = "dim"
        elif current_index is not None:
            state = "next"
        values = (marker, song["index"], song["name"], state)
        rows.append(tuple(cell(value, row_color) for value in values))
        interlude = song.get("interlude", "")
        if interlude:
            interlude_values = ("", "", f"  interlude: {interlude}", "")
            interlude_style = "selected" if is_selected else "dim"
            rows.append(tuple(cell(value, interlude_style) for value in interlude_values))

    if not rows:
        return [text_line("No actual setlist rows found.", "warn")]
    lines = []
    if current_slug and current_index is None:
        label = "Current song" if ableton_running else "Last open song"
        lines.append(text_line(f"{label} {current_slug!r} is not in the setlist.", "warn"))
    lines.extend(table_lines(("", "#", "Song", "State"), rows))
    return lines


def current_setlist_index(setlist: list[dict[str, str]], current_slug: str) -> int | None:
    if not current_slug:
        return None
    for index, song in enumerate(setlist):
        if song["slug"] == current_slug:
            return index
    return None


def resource_state(statuses: list[dict[str, str]], resource: str) -> str:
    for item in statuses:
        if item["resource"] == resource:
            return item["state"]
    return ""


def state_label(state: str) -> tuple[str, str]:
    if state == "ok":
        return "[ OK ]", "ok"
    if state == "fail":
        return "[FAIL]", "fail"
    if state == "skip":
        return "[SKIP]", "skip"
    return "[WAIT]", "wait"


def text_line(text: object = "", style: str = "") -> list[Segment]:
    return [cell(text, style)] if text != "" else []


def cell(value: object, style: str = "") -> Segment:
    return Segment(str(value), style)


def table_lines(headers: tuple[str, ...], rows: list[tuple[Segment, ...]]) -> list[list[Segment]]:
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(value.text)) for width, value in zip(widths, row)]
    divider = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
    lines = [
        text_line(divider),
        table_row_line(tuple(cell(header) for header in headers), widths),
        text_line(divider),
    ]
    for row in rows:
        lines.append(table_row_line(row, widths))
    lines.append(text_line(divider))
    return lines


def table_row_line(row: tuple[Segment, ...], widths: list[int]) -> list[Segment]:
    line = [Segment("| ")]
    for index, (value, width) in enumerate(zip(row, widths)):
        if index:
            line.append(Segment(" | "))
        line.append(Segment(value.text + " " * max(width - len(value.text), 0), value.style))
    line.append(Segment(" |"))
    return line


def render_ansi_line(line: list[Segment], no_color: bool) -> str:
    return "".join(render_ansi_segment(segment, no_color) for segment in line)


def render_ansi_segment(segment: Segment, no_color: bool) -> str:
    if no_color or not segment.style:
        return segment.text
    prefix = ansi_style(segment.style)
    if not prefix:
        return segment.text
    return f"{prefix}{segment.text}{Color.RESET}"


def ansi_style(style: str) -> str:
    return {
        "title": Color.BOLD + Color.CYAN,
        "ok": Color.GREEN,
        "current": Color.GREEN,
        "wait": Color.YELLOW,
        "warn": Color.YELLOW,
        "selected": Color.ORANGE,
        "fail": Color.RED,
        "error": Color.RED,
        "notice": Color.CYAN,
        "dim": Color.DIM,
        "last": Color.DIM,
        "skip": Color.DIM,
    }.get(style, "")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.default_int_handler)
    raise SystemExit(main())
