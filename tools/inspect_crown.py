import bpy, json, math
from mathutils import Vector

bpy.ops.wm.open_mainfile(filepath="/home/user/Cavaliere3D/Wildshift_Knight_09_LimbArmor.blend")
dg = bpy.context.evaluated_depsgraph_get()

def walk(c, depth=0):
    print("  " * depth + "[%s] hide_vp=%s hide_rend=%s n=%d kids=%s" % (
        c.name, c.hide_viewport, c.hide_render, len(c.objects), [k.name for k in c.children]))
    for o in c.objects:
        print("  " * (depth + 1) + "- %s (%s)" % (o.name, o.type))
    for k in c.children:
        walk(k, depth + 1)

print("=== COLLECTIONS ===")
walk(bpy.context.scene.collection)

print()
print("=== CROWN / SPIKE OBJECT DETAIL ===")
for o in sorted(bpy.data.objects, key=lambda x: x.name):
    n = o.name.lower()
    if "crown" in n or "spike" in n or "halo" in n or "crest" in n:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        cs = [mw @ v.co for v in me.vertices]
        mn = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
        mx = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
        cen = sum(cs, Vector((0, 0, 0))) / len(cs)
        print("%-42s %-9s v=%4d f=%4d" % (o.name, o.type, len(o.data.vertices) if o.type == 'MESH' else 0,
                                          len(o.data.polygons) if o.type == 'MESH' else 0))
        print("    parent=%s" % (o.parent.name if o.parent else None))
        print("    loc=%s rot=%s scale=%s" % (tuple(round(v, 5) for v in o.location),
                                              tuple(round(math.degrees(v), 3) for v in o.rotation_euler),
                                              tuple(round(v, 5) for v in o.scale)))
        print("    mods=%s mats=%s" % ([(m.name, m.type) for m in o.modifiers], [m.name for m in o.data.materials] if o.data else []))
        print("    eval verts=%d polys=%d" % (len(me.vertices), len(me.polygons)))
        print("    wbbox min=%s max=%s" % (tuple(round(v, 5) for v in mn), tuple(round(v, 5) for v in mx)))
        print("    wsize=%s centre=%s" % (tuple(round(v, 5) for v in (mx - mn)), tuple(round(v, 5) for v in cen)))
        ev.to_mesh_clear()
