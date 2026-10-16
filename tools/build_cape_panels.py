"""Prompt 14 - the cape refined into layered torn panels.

Opens `Wildshift_Knight_13_CapeBlockout.blend`, replaces the single cape shell
`WSK_Cape_Blockout_01` with ONE upper cape piece and FIVE separate lower panels,
all in the existing `Cape` collection, and saves
`Wildshift_Knight_14_CapePanels.blend`.

Silhouette
----------
The surface is the Prompt 13 surface, imported unchanged from
`tools/build_cape_blockout.py` (`surface`, `normal_at`, `THICK`, `PIVOT_VEC`,
`yoke_z`, `hem_z`).  Only the sampling is finer (48 x 56 cells per face instead
of 24 x 32), so the outline, flare, rear billow and four broad hem lobes are the
approved ones.  The new work is a set of cuts, not a new shape:

* Upper piece  - everything above a wavy seam at about 46 % of the drop
  (Z ~0.9 at the centre).  It is one closed shell and stays intact across the
  whole yoke, the shoulders and the upper back.  Only the long tears (below) cut
  into it.
* Lower panels - five separate closed shells hung from that seam.  Their
  boundaries are the four Prompt 13 tear apexes (u -0.62, -0.22, 0.16, 0.60):
  each narrow cut continues upward from the apex of one of the approved
  V-tears, so the panel edges are the tears themselves, not new lines.  The
  panels differ in width, height and hem shape.

Tears and missing sections
--------------------------
Gap columns are removed from the top of the tear down to the hem:
  G1  u -0.62, 1 cell  long narrow tear from the first V-apex, top ~Z 1.2
  G2  u -0.22, 2 cells medium tear from the second apex, 5 rows above the seam
  G3  u +0.16, 1 cell  long narrow tear from the third (deepest) apex
  G4  u +0.60, 1 cell  short tear, ends exactly at the seam
Missing sections are bites removed from the hem lobes:
  B1  u +0.39, half-width 0.05, deepest about Z 0.3 at the centre
  B2  u -0.42, half-width 0.05, the lobe between the first two tears
  B3  u +0.93, half-width 0.08, torn-off outer corner

Gap and bite columns are whole grid columns, so a gap is always a clean
2-4 cm opening at the hem and can be inspected.  Neighbouring panels never
share a vertex or an edge.  The only contact between a panel and the upper
piece is along the seam, where the two shells meet edge to edge.

Materials
---------
Two placeholder materials, both two-sided: `MAT_Cape_Burgundy_01` on the outer
and inner faces (unchanged from Prompt 13) and `MAT_Cape_Burgundy_Edge_01`, a
darker tone, on the 18 mm wall faces so each cut edge reads as thickness.

Pivot
-----
`WSK_Cape_Pivot_01` (Prompt 13, yoke centre) is still the parent of every cape
mesh with an identity local transform.  No cloth, no modifiers, nothing applied.

Run:  tools/bl.sh tools/build_cape_panels.py
"""
import bisect
import math
import os
import sys

import bpy            # noqa: F401  (must be imported first: sets module paths)
import bmesh          # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_cape_blockout as cb  # noqa: E402  (surface + constants of Prompt 13)

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_13_CapeBlockout.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_14_CapePanels.blend")

PROMPT = "14 - cape layered torn panels"
OLD_CAPE = "WSK_Cape_Blockout_01"
UPPER_NAME = "WSK_Cape_Upper_01"
PANEL_NAMES = [f"WSK_Cape_Panel_{k:02d}" for k in range(1, 6)]
PIVOT_NAME = cb.PIVOT_NAME
MAT_OUTER = cb.MAT_NAME                  # MAT_Cape_Burgundy_01 (Prompt 13)
MAT_EDGE = "MAT_Cape_Burgundy_Edge_01"
COLLECTION = "Cape"

NU, NV = 48, 56                 # cells across / down each face (Prompt 13: 24 x 32)
THICK = cb.THICK
PIVOT_VEC = cb.PIVOT_VEC

# seam: the upper piece ends here (fraction of the drop, per column)
SEAM_V = 0.46
SEAM_WAVE = 0.03

# gap columns: (centre u, number of cells, mode, parameter)
#   'row'  -> tear stops at a fixed row (v = row / NV)
#   'slit' -> tear stops this many rows above the seam
#   'seam' -> tear stops exactly at the seam (no cut into the upper piece)
GAPS = [
    (-0.62, 1, "row", 18),     # G1: first V-apex
    (-0.22, 2, "slit", 5),     # G2: second V-apex, two cells wide
    (0.16, 1, "row", 21),      # G3: third (deepest) V-apex
    (0.60, 1, "seam", 0),      # G4: fourth V-apex, short
]

# bites: (centre u, half-width u, centre v of the cut, edge v of the cut)
BITES = [
    (0.39, 0.05, 0.84, 0.97),
    (-0.42, 0.05, 0.90, 0.98),
    (0.93, 0.08, 0.86, 0.99),
]

NOTES = """Wildshift Knight 14 - Cape Layered Torn Panels
===============================================

The Prompt 13 cape shell (WSK_Cape_Blockout_01) is replaced by one upper piece
and five separate lower panels, all in the Cape collection.  The surface is the
Prompt 13 surface, sampled finer (48 x 56 cells); the outline is unchanged.

Objects
  WSK_Cape_Upper_01     upper cape: shoulders to a wavy seam at Z ~0.9,
                        one closed shell, cut only by the two long tears
  WSK_Cape_Panel_01..05 five separate lower panels, left to right (-X to +X),
                        each one closed shell hung from the seam
  WSK_Cape_Pivot_01     plain-axes empty at the yoke centre, parent of all
                        cape meshes (identity local transform)

Tears (gap columns, removed from the hem upward; on the four Prompt 13 V-apexes)
  G1 u -0.62  narrow, long, top about Z 1.2 in the upper piece
  G2 u -0.22  medium, two cells, 5 rows into the upper piece
  G3 u +0.16  narrow, long, top about Z 1.1 in the upper piece
  G4 u +0.60  short, ends at the seam

Missing sections (bites in the hem lobes)
  B1 u +0.39  large, centre about Z 0.3
  B2 u -0.42  notch in the lobe between the first two tears
  B3 u +0.93  torn-off outer corner

Materials (placeholders, both two-sided)
  MAT_Cape_Burgundy_01       outer and inner faces
  MAT_Cape_Burgundy_Edge_01  18 mm wall faces (cut edges)

Not done (by design)
  no cloth simulation, wind, physics, rigging or modifiers; nothing applied;
  the armour and the body are not modified.
"""


def smooth_bump(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def u_of_col(i):
    """Centre u of cell column i (0..NU-1)."""
    return -1.0 + (2.0 * i + 1.0) / NU


def seam_row(i):
    """Row index of the seam at the centre of column i."""
    u = u_of_col(i)
    v = SEAM_V + SEAM_WAVE * math.sin(3.1 * u + 0.6)
    return int(round(v * NV))


def build_gap_columns():
    """Return (groups, col_to_group) where groups is a list of dicts."""
    groups = []
    for ug, n, mode, param in GAPS:
        i0 = int(math.floor((ug + 1.0) * NU / 2.0))
        first = i0 - (n - 1) // 2
        cols = list(range(first, first + n))
        if cols[0] < 0 or cols[-1] >= NU:
            raise RuntimeError(f"gap at u={ug} falls outside the grid")
        groups.append({"u": ug, "cols": cols, "mode": mode, "param": param})
    groups.sort(key=lambda g: g["cols"][0])
    col_to_group = {}
    for k, g in enumerate(groups):
        for c in g["cols"]:
            col_to_group[c] = k
    return groups, col_to_group


GROUPS, COL_GROUP = build_gap_columns()
GROUP_LAST_COL = [g["cols"][-1] for g in GROUPS]


def tear_row(i):
    """Row at which the gap in column i stops (rows >= this are removed)."""
    g = GROUPS[COL_GROUP[i]]
    s = seam_row(i)
    if g["mode"] == "row":
        jt = min(g["param"], s)
    elif g["mode"] == "slit":
        jt = s - g["param"]
    else:
        jt = s
    return max(1, jt)


def bite_row(i):
    """Row at which the hem bite in column i starts (rows >= this are removed)."""
    u = u_of_col(i)
    best = None
    for c, hw, v_c, v_e in BITES:
        t = 1.0 - abs(u - c) / hw
        if t <= 0.0:
            continue
        v_cut = v_e - (v_e - v_c) * t ** 0.7 + 0.012 * math.sin(23.0 * u + 1.0)
        r = int(round(v_cut * NV))
        best = r if best is None else min(best, r)
    return NV + 1 if best is None else best


def panel_index(i):
    """0..4 for the lower panel that owns column i (outside any gap)."""
    return bisect.bisect_left(GROUP_LAST_COL, i)


def owner(i, j):
    """Return 'upper', a panel index 0..4, or None for a removed cell (i, j)."""
    if i in COL_GROUP:
        if j >= tear_row(i):
            return None
        if j < seam_row(i):
            return "upper"
        return None      # unreachable: tear_row <= seam_row
    if j >= bite_row(i):
        return None
    if j < seam_row(i):
        return "upper"
    return panel_index(i)


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------
_pts = {}
NORMAL_PASSES = 2


def smoothed_normals():
    """Node normals of the centre surface, lightly averaged over 3 x 3 neighbours.

    The Prompt 13 hem has V-shaped creases; a per-node normal that turns sharply
    across one cell makes the outer and inner faces of the shell cross there.
    Averaging the normal field (not the surface) spreads the turn over a few cells
    and removes the crossing.  The centre surface itself is unchanged.
    """
    n = [[cb.normal_at(-1.0 + 2.0 * i / NU, j / NV) for j in range(NV + 1)]
         for i in range(NU + 1)]
    for _ in range(NORMAL_PASSES):
        m = [[None] * (NV + 1) for _ in range(NU + 1)]
        for i in range(NU + 1):
            for j in range(NV + 1):
                acc = Vector((0.0, 0.0, 0.0))
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        a, b = i + di, j + dj
                        if 0 <= a <= NU and 0 <= b <= NV:
                            acc += n[a][b]
                acc.normalize()
                if acc.y > 0.0:          # keep the outward (-Y) orientation
                    acc = -acc
                m[i][j] = acc
        n = m
    return n


NORMALS = None


def grid_point(i, j):
    """(outer, inner) positions of grid node (i, j), pivot-relative."""
    global NORMALS
    key = (i, j)
    if key not in _pts:
        if NORMALS is None:
            NORMALS = smoothed_normals()
        u = -1.0 + 2.0 * i / NU
        v = j / NV
        p = cb.surface(u, v) - PIVOT_VEC
        n = NORMALS[i][j]
        _pts[key] = (p + n * (THICK * 0.5), p - n * (THICK * 0.5))
    return _pts[key]


def build_shell(cells, name):
    """Closed shell from a set of (i, j) cells.  Returns (verts, faces, is_wall, rows)."""
    cells = set(cells)
    idx = {}
    verts, rows = [], []

    def vid(side, i, j):
        k = (side, i, j)
        if k not in idx:
            outer, inner = grid_point(i, j)
            idx[k] = len(verts)
            verts.append(tuple(outer if side == 0 else inner))
            rows.append(j / NV)
        return idx[k]

    faces, is_wall = [], []
    for (i, j) in sorted(cells):
        a, b = vid(0, i, j), vid(0, i + 1, j)
        c, d = vid(0, i + 1, j + 1), vid(0, i, j + 1)
        faces.append((a, b, c, d))
        is_wall.append(False)
        a, b = vid(1, i, j), vid(1, i + 1, j)
        c, d = vid(1, i + 1, j + 1), vid(1, i, j + 1)
        faces.append((a, d, c, b))
        is_wall.append(False)

        # four sides: (neighbour cell, outer edge start, outer edge end)
        sides = [
            ((i, j - 1), (i, j), (i + 1, j)),
            ((i, j + 1), (i + 1, j + 1), (i, j + 1)),
            ((i - 1, j), (i, j + 1), (i, j)),
            ((i + 1, j), (i + 1, j), (i + 1, j + 1)),
        ]
        for nb, p, q in sides:
            if nb in cells:
                continue
            pa, qa = vid(0, *p), vid(0, *q)
            pi, qi = vid(1, *p), vid(1, *q)
            faces.append((pa, qa, qi, pi))
            is_wall.append(True)

    return verts, faces, is_wall, rows


def make_object(name, verts, faces, is_wall, mat_outer, mat_edge, collection):
    me = bpy.data.meshes.new(name + "_mesh")
    bm = bmesh.new()
    bverts = [bm.verts.new(v) for v in verts]
    bm.verts.ensure_lookup_table()
    for f in faces:
        bm.faces.new([bverts[k] for k in f])
    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for fi, face in enumerate(bm.faces):
        face.material_index = 1 if is_wall[fi] else 0
        face.smooth = not is_wall[fi]
    bm.to_mesh(me)
    bm.free()
    me.update()
    me.materials.append(mat_outer)
    me.materials.append(mat_edge)
    obj = bpy.data.objects.new(name, me)
    collection.objects.link(obj)
    return obj


def add_vertex_groups(obj, verts_v):
    """verts_v: list of the v (row/NV) of each vertex, in the object's order."""
    body = obj.vertex_groups.new(name="Cape_Body")
    hem = obj.vertex_groups.new(name="Cape_Hem")
    yoke = obj.vertex_groups.new(name="Cape_Yoke")
    for k, v in enumerate(verts_v):
        if v <= 0.2:
            yoke.add([k], 1.0, 'REPLACE')
        elif v >= 0.85:
            hem.add([k], 1.0, 'REPLACE')
        else:
            body.add([k], 1.0, 'REPLACE')


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    col = bpy.data.collections[COLLECTION]
    for name in [OLD_CAPE, UPPER_NAME] + PANEL_NAMES:
        if name in bpy.data.objects:
            if name != OLD_CAPE:
                raise RuntimeError(f"{name} already exists in the source checkpoint")
    if OLD_CAPE not in bpy.data.objects:
        raise RuntimeError(f"{OLD_CAPE} missing from the Prompt 13 checkpoint")

    pivot = bpy.data.objects[PIVOT_NAME]
    old = bpy.data.objects[OLD_CAPE]
    old_mesh = old.data
    old_mat = old.material_slots[0].material

    # remove the Prompt 13 single shell (its geometry is re-derived below)
    bpy.data.objects.remove(old, do_unlink=True)
    bpy.data.meshes.remove(old_mesh)

    mat_outer = old_mat
    mat_outer.use_backface_culling = False
    mat_edge = bpy.data.materials.new(MAT_EDGE)
    mat_edge.use_nodes = True
    bsdf = mat_edge.node_tree.nodes.get("Principled BSDF")
    colour = (0.12, 0.012, 0.022, 1.0)
    bsdf.inputs["Base Color"].default_value = colour
    bsdf.inputs["Roughness"].default_value = 0.82
    bsdf.inputs["Metallic"].default_value = 0.0
    mat_edge.diffuse_color = colour
    mat_edge.use_backface_culling = False

    # assign every cell to exactly one owner
    owners = {"upper": [], 0: [], 1: [], 2: [], 3: [], 4: []}
    for i in range(NU):
        for j in range(NV):
            o = owner(i, j)
            if o is not None:
                owners[o].append((i, j))

    report = []
    upper = None
    upper_cells = owners["upper"]
    specs = [(UPPER_NAME, upper_cells, "cape_upper")] + \
            [(PANEL_NAMES[k], owners[k], "cape_panel") for k in range(5)]

    for name, cells, part in specs:
        verts, faces, is_wall, rows = build_shell(cells, name)
        obj = make_object(name, verts, faces, is_wall, mat_outer, mat_edge, col)
        # same convention as Prompt 13: mesh coordinates are pivot-relative and
        # the parent inverse stays identity, so the pivot supplies the placement
        obj.parent = pivot
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.location = (0.0, 0.0, 0.0)
        add_vertex_groups(obj, rows)
        obj["wsk_part"] = part
        obj["wsk_prompt"] = PROMPT
        if part == "cape_panel":
            k = PANEL_NAMES.index(name)
            obj["wsk_panel_index"] = k + 1
            obj["wsk_note"] = "separate lower panel hung from the seam; closed shell"
        else:
            obj["wsk_note"] = "upper cape: shoulders to the seam; closed shell with two long tears"
        report.append((name, len(verts), len(faces), len(cells)))
        if name == UPPER_NAME:
            upper = obj

    # the pivot stays the cape's parent; its location is unchanged
    pivot["wsk_part"] = "cape_pivot"
    pivot["wsk_prompt"] = PROMPT

    txt = bpy.data.texts.get("WSK_Cape_Panels_Notes.txt") or \
        bpy.data.texts.new("WSK_Cape_Panels_Notes.txt")
    txt.from_string(NOTES)

    bpy.context.view_layer.update()
    for r in report:
        print("BUILT", r[0], "verts", r[1], "faces", r[2], "cells", r[3])
    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print("SAVED", DST)


if __name__ == "__main__":
    main()
