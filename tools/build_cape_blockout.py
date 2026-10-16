"""Prompt 13 - the cape base shape (blockout) on the checkpoint-12 knight.

Opens `Wildshift_Knight_12_ArmorDetails.blend` and adds ONE separate cape mesh
(plus a pivot empty) to the existing `Cape` collection, then saves
`Wildshift_Knight_13_CapeBlockout.blend`.  Every checkpoint-12 object keeps its
geometry, transform, parent, modifiers and material; nothing is applied or
deleted.  The cape guide envelope in `Reference` is left as it was.

Shape (metres, Blender axes: X right, Y forward/+Y = front, Z up)
-----------------------------------------------------------------
* Attachment: a narrow yoke across the upper back, top edge at Z ~1.60, set
  BEHIND the rear shoulder spikes (Y ~ -0.23 against spike tips at Y -0.176) so
  the cape reads as a separate garment hung from the shoulders.  It never
  touches the back plate (Y -0.164) or the helmet, and its front face stays
  behind Y = -0.20 everywhere, so the front torso and helmet stay bare.
* Width: half-width grows from 0.19 at the yoke to 0.56 by Z ~0.75 (the
  reference's 1.10 m solid cloth width), then holds to the hem.
* Depth: the cape falls behind the body and billows back to about Y -0.67 at
  mid-height (deepest point -0.68; reference rear extent -0.72 / -0.63), shallower
  at the sides.
* Hem: 0.06 m above the floor on the four long lobes, with four broad V-shaped
  tears (apex at Z 0.36-0.50) between them.  Tears are part of the surface
  outline, not holes, so the mesh stays closed.
* Volume: the surface is a shell of 18 mm thickness with a gentle back-billow
  and light vertical folds, so it has real depth and is not a flat sheet.

Topology
--------
One closed quad-grid solid: 24 x 32 cells on each face, two faces, a boundary
wall around the outline.  No modifiers, no booleans, nothing applied.  Vertex
groups `Cape_Yoke`, `Cape_Body`, `Cape_Hem` and `Cape_Panel_1..5` are written
so the cape can be split into panels later.  The five panel boundaries sit on
the four tear apexes.

Pivot: the cape object's origin is the yoke centre (0, -0.23, 1.60).  A plain
empty `WSK_Cape_Pivot_01` sits there too and is the cape's parent with an
identity local transform, ready for a rig or simulation driver.

Run:  tools/bl.sh tools/build_cape_blockout.py
"""
import bisect
import math
import os

import bpy            # noqa: F401  (must be imported first: sets module paths)
import bmesh          # noqa: E402
from mathutils import Vector  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_12_ArmorDetails.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_13_CapeBlockout.blend")

PROMPT = "13 - cape base shape"
CAPE_NAME = "WSK_Cape_Blockout_01"
PIVOT_NAME = "WSK_Cape_Pivot_01"
MAT_NAME = "MAT_Cape_Burgundy_01"
COLLECTION = "Cape"

PIVOT = (0.0, -0.23, 1.60)   # yoke centre; object origin and empty location
THICK = 0.018                # shell thickness, metres
NU, NV = 24, 32              # quad cells across / down each face

YOKE_Z = 1.60                # attachment height at the centre line
YOKE_DROOP = 0.05            # the yoke dips this much at the shoulders (u = +-1)
W_TOP, W_FULL = 0.19, 0.37   # half-width at yoke, extra half-width at full flare
W_FULL_V = 0.60              # the flare is complete at this fraction of the length
HEM_Z = 0.06                 # hem height on the lobes
HEM_RIPPLE = 0.03            # lobe length variation
Y_TOP, Y_DEPTH = -0.23, 0.36 # yoke depth and extra depth at the hem
Y_BILLOW = 0.24              # back-billow at mid-height
FOLD_AMP = 0.018             # vertical folds on the outer face

# four broad tears: (centre u, left half-width u, right half-width u, raise m)
TEARS = [
    (-0.62, 0.15, 0.12, 0.34),
    (-0.22, 0.12, 0.16, 0.27),
    (0.16, 0.17, 0.13, 0.41),
    (0.60, 0.13, 0.15, 0.30),
]

NOTES = """Wildshift Knight 13 - Cape Base Shape (blockout)
==================================================

One separate burgundy cape mesh, WSK_Cape_Blockout_01, in the Cape collection,
hung from the upper back behind the rear shoulder spikes.

Object and pivot
  WSK_Cape_Blockout_01  the cape mesh; origin at the yoke centre (0, -0.230, 1.600)
  WSK_Cape_Pivot_01     plain-axes empty at the same point, parent of the cape
                        (identity local transform)

Measurements (metres)
  yoke (top edge)       Z 1.55-1.60, half-width 0.19, front face Y -0.23
  full width            half-width 0.56 by Z ~0.75  (reference 1.10 m solid cloth)
  hem                   Z 0.06 on the four lobes, tears up to Z ~0.50
  rear extent           Y about -0.67 at mid-height (deepest -0.68), -0.59 at the hem
  shell thickness       0.018 (outer and inner faces)
  clearance             behind the rear shoulder spikes and the back plate;
                        front face never forward of Y -0.20

Topology
  one closed quad-grid solid, 24 x 32 cells per face, boundary walls, no
  modifiers, no applied transforms.  Vertex groups Cape_Yoke / Cape_Body /
  Cape_Hem and Cape_Panel_1..5 (panels split at the four tear apexes) are
  reserved for later panel work.

Material
  MAT_Cape_Burgundy_01 - single placeholder, dark burgundy, roughness 0.78,
  metallic 0, no emission, no textures.

Not done yet (by design)
  no cloth simulation, wind, physics, torn threads, chains or embroidery; the
  cape is a static blockout only.  The Reference-collection cape envelope
  guides are unchanged.
"""


def smooth01(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def hem_z(u):
    """Hem height for a column at u in [-1, 1]: lobes plus V-shaped tears."""
    z = HEM_Z + HEM_RIPPLE * (0.5 + 0.5 * math.sin(5.3 * u + 0.4))
    for c, wl, wr, h in TEARS:
        d = u - c
        w = wl if d < 0 else wr
        t = 1.0 - abs(d) / w
        if t > 0.0:
            z += h * t
    return z


def yoke_z(u):
    return YOKE_Z - YOKE_DROOP * u * u


def half_width(v):
    return W_TOP + W_FULL * smooth01(v / W_FULL_V)


def surface(u, v):
    """Centre surface of the cape: u in [-1, 1] across, v in [0, 1] down."""
    zt = yoke_z(u)
    zh = hem_z(u)
    x = u * half_width(v)
    z = zt - v * (zt - zh)
    # back billow: strongest mid-height, weaker at the sides (cloak edges fall)
    billow = Y_BILLOW * math.sin(math.pi * v) ** 1.2 * (0.6 + 0.4 * (1.0 - u * u))
    y = Y_TOP - Y_DEPTH * v ** 1.1 - billow
    # light vertical folds on the outer face, fading to the hem
    y += FOLD_AMP * math.sin(3.4 * math.pi * u + 0.3) * math.sin(math.pi * min(1.2 * v, 1.0))
    return Vector((x, y, z))


def normal_at(u, v, eps=1e-3):
    u0, u1 = max(-1.0, u - eps), min(1.0, u + eps)
    v0, v1 = max(0.0, v - eps), min(1.0, v + eps)
    su = (surface(u1, v) - surface(u0, v)) / (u1 - u0)
    sv = (surface(u, v1) - surface(u, v0)) / (v1 - v0)
    n = su.cross(sv)
    n.normalize()
    if n.y > 0.0:          # outward = toward -Y, away from the body
        n = -n
    return n


def build_cape_mesh():
    """Return (verts, faces, grid_info) for the closed shell, in pivot space."""
    outer, inner = {}, {}
    grid = []
    for i in range(NU + 1):
        u = -1.0 + 2.0 * i / NU
        for j in range(NV + 1):
            v = j / NV
            p = surface(u, v) - PIVOT_VEC
            n = normal_at(u, v)
            outer[(i, j)] = p + n * (THICK * 0.5)
            inner[(i, j)] = p - n * (THICK * 0.5)
            grid.append((i, j, u, v))

    verts, index = [], {}
    for key in sorted(outer):
        index[("o",) + key] = len(verts)
        verts.append(tuple(outer[key]))
    for key in sorted(inner):
        index[("i",) + key] = len(verts)
        verts.append(tuple(inner[key]))

    faces = []
    for i in range(NU):
        for j in range(NV):
            a, b = index[("o", i, j)], index[("o", i + 1, j)]
            c, d = index[("o", i + 1, j + 1)], index[("o", i, j + 1)]
            faces.append((a, b, c, d))
            a, b = index[("i", i, j)], index[("i", i + 1, j)]
            c, d = index[("i", i + 1, j + 1)], index[("i", i, j + 1)]
            faces.append((a, d, c, b))

    # boundary walls: top (yoke), bottom (hem), left and right edges
    boundary = []
    for i in range(NU):
        boundary.append(((i, 0), (i + 1, 0)))
        boundary.append(((i, NV), (i + 1, NV)))
    for j in range(NV):
        boundary.append(((0, j), (0, j + 1)))
        boundary.append(((NU, j), (NU, j + 1)))
    for p, q in boundary:
        faces.append((index[("o",) + p], index[("o",) + q],
                      index[("i",) + q], index[("i",) + p]))
    return verts, faces, index


PIVOT_VEC = Vector(PIVOT)
PANEL_CENTRES = [t[0] for t in TEARS]


def panel_of(u):
    return bisect.bisect_right(PANEL_CENTRES, u) + 1      # 1..5


def make_object(verts, faces, index, material):
    me = bpy.data.meshes.new(CAPE_NAME + "_mesh")
    me.from_pydata(verts, [], faces)
    me.validate(verbose=False)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    for poly in me.polygons:
        poly.use_smooth = True
    me.materials.append(material)

    obj = bpy.data.objects.new(CAPE_NAME, me)
    # vertex groups for later panel / rig work
    groups = {}
    for name in ["Cape_Yoke", "Cape_Body", "Cape_Hem"] + [f"Cape_Panel_{k}" for k in range(1, 6)]:
        groups[name] = obj.vertex_groups.new(name=name)
    for (side, i, j), idx in index.items():
        u = -1.0 + 2.0 * i / NU
        v = j / NV
        if v <= 0.2:
            groups["Cape_Yoke"].add([idx], 1.0, 'REPLACE')
        elif v >= 0.85:
            groups["Cape_Hem"].add([idx], 1.0, 'REPLACE')
        else:
            groups["Cape_Body"].add([idx], 1.0, 'REPLACE')
        groups[f"Cape_Panel_{panel_of(u)}"].add([idx], 1.0, 'REPLACE')
    return obj


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    col = bpy.data.collections[COLLECTION]
    for name in (CAPE_NAME, PIVOT_NAME, MAT_NAME):
        if name in bpy.data.objects or name in bpy.data.materials:
            raise RuntimeError(f"{name} already exists in the source checkpoint")

    mat = bpy.data.materials.new(MAT_NAME)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    colour = (0.23, 0.02, 0.035, 1.0)
    bsdf.inputs["Base Color"].default_value = colour
    bsdf.inputs["Roughness"].default_value = 0.78
    bsdf.inputs["Metallic"].default_value = 0.0
    mat.diffuse_color = colour

    verts, faces, index = build_cape_mesh()
    cape = make_object(verts, faces, index, mat)

    pivot = bpy.data.objects.new(PIVOT_NAME, None)
    pivot.empty_display_type = 'PLAIN_AXES'
    pivot.empty_display_size = 0.08
    pivot.location = PIVOT_VEC
    col.objects.link(pivot)
    col.objects.link(cape)

    cape.parent = pivot
    cape.matrix_parent_inverse = pivot.matrix_world.inverted()
    cape.location = (0.0, 0.0, 0.0)

    for obj, part, note in [
        (cape, "cape_base_shape", "one closed cloth-like shell, hung behind the rear shoulder spikes"),
        (pivot, "cape_pivot", "yoke centre: cape origin and parent for later rig or sim driver"),
    ]:
        obj["wsk_part"] = part
        obj["wsk_prompt"] = PROMPT
        obj["wsk_note"] = note

    txt = bpy.data.texts.get("WSK_Cape_Blockout_Notes.txt") or \
        bpy.data.texts.new("WSK_Cape_Blockout_Notes.txt")
    txt.from_string(NOTES)

    bpy.context.view_layer.update()
    print("BUILT", CAPE_NAME, len(cape.data.vertices), "verts",
          len(cape.data.polygons), "faces")
    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print("SAVED", DST)


if __name__ == "__main__":
    main()
