"""Prompt 5 - major armor plates for the Wildshift Knight.

Builds on checkpoint 04 without changing its body, helmet, reference, or scene
setup. Armor is authored as sixteen independent, closed low-density shells in
the existing Armor collection. No rig, cloth, weapon, chains, ornament, or
final textures are introduced.

Run: tools/bl.sh tools/build_armor_blockout.py
"""
import math
import os

import bpy  # noqa: F401 (must be imported first)
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_04_HelmetBlockout.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_05_ArmorBlockout.blend")
BODY = "WSK_Body_Base_01"
PROMPT = "Prompt 5 - major armor plates (blockout)"

# The armature guide joints are deliberately not consumed or moved. These
# coordinates are the approved Prompt 2/3 landmarks (world metres, Z up, +Y
# forward); armor ends stop short of the bending zones.
JOINTS = {
    "shoulder_R": Vector((0.200, 0.000, 1.630)),
    "shoulder_L": Vector((-0.200, 0.000, 1.630)),
    "elbow_R": Vector((0.316, -0.020, 1.281)),
    "elbow_L": Vector((-0.316, -0.020, 1.281)),
    "wrist_R": Vector((0.295, 0.022, 0.983)),
    "wrist_L": Vector((-0.295, 0.022, 0.983)),
    "hip_R": Vector((0.100, 0.000, 1.000)),
    "hip_L": Vector((-0.100, 0.000, 1.000)),
    "knee_R": Vector((0.155, 0.010, 0.550)),
    "knee_L": Vector((-0.155, 0.010, 0.550)),
    "ankle_R": Vector((0.215, -0.010, 0.115)),
    "ankle_L": Vector((-0.215, -0.010, 0.115)),
}

# Placeholder metal: dark enough to read as blackened steel against the neutral
# body, but with a controlled metallic highlight for the orthographic checks.
MAT_STEEL = "MAT_Armor_BlackenedSteel_01"
MAT_IRON = "MAT_Armor_BroadIron_01"
PLATE_THICKNESS = 0.006

# The torso loft from Prompt 3 (z, half-width, front depth, rear depth,
# centre-Y). Interpolating these clean body-only rings keeps the cuirass panels
# off the independently moving arms near the armpits and forearms.
TORSO_PROFILE = [
    (0.965, 0.116, 0.080, 0.086, 0.012),
    (0.990, 0.162, 0.110, 0.118, 0.010),
    (1.025, 0.172, 0.124, 0.130, 0.008),
    (1.085, 0.170, 0.122, 0.124, 0.005),
    (1.150, 0.158, 0.118, 0.110, 0.002),
    (1.220, 0.150, 0.116, 0.100, 0.000),
    (1.290, 0.152, 0.120, 0.102, -0.001),
    (1.370, 0.154, 0.128, 0.110, -0.003),
    (1.440, 0.163, 0.136, 0.118, -0.004),
    (1.510, 0.175, 0.144, 0.128, -0.004),
    (1.580, 0.186, 0.150, 0.138, -0.003),
    (1.630, 0.205, 0.138, 0.132, -0.001),
    (1.668, 0.150, 0.110, 0.112, 0.002),
    (1.690, 0.100, 0.086, 0.092, 0.004),
    (1.725, 0.068, 0.064, 0.068, 0.008),
]
TORSO_EXPONENT = 0.86


def set_props(obj, part, attachment, note, **extra):
    obj["wsk_part"] = part
    obj["wsk_attachment_hint"] = attachment
    obj["wsk_prompt"] = PROMPT
    obj["wsk_confidence"] = "measured body-fit blockout; reshape after rig fitting"
    obj["wsk_note"] = note
    for key, value in extra.items():
        obj[key] = value


def make_material(name, rgb, metallic, roughness):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = 0.0
    mat.diffuse_color = (*rgb, 1.0)
    mat.metallic = metallic
    mat.roughness = roughness
    mat["wsk_placeholder"] = True
    mat["wsk_role"] = "untextured dark armor blockout metal"
    return mat


def evaluated_world(obj):
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(depsgraph)
    me = ev.to_mesh()
    mw = ev.matrix_world.copy()
    verts = [mw @ v.co for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    return verts, faces


def body_bvh(obj):
    verts, faces = evaluated_world(obj)
    return BVHTree.FromPolygons(verts, faces, all_triangles=False)


def ray_hit(tree, origin, direction, label):
    result = tree.ray_cast(Vector(origin), Vector(direction).normalized(), 2.0)
    if result[0] is None:
        raise RuntimeError(f"Body-fit ray missed for {label}: {tuple(round(v, 4) for v in origin)}")
    point, normal, _face_index, _distance = result
    normal = normal.normalized()
    return Vector(point), normal


def make_mesh_object(name, verts, faces, collection, material, bevel=0.0012,
                     smooth=True):
    mesh = bpy.data.meshes.new(name + "_mesh")
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
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.data.materials.append(material)
    if bevel:
        mod = obj.modifiers.new("WSK_Softened_Plate_Edges", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = "ANGLE"
        mod.angle_limit = math.radians(38.0)
        mod.harden_normals = True
    return obj


def make_closed_shell(name, outer_grid, normal_grid, collection, material,
                      thickness=PLATE_THICKNESS, bevel=0.0012):
    """Thicken a structured sampled plate as two skins plus a closed perimeter.

    The inner skin is offset toward the body by `thickness`; the outer skin was
    sampled from the body at a larger clearance, so the plate remains a small
    independent shell rather than a fused part of the mannequin.
    """
    nr, nc = len(outer_grid), len(outer_grid[0])
    if nr < 2 or nc < 2 or any(len(r) != nc for r in outer_grid):
        raise ValueError(f"Bad grid for {name}")
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
    # Four perimeter walls make each plate a closed, independently editable solid.
    for j in range(nc - 1):
        faces.append((oi(0, j), oi(0, j + 1), ii(0, j + 1), ii(0, j)))
        faces.append((oi(nr - 1, j + 1), oi(nr - 1, j), ii(nr - 1, j), ii(nr - 1, j + 1)))
    for i in range(nr - 1):
        faces.append((oi(i + 1, 0), oi(i, 0), ii(i, 0), ii(i + 1, 0)))
        faces.append((oi(i, nc - 1), oi(i + 1, nc - 1), ii(i + 1, nc - 1), ii(i, nc - 1)))
    return make_mesh_object(name, verts, faces, collection, material,
                            bevel=bevel, smooth=True)


def signed_power(value, exponent):
    return math.copysign(abs(value) ** exponent, value) if value else 0.0


def torso_xyz(z, theta):
    """Body-only torso loft point at (z, theta), with linear ring interpolation."""
    if z <= TORSO_PROFILE[0][0]:
        lo, hi, f = TORSO_PROFILE[0], TORSO_PROFILE[1], 0.0
    elif z >= TORSO_PROFILE[-1][0]:
        lo, hi, f = TORSO_PROFILE[-2], TORSO_PROFILE[-1], 1.0
    else:
        lo, hi = TORSO_PROFILE[0], TORSO_PROFILE[1]
        for a, b in zip(TORSO_PROFILE[:-1], TORSO_PROFILE[1:]):
            if a[0] <= z <= b[0]:
                lo, hi = a, b
                break
        f = (z - lo[0]) / (hi[0] - lo[0])
    _z0, rx0, front0, back0, cy0 = lo
    _z1, rx1, front1, back1, cy1 = hi
    rx = rx0 + (rx1 - rx0) * f
    cy = cy0 + (cy1 - cy0) * f
    depth = front0 + (front1 - front0) * f if math.cos(theta) >= 0.0 else \
            back0 + (back1 - back0) * f
    x = rx * signed_power(math.sin(theta), TORSO_EXPONENT)
    y = cy + depth * signed_power(math.cos(theta), TORSO_EXPONENT)
    return Vector((x, y, z))


def torso_point(z, theta):
    """Body-only torso loft sample and three-dimensional outward normal."""
    p = torso_xyz(z, theta)
    dt, dz = 0.0002, 0.0002
    tangent_theta = (torso_xyz(z, theta + dt) - torso_xyz(z, theta - dt)) / (2.0 * dt)
    tangent_z = (torso_xyz(z + dz, theta) - torso_xyz(z - dz, theta)) / (2.0 * dz)
    normal = tangent_z.cross(tangent_theta).normalized()
    radial = Vector((math.sin(theta), math.cos(theta), 0.0))
    if normal.dot(radial) < 0.0:
        normal.negate()
    return p, normal


def sample_radial_panel(tree, name, angles, row_t, row_edges, side="front",
                        clearance=0.008, thickness=PLATE_THICKNESS,
                        ridge=0.0, ridge_width=math.radians(18.0)):
    """A wrapped cuirass panel sampled from Prompt 3's torso-only loft.

    `angles` encircle either the front (+Y) or rear (-Y) half. Sampling the
    torso profile rather than generic body rays prevents the cuirass from
    following an arm across the armpit; chest and back retain a close side seam.
    """
    outer_grid, normals = [], []
    for t in row_t:
        row, nr = [], []
        # The upper edge tucks inward beneath the pauldrons at the shoulder
        # line, keeping the cuirass clear of the deltoid and armpit articulation.
        fade = max(0.0, min(1.0, (t - 0.42) / 0.15))
        fade = fade * fade * (3.0 - 2.0 * fade)
        limit = math.radians(88.0 - 33.0 * fade)
        centre_angle = 0.0 if side == "front" else math.pi
        for angle_u in angles:
            theta = centre_angle + angle_u * limit
            side_pos = min(1.0, abs(theta) / (math.pi / 2.0)) if side == "front" else \
                       min(1.0, abs(theta - math.pi) / (math.pi / 2.0))
            bottom_z, top_z = row_edges(side_pos)
            z = bottom_z + (top_z - bottom_z) * t
            hit, normal = torso_point(z, theta)
            # Snap the analytic torso loft onto the actual low-poly body surface.
            # This removes the few-millimetre chord error between profile rings.
            nearest = tree.find_nearest(hit)
            if nearest[0] is not None and nearest[3] <= 0.018:
                hit = Vector(nearest[0])
                normal = Vector(nearest[1]).normalized()
                if normal.dot(Vector((math.sin(theta), math.cos(theta), 0.0))) < 0.0:
                    normal.negate()
            centre_ridge = ridge * math.exp(-((theta - (0.0 if side == "front" else math.pi)) /
                                                ridge_width) ** 2)
            broad_bulge = 0.0025 * (1.0 - side_pos) * math.sin(math.pi * t)
            p = hit + normal * (clearance + centre_ridge * (0.22 + 0.78 * math.sin(math.pi * t))
                                + broad_bulge)
            row.append(p)
            nr.append(normal)
        outer_grid.append(row)
        normals.append(nr)
    # Symmetrize the small nearest-surface snap differences about X=0; the
    # source mannequin itself is exactly bilateral and the chest remains so.
    for i in range(len(outer_grid)):
        for j in range(len(outer_grid[i]) // 2):
            k = len(outer_grid[i]) - 1 - j
            right_p = (Vector((-outer_grid[i][j].x, outer_grid[i][j].y, outer_grid[i][j].z))
                       + outer_grid[i][k]) * 0.5
            right_n = (Vector((-normals[i][j].x, normals[i][j].y, normals[i][j].z))
                       + normals[i][k]).normalized()
            outer_grid[i][j] = Vector((-right_p.x, right_p.y, right_p.z))
            outer_grid[i][k] = right_p
            normals[i][j] = Vector((-right_n.x, right_n.y, right_n.z))
            normals[i][k] = right_n
    return make_closed_shell(name, outer_grid, normals, bpy.data.collections["Armor"],
                             bpy.data.materials[MAT_STEEL], thickness=thickness)


def build_torso_panels(tree, armor_col):
    # A two-degree side seam separates the chest and back as genuinely distinct
    # parts while keeping the side articulation zone narrow and visually clean.
    angle_units = [-1.0 + 2.0 * i / 36.0 for i in range(37)]
    trows = [i / 14.0 for i in range(15)]

    def front_edges(s):
        return 1.095 + 0.080 * (s ** 1.55), 1.696 - 0.122 * (s ** 1.35)

    def rear_edges(s):
        return 1.100 + 0.075 * (s ** 1.55), 1.666 - 0.104 * (s ** 1.35)

    chest = sample_radial_panel(tree, "WSK_Armor_Chest_01", angle_units, trows,
                                front_edges, side="front", clearance=0.009,
                                ridge=0.0075, ridge_width=math.radians(15.0))
    set_props(chest, "single front cuirass / chest mass", "chest or upper-torso bone",
              "front shell; side seam deliberately stops before the back plate; no ornament")
    back = sample_radial_panel(tree, "WSK_Armor_Back_01", angle_units, trows,
                               rear_edges, side="rear", clearance=0.009,
                               ridge=0.0045, ridge_width=math.radians(14.0))
    set_props(back, "single rear cuirass / back mass", "chest or upper-torso bone",
              "separate rear shell with a restrained spinal swell; independent of chest")
    return chest, back


def pauldron_mesh(name, sign, collection, material):
    """Broad, shallow domed shoulder shell with a closed, inset underside."""
    cx, cy, top_z = sign * 0.252, -0.004, 1.728
    rx, ry, height = 0.151, 0.137, 0.119
    n_ang = 28
    phi_rows = [math.radians(v) for v in (12, 25, 40, 56, 72, 86, 90)]
    outer = []
    outer_normals = []
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
            # The outer edge drops slightly over the arm; the inner edge stays
            # high near the gorget. This yields a flared pauldron, not a sphere.
            edge_drop = 0.026 * max(0.0, radial_x) + 0.009 * max(0.0, -radial_y)
            z = top_z - height * (1.0 - math.cos(phi)) - edge_drop * (q ** 2.0)
            p = Vector((x, y, z))
            # Approximate ellipsoid normal; the extra edge drop is intentionally
            # small and is softened by the plate bevel.
            n = Vector(((x - cx) / (rx * rx), (y - cy) / (ry * ry),
                        (z - (top_z - height)) / (height * height))).normalized()
            ring.append(p)
            nr.append(n)
        outer.append(ring)
        outer_normals.append(nr)
    inner = [[outer[i][j] - outer_normals[i][j] * PLATE_THICKNESS
              for j in range(n_ang)] for i in range(len(outer))]
    outer_apex = apex
    inner_apex = apex - Vector((0.0, 0.0, PLATE_THICKNESS))
    verts = [outer_apex]
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
    # Close the rim of the cap at its lowest ring.
    a0, b0 = outer_offset[-1], inner_offset[-1]
    for j in range(n_ang):
        j1 = (j + 1) % n_ang
        faces.append((a0 + j, a0 + j1, b0 + j1, b0 + j))
    obj = make_mesh_object(name, verts, faces, collection, material,
                           bevel=0.0015, smooth=True)
    set_props(obj, "broad domed shoulder plate / pauldron", f"shoulder_{'R' if sign > 0 else 'L'} bone",
              "oversized cap covers the deltoid, but ends above the elbow; separate shell")
    obj["wsk_silhouette_span_m"] = round(2.0 * (rx + abs(cx)), 4)
    return obj


def build_shoulder_spike(name, sign, collection, material):
    """One broad, low-profile, independently editable shoulder spike per side."""
    base = Vector((sign * 0.363, -0.020, 1.686))
    tip = Vector((sign * 0.455, -0.032, 1.778))
    axis = (tip - base).normalized()
    u = Vector((1.0, 0.0, 0.0))
    u = (u - axis * u.dot(axis)).normalized()
    v = axis.cross(u).normalized()
    rings = [(0.0, 0.027, 0.020), (0.20, 0.027, 0.018), (0.72, 0.014, 0.011)]
    n = 6
    verts = []
    for t, rw, rd in rings:
        c = base.lerp(tip, t)
        for j in range(n):
            a = 2.0 * math.pi * j / n
            verts.append(c + u * (math.cos(a) * rw) + v * (math.sin(a) * rd))
    tip_i = len(verts)
    verts.append(tip)
    faces = []
    faces.append(tuple(reversed(range(n))))
    for r in range(len(rings) - 1):
        for j in range(n):
            j1 = (j + 1) % n
            faces.append((r * n + j, (r + 1) * n + j,
                          (r + 1) * n + j1, r * n + j1))
    last = (len(rings) - 1) * n
    for j in range(n):
        faces.append((last + j, tip_i, last + (j + 1) % n))
    obj = make_mesh_object(name, verts, faces, collection, material,
                           bevel=0.0008, smooth=False)
    set_props(obj, "single broad outward shoulder spike", f"shoulder_{'R' if sign > 0 else 'L'} bone",
              "one broad spike only; seated into its pauldron; no secondary thorns")
    return obj


def limb_frame(axis):
    axis = Vector(axis).normalized()
    right = Vector((1.0, 0.0, 0.0)) - axis * axis.x
    right.normalize()
    front = axis.cross(right).normalized()
    if front.y < 0.0:
        right.negate()
        front = axis.cross(right).normalized()
    return axis, right, front


def build_swept_guard(tree, name, distal, proximal, t0, t1, inner_span,
                      outer_span, side_sign, stations, collection, material,
                      clearance=0.008, thickness=PLATE_THICKNESS, ridge=0.0045):
    """A separately capped front/side shell following a limb segment.

    The swept panel wraps around the front and sides of the limb but leaves the
    rear of the limb open. Its ends stop short of the adjacent joints.
    """
    distal, proximal = Vector(distal), Vector(proximal)
    axis, right, front = limb_frame(proximal - distal)
    if side_sign > 0.0:
        angle_min, angle_max = -inner_span, outer_span
    else:
        angle_min, angle_max = -outer_span, inner_span
    angles = [math.radians(angle_min + (angle_max - angle_min) * j / 18.0)
              for j in range(19)]
    ts = [t0 + (t1 - t0) * i / (stations - 1) for i in range(stations)]
    outer_grid, normal_grid = [], []
    for ri, t in enumerate(ts):
        centre = distal.lerp(proximal, t)
        row, nr = [], []
        along = ri / max(1, stations - 1)
        for theta in angles:
            radial = (right * math.sin(theta) + front * math.cos(theta)).normalized()
            # Start just outside the limb rather than far away; a long ray can
            # otherwise hit the torso or pelvis before it reaches the arm/leg.
            origin = centre + radial * 0.16
            hit, normal = ray_hit(tree, origin, -radial,
                                  f"{name} t={t:.3f}, angle={math.degrees(theta):.1f}")
            ridge_factor = max(0.0, math.cos(theta)) ** 4
            end_factor = 0.38 + 0.62 * math.sin(math.pi * along) ** 0.55
            p = hit + normal * (clearance + ridge * ridge_factor * end_factor)
            row.append(p)
            nr.append(normal)
        outer_grid.append(row)
        normal_grid.append(nr)
    obj = make_closed_shell(name, outer_grid, normal_grid, collection, material,
                            thickness=thickness, bevel=0.0010)
    return obj


def build_limb_armor(tree, armor_col, steel, iron):
    objects = []
    sabaton_right = None
    # Forearms: leave ~25 mm at each elbow and wrist, then follow the actual
    # centre line through a 140-degree forward/side arc.
    for side, sign in (("R", 1.0), ("L", -1.0)):
        wrist = JOINTS[f"wrist_{side}"]
        elbow = JOINTS[f"elbow_{side}"]
        name = f"WSK_Armor_Forearm_{side}_01"
        obj = build_swept_guard(tree, name, wrist, elbow, 0.10, 0.90, 36.0, 68.0,
                                sign, 12, armor_col, steel, clearance=0.008, ridge=0.004)
        set_props(obj, "forearm bracer / dorsal shell", f"forearm_{side} bone",
                  "independent swept bracer; ends stop short of elbow and wrist pivots")
        objects.append(obj)

        # Thigh plates stop above the knee and below the hip; hip flexion stays
        # in the visible unarmoured bridge between torso and thigh.
        knee, hip = JOINTS[f"knee_{side}"], JOINTS[f"hip_{side}"]
        name = f"WSK_Armor_Thigh_{side}_01"
        obj = build_swept_guard(tree, name, knee, hip, 0.13, 0.80, 38.0, 58.0,
                                sign, 13, armor_col, steel, clearance=0.009, ridge=0.005)
        set_props(obj, "thigh guard / upper leg shell", f"thigh_{side} bone",
                  "separate front-and-side plate; clear hip flexion and knee bend")
        objects.append(obj)

        ankle = JOINTS[f"ankle_{side}"]
        name = f"WSK_Armor_Shin_{side}_01"
        obj = build_swept_guard(tree, name, ankle, knee, 0.15, 0.83, 50.0, 66.0,
                                sign, 13, armor_col, steel, clearance=0.009, ridge=0.006)
        set_props(obj, "shin greave / tibia shell", f"shin_{side} bone",
                  "separate greave with a central broad keel; knee and ankle remain open")
        objects.append(obj)

        # Dorsal hand plates are simple placeholders, deliberately not fingers
        # or a full glove. The wrist gap remains visible above them.
        hand_rows = [0.835, 0.850, 0.870, 0.892, 0.914, 0.934, 0.947]
        hand_widths = [0.013, 0.021, 0.024, 0.028, 0.027, 0.021, 0.013]
        outer, normals = [], []
        for z, width in zip(hand_rows, hand_widths):
            row, nr = [], []
            u_values = [-1.0 + 2.0 * j / 10.0 for j in range(11)]
            cx = sign * (0.285 + 0.070 * (z - 0.835))
            for u in u_values:
                x = cx + sign * u * width
                hit, normal = ray_hit(tree, (x, 0.85, z), (0.0, -1.0, 0.0),
                                      f"Gauntlet_{side} x={x:.3f}, z={z:.3f}")
                p = hit + normal * (0.007 + 0.0035 * (1.0 - abs(u)))
                row.append(p)
                nr.append(normal)
            outer.append(row)
            normals.append(nr)
        name = f"WSK_Armor_Gauntlet_{side}_01"
        obj = make_closed_shell(name, outer, normals, armor_col, iron,
                                thickness=0.0045, bevel=0.0008)
        set_props(obj, "placeholder dorsal hand armor / simple gauntlet", f"hand_{side} bone",
                  "single unornamented hand plate; finger segmentation deferred")
        objects.append(obj)

        # A shallow, closed sabaton shell wraps over the instep, sides and toe.
        # It begins ahead of the ankle joint and stays clear of the ground plane.
        theta = math.radians(15.0 if sign > 0 else -15.0)
        longitudinal = Vector((math.sin(theta), math.cos(theta), 0.0))
        across = Vector((math.cos(theta), -math.sin(theta), 0.0))
        ankle = JOINTS[f"ankle_{side}"]
        # (distance along foot, outer half-width, outer top Z, lower side Z)
        foot_rows = [(0.038, 0.060, 0.080, 0.014),
                     (0.055, 0.064, 0.076, 0.014),
                     (0.078, 0.067, 0.067, 0.014),
                     (0.104, 0.068, 0.057, 0.014),
                     (0.130, 0.068, 0.045, 0.014),
                     (0.152, 0.062, 0.033, 0.014),
                     (0.170, 0.047, 0.024, 0.014),
                     (0.184, 0.026, 0.016, 0.014)]
        foot_end = math.radians(135.0)
        foot_angles = [-foot_end + 2.0 * foot_end * j / 20.0 for j in range(21)]
        outer, normals = [], []
        for q, width, top_z, bottom_z in foot_rows:
            row, nr = [], []
            # Elliptical section chosen so the lower side edge stays ~8 mm above
            # the sole while the crown follows the descending toe profile.
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
                    raise RuntimeError(f"Sabaton_{side} sample drifted from the foot surface: {nearest[3] if nearest[0] else 'miss'}")
                body_normal = Vector(nearest[1]).normalized()
                if body_normal.dot(normal) < 0.0:
                    body_normal.negate()
                p = Vector(nearest[0]) + body_normal * 0.008
                if p.z < 0.014:
                    p.z = 0.014
                row.append(p)
                nr.append(body_normal)
            outer.append(row)
            normals.append(nr)
        name = f"WSK_Armor_Sabaton_{side}_01"
        obj = make_closed_shell(name, outer, normals, armor_col, iron,
                                thickness=0.0045, bevel=0.0007)
        if side == "R":
            sabaton_right = obj
        else:
            # The base body is exactly mirrored; reflect the right shoe shell
            # itself so coarse body-triangle snapping cannot create foot skew.
            if sabaton_right is None or len(sabaton_right.data.vertices) != len(obj.data.vertices):
                raise RuntimeError("Could not mirror the right sabaton mesh")
            for src_v, dst_v in zip(sabaton_right.data.vertices, obj.data.vertices):
                dst_v.co = (-src_v.co.x, src_v.co.y, src_v.co.z)
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bm.to_mesh(obj.data)
            bm.free()
            obj.data.update()
        set_props(obj, "foot armor / shallow sabaton placeholder", f"foot_{side} bone",
                  "upper, side and toe shell follows the splayed foot; sole and ankle remain clear")
        objects.append(obj)
    return objects


def write_notes(objects):
    names = "\n".join(f"  {o.name:34s} {o.get('wsk_part', '')}" for o in objects)
    text = bpy.data.texts.get("WSK_Armor_Blockout_Notes.txt")
    if text is None:
        text = bpy.data.texts.new("WSK_Armor_Blockout_Notes.txt")
    text.clear()
    text.write(f"""WILDSHIFT KNIGHT - PROMPT 5 ARMOR BLOCKOUT NOTES
=================================================
File: {os.path.basename(DST)}
Source: {os.path.basename(SRC)} (preserved; body and helmet unchanged)
Units: metres, Z up, character faces +Y. No rig was made.

ARMOR OBJECTS (all separately editable meshes in collection Armor)
{names}

DESIGN
  - Chest and back are different wraparound shells, with a narrow side seam.
  - Left and right pauldrons are broad shallow domes, each with one separate,
    broad shoulder spike (two spikes total, not a thorn field).
  - Forearm bracers, thigh plates and shin greaves are independent swept shells.
    Their ends leave the elbow, wrist, hip, knee and ankle articulation zones open.
  - Gauntlets and sabatons are simple placeholders, not finger/toe segmentation.
  - Armor is dark untextured blackened-metal placeholder material. No chains,
    filigree, cloth, weapon, final textures or armature were added.
  - All pieces remain individual objects. Attachment hints are metadata only;
    nothing is parented to a rig or permanently joined.

FIT / RESHAPING NOTES
  The pieces are sized against the neutral base-body rest pose and need a final
  fit pass once a rig and joint pivots exist. In particular, inspect the inner
  pauldron edge against the gorget and upper chest, the bracer ends through a
  full elbow/wrist bend, and the sabaton top at ankle flex. The shoulder cap
  intentionally nests over the deltoid; that body overlap is the only broad
  underlayer overlap. No neighboring armor plates are intended to pass deeply
  through one another.
""")
    project = bpy.data.texts.get("WSK_Project_Notes.txt")
    if project is not None:
        project.write("\n\n" + f"""Prompt 5 - Major armor plates (Wildshift_Knight_05_ArmorBlockout.blend)
======================================================================
Only the existing Armor collection was filled. The base body and Prompt 4
helmet/crown were preserved. Sixteen independent shells: front chest, back,
left/right pauldrons, two separate broad shoulder spikes, left/right forearm
guards, gauntlet placeholders, thigh guards, shin guards and sabatons.

The chest/back remain separate; limb guards are separate pieces; joints are
left clear. Armor uses untextured blackened-steel / dark-iron placeholders.
No rig, chains, filigree, cloth, weapon, ornament or final textures were added.
See WSK_Armor_Blockout_Notes.txt and tools/verify_armor_blockout.py.
""")


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    if BODY not in bpy.data.objects:
        raise RuntimeError(f"Missing base body {BODY} in {SRC}")
    armor_col = bpy.data.collections.get("Armor")
    if armor_col is None:
        raise RuntimeError("Prompt 1 Armor collection is missing")
    if armor_col.objects:
        raise RuntimeError("Refusing to overwrite existing Armor collection contents")

    body = bpy.data.objects[BODY]
    tree = body_bvh(body)
    steel = make_material(MAT_STEEL, (0.018, 0.022, 0.028), 0.78, 0.40)
    iron = make_material(MAT_IRON, (0.037, 0.042, 0.050), 0.78, 0.46)

    objects = []
    chest, back = build_torso_panels(tree, armor_col)
    objects.extend((chest, back))

    for side, sign in (("R", 1.0), ("L", -1.0)):
        obj = pauldron_mesh(f"WSK_Armor_Pauldron_{side}_01", sign, armor_col, iron)
        objects.append(obj)
    for side, sign in (("R", 1.0), ("L", -1.0)):
        objects.append(build_shoulder_spike(f"WSK_Armor_ShoulderSpike_{side}_01",
                                            sign, armor_col, iron))

    objects.extend(build_limb_armor(tree, armor_col, steel, iron))
    expected = 16
    if len(objects) != expected or len({o.name for o in objects}) != expected:
        raise RuntimeError(f"Expected {expected} unique armor objects, got {len(objects)}")

    # A rootless object-per-plate blockout is ready for later bone parenting.
    # Add the same stage tags used by the earlier checkpoints.
    for obj in objects:
        if obj.data.users != 1:
            raise RuntimeError(f"Armor mesh datablock is shared: {obj.name}")
        obj["wsk_prompt"] = PROMPT
    write_notes(objects)

    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print("SAVED", DST)
    print("ARMOR OBJECTS", len(objects))
    for obj in objects:
        print(obj.name, "verts", len(obj.data.vertices), "faces", len(obj.data.polygons))


if __name__ == "__main__":
    main()
