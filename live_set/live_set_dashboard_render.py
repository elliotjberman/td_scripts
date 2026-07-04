"""Terminal rendering helpers for the live-set dashboard."""

from __future__ import annotations

import contextlib
import curses
from dataclasses import dataclass
import sys
import time


SPINNER = ("|", "/", "-", "\\")
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
        draw_curses_line(screen, row, line, width, no_color)


def draw_curses_line(screen: curses.window, row: int, line: list[Segment], width: int, no_color: bool) -> None:
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
        row_style = ""
        is_current = current_index is not None and index == current_index
        is_selected = selection_mode == "ableton" and selected_index is not None and index == selected_index
        if is_selected:
            marker = ">"
            row_style = "selected"
        if is_current:
            state = "NOW" if ableton_running else "last"
            if not is_selected:
                row_style = "current" if ableton_running else "last"
        elif current_index is not None and index < current_index:
            state = "done"
            if not is_selected:
                row_style = "dim"
        elif current_index is not None:
            state = "next"
        rows.append(tuple(cell(value, row_style) for value in (marker, song["index"], song["name"], state)))
        interlude = song.get("interlude", "")
        if interlude:
            interlude_style = "selected" if is_selected else "dim"
            rows.append(tuple(cell(value, interlude_style) for value in ("", "", f"  interlude: {interlude}", "")))

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
