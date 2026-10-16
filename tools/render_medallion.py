"""Prompt 11 - render harness for the waist medallion.

Works on any checkpoint (WSK_SRC=<file>, WSK_TAG=<prefix>), so the same script
produces the "before" sheet from checkpoint 10 and the "after" sheet from
checkpoint 11.

Views: front, rear, both sides and both three-quarters at waist framing, a tight
front and rear framing of the ornament alone with the rest of the figure hidden,
and the whole figure from the front / rear / left silhouette cameras so the
ornament can be judged against the belt it sits on.

Env: WSK_SRC=<blend>, WSK_TAG=<prefix>, WSK_SKIP_RENDERS=1, WSK_SAMPLES=<n>,
     WSK_QUICK=1 (the tight framings only).
Run: tools/bl.sh tools/render_medallion.py
"""
import os

import bpy  # noqa: F401
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.environ.get("WSK_SRC", os.path.join(ROOT, "Wildshift_Knight_11_Medallion.blend"))
TAG = os.environ.get("WSK_TAG", "p11_")
SHOTS = os.path.join(ROOT, "analysis/medallion")
SAMPLES = int(os.environ.get("WSK_SAMPLES", "32"))
SKIP = os.environ.get("WSK_SKIP_RENDERS") == "1"
QUICK = os.environ.get("WSK_QUICK") == "1"

RES = (760, 950)
WAIST_Z = 1.055
ORTHO = 0.46
VIEWS = {
    "front": dict(loc=(0.0, 3.0, WAIST_Z), tgt=(0.0, 0.0, WAIST_Z), ortho=ORTHO),
    "rear": dict(loc=(0.0, -3.0, WAIST_Z), tgt=(0.0, 0.0, WAIST_Z), ortho=ORTHO),
    "side_left": dict(loc=(-3.0, 0.0, WAIST_Z), tgt=(0.0, 0.0, WAIST_Z), ortho=ORTHO),
    "side_right": dict(loc=(3.0, 0.0, WAIST_Z), tgt=(0.0, 0.0, WAIST_Z), ortho=ORTHO),
    "threequarter": dict(loc=(-0.95, 1.35, 1.32), tgt=(0.0, 0.06, 1.02), lens=125),
    "threequarter_rear": dict(loc=(0.95, -1.35, 1.32), tgt=(0.0, -0.06, 1.02), lens=125),
}
TIGHT = {
    "front_only": dict(loc=(0.0, 1.2, 1.055), tgt=(0.0, 0.0, 1.055), ortho=0.175),
    "rear_only": dict(loc=(0.0, -1.2, 1.030), tgt=(0.0, 0.0, 1.030), ortho=0.175),
    "threequarter_only": dict(loc=(0.55, 0.90, 1.28), tgt=(0.0, 0.03, 1.03), lens=140),
}
HIDE_PREFIX = ("WSK_Guide_", "WSK_Label_", "WSK_Ref_", "WSK_Joint_", "WSK_Mann_", "WSK_Studio_")
MEDALLION = "WSK_Armor_WaistMedallion"


def font(size, bold=False):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else "")
    try:
        return ImageFont.truetype(p, size)
    except OSError:
        return ImageFont.load_default(size=size)


def look_at(cam, loc, target):
    from mathutils import Vector
    cam.location = loc
    d = (Vector(target) - Vector(loc)).normalized()
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "Standard"
    for o in bpy.data.objects:
        if o.name.startswith(HIDE_PREFIX):
            o.hide_render = True
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.030, 0.030, 0.034, 1.0)
    bg.inputs[1].default_value = 1.0
    for name, loc, energy, size in (("MedRim", (0.5, -1.1, 1.6), 45.0, 0.5),
                                    ("MedTop", (-0.4, 0.5, 1.6), 22.0, 0.6),
                                    ("MedFront", (0.0, 1.6, 1.35), 26.0, 0.8),
                                    ("MedLow", (0.0, 0.9, 0.55), 12.0, 0.8)):
        lamp = bpy.data.lights.new(name, "AREA")
        lamp.energy = energy
        lamp.size = size
        obj = bpy.data.objects.new(name, lamp)
        scene.collection.objects.link(obj)
        look_at(obj, loc, (0.0, 0.0, 1.055))
    cam = bpy.data.objects.new("MedCam", bpy.data.cameras.new("MedCam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = RES
    return scene, cam


def set_view(cam, v):
    if "ortho" in v:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = v["ortho"]
    else:
        cam.data.type = "PERSP"
        cam.data.lens = v["lens"]
    look_at(cam, v["loc"], v["tgt"])


def backdrop(size):
    w, h = size
    g = np.linspace(0.66, 0.44, h)[:, None] * np.ones((1, w))
    arr = np.dstack([g * 255, g * 255, (g + 0.015) * 255, np.full((h, w), 255)]).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def render(scene, path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    im = Image.open(path).convert("RGBA")
    comp = Image.alpha_composite(backdrop(im.size), im)
    comp.convert("RGB").save(path)
    return comp.convert("RGB"), (np.asarray(im)[..., 3] > 127)


def sheet(items, out, cols, title, scale=0.62, bg=(235, 235, 238)):
    tiles = [(t, im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS))
             for t, im in items]
    tw = max(t.width for _, t in tiles)
    th = max(t.height for _, t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * tw, rows * (th + 34) + 34), bg)
    d = ImageDraw.Draw(canvas)
    d.text((12, 8), title, font=font(24, True), fill=(25, 25, 28))
    for i, (t, im) in enumerate(tiles):
        r, c = divmod(i, cols)
        canvas.paste(im, (c * tw + (tw - im.width) // 2, 34 + r * (th + 34)))
        d.text((c * tw + 10, 34 + r * (th + 34) + 4), t, font=font(19, True), fill=(25, 25, 28))
    canvas.save(out)
    print("sheet", out, canvas.size)
    return out


def hide_all_but(prefix):
    hidden = {}
    for o in bpy.data.objects:
        if o.type == "MESH" and not o.name.startswith(prefix):
            hidden[o.name] = o.hide_render
            o.hide_render = True
    return hidden


def restore(hidden):
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name in hidden:
            o.hide_render = hidden[o.name]


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    os.makedirs(SHOTS, exist_ok=True)
    if SKIP:
        return
    scene, cam = setup_render()
    shots = []
    views = (("front_only", TIGHT["front_only"]), ("rear_only", TIGHT["rear_only"])) if QUICK \
        else VIEWS.items()
    for name, v in views:
        set_view(cam, v)
        print("      rendering", name)
        im, _ = render(scene, os.path.join(SHOTS, f"{TAG}waist_{name}.png"))
        shots.append((name, im))
    if not QUICK:
        sheet(shots[:4], os.path.join(SHOTS, f"{TAG}waist_four_views.png"), 4,
              f"waist: front / rear / left / right  ({os.path.basename(SRC)})")
        sheet(shots[4:], os.path.join(SHOTS, f"{TAG}waist_threequarter.png"), 2,
              "three-quarter front and three-quarter rear")

    # the ornament alone: every mesh whose name is not the waist ornament hidden
    hidden = hide_all_but(MEDALLION)
    tight = []
    for name, v in TIGHT.items():
        set_view(cam, v)
        print("      rendering ornament-only", name)
        im, _ = render(scene, os.path.join(SHOTS, f"{TAG}medallion_{name}.png"))
        tight.append((name.replace("_", " "), im))
    restore(hidden)
    sheet(tight, os.path.join(SHOTS, f"{TAG}medallion_only_sheet.png"), 3,
          "waist medallion alone (belt and body hidden)")
    if QUICK:
        return

    whole = []
    for name in ("WSK_Cam_Sil_Front_01", "WSK_Cam_Sil_Rear_01", "WSK_Cam_Sil_Left_01"):
        if name not in bpy.data.objects:
            continue
        scene.camera = bpy.data.objects[name]
        scene.render.resolution_x, scene.render.resolution_y = (560, 900)
        scene.render.filepath = os.path.join(SHOTS, f"{TAG}figure_{name[9:-3]}.png")
        bpy.ops.render.render(write_still=True)
        im = Image.open(scene.render.filepath).convert("RGB")
        whole.append((name[9:-3], im))
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = RES
    if whole:
        sheet(whole, os.path.join(SHOTS, f"{TAG}waist_in_context.png"), 3,
              "whole figure: front / rear / left")


if __name__ == "__main__":
    main()
