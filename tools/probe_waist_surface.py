"""Map the armour surface around the waist medallion mount (Prompt 11 probe 2).

Ray-casts the front and rear waist on a (x, z) grid so the new ornament can be
seated on the real outer surface, and reports the mount's true protrusion.

Run: tools/bl.sh tools/probe_waist_surface.py
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


def trees():
    out = []
    for o in bpy.data.objects:
        if o.type != "MESH" or o.name.startswith(SKIP) or not o.visible_get():
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        verts = [ev.matrix_world @ v.co for v in me.vertices]
        faces = [tuple(p.vertices) for p in me.polygons]
        ev.to_mesh_clear()
        if not verts:
            continue
        out.append((o.name, BVHTree.FromPolygons(verts, faces, all_triangles=False)))
    return out


TR = trees()


def first_hit(origin, direction, only=None):
    best = None
    for name, tree in TR:
        if only and name not in only:
            continue
        loc, nrm, idx, dist = tree.ray_cast(Vector(origin), Vector(direction), 1.0)
        if loc is not None and (best is None or dist < best[1]):
            best = (name, dist, loc, nrm)
    return best


print("== FRONT surface map (ray from y=+0.6 toward -Y) ==")
print("        " + "".join(f"{x:+.3f}  " for x in [-0.10, -0.08, -0.06, -0.04, -0.02, 0.0, 0.02, 0.04, 0.06, 0.08, 0.10]))
for z in [0.95 + 0.01 * i for i in range(20)]:
    row = f"z={z:.3f} "
    for x in [-0.10, -0.08, -0.06, -0.04, -0.02, 0.0, 0.02, 0.04, 0.06, 0.08, 0.10]:
        h = first_hit((x, 0.6, z), (0, -1, 0))
        row += f"{h[2].y:+.4f}  " if h else "  --      "
    print(row)

print("\n== which object is frontmost (front) ==")
for z in [0.96, 1.00, 1.02, 1.05, 1.06, 1.08, 1.10, 1.12]:
    line = f"z={z:.3f} "
    for x in [-0.06, -0.03, 0.0, 0.03, 0.06]:
        h = first_hit((x, 0.6, z), (0, -1, 0))
        line += f"[{h[0].replace('WSK_Armor_', '').replace('WSK_', '') if h else '--':>16s}]"
    print(line)

print("\n== REAR surface map (ray from y=-0.6 toward +Y) ==")
print("        " + "".join(f"{x:+.3f}  " for x in [-0.10, -0.08, -0.06, -0.04, -0.02, 0.0, 0.02, 0.04, 0.06, 0.08, 0.10]))
for z in [0.90 + 0.01 * i for i in range(20)]:
    row = f"z={z:.3f} "
    for x in [-0.10, -0.08, -0.06, -0.04, -0.02, 0.0, 0.02, 0.04, 0.06, 0.08, 0.10]:
        h = first_hit((x, -0.6, z), (0, 1, 0))
        row += f"{h[2].y:+.4f}  " if h else "  --      "
    print(row)

print("\n== which object is rearmost ==")
for z in [0.92, 0.96, 0.99, 1.02, 1.05, 1.08]:
    line = f"z={z:.3f} "
    for x in [-0.06, -0.03, 0.0, 0.03, 0.06]:
        h = first_hit((x, -0.6, z), (0, 1, 0))
        line += f"[{h[0].replace('WSK_Armor_', '').replace('WSK_', '') if h else '--':>16s}]"
    print(line)

print("\n== mount evaluated geometry ==")
mount = bpy.data.objects["WSK_Armor_WaistMedallionMount_01"]
ev = mount.evaluated_get(dg)
me = ev.to_mesh()
pts = [ev.matrix_world @ v.co for v in me.vertices]
print("  y range %.5f .. %.5f" % (min(p.y for p in pts), max(p.y for p in pts)))
print("  x range %.5f .. %.5f" % (min(p.x for p in pts), max(p.x for p in pts)))
print("  z range %.5f .. %.5f" % (min(p.z for p in pts), max(p.z for p in pts)))
import math
r = max(math.hypot(p.x, p.z - 1.055) for p in pts)
print("  max radius from (0,1.055): %.5f" % r)
front = [p for p in pts if p.y > max(q.y for q in pts) - 1e-6]
print("  front-face pts: %d, radius range %.5f .. %.5f"
      % (len(front), min(math.hypot(p.x, p.z - 1.055) for p in front),
         max(math.hypot(p.x, p.z - 1.055) for p in front)))
ev.to_mesh_clear()

print("\n== belt outer skin vs mount at x=0 ==")
for z in [1.005, 1.02, 1.04, 1.055, 1.07, 1.09, 1.105]:
    h = first_hit((0.0, 0.6, z), (0, -1, 0), only={"WSK_Armor_WaistBelt_01"})
    h2 = first_hit((0.0, 0.6, z), (0, -1, 0))
    print(f"  z={z:.3f} belt={h[2].y:+.5f}   all={h2[0]:32s} y={h2[2].y:+.5f}")
