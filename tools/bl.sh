#!/usr/bin/env bash
# Run a script with the headless Blender (bpy) module.
# Usage: tools/bl.sh path/to/script.py [args...]
#
# The sandbox has no X11/GL/EGL runtime, so two sets of stub libraries are
# generated (see tools/setup_headless_blender.sh) and put on LD_LIBRARY_PATH.
# Blender's file/scene API and Cycles CPU rendering work fine that way;
# EEVEE / OpenGL viewport features are unavailable by design.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STUB_DIR="${WSK_STUB_DIR:-$(dirname "${REPO_ROOT}")/wsx-libs}"
export LD_LIBRARY_PATH="${STUB_DIR}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

exec "${REPO_ROOT}/.venv/bin/python" -u "$@"
