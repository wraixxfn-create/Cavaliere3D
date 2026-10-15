# Headless Blender for this sandbox

There is no Blender executable, no X11 and no OpenGL/EGL runtime here, and
`apt` has no network access. Blender is therefore used as the official `bpy`
Python module (4.5.0 from PyPI). That module links against X11/GL/EGL sonames
that do not exist in this image, so `build_stubs.py` and `egl_stub.py` generate
minimal replacement `.so` files:

* `build_stubs.py` scans the undefined symbols of `bpy/__init__.so` and the
  bundled USD/OpenGL libraries, groups them by the library they belong to
  (libX11, libXfixes, libXrender, libXi, libxkbcommon, libSM, libICE, libGL),
  emits a `void *symbol(void) { return 0; }` stub for each, and rebuilds the
  library with a version script when the symbols are versioned. `extra.json`
  records the symbols the auto-fix loop had to add by hand.
* `egl_stub.py` does the same for libEGL/libGLES, which Blender's GL-context
  probe dlopens.

Importing a stub symbol is fine because nothing headless ever calls it.

Working: the whole Python API, file I/O, node set-up, Cycles CPU rendering.
Not working: EEVEE, OpenGL viewports, GPU rendering — those need a real GL.
