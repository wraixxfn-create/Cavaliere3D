"""Prompt 12 - render harness for the selective armour trim.

Works on any checkpoint (WSK_SRC=<file>, WSK_TAG=<prefix>), so the same script
produces the "before" sheets from checkpoint 11 and the "after" sheets from
checkpoint 12.

Views: gameplay-distance whole figure (front and three-quarter), and close
framings of each decorated location - chest, waist band, helmet brow, knees and
shins - each from the front and a three-quarter angle, with an ornament-hidden
"before" twin of every close framing for comparison.

Env: WSK_SRC=<blend>, WSK_TAG=<prefix>, WSK_SKIP_RENDERS=1, WSK_SAMPLES=<n>,
     WSK_QUICK=1 (gameplay views only).
Run: tools/bl.sh tools/render_armor_details.py
"""
import os

import bpy  # noqa: F401
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.environ.get("WSK_SRC", os.path.join(ROOT, "Wildshift_Knight_12_ArmorDetails.blend"))
TAG = os.environ.get("WSK_TAG", "p12_")
SHOTS = os.path.join(ROOT, "analysis/armor_details")
SAMPLES = int(os.environ.get("WSK_SAMPLES", "32"))
SKIP = os.environ.get("WSK_SKIP_RENDERS") == "1"
QUICK = os.environ.get("WSK_QUICK") == "1"

RES = (760, 950)
HIDE_PREFIX = ("WSK_Guide_", "WSK_Label_", "WSK_Ref_", "WSK_Joint_", "WSK_Mann_", "WSK_Studio_")
ORNAMENTS = tuple(n for n in (
    "WSK_Decor_ChestKeelTrim_01", "WSK_Decor_ChestChevron_L_01", "WSK_Decor_ChestChevron_R_01",
    "WSK_Decor_BeltTrimTop_L_01", "WSK_Decor_BeltTrimTop_R_01",
    "WSK_Decor_BrowTrim_L_01", "WSK_Decor_BrowTrim_R_01",
    "WSK_Decor_KneeRidge_L_01", "WSK_Decor_KneeRidge_R_01",
    "WSK_Decor_ShinRidge_L_01", "WSK_Decor_ShinRidge_R_01"))

VIEWS = {
    "figure_front": dict(loc=(0.0, 4.0, 1.0), tgt=(0.0, 0.0, 1.0), ortho=2.5, res=(520, 650)),
    "figure_threequarter": dict(loc=(3.0, 3.0, 1.6), tgt=(0.0, 0.0, 1.0), lens=50, res=(520, 650)),
    "chest_front": dict(loc=(0.0, 1.6, 1.42), tgt=(0.0, 0.0, 1.42), ortho=0.52),
    "chest_threequarter": dict(loc=(0.85, 1.05, 1.52), tgt=(0.0, 0.06, 1.42), lens=110),
    "waist_front": dict(loc=(0.0, 1.6, 1.055), tgt=(0.0, 0.0, 1.055), ortho=0.52),
    "waist_threequarter": dict(loc=(0.85, 1.05, 1.16), tgt=(0.0, 0.06, 1.05), lens=110),
    "brow_front": dict(loc=(0.0, 1.2, 1.895), tgt=(0.0, 0.0, 1.895), ortho=0.30),
    "brow_threequarter": dict(loc=(0.55, 0.85, 1.96), tgt=(0.0, 0.03, 1.895), lens=130),
    "knees_front": dict(loc=(0.0, 1.6, 0.55), tgt=(0.0, 0.0, 0.55), ortho=0.62),
    "legs_threequarter": dict(loc=(0.75, 1.15, 0.55), tgt=(0.0, 0.02, 0.50), lens=110),
    "shins_front": dict(loc=(0.0, 1.6, 0.42), tgt=(0.0, 0.0, 0.42), ortho=0.62),
}


def font(size, bold=False):
    for name in (("DejaVuSans-Bold.ttf", "DejaVuSans.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def look_at(cam, loc, target):
    from mathutils import Vector
    direction = Vector(target) - Vector(loc)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    for o in bpy.data.objects:
        if o.name.startswith(HIDE_PREFIX):
            o.hide_render = True
    cam_data = bpy.data.cameras.new("WSK_Cam_DecorScratch")
    cam = bpy.data.objects.new("WSK_Cam_DecorScratch", cam_data)
    bpy.data.collections["Lighting and Cameras"].objects.link(cam)
    scene.camera = cam
    return scene, cam


def set_view(cam, v):
    cam.location = v["loc"]
    if "ortho" in v:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = v["ortho"]
    else:
        cam.data.type = "PERSP"
        cam.data.lens = v.get("lens", 50)
    look_at(cam, cam.location, v["tgt"])


def render(scene, path, res):
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return Image.open(path).convert("RGBA")


def backdrop(size):
    bg = Image.new("RGBA", size, (235, 235, 238, 255))
    return bg


def sheet(items, out, cols, title, scale=0.62):
    """items: list of (label, PIL image)."""
    if not items:
        return
    w, h = items[0][1].size
    tw, th = int(w * scale), int(h * scale)
    rows = (len(items) + cols - 1) // cols
    pad, bar = 12, 34
    W = cols * (tw + pad) + pad
    H = rows * (th + pad + bar) + pad + bar
    canvas = Image.new("RGB", (W, H), (235, 235, 238))
    draw = ImageDraw.Draw(canvas)
    draw.text((pad, 6), title, fill=(30, 30, 40), font=font(20, True))
    for i, (label, im) in enumerate(items):
        r, c = divmod(i, cols)
        x = pad + c * (tw + pad)
        y = pad + bar + r * (th + pad + bar)
        tile = backdrop((tw, th))
        tile.alpha_composite(im.resize((tw, th), Image.LANCZOS))
        canvas.paste(tile.convert("RGB"), (x, y))
        draw.rectangle([x, y, x + tw, y + th], outline=(160, 160, 170))
        draw.text((x + 4, y + th + 6), label, fill=(40, 40, 50), font=font(16))
    canvas.save(out)
    print("      wrote", out)


def hide_ornaments(flag):
    for n in ORNAMENTS:
        if n in bpy.data.objects:
            bpy.data.objects[n].hide_render = flag


def main():
    if SKIP:
        print("SKIP renders")
        return
    os.makedirs(SHOTS, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=SRC)
    scene, cam = setup_render()

    names = list(VIEWS) if not QUICK else ["figure_front", "figure_threequarter"]
    after, before = [], []
    for name in names:
        v = VIEWS[name]
        res = v.get("res", RES)
        print("      rendering", name)
        set_view(cam, v)
        hide_ornaments(False)
        im = render(scene, os.path.join(SHOTS, f"{TAG}{name}.png"), res)
        after.append((name, im))
        hide_ornaments(True)
        im_b = render(scene, os.path.join(SHOTS, f"{TAG}bare_{name}.png"), res)
        before.append((name, im_b))
        hide_ornaments(False)

    if len(after) > 2:
        close_a = [it for it in after if not it[0].startswith("figure")]
        close_b = [it for it in before if not it[0].startswith("figure")]
        sheet(close_a, os.path.join(SHOTS, f"{TAG}detail_sheet.png"), 2,
              f"{TAG}decorated locations - close inspection")
        sheet(close_b, os.path.join(SHOTS, f"{TAG}bare_detail_sheet.png"), 2,
              f"{TAG}the same views without the trim (checkpoint-11 plates)")
        pairs = []
        for (n, im), (_, imb) in zip(close_a[:4], close_b[:4]):
            pairs.append((n + " - with trim", im))
            pairs.append((n + " - without", imb))
        sheet(pairs, os.path.join(SHOTS, f"{TAG}before_after_sheet.png"), 2,
              f"{TAG}before / after at close range")
    fig = [it for it in after if it[0].startswith("figure")]
    figb = [it for it in before if it[0].startswith("figure")]
    sheet(fig + figb, os.path.join(SHOTS, f"{TAG}gameplay_sheet.png"), 2,
          f"{TAG}gameplay distance - with trim / without (front, three-quarter)")
    print("DONE", SHOTS)


if __name__ == "__main__":
    main()
