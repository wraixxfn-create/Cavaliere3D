"""Prompt 9 - refine arm, hand, leg and foot armour.

The script opens checkpoint 08, removes only the ten Prompt-5 limb placeholders,
and replaces them with layered, closed armour parts.  The torso, shoulder,
helmet, body, proportions and scene setup are preserved.  Empty objects provide
manual pose pivots and future attachment hints; they are not a rig.

Run: tools/bl.sh tools/build_limb_armor.py
"""
import math
import os
import sys

import bpy  # noqa: F401
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import build_armor_blockout as A  # noqa: E402

SRC = os.path.join(ROOT, "Wildshift_Knight_08_TorsoArmor.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_09_LimbArmor.blend")
PROMPT = "Prompt 9 - refined limb armour"
BODY = "WSK_Body_Base_01"

# Approved body landmarks from Prompts 2/3.  Nothing in this script changes the
# body or these proportions.
J = A.JOINTS

LEGACY = [
    f"WSK_Armor_{part}_{side}_01"
    for side in ("R", "L")
    for part in ("Forearm", "Gauntlet", "Thigh", "Shin", "Sabaton")
]


def set_props(obj, part, attachment, note, overlap="", helper=False):
    obj["wsk_part"] = part
    obj["wsk_attachment_hint"] = attachment
    obj["wsk_prompt"] = PROMPT
    obj["wsk_note"] = note
    obj["wsk_overlap_direction"] = overlap or "not an overlapping plate"
    obj["wsk_major_segment"] = True
    obj["wsk_requires_helper_bone"] = bool(helper)
    obj["wsk_neutral_pose"] = True
    bevels = [m.width for m in obj.modifiers if m.type == "BEVEL"]
    if bevels:
        obj["wsk_bevel_mm"] = round(bevels[0] * 1000.0, 2)


def parent_keep_world(obj, parent):
    """Parent to a meaningful joint pivot without moving world-space geometry."""
    # Newly-created empties do not have an evaluated matrix_world until the
    # dependency graph updates. Preserve the evaluated world matrix explicitly;
    # otherwise each authored world-space mesh is translated by its joint twice.
    bpy.context.view_layer.update()
    world = obj.matrix_world.copy()
    obj.parent = parent
    bpy.context.view_layer.update()
    obj.matrix_parent_inverse = parent.matrix_world.inverted()
    obj.matrix_world = world
    bpy.context.view_layer.update()


def make_root(name, position, collection, parent=None, display="CIRCLE"):
    root = bpy.data.objects.new(name, None)
    collection.objects.link(root)
    root.location = Vector(position)
    root.empty_display_type = display
    root.empty_display_size = 0.035
    root.show_in_front = True
    root["wsk_prompt"] = PROMPT
    root["wsk_control_type"] = "manual pose / future bone attachment pivot; not a rig"
    root["wsk_rest_location"] = tuple(float(x) for x in position)
    if parent:
        parent_keep_world(root, parent)
    return root


def ray_body(tree, centre, radial, label, radius=0.18):
    """Find the outward body surface along a local radial direction."""
    radial = Vector(radial).normalized()
    origin = Vector(centre) + radial * radius
    hit = tree.ray_cast(origin, -radial, radius * 2.0)
    if hit[0] is None:
        raise RuntimeError(f"Body-fit ray missed for {label}")
    point, normal = Vector(hit[0]), Vector(hit[1]).normalized()
    # The source body is a consistently outward-wound closed manifold. Trust
    # its normal near branch regions: a cylinder-radial vector can point into
    # the torso at the armpit/groin and would push a plate through the body.
    return point, normal


def plate_material(layer_index, steel, iron):
    # Broad first plates use iron; subordinate lames use blackened steel.  The
    # restrained alternation keeps all four limbs in one visual language.
    return iron if layer_index == 0 else steel


def build_swept_plate(tree, name, distal, proximal, t0, t1, sign,
                       inner_span, outer_span, clearance, thickness,
                       material, collection, rows=8, cols=21,
                       ridge=0.004, distal_point=0.0, bevel=0.00115):
    """Build one front/side limb plate as a closed, body-fitted shell.

    Coordinates run distal -> proximal.  A small centre-front point on the
    distal edge creates the repeated gothic V used throughout the limb set.
    """
    distal, proximal = Vector(distal), Vector(proximal)
    axis, right, front = A.limb_frame(proximal - distal)
    if sign > 0:
        amin, amax = -inner_span, outer_span
    else:
        amin, amax = -outer_span, inner_span
    outer, normals = [], []
    for ri in range(rows):
        v = ri / (rows - 1)
        row, nr = [], []
        for ci in range(cols):
            u = ci / (cols - 1)
            theta = math.radians(amin + (amax - amin) * u)
            # A shallow down-point at the centre/front; side edges stay high so
            # joints remain clear and plate ends do not form fragile needles.
            frontness = max(0.0, math.cos(theta)) ** 3.0
            edge_t0 = t0 - distal_point * frontness
            t = edge_t0 + (t1 - edge_t0) * v
            centre = distal.lerp(proximal, t)
            radial = (right * math.sin(theta) + front * math.cos(theta)).normalized()
            hit, normal = ray_body(tree, centre, radial,
                                   f"{name} row {ri} col {ci}")
            crown = ridge * (max(0.0, math.cos(theta)) ** 7.0)
            crown *= 0.30 + 0.70 * math.sin(math.pi * v) ** 0.55
            # Rolled exposed lip: enough to catch a highlight, still broad.
            lip = 0.0015 * (1.0 - v) ** 3.0 * frontness
            row.append(hit + normal * (clearance + crown + lip))
            nr.append(normal)
        outer.append(row)
        normals.append(nr)
    obj = A.make_closed_shell(name, outer, normals, collection, material,
                              thickness=thickness, bevel=bevel)
    return obj


def build_joint_cop(tree, name, joint, axis, sign, half_length, material,
                    collection, span_inner=66.0, span_outer=82.0,
                    clearance=0.024, thickness=0.0052, bevel=0.00135):
    """Separate knee/elbow cop with a broad central keel and short side wings."""
    axis = Vector(axis).normalized()
    distal = Vector(joint) - axis * half_length
    proximal = Vector(joint) + axis * half_length
    obj = build_swept_plate(
        tree, name, distal, proximal, 0.0, 1.0, sign,
        span_inner, span_outer, clearance, thickness, material, collection,
        rows=8, cols=21, ridge=0.0060, distal_point=0.08, bevel=bevel,
    )
    return obj


def hand_centre(sign, z):
    # Follows the Prompt-3 neutral hand centreline (slightly inward at the tips).
    return sign * (0.285 + 0.070 * (z - 0.835))


def hand_patch(tree, name, sign, z_top, z_bottom, half_top, half_bottom,
               clearance, thickness, material, collection, rows=7, cols=9,
               x_offset=0.0, tip=0.0, bevel=0.0008):
    """Closed dorsal hand/finger plate sampled from the real mitten body."""
    outer, normals = [], []
    for ri in range(rows):
        v = ri / (rows - 1)
        row, nr = [], []
        for ci in range(cols):
            u = -1.0 + 2.0 * ci / (cols - 1)
            z = z_top + (z_bottom - z_top) * v
            if ri == rows - 1:
                z -= tip * (1.0 - abs(u))
            half = half_top + (half_bottom - half_top) * v
            x = hand_centre(sign, z) + x_offset + u * half
            origin = Vector((x, 0.32, z))
            hit = tree.ray_cast(origin, Vector((0.0, -1.0, 0.0)), 0.55)
            if hit[0] is None:
                # The mitten has a small concave thumb/palm notch.  Boundary
                # samples can pass through that notch; snap those few points to
                # the nearest real surface rather than bridging empty space.
                nearest = tree.find_nearest(Vector((x, 0.095, z)))
                if nearest[0] is None or nearest[3] > 0.028:
                    raise RuntimeError(f"Hand-fit ray missed for {name} at {x:.4f}, {z:.4f}")
                nearest_point = Vector(nearest[0])
                # Preserve the structured plate grid in X/Z.  Snapping all
                # coordinates to the concave mitten notch can collapse adjacent
                # samples into sub-millimetre edges.
                point = Vector((x, nearest_point.y, z))
                normal = Vector(nearest[1]).normalized()
            else:
                point, normal = Vector(hit[0]), Vector(hit[1]).normalized()
            # Gauntlet plates are deliberately dorsal rather than a full glove.
            # A stable +Y construction normal prevents the concave thumb notch
            # from flipping isolated samples back through the hand.
            normal = Vector((0.0, 1.0, 0.0))
            ridge = 0.0018 * (1.0 - abs(u)) ** 3 * math.sin(math.pi * v)
            row.append(point + normal * (clearance + ridge))
            nr.append(normal)
        outer.append(row)
        normals.append(nr)
    return A.make_closed_shell(name, outer, normals, collection, material,
                               thickness=thickness, bevel=bevel)


def foot_profile(q):
    """Sabaton half-width/top profile; q is distance forward from the ankle."""
    keys = [
        (0.010, 0.058, 0.108),
        (0.040, 0.064, 0.091),
        (0.075, 0.068, 0.073),
        (0.110, 0.068, 0.057),
        (0.145, 0.063, 0.043),
        (0.175, 0.052, 0.034),
        (0.198, 0.032, 0.028),
    ]
    if q <= keys[0][0]:
        return keys[0][1], keys[0][2]
    if q >= keys[-1][0]:
        return keys[-1][1], keys[-1][2]
    for a, b in zip(keys[:-1], keys[1:]):
        if a[0] <= q <= b[0]:
            f = (q - a[0]) / (b[0] - a[0])
            return a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f
    raise AssertionError


def build_foot_plate(tree, name, side, sign, q0, q1, clearance,
                     thickness, material, collection, rows=7, cols=17,
                     bevel=0.0009):
    """One dorsal/side sabaton lame, open underneath but closed as a solid."""
    angle = math.radians(15.0 if sign > 0 else -15.0)
    longitudinal = Vector((math.sin(angle), math.cos(angle), 0.0))
    across = Vector((math.cos(angle), -math.sin(angle), 0.0))
    ankle = Vector(J[f"ankle_{side}"])
    end = math.radians(122.0)
    outer, normals = [], []
    for ri in range(rows):
        v = ri / (rows - 1)
        q = q0 + (q1 - q0) * v
        width, top_z = foot_profile(q)
        # Side edge stays above the separate sole and leaves a readable welt.
        bottom_z = 0.018
        half_h = (top_z - bottom_z) / max(0.20, 1.0 - math.cos(end))
        centre_z = top_z - half_h
        centre = ankle + longitudinal * q
        row, nr = [], []
        for ci in range(cols):
            phi = -end + 2.0 * end * ci / (cols - 1)
            sn, cs = math.sin(phi), math.cos(phi)
            guess_xy = centre + across * (width * sn)
            guess = Vector((guess_xy.x, guess_xy.y, centre_z + half_h * cs))
            radial = Vector((across.x * sn / max(width, 1e-5),
                             across.y * sn / max(width, 1e-5),
                             cs / max(half_h, 1e-5))).normalized()
            nearest = tree.find_nearest(guess)
            if nearest[0] is None or nearest[3] > 0.055:
                raise RuntimeError(f"Foot-fit sample drifted for {name}: {nearest[3] if nearest[0] else 'miss'}")
            point, normal = Vector(nearest[0]), Vector(nearest[1]).normalized()
            keel = 0.0040 * max(0.0, cs) ** 8 * math.sin(math.pi * v) ** 0.6
            lip = 0.0010 * (1.0 - v) ** 3 * max(0.0, cs)
            p = point + normal * (clearance + keel + lip)
            p.z = max(p.z, 0.016)
            row.append(p)
            nr.append(normal)
        outer.append(row)
        normals.append(nr)
    return A.make_closed_shell(name, outer, normals, collection, material,
                               thickness=thickness, bevel=bevel)


def make_sole(name, side, sign, material, collection):
    """Broad, flat, tapered sole with a heel and an unmistakable forward toe."""
    angle = math.radians(15.0 if sign > 0 else -15.0)
    longitudinal = Vector((math.sin(angle), math.cos(angle), 0.0))
    across = Vector((math.cos(angle), -math.sin(angle), 0.0))
    ankle = Vector(J[f"ankle_{side}"])
    # rear -> front.  The last two widths taper sharply to indicate direction.
    stations = [
        (-0.082, 0.052), (-0.045, 0.063), (0.010, 0.073),
        (0.075, 0.075), (0.140, 0.066), (0.190, 0.048), (0.215, 0.018),
    ]
    ring = []
    for q, width in stations:
        ring.append(ankle + longitudinal * q - across * width)
    for q, width in reversed(stations):
        ring.append(ankle + longitudinal * q + across * width)
    z0, z1 = 0.0015, 0.0135
    verts = [Vector((p.x, p.y, z1)) for p in ring] + [Vector((p.x, p.y, z0)) for p in ring]
    n = len(ring)
    faces = [tuple(range(n)), tuple(reversed(range(n, 2 * n)))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    obj = A.make_mesh_object(name, verts, faces, collection, material,
                             bevel=0.0012, smooth=False)
    # Weighted normals are unnecessary in Blender 4.5; the bevel's hardened
    # normals plus flat broad faces provide a stable sole highlight.
    return obj


def build_side(side, sign, tree, armor, controls, steel, iron):
    made = []
    shoulder, elbow, wrist = (Vector(J[f"{j}_{side}"]) for j in ("shoulder", "elbow", "wrist"))
    hip, knee, ankle = (Vector(J[f"{j}_{side}"]) for j in ("hip", "knee", "ankle"))

    # Manual-pose pivots.  Their hierarchy previews shoulder/elbow/wrist and
    # hip/knee/ankle chains without an armature or weights.
    upper_root = make_root(f"WSK_LimbPose_UpperArm_{side}_01", shoulder, controls)
    elbow_cop_root = make_root(f"WSK_LimbPose_ElbowCop_{side}_01", elbow, controls, upper_root)
    fore_root = make_root(f"WSK_LimbPose_Forearm_{side}_01", elbow, controls, upper_root)
    hand_root = make_root(f"WSK_LimbPose_Hand_{side}_01", wrist, controls, fore_root)
    thigh_root = make_root(f"WSK_LimbPose_Thigh_{side}_01", hip, controls)
    knee_cop_root = make_root(f"WSK_LimbPose_KneeCop_{side}_01", knee, controls, thigh_root)
    shin_root = make_root(f"WSK_LimbPose_Shin_{side}_01", knee, controls, thigh_root)
    foot_root = make_root(f"WSK_LimbPose_Foot_{side}_01", ankle, controls, shin_root)

    proximal_overlap = "proximal plate overlaps the next distal plate"

    # UPPER ARM: three nested lames, hidden under the pauldron and stopping
    # roughly 35 mm above the elbow pivot.
    arm_layers = [
        (f"WSK_Armor_UpperArm_{side}_01", 0.57, 0.86, 0.032, 0.024, 0),
        (f"WSK_Armor_UpperArmLame_Middle_{side}_01", 0.28, 0.59, 0.0165, 0.018, 1),
        (f"WSK_Armor_UpperArmLame_Distal_{side}_01", 0.21, 0.36, 0.008, 0.010, 2),
    ]
    for name, t0, t1, clear, point, idx in arm_layers:
        obj = build_swept_plate(tree, name, elbow, shoulder, t0, t1, sign,
                                50.0, 78.0, clear, 0.0048,
                                plate_material(idx, steel, iron), armor,
                                ridge=0.0048, distal_point=point)
        set_props(obj, f"layered upper-arm plate {idx + 1}/3", f"upper_arm_{side} bone",
                  "separate upper-arm lame; pauldron and elbow remain independent",
                  proximal_overlap)
        parent_keep_world(obj, upper_root)
        made.append(obj)

    upper_axis = (shoulder - elbow).normalized()
    lower_axis = (elbow - wrist).normalized()
    elbow_axis = (upper_axis + lower_axis).normalized()
    cop = build_joint_cop(tree, f"WSK_Armor_ElbowCop_{side}_01", elbow,
                          elbow_axis, sign, 0.038, iron, armor,
                          span_inner=56.0, span_outer=68.0,
                          clearance=0.0205)
    set_props(cop, "separate elbow cop / floating joint plate",
              f"elbow_cop_{side} helper bone",
              "rotate between upper arm and forearm; a dedicated helper bone is recommended",
              "floats outside both arm stacks; never forms a rigid sleeve", helper=True)
    parent_keep_world(cop, elbow_cop_root)
    made.append(cop)

    # FOREARM: same proximal-over-distal cascade and keel vocabulary.
    fore_layers = [
        (f"WSK_Armor_Forearm_{side}_01", 0.58, 0.76, 0.025, 0.026, 0),
        (f"WSK_Armor_ForearmLame_Middle_{side}_01", 0.32, 0.66, 0.0165, 0.016, 1),
        (f"WSK_Armor_ForearmLame_Distal_{side}_01", 0.11, 0.40, 0.008, 0.010, 2),
    ]
    for name, t0, t1, clear, point, idx in fore_layers:
        obj = build_swept_plate(tree, name, wrist, elbow, t0, t1, sign,
                                44.0, 72.0, clear, 0.0047,
                                plate_material(idx, steel, iron), armor,
                                ridge=0.0046, distal_point=point)
        set_props(obj, f"layered forearm guard {idx + 1}/3", f"forearm_{side} bone",
                  "dorsal and side bracer; separate from elbow cop and wrist cuff",
                  proximal_overlap)
        parent_keep_world(obj, fore_root)
        made.append(obj)

    cuff = build_swept_plate(tree, f"WSK_Armor_WristCuff_{side}_01",
                             wrist, elbow, 0.005, 0.082, sign,
                             58.0, 70.0, 0.007, 0.0038, steel, armor,
                             rows=5, cols=21, ridge=0.0022,
                             distal_point=0.0, bevel=0.00085)
    set_props(cuff, "separate wrist cuff", f"forearm_{side} bone",
              "short cuff ends at the wrist pivot; hand armour rotates independently",
              "segmented gap between bracer and hand")
    parent_keep_world(cuff, fore_root)
    made.append(cuff)

    # HAND: one broad palm plate, one overlapping knuckle row, four simple
    # finger plates and one thumb plate.  These read as a gauntlet without
    # pretending to be a final articulated finger mechanism.
    palm = hand_patch(tree, f"WSK_Armor_Gauntlet_{side}_01", sign,
                      0.972, 0.882, 0.022, 0.031,
                      0.026, 0.0042, iron, armor,
                      rows=8, cols=11, tip=0.002, bevel=0.00095)
    set_props(palm, "gauntlet dorsal palm plate", f"hand_{side} bone",
              "broad keeled back-of-hand plate; independent from wrist cuff",
              proximal_overlap)
    parent_keep_world(palm, hand_root); made.append(palm)

    knuckle = hand_patch(tree, f"WSK_Armor_GauntletKnuckle_{side}_01", sign,
                         0.874, 0.848, 0.032, 0.029,
                         0.011, 0.0035, steel, armor,
                         rows=5, cols=11, tip=0.004, bevel=0.00075)
    set_props(knuckle, "simple overlapping knuckle plate", f"hand_{side} bone",
              "single broad knuckle row; individual mechanical knuckles deferred",
              proximal_overlap)
    parent_keep_world(knuckle, hand_root); made.append(knuckle)

    finger_offsets = (-0.018, -0.006, 0.006, 0.018)
    for i, xoff in enumerate(finger_offsets, 1):
        obj = hand_patch(tree, f"WSK_Armor_GauntletFinger{i}_{side}_01", sign,
                         0.858, 0.807, 0.0044, 0.0035,
                         0.006, 0.0030, steel, armor,
                         rows=5, cols=5, x_offset=xoff,
                         tip=0.004 + 0.001 * (i in (2, 3)), bevel=0.00055)
        set_props(obj, f"simple finger plate {i}/4", f"hand_{side} bone (finger bone later)",
                  "broad placeholder finger plate; no articulated mechanical finger built",
                  "knuckle row overlaps the finger plate")
        parent_keep_world(obj, hand_root); made.append(obj)

    # The neutral mitten's thumb lies on the medial side of each hanging hand.
    thumb_offset = -sign * 0.027
    thumb = hand_patch(tree, f"WSK_Armor_GauntletThumb_{side}_01", sign,
                       0.916, 0.856, 0.0065, 0.0050,
                       0.008, 0.0032, steel, armor,
                       rows=6, cols=5, x_offset=thumb_offset,
                       tip=0.004, bevel=0.0006)
    set_props(thumb, "simple thumb plate", f"hand_{side} bone (thumb bone later)",
              "single broad thumb shell; articulation deferred", proximal_overlap)
    parent_keep_world(thumb, hand_root); made.append(thumb)

    # THIGH: three separate plates under the waist panels.  Their distal edges
    # stop above the knee cop and do not bridge the joint.
    thigh_layers = [
        (f"WSK_Armor_Thigh_{side}_01", 0.70, 0.82, 0.042, 0.040, 0),
        (f"WSK_Armor_ThighLame_Middle_{side}_01", 0.34, 0.67, 0.017, 0.018, 1),
        (f"WSK_Armor_ThighLame_Distal_{side}_01", 0.17, 0.42, 0.008, 0.012, 2),
    ]
    for name, t0, t1, clear, point, idx in thigh_layers:
        obj = build_swept_plate(tree, name, knee, hip, t0, t1, sign,
                                48.0, 68.0, clear, 0.0052,
                                plate_material(idx, steel, iron), armor,
                                rows=9, cols=23, ridge=0.0056,
                                distal_point=point, bevel=0.00125)
        set_props(obj, f"layered thigh guard {idx + 1}/3", f"thigh_{side} bone",
                  "separate front-and-side cuisse; hip and knee flexion remain open",
                  proximal_overlap)
        parent_keep_world(obj, thigh_root); made.append(obj)

    thigh_axis = (hip - knee).normalized()
    shin_axis = (knee - ankle).normalized()
    knee_axis = (thigh_axis + shin_axis).normalized()
    kneecop = build_joint_cop(tree, f"WSK_Armor_KneeCop_{side}_01", knee,
                              knee_axis, sign, 0.054, iron, armor,
                              span_inner=60.0, span_outer=72.0,
                              clearance=0.022, thickness=0.0055,
                              bevel=0.00145)
    set_props(kneecop, "separate poleyn / knee cop",
              f"knee_cop_{side} helper bone",
              "floating poleyn rotates between thigh and shin; dedicated helper bone recommended",
              "floats outside thigh and shin stacks; never forms a rigid knee shell", helper=True)
    parent_keep_world(kneecop, knee_cop_root); made.append(kneecop)

    # SHIN: broad greave with the same three-lame, proximal-over-distal order.
    shin_layers = [
        (f"WSK_Armor_Shin_{side}_01", 0.61, 0.85, 0.026, 0.027, 0),
        (f"WSK_Armor_ShinLame_Middle_{side}_01", 0.35, 0.68, 0.017, 0.017, 1),
        (f"WSK_Armor_ShinLame_Distal_{side}_01", 0.14, 0.43, 0.008, 0.011, 2),
    ]
    for name, t0, t1, clear, point, idx in shin_layers:
        obj = build_swept_plate(tree, name, ankle, knee, t0, t1, sign,
                                54.0, 70.0, clear, 0.0051,
                                plate_material(idx, steel, iron), armor,
                                rows=9, cols=23, ridge=0.0060,
                                distal_point=point, bevel=0.00125)
        set_props(obj, f"layered shin greave {idx + 1}/3", f"shin_{side} bone",
                  "separate front-and-side greave; does not bridge knee or ankle",
                  proximal_overlap)
        parent_keep_world(obj, shin_root); made.append(obj)

    ankle_cuff = build_swept_plate(tree, f"WSK_Armor_AnkleCuff_{side}_01",
                                   ankle, knee, 0.050, 0.092, sign,
                                   56.0, 68.0, 0.007, 0.0038, steel, armor,
                                   rows=5, cols=23, ridge=0.0025,
                                   distal_point=0.0, bevel=0.0009)
    set_props(ankle_cuff, "separate ankle cuff", f"shin_{side} bone",
              "short greave cuff ends at ankle; sabaton rotates on its own pivot",
              "segmented gap between shin stack and foot")
    parent_keep_world(ankle_cuff, shin_root); made.append(ankle_cuff)

    # FOOT: a readable sole plus three dorsal lames, proximal plate outside the
    # next one so every overlap sheds forward in the same direction.
    foot_layers = [
        (f"WSK_Armor_Sabaton_{side}_01", 0.014, 0.086, 0.025, 0),
        (f"WSK_Armor_SabatonLame_Middle_{side}_01", 0.070, 0.150, 0.0165, 1),
        (f"WSK_Armor_SabatonLame_Toe_{side}_01", 0.134, 0.198, 0.008, 2),
    ]
    for name, q0, q1, clear, idx in foot_layers:
        obj = build_foot_plate(tree, name, side, sign, q0, q1, clear,
                               0.0043, plate_material(idx, steel, iron), armor)
        set_props(obj, f"layered sabaton plate {idx + 1}/3", f"foot_{side} bone",
                  "separate instep/toe lame over a stable sole",
                  "rear/proximal sabaton plate overlaps the plate ahead")
        parent_keep_world(obj, foot_root); made.append(obj)

    sole = make_sole(f"WSK_Armor_Sole_{side}_01", side, sign, iron, armor)
    set_props(sole, "stable armour sole", f"foot_{side} bone",
              "flat heel-to-pointed-toe foundation; forward direction follows +Y with 15 degree splay",
              "sabaton side edges terminate above the sole welt")
    sole["wsk_ground_contact_z_m"] = 0.0015
    sole["wsk_forward_axis"] = "+Y, splayed 15 degrees outward"
    parent_keep_world(sole, foot_root); made.append(sole)

    return made


def write_notes(parts, roots):
    text = bpy.data.texts.get("WSK_Limb_Armor_Notes.txt") or bpy.data.texts.new("WSK_Limb_Armor_Notes.txt")
    text.clear()
    text.write(f"""WILDSHIFT KNIGHT - PROMPT 9 LIMB ARMOUR NOTES
================================================
File: {os.path.basename(DST)}
Source: {os.path.basename(SRC)}
Units: metres, Z up, character faces +Y.  Saved in the neutral standing pose.
No armature, bones, weights, constraints, shape keys or animation were created.

CONSTRUCTION
  - 54 closed armour meshes: 27 per side. Every major plate has its own mesh,
    controlled bevel and attachment metadata.
  - Upper arm, forearm, thigh and shin use three broad lames each. In every
    stack the proximal plate sits outside and overlaps the next distal plate.
  - Elbow and knee have separate floating cops; wrist and ankle have short
    cuffs. No continuous rigid shell crosses a joint.
  - Each hand has a palm plate, broad knuckle plate, four simple finger plates
    and one thumb plate. These are deliberately simple armour reads, not a
    mechanical finger mechanism.
  - Each foot has three overlapping dorsal sabaton plates and a separate flat,
    tapered sole. The pointed +Y toe makes the forward direction explicit.
  - Placeholder materials only; no chains, filigree, textures or ornament.

MANUAL POSE CONTROLS (empties, not a rig)
  {chr(10).join('  ' + r.name for r in roots)}
The elbow/forearm/hand and knee/shin/foot roots form parented preview chains.
All controls are saved at zero rotation.  The verification script tests elbow
20 deg, wrist 12 deg, knee 20 deg and ankle 12 deg, then restores neutral.

ATTACHMENT-BONE REPORT
  REQUIRED / RECOMMENDED HELPER BONES:
    WSK_Armor_ElbowCop_R_01, WSK_Armor_ElbowCop_L_01
      -> separate elbow-cop helper so the plate can split the upper/lower-arm angle.
    WSK_Armor_KneeCop_R_01, WSK_Armor_KneeCop_L_01
      -> separate poleyn helper so the plate can split the thigh/shin angle.
  OPTIONAL FOR EXTREME RANGE:
    WSK_Armor_WristCuff_R/L_01 and WSK_Armor_AnkleCuff_R/L_01 may use small
      follow/helper bones if a final rig needs unusually deep wrist/ankle flexion.
  LATER FINGER RIG:
    The four finger plates and thumb plate currently follow the hand bone. Move
      them to individual finger/thumb bones only when actual finger articulation
      is authored.

KNOWN RANGE NOTES
  - Neutral fit preserves visible air/seams at elbow, wrist, knee and ankle.
  - The pose checks are approximate armour-only rotations because this stage
    intentionally has no body rig. Recheck skin clearance once the body deforms.
  - Elbow and knee cops are the pieces most likely to need animator-controlled
    slide as joint angles become acute.

OBJECTS
{chr(10).join('  ' + p.name + ' -> ' + p.get('wsk_attachment_hint', '') for p in parts)}
""")
    project = bpy.data.texts.get("WSK_Project_Notes.txt")
    if project:
        project.write("\n\nPrompt 9 - Limb armour (Wildshift_Knight_09_LimbArmor.blend)\n"
                      "=========================================================\n"
                      "Replaced only the ten legacy limb placeholders with 54 separate layered limb armour meshes. "
                      "Upper arm, forearm, hand, thigh, shin and foot construction is now segmented for future rigging. "
                      "Elbow and knee cops are marked for helper bones; wrist/ankle cuffs may optionally use follow bones. "
                      "Eight empty pivots per side are manual pose controls, not a rig. See WSK_Limb_Armor_Notes.txt.\n")


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    armor = bpy.data.collections.get("Armor")
    body = bpy.data.objects.get(BODY)
    if armor is None or body is None:
        raise RuntimeError("Checkpoint 08 is missing the body or Armor collection")

    # Scope guard: delete only the five legacy limb placeholders per side.
    missing = [n for n in LEGACY if n not in bpy.data.objects]
    if missing:
        raise RuntimeError(f"Missing legacy limb placeholders: {missing}")
    for name in LEGACY:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

    controls = bpy.data.collections.get("Limb Pose Controls")
    if controls is None:
        controls = bpy.data.collections.new("Limb Pose Controls")
        bpy.context.scene.collection.children.link(controls)
    # Empties do not render, so keep this collection render-enabled: disabling
    # a parent collection would also suppress its parented armour children even
    # though the meshes themselves live in the Armor collection.
    controls.hide_render = False

    tree = A.body_bvh(body)
    steel = bpy.data.materials[A.MAT_STEEL]
    iron = bpy.data.materials[A.MAT_IRON]

    parts = []
    for side, sign in (("R", 1.0), ("L", -1.0)):
        parts.extend(build_side(side, sign, tree, armor, controls, steel, iron))

    # The base body is exactly bilateral. Mirror the completed right armour
    # onto the left to remove tiny triangle-selection differences at the hand,
    # groin and foot while retaining a separate mesh/object for every piece.
    for right in [p for p in parts if "_R_01" in p.name]:
        left = bpy.data.objects[right.name.replace("_R_01", "_L_01")]
        if len(left.data.vertices) != len(right.data.vertices):
            raise RuntimeError(f"Cannot mirror mismatched pair {right.name} / {left.name}")
        for rv, lv in zip(right.data.vertices, left.data.vertices):
            lv.co = (-rv.co.x, rv.co.y, rv.co.z)
        bm = bmesh.new()
        bm.from_mesh(left.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(left.data)
        bm.free()
        left.data.update()

    roots = sorted(list(controls.objects), key=lambda o: o.name)
    if len(parts) != 54 or len(roots) != 16:
        raise RuntimeError(f"Expected 54 limb meshes and 16 controls, got {len(parts)} / {len(roots)}")
    for obj in parts:
        if obj.data.users != 1:
            raise RuntimeError(f"Shared mesh datablock on {obj.name}")
        if not any(m.type == "BEVEL" for m in obj.modifiers):
            raise RuntimeError(f"Missing bevel on {obj.name}")
        # Keep neutral object transforms exact; geometry is authored in world
        # coordinates and parent inverses carry the pose-pivot relationship.
        if obj.location.length > 1e-8 or any(abs(s - 1.0) > 1e-8 for s in obj.scale):
            raise RuntimeError(f"Unexpected object transform on {obj.name}")

    write_notes(parts, roots)
    bpy.context.scene["wsk_checkpoint"] = 9
    bpy.context.scene["wsk_prompt_09"] = "refined segmented limb armour; neutral pose"
    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print("SAVED", DST)
    print("LIMB PARTS", len(parts), "POSE CONTROLS", len(roots))
    for obj in parts:
        print(obj.name, len(obj.data.vertices), "verts", len(obj.data.polygons), "faces")


if __name__ == "__main__":
    main()
