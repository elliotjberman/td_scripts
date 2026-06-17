#!/bin/zsh
set -euo pipefail

script_dir="${0:A:h}"
repo_root="${script_dir:h}"
ghostty_app="/Applications/Ghostty.app"
dashboard_command="cd ${(q)repo_root} && exec ./live_set/live_set_dashboard.py --launch-stack"

if [[ -d "$ghostty_app" ]]; then
  /usr/bin/open -na "$ghostty_app" --args -e /bin/zsh -lc "$dashboard_command"
  exit 0
fi

/usr/bin/osascript <<APPLESCRIPT
tell application "Terminal"
  activate
  do script "cd " & quoted form of "$repo_root" & " && ./live_set/live_set_dashboard.py --launch-stack"
end tell
APPLESCRIPT
