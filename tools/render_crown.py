"""Prompt 10 - render the crown and shoulder-spike inspection views.

Views: front, both sides, rear, two three-quarters, plus a tight crown-only
framing and the shoulder fan, so the silhouette can be judged from every angle
the prompt asks for.  Works on any checkpoint (WSK_SRC=<file>), so the same
harness produces the "before" and "after" sheets.

Env: WSK_SRC=<blend>, WSK_TAG=<prefix>, WSK_SKIP_RENDERS=1, WSK_SAMPLES=<n>,
     WSK_QUICK=1 (crown close-ups only).
Run: tools/bl.sh tools/render_crown.py
"""
import os

import bpy  # noqa: F401
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.environ.get("WSK_SRC", os.path.join(ROOT, "Wildshift_Knight_10_Crown.blend"))
TAG = os.environ.get("WSK_TAG", "")
SHOTS = os.path.join(ROOT, "analysis/crown")
SAMPLES = int(os.environ.get("WSK_SAMPLES", "32"))
SKIP = os.environ.get("WSK_SKIP_RENDERS") == "1"
QUICK = os.environ.get("WSK_QUICK") == "1"

VIEW_CENTRE_Z = 1.94
ORTHO = 0.62
RES = (800, 1000)
VIEWS = {
    "front": dict(loc=(0.0, 3.0, VIEW_CENTRE_Z), tgt=(0.0, 0.0, VIEW_CENTRE_Z), ortho=ORTHO),
    "side_left": dict(loc=(-3.0, -0.035, VIEW_CENTRE_Z), tgt=(0.0, -0.035, VIEW_CENTRE_Z), ortho=ORTHO),
    "side_right": dict(loc=(3.0, -0.035, VIEW_CENTRE_Z), tgt=(0.0, -0.035, VIEW_CENTRE_Z), ortho=ORTHO),
    "rear": dict(loc=(0.0, -3.0, VIEW_CENTRE_Z), tgt=(0.0, 0.0, VIEW_CENTRE_Z), ortho=ORTHO),
    "threequarter": dict(loc=(-1.55, 2.05, 2.20), tgt=(0.0, -0.02, 1.93), lens=140),
    "threequarter_rear": dict(loc=(1.75, -1.85, 2.25), tgt=(0.0, -0.05, 1.93), lens=140),
    "top": dict(loc=(0.0, -0.20, 3.60), tgt=(0.0, -0.10, 1.95), ortho=0.55),
}
CROWN_ONLY = dict(loc=(0.0, 3.0, 2.02), tgt=(0.0, 0.0, 2.02), ortho=0.46)
SHOULDER = dict(loc=(0.0, 3.0, 1.63), tgt=(0.0, 0.0, 1.63), ortho=0.90)
HIDE_PREFIX = ("WSK_Guide_", "WSK_Label_", "WSK_Ref_", "WSK_Joint_", "WSK_Mann_", "WSK_Studio_")
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
    for name, loc, energy, size in (("CrownRim", (0.9, -1.3, 2.5), 60.0, 0.6),
                                    ("CrownTop", (-0.6, 0.9, 2.8), 25.0, 0.8),
                                    ("CrownFront", (0.0, 2.2, 2.3), 30.0, 0.9)):
        lamp = bpy.data.lights.new(name, "AREA")
        lamp.energy = energy
        lamp.size = size
        obj = bpy.data.objects.new(name, lamp)
        scene.collection.objects.link(obj)
        look_at(obj, loc, (0.0, 0.0, 1.95))
    cam = bpy.data.objects.new("CrownCam", bpy.data.cameras.new("CrownCam"))
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


def sheet(items, out, cols, title, scale=0.6, bg=(235, 235, 238)):
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
    only = os.environ.get("WSK_ONLY", "")
    shots = []
    for name, v in (() if only == "shoulders" else VIEWS.items()):
        set_view(cam, v)
        print("      rendering", name)
        im, _ = render(scene, os.path.join(SHOTS, f"{pre}crown_{name}.png"))
        shots.append((name, im))
    if shots:
        sheet(shots[:4], os.path.join(SHOTS, f"{pre}crown_four_views.png"), 4,
              f"crown: front / left / right / rear  ({os.path.basename(SRC)})")
        sheet([shots[4], shots[5]], os.path.join(SHOTS,
              f"{pre}crown_threequarter.png"), 2,
              "three-quarter front and three-quarter rear")

    # crown only, tight framing, with the body hidden so the crown reads alone
    body = bpy.data.objects.get(BODY)
    keep = [o for o in bpy.data.objects if o.name.startswith("WSK_Helmet_")]
    hidden = {}
    for o in bpy.data.objects:
        if o.type == "MESH" and o not in keep:
            hidden[o.name] = o.hide_render
            o.hide_render = True
    tight = []
    for name, v in (() if only == "shoulders" else (("front", CROWN_ONLY),
                    ("threequarter", dict(loc=(-1.35, 1.75, 2.35), tgt=(0.0, -0.06, 2.02), lens=140)))):
        set_view(cam, v)
        print("      rendering crown-only", name)
        im, _ = render(scene, os.path.join(SHOTS, f"{pre}crownonly_{name}.png"))
        tight.append(("crown only " + name, im))
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name in hidden:
            o.hide_render = hidden[o.name]
    if QUICK:
        sheet(tight, os.path.join(SHOTS, f"{pre}crown_only_sheet.png"), 2,
              "crown alone (helmet and body hidden)")
        return

    # shoulders with the body hidden, so the spike fan reads against the crown
    hidden = {}
    for o in bpy.data.objects:
        if o is body:
            hidden[o.name] = o.hide_render
            o.hide_render = True
    shoulder = []
    for name, v in (("front", SHOULDER),
                    ("rear", dict(SHOULDER, loc=(0.0, -3.0, 1.63), tgt=(0.0, 0.0, 1.63))),
                    ("side", dict(SHOULDER, loc=(3.0, 0.0, 1.63), tgt=(0.0, 0.0, 1.63))),
                    ("threequarter", dict(loc=(1.30, 1.45, 2.10), tgt=(0.02, 0.0, 1.60), lens=58))):
        set_view(cam, v)
        print("      rendering shoulder", name)
        im, _ = render(scene, os.path.join(SHOTS, f"{pre}shoulderplane_{name}.png"))
        shoulder.append((name, im))
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name in hidden:
            o.hide_render = hidden[o.name]
    sheet(tight + shoulder, os.path.join(SHOTS, f"{pre}crown_only_sheet.png"), 2,
          "crown alone and the shoulder spike fan (other parts hidden)")

    # in context: whole figure, from the saved silhouette cameras
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
    sheet(whole, os.path.join(SHOTS, f"{pre}crown_in_context.png"), 3,
          "crown in context: front / rear / left, whole figure")


if __name__ == "__main__":
    main()
