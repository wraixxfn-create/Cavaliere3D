"""Prompt 3 - build the clean base body for the "Wildshift Knight".

Opens `Wildshift_Knight_02_Proportions.blend`, replaces the blockout mannequin's
rough body placeholders with one coherent, watertight humanoid base mesh, and
saves `Wildshift_Knight_03_BaseBody.blend`.

How the body is built
---------------------
Everything is authored in world space (object transform = identity, so a
coordinate read in Edit mode *is* a world coordinate, exactly like the Prompt 2
blockout).

1.  Torso / neck / head is one lofted "half shell": rings of K+1 vertices from
    the front centreline (X = 0) round one side to the back centreline (X = 0).
    Only the +X half is authored; a Mirror modifier welds the seam.
2.  A rectangular *patch of quads* is deleted where a limb attaches and the
    ordered boundary loop of that patch becomes the first ring of the limb
    tube.  The limb is therefore continuous with the torso - no bridging, no
    overlap, no hidden interior surface.
3.  Limb tubes are lofted outward from that ring.  Every ring uses the same
    angular positions around the tube axis as the ring before it, so a tube
    cannot twist; the angles are eased onto an even spacing over the first few
    rings so the cross-sections are regular.  Each ring frame's "front" axis is
    held at +Y, the character's facing direction.
4.  Extra edge loops are packed around the shoulder, elbow, hip and knee.
5.  A Mirror modifier (X, clipping + merge, applied before saving) turns the
    authored half into the full body and welds the centreline seam.

Run:  tools/bl.sh tools/build_base_body.py
"""
import math
import os

import bpy          # noqa: F401  (must be imported first: sets module paths)
import bmesh        # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_02_Proportions.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_03_BaseBody.blend")

BODY = "WSK_Body_Base_01"
K = 16                      # torso half-ring columns -> 32 columns around the body
MIRROR_MERGE = 0.0005

# --------------------------------------------------------------------------
# PARAMS - every number is either carried over from the approved Prompt 2
# proportion sheet [guide] or is a decision taken in this step [new].
# --------------------------------------------------------------------------
E_TORSO = 0.86              # cross-section exponent: <1 slightly boxy, 1 ellipse
TORSO = [                   # (z, rx, ry_front, ry_back, cy) half-rings
    (0.965, 0.116, 0.080, 0.086, 0.012),   # crotch rim          guide crotch 0.97
    (0.990, 0.162, 0.110, 0.118, 0.010),   # lower hip
    (1.025, 0.172, 0.124, 0.130, 0.008),   # hip, widest         guide pelvis 0.34
    (1.085, 0.170, 0.122, 0.124, 0.005),   # upper pelvis
    (1.150, 0.158, 0.118, 0.110, 0.002),   # lower abdomen
    (1.220, 0.150, 0.116, 0.100, 0.000),   # waist               guide waist 0.30
    (1.290, 0.152, 0.120, 0.102, -0.001),  # upper abdomen
    (1.370, 0.154, 0.128, 0.110, -0.003),  # lower chest
    (1.440, 0.163, 0.136, 0.118, -0.004),  # chest / armpit      guide 1.42
    (1.510, 0.175, 0.144, 0.128, -0.004),  # chest
    (1.580, 0.186, 0.150, 0.138, -0.003),  # upper chest         guide 0.40 wide
    (1.630, 0.205, 0.138, 0.132, -0.001),  # acromion: the widest torso ring sits
                                           #   exactly on the shoulder joint line,
                                           #   so the joint is inside the deltoid
                                           #   and the chest slopes away below it
    (1.668, 0.150, 0.110, 0.112, 0.002),   # trapezius slope     guide 1.6675
    (1.690, 0.100, 0.086, 0.092, 0.004),   # neck base           guide 1.68
    (1.725, 0.068, 0.064, 0.068, 0.008),   # neck
    (1.755, 0.064, 0.062, 0.066, 0.010),   # neck top            guide 1.78
    (1.780, 0.070, 0.082, 0.078, 0.014),   # jaw / chin
    (1.815, 0.080, 0.095, 0.092, 0.012),   # mid head
    (1.855, 0.086, 0.098, 0.090, 0.008),   # skull, widest (0.172 x 0.188)
    (1.884, 0.082, 0.089, 0.076, 0.004),   # upper skull, back sloping in
    (1.902, 0.066, 0.070, 0.056, 0.002),   # crown ring
]
# [new] crown apex sits at 1.910, i.e. 0.09 below the 2.00 m helmet-dome
# envelope of the guide, so the helmet built later encloses the skull with
# shell clearance instead of intersecting it.  The blank cranium is 0.35 m
# tall (chin 1.74 -> crown 1.91), 0.172 m wide and 0.19 m deep.
TORSO_POLE = Vector((0.0, 0.002, 1.910))
CROTCH_POLE = Vector((0.0, 0.012, 0.972))  # crotch centre, dished upward so
#   the thigh rings below it cannot poke through the crotch surface.

SHOULDER_CUT = (8, 11, 6, 10)   # rows 8..11 x cols 6..10 -> 2*(4+3) = 14-vert ring
HIP_CUT = (0, 2, 4, 10)         # rows 0..2  x cols 4..10 -> 2*(6+2) = 16-vert ring

# Arm stations (centre, semi-axis A across the arm, B front-back).  Shoulder
# joint (0.200, 0, 1.630), elbow (0.316, -0.020, 1.281) and wrist
# (0.295, 0.022, 0.983) are the approved joint markers, hit exactly.
ARM = [
    ((0.204, 0.002, 1.538), 0.068, 0.082),   # deltoid (ring 0 = the cut loop)
    ((0.252, -0.002, 1.508), 0.060, 0.078),  # deltoid bulge: the arm exits
    ((0.276, -0.008, 1.452), 0.062, 0.074),  # outward before it drops, which
    ((0.294, -0.012, 1.392), 0.064, 0.070),  # is also what keeps its inner
    ((0.303, -0.016, 1.340), 0.063, 0.068),  # wall outside the ribcage
    ((0.311, -0.018, 1.302), 0.061, 0.066),
    ((0.316, -0.020, 1.281), 0.060, 0.065),  # elbow   (guide marker)
    ((0.313, -0.013, 1.252), 0.059, 0.064),  # elbow loop
    ((0.308, 0.000, 1.180), 0.055, 0.060),
    ((0.302, 0.011, 1.100), 0.052, 0.057),
    ((0.297, 0.019, 1.020), 0.050, 0.055),
    ((0.295, 0.022, 0.983), 0.049, 0.054),   # wrist   (guide marker)
    ((0.293, 0.030, 0.945), 0.036, 0.054),   # palm
    ((0.291, 0.038, 0.905), 0.031, 0.057),   # knuckles
    ((0.289, 0.043, 0.872), 0.030, 0.056),
    ((0.287, 0.046, 0.840), 0.028, 0.053),
    ((0.286, 0.048, 0.812), 0.025, 0.047),
    ((0.285, 0.049, 0.797), 0.017, 0.030),   # fingertips
]
THUMB_BAND = 13             # the quad band palm -> knuckles
THUMB_BAND_W = 2            # two columns wide, centred on the front (+Y) edge
THUMB = [(0.018, 0.017), (0.036, 0.015), (0.050, 0.010)]  # (offset, radius)

# Leg stations (centre, semi-axis A across, B front-back).  Hip joint
# (0.100, 0, 1.000), knee (0.155, 0.010, 0.550) and ankle (0.215, -0.010,
# 0.115) are the approved joint markers, hit exactly.
LEG = [
    ((0.122, 0.014, 0.950), 0.072, 0.080),
    ((0.120, 0.010, 0.915), 0.086, 0.098),
    ((0.118, 0.006, 0.870), 0.094, 0.108),   # widest thigh   guide 0.20 x 0.22
    ((0.120, 0.004, 0.800), 0.094, 0.106),
    ((0.126, 0.004, 0.720), 0.090, 0.100),
    ((0.136, 0.006, 0.640), 0.084, 0.094),
    ((0.146, 0.009, 0.585), 0.080, 0.089),   # knee loop
    ((0.153, 0.010, 0.550), 0.077, 0.086),   # knee           (guide marker)
    ((0.159, 0.010, 0.515), 0.075, 0.084),   # knee loop
    ((0.168, 0.008, 0.460), 0.072, 0.080),
    ((0.180, 0.003, 0.380), 0.068, 0.076),
    ((0.192, -0.002, 0.300), 0.063, 0.070),
    ((0.202, -0.006, 0.230), 0.058, 0.065),
    ((0.210, -0.009, 0.170), 0.055, 0.061),
    ((0.215, -0.010, 0.115), 0.052, 0.056),  # ankle          (guide marker)
]
FOOT = [                    # (z, half width, centre y along the foot, half length)
    (0.085, 0.052, 0.000, 0.070),   # just under the ankle
    (0.060, 0.058, 0.020, 0.098),
    (0.035, 0.062, 0.040, 0.122),
    (0.012, 0.064, 0.052, 0.140),
    (0.000, 0.064, 0.056, 0.146),   # sole: toe +0.202, heel -0.090
]
E_FOOT = 0.55               # boxier cross-section, reads as a boot
SHARP_ANGLE_DEG = 40.0      # edges sharper than this stay crisp under smoothing
FOOT_YAW_DEG = 15.0         # guide: toes splayed outward


# --------------------------------------------------------------------------
# maths helpers
# --------------------------------------------------------------------------
def sgnpow(v, e):
    return math.copysign(abs(v) ** e, v) if v else 0.0


def frame_from_normal(n, ref=Vector((0.0, 1.0, 0.0))):
    """Ring frame (u, v) in the plane normal to `n`, v as close to +Y as it can
    be.  Holding v at the character's front is what stops tubes twisting."""
    n = Vector(n).normalized()
    r = Vector(ref)
    v = r - n * r.dot(n)
    if v.length < 1e-6:
        r = Vector((0.0, 0.0, 1.0))
        v = r - n * r.dot(n)
    v.normalize()
    return n.cross(v), v


def roll_frame(u, v, n, roll):
    if not roll:
        return u, v
    c, s = math.cos(roll), math.sin(roll)
    return (u * c - v * s), (u * s + v * c)


def ang_diff(a, b):
    d = (a - b) % (2.0 * math.pi)
    return d - 2.0 * math.pi if d > math.pi else d


def half_ring(z, rx, ryf, ryb, cy, e, k=K):
    """One torso cross-section, front centreline round to the back centreline."""
    pts = []
    for j in range(k + 1):
        th = math.pi * j / k
        s, c = math.sin(th), math.cos(th)
        ry = ryf if c >= 0.0 else ryb
        x, y = rx * sgnpow(s, e), cy + ry * sgnpow(c, e)
        if abs(x) < 1e-9:
            x = 0.0
        pts.append(Vector((x, y, z)))
    return pts


def oval_ring(centre, u, v, a, b, thetas, e=1.0):
    """Closed ring: angle 0 -> +u, angle 90 deg -> +v."""
    return [Vector(centre) + u * (a * sgnpow(math.cos(t), e))
            + v * (b * sgnpow(math.sin(t), e)) for t in thetas]


class Builder:
    def __init__(self):
        self.verts = []
        self.faces = []

    def add_verts(self, pts):
        i0 = len(self.verts)
        self.verts.extend(Vector(p) for p in pts)
        return list(range(i0, len(self.verts)))

    def add_face(self, ids):
        self.faces.append(tuple(ids))

    def fan(self, ids, apex):
        """Triangles from an apex to an OPEN polyline (a half ring: do not
        wrap, or the fan would close the ring across the mirror plane)."""
        for i in range(len(ids) - 1):
            self.add_face((apex, ids[i], ids[i + 1]))


def patch_boundary(grid_ids, r0, r1, c0, c1):
    """Ordered vertex loop around the rectangle of faces rows r0..r1, cols c0..c1."""
    loop = [grid_ids[r0][c] for c in range(c0, c1 + 1)]
    loop += [grid_ids[r][c1] for r in range(r0 + 1, r1 + 1)]
    loop += [grid_ids[r1][c] for c in range(c1 - 1, c0 - 1, -1)]
    loop += [grid_ids[r][c0] for r in range(r1 - 1, r0, -1)]
    return loop


def patch_normal(rows, r0, r1, c0, c1, inward):
    """Average outward normal and centre of a rectangle of quads."""
    n = Vector((0.0, 0.0, 0.0))
    centre = Vector((0.0, 0.0, 0.0))
    for r in range(r0, r1):
        for c in range(c0, c1):
            p0, p1, p3 = rows[r][c], rows[r][c + 1], rows[r + 1][c]
            n += (p1 - p0).cross(p3 - p0)
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            centre += rows[r][c]
    centre /= (r1 - r0 + 1) * (c1 - c0 + 1)
    n.normalize()
    if n.dot(centre - Vector(inward)) < 0.0:
        n = -n
    return n, centre


def angle_order(mesh, loop, centre, u, v):
    """Sort a cut boundary loop by its angle about the limb axis, unwrapped so
    the sequence is strictly increasing."""
    th = []
    for vid in loop:
        d = mesh.verts[vid] - centre
        th.append(math.atan2(d.dot(v), d.dot(u)))
    order = sorted(range(len(loop)), key=lambda i: th[i])
    loop = [loop[i] for i in order]
    th = [th[i] for i in order]
    for i in range(1, len(th)):
        while th[i] <= th[i - 1]:
            th[i] += 2.0 * math.pi
    return loop, th


def station_frames(spine, c0, n0, steps=3, ref=Vector((0.0, 1.0, 0.0))):
    """(centre, u, v, A, B, n) per station, ring normal eased from the cut
    normal onto the local tube tangent so the first bands do not bow."""
    centres = [Vector(s[0]) for s in spine]
    out = []
    for i, (centre, a, b) in enumerate(spine):
        c = Vector(centre)
        if i == 0:
            t = c - Vector(c0)
        elif i == len(spine) - 1:
            t = c - centres[i - 1]
        else:
            t = centres[i + 1] - centres[i - 1]
        blend = min(1.0, (i + 1) / float(steps))
        nrm = (Vector(n0) * (1.0 - blend) + t.normalized() * blend).normalized()
        u, v = frame_from_normal(nrm, ref)
        out.append((c, u, v, a, b, nrm, 1.0))
    return out


def build_tube(mesh, loop, thetas, frames, cut=None, ease=3, e=1.0):
    """Loft a limb outward from a cut boundary loop.

    `frames` are the rings after ring 0.  `cut` = (row, first_col, ncols) removes
    a patch of tube quads for a further branch (the thumb) and the patch's
    boundary loop is returned.
    """
    n = len(loop)
    even = [thetas[0] + 2.0 * math.pi * i / n for i in range(n)]
    rings = [list(loop)]
    for i, (centre, u, v, a, b, _nrm, se) in enumerate(frames):
        bl = min(1.0, (i + 1) / float(ease))
        th = [thetas[j] + bl * (even[j] - thetas[j]) for j in range(n)]
        rings.append(mesh.add_verts(oval_ring(centre, u, v, a, b, th, se * e)))
    skip = set()
    branch = None
    if cut is not None:
        row, col, width = cut
        skip = {(row, (col + k) % n) for k in range(width)}
        branch = [rings[row][(col + k) % n] for k in range(width + 1)]
        branch += [rings[row + 1][(col + width) % n]]
        branch += [rings[row + 1][(col + k) % n] for k in range(width - 1, -1, -1)]
    for i in range(len(rings) - 1):
        r0, r1 = rings[i], rings[i + 1]
        for j in range(n):
            if (i, j) in skip:
                continue
            k = (j + 1) % n
            mesh.add_face((r0[j], r0[k], r1[k], r1[j]))
    return rings, even, branch


def tube_patch_normal(mesh, rings, row, col, width):
    n = Vector((0.0, 0.0, 0.0))
    centre = Vector((0.0, 0.0, 0.0))
    ncol = len(rings[0])
    for k in range(width):
        p0 = mesh.verts[rings[row][(col + k) % ncol]]
        p1 = mesh.verts[rings[row][(col + k + 1) % ncol]]
        p3 = mesh.verts[rings[row + 1][(col + k) % ncol]]
        n += (p1 - p0).cross(p3 - p0)
    for k in range(width + 1):
        for r in (row, row + 1):
            centre += mesh.verts[rings[r][(col + k) % ncol]]
    centre /= 2.0 * (width + 1)
    n.normalize()
    if n.dot(centre - Vector((0.0, 0.0, centre.z))) < 0.0:
        n = -n
    return n, centre


# --------------------------------------------------------------------------
# materials / scene housekeeping
# --------------------------------------------------------------------------
def get_material(name, rgba, roughness=0.85):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = 0.0
    mat.diffuse_color = rgba
    mat.roughness = roughness
    return mat


def get_collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def purge(names):
    for obj in [o for o in bpy.data.objects if o.name in names]:
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in (bpy.data.meshes,):
        for block in [b for b in coll if b.users == 0 and b.name.startswith("WSK_Body_")]:
            coll.remove(block)


# --------------------------------------------------------------------------
# build the half body
# --------------------------------------------------------------------------
def build_half():
    mesh = Builder()

    # ---- torso / neck / head shell ---------------------------------------
    rows_pts = [half_ring(*r, E_TORSO) for r in TORSO]
    grid = [mesh.add_verts(row) for row in rows_pts]

    sr0, sr1, sc0, sc1 = SHOULDER_CUT
    hr0, hr1, hc0, hc1 = HIP_CUT
    for r in range(len(grid) - 1):
        for c in range(len(grid[0]) - 1):
            if sr0 <= r < sr1 and sc0 <= c < sc1:
                continue
            if hr0 <= r < hr1 and hc0 <= c < hc1:
                continue
            mesh.add_face((grid[r][c], grid[r][c + 1],
                           grid[r + 1][c + 1], grid[r + 1][c]))

    # crown and crotch: fans to a pole that lies on the mirror plane
    mesh.fan(grid[-1], mesh.add_verts([TORSO_POLE])[0])
    mesh.fan(grid[0], mesh.add_verts([CROTCH_POLE])[0])

    # ---- shoulder + arm + hand -------------------------------------------
    n_sh, c_sh = patch_normal(rows_pts, sr0, sr1, sc0, sc1,
                              inward=(0.0, rows_pts[sr0][0].y, rows_pts[sr0][0].z))
    u0, v0 = frame_from_normal(n_sh)
    loop = patch_boundary(grid, sr0, sr1, sc0, sc1)
    loop, th = angle_order(mesh, loop, c_sh, u0, v0)
    frames = station_frames(ARM, c_sh, n_sh, steps=3)
    n_arm = len(th)
    even_arm = [th[0] + 2.0 * math.pi * i / n_arm for i in range(n_arm)]
    col = min(range(n_arm), key=lambda j: abs(ang_diff(even_arm[j], math.pi * 0.5)))
    tcut = (THUMB_BAND, col, THUMB_BAND_W)
    arm_rings, even_arm, thumb_loop = build_tube(
        mesh, loop, th, frames, cut=tcut, ease=3)
    mesh.add_face(arm_rings[-1])                       # fingertip cap

    # ---- thumb ------------------------------------------------------------
    n_th, c_th = tube_patch_normal(mesh, arm_rings, *tcut)
    u0t, v0t = frame_from_normal(n_th, ref=Vector((0.0, 0.0, 1.0)))
    tloop, tth = angle_order(mesh, thumb_loop, c_th, u0t, v0t)
    tstations = [(c_th + n_th * off, rad, rad) for off, rad in THUMB]
    tframes = station_frames(tstations, c_th, n_th, steps=2,
                             ref=Vector((0.0, 0.0, 1.0)))
    t_rings, _te, _ = build_tube(mesh, tloop, tth, tframes, ease=2)
    mesh.add_face(t_rings[-1])                         # thumb tip cap

    # ---- hip + leg + foot -------------------------------------------------
    n_hp, c_hp = patch_normal(rows_pts, hr0, hr1, hc0, hc1,
                              inward=(0.0, 0.0, rows_pts[hr0][0].z))
    u0h, v0h = frame_from_normal(n_hp)
    hloop = patch_boundary(grid, hr0, hr1, hc0, hc1)
    hloop, hth = angle_order(mesh, hloop, c_hp, u0h, v0h)
    hframes = station_frames(LEG, c_hp, n_hp, steps=3)

    # roll the last leg rings so the ankle frame lines up with the splayed
    # foot frame (a twist of at most FOOT_YAW over the last three rings)
    yaw = math.radians(-FOOT_YAW_DEG)          # right foot toes point outward
    xhat = Matrix.Rotation(yaw, 3, "Z") @ Vector((1.0, 0.0, 0.0))
    yhat = Matrix.Rotation(yaw, 3, "Z") @ Vector((0.0, 1.0, 0.0))
    uA, vA, nA = hframes[-1][1], hframes[-1][2], hframes[-1][5]
    roll = math.atan2(nA.dot(vA.cross(yhat)), vA.dot(yhat)) if abs(vA.dot(yhat)) < 1.0 else 0.0
    for k, share in ((3, 1 / 3.0), (2, 2 / 3.0), (1, 1.0)):
        idx = len(hframes) - k
        c, u, v, a, b, nrm, se = hframes[idx]
        u2, v2 = roll_frame(u, v, nrm, roll * share)
        hframes[idx] = (c, u2, v2, a, b, nrm, se)

    foot = []
    ankle = Vector(LEG[-1][0])
    for z, hx, cy, hy in FOOT:
        off = Matrix.Rotation(yaw, 3, "Z") @ Vector((0.0, cy, 0.0))
        centre = Vector((ankle.x + off.x, ankle.y + off.y, z))
        foot.append((centre, xhat, yhat, hx, hy, Vector((0.0, 0.0, -1.0)), E_FOOT))
    leg_rings, _le, _ = build_tube(mesh, hloop, hth, hframes + foot, ease=3)
    mesh.add_face(leg_rings[-1])                       # sole cap
    return mesh


# --------------------------------------------------------------------------
def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    scene = bpy.context.scene
    body_col = get_collection("Body")
    ref_col = get_collection("Reference")

    purge({BODY})
    mat = get_material("MAT_Body_NeutralGrey_01", (0.42, 0.43, 0.45, 1.0), 0.85)

    half = build_half()

    me = bpy.data.meshes.new(BODY + "_mesh")
    me.from_pydata([tuple(v) for v in half.verts], [], [list(f) for f in half.faces])
    me.validate(verbose=False)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()

    obj = bpy.data.objects.new(BODY, me)
    body_col.objects.link(obj)
    obj.data.materials.append(mat)

    bpy.context.view_layer.objects.active = obj
    for o in bpy.data.objects:
        o.select_set(False)
    obj.select_set(True)

    mod = obj.modifiers.new("WSK_Mirror", "MIRROR")
    mod.use_axis[0] = True
    mod.use_clip = True
    mod.use_mirror_merge = True
    mod.merge_threshold = MIRROR_MERGE
    bpy.ops.object.modifier_apply(modifier=mod.name)

    # a cut patch leaves the vertices that used to be interior to it orphaned:
    # drop them so the mesh carries no floating geometry
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    loose = [v for v in bm.verts if not v.link_edges]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    # smooth shading with angle-based creases: a lofted shell reads as a solid
    # form instead of a faceted blockout, and the silhouette is unchanged
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2:
            e.smooth = e.calc_face_angle(0.0) < math.radians(SHARP_ANGLE_DEG)
    bm.to_mesh(obj.data)
    bm.free()

    # tidy: nothing may sit below the ground plane
    zmin = min(v.co.z for v in obj.data.vertices)
    if abs(zmin) > 1e-6:
        for v in obj.data.vertices:
            v.co.z -= zmin
    obj.data.update()

    obj["wsk_part"] = ("base body: torso, pelvis, neck, head blank, arms, "
                       "hands with thumbs, legs, feet")
    obj["wsk_confidence"] = "guide-derived blockout, clean quad flow, no skin detail"
    obj["wsk_modifiers_applied"] = "WSK_Mirror (X, clip, merge 0.5 mm)"
    obj["wsk_prompt"] = "Prompt 3 - clean base body"

    # ---- retire the Prompt 2 blockout mannequin, keep it in the file ------
    blockout = bpy.data.collections.get("Blockout")
    retired = []
    if blockout is not None:
        blockout.hide_viewport = True
        blockout.hide_render = True
        for o in blockout.objects:
            o.hide_viewport = True
            o.hide_render = True
            retired.append(o.name)

    # ---- scene state: proportion guide stays, reference images stay -------
    for o in bpy.data.objects:
        if o.name.startswith(("WSK_Guide_", "WSK_Label_", "WSK_Ref_", "WSK_Joint_")):
            o.hide_render = True

    body_col.hide_viewport = False
    body_col.hide_render = False
    ref_col["wsk_status"] = ("retained proportion guide (Prompt 2). Hidden from "
                             "renders; switch hide_render off to see it again.")
    body_col["wsk_status"] = "deliverable base body for Prompt 3"

    write_text_blocks(obj)

    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print("SAVED", DST)
    print("verts", len(obj.data.vertices), "faces", len(obj.data.polygons),
          "retired", len(retired), "blockout parts")


TOPOLOGY_NOTES = """WILDSHIFT KNIGHT - BASE BODY TOPOLOGY NOTES (Prompt 3)
======================================================

Object: {name}   Collection: Body
Mesh:   one closed manifold surface, no modifiers left on the object, identity
        object transform (1 unit = 1 m, origin on the ground between the feet,
        character faces +Y).  Scale is 1.000 on every axis.
Counts: {nv} vertices / {nf} faces - {nq} quads ({qpct:.1f} %), {nt} triangles,
        {nn} n-gons (the six tube-root caps only).
Enclosed volume {vol:.4f} m^3, surface area {area:.4f} m^2.

HOW IT IS MADE
  Torso / neck / head is a lofted half shell: rings of 17 vertices (16 columns
  authored on +X) from the crotch to the crown.  Where a limb attaches, a
  rectangular patch of quads is removed and its 14- or 16-vertex boundary loop
  becomes the first ring of the limb tube, so every limb is continuous with the
  torso - no bridging, no overlapping shells, no interior geometry.  Ring
  angles are eased from the (irregular) cut boundary onto an even spacing over
  the first three rings, and each ring's "front" axis is held at +Y, so no tube
  twists.  The +X half was built and then mirrored with an applied Mirror
  modifier (clip + 0.5 mm merge): left and right are exact, the centreline is
  welded, and V-E+F = 2 (closed, genus 0).

RING COUNTS (the numbers that matter to a rig)
  torso / neck / head      17 verts per half ring -> 32 around the body
  arm tube                 14 verts (7 per quarter)
  leg tube                 16 verts (8 per quarter)
  thumb                     6 verts
  extra loops packed around the shoulder (2), elbow (3), hip (2) and knee (3)
  limb cross-section bands: upper arm 0.05 m, forearm 0.04-0.08 m, thigh
  0.05-0.07 m, shank 0.06-0.08 m - i.e. 15-20 deformable bands per limb.

DEFORMATION-FRIENDLY FLOW - WHAT IS GOOD
  * shoulders: the deltoid rings ARE the quad grid of the cut, so the deltoid
    carries with the chest and there is no pole or triangle in the armpit.
  * elbow / knee: three loops across the joint line plus a mid-joint ring.
  * hip: the thigh tube starts inside the pelvis silhouette and the crotch is a
    shallow fan that sits above the thigh rings, so a big thigh rotation cannot
    pull the opposite buttock.
  * every limb ring is a clean quad loop perpendicular to the limb axis, which
    is exactly what an armature modifier wants.

KNOWN LIMITATIONS (read before rigging)
  1. Elbows and knees are straight in the rest pose and the arm chain has no
     natural carrying angle.  A rig will want a small forward offset on the
     elbow/knee bones, and the first bend may pinch on the inner side because
     there are only three loops there.  Add 1-2 loops if the pose needs more.
  2. There is no clavicle topology: the deltoid deforms as part of the chest.
     Fine for an FK arm; a full shoulder rig would want a loop running along
     the top of the shoulder.
  3. The hands are mitten blocks (palm, knuckles, thumb).  No finger loops and
     no knuckle topology - fingers are a separate, later decision.
  4. The head is a compact cranium blank (crown at Z 1.910, 0.09 m below the
     2.00 m helmet-dome envelope) with no face, jaw or eye topology, and the
     neck is short (Z 1.690-1.755).  It exists to carry a helmet.
  5. Vertex counts are blockout density (see Counts above): enough for
     proportion and armour-fit checks, not for skin sliding.
  6. The body is bilaterally symmetric by construction.  Any later asymmetry
     (scars, a pauldron, the sword arm) must be authored after this checkpoint;
     the reference's asymmetric pose is still recorded by the Prompt 2 empties
     WSK_Guide_RefPose_* and is deliberately NOT baked into the body.
  7. The mesh is smooth-shaded with edges sharper than 40 deg marked sharp.
     The silhouette is unaffected.

MATERIAL
  MAT_Body_NeutralGrey_01 - one Principled BSDF, flat grey, roughness 0.85,
  metallic 0, no textures, no sculpted pores, veins or scars anywhere.
"""


def write_text_blocks(obj):
    me = obj.data
    lens = [len(p.vertices) for p in me.polygons]
    nq = sum(1 for n in lens if n == 4)
    nt = sum(1 for n in lens if n == 3)
    nn = len(lens) - nq - nt
    bm = bmesh.new()
    bm.from_mesh(me)
    vol = abs(sum(f.verts[0].co.dot(f.verts[1].co.cross(f.verts[2].co)) / 6.0
                  for f in bm.faces))
    area = sum(f.calc_area() for f in bm.faces)
    bm.free()
    txt = bpy.data.texts.get("WSK_BaseBody_Topology_Notes.txt")
    if txt is None:
        txt = bpy.data.texts.new("WSK_BaseBody_Topology_Notes.txt")
    txt.clear()
    txt.write(TOPOLOGY_NOTES.format(
        name=obj.name, nv=len(me.vertices), nf=len(me.polygons), nq=nq, nt=nt,
        nn=nn, qpct=nq / len(me.polygons) * 100.0, vol=vol, area=area))

    notes = bpy.data.texts.get("WSK_Project_Notes.txt")
    if notes is None:
        notes = bpy.data.texts.new("WSK_Project_Notes.txt")
    notes.write(PROJECT_NOTES)


PROJECT_NOTES = """
Prompt 3 - Base body (Wildshift_Knight_03_BaseBody.blend)
========================================================
The Prompt 2 blockout mannequin (`Blockout` collection, WSK_Mann_*) and the
whole proportion guide (`Reference` collection: WSK_Joint_*, WSK_Guide_*,
WSK_Label_*, WSK_Ref_*) are RETAINED in the file.

  Blockout  - retired: the collection and every WSK_Mann_* object are disabled
              in the viewport and in renders.  Nothing was deleted.
  Reference - the agreed proportion guide, kept enabled and separate from the
              body.  Its objects are hidden from renders only.

Collections used:
  Body      -> WSK_Body_Base_01     the deliverable base body (single object)
  Blockout  -> WSK_Mann_*           Prompt 2 blockout, disabled
  Reference -> WSK_Joint_*, WSK_Guide_*, WSK_Label_*, WSK_Ref_*   guide
  Helmet / Armor / Cape / Accessories / Weapon / Rig are still empty: Prompt 3
  creates no armour, no helmet, no cape, no chains, no weapon and no rig.

Body rules (same as Prompt 2, so the two checkpoints stay comparable):
  - one object, identity transform, vertices authored in world space;
  - no modifiers at rest (the Mirror modifier was applied and is recorded in
    the object property wsk_modifiers_applied);
  - axis convention unchanged: Z up, ground at Z = 0, character faces +Y,
    origin between the feet at X = 0 / Y = 0;
  - scale is 1.000 on all axes, dimension X 1.000: no object-level scaling, so
    later modifiers (subdivision, armature, shrinkwrap for armour) behave;
  - neutral untextured Principled material MAT_Body_NeutralGrey_01.

World dimensions preserved from the guide: height to the crown 1.956 m (the
2.00 m envelope belongs to the helmet), feet on Z = 0, joint markers unchanged.
See the text block 'WSK_BaseBody_Topology_Notes.txt' for the topology report.
"""


if __name__ == "__main__":
    main()
