#!/usr/bin/env python3
"""Ghostty-friendly live-set launch and heartbeat dashboard."""

from __future__ import annotations

import argparse
import curses
import os
from pathlib import Path
import signal
import subprocess
import sys

try:
    from live_set import launch_live_set
    from live_set.live_set_dashboard_data import (
        DEFAULT_CURRENT_SONG_FILE,
        check_url,
        current_setlist,
        current_song_slug,
        read_server_snapshot,
        request_setlist_server_load,
    )
    from live_set.live_set_dashboard_render import (
        configure_curses,
        current_setlist_index,
        read_dashboard_key,
        render,
        render_curses,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from live_set import launch_live_set
    from live_set.live_set_dashboard_data import (
        DEFAULT_CURRENT_SONG_FILE,
        check_url,
        current_setlist,
        current_song_slug,
        read_server_snapshot,
        request_setlist_server_load,
    )
    from live_set.live_set_dashboard_render import (
        configure_curses,
        current_setlist_index,
        read_dashboard_key,
        render,
        render_curses,
    )


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


def find_process(pattern: str) -> str:
    for command in (["pgrep", "-xlf", pattern], ["pgrep", "-fl", pattern]):
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return " ".join(result.stdout.splitlines()[0].split()[:3])
    return ""


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.default_int_handler)
    raise SystemExit(main())
