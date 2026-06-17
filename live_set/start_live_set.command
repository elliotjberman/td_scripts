#!/bin/zsh
set -euo pipefail

script_dir="${0:A:h}"
source_repo_root="${script_dir:h}"
runtime_repo_root="${LIVE_SET_TD_SCRIPTS_ROOT:-$HOME/td_scripts}"
if [[ ! -d "$runtime_repo_root" ]]; then
  runtime_repo_root="$source_repo_root"
fi
dashboard_script="$source_repo_root/live_set/live_set_dashboard.py"
dashboard_command="cd ${(q)runtime_repo_root} && exec ${(q)dashboard_script} --launch-stack"
terminal_app="${LIVE_SET_TERMINAL_APP:-auto}"

resolve_app() {
  local app="$1"
  local candidate

  if [[ "$app" == /* || "$app" == *.app ]]; then
    [[ -d "$app" ]] && print -r -- "$app"
    return
  fi

  for candidate in \
    "$HOME/Applications/${app}.app" \
    "/Applications/${app}.app" \
    "$HOME/Applications/$app" \
    "/Applications/$app"; do
    if [[ -d "$candidate" ]]; then
      print -r -- "$candidate"
      return
    fi
  done
}

app_key() {
  local base
  base="$(basename "$1" .app)"
  print -r -- "$(printf "%s" "$base" | tr "[:upper:]" "[:lower:]")"
}

open_terminal_app() {
  /usr/bin/osascript <<APPLESCRIPT
tell application "Terminal"
  activate
  do script "cd " & quoted form of "$runtime_repo_root" & " && exec " & quoted form of "$dashboard_script" & " --launch-stack"
end tell
APPLESCRIPT
}

open_ghostty() {
  /usr/bin/open -na "$1" --args -e /bin/zsh -lc "$dashboard_command"
}

open_wezterm() {
  /usr/bin/open -na "$1" --args start -- /bin/zsh -lc "$dashboard_command"
}

open_supported_terminal() {
  local app="$1"
  case "$(app_key "$app")" in
    ghostty)
      open_ghostty "$app"
      ;;
    wezterm)
      open_wezterm "$app"
      ;;
    terminal)
      open_terminal_app
      ;;
    *)
      print -ru2 "No launch adapter for terminal app: $app"
      print -ru2 "Falling back to Terminal."
      open_terminal_app
      ;;
  esac
}

if [[ "$terminal_app" != "auto" ]]; then
  resolved_app="$(resolve_app "$terminal_app")"
  if [[ -n "$resolved_app" ]]; then
    open_supported_terminal "$resolved_app"
    exit 0
  fi
  print -ru2 "Terminal app not found: $terminal_app"
  print -ru2 "Falling back to Terminal."
  open_terminal_app
  exit 0
fi

for candidate in \
  "$HOME/Applications/Ghostty.app" \
  "/Applications/Ghostty.app" \
  "$HOME/Applications/WezTerm.app" \
  "/Applications/WezTerm.app"; do
  if [[ -d "$candidate" ]]; then
    open_supported_terminal "$candidate"
    exit 0
  fi
done

open_terminal_app
