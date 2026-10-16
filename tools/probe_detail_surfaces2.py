"""Prompt 12 prep (2): fine probes for trim path end-points and host parenting."""
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
    hit = tree.ray_cast(origin, direction, limit)
    return None if hit[0] is None else (hit[0], hit[1])


belt = bvh_of("WSK_Armor_WaistBelt_01")
band = bvh_of("WSK_Helmet_CrownBand_01")
knee_l = bvh_of("WSK_Armor_KneeCop_L_01")
knee_r = bvh_of("WSK_Armor_KneeCop_R_01")
shin_l = bvh_of("WSK_Armor_Shin_L_01")
shin_r = bvh_of("WSK_Armor_Shin_R_01")
chest = bvh_of("WSK_Armor_Chest_01")

print("== belt arc end (radial cast, z=1.0965 / 1.0135) ==")
for z in (1.0965,):
    for deg in range(0, 92, 2):
        a = math.radians(deg)
        d = Vector((math.sin(a), math.cos(a), 0.0))
        h = cast(belt, d * 0.5 + Vector((0, 0, z)), -d)
        print(f"  z={z} deg={deg:3d} " + (f"r={math.hypot(h[0].x, h[0].y):.4f} x={h[0].x:.4f} y={h[0].y:.4f} n={tuple(round(c,2) for c in h[1])}" if h else "MISS"))

print("\n== crown band lower edge z(x): finest hit z at each x (front) ==")
for x in (0.006, 0.01, 0.02, 0.03, 0.05, 0.065, 0.075, 0.082):
    lo = None
    for i in range(80):
        z = 1.870 + 0.001 * i
        h = cast(band, Vector((x, 0.6, z)), Vector((0.0, -1.0, 0.0)))
        if h and h[0].y > -0.05:
            lo = (z, h[0].y, h[1])
            break
    print(f"  x={x:.3f} " + (f"lower z={lo[0]:.3f} y={lo[1]:.4f} n={tuple(round(c,2) for c in lo[2])}" if lo else "MISS"))

print("\n== crown band: hits at trim height z=1.8945 ==")
for x in (0.006, 0.01, 0.02, 0.03, 0.05, 0.065, 0.075, 0.082):
    h = cast(band, Vector((x, 0.6, 1.8945)), Vector((0.0, -1.0, 0.0)))
    print(f"  x={x:.3f} " + (f"y={h[0].y:.4f} n={tuple(round(c,2) for c in h[1])}" if h else "MISS"))

print("\n== knee ridge path x=-0.150 / +0.150 (hits along z) ==")
for label, tree, x in (("L", knee_l, -0.150), ("R", knee_r, +0.150)):
    for z in [0.495 + 0.01 * i for i in range(12)]:
        h = cast(tree, Vector((x, 1.0, z)), Vector((0.0, -1.0, 0.0)))
        print(f"  {label} x={x:+.3f} z={z:.3f} " + (f"y={h[0].y:.4f} n={tuple(round(c,2) for c in h[1])}" if h else "MISS"))

print("\n== shin ridge path x=-0.170 / +0.170 (hits along z) ==")
for label, tree, x in (("L", shin_l, -0.170), ("R", shin_r, +0.170)):
    for z in [0.365 + 0.01 * i for i in range(13)]:
        h = cast(tree, Vector((x, 1.0, z)), Vector((0.0, -1.0, 0.0)))
        print(f"  {label} x={x:+.3f} z={z:.3f} " + (f"y={h[0].y:.4f} n={tuple(round(c,2) for c in h[1])}" if h else "MISS"))

print("\n== chest chevron path samples (x from 0.010 to 0.112, z 1.450->1.560) ==")
for i in range(11):
    t = i / 10
    x = 0.010 + (0.112 - 0.010) * t
    z = 1.450 + (1.560 - 1.450) * t
    h = cast(chest, Vector((x, 1.0, z)), Vector((0.0, -1.0, 0.0)))
    print(f"  t={t:.1f} x={x:.3f} z={z:.3f} " + (f"y={h[0].y:.4f} n={tuple(round(c,2) for c in h[1])}" if h else "MISS"))

print("\n== chest keel path: hits z 1.150..1.605 step 0.05 ==")
for z in [1.15 + 0.05 * i for i in range(10)]:
    h = cast(chest, Vector((0.0, 1.0, z)), Vector((0.0, -1.0, 0.0)))
    print(f"  z={z:.3f} " + (f"y={h[0].y:.4f} n={tuple(round(c,2) for c in h[1])}" if h else "MISS"))

print("\n== host parenting chain ==")
for n in ("WSK_Armor_Chest_01", "WSK_Armor_WaistBelt_01", "WSK_Helmet_CrownBand_01",
          "WSK_Armor_KneeCop_L_01", "WSK_Armor_KneeCop_R_01",
          "WSK_Armor_Shin_L_01", "WSK_Armor_Shin_R_01",
          "WSK_Armor_WaistMedallionRing_01"):
    o = bpy.data.objects[n]
    chain = []
    p = o.parent
    while p:
        chain.append(p.name)
        p = p.parent
    print(f"  {n}: parent-chain={chain} loc={tuple(round(c,4) for c in o.location)} "
          f"mw_identity={all(abs(o.matrix_world[r][c] - (1.0 if r == c else 0.0)) < 1e-9 for r in range(4) for c in range(4))}")
