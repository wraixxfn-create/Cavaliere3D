"""Prompt 13 verification - cape base shape (checkpoint 13).

Usage: tools/bl.sh tools/verify_cape_blockout.py

Checks, on the saved Wildshift_Knight_13_CapeBlockout.blend against the
checkpoint-12 file it was built from:
  scope       - every checkpoint-12 object is unchanged (transform, parent,
                collection, material, modifiers, mesh coordinates)
  topology    - one closed, manifold, outward-facing shell; no loose parts
  shape       - width, length, hem, tears, rear extent, shell thickness
  placement   - pivot/origin, attachment, front face behind the torso, no
                contact with the floor
  clearance   - distance to every armour/body/helmet/crown mesh, and no
                vertex inside any of them
  material    - one burgundy placeholder, no emission, no textures
Prints PASS/FAIL per check and writes analysis/verify/verify_cape_blockout_report.txt
"""
import math
import os
import sys

import bpy            # noqa: F401
import bmesh          # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_12_ArmorDetails.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_13_CapeBlockout.blend")
REPORT = os.path.join(ROOT, "analysis/verify/verify_cape_blockout_report.txt")

CAPE = "WSK_Cape_Blockout_01"
PIVOT = "WSK_Cape_Pivot_01"
MAT = "MAT_Cape_Burgundy_01"
NU, NV = 24, 32
THICK = 0.018
PIVOT_LOC = (0.0, -0.23, 1.60)

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS" if ok else "FAIL"), name, "-", detail)


def fingerprint(scene_objs):
    fp = {}
    for o in scene_objs:
        mw = tuple(round(x, 6) for row in o.matrix_world for x in row)
        mesh_hash = None
        npoly = 0
        if o.type == 'MESH' and o.data is not None:
            mesh_hash = hash(tuple(round(c, 7) for v in o.data.vertices for c in v.co))
            npoly = len(o.data.polygons)
        mods = tuple((m.name, m.type) for m in o.modifiers)
        mats = tuple(s.material.name if s.material else None for s in o.material_slots)
        fp[o.name] = dict(
            type=o.type,
            parent=o.parent.name if o.parent else None,
            cols=tuple(sorted(c.name for c in o.users_collection)),
            mw=mw, mesh=mesh_hash, npoly=npoly, mods=mods, mats=mats,
            data=o.data.name if o.data else None,
        )
    return fp


# --------------------------------------------------------------------------
# 1. scope: compare against checkpoint 12
# --------------------------------------------------------------------------
bpy.ops.wm.open_mainfile(filepath=SRC)
old_objs = list(bpy.data.objects)
old_fp = fingerprint(old_objs)
old_mats = {m.name for m in bpy.data.materials}
old_cols = {c.name for c in bpy.data.collections}
old_texts = {t.name for t in bpy.data.texts}

bpy.ops.wm.open_mainfile(filepath=DST)
new_objs = list(bpy.data.objects)
new_fp = fingerprint(new_objs)

missing = [n for n in old_fp if n not in new_fp]
changed = [n for n in old_fp if n in new_fp and old_fp[n] != new_fp[n]]
added = sorted(n for n in new_fp if n not in old_fp)
check("scope: no checkpoint-12 object removed", not missing, f"missing={missing[:5]}")
check("scope: all checkpoint-12 objects unchanged", not changed,
      f"{len(old_fp)} objects compared; changed={changed[:5]}")
check("scope: only the cape mesh and pivot added", added == sorted([CAPE, PIVOT]),
      f"added={added}")
new_mats = sorted({m.name for m in bpy.data.materials} - old_mats)
check("scope: exactly one new material", new_mats == [MAT], f"new={new_mats}")
new_cols = sorted({c.name for c in bpy.data.collections} - old_cols)
check("scope: no collection added", not new_cols, f"new={new_cols}")
check("scope: cape and pivot in the Cape collection",
      set(bpy.data.objects[CAPE].users_collection) == {bpy.data.collections["Cape"]}
      and set(bpy.data.objects[PIVOT].users_collection) == {bpy.data.collections["Cape"]},
      f"cape cols={[c.name for c in bpy.data.objects[CAPE].users_collection]}")

cape = bpy.data.objects[CAPE]
pivot = bpy.data.objects[PIVOT]
me = cape.data

# --------------------------------------------------------------------------
# 2. topology
# --------------------------------------------------------------------------
bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()
bm.faces.ensure_lookup_table()
n_v, n_e, n_f = len(bm.verts), len(bm.edges), len(bm.faces)
boundary = [e for e in bm.edges if len(e.link_faces) != 2]
nonmanifold_v = [v for v in bm.verts if not v.is_manifold]
loose = [v for v in bm.verts if len(v.link_faces) == 0]
check("topology: closed (no boundary edges)", not boundary, f"boundary edges={len(boundary)}")
check("topology: manifold vertices", not nonmanifold_v, f"non-manifold={len(nonmanifold_v)}")
check("topology: no loose vertices", not loose, f"loose={len(loose)}")
chi = n_v - n_e + n_f
check("topology: sphere topology (V-E+F = 2)", chi == 2, f"V={n_v} E={n_e} F={n_f} chi={chi}")
# connected components
seen, comps = set(), 0
for v in bm.verts:
    if v in seen:
        continue
    comps += 1
    stack = [v]
    seen.add(v)
    while stack:
        cur = stack.pop()
        for e in cur.link_edges:
            o = e.other_vert(cur)
            if o not in seen:
                seen.add(o)
                stack.append(o)
check("topology: one connected shell", comps == 1, f"components={comps}")
bm.free()

# outward normals: signed volume about the pivot must be positive
vol = 0.0
for poly in me.polygons:
    vs = [me.vertices[i].co for i in poly.vertices]
    for k in range(1, len(vs) - 1):
        vol += vs[0].dot(vs[k].cross(vs[k + 1])) / 6.0
check("topology: outward-facing normals (positive enclosed volume)", vol > 0,
      f"volume={vol * 1e3:.3f} litres (pivot-relative, closed shell)")
check("topology: vertex count within blockout budget", n_v <= 2500,
      f"{n_v} vertices, {n_f} faces")

# --------------------------------------------------------------------------
# 3. world-space placement
# --------------------------------------------------------------------------
world = [cape.matrix_world @ v.co for v in me.vertices]
xs = [p.x for p in world]
ys = [p.y for p in world]
zs = [p.z for p in world]
check("placement: pivot at the yoke centre",
      all(abs(a - b) < 1e-6 for a, b in zip(pivot.location, PIVOT_LOC)),
      f"pivot={tuple(round(c, 4) for c in pivot.location)}")
check("placement: cape origin equals pivot",
      (cape.matrix_world.translation - Vector(PIVOT_LOC)).length < 1e-6,
      f"origin={tuple(round(c, 4) for c in cape.matrix_world.translation)}")
from mathutils import Matrix  # noqa: E402
ident_err = max(abs(cape.matrix_basis[r][c] - (1.0 if r == c else 0.0))
                for r in range(4) for c in range(4))
check("placement: cape parented to pivot with identity local transform",
      cape.parent == pivot and ident_err < 1e-9,
      f"parent={cape.parent.name if cape.parent else None}, local error {ident_err:.2e}")
top = [p for p in world if p.z > 1.50]
N_GRID = (NU + 1) * (NV + 1)
# centre surface (midpoint of each outer/inner pair) along the yoke edge, j = 0
top_mid = [(world[i * (NV + 1)] + world[N_GRID + i * (NV + 1)]) * 0.5 for i in range(NU + 1)]
mirror_err = max(abs(top_mid[i].x + top_mid[NU - i].x) + abs(top_mid[i].z - top_mid[NU - i].z)
                 + abs(top_mid[i].y - top_mid[NU - i].y) for i in range(NU + 1))
check("placement: yoke edge mirror-symmetric about X = 0", mirror_err < 1e-6,
      f"worst mirror mismatch {mirror_err * 1000:.4f} mm along the yoke edge")
top_hw = max(abs(p.x) for p in top) if top else 0.0
check("shape: yoke half-width 0.17-0.21 m", 0.17 <= top_hw <= 0.21,
      f"yoke half-width {top_hw:.3f} m")

ymax = max(ys)
check("placement: entire cape behind the torso front (Y max < -0.20)", ymax < -0.20,
      f"Y max {ymax:+.3f} m (torso centre Y 0, back plate front face -0.164)")
zmax = max(zs)
check("placement: no part above the shoulder line (Z max < 1.61)", zmax < 1.61,
      f"Z max {zmax:.3f} m")

zmin = min(zs)
check("placement: clears the floor (Z min > 0.04)", zmin > 0.04,
      f"Z min {zmin:.3f} m (reference hem 0.06 m)")
hem_band = [p for p in world if p.z < 0.10]
check("placement: lobes reach to the hem band (0.05-0.09 m)",
      hem_band and 0.05 <= min(p.z for p in hem_band) and max(p.z for p in hem_band) <= 0.12,
      f"hem Z {min(p.z for p in hem_band):.3f}..{max(p.z for p in hem_band):.3f}" if hem_band else "none")

# --------------------------------------------------------------------------
# 4. shape against the reference numbers
# --------------------------------------------------------------------------
mid = [p for p in world if 0.70 <= p.z <= 0.80]
mid_hw = max(abs(p.x) for p in mid) if mid else 0.0
check("shape: full half-width 0.50-0.60 m near Z 0.75 (reference 0.55)",
      0.50 <= mid_hw <= 0.60, f"half-width {mid_hw:.3f} m at Z 0.70-0.80")
rear = min(ys)
check("shape: rear extent between -0.55 and -0.70 m (reference -0.72 / -0.63)",
      -0.70 <= rear <= -0.55, f"Y min {rear:.3f} m")
mid_depth = min(p.y for p in world if 0.85 <= p.z <= 1.05)
check("shape: mid-height rear billow reaches the reference -0.63..-0.72 m",
      -0.72 <= mid_depth <= -0.63, f"Y at Z 0.85-1.05: {mid_depth:.3f} m (reference -0.72 at Z ~1.07)")

# tears: runs along the bottom row
bottom = []
for i in range(NU + 1):
    idx = i * (NV + 1) + NV
    bottom.append(world[idx].z)
runs_high, runs_low = 0, 0
prev = None
for z in bottom:
    state = z > 0.20
    if state != prev:
        if state:
            runs_high += 1
        else:
            runs_low += 1
        prev = state
tear_apex = max(bottom)
check("shape: four broad tears in the hem", runs_high == 4,
      f"raised hem runs={runs_high}, peak tear Z={tear_apex:.3f} m")
check("shape: five hanging lobes between and beside the tears", runs_low == 5,
      f"low hem runs={runs_low}")
check("shape: tears are broad, not pinholes (apex Z 0.30-0.55)",
      0.30 <= tear_apex <= 0.55, f"apex Z {tear_apex:.3f}")

# shell thickness: outer and inner faces of each grid point
th = []
N = (NU + 1) * (NV + 1)
for k in range(N):
    th.append((world[k] - world[N + k]).length)
check("shape: shell thickness 18 mm everywhere",
      max(abs(t - THICK) for t in th) < 2e-4,
      f"min {min(th) * 1e3:.2f} mm, max {max(th) * 1e3:.2f} mm")

# not a flat plate: depth variation across the back
depth_span = max(ys) - min(ys)
check("shape: real depth, not a paper-thin sheet (depth span > 0.3 m)",
      depth_span > 0.3, f"Y span {depth_span:.3f} m")

# vertex groups
vg = {g.name for g in cape.vertex_groups}
need = {"Cape_Yoke", "Cape_Body", "Cape_Hem"} | {f"Cape_Panel_{k}" for k in range(1, 6)}
check("design: vertex groups for yoke, body, hem and five panels", need <= vg,
      f"groups={sorted(vg)}")

# --------------------------------------------------------------------------
# 5. clearance against every solid mesh in the knight
# --------------------------------------------------------------------------
depsgraph = bpy.context.evaluated_depsgraph_get()
skip_cols = {"Cape", "Reference", "Lighting and Cameras"}
others = []
for o in bpy.data.objects:
    if o.type != 'MESH' or o.name == CAPE:
        continue
    if any(c.name in skip_cols for c in o.users_collection):
        continue
    if len(o.data.polygons) == 0:
        continue
    others.append(o)

def winding_number(tris, p):
    """Generalised winding number of a closed triangle soup about p (~1 inside, ~0 outside)."""
    total = 0.0
    for a, b, c in tris:
        va, vb, vc = a - p, b - p, c - p
        la, lb, lc = va.length, vb.length, vc.length
        num = va.dot(vb.cross(vc))
        den = la * lb * lc + va.dot(vb) * lc + va.dot(vc) * lb + vb.dot(vc) * la
        total += 2.0 * math.atan2(num, den)
    return total / (4.0 * math.pi)


clear_report = []
min_clear = (1e9, None)
inside_any = []
for o in others:
    ev = o.evaluated_get(depsgraph)
    emesh = ev.to_mesh()
    mw = ev.matrix_world.copy()
    wv = [mw @ v.co for v in emesh.vertices]
    wf = [tuple(p.vertices) for p in emesh.polygons]
    tree = BVHTree.FromPolygons(wv, wf, all_triangles=False)
    ev.to_mesh_clear()
    tris = []
    for f in wf:
        for k in range(1, len(f) - 1):
            tris.append((wv[f[0]], wv[f[k]], wv[f[k + 1]]))
    lo = Vector((min(v.x for v in wv), min(v.y for v in wv), min(v.z for v in wv)))
    hi = Vector((max(v.x for v in wv), max(v.y for v in wv), max(v.z for v in wv)))
    pad = Vector((0.002, 0.002, 0.002))
    d_min, n_in = 1e9, 0
    for p in world:
        loc, nrm, _, dist = tree.find_nearest(p)
        if loc is None:
            continue
        if dist < d_min:
            d_min = dist
        inside_box = all(lo[k] - pad[k] <= p[k] <= hi[k] + pad[k] for k in range(3))
        if inside_box and abs(winding_number(tris, p)) > 0.5:
            n_in += 1
    clear_report.append((d_min, o.name, n_in))
    if d_min < min_clear[0]:
        min_clear = (d_min, o.name)
    if n_in:
        inside_any.append((o.name, n_in))

clear_report.sort()
lines = [f"  {d * 1000:8.1f} mm  {name}  (inside-test hits {n})" for d, name, n in clear_report[:12]]
check("clearance: no cape vertex inside any solid part (winding number)", not inside_any,
      f"{len(inside_any)} parts contain cape vertices: {inside_any[:4]}")
check("clearance: nearest solid part at least 25 mm from the cape",
      min_clear[0] >= 0.025,
      f"closest: {min_clear[1]} at {min_clear[0] * 1000:.1f} mm")
body_names = {"WSK_Body_Base_01", "WSK_Mann_Chest_01", "WSK_Mann_Pelvis_01",
              "WSK_Helmet_Shell_01", "WSK_Helmet_NeckGuard_01"}
body_clear = min((d for d, n, _ in clear_report if n in body_names), default=None)
check("clearance: body and helmet at least 40 mm from the cape",
      body_clear is not None and body_clear >= 0.04,
      f"closest body/helmet part {body_clear * 1000:.1f} mm" if body_clear is not None else "none")

# --------------------------------------------------------------------------
# 6. material
# --------------------------------------------------------------------------
slots = [s.material.name if s.material else None for s in cape.material_slots]
check("material: single placeholder burgundy material", slots == [MAT], f"slots={slots}")
mat = bpy.data.materials[MAT]
bsdf = mat.node_tree.nodes.get("Principled BSDF")
col = bsdf.inputs["Base Color"].default_value
emit = bsdf.inputs.get("Emission Strength")
check("material: burgundy hue (red dominant, dark)",
      col[0] > col[1] * 3 and col[0] > col[2] * 3 and 0.1 < col[0] < 0.4,
      f"base {tuple(round(c, 3) for c in col[:3])}")
check("material: no emission and no textures",
      (emit is None or emit.default_value == 0.0)
      and not any(n.type == 'TEX_IMAGE' for n in mat.node_tree.nodes),
      "emission strength 0, no image textures")
check("material: no modifiers on the cape (blockout is applied geometry)",
      len(cape.modifiers) == 0, f"modifiers={[m.name for m in cape.modifiers]}")

# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------
passed = sum(1 for _, ok, _ in results if ok)
print(f"\n{passed}/{len(results)} checks passed")
print("closest solid parts (mm):")
for line in lines:
    print(line)

os.makedirs(os.path.dirname(REPORT), exist_ok=True)
with open(REPORT, "w") as fh:
    fh.write("Prompt 13 - cape base shape verification\n")
    fh.write(f"{passed}/{len(results)} checks passed\n\n")
    for name, ok, detail in results:
        fh.write(f"{'PASS' if ok else 'FAIL'}  {name}  -  {detail}\n")
    fh.write("\nclosest solid parts to the cape (distance mm, part, inside hits):\n")
    for d, name, n in clear_report[:20]:
        fh.write(f"  {d * 1000:8.1f}  {name}  ({n})\n")
sys.exit(0 if passed == len(results) else 1)
