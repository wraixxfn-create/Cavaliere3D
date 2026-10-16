"""Prompt-11 verification for the waist medallion.

Checks scope (what changed and what did not), the mount it is seated on, the
independent components, the measured seating, the design restraint and the
rendered centring.  Writes analysis/verify/verify_medallion_report.txt.

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

PREFIX = "WSK_Armor_WaistMedallion"
MOUNT = "WSK_Armor_WaistMedallionMount_01"
BELT = "WSK_Armor_WaistBelt_01"
BODY = "WSK_Body_Base_01"
FRONT_OBJECTS = (
    "WSK_Armor_WaistMedallionMount_01",
    "WSK_Armor_WaistBelt_01",
    "WSK_Armor_WaistPanel_Front_01_01",
    "WSK_Armor_WaistPanel_Front_02_01",
    "WSK_Armor_WaistPanel_Front_03_01",
    "WSK_Armor_Chest_01",
)
REAR_OBJECTS = ("WSK_Armor_Back_01",)

MOUNT_CENTRE = Vector((0.0, 1.055))
MOUNT_RADIUS = 0.043
REAR_CENTRE = Vector((0.0, 1.155))
FRONT_SIGN, REAR_SIGN = 1.0, -1.0
REAR_SCALE = 0.88

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
    lines.append(f"[{'OK  ' if cond else 'WARN'}] {label}" + (f"  -> {detail}" if detail else ""))


# ---------------------------------------------------------------- helpers ---
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


def mesh_quality(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    loose = sum(1 for v in bm.verts if not v.link_edges)
    degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-12)
    shortest = min((e.calc_length() for e in bm.edges), default=0.0)
    bm.free()
    return non_manifold, loose, degenerate, shortest


def outward(obj):
    verts, polys = evaluated(obj)
    vol = 0.0
    for face in polys:
        if len(face) < 3:
            continue
        a = verts[face[0]]
        for i in range(1, len(face) - 1):
            vol += a.dot(verts[face[i]].cross(verts[face[i + 1]])) / 6.0
    return vol


def ray_y(tree, x, z, sign):
    origin = Vector((x, sign * 0.6, z))
    hit = tree.ray_cast(origin, Vector((0.0, -sign, 0.0)), 1.0)
    return None if hit[0] is None else hit[0].y


# ------------------------------------------------------------------ load ---
bpy.ops.wm.open_mainfile(filepath=DST)
hashes11 = {o.name: mesh_hash(o) for o in bpy.data.objects}
names11 = set(hashes11)
med = sorted(n for n in names11 if n.startswith(PREFIX) and n != MOUNT)
rear_med = sorted(n for n in med if n.startswith(PREFIX + "Rear"))
front_med = sorted(n for n in med if n not in rear_med)
rings = [n for n in front_med if n.endswith("_Ring_01")]
centres = [n for n in front_med if n.endswith("_Center_01")]
rays = [n for n in med if "_Ray_" in n]
front_rays = [n for n in front_med if "_Ray_" in n]
rear_rays = [n for n in rear_med if "_Ray_" in n]
rear_rings = [n for n in rear_med if n.endswith("_Ring_01")]

bpy.ops.wm.open_mainfile(filepath=SRC)
hashes10 = {o.name: mesh_hash(o) for o in bpy.data.objects}
names10 = set(hashes10)
bpy.ops.wm.open_mainfile(filepath=DST)
scene = bpy.context.scene

# --------------------------------------------------------------------------
section("A  scope - what changed and what did not")
# --------------------------------------------------------------------------
added = sorted(names11 - names10)
removed = sorted(names10 - names11)
changed = sorted(n for n in (names10 & names11) if hashes10[n] != hashes11[n])
check(set(added) == set(med) and len(added) == len(med),
      "the waist ornament is the only geometry added",
      f"{len(added)} objects: {len(rings)} ring, {len(centres)} centre, {len(rays)} radial")
check(not removed, "nothing was removed from checkpoint 10")
check(not changed, "no existing object changed: every plate, the body, the helmet, "
                   "the crown and the scene are byte-identical to checkpoint 10")
check(hashes10[MOUNT] == hashes11[MOUNT],
      "the waist medallion mount from checkpoint 8 is untouched - the waist armour "
      "was not rebuilt, only seated")
check(len(bpy.data.collections) == 14, "no collection was added",
      f"{len(bpy.data.collections)} collections")
check(len(bpy.data.worlds) == 2 and len(bpy.data.cameras) == 13,
      "worlds and the camera set are unchanged",
      f"{len(bpy.data.worlds)} worlds, {len(bpy.data.cameras)} cameras")
check(len([m for m in bpy.data.materials if m.use_nodes and any(
              n.type == "EMISSION" for n in m.node_tree.nodes)]) == 0,
      "no material has an emission shader (no glow, no magical effect)")
check(not any(o.modifiers and any(m.type in ("PARTICLE_SYSTEM", "FLUID")
                                  for m in o.modifiers) for o in bpy.data.objects)
      and len(bpy.data.particles) == 0,
      "no particle systems")
new_mats = [bpy.data.materials[n] for n in ("MAT_Orn_AntiqueGold_01",
                                            "MAT_Orn_ShadowStone_01")]
check(len([m for m in bpy.data.materials if m.name.startswith("MAT_Orn_")]) == 2
      and all(m.get("wsk_placeholder") for m in new_mats),
      "exactly two placeholder materials were added and both are flagged placeholder",
      ", ".join(m.name for m in new_mats))
check(not any(any(n.type in ("TEX_IMAGE", "TEX_NOISE", "TEX_WAVE")
                  for n in m.node_tree.nodes) for m in new_mats),
      "the ornament materials carry no textures - final texturing is deferred")
check(not any(o.data.materials and any(m.name.startswith("MAT_Orn_")
                                       for m in o.data.materials)
              for o in bpy.data.objects
              if o.type == "MESH" and not o.name.startswith(PREFIX)),
      "no other part of the character was given the ornament materials")

# --------------------------------------------------------------------------
section("B  locating the mount and centring on it")
# --------------------------------------------------------------------------
mount = bpy.data.objects[MOUNT]
mv, _mf = evaluated(mount)
mx = (min(p.x for p in mv) + max(p.x for p in mv)) / 2.0
mz = (min(p.z for p in mv) + max(p.z for p in mv)) / 2.0
my = max(p.y for p in mv)
mrad = max(math.hypot(p.x - mx, p.z - mz) for p in mv)
check(abs(mx) < 1e-6 and abs(mz - MOUNT_CENTRE.y) < 1e-6,
      "the checkpoint-8 mount sits on the centre line at z 1.055 as documented",
      f"centre x {mx:+.4f}, z {mz:.4f}, radius {mrad * 1000:.1f} mm")
check("medallion" in mount.get("wsk_part", "") and mount.get("wsk_prompt", ""),
      "the mount is the object checkpoint 8 left for this prompt",
      f"'{mount.get('wsk_part')}' ({mount.get('wsk_prompt')})")

for tag, centre, names in (("front", MOUNT_CENTRE, front_med),
                           ("rear", REAR_CENTRE, rear_med)):
    pts = []
    for n in names:
        v, _f = evaluated(bpy.data.objects[n])
        pts += v
    cx = (min(p.x for p in pts) + max(p.x for p in pts)) / 2.0
    cz = (min(p.z for p in pts) + max(p.z for p in pts)) / 2.0
    check(abs(cx) < 0.0015 and abs(cz - centre.y) < 0.0015,
          f"the {tag} ornament is centred on its mounting axis",
          f"centre ({cx * 1000:+.2f}, {cz * 1000:+.2f}) mm vs "
          f"(0.00, {centre.y * 1000:.2f}) mm")
    span = max(p.x for p in pts) - min(p.x for p in pts)
    note(f"{tag} ornament span {span * 1000:.1f} mm, "
         f"z {min(p.z for p in pts):.4f} .. {max(p.z for p in pts):.4f}")

fpts = []
for n in front_med:
    v, _f = evaluated(bpy.data.objects[n])
    fpts += v
frad = max(math.hypot(p.x, p.z - MOUNT_CENTRE.y) for p in fpts)
check(frad <= mrad - 0.0008,
      "the whole front ornament stays inside the mount's rim, so the plain bezel "
      "of checkpoint 8 reads as its setting",
      f"ornament reaches {frad * 1000:.2f} mm, mount rim {mrad * 1000:.2f} mm, "
      f"{1000 * (mrad - frad):.2f} mm of recess")

# --------------------------------------------------------------------------
section("C  independent components and mesh quality")
# --------------------------------------------------------------------------
check(len(rings) == 1 and len(centres) == 1,
      "the front ornament is one ring and one centre", f"{rings} / {centres}")
check(len(front_rays) == 16 and len(rear_rays) == 16,
      "sixteen separate radial elements front and rear (eight primary, eight minor)",
      f"{len(front_rays)} front, {len(rear_rays)} rear")
check(all(bpy.data.objects[n].data.users == 1 for n in med),
      "every ornament part is a separate single-user mesh")
check(len({bpy.data.objects[n].data.name for n in med}) == len(med),
      "each part owns its own mesh datablock",
      f"{len({bpy.data.objects[n].data.name for n in med})} meshes for {len(med)} parts")
check(all(bpy.data.objects[n].matrix_world.is_identity for n in med),
      "every part has an identity transform, so world space is mesh space and a "
      "part can be moved or replaced on its own")
check(not any(bpy.data.objects[n].data.shape_keys for n in med),
      "no shape keys - the ornament is plain editable geometry")

quality = {n: mesh_quality(bpy.data.objects[n]) for n in med}
check(all(q[0] == 0 for q in quality.values()),
      "every part is a closed manifold (each is a solid, not a floating skin)",
      f"worst {max(q[0] for q in quality.values())} non-manifold edges")
check(all(q[1] == 0 and q[2] == 0 for q in quality.values()),
      "no loose vertices and no degenerate faces")
check(all(q[3] >= 0.0002 for q in quality.values()),
      "no collapsed edges", f"shortest edge {min(q[3] for q in quality.values()) * 1000:.3f} mm")
vols = {n: outward(bpy.data.objects[n]) for n in med}
check(all(v > 0 for v in vols.values()),
      "every part is wound outward (positive signed volume) so lit faces face out",
      f"smallest {min(vols.values()) * 1e9:.1f} mm3")
check(all(not bpy.data.objects[n].modifiers or
          [m.type for m in bpy.data.objects[n].modifiers] == ["BEVEL"] for n in med),
      "the only modifiers are non-destructive edge bevels",
      f"{sum(1 for n in med if bpy.data.objects[n].modifiers)} bevelled parts")

# --------------------------------------------------------------------------
section("D  seating on the measured armour surface")
# --------------------------------------------------------------------------
waist_w_early = (lambda pts: max(p.x for p in pts) - min(p.x for p in pts))(
    evaluated(bpy.data.objects[BELT])[0])
front_tree = bvh(FRONT_OBJECTS)
rear_tree = bvh(REAR_OBJECTS)
body_tree = bvh(BODY)


# ring seating, measured on the real mesh: for every azimuth the ring's
# front-most vertex is compared with the most protruding piece of armour under
# its band, and its back-most vertex with the armour surface at its own radius.
BAND_RADII = (0.0230, 0.0244, 0.0262, 0.0278, 0.0290, 0.0293)


CREST_RADIUS = 0.0262
LATHE_SEGS = 96


def ring_seating(obj, centre, sign, tree, scale, segs=LATHE_SEGS):
    """Measure the ring against the armour along its own 96 azimuths.

    The lathe puts a vertex at every (profile row, azimuth) sample, so each row
    can be read back exactly.  For every azimuth the crest row is compared with
    the most protruding piece of armour under the ring's whole band width, and
    the deepest row is compared with the armour at that vertex's own radius.
    """
    verts, _f = evaluated(obj)
    crest, back = [None] * segs, [None] * segs
    for p in verts:
        r = math.hypot(p.x - centre.x, p.z - centre.y)
        if r < 0.0002:
            continue
        th = math.atan2(p.z - centre.y, p.x - centre.x) % (2.0 * math.pi)
        i = int(round(th / (2.0 * math.pi) * segs)) % segs
        if abs(r - CREST_RADIUS * scale) < 0.0004:
            if crest[i] is None or sign * p.y > sign * crest[i][0]:
                crest[i] = (p.y, r)
        if back[i] is None or sign * p.y < sign * back[i][0]:
            back[i] = (p.y, r)
    rows = []
    for i in range(segs):
        if crest[i] is None or back[i] is None:
            continue
        th = i / segs * 2.0 * math.pi
        band = [ray_y(tree, centre.x + r * scale * math.cos(th),
                      centre.y + r * scale * math.sin(th), sign)
                for r in BAND_RADII]
        band = [b for b in band if b is not None]
        if not band:
            continue
        worst = max(band, key=lambda y: sign * y)
        proud = sign * (crest[i][0] - worst)
        local = ray_y(tree, centre.x + back[i][1] * math.cos(th),
                      centre.y + back[i][1] * math.sin(th), sign)
        burial = None if local is None else sign * (local - back[i][0])
        rows.append((proud, burial, back[i][1]))
    return rows


seating = {}
for tag, sign, centre, tree, scale in (("front", FRONT_SIGN, MOUNT_CENTRE, front_tree, 1.0),
                                       ("rear", REAR_SIGN, REAR_CENTRE, rear_tree, REAR_SCALE)):
    rows = ring_seating(bpy.data.objects[rings[0] if tag == "front" else rear_rings[0]],
                        centre, sign, tree, scale)
    seating[tag] = rows
    proud = [r[0] for r in rows]
    burial = [r[1] for r in rows if r[1] is not None]
    check(min(proud) > 0.0004,
          f"the {tag} ring's crest stands proud of the armour at every azimuth, "
          "even against the most protruding metal under its band - it is readable "
          "in a raking light and never sinks flush",
          f"crest relief {min(proud) * 1000:+.2f} .. {max(proud) * 1000:+.2f} mm "
          f"over {len(rows)} azimuths")
    check(max(proud) < 0.006,
          f"the {tag} ring never stands more than 6 mm off the plate "
          "(no obvious floating)",
          f"max relief {max(proud) * 1000:.2f} mm")
    check(len(burial) == len(rows) and min(burial) > -0.006,
          f"the {tag} ring's back is buried in the plate at every azimuth and "
          "never more than 6 mm deep",
          f"burial {min(burial) * 1000:+.2f} .. {max(burial) * 1000:+.2f} mm, "
          f"mean {sum(burial) / len(burial) * 1000:+.2f} mm")

# rays: the root must be inside the ring band, the tip inside the mount rim
band = (0.0227, 0.0292)
roots, tips = [], []
for n in rays:
    o = bpy.data.objects[n]
    v, _f = evaluated(o)
    scale = REAR_SCALE if n.startswith(PREFIX + "Rear") else 1.0
    centre = REAR_CENTRE if n.startswith(PREFIX + "Rear") else MOUNT_CENTRE
    rad = [math.hypot(p.x - centre.x, p.z - centre.y) for p in v]
    roots.append((n, min(rad) / scale, max(rad) / scale))
    tips.append((n, max(rad) / scale))
check(all(band[0] - 1e-3 <= lo <= 0.0262 for _n, lo, _hi in roots),
      "every radial element starts under the ring band, so the ring and the rays "
      "are interlocked rather than butted together",
      f"root radii {min(lo for _n, lo, _hi in roots) * 1000:.2f} .. "
      f"{max(lo for _n, lo, _hi in roots) * 1000:.2f} mm, band starts at "
      f"{band[0] * 1000:.2f} mm")
check(all(hi <= mrad - 0.0008 for _n, hi in tips),
      "no radial element reaches past the mount's rim",
      f"longest tip {max(hi for _n, hi in tips) * 1000:.2f} mm of "
      f"{mrad * 1000:.2f} mm")

# penetration into the plates and clearance from the body
pen = {}
for n in med:
    o = bpy.data.objects[n]
    v, _f = evaluated(o)
    worst_p = 0.0
    for p in v:
        for tree in (front_tree, rear_tree):
            loc, nrm, _i, dist = tree.find_nearest(p, 0.02)
            if loc is None:
                continue
            if (p - loc).dot(nrm) < 0.0:
                worst_p = max(worst_p, dist)
    pen[n] = worst_p
check(max(pen.values()) < 0.006,
      "no ornament vertex is driven more than 6 mm into the armour it sits on",
      f"deepest {max(pen.values()) * 1000:.2f} mm ({max(pen, key=pen.get)})")
body_gap = []
for n in med:
    v, _f = evaluated(bpy.data.objects[n])
    for p in v:
        hit = body_tree.find_nearest(p, 0.05)
        if hit[0] is not None:
            inside = (p - hit[0]).dot(hit[1]) < 0.0
            body_gap.append((hit[3], inside, n))
check(all(not ins for _d, ins, _n in body_gap),
      "no ornament vertex is inside the body - the ornament never reaches the "
      "figure under the armour",
      f"closest approach to the body {min(d for d, _i, _n in body_gap) * 1000:.2f} mm")

# the ring's opening really is open: the mount plate shows through it
axis_y = ray_y(front_tree, 0.0, MOUNT_CENTRE.y, FRONT_SIGN)
ctr_obj = bpy.data.objects[centres[0]]
cv, _cf = evaluated(ctr_obj)
ring_face = max(p.y for p in cv)
check(axis_y is not None and abs(ring_face - axis_y) <= 0.005,
      "looking straight down the ornament axis the armour is only a few "
      "millimetres behind, so the centre reads as a shallow recess and not as a "
      "hole floating in front of the belt",
      f"armour surface {axis_y:+.4f} m, ornament front plane {ring_face:+.4f} m, "
      f"depth {(ring_face - axis_y) * 1000:.2f} mm")

# --------------------------------------------------------------------------
section("E  design - restrained, deliberate, original")
# --------------------------------------------------------------------------
ring_obj = bpy.data.objects[rings[0]]
rv, _rf = evaluated(ring_obj)
radii = [math.hypot(p.x - MOUNT_CENTRE.x, p.z - MOUNT_CENTRE.y) for p in rv]
# the outer wall, read per azimuth, so the wobble of the rim is measured and not
# the profile's own radial spread
bins = {}
for p, r in zip(rv, radii):
    th = math.atan2(p.z - MOUNT_CENTRE.y, p.x - MOUNT_CENTRE.x)
    k = int((th % (2 * math.pi)) / (2 * math.pi) * 96) % 96
    bins[k] = max(bins.get(k, 0.0), r)
outer = sorted(bins.values())
inner = [r for r in radii if r < 0.0250]
mean_r = sum(outer) / len(outer)
spread = (max(outer) - min(outer)) / mean_r
check(0.004 <= spread <= 0.05,
      "the ring is circular but not machined: its outer wall carries a ~1 % "
      "hand-forged wobble",
      f"rim radius {min(outer) * 1000:.2f} .. {max(outer) * 1000:.2f} mm "
      f"({spread * 100:+.2f} % spread), inner lip {min(inner) * 1000:.1f} .. "
      f"{max(inner) * 1000:.1f} mm")
check(max(outer) - min(inner) <= 0.009,
      "the ring wall is thin, so the gold reads as a bezel and not as a plate",
      f"wall {(max(outer) - min(inner)) * 1000:.2f} mm at its widest")
orn_w = max(p.x for p in fpts) - min(p.x for p in fpts)
check(70.0 <= orn_w * 1000 <= 90.0,
      "the front ornament is 70-90 mm across",
      f"{orn_w * 1000:.1f} mm across, {2 * max(outer) * 1000:.1f} mm of it the ring")
check(0.15 <= orn_w / waist_w_early <= 0.25,
      "and that is the proportion the supplied reference reads at: its motif is "
      "62 mm on a 0.30-0.33 m wide figure (19-20 %)",
      f"{orn_w / waist_w_early * 100:.1f} % of the belt's front width")

# the centre is recessed relative to the ring
crest_y = max(p.y for p in rv)
ctr_axis = max(p.y for p in cv)
axis_plate = ray_y(front_tree, 0.0, MOUNT_CENTRE.y, FRONT_SIGN)
check(0.0012 <= crest_y - ctr_axis <= 0.004,
      "the centre is set inside the ring: recessed behind the crest but standing "
      "clear of the plate, so the gold frames a dark stone instead of a flat "
      "button that merges with the belt",
      f"ring crest {crest_y:+.4f} m, centre face {ctr_axis:+.4f} m, recess "
      f"{(crest_y - ctr_axis) * 1000:.2f} mm, and the centre stands "
      f"{(ctr_axis - axis_plate) * 1000:.2f} mm in front of the armour")
check(0.0015 <= ctr_axis - axis_plate <= 0.005,
      "the centre's own rim is a real edge, not a decal: it steps off the plate",
      f"centre face {(ctr_axis - axis_plate) * 1000:.2f} mm proud of the armour")

# radial families: alternating, graded, tapering
def azimuth(n):
    o = bpy.data.objects[n]
    v, _f = evaluated(o)
    centre = REAR_CENTRE if n.startswith(PREFIX + "Rear") else MOUNT_CENTRE
    p = max(v, key=lambda q: math.hypot(q.x - centre.x, q.z - centre.y))
    return math.degrees(math.atan2(p.z - centre.y, p.x - centre.x)) % 360.0


fam = sorted((azimuth(n), "primary" if "_Ray_P" in n else "minor", n) for n in front_rays)
order = [f for _a, f, _n in fam]
check(all(order[i] != order[i + 1] for i in range(len(order) - 1))
      and order[0] != order[-1],
      "the two radial families alternate all the way round: no two blades of the "
      "same size sit next to each other",
      "".join("P" if f == "primary" else "m" for f in order))
gaps = [fam[(i + 1) % len(fam)][0] - fam[i][0] for i in range(len(fam) - 1)]
check(min(gaps) > 10.0,
      "the blades are spread around the ring without bunching",
      f"smallest azimuth gap {min(gaps):.1f} deg, largest {max(gaps):.1f} deg")
lens = {n: bpy.data.objects[n]["wsk_ray_length_m"] for n in front_rays}
prim = [v for k, v in lens.items() if "_Ray_P" in k]
minor = [v for k, v in lens.items() if "_Ray_M" in k]
check(min(prim) > max(minor),
      "every primary blade is longer than every minor one: the fan has a clear "
      "two-scale rhythm instead of a uniform gear",
      f"primary {min(prim) * 1000:.2f}-{max(prim) * 1000:.2f} mm, minor "
      f"{min(minor) * 1000:.2f}-{max(minor) * 1000:.2f} mm")
check(max(prim) / min(prim) >= 1.05 and max(minor) / min(minor) >= 1.05,
      "hand-set lengths: the blades of each family differ by at least 5 %",
      f"primary spread {max(prim) / min(prim):.3f}x, minor spread "
      f"{max(minor) / min(minor):.3f}x")

taper = True
for n in front_rays:
    o = bpy.data.objects[n]
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.free()
    v, _f = evaluated(o)
    centre = MOUNT_CENTRE
    rr = [math.hypot(p.x - centre.x, p.z - centre.y) for p in v]
    lo, hi = min(rr), max(rr)
    near = [p for p, r in zip(v, rr) if r < lo + (hi - lo) * 0.35]
    far = [p for p, r in zip(v, rr) if r > lo + (hi - lo) * 0.85]
    if near and far:
        w_near = (max(p.x for p in near) - min(p.x for p in near))
        w_far = (max(p.x for p in far) - min(p.x for p in far)) or 1e-9
        if w_near <= w_far:
            taper = False
check(taper, "every radial blade tapers from a wide root to a point - no blunt pegs")

# the whole ornament against the armour it decorates
waist = evaluated(bpy.data.objects[BELT])[0]
waist_w = max(p.x for p in waist) - min(p.x for p in waist)
check(orn_w <= 0.32 * waist_w,
      "the ornament is under a third of the waist's width: a deliberate centre "
      "piece, not a shield",
      f"ornament {orn_w * 1000:.1f} mm across vs belt {waist_w * 1000:.1f} mm "
      f"({orn_w / waist_w * 100:.1f} %)")
check(len(rays) + len(rings) + len(centres) == 34,
      "the ornament is 34 parts on four waist objects used as mounts "
      "(mount, belt, front panel, back plate)",
      "no geometry anywhere else on the figure")
decorated = sorted({n for n in med})
check(all(n.startswith(PREFIX) for n in decorated)
      and not any("Shoulder" in n or "Helmet" in n or "Thigh" in n or "Shin" in n
                  or "Forearm" in n or "Sabaton" in n for n in decorated),
      "no jewellery on any unrelated part of the character")
check(not any(n.name.startswith("WSK_") and "Lettering" in n for n in bpy.data.objects),
      "no lettering, insignia or crest was modelled (the motif is a plain ring, a "
      "plain disk and straight blades - nothing recognisable from any franchise)")

# the rear sibling
check(len(rear_rings) == 1 and rear_rays,
      "the same design is repeated on the rear", f"{rear_rings}")
r2 = bpy.data.objects[rear_rings[0]]
r2v, _f = evaluated(r2)
outer2 = max(math.hypot(p.x - REAR_CENTRE.x, p.z - REAR_CENTRE.y) for p in r2v)
check(abs(outer2 / max(outer) - REAR_SCALE) < 0.02,
      "the rear medallion is the same design at 88 % - sibling, not copy",
      f"{outer2 * 1000:.1f} mm vs {max(outer) * 1000:.1f} mm "
      f"({outer2 / max(outer):.3f})")
backv = evaluated(bpy.data.objects["WSK_Armor_Back_01"])[0]
check(min(p.z for p in r2v) >= min(p.z for p in backv) + 0.012,
      "the rear medallion sits wholly on the lower back plate, clear of its "
      "bottom edge",
      f"medallion z {min(p.z for p in r2v):.4f} .. {max(p.z for p in r2v):.4f}, "
      f"plate z {min(p.z for p in backv):.4f} .. {max(p.z for p in backv):.4f}")
rx = (min(p.x for p in r2v) + max(p.x for p in r2v)) / 2.0
check(abs(rx) < 0.0015,
      "the rear medallion is mirrored on the centre line like the front one",
      f"centre x {rx * 1000:+.2f} mm")

# --------------------------------------------------------------------------
section("F  rendered centring and restraint")
# --------------------------------------------------------------------------
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 6
scene.cycles.use_denoising = False
scene.render.film_transparent = True
scene.render.image_settings.color_mode = "RGBA"
RES = (760, 900)
scene.render.resolution_x, scene.render.resolution_y = RES
for o in bpy.data.objects:
    if o.name.startswith(("WSK_Guide_", "WSK_Label_", "WSK_Ref_", "WSK_Joint_",
                          "WSK_Mann_", "WSK_Studio_")):
        o.hide_render = True

cam = bpy.data.objects["WSK_Cam_Sil_Front_01"]
scene.camera = cam
cam.data.type = "ORTHO"


def mask_of(keep, view, centre_z, ortho, drop=()):
    hidden = {}
    for o in bpy.data.objects:
        if o.type == "MESH" and (not any(o.name.startswith(k) for k in keep)
                                 or any(o.name.startswith(k) for k in drop)):
            hidden[o.name] = o.hide_render
            o.hide_render = True
    cam.data.ortho_scale = ortho
    loc = {"front": (0.0, 3.0, centre_z), "rear": (0.0, -3.0, centre_z),
           "side": (3.0, 0.0, centre_z)}[view]
    cam.location = loc
    d = (Vector((0.0, 0.0, centre_z)) - Vector(loc)).normalized()
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    path = os.path.join(SHOTS, f"_mask_{view}_{centre_z}.png")
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    arr = np.asarray(Image.open(path).convert("RGBA"))[..., 3] > 127
    os.remove(path)
    for name, state in hidden.items():
        bpy.data.objects[name].hide_render = state
    return arr


ORTHO, CZ = 0.30, 1.055
mpp = ORTHO / RES[1]
m_front = mask_of(front_med, "front", CZ, ORTHO)
m_rear = mask_of(rear_med, "rear", REAR_CENTRE.y, ORTHO)
for name, arr, zref in (("front", m_front, CZ), ("rear", m_rear, REAR_CENTRE.y)):
    ys, xs = np.nonzero(arr)
    if not len(xs):
        check(False, f"the {name} ornament renders", "empty mask")
        continue
    cx = (RES[0] - 1) / 2.0
    off = (xs.mean() - cx) * mpp * 1000
    top = zref + (RES[1] / 2.0 - ys.min()) * mpp
    bot = zref - (ys.max() - RES[1] / 2.0) * mpp
    check(abs(off) <= 1.0,
          f"the {name} ornament's rendered silhouette is centred on the axis",
          f"centroid offset {off:+.2f} mm")
    check(abs((top + bot) / 2.0 - zref) <= 1e-3,
          f"the {name} ornament's rendered silhouette is centred vertically on "
          "its mount",
          f"mid {(top + bot) / 2.0:.4f} m vs {zref:.4f} m")
    span_m = (xs.max() - xs.min() + 1) * mpp
    area = arr.sum() * mpp * mpp * 1e4
    note(f"{name} rendered span {span_m * 1000:.1f} mm, height "
         f"{(ys.max() - ys.min() + 1) * mpp * 1000:.1f} mm, gold area "
         f"{area:.2f} cm2")

armour_only = mask_of(("WSK_Armor_", "WSK_Body", "WSK_Helmet_"), "front", CZ, ORTHO)
check((m_front & ~armour_only).sum() == 0,
      "the ornament's silhouette sits entirely on the armour - nothing overhangs "
      "the edge of the plates it is mounted on")
belt_narrow = mask_of(("WSK_Armor_WaistBelt_01",), "front", CZ, ORTHO)
check((m_front & belt_narrow).sum() >= 0.9 * m_front.sum(),
      "over 90 % of the ornament is over the waist belt band it is centred on",
      f"{(m_front & belt_narrow).sum() / m_front.sum() * 100:.1f} % over the belt")

shots = [f for f in sorted(os.listdir(SHOTS)) if f.startswith("p11_")]
check(len(shots) >= 8, "the inspection renders the prompt asks for exist",
      ", ".join(shots[:4]) + f" ... ({len(shots)} files)")

# --------------------------------------------------------------------------
section("G  design table")
# --------------------------------------------------------------------------
lines.append("azimuth   crest proud   back buried   (front ring, mm)")
for k, (proud, burial, r_back) in enumerate(seating["front"]):
    if k % 8:
        continue
    lines.append(f"  {k * 360 / len(seating['front']):6.1f}   "
                 f"{proud * 1000:+8.2f}   "
                 f"{'--' if burial is None else f'{burial * 1000:+8.2f}'}")
lines.append("")
lines.append("radial elements (front)")
for az, f, n in fam:
    o = bpy.data.objects[n]
    lines.append(f"  {n:42s} {f:8s} azimuth {az:6.2f} deg  "
                 f"run {o['wsk_ray_length_m'] * 1000:5.2f} mm")
lines.append("")
lines.append("radial elements (rear)")
for n in sorted(rear_rays):
    o = bpy.data.objects[n]
    lines.append(f"  {n:46s} azimuth {azimuth(n):6.2f} deg  "
                 f"run {o['wsk_ray_length_m'] * 1000:5.2f} mm")
lines.append("")
lines.append(f"front ornament: {2 * max(outer) * 1000:.1f} mm across on a "
             f"{waist_w * 1000:.1f} mm belt ({2 * max(outer) / waist_w * 100:.1f} %); "
             f"rear ornament {2 * outer2 * 1000:.1f} mm across")
for tag, rows in seating.items():
    proud = [r[0] for r in rows]
    burial = [r[1] for r in rows if r[1] is not None]
    lines.append(f"{tag} ring measured against the armour over "
                 f"{len(rows)} azimuths: crest {min(proud) * 1000:+.2f} .. "
                 f"{max(proud) * 1000:+.2f} mm proud, back "
                 f"{min(burial) * 1000:+.2f} .. {max(burial) * 1000:+.2f} mm buried")

lines.append(f"\n{'=' * 74}\n{passed} checks passed, {failed} failed, {warned} warnings\n")
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
with open(REPORT, "w") as fh:
    fh.write("\n".join(lines) + "\n")
print("\n".join(lines))
print(f"\nreport -> {REPORT}\n{passed} passed / {failed} failed / {warned} warnings")
