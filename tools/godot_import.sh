#!/usr/bin/env bash
# Headless (re)import of all assets. Usage: tools/godot_import.sh [project_dir]
source "$(dirname "$0")/env.sh"
DIR="${1:-$PROJECT_ROOT}"
flock -w 3600 /tmp/meocam_godot.lock timeout 1800 "$GODOT_BIN" --headless --path "$DIR" --import </dev/null 2>&1 \
  | grep -vE "ALSA|audio_driver|All audio drivers|audio_server|^\s*$" \
  | tee /tmp/godot_import_last.log | grep -E "ERROR|WARNING|SCRIPT ERROR" | sort | uniq -c | sort -rn | head -60
echo "import done (full log: /tmp/godot_import_last.log)"
