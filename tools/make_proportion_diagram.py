"""Render annotated orthographic proportion diagrams.

Renders the front and side orthographic views of the mannequin with the guides
visible, then overlays the measured landmark heights and the joint positions
(the WSK_Joint_* empties, which are viewport gizmos and do not render) as
labelled callouts. Projection is exact: the camera is orthographic and the
resolution / ortho scale are known, so world metres map linearly to pixels.

Outputs analysis/diagram_front.png, analysis/diagram_side.png
"""
import os

import bpy          # noqa: F401 (must be first)
from PIL import Image, ImageDraw
from mathutils import Vector

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_02_Proportions.blend")
OUT = os.path.join(ROOT, "analysis")

RES_X, RES_Y = 1300, 1700
ORTHO = 2.40          # vertical extent of the frame, metres
LOOK_Z = 1.03         # camera height / frame centre
SAMPLES = 48


def setup_scene():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"

    cam_data = bpy.data.cameras.new("WSK_Cam_Diagram_Ortho")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ORTHO
    cam = bpy.data.objects.new("WSK_Cam_Diagram_Ortho", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return scene, cam


# The front camera sits on +Y looking towards -Y with +Z up, so its screen
# right axis is world -X: a front view of a face-to-face character. The side
# camera sits on +X looking towards -X, so its screen right axis is world +Y.
FRONT_SIGN = -1.0
SIDE_SIGN = +1.0
# the cape reaches Y -0.72 while the body front is only Y +0.19, so the side
# view is panned backwards to keep the figure centred in the frame
SIDE_LOOK_Y = -0.22


def project(value, z, sign=FRONT_SIGN, look=0.0):
    """World (axis, z) -> pixel (px, py) for the orthographic frame."""
    px_per_m = RES_Y / ORTHO
    return (RES_X / 2.0 + sign * (value - look) * px_per_m,
            RES_Y / 2.0 - (z - LOOK_Z) * px_per_m)


def render(scene, cam, loc, path, look_y=0.0):
    cam.location = loc
    target = (0.0, look_y, LOOK_Z)
    cam.rotation_euler = (Vector(target) - cam.location).normalized().to_track_quat(
        "-Z", "Y").to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def label(d, xy, text, colour):
    """Draw text with a dark backing plate so it stays readable over guides."""
    x, y = xy
    w = 7 * len(text) + 8
    d.rectangle([x - 2, y - 2, x + w, y + 14], fill=(24, 24, 27))
    d.text(xy, text, fill=colour)


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    scene, cam = setup_scene()

    joints = {o.name.replace("WSK_Joint_", ""): (o.location.x, o.location.z)
              for o in bpy.data.objects if o.name.startswith("WSK_Joint_")}

    render(scene, cam, (0.0, 6.0, LOOK_Z), os.path.join(OUT, "_diagram_front_raw.png"))
    render(scene, cam, (6.0, SIDE_LOOK_Y, LOOK_Z),
           os.path.join(OUT, "_diagram_side_raw.png"), look_y=SIDE_LOOK_Y)

    # ---- front diagram: heights + joint callouts -------------------------
    img = Image.open(os.path.join(OUT, "_diagram_front_raw.png")).convert("RGB")
    d = ImageDraw.Draw(img)

    heights = [
        ("crown spike tips (guide only)", 2.11, (255, 190, 60)),
        ("helmet dome top = 2.00 m", 2.00, (255, 255, 90)),
        ("eyes", 1.77, (200, 200, 200)),
        ("chin", 1.74, (200, 200, 200)),
        ("shoulder line (pauldron top)", 1.68, (255, 130, 130)),
        ("shoulder joint", 1.63, (255, 130, 130)),
        ("waist", 1.22, (255, 130, 130)),
        ("hip joint", 1.00, (255, 130, 130)),
        ("crotch", 0.97, (200, 200, 200)),
        ("knee", 0.55, (255, 130, 130)),
        ("ankle", 0.115, (255, 130, 130)),
        ("ground", 0.0, (255, 60, 60)),
    ]
    for text, z, colour in heights:
        _, y = project(0.0, z)
        d.line([(0, y), (RES_X * 0.17, y)], fill=colour, width=2)
        d.line([(RES_X * 0.83, y), (RES_X, y)], fill=colour, width=1)
        label(d, (6, y - 15), f"{text}  Z={z:.3f}", colour)

    joint_marks = ["Shoulder_R", "Elbow_R", "Wrist_R", "Hip_R", "Knee_R", "Ankle_R",
                   "Neck", "Center_Waist"]
    for name in joint_marks:
        if name not in joints:
            continue
        x, z = joints[name]
        px, py = project(x, z)
        r = 9
        d.ellipse([px - r, py - r, px + r, py + r], outline=(60, 255, 190), width=3)
        d.line([(px, py), (px + 90, py - 40)], fill=(60, 255, 190), width=2)
        label(d, (px + 94, py - 52),
              f"{name.replace('_R', ' R')} ({x:+.3f}, {z:.3f})", (60, 255, 190))

    d.text((6, RES_Y - 26), "FRONT  orthographic  |  grid 0.10 m  |  body height 2.00 m "
                            "|  measurements +-5 %  (see WSK_Proportion_Sheet.txt)",
           fill=(255, 255, 255))
    img.save(os.path.join(OUT, "diagram_front.png"))

    # ---- side diagram ----------------------------------------------------
    img = Image.open(os.path.join(OUT, "_diagram_side_raw.png")).convert("RGB")
    # trim the dead space left of the cape: the mannequin is only ~0.9 m deep
    # including the cape envelope, so a full-width side frame is mostly empty.
    # Everything is drawn after the crop, with the same x offset applied.
    crop_x0 = int(RES_X * 0.17)
    img = img.crop((crop_x0, 0, int(RES_X * 0.95), RES_Y))
    ox = -crop_x0
    d = ImageDraw.Draw(img)
    for text, z, colour in heights:
        _, y = project(0.0, z)
        d.line([(0, y), (RES_X * 0.17, y)], fill=colour, width=2)
        d.line([(RES_X * 0.83, y), (RES_X, y)], fill=colour, width=1)
        label(d, (6, y - 15), f"{text}  Z={z:.3f}", colour)
    depths = [("cape rear  Y -0.72 m", -0.72, 0.14), ("cape hem rear  Y -0.63 m", -0.63, 0.10),
              ("back of pauldron  Y -0.15 m", -0.15, 0.14), ("centreline  Y 0.00", 0.0, 0.10),
              ("chest front  Y +0.18 m", 0.18, 0.14), ("toe  Y +0.17 m", 0.17, 0.10)]
    for text, y_world, z_text in depths:
        px, _ = project(y_world, 0.0, SIDE_SIGN, SIDE_LOOK_Y)
        d.line([(px + ox, 0), (px + ox, RES_Y)], fill=(90, 190, 255), width=1)
        tx, ty = project(y_world, 2.18 - z_text * 2.0, SIDE_SIGN, SIDE_LOOK_Y)
        label(d, (tx + 4 + ox, ty), text, (90, 190, 255))
    d.text((6, RES_Y - 26), "SIDE  orthographic  |  +Y (image right) = depth behind the "
                            "body  |  only depth source is a perspective reference view",
           fill=(255, 255, 255))
    img.save(os.path.join(OUT, "diagram_side.png"))

    for tmp in ("_diagram_front_raw.png", "_diagram_side_raw.png"):
        os.remove(os.path.join(OUT, tmp))
    print("wrote diagram_front.png and diagram_side.png")


if __name__ == "__main__":
    main()
