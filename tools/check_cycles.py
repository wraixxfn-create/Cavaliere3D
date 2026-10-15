"""Test whether Cycles CPU can render headless (no GPU context available)."""
import bpy
import os

bpy.ops.wm.open_mainfile(filepath="/home/user/Cavaliere3D/Wildshift_Knight_01.blend")
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 8
scene.render.resolution_x = 256
scene.render.resolution_y = 256
scene.render.filepath = "/tmp/cycles_test.png"
scene.camera = bpy.data.objects["WSK_Cam_Front_Ortho"]
print("starting cycles render", flush=True)
bpy.ops.render.render(write_still=True)
print("CYCLES RENDER OK", os.path.exists("/tmp/cycles_test.png"),
      os.path.getsize("/tmp/cycles_test.png") if os.path.exists("/tmp/cycles_test.png") else 0, flush=True)
