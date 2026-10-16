"""Prompt 16 view pass - inspect waist chains from front, rear and sides.

Opens `Wildshift_Knight_16_Chains.blend` and renders the whole figure from
front, rear, both sides and two three-quarter angles, plus front, three-quarter and side waist close-ups.
Render-only settings preserve the burgundy cape and do not save back to the
blend file.

Writes `analysis/chains/p16_*.png` and a compact inspection sheet.

Run: tools/bl.sh tools/render_chains.py (WSK_SAMPLES=<n> to change quality)
"""
import os

import bpy            # noqa: F401
from mathutils import Vector  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_16_Chains.blend")
OUT = os.path.join(ROOT, "analysis/chains")
SAMPLES = int(os.environ.get("WSK_SAMPLES", "24"))
FULL_RES = (440, 660)
DETAIL_RES = (760, 950)
TARGET = Vector((0.0, 0.0, 1.0))

# name: (camera location, projection, scale-or-lens, target, resolution)
VIEWS = {
    "front": ((0.0, 4.0, 1.0), "ORTHO", 2.5, TARGET, FULL_RES),
    "rear": ((0.0, -4.0, 1.0), "ORTHO", 2.5, TARGET, FULL_RES),
    "side_left": ((-4.0, 0.0, 1.0), "ORTHO", 2.5, TARGET, FULL_RES),
    "side_right": ((4.0, 0.0, 1.0), "ORTHO", 2.5, TARGET, FULL_RES),
    "threequarter_front": ((2.9, 2.9, 1.5), "PERSP", 50, TARGET, FULL_RES),
    "threequarter_rear": ((2.9, -2.9, 1.5), "PERSP", 50, TARGET, FULL_RES),
    "waist_front": ((0.0, 1.6, 1.055), "ORTHO", 0.52,
                    Vector((0.0, 0.0, 1.055)), DETAIL_RES),
    "waist_threequarter": ((0.78, 1.05, 1.16), "PERSP", 110,
                            Vector((0.0, 0.06, 1.05)), DETAIL_RES),
    "waist_side": ((1.35, 0.20, 1.045), "PERSP", 110,
                   Vector((0.0, 0.0, 1.045)), DETAIL_RES),
}


def make_camera(name, location, projection, value, target):
    data = bpy.data.cameras.new(name)
    if projection == "ORTHO":
        data.type = "ORTHO"
        data.ortho_scale = value
    else:
        data.type = "PERSP"
        data.lens = value
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = Vector(location)
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def configure(scene):
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = -1.5
    if scene.world and scene.world.use_nodes:
        background = scene.world.node_tree.nodes.get("Background")
        if background:
            background.inputs[0].default_value = (0.32, 0.32, 0.34, 1.0)
            background.inputs[1].default_value = 0.9


def main():
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=SRC)
    scene = bpy.context.scene
    configure(scene)

    requested = os.environ.get("WSK_VIEWS")
    view_names = list(VIEWS) if not requested else [name.strip() for name in requested.split(",") if name.strip()]
    missing = sorted(set(view_names) - set(VIEWS))
    if missing:
        raise ValueError(f"Unknown requested view(s): {missing}")
    rendered = {}
    for name in view_names:
        location, projection, value, target, resolution = VIEWS[name]
        camera = make_camera("TMP_P16_" + name, location, projection, value, target)
        scene.camera = camera
        scene.render.resolution_x, scene.render.resolution_y = resolution
        output = os.path.join(OUT, f"p16_{name}.png")
        scene.render.filepath = output
        print("RENDERING", name, "->", output)
        bpy.ops.render.render(write_still=True)
        rendered[name] = output
        bpy.data.objects.remove(camera, do_unlink=True)

    from PIL import Image, ImageDraw, ImageFont  # noqa: E402

    def font(size, bold=False):
        options = ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf") if bold else ("DejaVuSans.ttf",)
        for option in options:
            for root in ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation"):
                path = os.path.join(root, option)
                if os.path.exists(path):
                    return ImageFont.truetype(path, size)
        return ImageFont.load_default()

    full_names = ("front", "rear", "side_left", "side_right", "threequarter_front", "threequarter_rear")
    if any(name not in rendered for name in full_names + ("waist_front", "waist_threequarter")):
        print("SKIPPING inspection sheet for a selected subset of views")
        return
    thumb_w, thumb_h = 220, 330
    pad, header, label_h = 10, 32, 28
    detail_w, detail_h = 350, 438
    detail_y = header + 2 * (thumb_h + label_h + pad)
    sheet_width = 2 * (detail_w + pad) + pad
    sheet_height = detail_y + detail_h + label_h + pad
    sheet = Image.new("RGB", (sheet_width, sheet_height), (235, 235, 238))
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 6), "Prompt 16 - front / rear / side chain inspection", fill=(28, 30, 36), font=font(18, True))
    for index, name in enumerate(full_names):
        row, col = divmod(index, 3)
        x = pad + col * (thumb_w + pad)
        y = header + pad + row * (thumb_h + label_h + pad)
        image = Image.open(rendered[name]).convert("RGB").resize((thumb_w, thumb_h), Image.LANCZOS)
        sheet.paste(image, (x, y))
        draw.rectangle((x, y, x + thumb_w, y + thumb_h), outline=(160, 160, 170))
        draw.text((x + 4, y + thumb_h + 5), name.replace("_", " "), fill=(35, 36, 42), font=font(14))
    for col, name in enumerate(("waist_front", "waist_threequarter")):
        x = pad + col * (detail_w + pad)
        image = Image.open(rendered[name]).convert("RGB").resize((detail_w, detail_h), Image.LANCZOS)
        sheet.paste(image, (x, detail_y))
        draw.rectangle((x, detail_y, x + detail_w, detail_y + detail_h), outline=(160, 160, 170))
        draw.text((x + 4, detail_y + detail_h + 5), name.replace("_", " "), fill=(35, 36, 42), font=font(14))
    sheet.save(os.path.join(OUT, "p16_inspection_sheet.png"))
    print("SHEET", os.path.join(OUT, "p16_inspection_sheet.png"))


if __name__ == "__main__":
    main()
