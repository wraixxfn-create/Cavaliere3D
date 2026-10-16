"""Prompt 12 prep: dump the checkpoint-11 object inventory with bounds."""
import bpy
import os

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_11_Medallion.blend")
bpy.ops.wm.open_mainfile(filepath=SRC)

print("VERSION", bpy.app.version_string)
print("OBJECTS:", len(bpy.data.objects))
for o in sorted(bpy.data.objects, key=lambda x: x.name):
    if o.type == 'MESH':
        ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        n = len(me.vertices)
        bb = [o.matrix_world @ v.co for v in me.vertices]
        xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
        print(f"{o.name:52s} verts={n:5d} x=[{min(xs):+.4f},{max(xs):+.4f}] y=[{min(ys):+.4f},{max(ys):+.4f}] z=[{min(zs):+.4f},{max(zs):+.4f}] mats={[m.name for m in o.data.materials]} mods={[m.type for m in o.modifiers]}")
        ev.to_mesh_clear()
    else:
        print(f"{o.name:52s} {o.type}")
print("MATERIALS:")
for m in bpy.data.materials:
    print("  ", m.name, "metallic", m.metallic if hasattr(m, 'metallic') else None, "rough", m.roughness if hasattr(m, 'roughness') else None)
print("TEXTS:", [t.name for t in bpy.data.texts])
print("COLLECTIONS:", [(c.name, len(c.objects)) for c in bpy.data.collections])
