#!/bin/zsh
set -euo pipefail

script_dir="${0:A:h}"
source_repo_root="${script_dir:h}"
runtime_repo_root="${LIVE_SET_TD_SCRIPTS_ROOT:-$HOME/td_scripts}"
if [[ ! -d "$runtime_repo_root" ]]; then
  runtime_repo_root="$source_repo_root"
fi

cd "$runtime_repo_root"
exec "$source_repo_root/live_set/live_set_dashboard.py" --once --no-color
