"""Probe the helmet surfaces the crown thorns mount on (Prompt 10).

For the crest, the band, the gorget and the halo: the world-space extent and a
few cross-sections, plus a horizontal ray-cast sweep of the shell so the plant
heights of the two thorn rows can be chosen against real numbers.

Run: tools/bl.sh tools/probe_crown_mounts.py
"""
import math
import os

import bpy  # noqa: F401
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_09_LimbArmor.blend")


def evaluated_world(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    eo = obj.evaluated_get(deps)
    me = eo.to_mesh()
    mw = eo.matrix_world.copy()
    verts = [mw @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    eo.to_mesh_clear()
    return verts, polys


def report(name, obj):
    v, _p = evaluated_world(obj)
    mn = Vector((min(p.x for p in v), min(p.y for p in v), min(p.z for p in v)))
    mx = Vector((max(p.x for p in v), max(p.y for p in v), max(p.z for p in v)))
    print(f"{name}: X {mn.x:+.4f}..{mx.x:+.4f}  Y {mn.y:+.4f}..{mx.y:+.4f}  "
          f"Z {mn.z:+.4f}..{mx.z:+.4f}  ({len(v)} verts)")
    return v


def slice_band(v, z0, z1, label):
    sel = [p for p in v if z0 <= p.z <= z1]
    if not sel:
        print(f"   {label}: no geometry")
        return
    print(f"   {label}: X {min(p.x for p in sel):+.4f}..{max(p.x for p in sel):+.4f}"
          f"  Y {min(p.y for p in sel):+.4f}..{max(p.y for p in sel):+.4f}")


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    for name in ("WSK_Helmet_Crest_01", "WSK_Helmet_CrownBand_01",
                 "WSK_Helmet_NeckGuard_01", "WSK_Helmet_CrownHalo_01",
                 "WSK_Helmet_CrownSpine_01", "WSK_Helmet_CrownMount_01",
                 "WSK_Helmet_Shell_01", "WSK_Helmet_Faceplate_01"):
        obj = bpy.data.objects[name]
        v = report(name, obj)
        if name == "WSK_Helmet_Crest_01":
            for z0 in (1.90, 1.93, 1.96, 1.98, 2.00):
                slice_band(v, z0 - 0.005, z0 + 0.005, f"crest at z={z0:.2f}")
        if name == "WSK_Helmet_CrownBand_01":
            for z0 in (1.886, 1.90, 1.906, 1.914, 1.924):
                slice_band(v, z0 - 0.002, z0 + 0.002, f"band at z={z0:.3f}")
        if name == "WSK_Helmet_NeckGuard_01":
            for z0 in (1.82, 1.84, 1.86, 1.88):
                slice_band(v, z0 - 0.005, z0 + 0.005, f"gorget at z={z0:.2f}")
        print()

    shell = bpy.data.objects["WSK_Helmet_Shell_01"]
    sv, sp = evaluated_world(shell)
    tree = BVHTree.FromPolygons(sv, sp, all_triangles=False)
    print("shell horizontal ray sweep (first hit, outward normal):")
    for z in (1.860, 1.870, 1.875, 1.880, 1.890, 1.900, 1.906, 1.913,
              1.920, 1.930, 1.940, 1.950, 1.960, 1.975, 1.990):
        cells = []
        for th in (0, 25, 40, 55, 70, 85, 100, 115, 130, 145, 160, 180):
            a = math.radians(th)
            hd = Vector((math.sin(a), math.cos(a), 0.0))
            o = Vector((0.0, 0.0, z)) + hd * 0.45
            hit = tree.ray_cast(o, -hd, 0.9)
            if hit[0] is None:
                cells.append(f"{th:3d}:none")
            else:
                p, n = hit[0], hit[1]
                if n.dot(hd) < 0:
                    n = -n
                cells.append(f"{th:3d}:({p.x:+.3f},{p.y:+.3f},nz{n.z:+.2f})")
        print(f"  z={z:.3f}  " + "  ".join(cells))


if __name__ == "__main__":
    main()
