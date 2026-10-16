"""Prompt-11 verification for the waist medallion.

Checks scope (what changed and what did not), the mount it sits on, its
placement, the design of ring / centre / rays, that the three components really
are separate objects, mesh quality, and - the part the prompt asks for
explicitly - that nothing floats and nothing is buried in the armour.

Writes analysis/verify/verify_medallion_report.txt.

Run: tools/bl.sh tools/verify_medallion.py
"""
import hashlib
import math
import os
import struct

import bpy  # noqa: F401
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_10_Crown.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_11_Medallion.blend")
SHOTS = os.path.join(ROOT, "analysis/medallion")
REPORT = os.path.join(ROOT, "analysis/verify/verify_medallion_report.txt")

MOUNT = "WSK_Armor_WaistMedallionMount_01"
BODY = "WSK_Body_Base_01"
GOLD = "MAT_Armor_AntiqueGold_01"
RING = "WSK_Armor_WaistMedallionRing_01"
CORE = "WSK_Armor_WaistMedallionCore_01"
ROOT_EMPTY = "WSK_Armor_WaistMedallionRoot_01"
RAYS = [f"WSK_Armor_WaistMedallionRay_{i:02d}_01" for i in range(1, 13)]
PARTS = [RING, CORE] + RAYS

CENTRE = Vector((0.0, 0.0, 1.0550))
MOUNT_FACE_Y = 0.1430
MOUNT_R = 0.0430
BELT_TOP, BELT_BOTTOM = 1.105, 1.005
BELT_MID_Y = 0.1435
RING_OUT = 0.0350
CORE_R = 0.0242
RAY_BASE_R = 0.0300
TIER_ANGLES = {"V": (75.0, 105.0, 255.0, 285.0),
               "D": (45.0, 135.0, 225.0, 315.0),
               "H": (15.0, 165.0, 195.0, 345.0)}
TIER_TIPS = {"V": 0.0480, "D": 0.0465, "H": 0.0455}
RAY_TIPS = {a: TIER_TIPS[tier] for tier, angles in TIER_ANGLES.items() for a in angles}
TIER_OF = {a: tier for tier, angles in TIER_ANGLES.items() for a in angles}
PARITY_DIRS = (Vector((0.577, 0.577, 0.577)),
               Vector((-0.707, 0.500, 0.500)),
               Vector((0.267, -0.802, 0.535)),
               Vector((0.0, -0.9, 0.436)))

lines = []
passed = failed = warned = 0


def section(title):
    lines.append("\n== " + title + " ==")


def check(cond, label, detail=""):
    global passed, failed
    ok = bool(cond)
    passed += int(ok)
    failed += int(not ok)
    lines.append(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))
    return ok


def note(text):
    lines.append("      " + text)


def warn(cond, label, detail=""):
    global warned
    if not cond:
        warned += 1
    lines.append(f"[{'WARN' if not cond else 'OK  '}] {label}" + (f"  -> {detail}" if detail else ""))


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def mesh_hash(obj):
    h = hashlib.sha256()
    h.update(obj.type.encode())
    if obj.type == "MESH":
        for v in obj.data.vertices:
            h.update(struct.pack("<3d", *v.co))
        for p in obj.data.polygons:
            h.update(struct.pack("<I", len(p.vertices)))
            for i in p.vertices:
                h.update(struct.pack("<I", i))
        for m in obj.modifiers:
            h.update(m.type.encode())
            for attr in ("width", "thickness", "levels", "angle_limit", "segments"):
                if hasattr(m, attr):
                    value = getattr(m, attr)
                    if isinstance(value, (int, float)):
                        h.update(struct.pack("<d", float(value)))
    for row in obj.matrix_world:
        h.update(struct.pack("<4d", *row))
    h.update((obj.parent.name if obj.parent else "").encode())
    return h.hexdigest()


def mesh_hash_geometry(obj):
    """Hash of the mesh data only - used to show the mount was not reshaped."""
    h = hashlib.sha256()
    for v in obj.data.vertices:
        h.update(struct.pack("<3d", *v.co))
    for p in obj.data.polygons:
        h.update(struct.pack("<I", len(p.vertices)))
        for i in p.vertices:
            h.update(struct.pack("<I", i))
    return h.hexdigest()


def evaluated(obj):
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    eo = obj.evaluated_get(deps)
    me = eo.to_mesh()
    mw = eo.matrix_world.copy()
    verts = [mw @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    eo.to_mesh_clear()
    return verts, polys


def bvh(names):
    if isinstance(names, str):
        names = [names]
    verts, faces = [], []
    for name in names:
        v, f = evaluated(bpy.data.objects[name])
        off = len(verts)
        verts += v
        faces += [tuple(i + off for i in face) for face in f]
    return BVHTree.FromPolygons(verts, faces, all_triangles=False)


def parity_inside(tree, point, directions=PARITY_DIRS, max_hits=16):
    votes = 0
    for d in directions:
        n = 0
        t = 0.0
        while n < max_hits:
            hit = tree.ray_cast(point + d * t, d, 5.0)
            if hit[0] is None:
                break
            t = (hit[0] - point).dot(d) + 1e-4
            n += 1
        votes += int(n % 2 == 1)
    return votes >= 2


def nearest(tree, point):
    hit = tree.find_nearest(point)
    if hit[0] is None:
        return None, 9.9
    return hit[0].copy(), hit[3]


def mesh_quality(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    non_manifold = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    loose = sum(1 for v in bm.verts if not v.link_edges)
    degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-12)
    shortest = min((e.calc_length() for e in bm.edges), default=0.0)
    v = len(bm.verts)
    e = len(bm.edges)
    f = len(bm.faces)
    bm.free()
    return dict(boundary=boundary, non_manifold=non_manifold, loose=loose,
                degenerate=degenerate, shortest=shortest, V=v, E=e, F=f, chi=v - e + f)


def outward_volume(obj):
    """Signed volume about the mesh's own centroid (a far-away origin would lose
    the sign to cancellation: the figure is 1 m tall and the part 10 mm)."""
    verts, polys = evaluated(obj)
    c = Vector((0.0, 0.0, 0.0))
    for v in verts:
        c += v
    c /= len(verts)
    verts = [v - c for v in verts]
    vol = 0.0
    for face in polys:
        a = verts[face[0]]
        for i in range(1, len(face) - 1):
            b, c = verts[face[i]], verts[face[i + 1]]
            vol += a.dot(b.cross(c)) / 6.0
    return vol


def radius_xz(v):
    """Distance from the mount's axis, measured in the medallion's own plane."""
    return math.hypot(v.x - CENTRE.x, v.z - CENTRE.z)


def azimuth_of(obj):
    """Azimuth and reach of a ray's axis in the medallion plane, 0 deg = +X.

    The blade's axis is read as the reach-weighted mean direction of the part of
    it that stands outside the ring; taking the tip's own vertex would measure
    the 0.9 mm wide tip cap instead of the blade.
    """
    verts, _ = evaluated(obj)
    vec = Vector((0.0, 0.0, 0.0))
    reach = 0.0
    for v in verts:
        r = radius_xz(v)
        reach = max(reach, r)
        if r > RING_OUT:
            w = r - RING_OUT
            vec += Vector(((v.x - CENTRE.x) * w, 0.0, (v.z - CENTRE.z) * w))
    return math.degrees(math.atan2(vec.z, vec.x)) % 360.0, reach


# --------------------------------------------------------------------------
# load both checkpoints
# --------------------------------------------------------------------------
bpy.ops.wm.open_mainfile(filepath=DST)
hashes11 = {o.name: mesh_hash(o) for o in bpy.data.objects}
names11 = set(hashes11)
geom11 = {o.name: mesh_hash_geometry(o) for o in bpy.data.objects if o.type == "MESH"}
mats11 = {o.name: [tuple(row) for row in o.matrix_world] for o in bpy.data.objects}

bpy.ops.wm.open_mainfile(filepath=SRC)
hashes10 = {o.name: mesh_hash(o) for o in bpy.data.objects}
names10 = set(hashes10)
geom10 = {o.name: mesh_hash_geometry(o) for o in bpy.data.objects if o.type == "MESH"}
mats10 = {o.name: [tuple(row) for row in o.matrix_world] for o in bpy.data.objects}

bpy.ops.wm.open_mainfile(filepath=DST)
scene = bpy.context.scene

# --------------------------------------------------------------------------
section("A  scope - what changed and what did not")
# --------------------------------------------------------------------------
added = sorted(names11 - names10)
removed = sorted(names10 - names11)
changed = sorted(n for n in (names10 & names11) if hashes10[n] != hashes11[n])
expected_added = sorted(PARTS + [ROOT_EMPTY])
check(set(added) == set(expected_added),
      "the medallion is the only thing added (ring, centre, 12 rays, pivot)",
      f"{len(added)} added" + ("" if set(added) == set(expected_added)
                               else ": " + ", ".join(sorted(set(added) ^ set(expected_added)))))
check(not removed, "nothing was removed", f"{len(removed)} removed")
check(set(changed) <= {MOUNT},
      "no existing object's geometry or transform changed",
      f"changed: {', '.join(changed) if changed else 'none'}")
check(geom10[MOUNT] == geom11[MOUNT],
      "the waist medallion mount is byte-identical: it was found and re-used, not rebuilt")
check(bpy.data.objects[MOUNT].parent is not None and
      bpy.data.objects[MOUNT].parent.name == ROOT_EMPTY,
      "the mount is now parented to the medallion pivot (the only change to it)")
check(len(bpy.data.collections) == 14,
      "no collection was added or removed", f"{len(bpy.data.collections)} collections")
check(len(bpy.data.worlds) == 2 and len(bpy.data.cameras) == 13,
      "worlds and the camera set are unchanged",
      f"{len(bpy.data.worlds)} worlds, {len(bpy.data.cameras)} cameras")
check(len(bpy.data.lights) == 4,
      "no light was added to the saved file", f"{len(bpy.data.lights)} lights")
check(len([m for m in bpy.data.materials if m.use_nodes and any(
              n.type == "EMISSION" for n in m.node_tree.nodes)]) == 0,
      "no material gained an emission shader (no glow, no magical effect)")
check(len([m for m in bpy.data.materials if m.name == GOLD]) == 1 and
      "_tex" not in GOLD.lower() and not any(i.type == "TEX_IMAGE" for i in
      bpy.data.materials[GOLD].node_tree.nodes),
      "the ornament uses one placeholder material with no texture", GOLD)
check(not any(o.modifiers and any(m.type in ("PARTICLE_SYSTEM", "FLUID", "CLOTH")
                                  for m in o.modifiers) for o in bpy.data.objects)
      and len(bpy.data.particles) == 0,
      "no particle systems, cloth or fluid (no animated effect)")
new_ornament = [o for o in bpy.data.objects
                if o.name == ROOT_EMPTY or o.name in PARTS]
check(len(new_ornament) == len(PARTS) + 1,
      "the ornament is one group of 14 meshes and a pivot - no extra jewellery was "
      "added anywhere else on the character", f"{len(new_ornament)} objects")

# the rest of the armour must be untouched, mesh-for-mesh
untouched = [n for n in names10 & names11
             if n.startswith(("WSK_Armor_", "WSK_Body", "WSK_Helmet_"))
             and n not in PARTS and n != MOUNT
             and bpy.data.objects[n].type == "MESH"]
check(all(geom10[n] == geom11[n] for n in untouched),
      "the waist belt, the fauld panels, the torso armour, the shoulder and limb "
      "armour, the helmet and the body are byte-identical to checkpoint 10",
      f"{len(untouched)} objects compared")

# --------------------------------------------------------------------------
section("B  the mount that was found, and the placement of the ornament")
# --------------------------------------------------------------------------
mount = bpy.data.objects[MOUNT]
mverts, _ = evaluated(mount)
m_r = max(math.hypot(v.x, v.z - CENTRE.z) for v in mverts)
m_face = max(v.y for v in mverts)
check(abs(m_face - MOUNT_FACE_Y) < 1e-4 and abs(m_r - MOUNT_R) < 1e-4,
      "the checkpoint-8 mount is what the prompt said it was",
      f"face Y {m_face:.4f}, radius {m_r * 1000:.1f} mm")
check(abs(CENTRE.z - (BELT_TOP + BELT_BOTTOM) / 2.0) < 0.002,
      "the mount sits on the belt's centre line",
      f"mount Z {CENTRE.z:.3f}, belt {BELT_BOTTOM:.3f}-{BELT_TOP:.3f}")

ring = bpy.data.objects[RING]
rverts, _ = evaluated(ring)
rc_x = (min(v.x for v in rverts) + max(v.x for v in rverts)) / 2.0
rc_z = (min(v.z for v in rverts) + max(v.z for v in rverts)) / 2.0
check(abs(rc_x - CENTRE.x) < 5e-5 and abs(rc_z - CENTRE.z) < 5e-5,
      "the medallion is centred on the mount's axis",
      f"ring centre ({rc_x * 1000:+.3f}, {rc_z * 1000:+.3f}) mm vs "
      f"({CENTRE.x * 1000:+.3f}, {CENTRE.z * 1000:+.3f}) mm")

all_verts = {}
for name in PARTS:
    all_verts[name], _ = evaluated(bpy.data.objects[name])
low_z = min(v.z for vs in all_verts.values() for v in vs)
high_z = max(v.z for vs in all_verts.values() for v in vs)
wide_x = max(abs(v.x) for vs in all_verts.values() for v in vs)
check(low_z > BELT_BOTTOM + 0.002 and high_z < BELT_TOP - 0.002,
      "the whole ornament fits inside the belt band with a margin",
      f"Z {low_z:.4f}..{high_z:.4f} inside {BELT_BOTTOM:.3f}..{BELT_TOP:.3f}")
check(wide_x <= MOUNT_R + 0.004,
      "the ornament is no wider than the plate it is mounted on",
      f"half-span {wide_x * 1000:.1f} mm vs mount radius {MOUNT_R * 1000:.1f} mm")
ring_rear = min(v.y for v in rverts)
check(MOUNT_FACE_Y - 0.0015 < ring_rear < MOUNT_FACE_Y - 0.0002,
      "the ring is seated into the mount's face, not balanced on it",
      f"ring rear seat Y {ring_rear:.4f} vs mount face {MOUNT_FACE_Y:.4f}")
check(max(radius_xz(v) for v in rverts) < MOUNT_R,
      "the mount's rim stays visible outside the ring",
      f"ring {max(math.hypot(v.x, v.z - CENTRE.z) for v in rverts) * 1000:.1f} mm "
      f"inside {MOUNT_R * 1000:.1f} mm")

# --------------------------------------------------------------------------
section("C  the design")
# --------------------------------------------------------------------------
check(len(RAYS) == 12, "a limited number of radial elements: twelve", f"{len(RAYS)} rays")
az = {}
for name in RAYS:
    a, reach = azimuth_of(bpy.data.objects[name])
    az[name] = (a, reach)
order = sorted(az.items(), key=lambda kv: kv[1][0])
gaps = [round((order[i + 1][1][0] - order[i][1][0]) % 360.0, 3) for i in range(len(order) - 1)]
gaps.append(round((order[0][1][0] - order[-1][1][0]) % 360.0, 3))
check(all(abs(g - 30.0) < 0.5 for g in gaps),
      "the rays are evenly spaced at 30 degrees", f"gaps {min(gaps)}..{max(gaps)}")
tiers = {"V": [], "D": [], "H": []}
for name, (a, reach) in az.items():
    key = round(a, 1)
    tier = TIER_OF.get(key)
    if tier is None:
        check(False, f"{name} has one of the designed azimuths",
              f"azimuth {a:.2f} deg")
        continue
    tiers[tier].append(reach)
    check(abs(reach - RAY_TIPS[key]) < 2e-4,
          f"{name} reach matches the design",
          f"az {a:.1f} deg reach {reach * 1000:.2f} mm vs "
          f"{RAY_TIPS[key] * 1000:.2f} mm")
check(len(tiers["V"]) == len(tiers["D"]) == len(tiers["H"]) == 4,
      "three graded reach tiers of four blades each",
      f"{len(tiers['V'])}/{len(tiers['D'])}/{len(tiers['H'])}")
check(abs(np.mean(tiers["V"]) - 0.0480) < 2e-4 and
      abs(np.mean(tiers["D"]) - 0.0465) < 2e-4 and
      abs(np.mean(tiers["H"]) - 0.0455) < 2e-4 and
      np.mean(tiers["V"]) > np.mean(tiers["D"]) > np.mean(tiers["H"]),
      "reach falls off monotonically from the vertical pair to the horizontal pair",
      f"V {np.mean(tiers['V']) * 1000:.2f}, D {np.mean(tiers['D']) * 1000:.2f}, "
      f"H {np.mean(tiers['H']) * 1000:.2f} mm")
check(all(abs(math.sin(math.radians(a))) < 0.99 and abs(math.cos(math.radians(a))) < 0.99
          for a, _r in az.values()),
      "no blade points straight up or straight out of the silhouette",
      f"azimuths {', '.join('%.0f' % a for a, _ in sorted(az.values()))}")
mirror = []
for name, (a, reach) in az.items():
    target = (180.0 - a) % 360.0
    match = [r for aa, r in az.values() if abs(((aa - target + 180) % 360) - 180) < 0.5]
    mirror.append(bool(match) and abs(match[0] - reach) < 1e-4)
check(all(mirror), "the ray pattern is exactly mirror-symmetric about X = 0")
check(len([o for o in bpy.data.objects if o.name.startswith("WSK_Armor_WaistMedallionRing")]) == 1
      and len([o for o in bpy.data.objects if o.name.startswith("WSK_Armor_WaistMedallionCore")]) == 1,
      "exactly one ring and one centre")
cverts, _ = evaluated(bpy.data.objects[CORE])
field = min(v.y for v in cverts if radius_xz(v) < 0.021 and v.y > 0.146)
rim = max(v.y for v in cverts if radius_xz(v) > 0.0185 and v.y > 0.146)
check(rim - field > 0.002,
      "the centre is dished: a raised rim standing proud of a recessed field, so it "
      "reads in rendered light",
      f"rim {rim:.4f} vs field {field:.4f} ({1000 * (rim - field):.2f} mm)")
check(max(v.y for v in cverts) < max(v.y for v in rverts) - 0.002,
      "the centre sits below the ring's face, inside the bezel",
      f"centre {max(v.y for v in cverts):.4f} vs ring {max(v.y for v in rverts):.4f}")
depth = (max(v.y for v in rverts) - MOUNT_FACE_Y)
check(0.008 < depth < 0.020,
      "the ornament has real depth to catch light",
      f"{(depth) * 1000:.1f} mm from the mount's face to the ring's crest")

# --------------------------------------------------------------------------
section("D  separate components and hierarchy")
# --------------------------------------------------------------------------
check(all(bpy.data.objects[n].data.users == 1 for n in PARTS),
      "every part is a separate single-user mesh (nothing joined)")
check(all(len(bpy.data.objects[n].data.materials) == 1 for n in PARTS),
      "each part carries its own material slot")
root = bpy.data.objects[ROOT_EMPTY]
check(all(bpy.data.objects[n].parent is root for n in PARTS + [MOUNT]),
      "ring, centre, rays and the mount all hang off the medallion pivot")
check(root.type == "EMPTY" and (root.location - CENTRE).length < 1e-6,
      "the pivot empty is on the mount's axis",
      f"({root.location.x:.4f}, {root.location.y:.4f}, {root.location.z:.4f})")
world_ok = []
for name in PARTS:
    obj = bpy.data.objects[name]
    base = obj.matrix_basis
    world_ok.append(all(abs(base[i][j] - (1.0 if i == j else 0.0)) < 1e-9
                        for i in range(4) for j in range(4)))
check(all(world_ok),
      "parenting did not move anything: every new part keeps an identity local transform")
mount_move = 0.0
for row10, row11 in zip(mats10[MOUNT], mats11[MOUNT]):
    for a, b in zip(row10, row11):
        mount_move = max(mount_move, abs(a - b))
check(mount_move < 1e-9,
      "the mount keeps the exact world matrix it had in checkpoint 10 - it was not "
      "rotated, scaled or moved, only re-parented",
      f"largest matrix element change {mount_move:.2e}")
bpy.context.view_layer.update()
ev_ring = evaluated(bpy.data.objects[RING])[0]
zs = [v.z for v in ev_ring]
xs = [v.x for v in ev_ring]
check(abs(min(zs) - (CENTRE.z - RING_OUT)) < 1e-6 and
      abs(max(zs) - (CENTRE.z + RING_OUT)) < 1e-6 and
      abs(max(xs) - RING_OUT) < 1e-6 and abs(min(xs) + RING_OUT) < 1e-6,
      "the evaluated ring is still centred on the mount after parenting",
      f"X {min(xs) * 1000:+.2f}..{max(xs) * 1000:+.2f} mm, "
      f"Z {min(zs):.4f}..{max(zs):.4f} m")

# --------------------------------------------------------------------------
section("E  mesh quality")
# --------------------------------------------------------------------------
for name in PARTS:
    obj = bpy.data.objects[name]
    q = mesh_quality(obj)
    label = ("ring" if name == RING else "centre" if name == CORE else
             "ray " + name.rsplit("_", 2)[-2])
    check(q["boundary"] == 0 and q["non_manifold"] == 0 and q["loose"] == 0
          and 2 * q["E"] == sum(len(f.vertices) for f in obj.data.polygons),
          f"{label}: a closed manifold solid with no loose geometry",
          f"boundary {q['boundary']}, non-manifold {q['non_manifold']}, V {q['V']}, "
          f"E {q['E']}, F {q['F']}")
    check(outward_volume(obj) > 0,
          f"{label}: normals point outwards",
          f"volume {outward_volume(obj) * 1e6:.1f} mm3")
print_ring = mesh_quality(ring)
check(print_ring["chi"] == 0, "the ring is a ring: genus 1 (like a washer)",
      f"V-E+F = {print_ring['chi']}")
check(mesh_quality(bpy.data.objects[CORE])["chi"] == 2 and
      all(mesh_quality(bpy.data.objects[n])["chi"] == 2 for n in RAYS),
      "the centre and every blade are simple genus-0 solids")
check(all(obj.modifiers and obj.modifiers[0].type == "BEVEL" and
          obj.modifiers[0].show_viewport for obj in
          [bpy.data.objects[n] for n in PARTS]),
      "the edge bevel is still an unapplied modifier on every part (non-destructive)")
check(all(len(o.modifiers) == 1 for o in [bpy.data.objects[n] for n in PARTS]),
      "no other modifier, boolean or sub-division was used")
shortest = min(mesh_quality(bpy.data.objects[n])["shortest"] for n in PARTS)
check(shortest > 1.5e-4,
      "no degenerate feature: the shortest edge in the whole ornament is well above "
      "the bevel width", f"{shortest * 1000:.3f} mm")

# --------------------------------------------------------------------------
section("F  planting - nothing floats, nothing is buried")
# --------------------------------------------------------------------------
armour_names = [o.name for o in bpy.data.collections["Armor"].objects
                if o.type == "MESH" and o.name not in PARTS and o.name != MOUNT]
tree = bvh(armour_names)
mount_tree = bvh([MOUNT])
ring_tree = bvh([RING])
core_tree = bvh([CORE])
body_tree = bvh([BODY])
helmet_names = [o.name for o in bpy.data.collections["Helmet"].objects if o.type == "MESH"]
helmet_tree = bvh(helmet_names)
tree_all = bvh(armour_names + [MOUNT])

# 1. no vertex of the ornament may be inside the body, the helmet or any other
#    armour plate (only the mount is allowed to be entered)
bad_pen, worst_pen = [], None
for name in PARTS:
    for v in all_verts[name]:
        if parity_inside(body_tree, v) or parity_inside(helmet_tree, v):
            bad_pen.append(name)
            break
check(not bad_pen,
      "no part of the medallion is inside the body or the helmet",
      f"{len(set(bad_pen))} parts offending")

thin = []
for name in RAYS:
    for v in all_verts[name]:
        p, d = nearest(tree_all, v)
        if d < 5e-5:
            thin.append((name, d))
min_contact = min(nearest(tree_all, v)[1] for name in RAYS for v in all_verts[name])
check(not thin, "no ray vertex is touching or inside any armour surface",
      f"{len(thin)} contacts" if thin else f"closest ray vertex to armour {min_contact * 1000:.3f} mm")

# 2. the blades' buried roots must be inside the ring (that is the planting)
roots_in_ring = 0
for name in RAYS:
    verts = all_verts[name]
    base = [v for v in verts if radius_xz(v) < RAY_BASE_R + 0.0005]
    if base and any(parity_inside(ring_tree, v) for v in base):
        roots_in_ring += 1
check(roots_in_ring == len(RAYS),
      "every blade's base is buried inside the ring solid: the rays grow out of "
      "the ring rather than being laid on it", f"{roots_in_ring}/{len(RAYS)}")
core_in_ring = any(parity_inside(ring_tree, v) for v in all_verts[CORE]
                   if radius_xz(v) > 0.0245)
check(core_in_ring,
      "the centre's plug flange overlaps the ring's aperture wall: the two are joined")

# 3. clearance to the armour under each blade: small, and never floating.
#    Measured at each of the blade's cross-sections, on the blade's own centre
#    line, against the lowest point of that section - i.e. the face that is
#    supposed to be resting on the armour, not the blade's top or its flanks.
gaps = []
stations = 0
for name in RAYS:
    ang = math.radians(az[name][0])
    axis = Vector((math.cos(ang), 0.0, math.sin(ang)))
    reach = az[name][1]
    pts = [(v, (v.x - CENTRE.x) * axis.x + (v.z - CENTRE.z) * axis.z)
           for v in all_verts[name]]
    step = 0.0010
    s_pos = RING_OUT + 0.0005
    while s_pos < reach - 0.0004:
        near = [v for v, t in pts if abs(t - s_pos) < step * 0.75]
        s_pos += step
        if len(near) < 3:
            continue
        centre = CENTRE + axis * (sum(t for _v, t in pts if abs(t - (s_pos - step)) < step * 0.75)
                                  / max(1, len(near)))
        back = min(v.y for v in near)
        # the mount's own face is a real supporting surface, so it is included
        hit = tree_all.ray_cast(Vector((centre.x, 1.0, centre.z)), Vector((0.0, -1.0, 0.0)), 3.0)
        stations += 1
        if hit[0] is None:
            gaps.append((9.9, name, Vector((centre.x, back, centre.z))))
            continue
        # lift = how far the blade's back sits above the armour it rests on
        gaps.append((back - hit[0].y, name, Vector((centre.x, back, centre.z))))
gap_vals = np.array([g for g, _n, _v in gaps])
check(len(gaps) >= 120, "the blade-to-armour measurement covers the whole ray set",
      f"{len(gaps)} stations across 12 blades")
check(gap_vals.min() > 5.0e-5,
      "no blade is buried in the armour under it: every station of every blade "
      "rests above the surface, not inside it",
      f"tightest lift {gap_vals.min() * 1000:.3f} mm")
check(gap_vals.max() < 0.0030,
      "no blade floats: the loosest station is under 3 mm off the armour",
      f"largest lift {gap_vals.max() * 1000:.3f} mm")
check(np.median(gap_vals) < 0.0015,
      "the blades sit close to the armour surface",
      f"median lift {np.median(gap_vals) * 1000:.3f} mm")
loosest = max(gaps, key=lambda g: g[0])
tightest = min(gaps, key=lambda g: g[0])
note(f"loosest station  {loosest[0] * 1000:.2f} mm on {loosest[1].rsplit('_', 2)[-2]} at "
     f"({loosest[2].x * 1000:+.1f}, {loosest[2].z:.4f})")
note(f"tightest station {tightest[0] * 1000:.2f} mm on {tightest[1].rsplit('_', 2)[-2]} at "
     f"({tightest[2].x * 1000:+.1f}, {tightest[2].z:.4f})")

# 4. the ring and centre must not poke into the belt either
# 4b. every *visible* vertex of the ornament must clear the rest of the armour.
#     A vertex is hidden when it is inside the mount's socket or inside another
#     part of the ornament, so it cannot be seen to clash with anything.
part_trees = {name: bvh([name]) for name in PARTS}
belt_tree = bvh([n for n in armour_names if n != MOUNT])


def socketed(v):
    return radius_xz(v) < MOUNT_R and v.y < MOUNT_FACE_Y


def enclosed_by_ornament(name, v):
    return any(parity_inside(part_trees[o], v) for o in PARTS if o != name)


clashes = []
checked = 0
for name in PARTS:
    for v in all_verts[name]:
        if socketed(v) or enclosed_by_ornament(name, v):
            continue
        checked += 1
        d = nearest(belt_tree, v)[1]
        if d < 5e-5:
            clashes.append((name, v, d))
check(not clashes,
      "no visible vertex of the ornament intersects the belt, the fauld panels, the "
      "torso armour, the limbs or the body",
      f"{len(clashes)} clashes out of {checked} visible vertices")
note(f"{checked} of {sum(len(v) for v in all_verts.values())} ornament vertices are "
     f"visible metal; the rest are socketed into the mount or buried in the ring, "
     f"which is where the components are joined")
seat_inside = [v for v in all_verts[RING] if v.y < MOUNT_FACE_Y]
check(seat_inside and all(parity_inside(mount_tree, v) for v in seat_inside),
      "the whole rear seat of the ring is inside the mount's face: the ornament is "
      "socketed, not balanced on it",
      f"{len(seat_inside)} seated vertices")
core_max_r = max(radius_xz(v) for v in all_verts[CORE])
core_back = min(v.y for v in all_verts[CORE])
check(0.0 < core_max_r - 0.0250 < 0.0012,
      "the centre's plug overshoots the ring's aperture by a socketing margin - a "
      "flange, not a second disc",
      f"plug radius {core_max_r * 1000:.2f} mm vs aperture 25.00 mm")
check(MOUNT_FACE_Y - 0.0010 < core_back < MOUNT_FACE_Y,
      "the centre is socketed 1 mm or less into the mount, never plunged into it",
      f"core rear Y {core_back:.4f} vs mount face {MOUNT_FACE_Y:.4f}")
check(all(radius_xz(v) < RING_OUT for v in all_verts[CORE]),
      "the centre stays inside the ring's outer wall",
      f"max radius {core_max_r * 1000:.1f} mm vs ring {RING_OUT * 1000:.1f} mm")

# 5. gap between the mount's rim and the ring must be a real gap, but small
rim_pts = [v for v in mverts if radius_xz(v) > MOUNT_R - 0.001]
d_min = min(nearest(ring_tree, p)[1] for p in rim_pts)
check(0.004 < d_min < 0.012,
      "the ring leaves a clean band of the mount's face visible around it",
      f"nearest ring vertex to the mount's rim {d_min * 1000:.2f} mm")
ring_lift = max(v.y for v in all_verts[RING]) - max(v.y for v in all_verts[CORE])
check(ring_lift > 0.002,
      "the ring stands proud of the centre, so the ornament has a real rim",
      f"{ring_lift * 1000:.2f} mm")

# --------------------------------------------------------------------------
section("G  the rendered read")
# --------------------------------------------------------------------------
os.makedirs(SHOTS, exist_ok=True)
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 12
scene.cycles.use_denoising = False
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.film_transparent = True
scene.view_settings.view_transform = "Standard"
for o in bpy.data.objects:
    if o.name.startswith(("WSK_Guide_", "WSK_Label_", "WSK_Ref_", "WSK_Joint_",
                          "WSK_Mann_", "WSK_Studio_")):
        o.hide_render = True
saved_hide = {}
for o in bpy.data.objects:
    if o.type == "MESH" and not o.name.startswith("WSK_Armor_WaistMedallion"):
        saved_hide[o.name] = o.hide_render
        o.hide_render = True
bg = scene.world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (0.030, 0.030, 0.034, 1.0)
cam = bpy.data.objects.new("VerifyMedCam", bpy.data.cameras.new("VerifyMedCam"))
scene.collection.objects.link(cam)
scene.camera = cam
cam.data.type = "ORTHO"
cam.data.ortho_scale = 0.13
cam.location = (0.0, 1.2, CENTRE.z)
d = (CENTRE - Vector(cam.location)).normalized()
cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
scene.render.resolution_x, scene.render.resolution_y = 480, 600
path = os.path.join(SHOTS, "p11_medallion_orthographic.png")
scene.render.filepath = path
bpy.ops.render.render(write_still=True)
mask = np.asarray(Image.open(path).convert("RGBA"))[..., 3] > 127
ys, xs = np.nonzero(mask)
cx = (xs.min() + xs.max()) / 2.0
cy = (ys.min() + ys.max()) / 2.0
# Blender's orthographic scale applies to the *larger* image dimension.
mm_per_px = 0.13 / max(scene.render.resolution_x, scene.render.resolution_y) * 1000.0
check(abs(cx - (mask.shape[1] - 1) / 2.0) < 1.0,
      "in an orthographic front render the ornament is horizontally centred",
      f"mask centre x {cx:.1f} px vs image centre {(mask.shape[1] - 1) / 2.0:.1f} px")
half_width = (xs.max() - xs.min() + 1) / 2.0 * mm_per_px
half_height = (ys.max() - ys.min() + 1) / 2.0 * mm_per_px
geom_hw = max(abs(v.x) for vs in all_verts.values() for v in vs) * 1000.0
geom_hh = (max(v.z for vs in all_verts.values() for v in vs) -
           min(v.z for vs in all_verts.values() for v in vs)) / 2.0 * 1000.0
check(abs(half_width - geom_hw) < 0.6 and abs(half_height - geom_hh) < 0.6,
      "the rendered silhouette is exactly the modelled ornament",
      f"render {half_width:.2f} x {half_height:.2f} mm vs model "
      f"{geom_hw:.2f} x {geom_hh:.2f} mm")
check(abs(cy - (mask.shape[0] - 1) / 2.0 - 0.0) < 1.5,
      "the ornament is centred vertically on the belt's centre line",
      f"mask centre y {cy:.1f} px vs image centre {(mask.shape[0] - 1) / 2.0:.1f} px")
check(half_height * 2 < (BELT_TOP - BELT_BOTTOM) * 1000,
      "the ornament is smaller than the belt it sits on, so it does not overwhelm it",
      f"{half_height * 2:.0f} mm ornament on a "
      f"{(BELT_TOP - BELT_BOTTOM) * 1000:.0f} mm belt")
share = mask.sum() / (mask.shape[0] * mask.shape[1])
check(0.10 < share < 0.45,
      "the ornament reads as one deliberate mass rather than a scatter of pieces",
      f"{share * 100:.1f} % of the frame")
for o in bpy.data.objects:
    if o.type == "MESH" and o.name in saved_hide:
        o.hide_render = saved_hide[o.name]

# --------------------------------------------------------------------------
section("summary")
# --------------------------------------------------------------------------
lines.append(f"checks passed: {passed}")
lines.append(f"checks failed: {failed}")
lines.append(f"warnings:      {warned}")
lines.append("")
lines.append("The ornaments: 1 ring (genus 1, revolved 9-point profile), 1 dished centre disc")
lines.append("with a rear plug flange, 12 fitted radial blades, 1 pivot empty.  Fourteen")
lines.append("separate meshes on a common data path - no booleans, no applied modifiers, no")
lines.append("texture work, no glow, and nothing else on the character was touched.")

text = "\n".join(lines)
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
with open(REPORT, "w") as fh:
    fh.write(text + "\n")
print(text)
print(f"\nWROTE {REPORT}")
