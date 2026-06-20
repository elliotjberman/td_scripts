"""Setlist and server data helpers for the live-set dashboard."""

from __future__ import annotations

import argparse
import csv
import json
import socket
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


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
LOAD_SET_TIMEOUT_SECONDS = 10.0


def check_url(url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=0.8) as response:
            if 200 <= response.status < 400:
                return True, f"HTTP {response.status}"
            return False, f"HTTP {response.status}"
    except (urllib.error.URLError, TimeoutError) as exc:
        detail = exc.reason if isinstance(exc, urllib.error.URLError) else exc
        return False, str(detail)


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
        path = Path(configured).expanduser().resolve()
        return path if path.exists() else None
    for path in DEFAULT_SETLIST_FILES:
        if path.exists():
            return path
    return None


def setlist_from_status(data: object) -> list[dict[str, str]]:
    return setlist_from_value(data)


def setlist_from_value(
    value: object,
    base_path: str = "",
    config_dir: Path | None = None,
) -> list[dict[str, str]]:
    if isinstance(value, dict):
        base_path = base_path_from_mapping(value, base_path, config_dir)
        return setlist_from_value(value.get("sets"), base_path, config_dir)
    if isinstance(value, list):
        rows = []
        for index, item in enumerate(value, start=1):
            row = setlist_row(item, index, base_path)
            if row["slug"] or row["name"]:
                rows.append(row)
        return rows
    return []


def setlist_row(item: object, index: int, base_path: str = "") -> dict[str, str]:
    if isinstance(item, str):
        return setlist_path_row(item, index, base_path)
    if not isinstance(item, dict):
        return setlist_path_row(str(item), index, base_path)

    path_text = first_text(item, ("path", "ableton_path", "ableton_set"))
    name = first_text(item, ("name", "song_name", "title", "slug")) or path_text
    display = display_name_from_value(name)
    slug = parse_song_slug(item.get("slug") or display)
    return {
        "index": str(item.get("index") or index),
        "slug": slug,
        "name": display,
        "interlude": str(item.get("interlude") or ""),
        "ableton_path": resolve_set_path(path_text, base_path),
    }


def setlist_path_row(path_text: str, index: int, base_path: str = "") -> dict[str, str]:
    display = display_name_from_value(path_text)
    return {
        "index": str(index),
        "slug": parse_song_slug(display),
        "name": display,
        "interlude": "",
        "ableton_path": resolve_set_path(path_text, base_path),
    }


def base_path_from_mapping(
    data: dict[str, object],
    fallback: str = "",
    config_dir: Path | None = None,
) -> str:
    base_path = str(data.get("basePath") or "").strip()
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
    if not isinstance(data, dict):
        return parse_song_slug(data)
    current_index = current_index_from_status(data)
    if current_index is not None and 0 <= current_index < len(setlist):
        return setlist[current_index]["slug"]
    current_path = data.get("current_path")
    if current_path:
        return parse_song_slug(display_name_from_value(current_path))
    return ""


def current_index_from_status(data: dict[str, object]) -> int | None:
    value = data.get("current_index")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
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
