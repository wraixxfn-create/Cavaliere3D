"""Prompt 14 render pass - cape layered torn panels.

Opens `Wildshift_Knight_14_CapePanels.blend` and renders, WITHOUT saving the file:

  * context   - the whole knight with the cape (rear, both sides, two three-quarters)
  * cape_only - every other mesh hidden for render, to read the panels and tears
  * hem       - close-ups of the lower cape, from the rear and from the left side

Cycles on CPU (EEVEE needs a GL context this sandbox does not have), orthographic
cameras at the gameplay scale of Prompts 6-13 (ortho scale 2.5) plus two
perspective three-quarter views and two orthographic hem close-ups.  The render
settings are the Prompt 13 ones (Standard transform, -1.5 EV) so the burgundy
keeps its colour; they are render-only and the saved file is unchanged.

Writes analysis/cape/p14_*.png and analysis/cape/p14_contact_sheet.png.

Run:  tools/bl.sh tools/render_cape_panels.py       (WSK_SKIP_RENDERS=1 to skip)
"""
import os

import bpy            # noqa: F401
from mathutils import Vector  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_14_CapePanels.blend")
OUT = os.path.join(ROOT, "analysis/cape")
SAMPLES = int(os.environ.get("WSK_SAMPLES", "24"))
RES = (420, 640)
TARGET = Vector((0.0, 0.0, 1.0))
CAPE_PARTS = ["WSK_Cape_Upper_01"] + [f"WSK_Cape_Panel_{k:02d}" for k in range(1, 6)]

# name: (camera location, projection, ortho scale, target)
VIEWS = {
    "rear":         ((0.0, -4.0, 1.0), 'ORTHO', 2.5, TARGET),
    "side_left":    ((-4.0, 0.0, 1.0), 'ORTHO', 2.5, TARGET),
    "side_right":   ((4.0, 0.0, 1.0), 'ORTHO', 2.5, TARGET),
    "threeq_rear":  ((2.9, -2.9, 1.5), 'PERSP', 2.5, TARGET),
    "threeq_front": ((-2.9, 2.9, 1.5), 'PERSP', 2.5, TARGET),
}
HEM_VIEWS = {
    "hem_rear":      ((0.0, -4.0, 0.55), 'ORTHO', 1.5, Vector((0.0, -0.5, 0.55))),
    "hem_side_left": ((-4.0, -0.4, 0.55), 'ORTHO', 1.5, Vector((-0.2, -0.5, 0.55))),
}


def make_camera(name, loc, proj, ortho_scale, target):
    cam = bpy.data.cameras.new(name)
    if proj == 'ORTHO':
        cam.type = 'ORTHO'
        cam.ortho_scale = ortho_scale
    else:
        cam.type = 'PERSP'
        cam.lens = 50
    obj = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = Vector(loc)
    direction = (Vector(target) - Vector(loc)).normalized()
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
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = -1.5


def main():
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=SRC)
    scene = bpy.context.scene
    set_render(scene)
    if os.environ.get("WSK_SKIP_RENDERS") == "1":
        print("RENDERS SKIPPED")
        return

    if scene.world and scene.world.use_nodes:
        bg = scene.world.node_tree.nodes.get("Background")
        if bg:
            bg.inputs[0].default_value = (0.32, 0.32, 0.34, 1.0)
            bg.inputs[1].default_value = 0.9

    all_meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    original_hide = {o.name: o.hide_render for o in all_meshes}
    tiles = []
    jobs = [("context", VIEWS), ("cape_only", VIEWS), ("hem", HEM_VIEWS)]
    for mode, views in jobs:
        for o in all_meshes:
            if mode == "cape_only":
                o.hide_render = o.name not in CAPE_PARTS + ["WSK_Studio_Ground_01"]
            elif mode == "hem":
                o.hide_render = o.name not in CAPE_PARTS + ["WSK_Studio_Ground_01"] \
                    and o.name not in ("WSK_Mann_Foot_L_01", "WSK_Mann_Foot_R_01",
                                       "WSK_Mann_Shin_L_01", "WSK_Mann_Shin_R_01")
            else:
                o.hide_render = original_hide[o.name]
        for name, (loc, proj, scale, target) in views.items():
            cam = make_camera(f"TMP_{mode}_{name}", loc, proj, scale, target)
            scene.camera = cam
            path = os.path.join(OUT, f"p14_{mode}_{name}.png")
            scene.render.filepath = path
            bpy.ops.render.render(write_still=True)
            print("RENDERED", path)
            tiles.append((mode, name, path))
            bpy.data.objects.remove(cam, do_unlink=True)

    from PIL import Image, ImageDraw  # noqa: E402
    names = list(VIEWS)
    thumb_w, thumb_h = RES[0] // 2, RES[1] // 2
    sheet = Image.new("RGB", (len(names) * thumb_w, 2 * thumb_h + 30), (20, 20, 22))
    draw = ImageDraw.Draw(sheet)
    for r, mode in enumerate(("context", "cape_only")):
        for c, name in enumerate(names):
            path = [t[2] for t in tiles if t[0] == mode and t[1] == name][0]
            im = Image.open(path).convert("RGB").resize((thumb_w, thumb_h), Image.LANCZOS)
            sheet.paste(im, (c * thumb_w, r * thumb_h + 30))
            draw.text((c * thumb_w + 6, r * thumb_h + 8), f"{mode}: {name}", fill=(235, 235, 235))
    sheet.save(os.path.join(OUT, "p14_contact_sheet.png"))
    print("SHEET", os.path.join(OUT, "p14_contact_sheet.png"))


if __name__ == "__main__":
    main()
