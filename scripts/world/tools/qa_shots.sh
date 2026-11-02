#!/usr/bin/env bash
# World QA shots. Usage: scripts/world/tools/qa_shots.sh /abs/out_dir [only=a,b] [frames=24] [size=960x540]
source "$(dirname "$0")/../../../tools/env.sh"
OUT="$1"; shift
SIZE="960x540"
for a in "$@"; do case "$a" in size=*) SIZE="${a#size=}";; esac; done
cd "$PROJECT_ROOT"
flock -w 3600 /tmp/meocam_godot.lock timeout "${SHOT_TIMEOUT:-2400}" xvfb-run -a -s "-screen 0 ${SIZE}x24" \
  "$GODOT_BIN" --path "$PROJECT_ROOT" --resolution "$SIZE" --script res://scripts/world/tools/qa_shots.gd -- out="$OUT" "$@" </dev/null 2>&1 \
  | grep -E "QA shot|ERROR|SCRIPT|rror" | grep -v "ALSA" | head -60
