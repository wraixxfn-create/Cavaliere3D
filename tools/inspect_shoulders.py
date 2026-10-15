"""Prompt 7 - inspect the shoulder objects of checkpoint 6 before modifying.

Read-only.  Opens Wildshift_Knight_06_Silhouette.blend and prints:

* every object in the Armor / Helmet collections with its world bounds;
* a full report on the shoulder objects (pauldrons, shoulder spikes) including
  mesh size, closed-manifold status, modifiers, materials and custom props;
* the body/arm cross-section profile around the shoulder, so the new plates can
  be built on the real deltoid + upper-arm volume;
* current clearances between the shoulder armour and the body, the gorget, the
  helmet, the chest and the back plate.

Run: tools/bl.sh tools/inspect_shoulders.py
"""
import math
import os
import sys

import bpy  # noqa: F401
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

SRC = os.path.join(ROOT, "Wildshift_Knight_06_Silhouette.blend")
BODY = "WSK_Body_Base_01"

SHOULDER_NAMES = [
    "WSK_Armor_Pauldron_R_01", "WSK_Armor_Pauldron_L_01",
    "WSK_Armor_ShoulderSpike_R_01", "WSK_Armor_ShoulderSpike_L_01",
]
NEIGHBOURS = [
    "WSK_Helmet_NeckGuard_01", "WSK_Helmet_Shell_01", "WSK_Helmet_Crest_01",
    "WSK_Armor_Chest_01", "WSK_Armor_Back_01",
    "WSK_Armor_Forearm_R_01", "WSK_Armor_Forearm_L_01",
    "WSK_Helmet_CrownHalo_01", "WSK_Helmet_CrownBand_01",
]


def evaluated_world(obj):
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(depsgraph)
    me = ev.to_mesh()
    mw = ev.matrix_world.copy()
    verts = [mw @ v.co for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    return verts, faces


def stats(name):
    obj = bpy.data.objects[name]
    verts, faces = evaluated_world(obj)
    vmin = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
    vmax = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    loose = sum(1 for v in bm.verts if not v.link_edges)
    bm.free()
    print(f"\n-- {name} ({obj.type})")
    print(f"   base mesh   {len(obj.data.vertices)} v / {len(obj.data.polygons)} f"
          f"   evaluated {len(verts)} v / {len(faces)} f")
    print(f"   bounds  X {vmin.x:+.4f} .. {vmax.x:+.4f}  ({vmax.x - vmin.x:.4f})")
    print(f"           Y {vmin.y:+.4f} .. {vmax.y:+.4f}  ({vmax.y - vmin.y:.4f})")
    print(f"           Z {vmin.z:+.4f} .. {vmax.z:+.4f}  ({vmax.z - vmin.z:.4f})")
    print(f"   manifold: non-manifold edges {non_manifold}, boundary edges {boundary}, loose verts {loose}")
    print(f"   transform location {tuple(round(v, 4) for v in obj.location)}"
          f" scale {tuple(round(v, 4) for v in obj.scale)}")
    print(f"   collections {[c.name for c in obj.users_collection]}")
    print(f"   materials {[m.name if m else None for m in obj.data.materials]}")
    for mod in obj.modifiers:
        extra = ""
        if mod.type == "BEVEL":
            extra = (f" width={mod.width} segments={mod.segments}"
                     f" limit={mod.limit_method} angle={math.degrees(mod.angle_limit):.1f}"
                     f" harden={mod.harden_normals}")
        print(f"   modifier {mod.name} [{mod.type}]{extra}")
    for key in sorted(obj.keys()):
        if key.startswith("wsk"):
            print(f"   prop {key} = {obj[key]!r}")
    return obj


def body_profile():
    obj = bpy.data.objects[BODY]
    verts, _ = evaluated_world(obj)
    print("\nBODY CROSS-SECTION AROUND THE SHOULDER")
    print("   z      body max|x| |y|<0.25    arm centre x   arm radius   front y    back y")
    for i in range(21):
        z = 1.78 - 0.02 * i
        slab = [v for v in verts if abs(v.z - z) <= 0.012 and abs(v.y) < 0.30]
        if not slab:
            print(f"  {z:.3f}   (empty)")
            continue
        xs = [abs(v.x) for v in slab]
        rx = max(xs)
        # arm section: everything farther out than 0.11 m from the centre line
        arm = [v for v in slab if abs(v.x) > 0.115]
        if arm:
            cx = sum(abs(v.x) for v in arm) / len(arm)
            rad = max(abs(v.x) for v in arm) - min(abs(v.x) for v in arm)
            front = max(v.y for v in arm)
            back = min(v.y for v in arm)
            print(f"  {z:.3f}   {rx:.4f}            {cx:.4f}         {rad / 2:.4f}"
                  f"      {front:+.3f}    {back:+.3f}")
        else:
            print(f"  {z:.3f}   {rx:.4f}            (torso only)")
    # torso-only max at the shoulder line, for the gorget/neck check
    for z in (1.740, 1.700, 1.660, 1.630):
        slab = [v for v in verts if abs(v.z - z) <= 0.010]
        if slab:
            print(f"  torso slab z {z:.3f}: X +-{max(abs(v.x) for v in slab):.4f}"
                  f"  Y {min(v.y for v in slab):+.4f} .. {max(v.y for v in slab):+.4f}")


def clearance(part_name, other_name):
    a, _ = evaluated_world(bpy.data.objects[part_name])
    b, bf = evaluated_world(bpy.data.objects[other_name])
    tree = BVHTree.FromPolygons(b, bf, all_triangles=False)
    best = None
    for p in a:
        hit = tree.find_nearest(p)
        if hit[0] is None:
            continue
        d = (Vector(hit[0]) - p).length
        if best is None or d < best[0]:
            best = (d, p, Vector(hit[0]))
    if best is None:
        return None
    return best


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    print("=" * 78)
    print("CHECKPOINT 6 SHOULDER INSPECTION (read only)")
    print("=" * 78)

    print("\nCOLLECTIONS")
    for col in bpy.data.collections:
        print(f"  {col.name}: {len(col.objects)} objects"
              f"   children {[c.name for c in col.children]}")

    group = []
    for obj in sorted(bpy.data.objects, key=lambda o: o.name):
        if obj.type != "MESH":
            continue
        if obj.name in SHOULDER_NAMES:
            group.append(obj.name)
        elif obj.name.startswith(("WSK_Armor_", "WSK_Helmet_")):
            verts, _ = evaluated_world(obj)
            vmin = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
            vmax = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
            print(f"  [other] {obj.name:34s} X {vmin.x:+.3f}..{vmax.x:+.3f}"
                  f"  Z {vmin.z:+.3f}..{vmax.z:+.3f}  coll {obj.users_collection[0].name}")

    print("\nSHOULDER OBJECTS (detailed)")
    for name in group:
        stats(name)

    body_profile()

    print("\nCURRENT CLEARANCES (surface to surface, metres)")
    for part in SHOULDER_NAMES:
        for other in [BODY] + NEIGHBOURS:
            res = clearance(part, other)
            if res is None:
                print(f"  {part} -> {other}: no nearest point")
                continue
            d, pa, pb = res
            print(f"  {part:34s} -> {other:26s} min {d:.4f} m"
                  f"  at ({pa.x:+.3f},{pa.y:+.3f},{pa.z:+.3f})")

    print("\nBODY/ARM DATA FOR PLATE LAYOUT")
    print("  shoulder joint R (0.200, 0.000, 1.630); elbow R (0.316, -0.020, 1.281)")
    print("  approved: plate span 0.530 (+-0.265), spike span 0.640 (+-0.320),"
          " top edge Z 1.740")


if __name__ == "__main__":
    main()
