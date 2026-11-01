#!/usr/bin/env bash
# Render a scene to PNG using Forward+ on software Vulkan.
# Usage: tools/screenshot.sh scene=res://scenes/x.tscn out=/abs/out.png [frames=60] [cam=x,y,z look=x,y,z] [size=1600x900] ...
source "$(dirname "$0")/env.sh"
SIZE="1600x900"
for a in "$@"; do case "$a" in size=*) SIZE="${a#size=}";; esac; done
DIR="${PROJECT_DIR:-$PROJECT_ROOT}"
[ "${SKIP_IMPORT:-0}" = "1" ] || "$(dirname "$0")/godot_import.sh" "$DIR" >/dev/null 2>&1
flock -w 3600 /tmp/meocam_godot.lock timeout "${SHOT_TIMEOUT:-600}" xvfb-run -a -s "-screen 0 ${SIZE}x24" \
  "$GODOT_BIN" --path "$DIR" --resolution "$SIZE" --script res://tools/screenshot.gd -- "$@" </dev/null 2>&1 \
  | grep -vE "ALSA|audio_driver|All audio drivers|audio_server|^\s*at: (init_output|initialize)" | tail -40
