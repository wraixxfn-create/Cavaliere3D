"""Prompt 12 prep: probe the surfaces the trim will be fitted to.

Ray-casts the evaluated hosts and prints surface reads in metres, so the
detail paths can be written as measured numbers.
"""
import math
import os

import bpy  # noqa: F401
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_11_Medallion.blend")
bpy.ops.wm.open_mainfile(filepath=SRC)
bpy.context.view_layer.update()
deps = bpy.context.evaluated_depsgraph_get()


def bvh_of(name):
    o = bpy.data.objects[name]
    ev = o.evaluated_get(deps)
    me = ev.to_mesh()
    mw = ev.matrix_world.copy()
    verts = [mw @ v.co for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, faces, all_triangles=False)


def cast(tree, origin, direction, limit=3.0):
    """Returns (point, normal) or None.  BVHTree.ray_cast -> (loc, nrm, idx, dist)."""
    hit = tree.ray_cast(origin, direction, limit)
    return None if hit[0] is None else (hit[0], hit[1])


def report(label, fn, *args):
    out = fn(*args)
    print(f"{label}: {out}")


chest = bvh_of("WSK_Armor_Chest_01")
belt = bvh_of("WSK_Armor_WaistBelt_01")
band = bvh_of("WSK_Helmet_CrownBand_01")
shell = bvh_of("WSK_Helmet_Shell_01")
crest = bvh_of("WSK_Helmet_Crest_01")
knee_l = bvh_of("WSK_Armor_KneeCop_L_01")
knee_r = bvh_of("WSK_Armor_KneeCop_R_01")
shin_l = bvh_of("WSK_Armor_Shin_L_01")
shin_r = bvh_of("WSK_Armor_Shin_R_01")

print("== collections of hosts ==")
for n in ("WSK_Armor_Chest_01", "WSK_Armor_WaistBelt_01", "WSK_Helmet_CrownBand_01",
          "WSK_Armor_KneeCop_L_01", "WSK_Armor_Shin_L_01", "WSK_Armor_WaistMedallionRing_01"):
    o = bpy.data.objects[n]
    print(f"  {n}: {[c.name for c in o.users_collection]}")

print("\n== chest front Y at x=0 (keel profile) ==")
for z in [1.12 + 0.04 * i for i in range(15)]:
    h = cast(chest, Vector((0.0, 1.0, z)), Vector((0.0, -1.0, 0.0)))
    print(f"  z={z:.3f} y={h[0].y:.4f}" if h else f"  z={z:.3f} MISS")

print("\n== chest front Y cross-sections at several z ==")
for z in (1.20, 1.35, 1.50, 1.58, 1.62):
    row = []
    for x in [0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.14]:
        h = cast(chest, Vector((x, 1.0, z)), Vector((0.0, -1.0, 0.0)))
        row.append(f"{x:.2f}:{h[0].y:.4f}" if h else f"{x:.2f}:MISS")
    print(f"  z={z:.2f} " + " ".join(row))

print("\n== chest: normal at keel for a few z ==")
for z in (1.15, 1.30, 1.45, 1.60):
    h = cast(chest, Vector((0.0, 1.0, z)), Vector((0.0, -1.0, 0.0)))
    if h:
        print(f"  z={z:.2f} y={h[0].y:.4f} n={tuple(round(c,3) for c in h[1])}")

print("\n== belt: outer surface by radial cast (azimuth from +Y front, deg) ==")
axis_y = 0.0
for z in (1.010, 1.030, 1.055, 1.080, 1.100):
    row = []
    for deg in (0, 15, 30, 45, 60, 75, 90):
        a = math.radians(deg)
        d = Vector((math.sin(a), math.cos(a), 0.0))
        h = cast(belt, d * 0.5 + Vector((0, 0, z)), -d)
        row.append(f"{deg:3d}:{h[0].length if h else -1:.4f}".replace("nan", "MISS") if True else "")
        if h:
            row[-1] = f"{deg:3d}:r={math.hypot(h[0].x, h[0].y - axis_y):.4f},y={h[0].y:.4f}"
    print(f"  z={z:.3f} " + " ".join(row))

print("\n== belt: vertical cross-section at x=0 (front) ==")
for z in [1.000 + 0.005 * i for i in range(23)]:
    h = cast(belt, Vector((0.0, 1.0, z)), Vector((0.0, -1.0, 0.0)))
    print(f"  z={z:.3f} y={h[0].y:.4f} n={tuple(round(c,2) for c in h[1])}" if h else f"  z={z:.3f} MISS")

print("\n== belt: vertical cross-section at x=0.10 ==")
for z in (1.010, 1.050, 1.098):
    h = cast(belt, Vector((0.10, 1.0, z)), Vector((0.0, -1.0, 0.0)))
    print(f"  z={z:.3f} y={h[0].y:.4f}" if h else f"  z={z:.3f} MISS")

print("\n== crown band front surface Y at x sweep (z sweep) ==")
for z in (1.890, 1.897, 1.905, 1.915, 1.922):
    row = []
    for x in (0.0, 0.01, 0.02, 0.03, 0.05, 0.07, 0.09, 0.097):
        h = cast(band, Vector((x, 0.6, z)), Vector((0.0, -1.0, 0.0)))
        row.append(f"{x:.3f}:{h[0].y:.4f}" if h else f"{x:.3f}:MISS")
    print(f"  z={z:.3f} " + " ".join(row))

print("\n== crest x-extent vs z (cast along +X from x=-0.2) ==")
for z in (1.880, 1.890, 1.900, 1.910, 1.920):
    row = []
    for y in (0.10, 0.115, 0.125, 0.135):
        h = cast(crest, Vector((-0.2, y, z)), Vector((1.0, 0.0, 0.0)))
        row.append(f"y={y:.3f}:" + (f"{h[0].x:.4f}" if h else "MISS"))
    print(f"  z={z:.3f} " + " ".join(row))

print("\n== helmet shell front Y at x=0 (below the band) ==")
for z in (1.80, 1.85, 1.87, 1.88, 1.885):
    h = cast(shell, Vector((0.0, 0.6, z)), Vector((0.0, -1.0, 0.0)))
    print(f"  z={z:.3f} y={h[0].y:.4f}" if h else f"  z={z:.3f} MISS")

print("\n== knee cop L front Y (x sweep at several z) ==")
for z in (0.495, 0.530, 0.560, 0.590, 0.610):
    row = []
    for x in (-0.22, -0.19, -0.16, -0.13, -0.10, -0.07):
        h = cast(knee_l, Vector((x, 1.0, z)), Vector((0.0, -1.0, 0.0)))
        row.append(f"{x:.2f}:{h[0].y:.4f}" if h else f"{x:.2f}:MISS")
    print(f"  z={z:.3f} " + " ".join(row))

print("\n== knee cop L: best-front-point scan (max y per x at z=0.55) ==")
z = 0.55
for x in (-0.24, -0.21, -0.18, -0.15, -0.12, -0.09, -0.06):
    h = cast(knee_l, Vector((x, 1.0, z)), Vector((0.0, -1.0, 0.0)))
    if h:
        print(f"  x={x:.2f} y={h[0].y:.4f} n={tuple(round(c,2) for c in h[1])}")

print("\n== shin L front Y (x sweep at several z) ==")
for z in (0.370, 0.400, 0.430, 0.460, 0.490):
    row = []
    for x in (-0.25, -0.22, -0.19, -0.16, -0.13, -0.10):
        h = cast(shin_l, Vector((x, 1.0, z)), Vector((0.0, -1.0, 0.0)))
        row.append(f"{x:.2f}:{h[0].y:.4f}" if h else f"{x:.2f}:MISS")
    print(f"  z={z:.3f} " + " ".join(row))

print("\n== shin L: normals at z=0.43 ==")
for x in (-0.22, -0.18, -0.14, -0.10):
    h = cast(shin_l, Vector((x, 1.0, 0.43)), Vector((0.0, -1.0, 0.0)))
    if h:
        print(f"  x={x:.2f} y={h[0].y:.4f} n={tuple(round(c,2) for c in h[1])}")

print("\n== medallion extents (for trim stop margins) ==")
for n in ("WSK_Armor_WaistMedallionRing_01", "WSK_Armor_WaistMedallionRay_01_01",
          "WSK_Armor_WaistMedallionRay_03_01"):
    o = bpy.data.objects[n]
    ev = o.evaluated_get(deps)
    me = ev.to_mesh()
    mw = ev.matrix_world.copy()
    vs = [mw @ v.co for v in me.vertices]
    print(f"  {n}: x=[{min(v.x for v in vs):.4f},{max(v.x for v in vs):.4f}] "
          f"y=[{min(v.y for v in vs):.4f},{max(v.y for v in vs):.4f}] "
          f"z=[{min(v.z for v in vs):.4f},{max(v.z for v in vs):.4f}]")
    ev.to_mesh_clear()
