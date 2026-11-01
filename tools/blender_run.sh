#!/usr/bin/env bash
# Run a Blender Python generator headlessly. Usage: tools/blender_run.sh blender/cat/build_cat.py [-- args]
source "$(dirname "$0")/env.sh"
SCRIPT="$1"; shift
cd "$PROJECT_ROOT"
timeout "${BLENDER_TIMEOUT:-3600}" "$BLENDER_BIN" -b --factory-startup --python-exit-code 1 -P "$SCRIPT" -- "$@" 2>&1 | grep -vE "^Fra:|^\s*$|Color management" | tail -"${BLENDER_TAIL:-80}"
exit "${PIPESTATUS[0]}"
