import bpy
from mathutils import Vector
import math

# Start from a clean empty scene (no unrelated user work in this fresh project)
bpy.ops.wm.read_factory_settings(use_empty=True)

scene = bpy.context.scene

# ---------- Units & scale ----------
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0   # 1 Blender unit = 1 meter
scene.unit_settings.length_unit = 'METERS'

# ---------- Collections ----------
collection_names = [
    "Reference",
    "Blockout",
    "Body",
    "Helmet",
    "Armor",
    "Cape",
    "Accessories",
    "Weapon",
    "Rig",
    "Lighting and Cameras",
]
collections = {}
for name in collection_names:
    col = bpy.data.collections.new(name)
    scene.collection.children.link(col)
    collections[name] = col

LAC = collections["Lighting and Cameras"]

def link_to(obj, col):
    # remove from any existing collections then link
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)

# ---------- Origin / centerline reference ----------
origin_empty = bpy.data.objects.new("WSK_Origin_Centerline", None)
origin_empty.empty_display_type = 'PLAIN_AXES'
origin_empty.empty_display_size = 0.2
origin_empty.location = (0.0, 0.0, 0.0)
scene.collection.objects.link(origin_empty)

height_ref = bpy.data.objects.new("WSK_HeightRef_2m", None)
height_ref.empty_display_type = 'SPHERE'
height_ref.empty_display_size = 0.05
height_ref.location = (0.0, 0.0, 2.0)
scene.collection.objects.link(height_ref)

# ---------- Ground plane ----------
bpy.ops.mesh.primitive_plane_add(size=4.0, location=(0.0, 0.0, 0.0))
ground = bpy.context.active_object
ground.name = "WSK_Studio_Ground_01"
link_to(ground, LAC)

# ---------- Cameras ----------
def make_camera(name, loc, target, ortho=True, ortho_scale=2.5, lens=50):
    cam_data = bpy.data.cameras.new(name)
    if ortho:
        cam_data.type = 'ORTHO'
        cam_data.ortho_scale = ortho_scale
    else:
        cam_data.type = 'PERSP'
        cam_data.lens = lens
    obj = bpy.data.objects.new(name, cam_data)
    link_to(obj, LAC)
    obj.location = loc
    direction = (Vector(target) - Vector(loc)).normalized()
    obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return obj

front_cam = make_camera("WSK_Cam_Front_Ortho", (0.0, 4.0, 1.0), (0.0, 0.0, 1.0), True, 2.5)
side_cam = make_camera("WSK_Cam_Side_Ortho", (4.0, 0.0, 1.0), (0.0, 0.0, 1.0), True, 2.5)
rear_cam = make_camera("WSK_Cam_Rear_Ortho", (0.0, -4.0, 1.0), (0.0, 0.0, 1.0), True, 2.5)
threeq_cam = make_camera("WSK_Cam_ThreeQuarter", (3.0, 3.0, 1.6), (0.0, 0.0, 1.0), False, 2.5, 50)

# ---------- Lighting (neutral studio) ----------
def make_light(name, type_, energy, loc, target=None, size=1.0):
    light_data = bpy.data.lights.new(name, type_)
    light_data.energy = energy
    if type_ == 'AREA':
        light_data.size = size
    obj = bpy.data.objects.new(name, light_data)
    link_to(obj, LAC)
    obj.location = loc
    if target is not None:
        direction = (Vector(target) - Vector(loc)).normalized()
        obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return obj

key = make_light("WSK_Light_Key", 'AREA', 800, (3.0, 3.0, 4.0), (0.0, 0.0, 1.0), 2.0)
fill = make_light("WSK_Light_Fill", 'AREA', 300, (-3.0, 2.0, 3.0), (0.0, 0.0, 1.0), 2.0)
rim = make_light("WSK_Light_Rim", 'AREA', 500, (0.0, -3.0, 3.5), (0.0, 0.0, 1.0), 1.5)
sun = make_light("WSK_Light_Sun", 'SUN', 2.0, (5.0, -2.0, 6.0), (0.0, 0.0, 1.0))

# ---------- World background ----------
world = bpy.data.worlds.new("WSK_World")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.05, 0.05, 0.05, 1.0)
    bg.inputs[1].default_value = 1.0

# ---------- Documentation text block ----------
notes = """Wildshift Knight 01 - Project Setup Notes
===========================================

Blender version: 4.5.0
Units: Metric, 1 Blender unit = 1 meter.
Character scale: provisional human height ~2.0 m (excluding tallest helmet spikes).
  Height reference empty: WSK_HeightRef_2m at Z=2.0.

Coordinate / orientation convention:
  - Z axis = vertical (up). Ground plane at Z=0.
  - Y axis = facing / forward. Character faces +Y (toward front camera).
  - X axis = right.
  - Origin = base of character, centered on ground (feet center). Centerline = X=0, Y=0 (vertical Z axis).
  - Front camera is on +Y side looking toward origin.

Collections:
  Reference, Blockout, Body, Helmet, Armor, Cape, Accessories, Weapon, Rig, Lighting and Cameras.

Cameras:
  WSK_Cam_Front_Ortho, WSK_Cam_Side_Ortho, WSK_Cam_Rear_Ortho (orthographic),
  WSK_Cam_ThreeQuarter (perspective inspection).

Naming convention:
  Objects:     WSK_<Category>_<Descriptor>_<Index>   (e.g. WSK_Helmet_Crown_01)
  Collections: as listed above (Title Case).
  Materials:   MAT_<Category>_<Descriptor>_<Index>    (e.g. MAT_Armor_Blackened_01)
  Textures:    TEX_<Category>_<Descriptor>_<Index>
  Rig bones:   DEF_<BoneName>, CTRL_<BoneName>, MCH_<BoneName>
  Lights/Cams: WSK_<Type>_<Name>

Reference image:
  No reference image file was found in the workspace at setup time.
  If a reference becomes available, import it into the 'Reference' collection
  as an empty image (Add > Image > Reference) preserving aspect ratio.
  The supplied combined four-view image is a visual reference only, not a
  clean orthographic sheet.

Limitations:
  - No detailed geometry, materials, rigging, or animation created.
  - Ground plane and studio lights only for inspection.
  - Stubs used to run bpy headlessly do not affect the saved .blend.
"""
txt = bpy.data.texts.new("WSK_Project_Notes.txt")
txt.from_string(notes)

# ---------- Save ----------
out_path = "/home/user/Cavaliere3D/Wildshift_Knight_01.blend"
bpy.ops.wm.save_as_mainfile(filepath=out_path)
print("SAVED", out_path)
