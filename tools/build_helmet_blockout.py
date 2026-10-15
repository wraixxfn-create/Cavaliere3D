"""Prompt 4 - helmet base and head silhouette for the "Wildshift Knight".

Opens `Wildshift_Knight_03_BaseBody.blend`, builds the helmet foundation and the
crown blockout around the existing head blank, and saves
`Wildshift_Knight_04_HelmetBlockout.blend`.  Nothing that already exists in the
file (body, proportion guide, retired blockout, cameras, lights) is modified.

What is built
-------------
Collection `Helmet`                              (moves with the head)
    WSK_Helmet_Root_01            empty on the neck joint (guide WSK_Joint_Neck)
    WSK_Helmet_Shell_01        enclosed skull: ogival dome, cheek guards, nape
    WSK_Helmet_Faceplate_01    narrow recessed face plate, near black
    WSK_Helmet_Crest_01        centre crest: chin -> brow -> blade tip
    WSK_Helmet_NeckGuard_01    gorget on the neck/trapezius (NOT parented to
                               the head: it belongs to the torso)
Collection `Crown` (child of `Helmet`)
    WSK_Helmet_CrownBand_01    circlet round the brow - carries the halo mount
    WSK_Helmet_CrownHalo_01    full ring behind the head (frames it from the
                               front, whole ring + spine from behind)
    WSK_Helmet_CrownSpine_01   vertical diameter of the ring (rear centre line)
    WSK_Helmet_CrownMount_01   bracket: back of the band -> spine
    WSK_Helmet_CrownSpike_*    nine broad radial spikes, children of the halo,
                               sweeping back more the lower they sit

How it is built
---------------
* Shell, face plate and gorget are authored as a +X HALF surface in world space
  (identity transform, like the Prompt 2/3 objects) and keep three live
  modifiers - Mirror (X, clip, merge), Solidify (wall thickness) and
  Subdivision Surface - so they stay a few hundred vertices to edit.
* The shell is lofted from horizontal sections (half-width a, front extent f,
  back extent b, centre cy, superellipse exponents) read from SHELL_TABLE
  below; above OGIVE_Z0 the half-width follows a two-centred arch.  The face opening is a slot cut out of the front columns; the
  column positions are solved per ring so the slot edge is one clean edge loop
  exactly on the designed opening outline.
* The gorget is shrink-fitted: every vertex is a ray hit on the base body's
  neck/trapezius pushed out along the body normal by a fixed clearance.
* The crown band is fitted the same way to the evaluated (subdivided) shell.
* Crown pieces have meaningful pivots: the halo pivots on its own centre and
  carries the spikes as children, each spike pivots on its base with local +Z
  along the spike, so a spike's length is just its local Z scale.

Run:  tools/bl.sh tools/build_helmet_blockout.py
"""
import math
import os

import bpy          # noqa: F401  (must be imported first: sets module paths)
import bmesh        # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_03_BaseBody.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_04_HelmetBlockout.blend")
BODY = "WSK_Body_Base_01"
PROMPT = "Prompt 4 - helmet base and head silhouette (blockout)"

# --------------------------------------------------------------------------
# PARAMETERS.  [guide] = carried over from the approved Prompt 2 proportion
# sheet, [body] = forced by the Prompt 3 head blank, [new] = decided here.
# --------------------------------------------------------------------------
HEAD_PIVOT = Vector((0.0, 0.0, 1.780))   # [guide] WSK_Joint_Neck

MIRROR_MERGE = 0.0005
SHELL_THICK = 0.005        # [new] wall incl. liner stand-off is the clearance
FACE_THICK = 0.004
GORGET_THICK = 0.004

# Shell sections (z, a, f, b, cy, nf, nb):  a = half width (X), f / b = extent
# in front of / behind cy (Y), nf / nb = superellipse exponents (2 = ellipse,
# >2 boxier).  Below the brow the front columns are the face slot, so `f` there
# is the imaginary surface the cheek guards belong to.
Z_APEX = 1.998             # [guide] helmet dome top 2.00
OGIVE_Z0 = 1.845           # widest point; above it the front view is a
OGIVE_A0 = 0.098           #   two-centred (gothic) arch closing on Z_APEX


def ogive_a(z):
    """Half width of the front-view gothic arch: two circular arcs that meet at
    the apex at ~140 deg, i.e. a pointed - not round - dome."""
    h = Z_APEX - OGIVE_Z0
    r = (OGIVE_A0 ** 2 + h ** 2) / (2.0 * OGIVE_A0)
    xc = OGIVE_A0 - r
    return max(0.0, xc + math.sqrt(max(r * r - (z - OGIVE_Z0) ** 2, 0.0)))


SHELL_TABLE = [
    # z      a       f      b      cy      nf    nb
    (1.740, 0.0880, 0.1180, 0.097, 0.010, 2.20, 2.30),
    (1.760, 0.0903, 0.1200, 0.099, 0.010, 2.20, 2.30),
    (1.780, 0.0915, 0.1220, 0.101, 0.010, 2.20, 2.30),
    (1.800, 0.0936, 0.1240, 0.103, 0.010, 2.20, 2.30),
    (1.820, 0.0957, 0.1255, 0.105, 0.0095, 2.20, 2.30),
    (1.845, 0.0980, 0.126, 0.106, 0.0086, 2.20, 2.30),
    (1.860, None,   0.126, 0.106, 0.0080, 2.20, 2.30),
    (1.875, None,   0.124, 0.105, 0.0070, 2.18, 2.28),
    (1.890, None,   0.118, 0.104, 0.0050, 2.14, 2.24),
    (1.910, None,   0.109, 0.100, 0.0030, 2.10, 2.18),
    (1.930, None,   0.098, 0.093, 0.0010, 2.06, 2.12),
    (1.950, None,   0.084, 0.082, -0.001, 2.03, 2.06),
    (1.965, None,   0.071, 0.070, -0.002, 2.00, 2.02),
    (1.977, None,   0.057, 0.057, -0.003, 2.00, 2.00),
    (1.986, None,   0.043, 0.044, -0.004, 2.00, 2.00),
    (1.992, None,   0.030, 0.031, -0.004, 2.00, 2.00),
    (1.9965, None,  0.016, 0.017, -0.004, 2.00, 2.00),
    (Z_APEX, None,  0.0,   0.0,   -0.004, 2.00, 2.00),
]
SHELL_K = 24               # columns per half ring (front centre -> back centre)
SLOT_J = 4                 # columns 0..3 below the brow are the face slot
RIM_FRONT = 1.763          # [new] cheek-guard front corners at the slot
RIM_SIDE = 1.763           # [new] jaw line (overlaps the gorget top)
RIM_BACK = 1.776           # [new] nape
BROW_Z = 1.875             # [new] top of the face slot at its corners ...
BROW_DIP = 0.011           #   ... dipping 11 mm at the centre: a hard brow V
ROWS_LOW = 9               # rows rim -> brow
ROWS_HIGH = 12             # rows brow -> last ring under the apex
# face slot half width (z, w)  -> narrow, kite shaped, widest under the brow
SLOT_TABLE = [(1.755, 0.0225), (1.763, 0.024), (1.780, 0.0275), (1.800, 0.032),
              (1.820, 0.0355), (1.840, 0.0385), (1.860, 0.040), (1.880, 0.0405)]

# Face plate: half width hw(z) and keel position y_keel(z); the surface is a
# shallow V (keel) set back ~13 mm behind the slot rim.
FACE_TABLE = [
    # z      hw      y_keel
    (1.740, 0.0000, 0.1135),
    (1.744, 0.0070, 0.1150),
    (1.750, 0.0150, 0.1165),
    (1.758, 0.0235, 0.1180),
    (1.768, 0.0305, 0.1195),
    (1.782, 0.0370, 0.1210),
    (1.800, 0.0430, 0.1215),
    (1.820, 0.0470, 0.1215),
    (1.840, 0.0500, 0.1212),
    (1.858, 0.0518, 0.1200),
    (1.872, 0.0525, 0.1168),
    (1.884, 0.0520, 0.1120),
    (1.895, 0.0510, 0.1070),
]
FACE_K_V, FACE_E_V, FACE_Q_V = 0.24, 0.003, 1.0
FACE_ROWS, FACE_COLS = 18, 6

# Crest (centre fin): (z, y_front).  Root follows the face plate keel, then the
# brow / forehead; above Z_CREST_FREE it stands free as a blade tip.
CREST_FRONT = [(1.740, 0.1140), (1.744, 0.1220), (1.751, 0.1287),
               (1.762, 0.1340), (1.780, 0.1372), (1.810, 0.1388),
               (1.840, 0.1393), (1.862, 0.1395), (1.878, 0.1393),
               (1.895, 0.1382), (1.915, 0.1345), (1.935, 0.1262),
               (1.955, 0.1155), (1.972, 0.1058), (1.988, 0.0970),
               (2.004, 0.0890)]
CREST_HALF_T = 0.0036
Z_CREST_FREE = 1.962

# Gorget: top edge (front, side, back) and lower rows; clearance to the body.
GORGET_TOP = (1.755, 1.766, 1.778)  # front / side / back top edge
# front half of the top edge as (deg from the front, z): high behind the chin so
# no throat shows under the cheek guards, low across the diagonals where a
# tilted + turned helmet rim comes down (see the rig sweep in the verify report)
GORGET_TOP_FRONT = [(0.0, 1.755), (25.0, 1.754), (50.0, 1.7505), (70.0, 1.7565),
                    (90.0, 1.766)]
GORGET_BOTTOM = (1.708, 1.679, 1.679)  # front / side / back: short at the front so
                           #   the chin can drop in front of the chest
GORGET_CLEAR_TOP = 0.006   # clearance to the body at the top edge (8 mm below):
                           #   leaves the tilting helmet rim room above it
GORGET_RINGS = 9
GORGET_CLEAR = 0.008
GORGET_K = 20

# Crown band (circlet): centre height front -> back, height, thickness, gap.
BAND_Z = (1.896, 1.914)
BAND_H = 0.020
BAND_T = 0.0065
BAND_GAP = 0.0015
BAND_SEG = 64

# Halo: a full ring BEHIND the head (front view: frames the upper head, lower
# half hidden behind it; back view: whole ring + central spine).  Its plane is
# tilted back a little; the spikes lean further back the further they are from
# the top, so the side view shows the reference's backward fan.
HALO_R = 0.125             # centreline radius -> outer width 0.268 (guide 0.28)
HALO_TUBE = 0.0095
HALO_C = Vector((0.0, -0.140, 1.920))
HALO_TILT_DEG = 8.0        # top leans back
SPIKE_CONE_DEG = 70.0      # backward lean out of the ring plane at |angle| =
SPIKE_CONE_EXP = 1.1       #   120 deg, eased: 0 at the top, ~51 deg at +-90
SPINE_HALF = (0.0066, 0.0046)   # rear spine section half width / depth
MOUNT_BAND = (0.016, 0.0115)    # mount half width / half height at the band
MOUNT_SPINE = (0.0095, 0.0085)  # ... and at the spine

# Spikes: (suffix, angle from the top of the halo in deg (+ = character right),
#          length from the halo centreline, base half width, base half depth)
SPIKES = [
    ("C",  0.0,    0.145, 0.0118, 0.0070),
    ("R1", 30.0,   0.105, 0.0108, 0.0065),
    ("L1", -30.0,  0.105, 0.0108, 0.0065),
    ("R2", 60.0,   0.098, 0.0102, 0.0062),
    ("L2", -60.0,  0.098, 0.0102, 0.0062),
    ("R3", 90.0,   0.088, 0.0098, 0.0060),
    ("L3", -90.0,  0.088, 0.0098, 0.0060),
    ("R4", 120.0,  0.085, 0.0092, 0.0057),
    ("L4", -120.0, 0.085, 0.0092, 0.0057),
]

RIDGE_CREASE = 0.75        # subsurf crease on the dome's centre line (0 = off):
RIDGE_Z_FRONT = 1.925      #   a medial ridge from above the brow band over the
RIDGE_Z_BACK = 1.930       #   apex to the back, so the ogive reads in 3/4 views

SHARP_ANGLE_DEG = 40.0

# --------------------------------------------------------------------------
# small maths helpers
# --------------------------------------------------------------------------


def pchip(xs, ys, flat_ends=False):
    """Shape-preserving cubic (PCHIP) through the samples - no overshoot, so a
    profile table can never bulge past its own control values.  flat_ends gives
    zero end slopes (for curves that meet a mirror plane or a flat blend)."""
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)
    h = np.diff(xs)
    d = np.diff(ys) / h
    m = np.zeros_like(ys)
    for k in range(1, len(xs) - 1):
        if d[k - 1] * d[k] > 0.0:
            w1, w2 = 2.0 * h[k] + h[k - 1], h[k] + 2.0 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / d[k - 1] + w2 / d[k])
    m[0], m[-1] = (0.0, 0.0) if flat_ends else (d[0], d[-1])

    def f(x):
        x = min(max(float(x), xs[0]), xs[-1])
        k = int(min(max(np.searchsorted(xs, x) - 1, 0), len(xs) - 2))
        t = (x - xs[k]) / h[k]
        t2, t3 = t * t, t * t * t
        return float((2 * t3 - 3 * t2 + 1) * ys[k] + (t3 - 2 * t2 + t) * h[k] * m[k]
                     + (-2 * t3 + 3 * t2) * ys[k + 1] + (t3 - t2) * h[k] * m[k + 1])
    return f


def smoothstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3.0 - 2.0 * x)


# --------------------------------------------------------------------------
# profiles
# --------------------------------------------------------------------------
_zs = [r[0] for r in SHELL_TABLE]
_a_low = [(r[0], r[1]) for r in SHELL_TABLE if r[1] is not None]
_A_LOW = pchip([p[0] for p in _a_low], [p[1] for p in _a_low])
_F = pchip(_zs, [r[2] for r in SHELL_TABLE])
_B = pchip(_zs, [r[3] for r in SHELL_TABLE])
_CY = pchip(_zs, [r[4] for r in SHELL_TABLE])
_NF = pchip(_zs, [r[5] for r in SHELL_TABLE])
_NB = pchip(_zs, [r[6] for r in SHELL_TABLE])
_SLOT = pchip([p[0] for p in SLOT_TABLE], [p[1] for p in SLOT_TABLE])
_FACE_HW = pchip([r[0] for r in FACE_TABLE], [r[1] for r in FACE_TABLE])
_FACE_KEEL = pchip([r[0] for r in FACE_TABLE], [r[2] for r in FACE_TABLE])
_CREST_FRONT = pchip([p[0] for p in CREST_FRONT], [p[1] for p in CREST_FRONT])


def shell_params(z):
    a = _A_LOW(z) if z <= OGIVE_Z0 else ogive_a(z)
    return a, _F(z), _B(z), _CY(z), _NF(z), _NB(z)


def shell_point(z, t):
    """Shell outer surface at height z, section parameter t (0 = front
    centre, pi/2 = side, pi = back centre) on the +X half."""
    a, f, b, cy, nf, nb = shell_params(z)
    s, c = math.sin(t), math.cos(t)
    if c >= 0.0:
        e = 2.0 / nf
        x, y = a * abs(s) ** e, cy + f * c ** e
    else:
        e = 2.0 / nb
        x, y = a * abs(s) ** e, cy - b * (-c) ** e
    if t <= 1e-9 or t >= math.pi - 1e-9:
        x = 0.0
    return Vector((x, y, z))


def slot_t(z):
    """Section parameter of the face-slot edge at height z."""
    a, _f, _b, _cy, nf, _nb = shell_params(z)
    w = _SLOT(z)
    return math.asin(min((w / a) ** (nf / 2.0), 0.999))


def face_point(x, z):
    k = FACE_K_V * x
    y = (_FACE_KEEL(z) - (math.sqrt(k * k + FACE_E_V ** 2) - FACE_E_V)
         - FACE_Q_V * x * x)
    return Vector((x, y, z))


# --------------------------------------------------------------------------
# scene helpers
# --------------------------------------------------------------------------


def new_mesh_object(name, verts, faces, collection, material, smooth=True,
                    sharp_angle=None):
    me = bpy.data.meshes.new(name + "_mesh")
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate(verbose=False)
    me.update()
    me.polygons.foreach_set("use_smooth", [smooth] * len(me.polygons))
    if sharp_angle is not None:
        me.set_sharp_from_angle(angle=math.radians(sharp_angle))
    obj = bpy.data.objects.new(name, me)
    collection.objects.link(obj)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def add_symmetric_stack(obj, thickness, offset, levels=1, render_levels=2):
    m = obj.modifiers.new("WSK_Mirror", "MIRROR")
    m.use_axis[0] = True
    m.use_clip = True
    m.use_mirror_merge = True
    m.merge_threshold = MIRROR_MERGE
    s = obj.modifiers.new("WSK_Solidify", "SOLIDIFY")
    s.thickness = thickness
    s.offset = offset
    s.use_even_offset = True
    s.use_quality_normals = True
    s.use_rim = True
    d = obj.modifiers.new("WSK_Subsurf", "SUBSURF")
    d.levels = levels
    d.render_levels = render_levels
    d.quality = 3
    return obj


def make_material(name, rgb, metallic, roughness, edge=0.35):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    # dim the white grazing-angle (F82) sheen so "dark" metal stays dark
    bsdf.inputs["Specular Tint"].default_value = (edge, edge, edge * 1.04, 1.0)
    mat.diffuse_color = (*rgb, 1.0)          # solid-mode viewport colour
    mat.metallic = metallic
    mat.roughness = roughness
    return mat


def evaluated_world(obj):
    """World-space vertices / polygons of an object after its modifiers."""
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    eo = obj.evaluated_get(deps)
    me = eo.to_mesh()
    mw = eo.matrix_world.copy()
    verts = [mw @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    eo.to_mesh_clear()
    return verts, polys


def bvh_of(obj):
    v, p = evaluated_world(obj)
    return BVHTree.FromPolygons(v, p)


def set_props(obj, part, confidence, **extra):
    obj["wsk_part"] = part
    obj["wsk_confidence"] = confidence
    obj["wsk_prompt"] = PROMPT
    for k, v in extra.items():
        obj[k] = v


def parent_keep_world(child, parent):
    """Parent without moving: the child's world matrix is unchanged."""
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


# --------------------------------------------------------------------------
# 1. shell
# --------------------------------------------------------------------------


def build_shell(col, mat):
    ts_rim = slot_t(RIM_FRONT)
    ts_brow = slot_t(BROW_Z)

    def z_rim(t):
        # front corner -> jaw (side) -> nape, smooth and monotone
        if t <= math.pi / 2:
            u = (t - ts_rim) / (math.pi / 2 - ts_rim)
            return RIM_FRONT + (RIM_SIDE - RIM_FRONT) * smoothstep(u)
        u = (t - math.pi / 2) / (math.pi / 2)
        return RIM_SIDE + (RIM_BACK - RIM_SIDE) * smoothstep(u)

    def z_brow(t):
        if t < ts_brow:
            return BROW_Z - BROW_DIP * (1.0 - t / ts_brow) ** 2
        return BROW_Z

    n_rows = ROWS_LOW + ROWS_HIGH + 1          # ring rows (pole extra)
    i_b = ROWS_LOW

    def row_z(i, t):
        if i <= i_b:
            s = i / i_b
            return z_rim(t) + (z_brow(t) - z_rim(t)) * s
        # evenly spaced dome rows: the last ring stays ~1 cm under the apex so
        # the pole fan is not a ring of slivers (which the solidify folds)
        w = (i - i_b) / (ROWS_HIGH + 1)
        zb = z_brow(t)
        return zb + (Z_APEX - zb) * w

    def row_slot_t(i):
        if i <= i_b:
            t = ts_rim
            for _ in range(6):                     # fixed point: z depends on t
                t = slot_t(row_z(i, t))
            return t
        rho = ((i - i_b) / ROWS_HIGH) ** 2
        return ts_brow * (1.0 - rho) + (math.pi * SLOT_J / SHELL_K) * rho

    def col_t(i, j):
        ts = row_slot_t(i)
        if j <= SLOT_J:
            return ts * j / SLOT_J
        u = (j - SLOT_J) / (SHELL_K - SLOT_J)
        return ts + (math.pi - ts) * u

    verts, faces, vid = [], [], {}

    def v(i, j):
        if (i, j) not in vid:
            t = col_t(i, j)
            p = shell_point(row_z(i, t), t)
            vid[(i, j)] = len(verts)
            verts.append(p)
        return vid[(i, j)]

    for i in range(n_rows - 1):
        for j in range(SHELL_K):
            if i < i_b and j < SLOT_J:
                continue                            # the face slot
            # winding gives outward normals (checked in verify)
            faces.append((v(i, j), v(i + 1, j), v(i + 1, j + 1), v(i, j + 1)))
    apex = len(verts)
    verts.append(Vector((0.0, _CY(Z_APEX), Z_APEX)))
    top = n_rows - 1
    for j in range(SHELL_K):
        faces.append((v(top, j), apex, v(top, j + 1)))

    obj = new_mesh_object("WSK_Helmet_Shell_01", verts, faces, col, mat)
    if RIDGE_CREASE > 0.0:
        ridge = set()
        for i in range(n_rows - 1):
            for j, zmin in ((0, RIDGE_Z_FRONT), (SHELL_K, RIDGE_Z_BACK)):
                if (i, j) in vid and (i + 1, j) in vid and verts[vid[(i, j)]].z >= zmin:
                    ridge.add(frozenset((vid[(i, j)], vid[(i + 1, j)])))
        for j in (0, SHELL_K):
            ridge.add(frozenset((vid[(top, j)], apex)))
        me = obj.data
        attr = (me.attributes.get("crease_edge")
                or me.attributes.new("crease_edge", "FLOAT", "EDGE"))
        attr.data.foreach_set("value", [RIDGE_CREASE if frozenset(e.vertices) in ridge
                                        else 0.0 for e in me.edges])
    add_symmetric_stack(obj, SHELL_THICK, -1.0)
    sol = obj.modifiers["WSK_Solidify"]
    sol.edge_crease_rim = 0.0
    set_props(obj, "helmet shell: ogival dome, cheek guards, nape, face slot",
              "blockout - large forms only, guide-matched envelope",
              wsk_wall_m=SHELL_THICK, wsk_modifiers="Mirror X > Solidify > Subsurf")
    return obj


# --------------------------------------------------------------------------
# 2. face plate
# --------------------------------------------------------------------------


def build_faceplate(col, mat):
    z_top, z_chin = FACE_TABLE[-1][0], FACE_TABLE[0][0]
    rows = []
    for r in range(FACE_ROWS):
        s = r / FACE_ROWS
        # denser towards the chin, where the outline turns fastest
        z = z_top + (z_chin - z_top) * (1.0 - (1.0 - s) ** 1.35)
        rows.append(z)
    verts, faces = [], []
    grid = []
    for z in rows:
        hw = _FACE_HW(z)
        ids = []
        for k in range(FACE_COLS + 1):
            x = hw * k / FACE_COLS
            ids.append(len(verts))
            verts.append(face_point(x, z))
        grid.append(ids)
    chin = len(verts)
    verts.append(face_point(0.0, z_chin))
    for r in range(FACE_ROWS - 1):
        for k in range(FACE_COLS):
            a, b = grid[r][k], grid[r][k + 1]
            c, d = grid[r + 1][k + 1], grid[r + 1][k]
            faces.append((a, b, c, d))       # +Y facing (outward)
    last = grid[-1]
    for k in range(FACE_COLS):
        faces.append((last[k], last[k + 1], chin))
    obj = new_mesh_object("WSK_Helmet_Faceplate_01", verts, faces, col, mat)
    add_symmetric_stack(obj, FACE_THICK, -1.0)
    set_props(obj, "recessed face plate: shallow keel, no facial features, "
              "no eye openings", "blockout",
              wsk_recess_note="sits ~13 mm behind the slot rim of the shell")
    return obj


# --------------------------------------------------------------------------
# 3. crest
# --------------------------------------------------------------------------


def build_crest(col, mat, shell_bvh):
    """Thin centre fin, triangular section (back face embedded)."""
    z0, z1 = CREST_FRONT[0][0], CREST_FRONT[-1][0]
    n = 68
    zs = [z0 + (z1 - z0) * i / n for i in range(n + 1)]

    def surface_y(z):
        if z <= BROW_Z - BROW_DIP:                 # on the face plate keel
            return _FACE_KEEL(z)
        hit = shell_bvh.ray_cast(Vector((0.0, 0.40, z)), Vector((0.0, -1.0, 0.0)), 1.0)
        if hit[0] is None or hit[0].y < 0.06:       # slipped under the brow
            return _FACE_KEEL(z)
        if z <= BROW_Z + 0.006:
            # brow transition: stay sunk in the face plate as well, so the fin
            # bridges plate and brow (no see-through window at the slot top -
            # the render-level subdivision rounds the brow V upwards)
            return min(hit[0].y, _FACE_KEEL(z))
        return hit[0].y

    y_free0 = surface_y(Z_CREST_FREE) - 0.002
    verts, faces = [], []
    sec = []
    for i, z in enumerate(zs):
        yf = _CREST_FRONT(z)
        if i == 0 or i == n:
            sec.append([len(verts)])
            verts.append(Vector((0.0, yf, z)))
            continue
        if z <= Z_CREST_FREE:
            # back edge sunk 2 mm into plate / shell all the way up; the crown
            # band simply runs into the fin (allowed contact), so there is no
            # step in the back edge that could open a see-through window
            yr = surface_y(z) - 0.002
        else:
            u = (z - Z_CREST_FREE) / (z1 - Z_CREST_FREE)
            yr = y_free0 + (yf - 0.004 - y_free0) * u
        yr = min(yr, yf - 0.003)
        t = CREST_HALF_T * min(1.0, (z - z0) / 0.010, (z1 - z) / 0.030 + 0.25)
        ids = [len(verts), len(verts) + 1, len(verts) + 2]
        verts += [Vector((-t, yr, z)), Vector((0.0, yf, z)), Vector((t, yr, z))]
        sec.append(ids)
    for i in range(n):
        a, b = sec[i], sec[i + 1]
        if len(a) == 1:
            for k in range(3):
                faces.append((a[0], b[(k + 1) % 3], b[k]))
        elif len(b) == 1:
            for k in range(3):
                faces.append((a[k], a[(k + 1) % 3], b[0]))
        else:
            for k in range(3):
                faces.append((a[k], a[(k + 1) % 3], b[(k + 1) % 3], b[k]))
    obj = new_mesh_object("WSK_Helmet_Crest_01", verts, faces, col, mat,
                          smooth=True, sharp_angle=SHARP_ANGLE_DEG)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    set_props(obj, "centre crest: chin point -> face keel -> brow -> blade tip",
              "blockout", wsk_tip_z=round(z1, 3))
    return obj


# --------------------------------------------------------------------------
# 4. gorget / neck guard
# --------------------------------------------------------------------------


def build_neck_guard(col, mat, body_bvh):
    def cy_body(z):
        return float(np.interp(z, [1.668, 1.690, 1.725, 1.755, 1.780],
                               [0.002, 0.004, 0.008, 0.010, 0.014]))

    top_front = pchip([math.radians(a) for a, _z in GORGET_TOP_FRONT],
                      [z for _a, z in GORGET_TOP_FRONT], flat_ends=True)

    def z_top(th):
        _f, s, b = GORGET_TOP
        if th <= math.pi / 2:
            return float(top_front(th))
        return s + (b - s) * smoothstep((th - math.pi / 2) / (math.pi / 2))

    def z_bot(th):
        f, s, b = GORGET_BOTTOM
        if th <= math.pi / 2:
            return f + (s - f) * smoothstep(min(th / (0.55 * math.pi), 1.0))
        return s + (b - s) * smoothstep((th - math.pi / 2) / (math.pi / 2))

    rows = GORGET_RINGS
    verts, faces, grid = [], [], []
    for r in range(rows):
        ids = []
        for j in range(GORGET_K + 1):
            th = math.pi * j / GORGET_K
            zt, zb = z_top(th), z_bot(th)
            # rows blend from the (sloping) top edge to the bottom edge; the
            # exponent packs rows into the trapezius flare
            u = (r / (rows - 1)) ** 0.8
            z = zt + (zb - zt) * u
            clear = GORGET_CLEAR_TOP + (GORGET_CLEAR - GORGET_CLEAR_TOP) * u
            d = Vector((math.sin(th), math.cos(th), 0.0))
            o = Vector((0.0, cy_body(z), z))
            hit = body_bvh.ray_cast(o, d, 0.5)
            p, nrm = hit[0], hit[1]
            if nrm.dot(d) < 0:
                nrm = -nrm
            q = p + nrm * clear
            if j in (0, GORGET_K):
                q.x = 0.0
            ids.append(len(verts))
            verts.append(q)
        grid.append(ids)
    for r in range(rows - 1):
        for j in range(GORGET_K):
            faces.append((grid[r][j], grid[r][j + 1], grid[r + 1][j + 1], grid[r + 1][j]))
    obj = new_mesh_object("WSK_Helmet_NeckGuard_01", verts, faces, col, mat)
    # inner surface authored -> solidify outward (+1)
    add_symmetric_stack(obj, GORGET_THICK, 1.0)
    set_props(obj, "gorget / neck guard: closes the neck between helmet rim and "
              "shoulders; rides on the torso, not on the head",
              "blockout - shrink-fitted to the base body, 6 mm (top) to 8 mm clearance",
              wsk_clearance_m=GORGET_CLEAR, wsk_clearance_top_m=GORGET_CLEAR_TOP)
    return obj


# --------------------------------------------------------------------------
# 5. crown
# --------------------------------------------------------------------------


def band_centre_z(th):
    return BAND_Z[0] + (BAND_Z[1] - BAND_Z[0]) * 0.5 * (1.0 - math.cos(th))


def shell_hit(shell_bvh, th, z):
    """Outer shell surface along a horizontal ray at polar angle th."""
    d = Vector((math.sin(th), math.cos(th), 0.0))
    o = Vector((0.0, 0.0, z)) + d * 0.40
    hit = shell_bvh.ray_cast(o, -d, 0.60)
    p, n = hit[0], hit[1]
    if n.dot(d) < 0:
        n = -n
    return p, n


def build_band(col, mat, shell_bvh):
    # ray-fit the +X half (0..pi) and mirror it exactly: the evaluated shell's
    # triangulation is not mirror-symmetric, so fitting both halves would leave
    # sub-millimetre left/right differences
    half = BAND_SEG // 2
    ring_pts = []
    for k in range(half + 1):
        th = math.pi * k / half
        zc = band_centre_z(th)
        pts = []
        for (zz, depth) in ((zc - BAND_H / 2, BAND_GAP), (zc + BAND_H / 2, BAND_GAP),
                            (zc + BAND_H / 2, BAND_GAP + BAND_T),
                            (zc - BAND_H / 2, BAND_GAP + BAND_T)):
            p, n = shell_hit(shell_bvh, th, zz)
            nh = Vector((n.x, n.y, 0.0)).normalized()
            q = p + nh * depth
            q.z = zz
            if k in (0, half):
                q.x = 0.0
            pts.append(q)
        ring_pts.append(pts)
    for k in range(half + 1, BAND_SEG):
        ring_pts.append([Vector((-q.x, q.y, q.z)) for q in ring_pts[BAND_SEG - k]])
    verts, faces, rings = [], [], []
    for pts in ring_pts:
        rings.append(list(range(len(verts), len(verts) + 4)))
        verts += pts
    for k in range(BAND_SEG):
        a, b = rings[k], rings[(k + 1) % BAND_SEG]
        for m in range(4):
            faces.append((a[m], a[(m + 1) % 4], b[(m + 1) % 4], b[m]))
    obj = new_mesh_object("WSK_Helmet_CrownBand_01", verts, faces, col, mat,
                          smooth=True, sharp_angle=SHARP_ANGLE_DEG)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    set_props(obj, "crown band / circlet: sits on the shell round the brow and "
              "carries the halo", "blockout - thorns deliberately omitted",
              wsk_gap_to_shell_m=BAND_GAP)
    return obj


def band_outer_point(shell_bvh, th):
    zc = band_centre_z(th)
    p, n = shell_hit(shell_bvh, th, zc)
    nh = Vector((n.x, n.y, 0.0)).normalized()
    q = p + nh * (BAND_GAP + BAND_T)
    q.z = zc
    if abs(math.sin(th)) < 1e-9:          # centre line: exactly on X = 0
        q.x, nh.x = 0.0, 0.0
        nh.normalize()
    return q, nh


def sweep_tube(path, radii, up_hint, sides=10, cap=True):
    """Tube along `path` (list of Vector) with elliptical sections
    radii[i] = (r_u, r_v); frames are parallel-transported so nothing twists."""
    n = len(path)
    tangents = []
    for i in range(n):
        a = path[max(i - 1, 0)]
        b = path[min(i + 1, n - 1)]
        tangents.append((b - a).normalized())
    u = up_hint - tangents[0] * up_hint.dot(tangents[0])
    u.normalize()
    frames = []
    for i in range(n):
        t = tangents[i]
        u = u - t * u.dot(t)
        u.normalize()
        frames.append((u.copy(), t.cross(u)))
    verts, faces, rings = [], [], []
    for i in range(n):
        uu, vv = frames[i]
        ru, rv = radii[i]
        ids = []
        for k in range(sides):
            a = 2.0 * math.pi * k / sides
            ids.append(len(verts))
            verts.append(path[i] + uu * (ru * math.cos(a)) + vv * (rv * math.sin(a)))
        rings.append(ids)
    for i in range(n - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(sides):
            faces.append((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]))
    if cap:
        for idx, ring in ((0, rings[0]), (n - 1, rings[-1])):
            c = len(verts)
            verts.append(path[idx].copy())
            for k in range(sides):
                faces.append((ring[k], ring[(k + 1) % sides], c))
    return verts, faces


def recalc_normals(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()


def halo_matrix():
    return Matrix.Translation(HALO_C) @ Matrix.Rotation(math.radians(HALO_TILT_DEG), 4, "X")


def spike_cone(ang_deg):
    """Backward lean of a spike out of the halo plane: the top spike stands in
    the plane, the side spikes sweep back - a shallow cone, which is what turns
    the edge-on halo into the reference's backward fan in the side view."""
    return SPIKE_CONE_DEG * (abs(ang_deg) / 120.0) ** SPIKE_CONE_EXP


def build_halo(col, mat):
    """Closed ring in the halo's local XZ plane (local +Y = ring normal)."""
    seg, sides = 56, 10
    verts, faces = [], []
    for i in range(seg):
        p = 2.0 * math.pi * i / seg
        c = Vector((HALO_R * math.sin(p), 0.0, HALO_R * math.cos(p)))
        radial = Vector((math.sin(p), 0.0, math.cos(p)))
        for k in range(sides):
            a = 2.0 * math.pi * k / sides
            verts.append(c + radial * (HALO_TUBE * math.cos(a))
                         + Vector((0.0, 1.0, 0.0)) * (HALO_TUBE * math.sin(a)))
    for i in range(seg):
        for k in range(sides):
            a0, a1 = i * sides + k, i * sides + (k + 1) % sides
            b0, b1 = ((i + 1) % seg) * sides + k, ((i + 1) % seg) * sides + (k + 1) % sides
            faces.append((a0, a1, b1, b0))
    obj = new_mesh_object("WSK_Helmet_CrownHalo_01", verts, faces, col, mat)
    obj.matrix_world = halo_matrix()
    recalc_normals(obj)
    set_props(obj, "halo ring behind the head; parent of the spine, the mount "
              "and the nine spikes", "blockout - smooth ring, thorny detail deferred",
              wsk_radius_m=HALO_R, wsk_tilt_deg=HALO_TILT_DEG,
              wsk_note="pivot = halo centre; rotate X to change the tilt, scale "
                       "uniformly to resize the whole halo with its spikes")
    return obj


def build_spine(col, mat, halo):
    """Vertical diameter of the halo (local Z), ends sunk into the ring."""
    n = 14
    zs = np.linspace(-HALO_R + 0.002, HALO_R - 0.002, n)
    path = [Vector((0.0, 0.0, float(z))) for z in zs]
    radii = [SPINE_HALF] * n
    verts, faces = sweep_tube(path, radii, Vector((1.0, 0.0, 0.0)), sides=8)
    obj = new_mesh_object("WSK_Helmet_CrownSpine_01", verts, faces, col, mat)
    recalc_normals(obj)
    obj.parent = halo
    obj.matrix_parent_inverse = Matrix.Identity(4)
    set_props(obj, "halo spine: vertical diameter of the ring, takes the mount "
              "and lines up with the top spike (rear view centre line)", "blockout")
    return obj


def build_mount(col, mat, shell_bvh, halo):
    """Tapered bracket: back of the crown band -> halo spine (3rd support)."""
    q, nh = band_outer_point(shell_bvh, math.pi)
    p0 = q - nh * 0.003                              # sink into the band
    mw = halo_matrix()
    inv = mw.inverted()
    # spine (local X = 0, Y = 0) at the band height
    loc = inv @ p0
    p1 = mw @ Vector((0.0, 0.0, loc.z))
    x = Vector((1.0, 0.0, 0.0))
    z = Vector((0.0, 0.0, 1.0))
    verts = []
    for (c, (w, h)) in ((p0, MOUNT_BAND), (p1, MOUNT_SPINE)):
        verts += [c - x * w - z * h, c + x * w - z * h, c + x * w + z * h, c - x * w + z * h]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    verts = [inv @ v for v in verts]
    obj = new_mesh_object("WSK_Helmet_CrownMount_01", verts, faces, col, mat, smooth=False)
    recalc_normals(obj)
    obj.parent = halo
    obj.matrix_parent_inverse = Matrix.Identity(4)
    set_props(obj, "crown mount: bracket from the back of the band to the halo "
              "spine - what carries the halo", "blockout",
              wsk_length_m=round((p1 - p0).length, 4))
    return obj


def build_spike(name, col, mat, length, w0, d0):
    """Rhombic thorn: base at the origin, tip at +Z * length."""
    stations = [0.0, 0.30, 0.62, 1.0]
    verts, faces, rings = [], [], []
    for s in stations[:-1]:
        k = (1.0 - s) ** 1.25
        z = s * length
        ids = []
        for (x, y) in ((w0 * k, 0.0), (0.0, d0 * k), (-w0 * k, 0.0), (0.0, -d0 * k)):
            ids.append(len(verts))
            verts.append(Vector((x, y, z)))
        rings.append(ids)
    tip = len(verts)
    verts.append(Vector((0.0, 0.0, length)))
    faces.append(tuple(reversed(rings[0])))
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(4):
            faces.append((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
    for k in range(4):
        faces.append((rings[-1][k], rings[-1][(k + 1) % 4], tip))
    obj = new_mesh_object(name, verts, faces, col, mat, smooth=False)
    recalc_normals(obj)
    return obj


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    helmet_col = bpy.data.collections["Helmet"]
    crown_col = bpy.data.collections.get("Crown")
    if crown_col is None:
        crown_col = bpy.data.collections.new("Crown")
        helmet_col.children.link(crown_col)

    body = bpy.data.objects[BODY]
    body_bvh = bvh_of(body)

    m_steel = make_material("MAT_Helmet_DarkSteel_01", (0.022, 0.022, 0.025), 0.80, 0.36)
    m_void = make_material("MAT_Helmet_FaceVoid_01", (0.004, 0.004, 0.005), 0.0, 0.95,
                           edge=1.0)
    m_iron = make_material("MAT_Helmet_CrownIron_01", (0.042, 0.039, 0.035), 0.85, 0.56,
                           edge=0.32)
    for m, role in ((m_steel, "helmet shell, crest and gorget - dark blackened steel"),
                    (m_void, "recessed face plate - near-black, matte, no emission"),
                    (m_iron, "crown band, halo, spine, mount and spikes - dark iron")):
        m["wsk_role"] = role
        m["wsk_placeholder"] = True

    # root on the neck joint: rotate it to preview a head turn (no rig)
    root = bpy.data.objects.new("WSK_Helmet_Root_01", None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.12
    root.location = HEAD_PIVOT
    helmet_col.objects.link(root)
    bpy.context.view_layer.update()
    set_props(root, "helmet assembly root on the guide neck joint (head pivot)",
              "guide marker WSK_Joint_Neck", wsk_note="not a bone - no rig exists")

    shell = build_shell(helmet_col, m_steel)
    face = build_faceplate(helmet_col, m_void)
    shell_bvh = bvh_of(shell)
    band = build_band(crown_col, m_iron, shell_bvh)
    crest = build_crest(helmet_col, m_steel, shell_bvh)
    gorget = build_neck_guard(helmet_col, m_steel, body_bvh)

    halo = build_halo(crown_col, m_iron)
    spine = build_spine(crown_col, m_iron, halo)
    mount = build_mount(crown_col, m_iron, shell_bvh, halo)

    spikes = []
    for suffix, ang, length, w0, d0 in SPIKES:
        sp = build_spike(f"WSK_Helmet_CrownSpike_{suffix}_01", crown_col, m_iron,
                         length, w0, d0)
        a = math.radians(ang)
        cone = math.radians(spike_cone(ang))
        sp.parent = halo
        sp.matrix_parent_inverse = Matrix.Identity(4)
        sp.location = (HALO_R * math.sin(a), 0.0, HALO_R * math.cos(a))
        sp.rotation_mode = "XYZ"
        sp.rotation_euler = (cone, a, 0.0)      # radial in the ring, then lean back
        side = "top centre" if suffix == "C" else (
            "character right" if suffix.startswith("R") else "character left")
        set_props(sp, f"crown spike, {side}: radial on the halo", "blockout",
                  wsk_angle_deg=ang, wsk_length_m=length,
                  wsk_backward_lean_deg=round(spike_cone(ang), 1),
                  wsk_note="pivot = base on the halo centreline, local +Z = spike "
                           "axis; scale Z to change the length")
        spikes.append(sp)

    # hierarchy: everything that moves with the head hangs off the root
    bpy.context.view_layer.update()
    for o in (shell, face, crest, band):
        parent_keep_world(o, root)
    halo_world = halo.matrix_world.copy()
    halo.parent = root
    halo.matrix_parent_inverse = Matrix.Identity(4)
    halo.matrix_basis = root.matrix_world.inverted() @ halo_world
    bpy.context.view_layer.update()

    # collections: visible, renderable
    for c in (helmet_col, crown_col):
        c.hide_viewport = False
        c.hide_render = False
    helmet_col["wsk_status"] = "Prompt 4 helmet blockout (shell, face plate, crest, gorget)"
    crown_col["wsk_status"] = "Prompt 4 crown blockout (band, halo, spine, mount, 9 spikes)"
    body.hide_viewport = False
    body.hide_render = False

    write_text_blocks(shell, face, crest, gorget, band, halo, [spine, mount], spikes)
    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print("SAVED", DST)


# --------------------------------------------------------------------------
# text blocks
# --------------------------------------------------------------------------
NOTES = """WILDSHIFT KNIGHT - HELMET BLOCKOUT NOTES (Prompt 4)
===================================================

Scope: head and helmet foundation only.  Large forms, simple dark placeholder
materials, no engraving, no gems, no glowing eyes, no small thorns, no rig.

OBJECTS (all names follow WSK_<Category>_<Descriptor>_<Index>)
  Helmet collection
    WSK_Helmet_Root_01        empty on the guide neck joint (0, 0, 1.780).
                              Parent of everything that turns with the head.
                              Rotate it to preview a head turn - it is not a bone.
    WSK_Helmet_Shell_01       enclosed skull: ogival (two-centred) dome with a
                              soft medial ridge, cheek guards, nape; a narrow
                              face slot with a hard brow V is cut in the front.
    WSK_Helmet_Faceplate_01   recessed near-black plate behind the slot, one
                              shallow keel ending in the pointed chin.  No eyes,
                              nose, mouth or eye openings - not a face.
    WSK_Helmet_Crest_01       centre fin: chin point, face keel, over the brow
                              and the band, free blade tip in front of the dome.
    WSK_Helmet_NeckGuard_01   gorget on the neck / trapezius.  NOT parented to
                              the head root: it belongs to the torso, so the head
                              turns inside it.  Short at the front (chin room).
  Crown collection (child of Helmet) - every element its own object
    WSK_Helmet_CrownBand_01   circlet round the brow, 1.5 mm off the shell.
    WSK_Helmet_CrownHalo_01   full ring BEHIND the head, plane tilted back
                              {tilt:.0f} deg.  From the front it frames the upper head
                              (its lower half hides behind the helmet); from
                              behind the whole ring and the spine read.  Pivot =
                              ring centre; spine, mount and spikes are children.
    WSK_Helmet_CrownSpine_01  vertical diameter of the ring, lines up with the
                              top spike (the rear centre line of the reference).
    WSK_Helmet_CrownMount_01  tapered bracket from the back of the band to the
                              spine: what visibly carries the halo.
    WSK_Helmet_CrownSpike_C/R1/L1/R2/L2/R3/L3/R4/L4_01
                              nine broad radial spikes at 0, +-30, +-60, +-90,
                              +-120 deg; length {lengths}.
                              Each leans back out of the ring plane by
                              {leans} so the side view
                              shows a fan sweeping back like the reference.
                              Pivot = spike base on the ring centre line, local
                              +Z = spike axis: scale local Z to change a length.

MODIFIERS (live, so the blockout stays editable)
  Shell / face plate / gorget: half mesh + Mirror (X, clip, merge 0.5 mm) >
  Solidify (shell {shell_t:.0f} mm inward, face plate {face_t:.0f} mm inward, gorget
  {gorget_t:.0f} mm outward) > Subdivision Surface (viewport 1, render 2).
  Edit the +X half; the -X half follows.  The shell's dome centre line carries
  a 0.75 subdivision crease (medial ridge).  Crest and crown: plain meshes.

KEY NUMBERS (world metres, Z up, character faces +Y)
{numbers}

MATERIALS (placeholders, Principled BSDF only, no textures, no emission)
  MAT_Helmet_DarkSteel_01   shell, crest, gorget
  MAT_Helmet_FaceVoid_01    face plate (near black, matte, non-metallic)
  MAT_Helmet_CrownIron_01   band, halo, spine, mount, spikes

DESIGN DECISIONS / DEVIATIONS FROM THE PROMPT 2 GUIDE
  * Helmet width {shell_w:.3f} m (guide 0.19, +{w_pct:.1f} %): the Prompt 3 skull blank
    is 0.172 m wide; 5 mm clearance + 5 mm wall each side need 0.192 m.  The
    reference's hooded head reads slimmer - the hood (Cape step) will hang close
    at the jaw.
  * Crown: halo outer width {ring_w:.3f} m (guide 0.28), spike span +-{spike_x:.3f} m
    (guide +-0.18) and the +-30 deg tips at Z {r1_top:.3f} (guide 2.11) sit on the guide.
    The top-centre spike is deliberately taller (tip Z {spike_top:.3f}): in the
    reference it is the tallest element and continues the crest line.  The
    proportion sheet marks crown spikes "guide only / not measured".  Scale
    WSK_Helmet_CrownSpike_C_01 in local Z to about 0.47 to put it on 2.11 m.
  * The lower spikes sweep back rather than down (lowest tips Z {low:.3f}, guide
    frame 1.76), which keeps them off the pauldrons that come later.
  * The hood/cowl of the reference is cloth and belongs to the Cape step.  The
    halo stands ~2 cm off the back of the helmet to leave room for it.

RIG READINESS (no rig was built - numbers in analysis/verify/verify_helmet_report.txt)
  * Head assembly hangs off one root on the neck joint; the gorget does not.
  * The helmet stops at the chin (Z {chin:.3f}) and projects to Y {front:.3f} only.
  * Head-bone and neck-bone poses are swept numerically against the torso and
    the gorget (clearance + first-contact angles in the report).
"""


def write_text_blocks(shell, face, crest, gorget, band, halo, braces, spikes):
    def ext(objs):
        pts = []
        for o in objs:
            v, _p = evaluated_world(o)
            pts += v
        arr = np.array([p[:] for p in pts])
        return arr.min(0), arr.max(0)

    smin, smax = ext([shell])
    hmin, hmax = ext([shell, face, crest])
    cmin, cmax = ext([band, halo] + braces + spikes)
    gmin, gmax = ext([gorget])
    numbers = "\n".join([
        f"  shell outer           X {smin[0]:+.3f}..{smax[0]:+.3f}  Y {smin[1]:+.3f}.."
        f"{smax[1]:+.3f}  Z {smin[2]:.3f}..{smax[2]:.3f}",
        f"  helmet incl. face     X {hmin[0]:+.3f}..{hmax[0]:+.3f}  Y {hmin[1]:+.3f}.."
        f"{hmax[1]:+.3f}  Z {hmin[2]:.3f}..{hmax[2]:.3f}",
        f"  crown (all pieces)    X {cmin[0]:+.3f}..{cmax[0]:+.3f}  Y {cmin[1]:+.3f}.."
        f"{cmax[1]:+.3f}  Z {cmin[2]:.3f}..{cmax[2]:.3f}",
        f"  gorget                X {gmin[0]:+.3f}..{gmax[0]:+.3f}  Y {gmin[1]:+.3f}.."
        f"{gmax[1]:+.3f}  Z {gmin[2]:.3f}..{gmax[2]:.3f}",
        f"  halo                  centre {tuple(round(c, 3) for c in HALO_C)}, "
        f"radius {HALO_R:.3f}, tube {HALO_TUBE:.4f}, tilted back {HALO_TILT_DEG:.0f} deg",
        f"  face slot             brow Z {BROW_Z:.3f} (V-dip {BROW_DIP * 1000:.0f} mm), "
        f"half width {SLOT_TABLE[0][1]:.3f}..{max(w for _z, w in SLOT_TABLE):.3f}",
    ])
    txt = bpy.data.texts.get("WSK_Helmet_Blockout_Notes.txt")
    if txt is None:
        txt = bpy.data.texts.new("WSK_Helmet_Blockout_Notes.txt")
    txt.clear()
    by = {suffix: (ang, length) for suffix, ang, length, _w, _d in SPIKES}
    lengths = ", ".join(f"{k} {by[k][1]:.3f}" for k in ("C", "R1", "R2", "R3", "R4"))
    leans = ", ".join(f"{spike_cone(by[k][0]):.0f}" for k in ("C", "R1", "R2", "R3", "R4"))
    spike_objs = {o.name: o for o in spikes}

    def top_of(name):
        return ext([spike_objs[name]])[1][2]

    lows = min(ext([o])[0][2] for o in spikes)
    sx = max(max(abs(ext([o])[0][0]), abs(ext([o])[1][0])) for o in spikes)
    halo_min, halo_max = ext([halo])
    txt.write(NOTES.format(
        tilt=HALO_TILT_DEG,
        lengths=f"(m from the ring centre line: {lengths} - left side mirrors)",
        leans=f"{leans} deg (top to bottom)",
        shell_t=SHELL_THICK * 1000, face_t=FACE_THICK * 1000,
        gorget_t=GORGET_THICK * 1000, numbers=numbers,
        shell_w=smax[0] - smin[0], w_pct=((smax[0] - smin[0]) / 0.19 - 1) * 100,
        ring_w=halo_max[0] - halo_min[0], spike_x=sx,
        r1_top=top_of("WSK_Helmet_CrownSpike_R1_01"),
        spike_top=top_of("WSK_Helmet_CrownSpike_C_01"), low=lows,
        chin=hmin[2], front=hmax[1]))

    notes = bpy.data.texts.get("WSK_Project_Notes.txt")
    if notes is None:
        notes = bpy.data.texts.new("WSK_Project_Notes.txt")
    notes.write(PROJECT_NOTES)


PROJECT_NOTES = """
Prompt 4 - Helmet base and head silhouette (Wildshift_Knight_04_HelmetBlockout.blend)
===================================================================================
Only the Helmet collection (and its new child collection Crown) was filled.
Body, proportion guide (Reference), retired blockout, cameras and lights are
unchanged; the base body stays visible as the scale reference for the head.

  Helmet -> WSK_Helmet_Root_01, _Shell_01, _Faceplate_01, _Crest_01, _NeckGuard_01
  Crown  -> WSK_Helmet_CrownBand_01, _CrownHalo_01, _CrownSpine_01, _CrownMount_01,
            WSK_Helmet_CrownSpike_{C,R1,L1,R2,L2,R3,L3,R4,L4}_01

Helmet rules:
  - shell, face plate and gorget: +X half in world space (identity transform)
    with live Mirror > Solidify > Subdivision modifiers;
  - everything that turns with the head is parented to WSK_Helmet_Root_01 on the
    guide neck joint; the gorget is not (it belongs to the torso);
  - spine, mount and spikes are children of the halo; spikes pivot at their
    base with local +Z along the spike;
  - placeholder materials MAT_Helmet_DarkSteel_01 / _FaceVoid_01 /
    MAT_Helmet_CrownIron_01: Principled only, no textures, no emission;
  - no armature, no bones, no shape keys, no facial rig.

Correction to the Prompt 3 section above: the delivered body's crown is at
Z 1.910 m (as the README and WSK_BaseBody_Topology_Notes.txt say), not 1.956 m.
See 'WSK_Helmet_Blockout_Notes.txt' for the helmet design notes.
"""


if __name__ == "__main__":
    main()
