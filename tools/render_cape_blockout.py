"""Prompt 13 render pass - cape base shape.

Opens `Wildshift_Knight_13_CapeBlockout.blend` and renders, WITHOUT saving the
file, the front, rear, both sides and two three-quarter views:

  * in context  - the whole knight with the cape
  * cape only   - every other mesh hidden for render, to read the silhouette

Cycles on CPU (EEVEE needs a GL context this sandbox does not have), orthographic
cameras at the gameplay scale used since Prompt 6 (ortho scale 2.5) plus one
perspective three-quarter.  Writes analysis/cape/p13_*.png and a contact sheet
analysis/cape/p13_contact_sheet.png.

Run:  tools/bl.sh tools/render_cape_blockout.py        (set WSK_SKIP_RENDERS=1 to skip)
"""
import math
import os

import bpy            # noqa: F401
from mathutils import Vector  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_13_CapeBlockout.blend")
OUT = os.path.join(ROOT, "analysis/cape")
SAMPLES = int(os.environ.get("WSK_SAMPLES", "24"))
RES = (420, 640)
TARGET = Vector((0.0, 0.0, 1.0))
CAPE = "WSK_Cape_Blockout_01"

VIEWS = {
    # name: (camera location, projection)
    "front":      ((0.0, 4.0, 1.0), 'ORTHO'),
    "rear":       ((0.0, -4.0, 1.0), 'ORTHO'),
    "side_left":  ((-4.0, 0.0, 1.0), 'ORTHO'),
    "side_right": ((4.0, 0.0, 1.0), 'ORTHO'),
    "threeq_rear": ((2.9, -2.9, 1.5), 'PERSP'),
    "threeq_front": ((-2.9, 2.9, 1.5), 'PERSP'),
}


def make_camera(name, loc, proj):
    cam = bpy.data.cameras.new(name)
    if proj == 'ORTHO':
        cam.type = 'ORTHO'
        cam.ortho_scale = 2.5
    else:
        cam.type = 'PERSP'
        cam.lens = 50
    obj = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = Vector(loc)
    direction = (TARGET - Vector(loc)).normalized()
    obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return obj


def set_render(scene):
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    # Standard keeps the saturated burgundy true; AgX would wash it toward pink
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = -1.5   # the placeholder lights overexpose a dark base colour


def main():
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=SRC)
    scene = bpy.context.scene
    set_render(scene)
    if os.environ.get("WSK_SKIP_RENDERS") == "1":
        print("RENDERS SKIPPED")
        return

    # neutral studio world, so the burgundy reads against the figure
    if scene.world and scene.world.use_nodes:
        bg = scene.world.node_tree.nodes.get("Background")
        if bg:
            bg.inputs[0].default_value = (0.32, 0.32, 0.34, 1.0)
            bg.inputs[1].default_value = 0.9

    all_meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    original_hide = {o.name: o.hide_render for o in all_meshes}
    tiles = []
    for mode in ("context", "cape_only"):
        for o in all_meshes:
            if mode == "cape_only":
                o.hide_render = o.name not in (CAPE, "WSK_Studio_Ground_01")
            else:
                o.hide_render = original_hide[o.name]
        for name, (loc, proj) in VIEWS.items():
            cam = make_camera(f"TMP_{mode}_{name}", loc, proj)
            scene.camera = cam
            path = os.path.join(OUT, f"p13_{mode}_{name}.png")
            scene.render.filepath = path
            bpy.ops.render.render(write_still=True)
            print("RENDERED", path)
            tiles.append((mode, name, path))
            bpy.data.objects.remove(cam, do_unlink=True)

    # contact sheet
    from PIL import Image, ImageDraw
    cols = len(VIEWS)
    thumb_w, thumb_h = RES[0] // 2, RES[1] // 2
    sheet = Image.new("RGB", (cols * thumb_w, 2 * thumb_h + 30), (20, 20, 22))
    draw = ImageDraw.Draw(sheet)
    for r, mode in enumerate(("context", "cape_only")):
        for c, name in enumerate(VIEWS):
            path = [t[2] for t in tiles if t[0] == mode and t[1] == name][0]
            im = Image.open(path).convert("RGB").resize((thumb_w, thumb_h), Image.LANCZOS)
            sheet.paste(im, (c * thumb_w, r * thumb_h + 30))
            draw.text((c * thumb_w + 6, r * thumb_h + 8), f"{mode}: {name}", fill=(235, 235, 235))
    sheet.save(os.path.join(OUT, "p13_contact_sheet.png"))
    print("SHEET", os.path.join(OUT, "p13_contact_sheet.png"))


if __name__ == "__main__":
    main()
