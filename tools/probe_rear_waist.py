"""Rear-waist surface probe for the Prompt 11 sibling medallion.

Maps the rearmost surface over the centre rear fauld panel and the lower back
plate so the rear ornament can be seated on real geometry.

Run: tools/bl.sh tools/probe_rear_waist.py
"""
import os

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_10_Crown.blend")

bpy.ops.wm.open_mainfile(filepath=SRC)
dg = bpy.context.evaluated_depsgraph_get()
SKIP = ("WSK_Guide_", "WSK_Label_", "WSK_Ref_", "WSK_Joint_", "WSK_Studio_", "WSK_CrownCam")

TR = []
for o in bpy.data.objects:
    if o.type != "MESH" or o.name.startswith(SKIP) or not o.visible_get():
        continue
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    verts = [ev.matrix_world @ v.co for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    if verts:
        TR.append((o.name, BVHTree.FromPolygons(verts, faces, all_triangles=False)))


def first_hit(origin, direction, only=None):
    best = None
    for name, tree in TR:
        if only and name not in only:
            continue
        loc, nrm, idx, dist = tree.ray_cast(Vector(origin), Vector(direction), 1.0)
        if loc is not None and (best is None or dist < best[1]):
            best = (name, dist, loc)
    return best


XS = [-0.06, -0.045, -0.03, -0.015, 0.0, 0.015, 0.03, 0.045, 0.06]
print("== REAR surface over the lower back / rear fauld ==")
print("          " + "".join(f"{x:+.3f}    " for x in XS))
for i in range(34):
    z = 0.88 + 0.012 * i
    row = f"z={z:.3f} "
    for x in XS:
        h = first_hit((x, -0.6, z), (0, 1, 0))
        row += f"{h[2].y:+.4f}  " if h else "  --      "
    print(row)

print("\n== rearmost object ==")
for z in [0.90, 0.93, 0.96, 0.98, 1.00, 1.02, 1.05, 1.08, 1.11, 1.14, 1.17, 1.20]:
    line = f"z={z:.3f} "
    for x in [-0.05, -0.025, 0.0, 0.025, 0.05]:
        h = first_hit((x, -0.6, z), (0, 1, 0))
        line += f"[{h[0].replace('WSK_Armor_', '').replace('WSK_', '') if h else '--':>18s}]"
    print(line)

print("\n== centre rear fauld panel extent (WSK_Armor_WaistPanel_Rear_02_01) ==")
o = bpy.data.objects["WSK_Armor_WaistPanel_Rear_02_01"]
ev = o.evaluated_get(dg)
me = ev.to_mesh()
pts = [ev.matrix_world @ v.co for v in me.vertices]
print("  x %.4f..%.4f  y %.4f..%.4f  z %.4f..%.4f"
      % (min(p.x for p in pts), max(p.x for p in pts),
         min(p.y for p in pts), max(p.y for p in pts),
         min(p.z for p in pts), max(p.z for p in pts)))
ev.to_mesh_clear()

print("\n== body rear surface at x=0 (what the ornament must not reach) ==")
for z in [0.92, 0.94, 0.96, 0.98, 1.00]:
    h = first_hit((0.0, -0.6, z), (0, 1, 0), only={"WSK_Body_Base_01"})
    hb = first_hit((0.0, 0.6, z), (0, -1, 0), only={"WSK_Body_Base_01"})
    print(f"  z={z:.3f}  rear-most body y={h[2].y:+.4f}   front-most body y={hb[2].y:+.4f}")

print("\n== lower back plate (WSK_Armor_Back_01) rear surface at x=0 ==")
for z in [1.11, 1.14, 1.17, 1.20, 1.25, 1.30]:
    h = first_hit((0.0, -0.6, z), (0, 1, 0), only={"WSK_Armor_Back_01"})
    print(f"  z={z:.3f}  y={h[2].y:+.4f}" if h else f"  z={z:.3f}  none")

print("\n== does anything else sit near the rear panel centre (0,-0.10,0.96)? ==")
p = Vector((0.0, -0.16, 0.96))
for name, tree in TR:
    loc, nrm, idx, dist = tree.find_nearest(p)
    if loc and dist < 0.22:
        print(f"  {name:42s} d={dist*1000:7.2f} mm at ({loc.x:+.3f},{loc.y:+.3f},{loc.z:+.3f})")
