"""Probe the waist region of checkpoint 10 for the medallion mount (Prompt 11).

Reports the existing medallion mount's geometry, every object near the front and
rear waist, the local armour surface around the mount, the material list and the
free vertical / lateral room available to a new ornament.

Run: tools/bl.sh tools/probe_medallion_mounts.py
"""
import os
import sys
from math import degrees

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_10_Crown.blend")

bpy.ops.wm.open_mainfile(filepath=SRC)


def world_bbox(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = Vector((min(p[i] for p in pts) for i in range(3)))
    hi = Vector((max(p[i] for p in pts) for i in range(3)))
    return lo, hi


def report_obj(o, tag=""):
    lo, hi = world_bbox(o)
    print(f"  {tag}{o.name:44s} ctr=({(lo.x+hi.x)/2:+.4f},{(lo.y+hi.y)/2:+.4f},{(lo.z+hi.z)/2:+.4f})"
          f" size=({hi.x-lo.x:.4f},{hi.y-lo.y:.4f},{hi.z-lo.z:.4f})"
          f" v={len(o.data.vertices):5d} mods={[m.type for m in o.modifiers]}")
    return lo, hi


print("== collections ==")
for c in bpy.data.collections:
    print(f"  {c.name:16s} {len(c.objects):3d} objects")

print("\n== materials ==")
for m in bpy.data.materials:
    print(f"  {m.name:34s} nodes={[n.type for n in m.node_tree.nodes] if m.use_nodes else None}")

print("\n== the mount ==")
mount = bpy.data.objects.get("WSK_Armor_WaistMedallionMount_01")
if mount is None:
    print("  MISSING")
else:
    lo, hi = report_obj(mount)
    print("  props:", dict(mount.items()))
    print("  matrix_world:\n", mount.matrix_world)
    print("  verts (first 8):", [tuple(round(v, 4) for v in (mount.matrix_world @ vv.co))
                                 for vv in list(mount.data.vertices)[:8]])

print("\n== objects whose bbox touches the waist band (z 0.90 .. 1.30) ==")
waist = []
for o in bpy.data.objects:
    if o.type != "MESH":
        continue
    lo, hi = world_bbox(o)
    if hi.z > 0.86 and lo.z < 1.34:
        waist.append((o, lo, hi))
for o, lo, hi in sorted(waist, key=lambda t: -t[2].z):
    report_obj(o, "  ")
    print(f"      props-> {o.get('wsk_part', '?')} | {o.get('wsk_attachment', '?')}")

print("\n== front-facing surfaces near the mount (y > 0.09, z 0.95..1.20) ==")
depsgraph = bpy.context.evaluated_depsgraph_get()
front_objs = []
for o, lo, hi in waist:
    if hi.y > 0.09 and lo.z < 1.22 and hi.z > 0.95:
        front_objs.append(o)
for o in front_objs:
    print(f"  {o.name:44s} ymax={world_bbox(o)[1].y:+.4f}")

print("\n== rear-facing surfaces near z 1.05 (y < -0.09) ==")
rear_objs = [o for o, lo, hi in waist if lo.y < -0.09]
for o in rear_objs:
    print(f"  {o.name:44s} ymin={world_bbox(o)[0].y:+.4f}")

print("\n== BVH distance from the mount front face to every other object ==")
if mount is not None:
    mlo, mhi = world_bbox(mount)
    centre = Vector((0.0, mlo.y - 0.004, (mlo.z + mhi.z) / 2))
    print(f"  probe point (just in front of mount): {tuple(round(v, 4) for v in centre)}")
    for o in bpy.data.objects:
        if o.type != "MESH" or o is mount:
            continue
        ev = o.evaluated_get(depsgraph)
        try:
            me = ev.to_mesh()
        except Exception:
            continue
        if len(me.vertices) == 0:
            continue
        tree = BVHTree.FromObject(o, depsgraph)
        loc, nrm, idx, dist = tree.find_nearest(centre)
        if loc and dist < 0.30:
            print(f"    {o.name:42s} d={dist*1000:7.2f} mm  at ({loc.x:+.3f},{loc.y:+.3f},{loc.z:+.3f})")
        ev.to_mesh_clear()

print("\n== free lateral room on the front belt at z = 1.055 ==")
z = 1.055
for x in [i * 0.005 for i in range(-24, 25, 2)]:
    hits = []
    for o, lo, hi in waist:
        if not (lo.x <= x <= hi.x and lo.y <= 0.0 <= hi.y and lo.z <= z <= hi.z):
            continue
        tree = BVHTree.FromObject(o, depsgraph)
        p = Vector((x, 0.30, z))
        d = Vector((0, -1, 0))
        loc, nrm, idx, dist = tree.ray_cast(p, d, 0.4)
        if loc:
            hits.append((o.name, dist, loc.y))
    hits.sort(key=lambda h: h[1])
    if hits:
        nm, dist, y = hits[0]
        print(f"    x={x:+.3f}  front-most {nm:38s} y={y:+.4f}")
