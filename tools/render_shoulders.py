"""Prompt 7 - render the shoulder inspection views.

Front, rear, side and two three-quarter close-ups of the shoulder assembly, plus
four whole-figure views so the shoulders can be judged in context.  Uses the
"Shoulder Check" view layer (real placeholder materials, contrasting backdrop).

Env: WSK_SKIP_RENDERS=1, WSK_SAMPLES=<n> (default 32).
Run: tools/bl.sh tools/render_shoulders.py
"""
import os

import bpy  # noqa: F401
from PIL import Image, ImageDraw  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_07_Shoulders.blend")
SHOTS = os.path.join(ROOT, "analysis/shoulders")
SAMPLES = int(os.environ.get("WSK_SAMPLES", "32"))
SKIP = os.environ.get("WSK_SKIP_RENDERS") == "1"
QUICK = os.environ.get("WSK_QUICK") == "1"

CLOSE = {
    "front": ("WSK_Cam_Shoulder_Front_01", (960, 620)),
    "rear": ("WSK_Cam_Shoulder_Rear_01", (960, 620)),
    "side": ("WSK_Cam_Shoulder_Side_01", (960, 620)),
    "threequarter": ("WSK_Cam_Shoulder_ThreeQ_01", (960, 700)),
    "threequarter_back": ("WSK_Cam_Shoulder_ThreeQBack_01", (960, 700)),
}
WHOLE = {
    "figure_front": "WSK_Cam_Sil_Front_01",
    "figure_rear": "WSK_Cam_Sil_Rear_01",
    "figure_left": "WSK_Cam_Sil_Left_01",
    "figure_right": "WSK_Cam_Sil_Right_01",
}


def render(name, path, size, samples=SAMPLES):
    scene = bpy.context.scene
    scene.camera = bpy.data.objects[name]
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.cycles.samples = samples
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("rendered", path)


def sheet(paths, out, cols=None, pad=8, title=""):
    images = [Image.open(p).convert("RGB") for p in paths]
    cols = cols or len(images)
    rows = (len(images) + cols - 1) // cols
    cw = max(i.width for i in images)
    ch = max(i.height for i in images)
    canvas = Image.new("RGB", (cols * cw + (cols + 1) * pad,
                              rows * ch + (rows + 1) * pad + (24 if title else 0)),
                       (28, 28, 30))
    for i, im in enumerate(images):
        r, c = divmod(i, cols)
        canvas.paste(im, (pad + c * (cw + pad),
                          pad + r * (ch + pad) + (24 if title else 0)))
    if title:
        ImageDraw.Draw(canvas).text((pad, 6), title, fill=(230, 230, 230))
    canvas.save(out)
    print("sheet", out, canvas.size)


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    os.makedirs(SHOTS, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.render.film_transparent = False
    # The "Shoulder Check" view layer is used for the saved file; here the same
    # result is produced by hiding the guide collections and switching the world.
    scene.world = bpy.data.worlds["WSK_World_Silhouette"]
    for name in ("Reference", "Blockout", "Silhouette Check"):
        col = bpy.data.collections.get(name)
        if col is not None:
            for obj in col.objects:
                obj.hide_render = True

    if SKIP:
        return
    close_paths = []
    for key, (cam, size) in CLOSE.items():
        path = os.path.join(SHOTS, f"shoulder_{key}.png")
        render(cam, path, size)
        close_paths.append(path)
    sheet(close_paths[:4], os.path.join(SHOTS, "shoulder_views.png"), cols=2,
          title="Prompt 7 - shoulder armour: front / rear / side / three-quarter")
    sheet(close_paths[3:], os.path.join(SHOTS, "shoulder_threequarter.png"), cols=2,
          title="three-quarter front and three-quarter rear")
    if QUICK:
        return

    whole_paths = []
    for key, cam in WHOLE.items():
        path = os.path.join(SHOTS, f"{key}.png")
        render(cam, path, (560, 900))
        whole_paths.append(path)
    sheet(whole_paths, os.path.join(SHOTS, "shoulder_in_context.png"), cols=4,
          title="checkpoint 7 in context: front / rear / left / right")


if __name__ == "__main__":
    main()
