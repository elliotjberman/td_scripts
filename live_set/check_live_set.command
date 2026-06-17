#!/bin/zsh
set -euo pipefail

script_dir="${0:A:h}"
repo_root="${script_dir:h}"

cd "$repo_root"
exec "$repo_root/live_set/live_set_dashboard.py" --once --no-color
