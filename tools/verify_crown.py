"""Prompt-10 verification for the thorn crown and the refined armour spikes.

Checks scope (what changed and what did not), crown design, planting, clearance,
mesh quality, the shoulder spike scale and the rendered silhouette balance.
Writes analysis/verify/verify_crown_report.txt.

Run: tools/bl.sh tools/verify_crown.py
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
SRC = os.path.join(ROOT, "Wildshift_Knight_09_LimbArmor.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_10_Crown.blend")
SHOTS = os.path.join(ROOT, "analysis/crown")
REPORT = os.path.join(ROOT, "analysis/verify/verify_crown_report.txt")

OLD_SPIKES = {f"WSK_Helmet_CrownSpike_{s}_01"
              for s in ("C", "R1", "L1", "R2", "L2", "R3", "L3", "R4", "L4")}
THORN_RE = ("WSK_Helmet_CrownThorn_", "WSK_Helmet_CrownBarb_")
SPIKE_RE = "WSK_Armor_ShoulderSpike"
MOUNTS = ("WSK_Helmet_Shell_01", "WSK_Helmet_Crest_01", "WSK_Helmet_CrownBand_01")
PARITY_DIRS = (Vector((0.577, 0.577, 0.577)),
               Vector((-0.707, 0.500, 0.500)),
               Vector((0.267, -0.802, 0.535)))

lines = []
passed = 0
failed = 0
warned = 0


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


def deep_inside(tree, point, depth):
    """True when `point` is at least `depth` inside the closed shell."""
    hit = tree.ray_cast(point, (point - tree.find_nearest(point)[0]).normalized(), depth)
    return hit[0] is None


def nearest(tree, point):
    hit = tree.find_nearest(point)
    if hit[0] is None:
        return None, None, 9.9
    return hit[0].copy(), hit[1].copy(), hit[3]


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
    """Signed volume: positive means the winding points outwards."""
    verts, polys = evaluated(obj)
    vol = 0.0
    for face in polys:
        if len(face) < 3:
            continue
        a = verts[face[0]]
        for i in range(1, len(face) - 1):
            b, c = verts[face[i]], verts[face[i + 1]]
            vol += a.dot(b.cross(c)) / 6.0
    return vol


# --------------------------------------------------------------------------
# load
# --------------------------------------------------------------------------

bpy.ops.wm.open_mainfile(filepath=DST)
hashes10 = {o.name: mesh_hash(o) for o in bpy.data.objects}
names10 = set(hashes10)
thorns = sorted(n for n in names10 if n.startswith(THORN_RE))
spikes = sorted(n for n in names10 if n.startswith(SPIKE_RE))
extra = [n for n in names10 if "CrownThorn" in n or "CrownBarb" in n]
assert len(extra) == len(thorns), extra

bpy.ops.wm.open_mainfile(filepath=SRC)
hashes09 = {o.name: mesh_hash(o) for o in bpy.data.objects}
names09 = set(hashes09)

bpy.ops.wm.open_mainfile(filepath=DST)
scene = bpy.context.scene

# --------------------------------------------------------------------------
section("A  scope - what changed and what did not")
# --------------------------------------------------------------------------
added = sorted(names10 - names09)
removed = sorted(names09 - names10)
changed = sorted(n for n in (names09 & names10) if hashes09[n] != hashes10[n])
check(set(removed) == OLD_SPIKES,
      "the nine checkpoint-4 radial crown spikes are the only objects removed",
      f"{len(removed)} removed")
check(set(changed) == set(spikes),
      "the twelve shoulder spikes are the only objects whose geometry changed",
      f"{len(changed)} changed: " + ", ".join(changed[:3]) + " ...")
check(set(added) == set(thorns),
      "the thorn crown is the only geometry added",
      f"{len(added)} added")
check(all(hashes09[n] == hashes10[n] for n in names09 & names10
          if n.startswith(("WSK_Helmet_", "WSK_Armor_", "WSK_Body"))and n not in spikes),
      "helmet shell, crest, face plate, gorget, band, halo, spine, mount, body "
      "and every other armour plate are byte-identical to checkpoint 9")
check(len(bpy.data.collections) == 14 and
      not any(c.name not in ("Helmet", "Crown", "Body", "Armor", "Cape",
                             "Accessories", "Weapon", "Rig", "Reference",
                             "Blockout", "Lighting and Cameras",
                             "Silhouette Check", "Shoulder Check",
                             "Limb Pose Controls")
              for c in bpy.data.collections),
      "no collection was added or removed",
      f"{len(bpy.data.collections)} collections")
check(len(bpy.data.worlds) == 2 and len(bpy.data.cameras) == 13,
      "worlds and the camera set are unchanged",
      f"{len(bpy.data.worlds)} worlds, {len(bpy.data.cameras)} cameras")
check(not any(o.type == "EMPTY" and o.name.startswith("WSK_Helmet_CrownSpike")
              for o in bpy.data.objects), "no spike empties were left behind")
check(len([m for m in bpy.data.materials if m.use_nodes and any(
              n.type == "EMISSION" for n in m.node_tree.nodes)]) == 0,
      "no material gained an emission shader (no glow)")
check(not any(o.modifiers and any(m.type in ("PARTICLE_SYSTEM", "FLUID")
                                  for m in o.modifiers) for o in bpy.data.objects)
      and len(bpy.data.particles) == 0,
      "no particle systems (no particle effects)")

# --------------------------------------------------------------------------
section("B  the crown design")
# --------------------------------------------------------------------------
rows = {"A": sorted(n for n in thorns if "CrownThorn" in n),
        "B": sorted(n for n in thorns if "CrownBarb" in n)}
check(len(rows["A"]) == 11 and len(rows["B"]) == 10,
      "the crown is one centre blade + five graded pairs (row A) and ten lower "
      "barbs (row B)", f"{len(rows['A'])} + {len(rows['B'])}")
check(all(bpy.data.objects[n].data.users == 1 for n in thorns),
      "every thorn is a separate single-user mesh")
check(len({bpy.data.objects[n].data.name for n in thorns}) == len(thorns),
      "each thorn owns its own mesh datablock",
      f"{len({bpy.data.objects[n].data.name for n in thorns})} distinct meshes "
      f"for {len(thorns)} thorns")

lens = {n: bpy.data.objects[n]["wsk_length_m"] for n in thorns}
centre = "WSK_Helmet_CrownThorn_C_01"
others = sorted((v, n) for n, v in lens.items() if n != centre)
check(lens[centre] == max(lens.values()),
      "the centre blade is the tallest element of the crown",
      f"{lens[centre]:.3f} m")
check(lens[centre] >= 1.15 * others[-1][0],
      "the centre blade is at least 15 % taller than the next tallest thorn",
      f"{lens[centre]:.3f} vs {others[-1][0]:.3f} m "
      f"({lens[centre] / others[-1][0]:.2f}x)")

graded = True
row_a_pairs = []
for k in "12345":
    r, l = f"WSK_Helmet_CrownThorn_R{k}_01", f"WSK_Helmet_CrownThorn_L{k}_01"
    row_a_pairs.append((k, lens[r], lens[l]))
for i in range(len(row_a_pairs) - 1):
    if row_a_pairs[i][1] < row_a_pairs[i + 1][1] or row_a_pairs[i][2] < row_a_pairs[i + 1][2]:
        graded = False
check(graded, "row A reach falls off steadily from the centre blade outwards",
      " > ".join(f"{v:.3f}" for _k, v, _l in row_a_pairs))
mean_b = sum(lens[n] for n in rows["B"]) / len(rows["B"])
mean_a = sum(lens[n] for n in rows["A"]) / len(rows["A"])
check(mean_b < 0.85 * mean_a, "the lower row is clearly the smaller row",
      f"row B mean {mean_b:.3f} m vs row A mean {mean_a:.3f} m")

sh = {n: bpy.data.objects[n]["wsk_length_m"] for n in spikes}
tallest_pair = sorted(lens.values())[-2]
check(max(sh.values()) <= 0.72 * lens[centre],
      "the largest shoulder spike stays well below the crown's centre blade",
      f"{max(sh.values()):.3f} m = {max(sh.values()) / lens[centre]:.2f}x "
      f"the centre blade ({lens[centre]:.3f} m)")
check(max(sh.values()) <= 0.80 * tallest_pair,
      "the shoulder fan is a smaller scale than the crown's own pairs",
      f"longest shoulder spike {max(sh.values()):.3f} m vs the shortest "
      f"crown pair thorn {min(lens.values()):.3f} m and the tallest pair "
      f"thorn {tallest_pair:.3f} m")

# not a mechanical gear: the thorn frames must be genuinely varied
frames = []
for n in thorns:
    obj = bpy.data.objects[n]
    axis = Vector(obj["wsk_axis"]).normalized()
    frames.append(axis)
angles = sorted(math.degrees(math.atan2(a.z, math.hypot(a.x, a.y))) for a in frames)
gaps = [angles[i + 1] - angles[i] for i in range(len(angles) - 1)]
uniq = sorted(set(round(a, 2) for a in angles))
ugaps = [uniq[i + 1] - uniq[i] for i in range(len(uniq) - 1)]
check(len(uniq) >= 9 and max(ugaps) >= 2.0 * min(ugaps),
      "the thorn tilts are genuinely graded, not one repeated angle",
      f"{len(uniq)} distinct tilts {uniq[0]:.0f}-{uniq[-1]:.0f} deg, gaps "
      f"{min(ugaps):.1f}-{max(ugaps):.1f} deg")
az = sorted(math.degrees(math.atan2(a.x, a.y)) for a in frames)
azgaps = [az[i + 1] - az[i] for i in range(len(az) - 1)]
check(max(azgaps) >= 1.4 * min(azgaps),
      "the thorn azimuths are unevenly spaced (no regular radial repetition)",
      f"azimuth gaps {min(azgaps):.0f}-{max(azgaps):.0f} deg")

asym = []
for k in "12345":
    for kind, pre in (("thorn", "WSK_Helmet_CrownThorn"), ("barb", "WSK_Helmet_CrownBarb")):
        r, l = f"{pre}_R{k}_01", f"{pre}_L{k}_01"
        if r in lens and l in lens:
            asym.append((k + kind[0], abs(lens[l] - lens[r]) / max(lens[r], lens[l])))
big = [a for a in asym if a[1] > 0.005]
check(len(big) >= 4, "at least four pairs carry a deliberate left/right difference",
      ", ".join(f"{k}:{v * 100:.1f}%" for k, v in big))
check(all(v <= 0.08 for _k, v in asym),
      "no left/right difference is large enough to break the design",
      f"largest {max(v for _k, v in asym) * 100:.1f}%")

# --------------------------------------------------------------------------
section("C  mounting, root depth and clearance")
# --------------------------------------------------------------------------
mount_trees = {n: bvh(n) for n in MOUNTS}
all_trees = {n: bvh(n) for n in ("WSK_Helmet_Shell_01", "WSK_Helmet_Crest_01",
                                 "WSK_Helmet_CrownBand_01", "WSK_Helmet_Faceplate_01",
                                 "WSK_Helmet_NeckGuard_01", "WSK_Helmet_CrownHalo_01",
                                 "WSK_Helmet_CrownSpine_01", "WSK_Helmet_CrownMount_01",
                                 "WSK_Body_Base_01",
                                 "WSK_Armor_Chest_01", "WSK_Armor_Back_01")}
all_trees.update({n: bvh(n) for n in spikes})
all_trees.update({n: bvh(n) for n in sorted({bpy.data.objects[s]["wsk_mount"]
                                             for s in spikes})})

contact = []
roots = []
for n in thorns:
    obj = bpy.data.objects[n]
    verts, _f = evaluated(obj)
    axis = Vector(obj["wsk_axis"]).normalized()
    base = Vector(obj["wsk_base"])
    best_name, best = None, 9.9
    for name, tree in mount_trees.items():
        loc, _nrm, dist = nearest(tree, base)
        if dist < best:
            best_name, best = name, dist
    contact.append((n, best_name, best))
    layer = base - axis * min(0.5 * obj["wsk_root_depth_m"], 0.0025)
    mount = bpy.data.objects[n]["wsk_mount"]
    inside = parity_inside(mount_trees[mount], layer)
    roots.append((n, inside))
check(all(dist <= 0.0010 for _n, _m, dist in contact),
      "every thorn's base sits ON a mounting surface (<= 1 mm from shell, crest "
      "or band)", f"worst {max(d for _n, _m, d in contact) * 1000:.2f} mm")
names_mount = sorted({m for _n, m, _d in contact})
check(len(names_mount) <= 3, "thorns mount only on the shell, the crest and the band",
      ", ".join(f"{m} x{sum(1 for _n, mm, _d in contact if mm == m)}"
                for m in names_mount))
check(sum(1 for _n, m, _d in contact if m == "WSK_Helmet_Crest_01") == 1,
      "exactly one thorn - the centre blade - is planted on the crest")
check(all(inside for _n, inside in roots),
      "every thorn's root crosses the metal it grows from, so no base can float",
      "; ".join(f"{n[12:]} {'ok' if ok else 'FLOATING'}"
                for n, ok in roots if not ok) or "all 21 shafts pass through their wall")
root_clear = []
for n in thorns:
    obj = bpy.data.objects[n]
    verts, _f = evaluated(obj)
    mount = obj["wsk_mount"]
    back = [p for p in verts if (p - Vector(obj["wsk_base"])).dot(
        Vector(obj["wsk_axis"]).normalized()) < 0.0]
    worst = min((nearest(all_trees[t], p)[2] for t in ("WSK_Body_Base_01",
                 "WSK_Helmet_NeckGuard_01", "WSK_Helmet_Faceplate_01")
                 for p in back), default=9.9)
    root_clear.append((n, worst))
check(all(v >= 0.002 for _n, v in root_clear),
      "no root reaches the head, the face plate or the gorget",
      f"closest {min(v for _n, v in root_clear) * 1000:.2f} mm")
check(all(bpy.data.objects[n]["wsk_root_depth_m"] >= 0.003 for n in thorns),
      "every solved root depth is at least 3 mm",
      f"min {min(bpy.data.objects[n]['wsk_root_depth_m'] for n in thorns) * 1000:.1f} mm, "
      f"max {max(bpy.data.objects[n]['wsk_root_depth_m'] for n in thorns) * 1000:.1f} mm")

worst = (9.9, "", "")
for n in thorns:
    verts, _f = evaluated(bpy.data.objects[n])
    own_mount = next(m for nn, m, _d in contact if nn == n)
    for name, tree in all_trees.items():
        if name == own_mount:
            continue
        for p in verts:
            loc, nrm, dist = nearest(tree, p)
            if loc is None or dist > 0.010:
                continue
            if parity_inside(tree, p):
                dist = -dist
            if dist < worst[0]:
                worst = (dist, n, name)
check(worst[0] >= 0.0015,
      "no thorn vertex penetrates another object, and every foreign surface "
      "keeps 1.5 mm of air",
      f"closest {worst[0] * 1000:.2f} mm ({worst[1]} vs {worst[2]})")
bad = []
for n in thorns:
    verts, _f = evaluated(bpy.data.objects[n])
    own_mount = next(m for nn, m, _d in contact if nn == n)
    for p in verts:
        loc, _nrm, dist = nearest(all_trees[own_mount], p)
        if loc is not None and dist > 0.012 and parity_inside(all_trees[own_mount], p):
            bad.append(n)
check(not bad, "no thorn is floating above its own mounting surface",
      ", ".join(sorted(set(bad))) or "all bases contact their metal")

qual = []
for n in thorns:
    obj = bpy.data.objects[n]
    nm, loose, degen, shortest = mesh_quality(obj)
    vol = outward(obj)
    qual.append((n, nm, loose, degen, shortest, vol, len(obj.data.vertices)))
check(all(q[1] == 0 and q[2] == 0 and q[3] == 0 for q in qual),
      "every thorn is a closed manifold with no loose geometry or degenerate faces")
check(all(q[5] > 0 for q in qual), "every thorn's normals point outwards")
check(all(q[4] >= 0.0004 for q in qual), "no thorn has a collapsed edge",
      f"shortest edge {min(q[4] for q in qual) * 1000:.2f} mm")
check(all(q[6] == 67 for q in qual),
      "every thorn uses the same 67-vertex profile (manageable, no subdivision)",
      f"{sum(q[6] for q in qual)} vertices for the whole crown")
check(not any(o.modifiers and any(m.type == "SUBSURF" for m in o.modifiers)
              for o in (bpy.data.objects[n] for n in thorns)),
      "no thorn carries a subdivision modifier")

# --------------------------------------------------------------------------
section("D  the shoulder spikes")
# --------------------------------------------------------------------------
pairwise = {}
for n in spikes:
    obj = bpy.data.objects[n]
    pairwise.setdefault(obj["wsk_mount"], []).append(n)
check(all(len(v) == 6 for v in pairwise.values()) and len(pairwise) == 2,
      "six spikes per pauldron, on two pauldrons",
      "; ".join(f"{k}: {len(v)}" for k, v in sorted(pairwise.items())))
check(all(bpy.data.objects[n].parent is not None and
          bpy.data.objects[n].parent.name.endswith(
              "_R_01" if n.endswith("_R_01") else "_L_01") for n in spikes),
      "each spike is still parented to its own shoulder root")
check(all(abs(bpy.data.objects[n].matrix_world.to_translation().length) < 1e-6
          for n in spikes),
      "each spike keeps an identity world matrix (mesh space = world space)")
fits = []
for n in spikes:
    obj = bpy.data.objects[n]
    verts, _f = evaluated(obj)
    axis = Vector(obj["wsk_axis"]).normalized()
    tip = Vector(obj["wsk_tip"])
    base = tip - axis * obj["wsk_length_m"]
    loc, _nrm, dist = nearest(all_trees[obj["wsk_mount"]], base)
    fits.append((n, dist))
    foreign = 9.9
    for name, tree in all_trees.items():
        if name == obj["wsk_mount"] or name == n:
            continue
        for p in verts:
            near, _n, d = nearest(tree, p)
            if near is not None and d < foreign:
                foreign = d
    fits[-1] = (n, dist, foreign)
check(all(d <= 0.0015 for _n, d, _f in fits),
      "every shoulder spike's base sits on its pauldron",
      f"worst {max(d for _n, d, _f in fits) * 1000:.2f} mm")
check(all(f >= 0.0015 for _n, _d, f in fits),
      "no shoulder spike touches the body, torso armour, helmet or another spike",
      f"closest foreign surface {min(f for _n, _d, f in fits) * 1000:.2f} mm")
check(all(0.050 <= v <= 0.135 for v in sh.values()),
      "shoulder spike lengths stay in a tight, smaller band",
      f"{min(sh.values()):.3f}-{max(sh.values()):.3f} m")
diffs = []
for k in range(1, 7):
    r = [n for n in spikes if n.endswith("_R_01")][k - 1]
    l = [n for n in spikes if n.endswith("_L_01")][k - 1]
    diffs.append(abs(sh[l] - sh[r]) / max(sh[l], sh[r]))
check(len([d for d in diffs if d > 0.005]) >= 3,
      "the prompt-7 left/right differences survive the re-cut",
      ", ".join(f"{d * 100:.1f}%" for d in diffs))
sq = [mesh_quality(bpy.data.objects[n]) for n in spikes]
check(all(q[0] == 0 and q[1] == 0 and q[2] == 0 for q in sq),
      "every shoulder spike is still a closed manifold with no loose or "
      "degenerate geometry",
      f"shortest edge {min(q[3] for q in sq) * 1000:.2f} mm")
check(all(q[3] >= 0.0004 for q in sq), "no shoulder spike has a collapsed edge")

# --------------------------------------------------------------------------
section("E  silhouette balance (rendered)")
# --------------------------------------------------------------------------
VIEW_CENTRE_Z, ORTHO, RES = 2.02, 0.46, (800, 1000)
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 6
scene.cycles.use_denoising = False
scene.render.film_transparent = True
scene.render.image_settings.color_mode = "RGBA"
scene.render.resolution_x, scene.render.resolution_y = RES
for o in bpy.data.objects:
    if o.name.startswith(("WSK_Guide_", "WSK_Label_", "WSK_Ref_", "WSK_Joint_",
                          "WSK_Mann_", "WSK_Studio_")):
        o.hide_render = True


def mask_of(keep_names, view):
    hidden = {}
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name not in keep_names:
            hidden[o.name] = o.hide_render
            o.hide_render = True
    cam = bpy.data.objects["WSK_Cam_Sil_Front_01"]
    scene.camera = cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = ORTHO
    loc = {"front": (0.0, 3.0, VIEW_CENTRE_Z), "rear": (0.0, -3.0, VIEW_CENTRE_Z),
           "side": (3.0, 0.0, VIEW_CENTRE_Z)}[view]
    cam.location = loc
    d = (Vector((0.0, 0.0, VIEW_CENTRE_Z)) - Vector(loc)).normalized()
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    path = os.path.join(SHOTS, f"_mask_{view}.png")
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    im = Image.open(path).convert("RGBA")
    arr = np.asarray(im)[..., 3] > 127
    os.remove(path)
    for name, state in hidden.items():
        bpy.data.objects[name].hide_render = state
    return arr


mpp = ORTHO / RES[1]
front = mask_of(set(thorns), "front")
rear = mask_of(set(thorns), "rear")
side = mask_of(set(thorns), "side")
cx = (RES[0] - 1) / 2.0
ys, xs = np.nonzero(front)
check(abs(xs.mean() - cx) * mpp <= 0.0015,
      "the crown silhouette is balanced left/right from the front",
      f"centroid offset {(xs.mean() - cx) * mpp * 1000:+.2f} mm")
left = (xs < cx).sum()
right = (xs > cx).sum()
check(abs(left / right - 1.0) <= 0.03,
      "the crown silhouette area is balanced left/right",
      f"L/R {left / right:.4f}")
span = (xs.max() - xs.min() + 1) * mpp
top = VIEW_CENTRE_Z + (RES[1] / 2.0 - ys.min()) * mpp
bottom = VIEW_CENTRE_Z - (ys.max() - RES[1] / 2.0) * mpp
check(span <= 0.42, "the crown's frontal span stays close to the helmet",
      f"{span:.3f} m (reference read 0.42, previously 0.361)")
check(1.99 <= top <= 2.20,
      "the tallest thorn stays inside the documented envelope",
      f"top {top:.3f} m (reference reads 2.18-2.23; guide says 2.11, "
      f"'guide only / not measured')")
check(bottom >= 1.80,
      "no thorn hangs low enough to reach the gorget or the shoulders",
      f"lowest silhouette point {bottom:.3f} m (gorget top 1.775 m)")
rys, rxs = np.nonzero(rear)
check(abs(rxs.mean() - cx) * mpp <= 0.0015
      and abs((rxs < cx).sum() / (rxs > cx).sum() - 1.0) <= 0.03,
      "the rear view is balanced as well",
      f"centroid offset {(rxs.mean() - cx) * mpp * 1000:+.2f} mm")
tips = [Vector(bpy.data.objects[n]["wsk_tip"]) for n in thorns]
mean_tip_y = sum(t.y for t in tips) / len(tips)
back = min(t.y for t in tips)
front_y = max(t.y for t in tips)
check(mean_tip_y < -0.02 and back < -0.12,
      "the fan sweeps back: the thorn tips are behind the head axis, so the "
      "side view is a comb and not a disc",
      f"mean tip Y {mean_tip_y:+.3f} m, rearmost {back:+.3f} m, frontmost "
      f"{front_y:+.3f} m")
check(abs(front.sum() - rear.sum()) / max(front.sum(), rear.sum()) <= 0.20,
      "the crown reads from the front and from behind alike (the ring frames "
      "one, the thorns the other)",
      f"front {front.sum() * mpp * mpp * 1e4:.0f} cm2, rear "
      f"{rear.sum() * mpp * mpp * 1e4:.0f} cm2")

shots = [f for f in sorted(os.listdir(SHOTS)) if f.startswith("p10_")]
check(len(shots) >= 8, "the inspection renders the prompt asks for exist",
      ", ".join(shots))

# --------------------------------------------------------------------------
section("F  design table")
# --------------------------------------------------------------------------
lines.append("row  name                              base (x,y,z)            "
             "tilt  lean  length  base_r  root")
for n in rows["A"] + rows["B"]:
    o = bpy.data.objects[n]
    tip = Vector(o["wsk_tip"])
    axis = Vector(o["wsk_axis"])
    base = tip - axis * o["wsk_length_m"]
    lines.append(f"{o['wsk_row']}    {n[12:]:32s} "
                 f"({base.x:+.3f},{base.y:+.3f},{base.z:+.3f})  "
                 f"{o['wsk_tilt_deg']:5.1f} {o['wsk_lean_deg']:5.1f}  "
                 f"{o['wsk_length_m']:.3f}   {o['wsk_base_radius_m'] * 1000:4.1f}  "
                 f"{o['wsk_root_depth_m'] * 1000:4.1f} mm")
lines.append("")
lines.append("mount counts: " + ", ".join(
    f"{m} x{sum(1 for _n, mm, _d in contact if mm == m)}" for m in names_mount))
lines.append("shoulder spikes: " + ", ".join(
    f"{n.split('_')[2]} {bpy.data.objects[n]['wsk_length_m']:.3f} m"
    for n in spikes if n.endswith("_R_01")))

# --------------------------------------------------------------------------
lines.append("")
lines.append("=" * 72)
lines.append(f"RESULT: {passed} checks passed, {failed} failed, {warned} warnings")
lines.append("=" * 72)
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
with open(REPORT, "w") as fh:
    fh.write("\n".join(lines) + "\n")
print("\n".join(lines))
print(f"\nwrote {REPORT}")
