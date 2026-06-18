"""Command-line wrapper for Windows-to-Mac plugin reference migration."""

from __future__ import annotations

from ableton_file_utilities.plugins.migration.windows_plugins import main


if __name__ == "__main__":
    raise SystemExit(main())
