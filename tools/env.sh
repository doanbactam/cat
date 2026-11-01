#!/usr/bin/env bash
# Shared environment for headless Godot / Blender tooling.
export GODOT_BIN="${GODOT_BIN:-/usr/local/bin/godot}"
export BLENDER_BIN="${BLENDER_BIN:-/usr/local/bin/blender}"
export GODOT_DOCS="${GODOT_DOCS:-/opt/tools/godot-docs/doc/classes}"
# Software Vulkan (lavapipe) so Forward+ works without a GPU.
export VK_ICD_FILENAMES="${VK_ICD_FILENAMES:-/usr/share/vulkan/icd.d/lvp_icd.json}"
export PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
