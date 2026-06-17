#!/usr/bin/env python3
"""Launch the TouchDesigner/Ableton live-set stack."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TD_PROJECT = REPO_ROOT / "big_kahuna" / "master_v2_no_tsv.toe"
DEFAULT_LOG = Path.home() / "Library" / "Logs" / "td_scripts" / "live_set_server.log"
DEFAULT_SERVER_DIRS = (
    Path.home() / "setlist_manager",
    Path.home() / "code" / "setlist_manager",
    Path.home() / "Documents" / "setlist_manager",
    REPO_ROOT.parent / "setlist_manager",
)


class LaunchError(RuntimeError):
    """Raised when the launcher cannot safely continue."""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run(args)
    except LaunchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the server, TouchDesigner project, and Ableton set for a live show.",
    )
    parser.add_argument(
        "--td-project",
        default=os.environ.get("LIVE_SET_TD_PROJECT", str(DEFAULT_TD_PROJECT)),
        help="TouchDesigner .toe project to open. Defaults to the repo master project.",
    )
    parser.add_argument(
        "--touchdesigner-app",
        default=os.environ.get("LIVE_SET_TOUCHDESIGNER_APP"),
        help="TouchDesigner app path or app name. Auto-detects /Applications/TouchDesigner.app.",
    )
    parser.add_argument(
        "--ableton-set",
        default=os.environ.get("LIVE_SET_ABLETON_SET"),
        help="Ableton .als file to open. If omitted, Ableton launches without a document.",
    )
    parser.add_argument(
        "--ableton-app",
        default=os.environ.get("LIVE_SET_ABLETON_APP"),
        help="Ableton app path or app name. Auto-detects installed Ableton Live apps.",
    )
    parser.add_argument(
        "--server-command",
        default=os.environ.get("LIVE_SET_SERVER_COMMAND"),
        help="Shell command used to start the setlist/server process.",
    )
    parser.add_argument(
        "--server-cwd",
        default=os.environ.get("LIVE_SET_SERVER_CWD"),
        help="Working directory for --server-command. Auto-detects ~/setlist_manager when present.",
    )
    parser.add_argument(
        "--server-ready-url",
        default=os.environ.get("LIVE_SET_SERVER_READY_URL"),
        help="Optional URL to poll before launching the apps, for example http://127.0.0.1:3000/health.",
    )
    parser.add_argument(
        "--server-wait",
        type=float,
        default=float(os.environ.get("LIVE_SET_SERVER_WAIT", "4")),
        help="Seconds to wait after starting the server when no ready URL is configured.",
    )
    parser.add_argument(
        "--server-log",
        default=os.environ.get("LIVE_SET_SERVER_LOG", str(DEFAULT_LOG)),
        help="File that receives server stdout/stderr.",
    )
    parser.add_argument("--skip-server", action="store_true", help="Do not start the server.")
    parser.add_argument("--skip-touchdesigner", action="store_true", help="Do not open TouchDesigner.")
    parser.add_argument("--skip-ableton", action="store_true", help="Do not open Ableton.")
    parser.add_argument("--dry-run", action="store_true", help="Print the launch plan without starting anything.")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    td_project = expand_path(args.td_project)
    ableton_set = expand_path(args.ableton_set) if args.ableton_set else None

    if not args.skip_touchdesigner:
        require_file(td_project, "TouchDesigner project")
    if ableton_set is not None and not args.skip_ableton:
        require_file(ableton_set, "Ableton set")

    td_app = args.touchdesigner_app or detect_touchdesigner_app()
    ableton_app = args.ableton_app or detect_ableton_app()
    server_cwd = resolve_server_cwd(args.server_cwd)
    server_command = args.server_command or infer_server_command(server_cwd)

    print("Launch plan:")
    if args.skip_server:
        print("  server: skipped")
    else:
        if not server_command:
            raise LaunchError(
                "No server command configured. Pass --server-command or set LIVE_SET_SERVER_COMMAND.",
            )
        cwd_label = str(server_cwd) if server_cwd else str(Path.cwd())
        print(f"  server: {server_command}  (cwd: {cwd_label})")

    print("  TouchDesigner:", "skipped" if args.skip_touchdesigner else f"{td_app} -> {td_project}")
    if args.skip_ableton:
        print("  Ableton: skipped")
    elif ableton_set is None:
        print(f"  Ableton: {ableton_app}")
    else:
        print(f"  Ableton: {ableton_app} -> {ableton_set}")

    if args.dry_run:
        return 0

    server_proc: subprocess.Popen[bytes] | None = None
    try:
        if not args.skip_server:
            server_proc = start_server(server_command, server_cwd, expand_path(args.server_log))
            wait_for_server(args.server_ready_url, args.server_wait)
            if server_proc.poll() is not None:
                raise LaunchError(
                    f"Server exited early with code {server_proc.returncode}. "
                    f"Check {expand_path(args.server_log)}.",
                )
        if not args.skip_touchdesigner:
            open_with_app(td_app, td_project)
        if not args.skip_ableton:
            open_with_app(ableton_app, ableton_set)
    except Exception:
        if server_proc is not None and server_proc.poll() is None:
            server_proc.terminate()
        raise

    print("Live-set stack launched.")
    if server_proc is not None:
        print(f"Server pid: {server_proc.pid}")
        print(f"Server log: {expand_path(args.server_log)}")
    return 0


def detect_touchdesigner_app() -> str:
    for candidate in (Path("/Applications/TouchDesigner.app"),):
        if candidate.exists():
            return str(candidate)
    return "TouchDesigner"


def detect_ableton_app() -> str:
    applications = Path("/Applications")
    candidates = sorted(applications.glob("Ableton Live*.app"), key=ableton_app_sort_key, reverse=True)
    if candidates:
        return str(candidates[0])
    return "Ableton Live"


def ableton_app_sort_key(app_path: Path) -> tuple[int, str]:
    version = 0
    for part in app_path.stem.split():
        if part.isdigit():
            version = int(part)
            break
    return version, app_path.name


def resolve_server_cwd(configured: str | None) -> Path | None:
    if configured:
        path = expand_path(configured)
        if not path.exists():
            raise LaunchError(f"Server working directory does not exist: {path}")
        if not path.is_dir():
            raise LaunchError(f"Server working directory is not a directory: {path}")
        return path
    for candidate in DEFAULT_SERVER_DIRS:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def infer_server_command(server_cwd: Path | None) -> str | None:
    if server_cwd is None:
        return None
    package_json = server_cwd / "package.json"
    if package_json.exists():
        try:
            scripts = json.loads(package_json.read_text(encoding="utf-8")).get("scripts", {})
        except json.JSONDecodeError as exc:
            raise LaunchError(f"Could not parse {package_json}: {exc}") from exc
        if "dev" in scripts:
            return "npm run dev"
        if "start" in scripts:
            return "npm start"
    for filename in ("server.py", "app.py", "main.py"):
        if (server_cwd / filename).exists():
            return f"python3 {filename}"
    return None


def start_server(command: str, cwd: Path | None, log_path: Path) -> subprocess.Popen[bytes]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log:
        header = f"\n--- live_set launch {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
        log.write(header.encode("utf-8"))
        log.flush()
        return subprocess.Popen(
            command,
            cwd=str(cwd) if cwd else None,
            shell=True,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def wait_for_server(ready_url: str | None, wait_seconds: float) -> None:
    if ready_url:
        deadline = time.monotonic() + wait_seconds
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(ready_url, timeout=1) as response:
                    if 200 <= response.status < 400:
                        return
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
            time.sleep(0.25)
        raise LaunchError(f"Server did not become ready at {ready_url}: {last_error}")
    if wait_seconds > 0:
        time.sleep(wait_seconds)


def open_with_app(app: str, target: Path | None) -> None:
    command = ["open", "-a", app]
    if target is not None:
        command.append(str(target))
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        target_label = f" with {target}" if target else ""
        raise LaunchError(f"Could not open {app}{target_label}: {exc}") from exc


def expand_path(value: str | os.PathLike[str]) -> Path:
    return Path(value).expanduser().resolve()


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise LaunchError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise LaunchError(f"{label} is not a file: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
