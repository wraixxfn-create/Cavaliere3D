"""Prompt 15 - a separate ceremonial polearm.

Opens `Wildshift_Knight_14_CapePanels.blend`, adds a polearm as several
separate objects in the existing `Weapon` collection, and saves
`Wildshift_Knight_15_Polearm.blend`.  Every checkpoint-14 object is left
untouched.

Design
------
* A long central shaft (consistent grip diameter ~32 mm) running most of the
  weapon's length.
* A narrow, angular spear-like head at the upper end.
* A small crosspiece just below the head.
* A restrained lower spike (pommel) at the bottom.
* A small burgundy cloth strip near the upper shaft, separate object.
* Total length ~1.40 m, standing vertically beside the character.
* Origin (pivot empty) at the intended grip, so the weapon can later be
  attached to a hand bone.

Run:  tools/bl.sh tools/build_polearm.py
"""
import math
import os

import bpy            # noqa: F401
from mathutils import Vector  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_14_CapePanels.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_15_Polearm.blend")

COLLECTION = "Weapon"
PIVOT_NAME = "WSK_Weapon_Pivot_01"
SHAFT_NAME = "WSK_Weapon_Shaft_01"
HEAD_NAME = "WSK_Weapon_Head_01"
CROSS_NAME = "WSK_Weapon_Crosspiece_01"
POMMEL_NAME = "WSK_Weapon_Pommel_01"
CLOTH_NAME = "WSK_Weapon_ClothStrip_01"

# world placement of the grip origin (beside the character, neutral upright)
PIVOT_LOC = (-0.85, 0.0, 1.05)

# geometry in pivot (grip) space: Z up along the weapon
SHAFT_BOTTOM = -0.95
SHAFT_TOP = 0.25
SHAFT_R = 0.016
SHAFT_N = 16

HEAD_BASE_Z = 0.25
HEAD_TIP_Z = 0.55
HEAD_HALF_W = 0.030
HEAD_THICK = 0.016

CROSS_Z = 0.22
CROSS_HALF = 0.08
CROSS_SECT = 0.018

POMMEL_BASE_Z = -0.95
POMMEL_TIP_Z = -1.08
POMMEL_R = 0.020
POMMEL_N = 12

CLOTH_CENTER = (0.028, 0.0, 0.18)
CLOTH_SIZE = (0.010, 0.09, 0.14)

MAT_STEEL = "MAT_Weapon_DarkSteel_01"
MAT_GOLD = "MAT_Weapon_AntiqueGold_01"
MAT_CLOTH = "MAT_Cape_Burgundy_01"


def link_to(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)


def make_material(name, color, metallic, roughness):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*color, 1.0)
            bsdf.inputs["Metallic"].default_value = metallic
            bsdf.inputs["Roughness"].default_value = roughness
    return m


def mesh_from_data(name, verts, faces, mat=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    if mat is not None:
        obj.data.materials.append(mat)
    return obj


def cylinder_z(name, z0, z1, r, n, mat):
    verts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x = r * math.cos(a)
        y = r * math.sin(a)
        verts.append((x, y, z0))
    for i in range(n):
        a = 2 * math.pi * i / n
        x = r * math.cos(a)
        y = r * math.sin(a)
        verts.append((x, y, z1))
    ci_b = len(verts)
    verts.append((0.0, 0.0, z0))
    ci_t = len(verts)
    verts.append((0.0, 0.0, z1))
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    for i in range(n):
        j = (i + 1) % n
        faces.append((ci_b, j, i))
    for i in range(n):
        j = (i + 1) % n
        faces.append((ci_t, n + i, n + j))
    return mesh_from_data(name, verts, faces, mat)


def cone_z(name, z_base, z_tip, r, n, mat):
    verts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        verts.append((r * math.cos(a), r * math.sin(a), z_base))
    apex = len(verts)
    verts.append((0.0, 0.0, z_tip))
    center = len(verts)
    verts.append((0.0, 0.0, z_base))
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, apex))
    for i in range(n):
        j = (i + 1) % n
        faces.append((center, j, i))
    return mesh_from_data(name, verts, faces, mat)


def box(name, center, size, mat):
    cx, cy, cz = center
    sx, sy, sz = size
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    verts = [
        (cx - hx, cy - hy, cz - hz),
        (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz),
        (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz),
        (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz),
        (cx - hx, cy + hy, cz + hz),
    ]
    faces = [
        (0, 1, 2, 3), (4, 5, 6, 7),
        (0, 1, 5, 4), (2, 3, 7, 6),
        (0, 3, 7, 4), (1, 2, 6, 5),
    ]
    return mesh_from_data(name, verts, faces, mat)


def blade_pyramid(name, z_base, z_tip, half_w, thick, mat):
    t = thick / 2.0
    verts = [
        (-half_w, -t, z_base),
        (half_w, -t, z_base),
        (half_w, t, z_base),
        (-half_w, t, z_base),
        (0.0, 0.0, z_tip),
    ]
    faces = [
        (0, 1, 4),
        (1, 2, 4),
        (2, 3, 4),
        (3, 0, 4),
        (0, 3, 2, 1),  # base
    ]
    return mesh_from_data(name, verts, faces, mat)



def cloth_strip(name, z0, z1, r_inner, r_outer, a0, a1, n, mat):
    verts = []
    def ring(r, z):
        out = []
        for i in range(n + 1):
            a = a0 + (a1 - a0) * i / n
            out.append((r * math.cos(a), r * math.sin(a), z))
        return out
    ob = ring(r_outer, z0)
    ot = ring(r_outer, z1)
    ib = ring(r_inner, z0)
    it = ring(r_inner, z1)
    base = len(verts)
    for v in ob: verts.append(v)
    for v in ot: verts.append(v)
    for v in ib: verts.append(v)
    for v in it: verts.append(v)
    faces = []
    for i in range(n):
        # outer surface
        faces.append((base + i, base + i + 1, base + (n + 1) + i + 1, base + (n + 1) + i))
        # inner surface (reversed)
        bi = base + 2 * (n + 1)
        faces.append((bi + i, bi + (n + 1) + i, bi + (n + 1) + i + 1, bi + i + 1))
    return mesh_from_data(name, verts, faces, mat)

def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    scene = bpy.context.scene
    weapon_col = bpy.data.collections.get(COLLECTION)
    if weapon_col is None:
        weapon_col = bpy.data.collections.new(COLLECTION)
        scene.collection.children.link(weapon_col)

    steel = make_material(MAT_STEEL, (0.08, 0.08, 0.09), 0.9, 0.35)
    gold = make_material(MAT_GOLD, (0.72, 0.55, 0.25), 0.85, 0.30)
    cloth_mat = bpy.data.materials.get(MAT_CLOTH)
    if cloth_mat is None:
        cloth_mat = make_material(MAT_CLOTH, (0.35, 0.06, 0.08), 0.0, 0.78)

    # pivot empty at grip
    pivot = bpy.data.objects.new(PIVOT_NAME, None)
    pivot.empty_display_type = "PLAIN_AXES"
    pivot.empty_display_size = 0.12
    pivot.location = PIVOT_LOC
    link_to(pivot, weapon_col)

    # shaft
    shaft = cylinder_z(SHAFT_NAME, SHAFT_BOTTOM, SHAFT_TOP, SHAFT_R, SHAFT_N, steel)
    shaft.location = (0.0, 0.0, 0.0)
    shaft.parent = pivot
    link_to(shaft, weapon_col)

    # head
    head = blade_pyramid(HEAD_NAME, HEAD_BASE_Z, HEAD_TIP_Z, HEAD_HALF_W, HEAD_THICK, steel)
    head.location = (0.0, 0.0, 0.0)
    head.parent = pivot
    link_to(head, weapon_col)

    # crosspiece
    cross = box(CROSS_NAME, (0.0, 0.0, CROSS_Z), (CROSS_HALF * 2, CROSS_SECT, CROSS_SECT), gold)
    cross.location = (0.0, 0.0, 0.0)
    cross.parent = pivot
    link_to(cross, weapon_col)

    # pommel / lower spike
    pommel = cone_z(POMMEL_NAME, POMMEL_BASE_Z, POMMEL_TIP_Z, POMMEL_R, POMMEL_N, steel)
    pommel.location = (0.0, 0.0, 0.0)
    pommel.parent = pivot
    link_to(pommel, weapon_col)

    # cloth strip (separate): curved band around the upper shaft
    cloth = cloth_strip(CLOTH_NAME, 0.12, 0.24, 0.020, 0.026, -1.0, 1.0, 10, cloth_mat)
    cloth.location = (0.0, 0.0, 0.0)
    cloth.parent = pivot
    link_to(cloth, weapon_col)

    # text block
    notes = """Wildshift Knight 15 - Ceremonial Polearm
=====================================

Separate ceremonial polearm added to the Weapon collection.  All checkpoint-14
objects are unchanged.

Objects (all parented to WSK_Weapon_Pivot_01, identity local transform):
  WSK_Weapon_Pivot_01      plain-axes empty at the grip (world %s)
  WSK_Weapon_Shaft_01      long central shaft, diameter %.3f m
  WSK_Weapon_Head_01       narrow angular spear-like head
  WSK_Weapon_Crosspiece_01 small gold crosspiece below the head
  WSK_Weapon_Pommel_01     restrained lower spike
  WSK_Weapon_ClothStrip_01 small burgundy cloth strip near the upper shaft

Total length ~%.2f m.  Neutral upright beside the character; not rigged to a
hand.  No glowing runes, particles or magical effects.
""" % (PIVOT_LOC, SHAFT_R * 2, (HEAD_TIP_Z - POMMEL_TIP_Z))
    txt = bpy.data.texts.new("WSK_Weapon_Polearm_Notes.txt")
    txt.from_string(notes)

    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print("SAVED", DST)


if __name__ == "__main__":
    main()
