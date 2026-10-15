"""Render orthographic progress checks of the proportion guide.

Uses Cycles CPU (this sandbox has no OpenGL, so EEVEE is unavailable) at low
sample counts; the point is silhouette and proportion, not beauty.

Outputs to analysis/checks/*.png plus a contact sheet.
"""
import math
import os
import sys

import bpy          # noqa: F401  (must be first)
from mathutils import Vector

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_02_Proportions.blend")
OUT = os.path.join(ROOT, "analysis/checks")

RES = (620, 840)
SAMPLES = 48


def look_at(obj, target):
    direction = (Vector(target) - obj.location).normalized()
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    os.makedirs(OUT, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"

    # hide the image-empty backdrops: they do not render, but keep the guides
    views = {
        "front": ((0.0, 6.0, 1.05), (0.0, 0.0, 1.05)),
        "back": ((0.0, -6.0, 1.05), (0.0, 0.0, 1.05)),
        "side_left": ((-6.0, 0.0, 1.05), (0.0, 0.0, 1.05)),
        "side_right": ((6.0, 0.0, 1.05), (0.0, 0.0, 1.05)),
        "threequarter": ((-4.2, 4.2, 1.85), (0.0, 0.0, 1.0)),
    }

    cam_data = bpy.data.cameras.new("WSK_Cam_Check_Ortho")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 2.35
    cam = bpy.data.objects.new("WSK_Cam_Check_Ortho", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    scene.camera = cam
    cam_data.clip_end = 60.0

    for name, (loc, target) in views.items():
        cam.location = loc
        if name == "threequarter":
            cam_data.type = "PERSP"
            cam_data.lens = 55
        else:
            cam_data.type = "ORTHO"
        look_at(cam, target)
        scene.render.filepath = os.path.join(OUT, f"check_{name}.png")
        print("rendering", name, flush=True)
        bpy.ops.render.render(write_still=True)

    print("done", OUT)


if __name__ == "__main__":
    main()
    sys.stdout.flush()
