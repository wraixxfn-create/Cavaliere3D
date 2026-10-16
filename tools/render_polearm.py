import bpy, os
ROOT="/home/user/Cavaliere3D"
bpy.ops.wm.open_mainfile(filepath=ROOT+"/Wildshift_Knight_15_Polearm.blend")
scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.device='CPU'
scene.cycles.samples=32
scene.render.resolution_x=1024
scene.render.resolution_y=1024
scene.render.image_settings.file_format='PNG'
outdir=ROOT+"/analysis/polearm"
os.makedirs(outdir, exist_ok=True)
for camname, fname in [("WSK_Cam_Front_Ortho","front.png"),("WSK_Cam_Side_Ortho","side.png")]:
    cam=bpy.data.objects[camname]
    scene.camera=cam
    scene.render.filepath=os.path.join(outdir,fname)
    bpy.ops.render.render(write_still=True)
    print("rendered", fname)
