"""Prompt 6 - refine the full character silhouette.

Builds on checkpoint 05 without changing its scale, orientation or unit system.
The body, the helmet shell/faceplate/crest/neck guard and the crown are left
alone except for one documented change: the central crown spike is shortened to
the height the Prompt 4 notes already recommended.

Only major shapes are touched:

* both pauldrons are rebuilt narrower, on the corrected reference shoulder span;
* both shoulder spikes are re-seated on the new pauldron face as one deliberate
  broad spike per shoulder (still exactly two spikes);
* thigh / shin guards are extended so the leg outline reads continuously with a
  small articulation gap left at the knee and the ankle;
* gauntlets are extended over the fingertips;
* sabatons are dropped onto the ground plane and their cuff is raised;
* a temporary flat silhouette material, a contrasting world and a dedicated
  view layer with four orthographic inspection cameras are added.

Nothing is joined, merged, parented to a rig, sculpted, UV mapped or animated.
No cape, no weapon, no chains, no ornament and no extra spikes are created.

Run: tools/bl.sh tools/build_silhouette.py
"""
import math
import os
import sys

import bpy  # noqa: F401 (must be imported first)
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

SRC = os.path.join(ROOT, "Wildshift_Knight_05_ArmorBlockout.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_06_Silhouette.blend")
BODY = "WSK_Body_Base_01"
PROMPT = "Prompt 6 - full character silhouette refinement"

import build_armor_blockout as A  # noqa: E402  (generic armour helpers only)

# ---------------------------------------------------------------------------
# Approved silhouette targets.
#
# Source: the raw percentage readings in analysis/reference_measurements.md,
# re-derived with ONE consistent calibration (body height 2.00 m, square
# pixels, per-view ground/dome landmarks).  The Prompt 2 document converted its
# width readings with 1 % of image width = 13.7 mm while it anchored the height
# at 2.00 m = 1050 px = 1.905 mm/px; those two scales disagree by 17.9 %, so
# every width in that document is 15 % short.  The ratios (width / height) are
# calibration free and are what these targets use.
# ---------------------------------------------------------------------------
TARGETS = {
    "body_height_m": 2.00,          # ground -> helmet dome top (agreed scale)
    "crown_spike_tips_z": 2.115,    # reference read 2.131 m (+/- 5 %)
    "helmet_width_m": 0.218,        # reference 13.5 % of frame width
    "shoulder_plate_span_m": 0.530,  # reference pauldron plate 0.549 m
    "shoulder_spike_span_m": 0.640,  # reference spiked extent 0.63 / 0.72 m
    "waist_span_m": 0.226,
    "stance_m": 0.510,              # between the two foot centres
    "sabaton_width_m": 0.129,
    "ground_z": 0.0,
}

# Pauldron: an ellipsoid cap.  cx / cy are the apex, top_z the crown of the
# dome, rx / ry the equatorial radii and height the drop from apex to equator.
# Outer edge = cx + rx = 0.265 m (span 0.530 m).
PAULDRON = dict(cx=0.1925, cy=-0.008, top_z=1.740, rx=0.0725, ry=0.137,
                height=0.119)

# Shoulder spike: elevation above horizontal, yaw toward the back, tip target.
SPIKE_ELEVATION = math.radians(45.0)
SPIKE_YAW = math.radians(-10.0)      # -10 deg = 10 deg toward the character's back
SPIKE_TIP = Vector((0.320, -0.0305, 1.7504))
SPIKE_SEAT_INSET = 0.018             # base pushed into the pauldron shell
SPIKE_RINGS = [(0.0, 0.027, 0.020), (0.20, 0.026, 0.019), (0.72, 0.014, 0.011)]

CENTRAL_CROWN_TIP_Z = TARGETS["crown_spike_tips_z"]

# Limb guards: parameter range along distal -> proximal.
THIGH_RANGE = (0.06, 0.82)           # knee -> hip   (was 0.13 .. 0.80)
SHIN_RANGE = (0.06, 0.94)            # ankle -> knee (was 0.15 .. 0.83)

GAUNTLET_ROWS = [0.812, 0.830, 0.848, 0.868, 0.890, 0.911, 0.930, 0.943, 0.954]
GAUNTLET_WIDTHS = [0.011, 0.018, 0.022, 0.025, 0.027, 0.027, 0.024, 0.019, 0.012]

# (distance along the foot from the ankle, outer half width, top Z, lower side Z)
SABATON_ROWS = [(0.030, 0.058, 0.086, 0.000),
                (0.048, 0.063, 0.080, 0.000),
                (0.070, 0.066, 0.070, 0.000),
                (0.100, 0.068, 0.059, 0.000),
                (0.130, 0.068, 0.047, 0.000),
                (0.152, 0.062, 0.035, 0.000),
                (0.170, 0.047, 0.025, 0.000),
                (0.184, 0.026, 0.016, 0.000)]
SABATON_MIN_Z = 0.0
SABATON_ANGLE = math.radians(15.0)

MAT_SILHOUETTE = "MAT_Silhouette_Dark_01"
WORLD_SILHOUETTE = "WSK_World_Silhouette"
VIEW_LAYER_SILHOUETTE = "Silhouette Check"
COL_SILHOUETTE = "Silhouette Check"
SIL_CAMERAS = {
    "WSK_Cam_Sil_Front_01": (0.0, 5.0, 1.03),
    "WSK_Cam_Sil_Rear_01": (0.0, -5.0, 1.03),
    "WSK_Cam_Sil_Left_01": (-5.0, 0.0, 1.03),
    "WSK_Cam_Sil_Right_01": (5.0, 0.0, 1.03),
}
SIL_ORTHO_SCALE = 2.60


# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------
def replace_mesh(obj, verts, faces, smooth=True):
    """Swap new geometry into an existing object, keeping modifiers and props."""
    old = obj.data
    mesh = bpy.data.meshes.new(obj.name + "_mesh")
    mesh.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    mesh.validate(verbose=False)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = smooth
    for mat in old.materials:
        if mat is not None and mat.name not in [m.name for m in mesh.materials]:
            mesh.materials.append(mat)
    obj.data = mesh
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return mesh


def drop_temp(obj):
    """Delete a throw-away helper object and its orphaned mesh."""
    mesh = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if mesh.users == 0:
        bpy.data.meshes.remove(mesh)


def mark(obj, note):
    obj["wsk_prompt"] = PROMPT
    obj["wsk_silhouette_note"] = note
    return obj


# ---------------------------------------------------------------------------
# pauldron and shoulder spike
# ---------------------------------------------------------------------------
def pauldron_geometry(sign, p):
    """Closed domed cap.  Mirrored exactly for sign = -1."""
    cx, cy, top_z = sign * p["cx"], p["cy"], p["top_z"]
    rx, ry, height = p["rx"], p["ry"], p["height"]
    n_ang = 28
    phi_rows = [math.radians(v) for v in (12, 25, 40, 56, 72, 86, 90)]
    outer, outer_normals = [], []
    apex = Vector((cx, cy, top_z))
    for phi in phi_rows:
        ring, nr = [], []
        q = math.sin(phi)
        for j in range(n_ang):
            a = 2.0 * math.pi * j / n_ang
            radial_x = math.cos(a)
            radial_y = math.sin(a)
            x = cx + sign * rx * q * radial_x
            y = cy + ry * q * radial_y
            edge_drop = 0.026 * max(0.0, radial_x) + 0.009 * max(0.0, -radial_y)
            z = top_z - height * (1.0 - math.cos(phi)) - edge_drop * (q ** 2.0)
            point = Vector((x, y, z))
            n = Vector(((x - cx) / (rx * rx), (y - cy) / (ry * ry),
                        (z - (top_z - height)) / (height * height))).normalized()
            ring.append(point)
            nr.append(n)
        outer.append(ring)
        outer_normals.append(nr)
    inner = [[outer[i][j] - outer_normals[i][j] * A.PLATE_THICKNESS
              for j in range(n_ang)] for i in range(len(outer))]
    inner_apex = apex - Vector((0.0, 0.0, A.PLATE_THICKNESS))
    verts = [apex]
    outer_offset = [0]
    for ring in outer:
        outer_offset.append(len(verts))
        verts.extend(ring)
    inner_tip = len(verts)
    verts.append(inner_apex)
    inner_offset = [inner_tip]
    for ring in inner:
        inner_offset.append(len(verts))
        verts.extend(ring)
    faces = []
    for j in range(n_ang):
        j1 = (j + 1) % n_ang
        faces.append((outer_offset[0], outer_offset[1] + j, outer_offset[1] + j1))
        faces.append((inner_offset[0], inner_offset[1] + j1, inner_offset[1] + j))
    for i in range(len(outer) - 1):
        a0, a1 = outer_offset[i + 1], outer_offset[i + 2]
        b0, b1 = inner_offset[i + 1], inner_offset[i + 2]
        for j in range(n_ang):
            j1 = (j + 1) % n_ang
            faces.append((a0 + j, a1 + j, a1 + j1, a0 + j1))
            faces.append((b0 + j, b0 + j1, b1 + j1, b1 + j))
    a0, b0 = outer_offset[-1], inner_offset[-1]
    for j in range(n_ang):
        j1 = (j + 1) % n_ang
        faces.append((a0 + j, a0 + j1, b0 + j1, b0 + j))
    return verts, faces


def ellipsoid_surface_point(centre, radii, direction):
    """Point where the ray from `centre` along `direction` leaves the ellipsoid."""
    d = Vector(direction)
    k = math.sqrt(sum((d[i] / radii[i]) ** 2 for i in range(3)))
    return Vector(centre) + d / k


def shoulder_spike_geometry(sign):
    p = PAULDRON
    centre = Vector((sign * p["cx"], p["cy"], p["top_z"] - p["height"]))
    radii = Vector((p["rx"], p["ry"], p["height"]))
    # +X is the character's right, so the outward component carries the sign;
    # the yaw toward the back is the same direction on both sides.
    d = Vector((sign * math.cos(SPIKE_ELEVATION) * math.cos(SPIKE_YAW),
                math.cos(SPIKE_ELEVATION) * math.sin(SPIKE_YAW),
                math.sin(SPIKE_ELEVATION)))
    seat = ellipsoid_surface_point(centre, radii, d)
    base = seat - d * SPIKE_SEAT_INSET
    tip = Vector((sign * SPIKE_TIP.x, SPIKE_TIP.y, SPIKE_TIP.z))
    axis = (tip - base)
    length = axis.length
    axis = axis.normalized()
    u = Vector((1.0, 0.0, 0.0))
    u = (u - axis * u.dot(axis)).normalized()
    v = axis.cross(u).normalized()
    n = 6
    verts = []
    for t, rw, rd in SPIKE_RINGS:
        c = base.lerp(tip, t)
        for j in range(n):
            a = 2.0 * math.pi * j / n
            verts.append(c + u * (math.cos(a) * rw) + v * (math.sin(a) * rd))
    tip_i = len(verts)
    verts.append(tip)
    faces = []
    faces.append(tuple(reversed(range(n))))
    for r in range(len(SPIKE_RINGS) - 1):
        for j in range(n):
            j1 = (j + 1) % n
            faces.append((r * n + j, (r + 1) * n + j,
                          (r + 1) * n + j1, r * n + j1))
    last = (len(SPIKE_RINGS) - 1) * n
    for j in range(n):
        faces.append((last + j, tip_i, last + (j + 1) % n))
    return verts, faces, base, tip, seat, length


# ---------------------------------------------------------------------------
# hand and foot shells (same construction as Prompt 5, refined extents)
# ---------------------------------------------------------------------------
def gauntlet_grid(tree, side, sign):
    outer, normals = [], []
    for z, width in zip(GAUNTLET_ROWS, GAUNTLET_WIDTHS):
        row, nr = [], []
        u_values = [-1.0 + 2.0 * j / 10.0 for j in range(11)]
        cx = sign * (0.285 + 0.070 * (z - 0.835))
        for u in u_values:
            x = cx + sign * u * width
            hit, normal = A.ray_hit(tree, (x, 0.85, z), (0.0, -1.0, 0.0),
                                    f"Gauntlet_{side} x={x:.3f}, z={z:.3f}")
            p = hit + normal * (0.007 + 0.0035 * (1.0 - abs(u)))
            row.append(p)
            nr.append(normal)
        outer.append(row)
        normals.append(nr)
    return outer, normals


def sabaton_grid(tree, side, sign):
    theta = SABATON_ANGLE if sign > 0 else -SABATON_ANGLE
    longitudinal = Vector((math.sin(theta), math.cos(theta), 0.0))
    across = Vector((math.cos(theta), -math.sin(theta), 0.0))
    ankle = A.JOINTS[f"ankle_{side}"]
    foot_end = math.radians(135.0)
    foot_angles = [-foot_end + 2.0 * foot_end * j / 20.0 for j in range(21)]
    outer, normals = [], []
    for q, width, top_z, bottom_z in SABATON_ROWS:
        row, nr = [], []
        half_h = (top_z - bottom_z) / (1.0 - math.cos(foot_end))
        centre_z = top_z - half_h
        centre = ankle + longitudinal * q
        for phi in foot_angles:
            sn, cs = math.sin(phi), math.cos(phi)
            xysize = centre + across * (width * sn)
            z = centre_z + half_h * cs
            normal = Vector((across.x * sn / max(width, 1e-6),
                             across.y * sn / max(width, 1e-6),
                             cs / max(half_h, 1e-6))).normalized()
            p = Vector((xysize.x, xysize.y, z))
            nearest = tree.find_nearest(p)
            if nearest[0] is None or nearest[3] > 0.045:
                raise RuntimeError(
                    f"Sabaton_{side} sample drifted from the foot surface: "
                    f"{nearest[3] if nearest[0] else 'miss'}")
            body_normal = Vector(nearest[1]).normalized()
            if body_normal.dot(normal) < 0.0:
                body_normal.negate()
            p = Vector(nearest[0]) + body_normal * 0.008
            if p.z < SABATON_MIN_Z:
                p.z = SABATON_MIN_Z
            row.append(p)
            nr.append(body_normal)
        outer.append(row)
        normals.append(nr)
    return outer, normals


# ---------------------------------------------------------------------------
# crown
# ---------------------------------------------------------------------------
def shorten_central_crown_spike(obj, target_z):
    """Squeeze the centre crown spike in world Z about its base ring."""
    mw = obj.matrix_world
    inv = mw.inverted()
    world = [mw @ v.co.copy() for v in obj.data.vertices]
    zs = [p.z for p in world]
    zmin = min(zs)
    ring = [p for p in world if p.z <= zmin + 0.004]
    base_z = sum(p.z for p in ring) / len(ring)
    tip_z = max(zs)
    scale = (target_z - base_z) / (tip_z - base_z)
    for v, p in zip(obj.data.vertices, world):
        p.z = base_z + scale * (p.z - base_z)
        v.co = inv @ p
    obj.data.update()
    return scale, base_z, tip_z, target_z


# ---------------------------------------------------------------------------
# silhouette inspection setup
# ---------------------------------------------------------------------------
def make_silhouette_material():
    mat = bpy.data.materials.get(MAT_SILHOUETTE) or bpy.data.materials.new(MAT_SILHOUETTE)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.012, 0.013, 0.016, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 1.0
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = 0.0
    mat.diffuse_color = (0.012, 0.013, 0.016, 1.0)
    mat["wsk_role"] = "temporary flat silhouette evaluation material"
    mat["wsk_placeholder"] = True
    return mat


def make_silhouette_world():
    world = bpy.data.worlds.get(WORLD_SILHOUETTE) or bpy.data.worlds.new(WORLD_SILHOUETTE)
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg is None:
        bg = world.node_tree.nodes.new("ShaderNodeBackground")
        out = world.node_tree.nodes.get("World Output")
        world.node_tree.links.new(bg.outputs[0], out.inputs[0])
    bg.inputs[0].default_value = (0.815, 0.825, 0.855, 1.0)
    bg.inputs[1].default_value = 1.0
    world["wsk_role"] = "flat contrasting backdrop for silhouette checking"
    return world


def make_silhouette_cameras():
    col = bpy.data.collections.get(COL_SILHOUETTE)
    if col is None:
        col = bpy.data.collections.new(COL_SILHOUETTE)
        bpy.context.scene.collection.children.link(col)
    target = Vector((0.0, 0.0, 1.03))
    made = []
    for name, loc in SIL_CAMERAS.items():
        cam_data = bpy.data.cameras.get(name)
        if cam_data is None:
            cam_data = bpy.data.cameras.new(name)
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = SIL_ORTHO_SCALE
        cam_data.clip_start = 0.01
        cam_data.clip_end = 100.0
        obj = bpy.data.objects.get(name)
        if obj is None:
            obj = bpy.data.objects.new(name, cam_data)
            col.objects.link(obj)
        obj.data = cam_data
        obj.location = Vector(loc)
        obj.rotation_euler = (target - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        made.append(obj)
    return col, made


def make_silhouette_view_layer(material, world):
    scene = bpy.context.scene
    vl = scene.view_layers.get(VIEW_LAYER_SILHOUETTE)
    if vl is None:
        vl = scene.view_layers.new(VIEW_LAYER_SILHOUETTE)
    vl.material_override = material
    vl.world_override = world

    excluded = {"Reference", "Blockout", "Lighting and Cameras"}
    for child in vl.layer_collection.children:
        child.exclude = child.name in excluded
    return vl


# ---------------------------------------------------------------------------
def rebuild_shoulders():
    notes = []
    for side, sign in (("R", 1.0), ("L", -1.0)):
        obj = bpy.data.objects[f"WSK_Armor_Pauldron_{side}_01"]
        verts, faces = pauldron_geometry(sign, PAULDRON)
        replace_mesh(obj, verts, faces, smooth=True)
        obj["wsk_silhouette_span_m"] = round(2.0 * (PAULDRON["rx"] + abs(PAULDRON["cx"])), 4)
        mark(obj, "narrowed to the corrected reference shoulder span 0.530 m")
        notes.append((obj.name, "pauldron span"))

        sobj = bpy.data.objects[f"WSK_Armor_ShoulderSpike_{side}_01"]
        verts, faces, base, tip, seat, length = shoulder_spike_geometry(sign)
        replace_mesh(sobj, verts, faces, smooth=False)
        sobj["wsk_spike_length_m"] = round(length, 4)
        sobj["wsk_spike_tip"] = (round(tip.x, 4), round(tip.y, 4), round(tip.z, 4))
        mark(sobj, ("one broad spike per shoulder, seated on the pauldron face at "
                    "45 deg out / 10 deg back; tip on the 0.640 m spiked span"))
        notes.append((sobj.name, f"spike length {length:.3f} m"))
    return notes


def rebuild_legs(tree):
    armour = bpy.data.collections["Armor"]
    steel = bpy.data.materials[A.MAT_STEEL]
    iron = bpy.data.materials[A.MAT_IRON]
    notes = []
    right_sabaton = None
    for side, sign in (("R", 1.0), ("L", -1.0)):
        knee = A.JOINTS[f"knee_{side}"]
        hip = A.JOINTS[f"hip_{side}"]
        obj = bpy.data.objects[f"WSK_Armor_Thigh_{side}_01"]
        tmp = A.build_swept_guard(tree, f"_tmp_thigh_{side}", knee, hip,
                                  THIGH_RANGE[0], THIGH_RANGE[1], 38.0, 58.0,
                                  sign, 13, armour, steel, clearance=0.009, ridge=0.005)
        replace_mesh(obj, [v.co.copy() for v in tmp.data.vertices],
                     [tuple(p.vertices) for p in tmp.data.polygons], smooth=True)
        mark(obj, "extended to within 25 mm of the knee so the leg outline reads continuously")
        drop_temp(tmp)
        notes.append((obj.name, "thigh"))

        ankle = A.JOINTS[f"ankle_{side}"]
        obj = bpy.data.objects[f"WSK_Armor_Shin_{side}_01"]
        tmp = A.build_swept_guard(tree, f"_tmp_shin_{side}", ankle, knee,
                                  SHIN_RANGE[0], SHIN_RANGE[1], 50.0, 66.0,
                                  sign, 13, armour, steel, clearance=0.009, ridge=0.006)
        replace_mesh(obj, [v.co.copy() for v in tmp.data.vertices],
                     [tuple(p.vertices) for p in tmp.data.polygons], smooth=True)
        mark(obj, "extended to within 25 mm of the knee and 26 mm of the ankle")
        drop_temp(tmp)
        notes.append((obj.name, "shin"))

        outer, normals = gauntlet_grid(tree, side, sign)
        obj = bpy.data.objects[f"WSK_Armor_Gauntlet_{side}_01"]
        replace_mesh(obj, *shell_geometry(outer, normals, 0.0045), smooth=True)
        mark(obj, "extended over the fingertips so the hand silhouette is armoured")
        notes.append((obj.name, "gauntlet"))

        outer, normals = sabaton_grid(tree, side, sign)
        obj = bpy.data.objects[f"WSK_Armor_Sabaton_{side}_01"]
        if side == "R":
            replace_mesh(obj, *shell_geometry(outer, normals, 0.0045), smooth=True)
            right_sabaton = obj
        else:
            # mirror the right shell exactly, as Prompt 5 did
            verts = [v.co.copy() for v in right_sabaton.data.vertices]
            faces = [tuple(p.vertices) for p in right_sabaton.data.polygons]
            replace_mesh(obj, verts, faces, smooth=True)
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            for v in bm.verts:
                v.co.x = -v.co.x
            # mirroring flips the winding, so flip it back before re-deriving
            # the normals or the shell ends up inside out
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bm.to_mesh(obj.data)
            bm.free()
            obj.data.update()
        mark(obj, "sole dropped onto the ground plane and cuff raised to 0.100 m")
        notes.append((obj.name, "sabaton"))
    return notes


def shell_geometry(outer_grid, normal_grid, thickness):
    """Same two-skin closed shell rule as build_armor_blockout.make_closed_shell."""
    nr, nc = len(outer_grid), len(outer_grid[0])
    outer = [outer_grid[i][j] for i in range(nr) for j in range(nc)]
    inner = []
    for i in range(nr):
        for j in range(nc):
            p = outer_grid[i][j]
            n = normal_grid[i][j].normalized()
            inner.append(p - n * thickness)
    verts = outer + inner
    layer = nr * nc

    def oi(i, j):
        return i * nc + j

    def ii(i, j):
        return layer + i * nc + j

    faces = []
    for i in range(nr - 1):
        for j in range(nc - 1):
            faces.append((oi(i, j), oi(i + 1, j), oi(i + 1, j + 1), oi(i, j + 1)))
            faces.append((ii(i, j), ii(i, j + 1), ii(i + 1, j + 1), ii(i + 1, j)))
    for j in range(nc - 1):
        faces.append((oi(0, j), oi(0, j + 1), ii(0, j + 1), ii(0, j)))
        faces.append((oi(nr - 1, j + 1), oi(nr - 1, j), ii(nr - 1, j), ii(nr - 1, j + 1)))
    for i in range(nr - 1):
        faces.append((oi(i + 1, 0), oi(i, 0), ii(i, 0), ii(i + 1, 0)))
        faces.append((oi(i, nc - 1), oi(i + 1, nc - 1), ii(i + 1, nc - 1), ii(i, nc - 1)))
    return verts, faces


# ---------------------------------------------------------------------------
# notes
# ---------------------------------------------------------------------------
NOTES = """WILDSHIFT KNIGHT - PROMPT 6 SILHOUETTE NOTES
==============================================
File  : Wildshift_Knight_06_Silhouette.blend
Source: Wildshift_Knight_05_ArmorBlockout.blend (preserved; read only)
Units : metres, Z up, character faces +Y.  Scale and orientation unchanged.
Scope : major shapes only.  No sculpting, UVs, final materials, rig or animation.
        No cape, weapon, chains or ornament.  No new spikes.

WHY THE SHOULDERS CHANGED
-------------------------
analysis/reference_measurements.md converts its width readings with
"1 % of image width = 13.7 mm" while it anchors the body height at
2.00 m = 1050 px = 1.905 mm/px.  Those two scales disagree by 17.9 %, so every
width in that document is about 15 % short.  The width / height RATIOS do not
depend on the calibration at all, and they are what Prompt 6 uses.

Front view, 849 x 1293 px, body height 81.2 % = 1050 px:
  pauldron plate outer edges   x 33.0 ... 67.0 %  -> 34.0 % of width
                               -> 0.340 * 849 / 1050 = 0.275 of body height
                               -> 0.549 m at 2.00 m   (document said 0.46 m)
  spiked shoulder extent       x 30.5 ... 69.5 %  -> 0.315 of height -> 0.630 m
  back view spiked extent      x 30.0 ... 74.0 %  -> 0.358 of height -> 0.715 m
  helmet / hood width          x 44.5 ... 58.0 %  -> 0.109 of height -> 0.218 m

Checkpoint 5's shoulders were 0.806 m of plate and 0.906 m over the spikes,
i.e. 1.65x too wide for its own head.  Prompt 6 narrows them to 0.530 m of
plate and 0.640 m over the spikes.

APPROVED PROPORTIONS (metres, ground Z = 0, body height 2.00 m)
---------------------------------------------------------------
  helmet dome top                      2.000   (model 1.995)
  crown spike tips                     2.115   (reference read 2.131)
  helmet shell width                   0.194   (reference 0.218 - see below)
  crown halo outer span                0.269   (reference 0.331)
  chin / lowest point of the helmet    1.740
  shoulder line, pauldron top edge     1.740   (reference read 1.744)
  pauldron outer edges                 0.530 span, +/- 0.265
  shoulder spike tips                  0.640 span, +/- 0.320, tip Z 1.750
  shoulder spike length                0.113, 45 deg out, 10 deg back
  chest / back plate outer edges       +/- 0.172
  waist (narrowest cuirass)            ~ +/- 0.16 at Z 1.22
  hip joint                            Z 1.000
  knee joint                           Z 0.550
  ankle joint                          Z 0.115
  foot centres                         +/- 0.236, stance 0.472 (reference 0.510)
  sabaton sole                         Z 0.000  (on the ground plane)
  sabaton cuff                         Z 0.100
  chest front / back plate extremes    Y +0.161 / -0.153

REMAINING VISUAL ISSUES
-----------------------
1. Head is narrow.  The corrected reference helmet width is 0.218 m and the
   crown ring 0.331 m; the model is 0.194 m and 0.269 m, about 11 % and 19 %
   narrow.  This is the Prompt 4 deviation (helmet sized off the 0.172 m
   Prompt 3 skull).  Fix it with the hood, not by rescaling the crown.
2. Stance is 0.472 m between foot centres against a reference read of 0.510 m.
   The legs belong to the Prompt 3 body, so this stays until the legs are
   re-posed or the body is re-lofted.
3. Chest depth is 0.314 m against a side-view read of 0.368 m; the cuirass is
   about 15 % shallow.
4. Feet are long: the Prompt 3 foot spans Y -0.114 ... +0.189 (0.303 m) against
   a reference read of 0.22 m.  The toe is right, the heel is 64 mm too far
   back.
5. Upper arms are unarmoured between the pauldron and the bracer.  No new part
   was added in Prompt 6; a rerebrace belongs with the arm-armour pass.
6. Arm pose is the symmetric Prompt 3 rest pose.  The reference is asymmetric
   (one hand on the sword grip at about X 0.44, Z 1.45).  Pose it after the
   rig, not now.
7. No cape yet.  The cape dominates the reference silhouette below the
   shoulders (0.94 m wide, hem at Z 0.21) and will change the outline again.

SILHOUETTE INSPECTION SETUP
---------------------------
  material    MAT_Silhouette_Dark_01   flat near-black diffuse
  world       WSK_World_Silhouette     flat light grey backdrop
  view layer  "Silhouette Check"       material_override + world_override,
                                       Reference / Blockout / Lighting and
                                       Cameras excluded
  cameras     WSK_Cam_Sil_{Front,Rear,Left,Right}_01  orthographic, 2.60 m,
                                       centred on Z 1.03, in collection
                                       "Silhouette Check"
Activate the "Silhouette Check" view layer and render any of the four cameras
to see the outline.  Everything stays editable; nothing is merged.
"""


def write_notes(extra):
    text = bpy.data.texts.get("WSK_Silhouette_Notes.txt")
    if text is None:
        text = bpy.data.texts.new("WSK_Silhouette_Notes.txt")
    text.clear()
    text.write(NOTES)
    if extra:
        text.write("\nBUILD LOG\n---------\n")
        for line in extra:
            text.write(f"  {line}\n")

    notes = bpy.data.texts.get("WSK_Project_Notes.txt")
    if notes is not None:
        body = notes.as_string()
        if "Prompt 6 - full character silhouette" not in body:
            notes.write("\n\nPrompt 6 - full character silhouette\n")
            notes.write("-----------------------------------\n")
            notes.write("Wildshift_Knight_06_Silhouette.blend refines the whole outline: the\n")
            notes.write("shoulders were narrowed from 0.806 m of pauldron plate and 0.906 m over\n")
            notes.write("the spikes to 0.530 m and 0.640 m, on a corrected reading of the\n")
            notes.write("reference (see WSK_Silhouette_Notes.txt).  The two shoulder spikes were\n")
            notes.write("re-seated on the new pauldron faces, the central crown spike was\n")
            notes.write("shortened to Z 2.115, the leg guards were extended toward the knee and\n")
            notes.write("ankle, the gauntlets were extended over the fingertips and the sabatons\n")
            notes.write("were dropped onto the ground plane.  Scale, orientation, the base body,\n")
            notes.write("the helmet and every separate editable object and modifier were kept.\n")
            notes.write("A temporary silhouette material, world, view layer and four orthographic\n")
            notes.write("inspection cameras were added; nothing was merged, rigged or caped.\n")


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    log = []

    tree = A.body_bvh(bpy.data.objects[BODY])

    log.append("shoulders:")
    for name, note in rebuild_shoulders():
        log.append(f"  {name}: {note}")

    log.append("legs and extremities:")
    for name, note in rebuild_legs(tree):
        log.append(f"  {name}: {note}")

    spike = bpy.data.objects["WSK_Helmet_CrownSpike_C_01"]
    scale, base, old_tip, new_tip = shorten_central_crown_spike(spike, CENTRAL_CROWN_TIP_Z)
    mark(spike, "shortened along its own axis so the tip sits on Z 2.115 m")
    log.append(f"crown: CrownSpike_C tip {old_tip:.4f} -> {new_tip:.4f} "
               f"(axial scale {scale:.3f}, base fixed at {base:.4f})")

    mat = make_silhouette_material()
    world = make_silhouette_world()
    col, cams = make_silhouette_cameras()
    vl = make_silhouette_view_layer(mat, world)
    log.append(f"silhouette setup: {MAT_SILHOUETTE}, {WORLD_SILHOUETTE}, "
               f"view layer '{vl.name}', {len(cams)} cameras in collection '{col.name}'")

    write_notes(log)

    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print(f"wrote {DST}  ({os.path.getsize(DST) / 1e6:.2f} MB)")
    for line in log:
        print("  ", line)


if __name__ == "__main__":
    main()
