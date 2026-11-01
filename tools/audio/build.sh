#!/usr/bin/env bash
# Regenerate all procedural audio. Creates the venv on first use (numpy/scipy/soundfile).
# Usage: tools/audio/build.sh [--only REGEX] [--cards] [--jobs N]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
VENV="$HERE/.venv"
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -r "$HERE/requirements.txt"
fi
command -v ffmpeg >/dev/null || { echo "ffmpeg (with libvorbis) is required"; exit 1; }
cd "$HERE"
exec "$VENV/bin/python" build_all.py "$@"
