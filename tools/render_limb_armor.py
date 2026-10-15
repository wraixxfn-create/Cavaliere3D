"""Render Prompt-9 neutral and manual-pose limb armour inspection sheets.

Run: tools/bl.sh tools/render_limb_armor.py
Environment: WSK_SAMPLES=<n> (default 12), WSK_QUICK=1 skips whole-figure views.
"""
import math
import os

import bpy  # noqa: F401
from mathutils import Vector  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_09_LimbArmor.blend")
OUT = os.path.join(ROOT, "analysis", "limb_armor")
SAMPLES = int(os.environ.get("WSK_SAMPLES", "12"))
QUICK = os.environ.get("WSK_QUICK") == "1"


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def camera(name, location, target, scale):
    data = bpy.data.cameras.new(name + "_data")
    data.type = "ORTHO"
    data.ortho_scale = scale
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = Vector(location)
    look_at(obj, target)
    return obj


def render(cam, path, size):
    scene = bpy.context.scene
    scene.camera = cam
    scene.render.engine = "BLENDER_EEVEE_NEXT" if False else "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("rendered", path)


def sheet(items, path, cols, title):
    ims = [(label, Image.open(p).convert("RGB")) for label, p in items]
    rows = (len(ims) + cols - 1) // cols
    cw = max(im.width for _, im in ims)
    ch = max(im.height for _, im in ims)
    pad, head, label_h = 10, 32, 24
    canvas = Image.new("RGB", (cols * cw + (cols + 1) * pad,
                               head + rows * (ch + label_h + pad) + pad),
                       (24, 25, 28))
    draw = ImageDraw.Draw(canvas)
    draw.text((pad, 9), title, fill=(235, 235, 238))
    for i, (label, im) in enumerate(ims):
        r, c = divmod(i, cols)
        x = pad + c * (cw + pad)
        y = head + r * (ch + label_h + pad)
        canvas.paste(im, (x, y + label_h))
        draw.text((x + 4, y + 5), label, fill=(224, 224, 228))
    canvas.save(path)
    print("sheet", path, canvas.size)


def hide_guides():
    for cname in ("Reference", "Blockout", "Silhouette Check", "Shoulder Check"):
        col = bpy.data.collections.get(cname)
        if col:
            col.hide_render = True
    # Do not hide the Limb Pose Controls collection: the empty parents do not
    # draw, while hiding their collection would also suppress the child armour.
    if bpy.data.worlds.get("WSK_World_Silhouette"):
        bpy.context.scene.world = bpy.data.worlds["WSK_World_Silhouette"]


def set_only(names):
    wanted = set(names)
    states = {}
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            states[obj.name] = obj.hide_render
            obj.hide_render = obj.name not in wanted
    return states


def restore(states):
    for name, state in states.items():
        obj = bpy.data.objects.get(name)
        if obj:
            obj.hide_render = state


def reset_pose(side="R"):
    for part in ("UpperArm", "ElbowCop", "Forearm", "Hand", "Thigh", "KneeCop", "Shin", "Foot"):
        bpy.data.objects[f"WSK_LimbPose_{part}_{side}_01"].rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()


def limb_names(side, group):
    tags = {
        "arm": ("UpperArm", "ElbowCop", "Forearm", "WristCuff", "Gauntlet"),
        "hand": ("ForearmLame_Distal", "WristCuff", "Gauntlet"),
        "leg": ("Thigh", "KneeCop", "Shin", "AnkleCuff", "Sabaton", "Sole"),
        "foot": ("ShinLame_Distal", "AnkleCuff", "Sabaton", "Sole"),
    }[group]
    out = []
    for obj in bpy.data.collections["Armor"].objects:
        if obj.type == "MESH" and f"_{side}_01" in obj.name and any(t in obj.name for t in tags):
            out.append(obj.name)
    return out


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    os.makedirs(OUT, exist_ok=True)
    hide_guides()

    scene = bpy.context.scene
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.use_single_layer = True
    if bpy.context.window and scene.view_layers.get("ViewLayer"):
        bpy.context.window.view_layer = scene.view_layers["ViewLayer"]

    # Close neutral views make plate ordering, hand read and the sole visible.
    cams = {
        "arms_front": camera("TMP_Limb_ArmsFront", (0, 3.2, 1.18), (0, 0.01, 1.18), 0.92),
        "arms_rear": camera("TMP_Limb_ArmsRear", (0, -3.2, 1.18), (0, 0.0, 1.18), 0.92),
        "legs_front": camera("TMP_Limb_LegsFront", (0, 3.2, 0.50), (0, 0.02, 0.50), 1.05),
        "legs_rear": camera("TMP_Limb_LegsRear", (0, -3.2, 0.50), (0, 0.0, 0.50), 1.05),
        "hand_3q": camera("TMP_Limb_Hand3Q", (1.55, 2.5, 1.16), (0.295, 0.02, 0.88), 0.38),
        "foot_3q": camera("TMP_Limb_Foot3Q", (1.45, 2.2, 0.56), (0.23, 0.03, 0.10), 0.48),
    }
    neutral = []
    for key in ("arms_front", "arms_rear", "legs_front", "legs_rear", "hand_3q", "foot_3q"):
        p = os.path.join(OUT, f"neutral_{key}.png")
        render(cams[key], p, (620, 720) if "3q" not in key else (620, 620))
        neutral.append((key.replace("_", " ").upper(), p))
    sheet(neutral, os.path.join(OUT, "limb_armor_neutral_views.png"), 3,
          "Prompt 9 — neutral limb armour: layering, gauntlets, greaves and soles")

    if not QUICK:
        whole = []
        for label, cname in (("FRONT", "WSK_Cam_Sil_Front_01"),
                             ("REAR", "WSK_Cam_Sil_Rear_01"),
                             ("LEFT", "WSK_Cam_Sil_Left_01"),
                             ("RIGHT", "WSK_Cam_Sil_Right_01")):
            p = os.path.join(OUT, f"figure_{label.lower()}.png")
            render(bpy.data.objects[cname], p, (520, 850))
            whole.append((label, p))
        sheet(whole, os.path.join(OUT, "limb_armor_four_directions.png"), 4,
              "Prompt 9 — neutral standing pose, all four orthographic directions")

    # Approximate armour-only joint rotations. The base body remains unrigged by
    # design, so each shot isolates the relevant armour chain.
    pose_cam = camera("TMP_Limb_PoseSide", (2.8, 0.0, 1.0), (0.30, 0.0, 1.0), 0.55)
    poses = []

    reset_pose()
    bpy.data.objects["WSK_LimbPose_Forearm_R_01"].rotation_euler.x = math.radians(20)
    bpy.data.objects["WSK_LimbPose_ElbowCop_R_01"].rotation_euler.x = math.radians(10)
    bpy.context.view_layer.update()
    pose_cam.location = (2.8, 0.0, 1.28); look_at(pose_cam, (0.31, 0.0, 1.28)); pose_cam.data.ortho_scale = 0.55
    states = set_only(limb_names("R", "arm"))
    p = os.path.join(OUT, "pose_elbow_20.png"); render(pose_cam, p, (560, 560)); restore(states)
    poses.append(("ELBOW +20° / COP +10°", p))

    bpy.data.objects["WSK_LimbPose_Hand_R_01"].rotation_euler.x = math.radians(-12)
    bpy.context.view_layer.update()
    pose_cam.location = (2.8, 0.0, 1.00); look_at(pose_cam, (0.31, 0.10, 1.00)); pose_cam.data.ortho_scale = 0.44
    states = set_only(limb_names("R", "hand"))
    p = os.path.join(OUT, "pose_wrist_12.png"); render(pose_cam, p, (560, 560)); restore(states)
    poses.append(("WRIST −12° AFTER ELBOW", p))

    reset_pose()
    bpy.data.objects["WSK_LimbPose_Shin_R_01"].rotation_euler.x = math.radians(20)
    bpy.data.objects["WSK_LimbPose_KneeCop_R_01"].rotation_euler.x = math.radians(10)
    bpy.context.view_layer.update()
    pose_cam.location = (2.8, 0.0, 0.55); look_at(pose_cam, (0.16, 0.0, 0.55)); pose_cam.data.ortho_scale = 0.65
    states = set_only(limb_names("R", "leg"))
    p = os.path.join(OUT, "pose_knee_20.png"); render(pose_cam, p, (560, 560)); restore(states)
    poses.append(("KNEE +20° / POLEYN +10°", p))

    bpy.data.objects["WSK_LimbPose_Foot_R_01"].rotation_euler.x = math.radians(-12)
    bpy.context.view_layer.update()
    pose_cam.location = (2.8, 0.0, 0.18); look_at(pose_cam, (0.22, 0.06, 0.16)); pose_cam.data.ortho_scale = 0.44
    states = set_only(limb_names("R", "foot"))
    p = os.path.join(OUT, "pose_ankle_12.png"); render(pose_cam, p, (560, 560)); restore(states)
    poses.append(("ANKLE −12° AFTER KNEE", p))

    reset_pose()
    sheet(poses, os.path.join(OUT, "limb_armor_joint_poses.png"), 2,
          "Prompt 9 — armour-only manual joint rotation checks (no body rig)")


if __name__ == "__main__":
    main()
