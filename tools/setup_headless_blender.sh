#!/usr/bin/env bash
# Reproduce this sandbox's headless Blender environment from scratch.
#
# There is no Blender install and no X11/GL/EGL runtime here, and apt has no
# network access. bpy (the official Blender-as-a-Python-module wheel, 4.5.0) is
# installed from PyPI, and the missing shared libraries it links against are
# replaced with tiny generated stubs. Headless scene editing and Cycles CPU
# rendering do not use them; only EEVEE / OpenGL viewport paths would.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STUB_DIR="${WSK_STUB_DIR:-$(dirname "${REPO_ROOT}")/wsx-libs}"

echo "== venv =="
python3 -m venv "${REPO_ROOT}/.venv"
"${REPO_ROOT}/.venv/bin/pip" install --upgrade pip
"${REPO_ROOT}/.venv/bin/pip" install "bpy==4.5.0" numpy pillow

echo "== stub libraries in ${STUB_DIR} =="
mkdir -p "${STUB_DIR}"
cp "${REPO_ROOT}/tools/headless/"*.py "${REPO_ROOT}/tools/headless/"*.json "${STUB_DIR}/"
python3 "${STUB_DIR}/build_stubs.py"   # X11 / GL / xkb / SM / ICE stubs (auto-fix loop)
python3 "${STUB_DIR}/egl_stub.py"      # EGL / GLES stubs used by the GL context probe

echo "== smoke test =="
"${REPO_ROOT}/tools/bl.sh" "${REPO_ROOT}/tools/check_cycles.py"
