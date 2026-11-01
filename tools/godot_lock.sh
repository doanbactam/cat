#!/usr/bin/env bash
# Serialize Godot invocations on the shared project dir (prevents .godot/ cache corruption
# when several agents import/run at once). Usage: tools/godot_lock.sh <command...>
exec flock -w 3600 /tmp/meocam_godot.lock "$@"
