"""Prompt 14 verification - cape layered torn panels (checkpoint 14).

Usage: tools/bl.sh tools/verify_cape_panels.py

Checks, on the saved Wildshift_Knight_14_CapePanels.blend against the
checkpoint-13 file it was built from:
  scope       - every checkpoint-13 object other than the replaced cape shell is
                unchanged (transform, parent, collection, material, modifiers,
                mesh coordinates); armour and body are byte-identical
  topology    - every cape piece is one closed, manifold, outward-facing shell
  structure   - one upper piece and five separate lower panels in the Cape
                collection, parented to the unchanged pivot
  separation  - panels never touch each other; a panel meets the upper piece
                only along the seam
  tears       - rear cross-sections: where the gaps are, how wide, how high
  bites       - the hem missing sections exist, with the intended depth
  silhouette  - the upper piece reproduces the approved Prompt 13 outline
  clearance   - distance to every armour/body/helmet/crown mesh; no cape
                vertex inside any of them (parity ray test)
  material    - two placeholder materials, two-sided, no textures

Writes analysis/verify/verify_cape_panels_report.txt
"""
import math
import os
import sys
from collections import Counter

import bpy            # noqa: F401
import bmesh          # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_13_CapeBlockout.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_14_CapePanels.blend")
REPORT = os.path.join(ROOT, "analysis/verify/verify_cape_panels_report.txt")

OLD = "WSK_Cape_Blockout_01"
UPPER = "WSK_Cape_Upper_01"
PANELS = [f"WSK_Cape_Panel_{k:02d}" for k in range(1, 6)]
PIVOT = "WSK_Cape_Pivot_01"
MAT_OUT = "MAT_Cape_Burgundy_01"
MAT_EDGE = "MAT_Cape_Burgundy_Edge_01"
COL = "Cape"
THICK = 0.018
SEAM_Z = (0.80, 1.12)     # the seam band (Z) where the panels meet the upper piece
#                           (the seam rises at the V-apexes, where the hem is raised)

results = []
lines = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    tag = "PASS" if ok else "FAIL"
    msg = f"[{tag}] {name}" + (f" - {detail}" if detail else "")
    print(msg)
    lines.append(msg)


def fingerprint(objs):
    fp = {}
    for o in objs:
        mw = tuple(round(x, 6) for row in o.matrix_world for x in row)
        mods = tuple((m.type, m.name) for m in o.modifiers)
        mats = tuple(s.material.name if s.material else None for s in o.material_slots)
        cols = tuple(sorted(c.name for c in o.users_collection))
        parent = o.parent.name if o.parent else None
        co = None
        if o.type == 'MESH':
            co = tuple(round(c, 6) for v in o.data.vertices for c in v.co)
        fp[o.name] = (o.type, parent, cols, mw, mods, mats, co)
    return fp


# --------------------------------------------------------------------------
# scope
# --------------------------------------------------------------------------
bpy.ops.wm.open_mainfile(filepath=SRC)
old_fp = fingerprint(list(bpy.data.objects))
old_mats = {m.name for m in bpy.data.materials}
old_mat_colour = tuple(bpy.data.materials[MAT_OUT].node_tree.nodes["Principled BSDF"]
                       .inputs["Base Color"].default_value)
old_cols = {c.name for c in bpy.data.collections}
old_cape = bpy.data.objects[OLD]
old_cape_world = [old_cape.matrix_world @ v.co for v in old_cape.data.vertices]

bpy.ops.wm.open_mainfile(filepath=DST)
new_objs = list(bpy.data.objects)
new_fp = fingerprint(new_objs)

removed = sorted(n for n in old_fp if n not in new_fp)
changed = sorted(n for n in old_fp if n in new_fp and old_fp[n] != new_fp[n])
added = sorted(n for n in new_fp if n not in old_fp)
expected_added = sorted([UPPER] + PANELS)

check("scope: only the Prompt 13 cape shell is removed",
      removed == [OLD], f"removed={removed}")
check("scope: every other checkpoint-13 object is unchanged",
      not changed, f"{len(old_fp) - len(removed)} objects compared; changed={changed[:5]}")
check("scope: exactly the upper piece and five panels added",
      added == expected_added, f"added={added}")
new_mats = sorted({m.name for m in bpy.data.materials} - old_mats)
check("scope: one new material (the wall tone)", new_mats == [MAT_EDGE], f"new={new_mats}")
check("scope: no collection added", {c.name for c in bpy.data.collections} == old_cols,
      f"collections={len(bpy.data.collections)}")
cape_col = bpy.data.collections[COL]
in_cape = sorted(o.name for o in cape_col.objects)
check("structure: Cape collection holds the pivot, upper piece and five panels only",
      in_cape == sorted([PIVOT, UPPER] + PANELS), f"Cape={in_cape}")

pivot = bpy.data.objects[PIVOT]
check("structure: pivot unchanged at the yoke centre (0, -0.23, 1.60)",
      (Vector(pivot.location) - Vector((0.0, -0.23, 1.60))).length < 1e-6,
      f"pivot={tuple(round(c, 4) for c in pivot.location)}")
parent_ok = True
for n in [UPPER] + PANELS:
    o = bpy.data.objects[n]
    ident = max(abs(o.matrix_basis[r][c] - (1.0 if r == c else 0.0))
                for r in range(4) for c in range(4))
    if o.parent != pivot or ident > 1e-9:
        parent_ok = False
check("structure: every cape piece parented to the pivot, identity local transform",
      parent_ok)
check("structure: no modifiers on any cape piece",
      all(len(bpy.data.objects[n].modifiers) == 0 for n in [UPPER] + PANELS))

mat_out = bpy.data.materials[MAT_OUT]
mat_edge = bpy.data.materials[MAT_EDGE]
check("material: outer material unchanged from Prompt 13",
      tuple(mat_out.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value)
      == old_mat_colour)
check("material: both placeholders are two-sided, untextured",
      mat_out.use_backface_culling is False and mat_edge.use_backface_culling is False
      and not any(n.type == 'TEX_IMAGE' for m in (mat_out, mat_edge) for n in m.node_tree.nodes))
check("material: wall tone is darker than the outer face",
      sum(mat_edge.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value[:3])
      < sum(mat_out.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value[:3]))

# --------------------------------------------------------------------------
# topology
# --------------------------------------------------------------------------
pieces = {}
for n in [UPPER] + PANELS:
    o = bpy.data.objects[n]
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    nv, ne, nf = len(bm.verts), len(bm.edges), len(bm.faces)
    boundary = [e for e in bm.edges if len(e.link_faces) != 2]
    nonman = [v for v in bm.verts if not v.is_manifold]
    loose = [v for v in bm.verts if len(v.link_faces) == 0]
    seen, comps = set(), 0
    for v in bm.verts:
        if v in seen:
            continue
        comps += 1
        st = [v]
        seen.add(v)
        while st:
            cur = st.pop()
            for e in cur.link_edges:
                oth = e.other_vert(cur)
                if oth not in seen:
                    seen.add(oth)
                    st.append(oth)
    vol = 0.0
    for poly in me.polygons:
        vs = [me.vertices[i].co for i in poly.vertices]
        for k in range(1, len(vs) - 1):
            vol += vs[0].dot(vs[k].cross(vs[k + 1])) / 6.0
    chi = nv - ne + nf
    bm.free()
    pieces[n] = {"V": nv, "F": nf, "chi": chi, "boundary": len(boundary),
                 "nonman": len(nonman), "loose": len(loose), "comps": comps, "vol": vol}
    det = (f"V={nv} F={nf} chi={chi} boundary={len(boundary)} nonmanifold={len(nonman)} "
           f"loose={len(loose)} shells={comps} volume={vol * 1e6:.1f} cm^3")
    check(f"topology: {n} closed, manifold, one shell, outward",
          not boundary and not nonman and not loose and comps == 1 and chi == 2 and vol > 0,
          det)

# face-face self-intersection (triangulated copy, exact segment-triangle tests)
from mathutils import geometry  # noqa: E402


def seg_hits(X, Y):
    for (p1, p2) in ((X[0], X[1]), (X[1], X[2]), (X[2], X[0])):
        d = p2 - p1
        L = d.length
        if L < 1e-12:
            continue
        hit = geometry.intersect_ray_tri(Y[0], Y[1], Y[2], d / L, p1, False)
        if hit is not None and (hit - p1).length <= L and (hit - p1).dot(d) >= 0:
            return True
    return False


for n in [UPPER] + PANELS:
    o = bpy.data.objects[n]
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    TV = [o.matrix_world @ v.co for v in bm.verts]
    TF = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    tr = BVHTree.FromPolygons(TV, TF, all_triangles=True)
    n_hit = 0
    for a_, b_ in tr.overlap(tr):
        if a_ >= b_ or set(TF[a_]) & set(TF[b_]):
            continue
        A = [TV[i] for i in TF[a_]]
        B = [TV[i] for i in TF[b_]]
        if seg_hits(A, B) or seg_hits(B, A):
            n_hit += 1
    check(f"topology: {n} has no self-intersecting faces", n_hit == 0,
          f"intersecting triangle pairs = {n_hit}")

total_v = sum(p["V"] for p in pieces.values())
check("topology: cape budget (all pieces under 8000 vertices)", total_v < 8000,
      f"total cape vertices {total_v}")

# world-space vertices of every cape piece
world = {}
for n in [UPPER] + PANELS:
    o = bpy.data.objects[n]
    world[n] = [o.matrix_world @ v.co for v in o.data.vertices]

# --------------------------------------------------------------------------
# separation
# --------------------------------------------------------------------------
def min_dist(a, b):
    """Minimum vertex-to-vertex distance between two point lists (coarse grid)."""
    best = 1e9
    from mathutils.kdtree import KDTree
    kd = KDTree(len(b))
    for k, p in enumerate(b):
        kd.insert(p, k)
    kd.balance()
    for p in a:
        _, _, d = kd.find(p)
        if d < best:
            best = d
    return best


panel_gaps = []
for i in range(5):
    for j in range(i + 1, 5):
        d = min_dist(world[PANELS[i]], world[PANELS[j]])
        panel_gaps.append((i + 1, j + 1, d))
min_pp = min(d for _, _, d in panel_gaps)
check("separation: no two lower panels touch (closest vertices >= 10 mm)",
      min_pp >= 0.010,
      "closest pairs: " + ", ".join(f"{a}-{b} {d * 1e3:.1f} mm" for a, b, d in panel_gaps))

# panel vertices coincident with an upper vertex: the seam only
up_pts = world[UPPER]
from mathutils.kdtree import KDTree  # noqa: E402
kd_up = KDTree(len(up_pts))
for k, p in enumerate(up_pts):
    kd_up.insert(p, k)
kd_up.balance()
seam_contacts = []
for n in PANELS:
    for p in world[n]:
        _, _, d = kd_up.find(p)
        if d < 1e-6:
            seam_contacts.append(p)
zs_contact = [p.z for p in seam_contacts]
check("separation: panels meet the upper piece only along the seam",
      seam_contacts and min(zs_contact) > SEAM_Z[0] and max(zs_contact) < SEAM_Z[1]
      and len(seam_contacts) <= 150,
      f"{len(seam_contacts)} shared seam vertices, Z {min(zs_contact):.3f}..{max(zs_contact):.3f}"
      if seam_contacts else "no seam contact")

# panels and upper must not otherwise come within 3 mm of each other
near = 1e9
for n in PANELS:
    kd_p = KDTree(len(world[n]))
    for k, p in enumerate(world[n]):
        kd_p.insert(p, k)
    kd_p.balance()
    for p in up_pts:
        _, _, d = kd_p.find(p)
        if d > 1e-6 and d < near:
            near = d
check("separation: nothing else of the upper piece closer than 1 mm to a panel",
      near >= 0.001 or near == 1e9, f"nearest non-seam pair {near * 1e3:.2f} mm")

# --------------------------------------------------------------------------
# tears and bites: ray-traced presence of the cape from the rear
# --------------------------------------------------------------------------
# A ray from the rear (-Y) at (x, z) hits the cape wherever it is present.
# Missing ray = a tear or bite at that point.  The triangulated mesh gives the
# same answer as the quad mesh (checked separately), so this is the geometry.
cape_objs = [bpy.data.objects[n] for n in [UPPER] + PANELS]
trees = {}
for o in cape_objs:
    mw = o.matrix_world.copy()
    wv = [mw @ v.co for v in o.data.vertices]
    wf = [tuple(p.vertices) for p in o.data.polygons]
    trees[o.name] = BVHTree.FromPolygons(wv, wf, all_triangles=False)


def present(x, z):
    origin = Vector((x, -2.0, z))
    for t in trees.values():
        loc, nrm, idx, dist = t.ray_cast(origin, Vector((0.0, 1.0, 0.0)))
        if loc is not None:
            return True
    return False


def gaps_at(z, x0=-0.62, x1=0.62, step=0.002):
    """x-intervals (start, end, width) inside the cape's span where the cape is absent."""
    xs = [x0 + k * step for k in range(int(round((x1 - x0) / step)) + 1)]
    pres = [present(x, z) for x in xs]
    if not any(pres):
        return []
    first = pres.index(True)
    last = len(pres) - 1 - pres[::-1].index(True)
    out, k = [], first
    while k <= last:
        if not pres[k]:
            s0 = k
            while not pres[k]:
                k += 1
            out.append((xs[s0], xs[k - 1], (k - s0) * step))
        else:
            k += 1
    return out


g045 = gaps_at(0.45)
desc = ", ".join(f"x {a:+.3f}..{b:+.3f} ({w * 1e3:.0f} mm)" for a, b, w in g045) or "none"
print("  Z 0.45 gaps:", desc)
lines.append("  Z 0.45 gaps: " + desc)
check("tears: four narrow tears through the lower cape (one per V-apex)",
      len(g045) == 4, f"gaps at Z 0.45 = {len(g045)}")
check("tears: every tear is narrow (under 50 mm at Z 0.45)",
      g045 and max(w for _, _, w in g045) < 0.05,
      "widths " + ", ".join(f"{w * 1e3:.0f}" for _, _, w in g045) + " mm")

# top of each tear: follow the gap upward from Z 0.45 (the tears slant as the
# cape flares, so a fixed-X probe would lose them); the tear top is the last Z
# at which a gap is still found near the tracked position
def track_tear(x0, z0=0.45, z_max=1.50, dz=0.01):
    x, z, top = x0, z0, z0
    while z <= z_max:
        gs = gaps_at(z, x0=x - 0.06, x1=x + 0.06, step=0.002)
        if not gs:
            break
        g = min(gs, key=lambda q: abs(0.5 * (q[0] + q[1]) - x))
        x = 0.5 * (g[0] + g[1])
        top = z
        z += dz
    return top

tops = []
for a, b, w in g045:
    tops.append(track_tear(0.5 * (a + b)))
desc = ", ".join(f"x {(a + b) / 2:+.3f}: top Z {t:.3f}" for (a, b, _), t in zip(g045, tops))
print("  tear tops:", desc)
lines.append("  tear tops: " + desc)
ordered = sorted(tops)
check("tears: two long tears climb to Z 1.10 or higher into the upper piece",
      sum(1 for t in tops if t >= 1.10) >= 2, "tear tops Z " + ", ".join(f"{t:.3f}" for t in tops))
check("tears: the short tear stops at the seam, well below the long tears",
      min(tops) <= max(tops) - 0.10 and min(tops) < 1.10,
      f"shortest top Z {min(tops):.3f}, longest {max(tops):.3f}")
check("tears: the upper piece is intact at the yoke (no gap at Z 1.35)",
      len(gaps_at(1.35)) == 0, f"gaps at Z 1.35 = {len(gaps_at(1.35))}")
check("tears: the upper piece is intact at the shoulders (no gap at Z 1.50)",
      len(gaps_at(1.50)) == 0, f"gaps at Z 1.50 = {len(gaps_at(1.50))}")

# bites: lowest point of the cape at each bite's x, compared with the hem line
def hem_at(x):
    z = 0.0
    while z < 1.6:
        if present(x, z):
            return z
        z += 0.002
    return None

HEM_HALF_WIDTH = 0.56          # x = u * half_width(v); at the hem the half width is 0.56 m
BITE_TESTS = [
    # name, centre u, lowest-Z band that a bite of this design produces
    ("B1", 0.39, (0.20, 0.40), "large missing section in the lobe between the 3rd and 4th tears"),
    ("B2", -0.42, (0.12, 0.32), "notch in the lobe between the 1st and 2nd tears"),
    ("B3", 0.93, (0.16, 0.42), "torn-off outer corner"),
]
bite_lowest = {}
for name, uc, band, what in BITE_TESTS:
    xc = uc * HEM_HALF_WIDTH
    z_low = hem_at(xc)
    bite_lowest[name] = z_low
    check(f"bites: {name} {what}",
          z_low is not None and band[0] <= z_low <= band[1],
          f"lowest cape at x={xc:+.3f}: Z {z_low:.3f} m (band {band[0]:.2f}-{band[1]:.2f})"
          if z_low is not None else "no cape at the bite centre")
# --------------------------------------------------------------------------
# panel shape: unequal lengths and spacing
# --------------------------------------------------------------------------
pan_info = []
for n in PANELS:
    w = world[n]
    xs_ = [p.x for p in w]
    zs_ = [p.z for p in w]
    lowest = min(zs_)
    lo_side = sorted(p.z for p in w if p.z < 0.2)
    pan_info.append((n, min(xs_), max(xs_), max(xs_) - min(xs_), lowest,
                     max(zs_), len(set(round(p.z, 2) for p in w if p.z < 0.3))))
width_at = [info[3] for info in pan_info]
spread = max(width_at) - min(width_at)
check("panels: unequal widths (spread over 0.08 m)", spread > 0.08,
      "widths " + ", ".join(f"{w:.3f}" for w in width_at) + f" m (spread {spread:.3f})")
centres = sorted((g[0] + g[1]) / 2.0 for g in g045)
steps = [b - a for a, b in zip(centres, centres[1:])]
check("panels: unequal spacing between tears (spread over 0.05 m)",
      len(steps) == 3 and (max(steps) - min(steps)) > 0.05,
      "tear spacings " + ", ".join(f"{s:.3f}" for s in steps) + " m" if steps else "no tears")

# lengths: lowest hem at each panel
lows = [round(p[4], 3) for p in pan_info]
check("panels: each panel reaches the floor band (0.04-0.10 m)",
      all(0.04 <= l <= 0.10 for l in lows), f"lowest points {lows}")

# --------------------------------------------------------------------------
# silhouette: the upper piece reproduces the Prompt 13 outline away from the tears
# --------------------------------------------------------------------------
import build_cape_blockout as cb   # noqa: E402  (the Prompt 13 surface definition)
TEAR_APEX_U = [-0.62, -0.22, 0.16, 0.60]


# every cape vertex must sit about half a shell thickness (9 mm) from the approved
# Prompt 13 surface.  Each vertex is measured against a 601 x 601 sample of that
# surface, then refined by two local searches in (u, v), so the answer is not
# limited by sample spacing (the hem is steep near the V-apexes).
HALF = cb.THICK * 0.5
N_S = 600
surf_pts = []
surf_kd = KDTree((N_S + 1) * (N_S + 1))
k_ = 0
for iu in range(N_S + 1):
    u_ = -1.0 + 2.0 * iu / N_S
    for iv in range(N_S + 1):
        surf_pts.append((u_, iv / N_S))
        surf_kd.insert(cb.surface(u_, iv / N_S), k_)
        k_ += 1
surf_kd.balance()


def surface_distance(p_):
    _, idx, d0 = surf_kd.find(p_)
    u0, v0 = surf_pts[idx]
    best = (d0, u0, v0)
    du, dv = 2.0 / N_S, 1.0 / N_S
    for scale in (1.0, 0.1):
        cu, cv = best[1], best[2]
        for a_ in range(-5, 6):
            for b_ in range(-5, 6):
                uu = min(max(cu + a_ * du * scale / 5.0, -1.0), 1.0)
                vv = min(max(cv + b_ * dv * scale / 5.0, 0.0), 1.0)
                d = (cb.surface(uu, vv) - p_).length
                if d < best[0]:
                    best = (d, uu, vv)
    return best[0]


up_dev = [abs(surface_distance(p_) - HALF) for p_ in world[UPPER]]
pan_dev = [abs(surface_distance(p_) - HALF) for n in PANELS for p_ in world[n]]


def dev_stats(devs):
    srt = sorted(devs)
    med = srt[len(srt) // 2]
    p99 = srt[int(0.99 * (len(srt) - 1))]
    return med, p99, srt[-1], sum(1 for d in srt if d > 0.003)


for label_, devs in (("upper", up_dev), ("panel", pan_dev)):
    med, p99, mx, n3 = dev_stats(devs)
    check(f"silhouette: {label_} vertices sit on the approved Prompt 13 surface (9 mm shell half-thickness)",
          med < 0.0005 and p99 < 0.003 and mx < 0.006,
          f"{len(devs)} vertices: median {med * 1e3:.2f} mm, 99th pct {p99 * 1e3:.2f} mm, "
          f"worst {mx * 1e3:.2f} mm from 9 mm; {n3} beyond 3 mm (the G1 crease, where the shell thins locally)")

old_min_y = min(p.y for p in old_cape_world)
new_min_y = min(p.y for p in [q for n in PANELS + [UPPER] for q in world[n]])
check("silhouette: rear extent unchanged (deepest point within 15 mm of Prompt 13)",
      abs(old_min_y - new_min_y) < 0.015, f"old {old_min_y:.3f} m, new {new_min_y:.3f} m")
old_max_x = max(abs(p.x) for p in old_cape_world)
new_max_x = max(abs(p.x) for n in PANELS + [UPPER] for p in world[n])
check("silhouette: overall width unchanged (within 5 mm)", abs(old_max_x - new_max_x) < 0.005,
      f"old {old_max_x:.3f} m, new {new_max_x:.3f} m")
old_low = min(p.z for p in old_cape_world)
new_low = min(p.z for n in PANELS for p in world[n])
check("silhouette: lowest hem unchanged (within 5 mm)", abs(old_low - new_low) < 0.005,
      f"old {old_low:.3f} m, new {new_low:.3f} m")

# --------------------------------------------------------------------------
# clearance against the armour, body, helmet and crown
# --------------------------------------------------------------------------
depsgraph = bpy.context.evaluated_depsgraph_get()
skip_cols = {COL, "Reference", "Lighting and Cameras"}
others = []
for o in bpy.data.objects:
    if o.type != 'MESH' or o.name in [OLD, UPPER] + PANELS:
        continue
    if any(c.name in skip_cols for c in o.users_collection):
        continue
    if len(o.data.polygons) == 0:
        continue
    others.append(o)

other_trees = []
for o in others:
    ev = o.evaluated_get(depsgraph)
    emesh = ev.to_mesh()
    mw = ev.matrix_world.copy()
    wv = [mw @ v.co for v in emesh.vertices]
    wf = [tuple(p.vertices) for p in emesh.polygons]
    ev.to_mesh_clear()
    lo = Vector((min(v.x for v in wv), min(v.y for v in wv), min(v.z for v in wv)))
    hi = Vector((max(v.x for v in wv), max(v.y for v in wv), max(v.z for v in wv)))
    other_trees.append((o.name, BVHTree.FromPolygons(wv, wf, all_triangles=False), lo, hi))


def inside(p, tree, lo, hi):
    """Parity of ray crossings towards +X (odd = inside a closed mesh)."""
    if not (lo.x - 0.01 <= p.x <= hi.x + 0.01 and lo.y - 0.01 <= p.y <= hi.y + 0.01
            and lo.z - 0.01 <= p.z <= hi.z + 0.01):
        return False
    count, origin = 0, p.copy()
    for _ in range(64):
        loc, nrm, idx, dist = tree.ray_cast(origin, Vector((1.0, 0.0, 0.0)))
        if loc is None:
            break
        count += 1
        origin = loc + Vector((1e-5, 0.0, 0.0))
    return count % 2 == 1


min_clear = (1e9, None)
inside_hits = []
cape_all = [(n, p) for n in [UPPER] + PANELS for p in world[n]]
for name, tree, lo, hi in other_trees:
    pad = 0.12
    for cn, p in cape_all:
        if not (lo.x - pad <= p.x <= hi.x + pad and lo.y - pad <= p.y <= hi.y + pad
                and lo.z - pad <= p.z <= hi.z + pad):
            continue
        loc, nrm, idx, d = tree.find_nearest(p)
        if loc is not None and d < min_clear[0]:
            min_clear = (d, (cn, name))
        if inside(p, tree, lo, hi):
            inside_hits.append((cn, name))
check("clearance: no cape vertex inside any armour, body, helmet or crown mesh",
      not inside_hits, f"inside hits={inside_hits[:5]}")
check("clearance: nearest solid part at least 30 mm from the cape",
      min_clear[0] >= 0.030,
      f"nearest {min_clear[0] * 1e3:.1f} mm ({min_clear[1][0]} to {min_clear[1][1]})")

# --------------------------------------------------------------------------
n_pass = sum(1 for _, ok, _ in results if ok)
summary = f"{n_pass} / {len(results)} checks passing"
print(summary)
header = ["Prompt 14 - cape layered torn panels: verification report",
          "source: Wildshift_Knight_13_CapeBlockout.blend",
          "target: Wildshift_Knight_14_CapePanels.blend", ""]
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
with open(REPORT, "w") as f:
    f.write("\n".join(header + lines + ["", summary]) + "\n")
print("REPORT", REPORT)
