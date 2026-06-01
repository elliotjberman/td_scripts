from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ableton_utilities.hardware_tracks import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
