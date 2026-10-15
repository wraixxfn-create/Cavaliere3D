import bpy, os

path = "/home/user/Cavaliere3D/Wildshift_Knight_01.blend"
bpy.ops.wm.open_mainfile(filepath=path)

scene = bpy.context.scene
print("FILE", path, "exists", os.path.exists(path), "size", os.path.getsize(path))
print("VERSION", bpy.app.version_string)
print("UNITS", scene.unit_settings.system, scene.unit_settings.scale_length, scene.unit_settings.length_unit)
print("COLLECTIONS:")
for c in bpy.data.collections:
    print("  -", repr(c.name), "objects:", len(c.objects))
print("OBJECTS:")
for o in bpy.data.objects:
    print("  -", o.name, o.type, tuple(round(x,3) for x in o.location))
print("CAMERAS:")
for o in bpy.data.objects:
    if o.type == 'CAMERA':
        print("  -", o.name, o.data.type, "ortho_scale" if o.data.type=='ORTHO' else "lens", getattr(o.data,'ortho_scale',None) or getattr(o.data,'lens',None))
print("TEXTS:", [t.name for t in bpy.data.texts])

print("THREEQ LENS CHECK:")
for o in bpy.data.objects:
    if o.name == "WSK_Cam_ThreeQuarter":
        print("  type", o.data.type, "lens", o.data.lens, "ortho_scale", o.data.ortho_scale)
