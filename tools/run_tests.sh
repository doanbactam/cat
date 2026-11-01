#!/usr/bin/env bash
# Usage: tools/run_tests.sh [filter]
source "$(dirname "$0")/env.sh"
DIR="${PROJECT_DIR:-$PROJECT_ROOT}"
[ "${SKIP_IMPORT:-0}" = "1" ] || "$(dirname "$0")/godot_import.sh" "$DIR" >/dev/null 2>&1
flock -w 3600 /tmp/meocam_godot.lock timeout 900 "$GODOT_BIN" --headless --path "$DIR" --script res://tests/run_tests.gd -- "$@" </dev/null 2>&1 \
  | grep -vE "ALSA|audio_driver|All audio drivers|audio_server|^\s*at: (init_output|initialize)|^\s*$"
exit "${PIPESTATUS[0]}"
