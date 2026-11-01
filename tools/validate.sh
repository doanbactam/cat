#!/usr/bin/env bash
# Loads every .gd/.tscn/.tres/.glb in the project and reports parse/load errors.
# Exit code != 0 when any error is found. Usage: tools/validate.sh [project_dir] [subdir-filter]
source "$(dirname "$0")/env.sh"
DIR="${1:-$PROJECT_ROOT}"
FILTER="${2:-}"
LOG=$(mktemp)
[ "${SKIP_IMPORT:-0}" = "1" ] || "$(dirname "$0")/godot_import.sh" "$DIR" >/dev/null 2>&1
flock -w 3600 /tmp/meocam_godot.lock timeout 900 "$GODOT_BIN" --headless --path "$DIR" --script res://tools/validate.gd -- "$FILTER" </dev/null >"$LOG" 2>&1
grep -vE "ALSA|audio_driver|All audio drivers|audio_server" "$LOG" | grep -vE "leaked|still in use|PagedAllocator|ObjectDB instances" | grep -E "SCRIPT ERROR|Parse Error|ERROR|VALIDATE|Failed|Cannot|Invalid|not found|Identifier" | head -120
if ! grep -q "VALIDATE SUMMARY" "$LOG"; then grep -A3 "handle_crash" "$LOG"; echo "VALIDATION FAILED (crash/timeout)"; rm -f "$LOG"; exit 2; fi
if grep -qE "SCRIPT ERROR|Parse Error|VALIDATE FAIL" "$LOG"; then echo "VALIDATION FAILED"; rm -f "$LOG"; exit 1; fi
echo "VALIDATION OK"; rm -f "$LOG"
