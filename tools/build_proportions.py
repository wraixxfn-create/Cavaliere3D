"""Prompt 2 — proportion guide + mannequin for the "Wildshift Knight".

Opens `Wildshift_Knight_01.blend` (the Prompt 1 project), adds a measured
proportion sheet, an edit-friendly mannequin blockout and a set of reference
guides, then saves `Wildshift_Knight_02_Proportions.blend`.

Deliberately NOT created here: armour, spikes, chains, ornaments, cape cloth,
weapon geometry, rig, any modifier, any procedural detail. The mannequin is
blockout geometry only, built so that proportions can be changed per part.

All numbers live in the PARAMS block below so they can be re-tuned in one place
and re-run; every value is annotated *measured* (read off the reference) or
*assumed* (not supported by the reference, see
analysis/reference_measurements.md).

Run:  tools/bl.sh tools/build_proportions.py
"""
import math
import os

import bpy          # must be imported first: it sets up the module search path
import bmesh        # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_01.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_02_Proportions.blend")

# --------------------------------------------------------------------------
# PARAMS — proportion sheet (metres, Z-up, ground at Z = 0, character faces +Y)
# --------------------------------------------------------------------------
P = {
    # ---- overall -------------------------------------------------------
    "height_total": 2.00,        # ground -> top of helmet dome            (measured)

    # ---- head / neck ---------------------------------------------------
    "z_helmet_top": 2.00,        # (measured)
    "z_chin": 1.74,              # (measured) hood bottom
    "head_w": 0.19,              # helmet width                            (measured)
    "head_d": 0.24,              # helmet depth incl. beak                 (assumed)
    "neck_w": 0.115,             # (assumed)
    "neck_d": 0.115,             # (assumed)
    "z_neck_top": 1.78,          # (assumed)
    "z_neck_bottom": 1.68,       # (assumed)

    # ---- torso ---------------------------------------------------------
    "z_shoulder": 1.63,          # shoulder joint height                   (assumed = 0.815 h)
    "shoulder_x": 0.20,          # joint centre from centreline            (assumed)
    "shoulder_ball_half": 0.03,  # deltoid cap half extent along X         (derived
                                 #   so body shoulder width = 0.46 m, measured)
    "shoulder_ball_w": 0.135,    # deltoid cap depth                       (assumed)
    "shoulder_ball_d": 0.075,    # deltoid cap height: top lands on the body
                                 #   shoulder line at Z 1.6675             (measured)
    "arm_drop": 0.03,            # arm starts below the joint so the deltoid
                                 #   is the top of the shoulder            (assumed)
    "chest_w_top": 0.40,         # body width at armpit line               (assumed)
    "chest_w_bot": 0.32,         # (assumed)
    "chest_d_top": 0.30,         # (assumed)
    "chest_d_bot": 0.26,         # (assumed)
    "z_chest_top": 1.68,         # (measured shoulder line)
    "z_chest_bot": 1.42,         # (assumed)
    "waist_w": 0.30,             # (assumed; armour reads 0.19 m)          armour narrower
    "waist_d": 0.24,             # (assumed)
    "z_waist": 1.22,             # (assumed)
    "pelvis_w_top": 0.32,        # (assumed)
    "pelvis_w_bot": 0.34,        # (assumed)
    "pelvis_d_top": 0.26,        # (assumed)
    "pelvis_d_bot": 0.27,        # (assumed)
    "z_pelvis_bot": 1.00,        # (assumed; hip joint line)
    "z_crotch": 0.97,            # (assumed = 0.485 h)

    # ---- arms (neutral A-pose; the reference pose is asymmetric) --------
    "hip_x": 0.10,               # (assumed)
    "upperarm_len": 0.34,        # (assumed)
    "upperarm_w_top": 0.15, "upperarm_w_bot": 0.125,   # (assumed)
    "upperarm_d_top": 0.17, "upperarm_d_bot": 0.13,    # (assumed)
    "arm_out_deg": 20.0,         # upper arm away from vertical            (assumed;
                                 #   the reference's relaxed arm hangs at ~18 deg)
    "forearm_len": 0.30,         # (assumed)
    "forearm_w_top": 0.125, "forearm_w_bot": 0.10,     # (assumed)
    "forearm_d_top": 0.13, "forearm_d_bot": 0.105,     # (assumed)
    "forearm_in_deg": 8.0,       # forward tilt of forearm                 (assumed)
    "hand_len": 0.20, "hand_w": 0.105, "hand_d": 0.075,  # (assumed, block only)

    # ---- legs ----------------------------------------------------------
    "knee_x": 0.155,             # (assumed) slight outward splay
    "ankle_x": 0.215,            # (measured) sabaton centres ±0.20-0.24
    "z_knee": 0.55,              # (assumed; robe hides knees)
    "z_ankle": 0.115,            # (assumed)
    "knee_y": 0.010,             # (assumed)
    "ankle_y": -0.010,           # (assumed)
    "thigh_w_top": 0.20, "thigh_w_bot": 0.16,          # (assumed)
    "thigh_d_top": 0.22, "thigh_d_bot": 0.165,         # (assumed)
    "shin_w_top": 0.155, "shin_w_bot": 0.115,          # (assumed)
    "shin_d_top": 0.175, "shin_d_bot": 0.125,          # (assumed)
    "foot_len": 0.30,            # (assumed; side view reads 0.15-0.25)
    "foot_w": 0.135,             # (assumed)
    "foot_h": 0.105,             # (assumed)
    "foot_yaw_deg": 15.0,        # (measured) toes splayed outward
    "foot_back": 0.09,           # heel behind ankle                       (assumed)

    # ---- cape (guide envelope only, no cloth) --------------------------
    "cape_attach_z": 1.60,       # (measured) top edge over the shoulders
    "cape_attach_x": 0.22,       # (measured)
    "cape_max_half_w": 0.55,     # (measured) solid-cloth max half width
    "cape_max_w_z": 0.75,        # (measured) height of widest point
    "cape_hem_z": 0.06,          # (measured) solid hem above ground
    "cape_hem_half_w": 0.48,     # (measured)
    "cape_back_y": -0.72,        # (measured) rear extent, mid
    "cape_back_y_hem": -0.63,    # (measured)
    "cape_front_y": 0.08,        # (assumed) front edge at the shoulders

    # ---- weapon (guide envelope only, no sword geometry) ---------------
    "weapon_len": 1.39,          # (measured) pommel top -> tip
    "weapon_x": 0.36,            # (measured) off-centre, character's left
    "weapon_y": 0.06,            # (assumed)
    "weapon_z_tip": 0.01,        # (measured)
    "weapon_cross_z": 1.13,      # (measured)
    "weapon_cross_span": 0.19,   # (measured)
    "weapon_blade_w": 0.05,      # (measured)
    "weapon_grip_w": 0.05,       # (assumed)
    "refpose_grip_z": 1.30,      # (measured) reference-pose hand height
}

# --------------------------------------------------------------------------
# Per-image reference calibration.
#
# (object name, path, X position of the backdrop, helmet-dome top as a fraction
#  of image height, ground contact as a fraction of image height)
#
# Every supplied image is its own render with its own framing, so the 2 m scale
# is re-derived per image. The helmet dome is the landmark that sets the body
# height; the crown spikes above it are decoration and are not part of the 2 m.
# Readings were taken from grid overlays (tools/crop_grid.py) and checked
# against the contact sheet. Uncertainty on the head-top landmark alone is
# about +-5 %, see analysis/reference_measurements.md.
# --------------------------------------------------------------------------
REFERENCE_VIEWS = [
    ("WSK_Ref_View_Front", "reference/ref_front.png", -4.6, 0.075, 0.887),
    ("WSK_Ref_View_Back", "reference/ref_back.png", -2.3, 0.080, 0.887),
    ("WSK_Ref_View_Side", "reference/ref_side.png", 0.0, 0.064, 0.897),
    ("WSK_Ref_View_ThreeQuarter", "reference/ref_threequarter.png", 2.3, 0.064, 0.897),
    # the contact sheet is a 2x2 collage: full image height = two panels, so the
    # front panel's fractions are halved
    ("WSK_Ref_Sheet_4Views", "reference/ref_4view_grid_original.png", 4.6,
     0.120 / 2.0, 0.907 / 2.0),
]


# --------------------------------------------------------------------------
# geometry helpers (world-space meshes, identity object transforms)
# --------------------------------------------------------------------------

def profile(segs):
    """Unit profile: segs=4 -> rectangle corners, segs=8 -> octagon."""
    if segs == 4:
        return [(1, 1), (-1, 1), (-1, -1), (1, -1)]
    return [(math.cos(2 * math.pi * i / segs), math.sin(2 * math.pi * i / segs))
            for i in range(segs)]


def prism(a, b, wa, da, wb=None, db=None, segs=4, up_hint=(0, 1, 0)):
    """Tapered prism from a to b. `w` = extent along the side axis (X-ish),
    `d` = extent along the up axis (Y-ish for vertical parts)."""
    a, b = Vector(a), Vector(b)
    wb = wa if wb is None else wb
    db = da if db is None else db
    axis = (b - a).normalized()
    up = Vector(up_hint)
    if abs(axis.dot(up)) > 0.999:
        up = Vector((1, 0, 0))
    side = axis.cross(up).normalized()
    up = side.cross(axis).normalized()
    prof = profile(segs)
    verts = []
    for point, w, d in ((a, wa, da), (b, wb, db)):
        for u, v in prof:
            verts.append(point + side * (u * w / 2.0) + up * (v * d / 2.0))
    n = len(prof)
    faces = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    faces.append(tuple(range(n)))
    faces.append(tuple(range(2 * n - 1, n - 1, -1)))
    return verts, faces


class Builder:
    """Accumulates prisms into one mesh."""

    def __init__(self):
        self.verts, self.faces = [], []

    def add(self, a, b, wa, da, wb=None, db=None, segs=4, up_hint=(0, 1, 0)):
        verts, faces = prism(a, b, wa, da, wb if wb is not None else wa,
                             db if db is not None else da, segs, up_hint)
        off = len(self.verts)
        self.verts += verts
        self.faces += [tuple(i + off for i in f) for f in faces]
        return self

    def add_bar_x(self, x0, x1, y, z, h, thick=0.015):
        """Bar running along X, sitting at height `z` (XZ plane)."""
        return self.add((x0, y, z), (x1, y, z), h, thick, segs=4, up_hint=(0, 0, 1))

    def add_bar_z(self, z0, z1, x, y, w=0.012, thick=0.012):
        """Vertical bar from z0 to z1."""
        return self.add((x, y, z0), (x, y, z1), w, thick, segs=4, up_hint=(0, 1, 0))

    def add_bar_y(self, y0, y1, x, z, w=0.012, thick=0.012):
        """Bar running along Y (depth)."""
        return self.add((x, y0, z), (x, y1, z), w, thick, segs=4, up_hint=(0, 0, 1))

    def add_frame_xz(self, x0, x1, z0, z1, y, thick=0.012):
        """Hollow rectangle outline lying in the XZ plane at depth `y`."""
        self.add_bar_x(x0, x1, y, z0, thick, thick)
        self.add_bar_x(x0, x1, y, z1, thick, thick)
        self.add_bar_z(z0, z1, x0, y, thick, thick)
        self.add_bar_z(z0, z1, x1, y, thick, thick)
        return self

    def add_frame_yz(self, x, y0, y1, z0, z1, thick=0.012):
        """Hollow rectangle outline lying in the YZ plane (a side-view card)."""
        self.add_bar_y(y0, y1, x, z0, thick, thick)
        self.add_bar_y(y0, y1, x, z1, thick, thick)
        self.add((x, y0, z0), (x, y0, z1), thick, thick, segs=4, up_hint=(0, 1, 0))
        self.add((x, y1, z0), (x, y1, z1), thick, thick, segs=4, up_hint=(0, 1, 0))
        return self


def make_object(name, verts, faces, collection, material=None, props=None,
                parent=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata([tuple(v) for v in verts], [], [list(f) for f in faces])
    mesh.validate(verbose=False)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    collection.objects.link(obj)
    if material is not None:
        obj.data.materials.append(material)
    if props:
        for key, value in props.items():
            obj[key] = value
    if parent is not None:
        obj.parent = parent
        obj.matrix_parent_inverse = Matrix.Identity(4)
    return obj


def get_collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def get_material(name, rgba, roughness=0.8):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = 0.0
    mat.diffuse_color = rgba
    mat.roughness = roughness
    return mat


def purge(prefixes):
    """Idempotent re-runs: drop objects and orphan meshes made by this script."""
    for obj in [o for o in bpy.data.objects if o.name.startswith(tuple(prefixes))]:
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.curves, bpy.data.images):
        for block in [b for b in coll if b.users == 0 and b.name.startswith(tuple(prefixes))]:
            coll.remove(block)


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------
def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    scene = bpy.context.scene

    blockout = get_collection("Blockout")
    reference = get_collection("Reference")

    purge(["WSK_Mann_", "WSK_Guide_", "WSK_Joint_", "WSK_Ref_", "WSK_Label_"])

    mat_body = get_material("MAT_Mann_NeutralGrey_01", (0.42, 0.43, 0.45, 1.0), 0.85)
    mat_ends = get_material("MAT_Mann_NeutralLight_01", (0.68, 0.68, 0.70, 1.0), 0.85)
    mat_guide = get_material("MAT_Guide_Red_01", (0.62, 0.06, 0.06, 1.0), 0.6)
    mat_silh = get_material("MAT_Guide_Blue_01", (0.05, 0.20, 0.70, 1.0), 0.6)
    mat_weap = get_material("MAT_Guide_Gold_01", (0.55, 0.40, 0.08, 1.0), 0.6)

    root = bpy.data.objects.new("WSK_Mann_Root", None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.3
    root.location = (0.0, 0.0, 0.0)
    blockout.objects.link(root)
    root["wsk_role"] = "Parent of every mannequin part. Origin = character origin."

    parts = {}

    def part(key, name, builder, material, props):
        obj = make_object(name, builder.verts, builder.faces, blockout, material,
                          props=props, parent=root)
        parts[key] = obj
        return obj

    # ---------------- torso ----------------
    b = Builder().add((0, 0, P["z_pelvis_bot"]), (0, 0.005, P["z_waist"]),
                      P["pelvis_w_bot"], P["pelvis_d_bot"],
                      P["pelvis_w_top"], P["pelvis_d_top"], segs=4)
    part("pelvis", "WSK_Mann_Pelvis_01", b, mat_body,
         {"wsk_part": "pelvis", "wsk_confidence": "assumed (hidden by robe)"})

    b = Builder().add((0, 0.005, P["z_waist"]), (0, 0, P["z_chest_bot"]),
                      P["waist_w"], P["waist_d"], P["waist_w"] + 0.01,
                      P["waist_d"] + 0.01, segs=4)
    part("abdomen", "WSK_Mann_Abdomen_01", b, mat_body,
         {"wsk_part": "abdomen / waist", "wsk_confidence": "assumed"})

    b = Builder().add((0, 0, P["z_chest_bot"]), (0, 0, P["z_chest_top"]),
                      P["chest_w_bot"], P["chest_d_bot"],
                      P["chest_w_top"], P["chest_d_top"], segs=8)
    part("chest", "WSK_Mann_Chest_01", b, mat_body,
         {"wsk_part": "chest / ribcage", "wsk_confidence": "assumed"})

    b = Builder().add((0, 0, P["z_neck_bottom"]), (0, 0, P["z_neck_top"]),
                      P["neck_w"], P["neck_d"], segs=8)
    part("neck", "WSK_Mann_Neck_01", b, mat_ends,
         {"wsk_part": "neck", "wsk_confidence": "assumed"})

    b = Builder().add((0, 0.012, P["z_chin"]), (0, 0.012, P["z_helmet_top"]),
                      P["head_w"], P["head_d"], P["head_w"] * 0.92,
                      P["head_d"] * 0.94, segs=8)
    part("head", "WSK_Mann_HeadPlaceholder_01", b, mat_ends,
         {"wsk_part": "head placeholder (helmet blank, no anatomy)",
          "wsk_confidence": "measured envelope"})

    # ---------------- shoulders + arms (mirrored, intentional A-pose) ----
    out = math.radians(P["arm_out_deg"])
    fin = math.radians(P["forearm_in_deg"])
    for side, sgn in (("R", 1.0), ("L", -1.0)):
        sh = Vector((sgn * P["shoulder_x"], 0.0, P["z_shoulder"]))
        # deltoid cap. Half extent chosen so that the body's outer shoulder
        # width lands on the measured pauldron plate width (0.46 m), the
        # shoulders being the one body dimension the armour actually reveals.
        ball_half = P["shoulder_ball_half"]
        b = Builder()
        verts, faces = prism(sh - Vector((sgn * ball_half, 0, 0)),
                             sh + Vector((sgn * ball_half, 0, 0)),
                             P["shoulder_ball_w"], P["shoulder_ball_d"],
                             segs=8, up_hint=(0, 1, 0))
        b.verts, b.faces = verts, faces
        part(f"shoulder_{side}", f"WSK_Mann_Shoulder_{side}_01", b, mat_ends,
             {"wsk_part": f"shoulder ball ({'right' if sgn > 0 else 'left'})",
              "wsk_confidence": "measured span, shape assumed"})

        arm_start = sh - Vector((0.0, 0.0, P["arm_drop"]))
        elbow = arm_start + Vector((sgn * P["upperarm_len"] * math.sin(out),
                                    -0.02,
                                    -P["upperarm_len"] * math.cos(out)))
        b = Builder().add(arm_start, elbow, P["upperarm_w_top"], P["upperarm_d_top"],
                          P["upperarm_w_bot"], P["upperarm_d_bot"], segs=8)
        part(f"upperarm_{side}", f"WSK_Mann_UpperArm_{side}_01", b, mat_body,
             {"wsk_part": f"upper arm ({'right' if sgn > 0 else 'left'})",
              "wsk_length_m": P["upperarm_len"], "wsk_confidence": "assumed"})

        wrist = elbow + Vector((-sgn * P["forearm_len"] * math.sin(fin) * 0.5,
                                P["forearm_len"] * math.sin(fin),
                                -P["forearm_len"] * math.cos(fin)))
        b = Builder().add(elbow, wrist, P["forearm_w_top"], P["forearm_d_top"],
                          P["forearm_w_bot"], P["forearm_d_bot"], segs=8)
        part(f"lowerarm_{side}", f"WSK_Mann_LowerArm_{side}_01", b, mat_body,
             {"wsk_part": f"lower arm ({'right' if sgn > 0 else 'left'})",
              "wsk_length_m": P["forearm_len"], "wsk_confidence": "assumed"})

        hand_end = wrist + Vector((0.0, P["hand_len"] * 0.35, -P["hand_len"] * 0.94))
        b = Builder().add(wrist, hand_end, P["hand_w"], P["hand_d"],
                          P["hand_w"] * 0.95, P["hand_d"] * 0.95, segs=4)
        part(f"hand_{side}", f"WSK_Mann_Hand_{side}_01", b, mat_ends,
             {"wsk_part": f"hand block ({'right' if sgn > 0 else 'left'}), no fingers",
              "wsk_length_m": P["hand_len"], "wsk_confidence": "assumed"})

    # ---------------- legs ----------------
    for side, sgn in (("R", 1.0), ("L", -1.0)):
        hip = Vector((sgn * P["hip_x"], 0.0, P["z_pelvis_bot"]))
        knee = Vector((sgn * P["knee_x"], P["knee_y"], P["z_knee"]))
        ankle = Vector((sgn * P["ankle_x"], P["ankle_y"], P["z_ankle"]))

        b = Builder().add(hip + Vector((0, 0, 0.02)), knee,
                          P["thigh_w_top"], P["thigh_d_top"],
                          P["thigh_w_bot"], P["thigh_d_bot"], segs=8)
        part(f"thigh_{side}", f"WSK_Mann_Thigh_{side}_01", b, mat_body,
             {"wsk_part": f"thigh ({'right' if sgn > 0 else 'left'})",
              "wsk_length_m": round((knee - hip).length, 4),
              "wsk_confidence": "assumed (hidden by robe)"})

        b = Builder().add(knee, ankle, P["shin_w_top"], P["shin_d_top"],
                          P["shin_w_bot"], P["shin_d_bot"], segs=8)
        part(f"lowerleg_{side}", f"WSK_Mann_LowerLeg_{side}_01", b, mat_body,
             {"wsk_part": f"lower leg ({'right' if sgn > 0 else 'left'})",
              "wsk_length_m": round((ankle - knee).length, 4),
              "wsk_confidence": "assumed"})

        # foot: block from heel to toe, splayed outward, sole flat on Z = 0.
        # The prism axis runs along the foot length at the mid-height of each
        # end, so the cross-section height means "distance from the sole".
        yaw = math.radians(-sgn * P["foot_yaw_deg"])
        rot = Matrix.Rotation(yaw, 4, "Z")

        def place(dy, mid_h):
            offset = rot @ Vector((0.0, dy, 0.0))
            return (ankle.x + offset.x, P["ankle_y"] + offset.y, mid_h)

        # two horizontal segments (ankle block + lower toe block) so that both
        # soles stay exactly on Z = 0 instead of tilting with the axis
        heel = place(-P["foot_back"], P["foot_h"] / 2)
        mid = place(-P["foot_back"] + P["foot_len"] * 0.5, P["foot_h"] / 2)
        toe = place(-P["foot_back"] + P["foot_len"], P["foot_h"] * 0.45 / 2)
        b = Builder()
        b.add(heel, mid, P["foot_w"], P["foot_h"], P["foot_w"] * 0.98, P["foot_h"],
              segs=4, up_hint=(0, 0, 1))
        b.add(mid, toe, P["foot_w"] * 0.98, P["foot_h"] * 0.45, P["foot_w"] * 0.8,
              P["foot_h"] * 0.45, segs=4, up_hint=(0, 0, 1))
        part(f"foot_{side}", f"WSK_Mann_Foot_{side}_01", b, mat_ends,
             {"wsk_part": f"foot / sabaton block ({'right' if sgn > 0 else 'left'})",
              "wsk_length_m": P["foot_len"], "wsk_yaw_deg": P["foot_yaw_deg"],
              "wsk_confidence": "length assumed, splay measured"})

    # bottom of the feet exactly on Z = 0: the sabaton prism is built with its
    # axis at the ankle height, so drop a flat sole box under each foot.
    # (kept as part of the foot objects above via foot_h offsets — verified in
    #  tools/verify_proportions.py)

    # ---------------- joints ----------------
    joints = {
        "WSK_Joint_Center_Hips": (0, 0, P["z_pelvis_bot"]),
        "WSK_Joint_Center_Waist": (0, 0, P["z_waist"]),
        "WSK_Joint_Center_Chest": (0, 0, P["z_shoulder"]),
        "WSK_Joint_Neck": (0, 0, P["z_neck_top"]),
    }
    for side, sgn in (("R", 1.0), ("L", -1.0)):
        joints[f"WSK_Joint_Shoulder_{side}"] = (sgn * P["shoulder_x"], 0, P["z_shoulder"])
        joints[f"WSK_Joint_Hip_{side}"] = (sgn * P["hip_x"], 0, P["z_pelvis_bot"])
        joints[f"WSK_Joint_Knee_{side}"] = (sgn * P["knee_x"], P["knee_y"], P["z_knee"])
        joints[f"WSK_Joint_Ankle_{side}"] = (sgn * P["ankle_x"], P["ankle_y"], P["z_ankle"])
    # elbow / wrist come from the built arm geometry so the markers cannot drift
    for side in ("R", "L"):
        for key, obj_key in (("Elbow", "upperarm"), ("Wrist", "lowerarm")):
            obj = parts[f"{obj_key}_{side}"]
            co = [obj.matrix_world @ v.co for v in obj.data.vertices]
            end = co[8:16] if key == "Elbow" else co[8:16]   # far cap of the prism
            centre = Vector((sum(c.x for c in end) / len(end),
                             sum(c.y for c in end) / len(end),
                             sum(c.z for c in end) / len(end)))
            joints[f"WSK_Joint_{key}_{side}"] = tuple(centre)

    for name, loc in joints.items():
        emp = bpy.data.objects.new(name, None)
        emp.empty_display_type = "SPHERE"
        emp.empty_display_size = 0.035
        emp.location = loc
        reference.objects.link(emp)
        emp["wsk_role"] = "joint marker (name = landmark)"

    # ---------------- guides: centreline, ruler, silhouettes, envelopes ----
    b = Builder()
    b.add_bar_z(0.0, 2.15, 0.0, 0.0, 0.012, 0.012)               # vertical centreline
    b.add_bar_x(-0.80, 0.80, 0.0, 0.002, 0.008, 0.008)           # ground line (X)
    make_object("WSK_Guide_Centerline_01", b.verts, b.faces, reference, mat_guide,
                props={"wsk_role": "vertical centreline (X=0, Y=0) + ground line at Z=0"})

    # height ruler, in the XZ plane behind the character
    b = Builder()
    # negative X so the ruler sits clear of the cape envelope (half width
    # 0.556 m) and of the weapon envelope on the +X side
    x_strip, y_r, z_top = -0.79, -0.9, 2.02
    b.add_bar_z(0.0, z_top, x_strip - 0.02, y_r, 0.02, 0.02)
    for i in range(0, 21):
        z = i * 0.1
        long_tick = (i % 5 == 0)
        # ticks point toward the body (positive X) so the labels stay clear
        b.add_bar_x(x_strip, x_strip + (0.12 if long_tick else 0.07), y_r, z,
                    0.014 if long_tick else 0.012, 0.014)
    make_object("WSK_Guide_HeightRuler_01", b.verts, b.faces, reference, mat_guide,
                props={"wsk_role": "0-2 m ruler, ticks every 0.1 m, long every 0.5 m",
                       "wsk_note": "labels WSK_Label_* are separate text objects"})

    for i in range(0, 5):
        metres = i * 0.5
        curve = bpy.data.curves.new(f"WSK_Label_{metres:.1f}m_curve", type="FONT")
        curve.body = f"{metres:.1f}"
        curve.size = 0.055
        curve.align_x = "RIGHT"
        curve.align_y = "CENTER"
        obj = bpy.data.objects.new(f"WSK_Label_{metres:.1f}m", curve)
        reference.objects.link(obj)
        # text plane faces +Y (readable from the front camera) and is mirrored
        # in X so it reads correctly in a front orthographic view
        obj.location = (x_strip + 0.20, y_r, metres)
        obj.rotation_euler = (math.radians(90), 0.0, math.radians(180))
        obj.data.materials.append(mat_guide)

    # helmet + shoulder-width silhouette card (front view)
    y_sil = -0.30
    b = Builder()
    b.add_frame_xz(-P["head_w"] / 2, P["head_w"] / 2, P["z_chin"], P["z_helmet_top"], y_sil)
    b.add_frame_xz(-0.14, 0.14, 1.79, 1.93, y_sil)               # crown ring outer
    b.add_frame_xz(-0.18, 0.18, 1.76, 2.11, y_sil)               # crown spike extent
    b.add_bar_x(-0.23, 0.23, y_sil, 1.60, 0.022, 0.014)          # shoulder (plate) width
    b.add_bar_x(-0.26, 0.26, y_sil, 1.51, 0.014, 0.014)          # spiked pauldron extent
    b.add_bar_x(-P["shoulder_x"], P["shoulder_x"], y_sil + 0.02, 1.63, 0.010, 0.010)
    make_object("WSK_Guide_Silhouette_HeadShoulders_01", b.verts, b.faces, reference,
                mat_silh, props={
                    "wsk_role": "front-view silhouette guide: helmet outline "
                                "(0.19 m), crown ring (0.28 m), spike extent (0.36 m), "
                                "shoulder plate width (0.46 m), spiked extent (0.52 m)"})

    # cape envelope (front card: max width + length; side card: depth)
    y_cape = -0.45
    b = Builder()
    b.add_frame_xz(-P["cape_max_half_w"], P["cape_max_half_w"], P["cape_hem_z"], 1.54, y_cape)
    b.add_bar_x(-P["cape_max_half_w"], P["cape_max_half_w"], y_cape + 0.02,
                P["cape_max_w_z"], 0.010, 0.010)
    b.add_bar_x(-P["cape_hem_half_w"], P["cape_hem_half_w"], y_cape + 0.02,
                P["cape_hem_z"], 0.010, 0.010)
    make_object("WSK_Guide_CapeEnvelope_Front_01", b.verts, b.faces, reference, mat_guide,
                props={"wsk_role": f"cape max width +-{P['cape_max_half_w']} m at "
                                   f"Z {P['cape_max_w_z']}, hem Z {P['cape_hem_z']}"})

    b = Builder().add_frame_yz(0.72, P["cape_back_y"], P["cape_front_y"],
                               P["cape_hem_z"], 1.54)
    make_object("WSK_Guide_CapeEnvelope_Side_01", b.verts, b.faces, reference, mat_guide,
                props={"wsk_role": f"cape depth envelope: Y {P['cape_front_y']} .. "
                                   f"{P['cape_back_y']}, Z {P['cape_hem_z']} .. 1.54"})

    # weapon envelope (guide only — no sword geometry)
    b = Builder()
    z_tip = P["weapon_z_tip"]
    z_cross = P["weapon_cross_z"]
    z_top = z_tip + P["weapon_len"]
    x_w, y_w = -P["weapon_x"], P["weapon_y"]
    b.add((x_w, y_w, z_tip), (x_w, y_w, z_cross), P["weapon_blade_w"], 0.02,
          P["weapon_blade_w"], 0.02, segs=4)
    b.add((x_w, y_w, z_cross), (x_w, y_w, z_top), P["weapon_grip_w"], 0.045,
          P["weapon_grip_w"], 0.045, segs=4)
    b.add_bar_x(x_w - P["weapon_cross_span"] / 2, x_w + P["weapon_cross_span"] / 2,
                y_w, z_cross, 0.03, 0.03)
    make_object("WSK_Guide_WeaponEnvelope_01", b.verts, b.faces, reference, mat_weap,
                props={"wsk_role": f"weapon envelope only: length {P['weapon_len']} m, "
                                   f"crossguard {P['weapon_cross_span']} m, axis vertical at "
                                   f"X {-P['weapon_x']} (character's left)",
                       "wsk_note": "no blade/crossguard ornament modelled"})

    # reference-pose targets (the reference pose is asymmetric on purpose)
    for name, loc, note in (
        ("WSK_Guide_RefPose_Grip_SwordHand", (-P["weapon_x"], P["weapon_y"], P["refpose_grip_z"]),
         "reference pose: left hand grips the sword here (arm raised, elbow bent)"),
        ("WSK_Guide_RefPose_Hand_Other", (0.28, 0.02, 0.88),
         "reference pose: right hand hangs beside the hip"),
    ):
        emp = bpy.data.objects.new(name, None)
        emp.empty_display_type = "CIRCLE"
        emp.empty_display_size = 0.06
        emp.location = loc
        reference.objects.link(emp)
        emp["wsk_role"] = note

    # ---------------- reference images (non-destructive, viewport only) ----
    # Each image is its own render with its own framing, so the empty is placed
    # and sized so that the image's own helmet-top and ground fractions land on
    # Z = 2.00 and Z = 0.00. See REFERENCE_VIEWS for the readings.
    for name, rel, x, dome_y, ground_y in REFERENCE_VIEWS:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            print("  reference image missing, skipped:", rel)
            continue
        body_frac = ground_y - dome_y
        height_m = 2.0 / body_frac                      # image height in metres
        emp = bpy.data.objects.new(name, None)
        emp.empty_display_type = "IMAGE"
        emp.empty_image_offset = (0.0, 0.0)
        emp.data = bpy.data.images.load(path, check_existing=True)
        emp.data.name = name + "_img"
        # for an image empty, empty_display_size is the size of the image along
        # its LARGEST dimension; every reference is portrait, so that is the
        # displayed height
        emp.empty_display_size = height_m
        # put the image's ground fraction on Z = 0
        emp.location = (x, -3.2, -(ground_y - 0.5) * height_m)
        reference.objects.link(emp)
        emp["wsk_role"] = (
            f"reference view '{rel}', backdrop only (image empties do not render). "
            f"Placed so the reading ground_y={ground_y:.3f} sits on Z=0 and "
            f"dome_y={dome_y:.3f} sits on Z=2.00; image height = {height_m:.3f} m.")
        emp["wsk_calibration"] = f"dome_y={dome_y} ground_y={ground_y} h={height_m:.4f}m"

    # ---------------- documentation ----------------
    if "WSK_Project_Notes.txt" in bpy.data.texts:
        notes = bpy.data.texts["WSK_Project_Notes.txt"].as_string()
    else:
        notes = ""
    notes += PROJECT_NOTES_APPEND
    bpy.data.texts["WSK_Project_Notes.txt"].from_string(notes)

    if "WSK_Proportion_Sheet.txt" in bpy.data.texts:
        bpy.data.texts.remove(bpy.data.texts["WSK_Proportion_Sheet.txt"])
    sheet = bpy.data.texts.new("WSK_Proportion_Sheet.txt")
    sheet.from_string(proportion_sheet_text())

    # ---------------- render defaults (Cycles CPU: EEVEE needs a GL context) --
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 64
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1440
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False

    # store the reference-image paths relative to the .blend so the project
    # stays portable (they resolve to //reference/*.png)
    bpy.ops.file.make_paths_relative()

    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print("SAVED", DST)

    report()


def report():
    print("\n--- mannequin parts ---")
    print(f"{'object':38s} {'min':>7s} {'max':>7s} {'dims (x,y,z)':>24s}")
    for obj in sorted((o for o in bpy.data.objects if o.name.startswith("WSK_Mann_")),
                      key=lambda o: o.name):
        if obj.type != "MESH":
            continue
        co = [obj.matrix_world @ v.co for v in obj.data.vertices]
        mn = Vector((min(c.x for c in co), min(c.y for c in co), min(c.z for c in co)))
        mx = Vector((max(c.x for c in co), max(c.y for c in co), max(c.z for c in co)))
        print(f"{obj.name:38s} {mn.z:7.3f} {mx.z:7.3f}   "
              f"{mx.x - mn.x:6.3f} {mx.y - mn.y:6.3f} {mx.z - mn.z:6.3f}   "
              f"X[{mn.x:+.3f},{mx.x:+.3f}] Y[{mn.y:+.3f},{mx.y:+.3f}]")

    mesh_objs = [o for o in bpy.data.objects if o.name.startswith("WSK_Mann_") and o.type == "MESH"]
    allco = [o.matrix_world @ v.co for o in mesh_objs for v in o.data.vertices]
    mn = Vector((min(c.x for c in allco), min(c.y for c in allco), min(c.z for c in allco)))
    mx = Vector((max(c.x for c in allco), max(c.y for c in allco), max(c.z for c in allco)))
    print(f"\nmannequin bbox  X[{mn.x:+.4f},{mx.x:+.4f}]  Y[{mn.y:+.4f},{mx.y:+.4f}]  "
          f"Z[{mn.z:+.4f},{mx.z:+.4f}]")
    print(f"ground contact: {mn.z:+.4f} m   height: {mx.z:.4f} m   "
          f"X symmetry error: {abs(mn.x + mx.x):.5f} m")
    print("\nobjects:", len(bpy.data.objects), " meshes:",
          len([o for o in bpy.data.objects if o.type == 'MESH']),
          " cages/mods:", sum(len(o.modifiers) for o in bpy.data.objects))


PROJECT_NOTES_APPEND = """


Prompt 2 - Proportions (Wildshift_Knight_02_Proportions.blend)
=============================================================
Reference views imported into the 'Reference' collection as image empties
(backdrop only - image empties do not render and are not packed, they read
../reference/*.png through a relative path).

Collections used:
  Blockout  -> WSK_Mann_*      mannequin blockout parts (21 objects + root empty)
  Reference -> WSK_Guide_*, WSK_Joint_*, WSK_Label_*, WSK_Ref_*  proportion guides

Mannequin rules:
  - every part is its own object with identity transform; all vertices are
    authored in world space, so a coordinate read in Edit mode is a world
    coordinate and X mirroring is exact.
  - no modifiers, no armature, no anatomy, no armour, no weapon geometry.
  - neutral untextured Principled materials only:
      MAT_Mann_NeutralGrey_01   torso / limbs
      MAT_Mann_NeutralLight_01  head, neck, hands, feet, shoulders
      MAT_Guide_Red_01 / MAT_Guide_Blue_01 / MAT_Guide_Gold_01   guides only
  - custom properties per part: wsk_part, wsk_confidence, wsk_length_m.

Pose: neutral A-pose, arms 30 deg out, mirrored. This is intentionally
symmetric. The reference itself is posed asymmetrically (left arm raised,
elbow ~90 deg, gripping the sword; right arm hanging) - that asymmetry is a
pose, not a proportion, so it is recorded with the empties
WSK_Guide_RefPose_* and not baked into the mannequin.

See text block 'WSK_Proportion_Sheet.txt' for the full measured/assumed table.
"""


def proportion_sheet_text():
    return f"""WILDSHIFT KNIGHT - PROPORTION SHEET (Prompt 2)
==============================================

Scale: metric, 1 unit = 1 m. Total body height {P['height_total']:.2f} m
(ground -> top of helmet dome). Helmet crown spikes reach 2.11-2.12 m and are
guide-only, they are NOT part of the body height.

The reference's four views are AI renders: perspective, inconsistent between
views, and the body is hidden under armour and cloth. Values below are marked
  [m] measured off the reference (analysis/reference_measurements.md)
  [a] assumed - not supported by the reference, standard 2 m human proportion

HEIGHT / Z (ground = 0)                 VALUE   NOTE
  ground contact (sole)                 0.000   [m] front view y 88.7%
  crown spike tips                      2.11    [m] guide only
  helmet dome top = body height         2.00    [m]
  skull top inside hood                 1.86    [m]
  eyes                                  1.77    [m]
  chin / hood bottom                    1.74    [m]
  neck top                              1.78    [a]
  shoulder joint                        1.63    [a] 0.815 h
  chest top / shoulder line             1.68    [m]
  chest bottom                          1.42    [a]
  waist bend                            1.22    [a]
  pelvis bottom / hip joint             1.00    [a] 0.50 h
  crotch                                0.97    [a] 0.485 h
  knee                                  0.55    [a] robe hides the knees
  ankle                                 0.115   [a]
  sabaton top                           0.105   [a]
  cape attach (over shoulders)          1.60    [m]
  cape hem (solid cloth)                0.06    [m] fray reaches the floor
  sword tip                             0.01    [m]
  sword crossguard                      1.13    [m]
  sword grip centre (reference pose)    1.30    [m]

WIDTHS (full X extent)                  VALUE   NOTE
  head / helmet                         0.19    [m] widest solid read
  crown ring outer                      0.28    [m]
  crown spike extent                    0.36    [m]
  neck                                  0.115   [a]
  shoulders, body (joint to joint)      0.40    [a]
  pauldron plate outer                  0.46    [m]
  pauldron incl. spikes                 0.52    [m]
  chest (armpit line)                   0.40    [a]
  waist (cinched armour reads 0.19)     0.30    [a]
  pelvis                                0.34    [a]
  hip joints                            0.20    [a] +-0.10
  knee joints                           0.31    [a] +-0.155
  ankle / sabaton centres               0.43    [a] +-0.215 (front view 0.40-0.48)
  foot block                            0.135   [a]
  upper arm (top -> elbow)              0.150 -> 0.125   [a]
  lower arm (elbow -> wrist)            0.125 -> 0.100   [a]
  hand block                            0.105   [a] no fingers
  thigh (top -> knee)                   0.200 -> 0.160   [a]
  lower leg (knee -> ankle)             0.155 -> 0.115   [a]
  cape max (solid cloth)                1.10    [m] +-0.55 at Z 0.75
  cape incl. frayed tips                1.15    [m]
  sword crossguard span                 0.19    [m]
  sword blade                           0.05    [m]

DEPTHS (full Y extent, +Y = forward)    VALUE   NOTE
  head / helmet                         0.24    [a]
  neck                                  0.115   [a]
  chest (top -> bottom)                 0.30 -> 0.26     [a]
  waist                                 0.24    [a]
  pelvis                                0.26    [a]
  thigh                                 0.22 -> 0.165    [a]
  lower leg                             0.175 -> 0.125   [a]
  foot block                            0.30 length      [a] side view reads 0.15-0.25
  cape front edge at shoulders          +0.08   [a]
  cape rear extent (mid / hem)          -0.72 / -0.63    [m]

ARMS AND LEGS (lengths)                 VALUE   NOTE
  shoulder -> elbow                     0.34    [a]
  elbow -> wrist                        0.30    [a]
  wrist -> fingertips                   0.20    [a] block, no fingers
  hip -> knee (thigh)                   0.45    [a]
  knee -> ankle (shank)                 0.44    [a]
  total arm (shoulder -> fingertip)     0.84    [a] 0.42 h
  total leg (hip -> sole)               1.00    [a] 0.50 h
  cape length (shoulder -> hem)         1.54    [m]
  weapon length (pommel -> tip)         1.39    [m]

ANGLES / POSE
  upper arm from vertical (A-pose)      30 deg  [a] neutral mannequin pose
  forearm forward tilt                  8 deg   [a]
  foot splay (toes outward)             15 deg  [m]
  spine                                 0 deg   [a] upright
  reference pose, sword arm             left arm, elbow bent ~90 deg, wrist at
                                        Z 1.30 / X -0.36, hand beside the hip on
                                        the other side at Z 0.88 / X +0.28

CALIBRATION AND ITS UNCERTAINTY
  The 2 m scale is anchored on two landmarks per image: the top of the helmet
  dome and the ground contact under the feet. Both are read off grid overlays
  (tools/crop_grid.py) and are the largest single source of error:
    front   dome y 7.5 %   ground y 88.7 %   ->  1.904 mm/px
    back    dome y 8.0 %   ground y 88.7 %   ->  1.883 mm/px
    side    dome y 6.4 %   ground y 89.7 %   ->  1.868 mm/px
  Cross-check: the front panel of the supplied contact sheet gives dome 12.0 %
  and ground 90.7 % of its panel (78.7 % of the panel height for a 2 m body)
  against 81.2 % from the standalone front render - a 3 % disagreement between
  two versions of the same render.
  The helmet apex itself is ambiguous: the hood/dome crown sits at y ~9.5-12 %
  while a thin helmet spike continues to y ~8.5 % and crown-ring spikes to
  y ~5 %. Choosing the spike instead of the dome as "the top of the body"
  would shrink every measurement below by about 5 %. Treat all lengths here as
  +-5 % unless marked otherwise, and +-10 % for anything taken from the side
  view.

UNCERTAINTIES (do not treat as fact)
  1. No orthographic reference exists; every view is a perspective AI render
     with a low camera, so verticals above mid-image read large and the
     pauldrons/head are systematically overstated.
  2. The body under the armour is invisible: torso taper, waist, hips, knees
     and ankles are assumed human proportions, not measured. Of the 30-odd
     widths in the table, only 8 are marked [m].
  3. Torso depth, foot length and cape depth come from a single perspective
     side view and are the least reliable numbers here.
  4. The back view is mirrored relative to the front (sword appears on the
     character's right); the front view was treated as authoritative, giving
     the sword to the LEFT hand.
  5. Cape width/length: the envelope uses the solid cloth; the frayed tips
     spread wider (1.15 m) and reach the floor.
  6. Crown spikes, chains and ornaments are deliberately not measured - they
     are detail, not proportion, and are out of scope for this step.
  7. The pose in the reference is asymmetric (left arm up, elbow bent, gripping
     the sword; right arm hanging). The mannequin is built in a neutral,
     mirrored A-pose because pose is not proportion; the reference pose is
     recorded with the empties WSK_Guide_RefPose_* instead.
  8. The shoulder reading comes from armour, not from the body: 0.46 m is the
     pauldron plate width at Z 1.60 and 0.52-0.54 m is the spiked lame extent
     around Z 1.35. The mannequin's body shoulder width was set to 0.46 m on
     that evidence, so shoulder width is partly a measurement and partly a
     decision.
"""


if __name__ == "__main__":
    main()
