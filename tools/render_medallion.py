"""Prompt 11 - render the waist medallion inspection views.

Views: tight front and rear close-ups, the waist in context, two three-quarters,
a grazing edge-on view for the relief depth, the ornament alone (armour and body
hidden) and whole-figure sheets.  Works on any checkpoint (WSK_SRC=<file>), so
the same harness produces the "before" and "after" sheets.

Env: WSK_SRC=<blend>, WSK_TAG=<prefix>, WSK_SKIP_RENDERS=1, WSK_SAMPLES=<n>,
     WSK_VIEWS=close|all
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
SAMPLES = int(os.environ.get("WSK_SAMPLES", "64"))
SKIP = os.environ.get("WSK_SKIP_RENDERS") == "1"
VIEWS_MODE = os.environ.get("WSK_VIEWS", "all")

FRONT_Z = 1.055          # the existing mount centre
REAR_Z = 1.155           # the rear medallion centre (lower back plate)
RES = (760, 900)

CLOSE = {
    "pf_front": dict(loc=(0.0, 1.2, FRONT_Z + 0.012), tgt=(0.0, 0.0, FRONT_Z + 0.012), ortho=0.235),
    "pf_rear": dict(loc=(0.0, -1.2, REAR_Z), tgt=(0.0, 0.0, REAR_Z), ortho=0.235),
    "pf_relief": dict(loc=(0.62, 0.62, FRONT_Z + 0.02), tgt=(0.0, 0.10, FRONT_Z), lens=90),
    "pf_threequarter": dict(loc=(-0.62, 0.78, FRONT_Z + 0.30), tgt=(0.0, 0.10, FRONT_Z), lens=95),
    "pf_threequarter_rear": dict(loc=(0.70, -0.72, REAR_Z + 0.32), tgt=(0.0, -0.09, REAR_Z), lens=95),
}
CONTEXT = {
    "waist_front": dict(loc=(0.0, 2.4, 1.02), tgt=(0.0, 0.0, 1.02), ortho=0.62),
    "waist_rear": dict(loc=(0.0, -2.4, 1.06), tgt=(0.0, 0.0, 1.06), ortho=0.62),
    "waist_left": dict(loc=(-2.4, 0.0, 1.02), tgt=(0.0, 0.0, 1.02), ortho=0.62),
    "waist_threequarter": dict(loc=(-1.35, 1.75, 1.55), tgt=(0.0, 0.0, 1.00), lens=95),
}
ALONE = {
    "front": dict(loc=(0.0, 1.2, FRONT_Z + 0.012), tgt=(0.0, 0.0, FRONT_Z + 0.012), ortho=0.155),
    "rear": dict(loc=(0.0, -1.2, REAR_Z), tgt=(0.0, 0.0, REAR_Z), ortho=0.155),
    "relief": dict(loc=(0.62, 0.62, FRONT_Z + 0.02), tgt=(0.0, 0.11, FRONT_Z), lens=90),
    "threequarter": dict(loc=(-0.42, 0.52, FRONT_Z + 0.16), tgt=(0.0, 0.11, FRONT_Z), lens=95),
}
HIDE_PREFIX = ("WSK_Guide_", "WSK_Label_", "WSK_Ref_", "WSK_Joint_", "WSK_Mann_", "WSK_Studio_")
MEDALLION_PREFIX = "WSK_Armor_WaistMedallion"
BODY = "WSK_Body_Base_01"


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
    for name, loc, energy, size in (("MedRim", (0.75, 1.05, 1.35), 22.0, 0.45),
                                    ("MedTop", (-0.55, -0.75, 1.55), 12.0, 0.6),
                                    ("MedFar", (0.0, -1.9, 1.05), 5.0, 0.7)):
        lamp = bpy.data.lights.new(name, "AREA")
        lamp.energy = energy
        lamp.size = size
        obj = bpy.data.objects.new(name, lamp)
        scene.collection.objects.link(obj)
        look_at(obj, loc, (0.0, 0.0, 1.02))
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


def sheet(items, out, cols, title, scale=0.72, bg=(235, 235, 238)):
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


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    os.makedirs(SHOTS, exist_ok=True)
    if SKIP:
        return
    scene, cam = setup_render()
    pre = TAG
    close, context = [], []
    for name, v in CLOSE.items():
        set_view(cam, v)
        print("      rendering", name)
        im, _ = render(scene, os.path.join(SHOTS, f"{pre}{name}.png"))
        close.append((name.replace("pf_", ""), im))
    sheet(close, os.path.join(SHOTS, f"{pre}medallion_closeups.png"), 3,
          f"waist medallion close-ups  ({os.path.basename(SRC)})")
    for name, v in CONTEXT.items():
        set_view(cam, v)
        print("      rendering", name)
        im, _ = render(scene, os.path.join(SHOTS, f"{pre}{name}.png"))
        context.append((name.replace("waist_", ""), im))
    sheet(context, os.path.join(SHOTS, f"{pre}medallion_in_context.png"), 4,
          "waist medallion in context")
    if VIEWS_MODE == "close":
        return

    # the ornament alone: every mesh except the medallion parts hidden
    hidden = {}
    for o in bpy.data.objects:
        if o.type == "MESH" and not o.name.startswith(MEDALLION_PREFIX):
            hidden[o.name] = o.hide_render
            o.hide_render = True
    alone = []
    for name, v in ALONE.items():
        set_view(cam, v)
        print("      rendering medallion-only", name)
        im, _ = render(scene, os.path.join(SHOTS, f"{pre}medalliononly_{name}.png"))
        alone.append(("medallion only " + name, im))
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name in hidden:
            o.hide_render = hidden[o.name]
    sheet(alone, os.path.join(SHOTS, f"{pre}medallion_only_sheet.png"), 2,
          "the waist medallion alone (mount, armour and body hidden)")

    # whole figure, from the saved silhouette cameras
    whole = []
    for name in ("WSK_Cam_Sil_Front_01", "WSK_Cam_Sil_Rear_01", "WSK_Cam_Sil_Left_01"):
        scene.camera = bpy.data.objects[name]
        scene.render.resolution_x, scene.render.resolution_y = (560, 900)
        scene.render.filepath = os.path.join(SHOTS, f"{pre}figure_{name[-9:]}.png")
        bpy.ops.render.render(write_still=True)
        im = Image.open(scene.render.filepath).convert("RGB")
        whole.append((name[9:-3], im))
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = RES
    sheet(whole, os.path.join(SHOTS, f"{pre}medallion_figure.png"), 3,
          "waist medallion at figure scale: front / rear / left")


if __name__ == "__main__":
    main()
