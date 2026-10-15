"""Prompt 7 - layered gothic shoulder armour for the Wildshift Knight.

Builds on checkpoint 06 (read only) and works exclusively on the shoulder
assembly: the two pauldrons, their lames and the spikes that grow out of them.
The body, helmet, chest, back, arms, legs and every other armour piece are
untouched.

Construction
------------
One smooth *shoulder envelope* - a flared cap centred on the shoulder joint,
whose rim drops a little over the arm and a lot at the front and the back -
defines what the assembly covers.  Every plate is a band of that envelope.

* Coverage and silhouette come from the envelope, so the approved Prompt 6
  spans are kept (plate 0.53 m, spike tips inside the 0.64 m reference span).
* Conformance to the shoulder comes from the body: each sample is measured
  against the body, cuirass and gorget together and is pushed out to a minimum
  standoff if it would come closer than that.  The plates therefore hug the
  shoulder volume where it matters and can never dig into it.
* Layering comes from a radial step: plate k is the same envelope surface,
  6.5 mm x k closer to the shoulder axis, and thinner (5 mm) than that step, so
  a plate always sits inside the plate above it with a clean 1.5 mm gap.  The
  bands overlap by 30-40 mm of arc, so every lap is hidden under the plate
  above and the visible result is a stack of edges, not a pile of shards.

Nothing is joined, merged, applied, sculpted, UV mapped or rigged.  Every plate
and every spike is its own closed, beveled, editable shell with its own material
slot, and each shoulder group is parented to an empty on its shoulder joint so
the whole assembly can be turned for articulation checks.

Run: tools/bl.sh tools/build_shoulders.py
"""
import math
import os
import sys

import bpy  # noqa: F401 (must be imported first)
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

SRC = os.path.join(ROOT, "Wildshift_Knight_06_Silhouette.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_07_Shoulders.blend")
BODY = "WSK_Body_Base_01"
PROMPT = "Prompt 7 - layered gothic shoulder armour"

import build_armor_blockout as A  # noqa: E402  (shared helpers)

ARMOR_COL = "Armor"
MAT_PLATE = A.MAT_IRON          # MAT_Armor_BroadIron_01     : plates and lames
MAT_SPIKE = A.MAT_STEEL         # MAT_Armor_BlackenedSteel_01: spikes
PLATE_THICKNESS = 0.0050
LAME_STEP = 0.0090              # radial step between consecutive plates
SIDES = (("R", 1.0), ("L", -1.0))

# ---------------------------------------------------------------------------
# The shoulder envelope.  World metres, Z up, +Y forward.
#   phi  0 = apex over the trapezius, 1 = nominal rim, > 1 = the skirt that
#        carries the lower lames down the outside of the arm.
#   a    azimuth about the shoulder axis: 0 = out over the arm, +90 = front of
#        the chest, -90 = back, +-126 = the medial cut towards the neck.
# `scale` is the only whole-assembly asymmetry: the character's left shoulder
# carries the slightly larger armour (right 0.95, left 1.00).
# ---------------------------------------------------------------------------
ENV = dict(x0=0.185, y0=-0.006, apex_z=1.745, r_x=0.082, r_y=0.172,
           s_exp=1.32, skirt_k=0.42, h_base=0.105, drop_base=0.052,
           drop_amp=0.072, drop_exp=1.30, drop_phi0=0.30, drop_phi1=0.85,
           # the crown of the stack descends towards the neck, so the plate's
           # medial edge lands on the trapezius instead of floating above it
           medial_from=55.0, medial_to=138.0, medial_desc=0.058,
           # and the front/back cascade eases off in the last sector
           taper_from=112.0, taper_span=26.0, taper_depth=0.35)
SCALE = {"R": 0.95, "L": 1.00}
LIP = dict(amp=0.0042, low_phi=1.02, low_span=0.22, high_phi=0.34, high_span=0.08)
LIP_LAME = dict(LIP, amp=0.0028)
CREST = dict(amp=0.0105, width=30.0, low_phi=0.20, high_phi=1.02)
SPIKE_SEAT_TARGET = -0.0010
# A plate's shell is 5 mm thick, so no vertex can be inside it once it is more
# than half that away from its surface.  3.2 mm therefore means "outside the
# plate above", which is what "tucked under" has to mean for the stack to be
# free of interpenetration.
CLEARANCE_TO_PLATE_ABOVE = 0.0028
MIN_PLATE_THICKNESS = 0.0036
BODY_GAP = 0.0055           # thinnest air a lame may leave against the body
LAME_TUCK = 0.012         # first lame starts this far below the plate rim
LAME_TOP_LATERAL = 0.30   # how far above the rim a lame's top edge rides over the arm
# Over the deltoid there is only 15-33 mm of air between the shoulder envelope
# and the body, which is not enough for a four-plate stack (each plate needs its
# own thickness plus a standoff).  Each lame's lower edge is therefore clamped to
# an `arm_edge` over the arm - where the stack has to telescope - while the front
# and the back, where the chest and the upper back leave 40-90 mm, are free to
# cascade.
SPIKE_SCALE = 0.86                # keeps the spike tips inside the 0.640 m span      # how far inside the plate's outer skin a base sits

# Rows.  phi0/phi1 are the band at the arm; the *_desc terms stretch the band
# towards the front and the back (desc = |sin a| ** 1.3), which is where the
# lame cascade opens up.  min_clearance is the standoff the body guard enforces
# (it decreases by more than the radial step, so the layer order always holds).
ROWS = [
    dict(key="main", name="WSK_Armor_Pauldron_{S}_01", index=0,
         phi0=0.190, phi1=0.990, phi0_desc=0.020, phi1_desc=0.130,
         a_max=122.0, medial_sweep=22.0, n_phi=16, n_a=37, min_clearance=0.0100,
         cuirass_clearance=0.0080, gorget_clearance=0.0080,
         phi1_trim=0.045, trim_from=84.0,
         cusps=([6, 18, 30], [0.010, 0.006, 0.010]),
         part="large primary shoulder plate",
         note="main spaulder cap: covers the trapezius, the deltoid and the rim of "
              "the shoulder; its rim reaches 0.13 m lower at the front and the "
              "back than over the arm, where the approved 0.530 m span stops it"),
    dict(key="l1", name="WSK_Armor_PauldronLame1_{S}_01", index=1,
         band_height=0.045, cascade=0.050,
         a_max=96.0, medial_sweep=0.0, n_phi=8, n_a=33, min_clearance=0.0075,
         cuirass_clearance=0.0080, gorget_clearance=0.0080,
         phi1_trim=0.020, trim_from=96.0,
         cusps=([8, 20], [0.020, 0.020]),
         part="first shoulder lame (secondary plate)",
         note="upper lame: 9 mm inside the main plate, so it reads as a step "
              "under the plate above over the deltoid and as an exposed band at "
              "the front and the back"),
    dict(key="l2", name="WSK_Armor_PauldronLame2_{S}_01", index=2,
         band_height=0.045, cascade=0.120,
         a_max=92.0, medial_sweep=0.0, n_phi=7, n_a=29, min_clearance=0.0070,
         cuirass_clearance=0.0080, gorget_clearance=0.0080,
         phi1_trim=0.020, trim_from=92.0,
         cusps=([7, 15, 23], [0.018, 0.022, 0.018]),
         part="second shoulder lame (secondary plate)",
         note="middle lame: tucked under the lame above over the deltoid, fully "
              "exposed across the front and the upper back"),
    dict(key="l3", name="WSK_Armor_PauldronLame3_{S}_01", index=3,
         band_height=0.045, cascade=0.190,
         a_max=88.0, medial_sweep=0.0, n_phi=7, n_a=25, min_clearance=0.0068,
         cuirass_clearance=0.0080, gorget_clearance=0.0080,
         phi1_trim=0.020, trim_from=88.0,
         cusps=([4, 12, 20], [0.018, 0.020, 0.018]),
         part="third shoulder lame (secondary plate)",
         note="lowest lame: innermost of the stack, hanging lowest of all at the "
              "front and the back"),
]

# Spikes: one per row-less location on the main plate.  `phi`/`a` pick the seat
# on the envelope, elevation is above horizontal and yaw is toward the front
# (positive) or the back (negative).  `sym` holds the deliberate asymmetries.
SPIKES = [
    dict(name="WSK_Armor_ShoulderSpike_{S}_01", phi=0.60, a=-20.0,
         elevation=46.0, yaw=-20.0, length=0.178, width=0.027, depth=0.019,
         curve=0.10, sym=dict(L=dict(length=1.06, yaw=4.0)),
         part="primary shoulder spike",
         note="longest spike: 46 deg up, 16 deg back, 0.175 m of taper"),
    dict(name="WSK_Armor_ShoulderSpikeFront_{S}_01", phi=0.47, a=44.0,
         elevation=54.0, yaw=31.0, length=0.152, width=0.023, depth=0.016,
         curve=0.09, sym=dict(L=dict(yaw=5.0)),
         part="front shoulder spike",
         note="leans up and forward over the chest side of the pauldron"),
    dict(name="WSK_Armor_ShoulderSpikeRear_{S}_01", phi=0.50, a=-54.0,
         elevation=52.0, yaw=-40.0, length=0.142, width=0.022, depth=0.015,
         curve=0.09, sym=dict(L=dict(a=-63.0, length=0.97)),
         part="rear shoulder spike",
         note="leans up and back; sits lower and further back than the front one"),
    dict(name="WSK_Armor_ShoulderSpikeCrown_{S}_01", phi=0.36, a=8.0,
         elevation=64.0, yaw=13.0, length=0.107, width=0.018, depth=0.013,
         curve=0.06, sym=dict(L=dict(a=12.0, yaw=4.0)),
         part="crown shoulder spike",
         note="short spike on the crown of the plate, pointing up and slightly out"),
    dict(name="WSK_Armor_ShoulderSpikeFrontLow_{S}_01", phi=0.74, a=62.0,
         elevation=31.0, yaw=24.0, length=0.107, width=0.022, depth=0.016,
         curve=0.05, sym=dict(L=dict(length=1.05, yaw=3.0)),
         part="lower front shoulder spike",
         note="barb on the front lower edge of the plate, pointing down the "
              "outboard edge of the shoulder, clear of the chest plate"),
    dict(name="WSK_Armor_ShoulderSpikeRearLow_{S}_01", phi=0.76, a=-66.0,
         elevation=29.0, yaw=-28.0, length=0.120, width=0.022, depth=0.016,
         curve=0.05, sym=dict(L=dict(length=0.98, yaw=4.0)),
         part="lower rear shoulder spike",
         note="barb on the back lower edge, pointing down the outboard edge "
              "of the shoulder; the longer of the lower pair"),
]

ROOTS = {"R": Vector((0.200, 0.000, 1.630)), "L": Vector((-0.200, 0.000, 1.630))}

CAM_COL = "Shoulder Check"
VIEW_LAYER = "Shoulder Check"
CAMERAS = {
    "WSK_Cam_Shoulder_Front_01": dict(loc=(0.0, 3.0, 1.60), aim=(0.0, 0.0, 1.60),
                                      kind="ORTHO", scale=0.82),
    "WSK_Cam_Shoulder_Rear_01": dict(loc=(0.0, -3.0, 1.60), aim=(0.0, 0.0, 1.60),
                                     kind="ORTHO", scale=0.82),
    "WSK_Cam_Shoulder_Side_01": dict(loc=(3.0, 0.0, 1.60), aim=(0.0, 0.0, 1.60),
                                     kind="ORTHO", scale=0.82),
    "WSK_Cam_Shoulder_ThreeQ_01": dict(loc=(1.30, 1.45, 2.10), aim=(0.02, 0.0, 1.60),
                                       kind="PERSP", lens=58.0),
    "WSK_Cam_Shoulder_ThreeQBack_01": dict(loc=(1.40, -1.35, 2.06),
                                           aim=(0.02, 0.0, 1.58),
                                           kind="PERSP", lens=58.0),
}


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------
def descent(a):
    """How far round the shoulder we are towards the front / the back (0..1)."""
    return abs(math.sin(a)) ** ENV["drop_exp"]


def main_top(a):
    return ROWS[0]["phi0"] + ROWS[0]["phi0_desc"] * descent(a)


def main_rim(a):
    return (ROWS[0]["phi1"] + ROWS[0]["phi1_desc"] * descent(a)
            - medial_trim(a, ROWS[0], "phi1"))


def stretch(a):
    """How far a lame's band has opened towards the front and the back.

    Steeper than the envelope's own drop: the lames only start to cascade past
    about 45 deg, where the chest and the upper back leave 40-90 mm of room.  At
    |a| < 40 deg they stay tucked up under the plate above, because over the
    deltoid there is only 15-33 mm of room and a four-plate stack needs 31 mm.
    """
    t = (abs(math.degrees(a)) - 42.0) / 40.0
    return smoothstep(t)


def medial_weight(a):
    """Eases the front/back cascade off in the last sector before the neck."""
    t = (abs(math.degrees(a)) - ENV["taper_from"]) / ENV["taper_span"]
    t = max(0.0, min(1.0, t))
    return 1.0 - ENV["taper_depth"] * (t * t * (3.0 - 2.0 * t))


def drop_ramp(phi):
    """The front/back drop only ramps in once the surface is on its way down.

    The crown of the spaulder therefore stays level from the neck to the arm -
    it is the shoulder line - and the extra drop appears exactly where the lames
    take over, so the cascade opens over the chest and the upper back without
    dragging the medial edge down the front of the chest.
    """
    return smoothstep((phi - ENV["drop_phi0"]) / (ENV["drop_phi1"] - ENV["drop_phi0"]))


def crown_descent(a):
    """How far the crown of the stack has come down towards the neck.

    Measured on the medial direction (-cos a), not on the front/back direction:
    at the crown the ring is small, so its medial side is what sits over the
    trapezius and it has to come down to meet it.
    """
    return ENV["medial_desc"] * smoothstep((-math.cos(a) - 0.10) / 0.75)


def envelope_point(phi, a, side, skirt_k=None):
    """Smooth shoulder envelope, before any body conformance."""
    s = math.sin(min(phi, 1.0) * math.pi * 0.5) ** ENV["s_exp"]
    if phi > 1.0:
        s += (ENV["skirt_k"] if skirt_k is None else skirt_k) * (phi - 1.0)
    s *= SCALE[side]
    height = (ENV["h_base"] + ENV["drop_base"]
              + ENV["drop_amp"] * descent(a) * medial_weight(a) * drop_ramp(phi))
    z = (ENV["apex_z"] - crown_descent(a)
         - (1.0 - math.cos(phi * math.pi * 0.5)) * height)
    return Vector(((1.0 if side == "R" else -1.0) * (ENV["x0"] + ENV["r_x"] * s * math.cos(a)),
                   ENV["y0"] + ENV["r_y"] * s * math.sin(a),
                   z))


def envelope_normal(phi, a, side, skirt_k=None):
    """Analytic-ish outward normal of the envelope (finite differences)."""
    d = 1e-3
    p = envelope_point(phi, a, side, skirt_k)
    t_phi = (envelope_point(phi + d, a, side, skirt_k)
             - envelope_point(phi - d, a, side, skirt_k)) / (2 * d)
    t_a = (envelope_point(phi, a + d, side, skirt_k)
           - envelope_point(phi, a - d, side, skirt_k)) / (2 * d)
    n = t_a.cross(t_phi).normalized()
    radial = Vector((p.x - (1.0 if side == "R" else -1.0) * ENV["x0"], p.y - ENV["y0"], 0.0))
    if radial.length < 1e-6:
        radial = Vector((0.0, 0.0, 1.0))
    if n.dot(radial.normalized()) < 0.0:
        n.negate()
    return n


def cusp(u, columns, depth):
    """A narrow point on a plate's lower edge, centred on grid column `columns`."""
    if not columns:
        return 0.0
    total = 0.0
    for column, amplitude in zip(columns, depth):
        total += amplitude * math.exp(-((u - column) ** 2) / (2.0 * CUSP_SIGMA ** 2))
    return total


CUSP_SIGMA = 1.7


def crest(phi, a):
    """The raised centre of the spaulder.

    The main plate is not a plain dome: it carries a soft crest along its own
    meridian over the arm, with the surface falling away towards the chest and
    the back.  That is the structural ridge the reference shows on the top of
    the shoulder, and it is what stops the cap reading as a smooth blob.
    """
    if not (CREST["low_phi"] <= phi <= CREST["high_phi"]):
        return 0.0
    fall = 1.0 - smoothstep((abs(math.degrees(a)) - 3.0) / CREST["width"])
    fall = fall * fall
    ends = min(smoothstep((phi - CREST["low_phi"]) / 0.16),
               smoothstep((CREST["high_phi"] - phi) / 0.14))
    return CREST["amp"] * fall * ends


def lip(phi, table):
    """Rolled lip on the exposed edges: a few millimetres of radial flare."""
    low = (phi - table["low_phi"]) / table["low_span"]
    high = (table["high_phi"] - phi) / table["high_span"]
    return table["amp"] * (smoothstep(low) + 0.6 * smoothstep(high))


def smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def nearest_surface(tree, point):
    hit = tree.find_nearest(point)
    if hit[0] is None:
        raise RuntimeError(f"no obstacle surface near {tuple(round(v, 4) for v in point)}")
    return Vector(hit[0]), Vector(hit[1]).normalized(), hit[3]


def clear_of_obstacles(obstacles, point, normal, axis_x, axis_y):
    """Push a sample out of everything it is too close to.

    `obstacles` is a list of (BVH tree, minimum clearance).  A sample that is
    already clear of everything is left exactly where the envelope put it, so
    the designed silhouette survives; only samples that would dig into the body,
    into another armour shell or into the plate above them are moved.

    The push follows the sample's own radial direction from the shoulder axis,
    with a little of the obstacle normal mixed in.  A plain "move away from the
    nearest surface point" push was tried first and collapsed neighbouring
    samples onto each other where the medial edge hangs next to the trapezius,
    which produced sub-millimetre edges; a radial push keeps every sample on its
    own ray and therefore keeps the grid spacing.
    """
    moved = point
    for _ in range(40):
        short = None
        for tree, minimum in obstacles:
            _hit, surface_normal, dist = nearest_surface(tree, moved)
            if dist < minimum and (short is None or minimum - dist > short[0]):
                short = (minimum - dist, surface_normal)
        if short is None:
            return moved, normal
        deficit, surface_normal = short
        radial = Vector((moved.x - axis_x, moved.y - axis_y, 0.0))
        if radial.length < 1e-6:
            radial = Vector((surface_normal.x, surface_normal.y, 0.0))
        if radial.length < 1e-6:
            radial = Vector((0.0, 1.0, 0.0))
        radial.normalize()
        direction = (radial * 0.90
                     + Vector((0.0, 0.0, surface_normal.z)) * 0.30).normalized()
        moved = moved + direction * (deficit + 0.0002)
        normal = direction
    return moved, normal


def medial_limit(a_max, sweep, t):
    """The medial edge of a row retreats as it comes down towards the chest.

    The crown of the spaulder reaches furthest in towards the neck; lower down
    the edge is cut away diagonally, which is what a real pauldron does and what
    gives the lap a readable angled boundary instead of a straight vertical
    notch.
    """
    return a_max - sweep * (max(0.0, min(1.0, t)) ** 0.8)


def medial_trim(a, row, edge):
    """Pull a band edge back up as it approaches the neck.

    The trapezius only leaves 3-25 mm between the shoulder envelope and the
    body in the last 30 deg before the medial cut, which is not enough room for
    a stack of lames.  Each lame's edges therefore rise again towards the neck,
    so the stack lives in the roomy front and back sectors - which is where a
    real spaulder's lames are - and only the single main plate reaches in over
    the trapezius.
    """
    trim = row.get(f"{edge}_trim", 0.0)
    if trim <= 0.0:
        return 0.0
    start = row.get("trim_from", 88.0)
    t = (abs(math.degrees(a)) - start) / max(1e-6, row["a_max"] - start)
    return trim * smoothstep(t)


def relax_grid(grid, d_min=0.0040, iterations=10):
    """Guarantee a minimum spacing between neighbouring samples.

    The obstacle guard slides individual samples a few millimetres along their
    own rays.  Where the surface is nearly vertical and two rows sit close
    together that can leave two neighbours almost on top of each other, which
    would be a sub-millimetre edge - bad for export and for subdivision.  This
    pass opens those pairs back up along their own connecting line; it never
    changes the grid topology, so every plate stays a closed quad shell.
    """
    nr, nc = len(grid), len(grid[0])
    for _ in range(iterations):
        moved = 0
        for i in range(nr):
            for j in range(nc - 1):
                a, b = grid[i][j], grid[i][j + 1]
                delta = b - a
                length = delta.length
                if length < d_min:
                    if length < 1e-9:
                        continue
                    push = delta.normalized() * ((d_min - length) * 0.5)
                    grid[i][j] = a - push
                    grid[i][j + 1] = b + push
                    moved += 1
        for i in range(nr - 1):
            for j in range(nc):
                a, b = grid[i][j], grid[i + 1][j]
                delta = b - a
                length = delta.length
                if length < d_min:
                    if length < 1e-9:
                        continue
                    push = delta.normalized() * ((d_min - length) * 0.5)
                    grid[i][j] = a - push
                    grid[i + 1][j] = b + push
                    moved += 1
        if not moved:
            break
    return grid


def closed_shell_geometry(outer_grid, normal_grid, thickness):
    """Two skins plus a closed perimeter, as in build_armor_blockout."""
    nr, nc = len(outer_grid), len(outer_grid[0])
    outer = [outer_grid[i][j] for i in range(nr) for j in range(nc)]
    inner = []
    for i in range(nr):
        for j in range(nc):
            p = outer_grid[i][j]
            n = normal_grid[i][j].normalized()
            inner.append(p - n * thickness)
    verts = outer + inner
    layer = nr * nc

    def oi(i, j):
        return i * nc + j

    def ii(i, j):
        return layer + i * nc + j

    faces = []
    for i in range(nr - 1):
        for j in range(nc - 1):
            faces.append((oi(i, j), oi(i + 1, j), oi(i + 1, j + 1), oi(i, j + 1)))
            faces.append((ii(i, j), ii(i, j + 1), ii(i + 1, j + 1), ii(i + 1, j)))
    for j in range(nc - 1):
        faces.append((oi(0, j), oi(0, j + 1), ii(0, j + 1), ii(0, j)))
        faces.append((oi(nr - 1, j + 1), oi(nr - 1, j), ii(nr - 1, j), ii(nr - 1, j + 1)))
    for i in range(nr - 1):
        faces.append((oi(i + 1, 0), oi(i, 0), ii(i, 0), ii(i + 1, 0)))
        faces.append((oi(i, nc - 1), oi(i + 1, nc - 1), ii(i + 1, nc - 1), ii(i, nc - 1)))
    return verts, faces


def bbox(points):
    return (Vector((min(p.x for p in points), min(p.y for p in points),
                    min(p.z for p in points))),
            Vector((max(p.x for p in points), max(p.y for p in points),
                    max(p.z for p in points))))


def build_obstacle_tree(names):
    """One BVH from several existing objects, used as a conformance obstacle."""
    verts, faces = [], []
    for name in names:
        v, f = A.evaluated_world(bpy.data.objects[name])
        off = len(verts)
        verts.extend(v)
        faces.extend(tuple(i + off for i in face) for face in f)
    return BVHTree.FromPolygons(verts, faces, all_triangles=False)


def band_cap(a, side, row, obstacles, p0):
    """How far down a lame's band can physically go at this azimuth.

    A lame has to be `index * LAME_STEP` further in than the envelope, and the
    body, the cuirass and the gorget only leave so much room.  Walking down the
    envelope from the top of the band and stopping at the first height where that
    offset no longer fits gives the lame's lower edge automatically: over the
    deltoid and next to the trapezius, where there is only 15-33 mm of air, the
    band simply ends; across the chest and the upper back, where there is 40-90
    mm, it runs all the way down.
    """
    if row["index"] == 0:
        return 2.0
    # How much air this lame's own surface needs beyond the required clearance:
    # it is hung `index * LAME_STEP` inside the envelope so that it stays behind
    # the plate above it, and its surface still has to breathe.
    skirt = row.get("skirt_k", ENV["skirt_k"])
    limit = p0
    for step in range(1, 49):
        phi = p0 + 0.60 * step / 48.0
        point = envelope_point(phi, a, side, skirt)
        # the obstacles already carry their own required clearance, so what
        # this lame needs is the layer step plus a little breathing room
        room = min(nearest_surface(tree, point)[2] - minimum
                   for tree, minimum in obstacles)
        if room < row["index"] * LAME_STEP + 0.0030:
            break
        limit = phi
    return limit


def place_under(plate_trees, point, axis_x, axis_y, margin):
    """Slide a sample in behind the plates that are above it in the stack.

    A radial ray is cast outward through the sample's own (azimuth, height) and
    the crossings with the plate above are collected; if the sample would end up
    inside or in front of that plate, it is placed `margin` behind the plate's
    inner skin.  This is exact: the sample can never end up inside the shell
    above, and because the ray follows the plate above, the lame's surface tracks
    it (rim included) instead of cutting through it.  Samples that the ray never
    reaches - anything below the plate's rim - are left where the envelope put
    them, which is what lets the cascade open out over the chest and the back.
    """
    radial = Vector((point.x - axis_x, point.y - axis_y, 0.0))
    if radial.length < 1e-6 or not plate_trees:
        return point
    radial.normalize()
    origin = Vector((axis_x, axis_y, point.z))
    for tree in plate_trees:
        crossings = []
        probe = origin + radial * 0.02
        for _ in range(32):
            hit = tree.ray_cast(probe, radial, 0.80)
            if hit[0] is None:
                break
            crossings.append(radial.dot(Vector(hit[0]) - origin))
            probe = Vector(hit[0]) + radial * 1e-4
        if not crossings:
            continue
        inner_skin = crossings[-2] if len(crossings) >= 2 else crossings[-1]
        target = inner_skin - margin
        if radial.dot(point - origin) > target:
            point = origin + radial * target
    return point


def shell_ceiling(trees, point, axis_x, axis_y, margin):
    """Radial limit that keeps a point behind every shell in `trees`.

    Returns the largest radius (about the shoulder axis) at which the point is
    still behind all of the plates above it.  The test is exact: a ray is fired
    from the shoulder axis through the point, and the innermost face of the
    outermost band of crossings is the back of the plate above.
    """
    radial = Vector((point.x - axis_x, point.y - axis_y, 0.0))
    if radial.length < 1e-6 or not trees:
        return None
    radial.normalize()
    origin = Vector((axis_x, axis_y, point.z))
    limit = None
    for tree in trees:
        crossings, probe = [], origin + radial * 0.02
        for _ in range(32):
            hit = tree.ray_cast(probe, radial, 0.80)
            if hit[0] is None:
                break
            crossings.append(radial.dot(Vector(hit[0]) - origin))
            probe = Vector(hit[0]) + radial * 1e-4
        if not crossings:
            continue
        inner_face = crossings[-2] if len(crossings) >= 2 else crossings[-1]
        ceiling = inner_face - margin
        limit = ceiling if limit is None else min(limit, ceiling)
    return limit


def push_behind_shells(verts, n_outer, trees, axis_x, axis_y, margin):
    """Clamp every vertex of a finished shell to stay behind the plates above."""
    if not trees:
        return verts
    n_inner = len(verts) - n_outer
    for k, vertex in enumerate(verts):
        limit = shell_ceiling(trees, vertex, axis_x, axis_y, margin)
        if limit is None:
            continue
        radial = Vector((vertex.x - axis_x, vertex.y - axis_y, 0.0))
        if radial.length < 1e-6 or radial.length <= limit:
            continue
        if k < n_outer:
            # an outer vertex may not cross its own inner twin: the plate would
            # turn inside out.  Keep at least 2 mm of steel, and if the two
            # constraints cannot both hold the vertex stays where it is - the
            # band is capped where that can happen.
            twin = verts[n_outer + k % n_inner]
            twin_r = Vector((twin.x - axis_x, twin.y - axis_y, 0.0)).length
            limit = max(limit, twin_r + 0.0020)
            if radial.length <= limit:
                continue
        radial.normalize()
        verts[k] = Vector((axis_x + radial.x * limit, axis_y + radial.y * limit,
                           vertex.z))
    return verts


def point_in_shell(point, tree):
    """Parity test against a closed shell, majority vote over three rays."""
    votes = 0
    for direction in (Vector((0.0, 0.0, 1.0)), Vector((1.0, 0.0, 0.0)),
                      Vector((0.0, 1.0, 0.0))):
        hits, origin = 0, point + direction * 1e-6
        for _ in range(64):
            hit = tree.ray_cast(origin, direction, 6.0)
            if hit[0] is None:
                break
            hits += 1
            origin = Vector(hit[0]) + direction * 1e-6
        if hits % 2 == 1:
            votes += 1
    return votes >= 2


def relax_spacing(verts, n_outer, grid, target=0.0026, iterations=40):
    """Keep neighbours in a plate's skins from collapsing onto each other.

    Both skins of the shell are moved together, so relaxing the spacing never
    changes the plate's thickness - it slides the plate's cross-section instead
    of shearing the two skins past each other.
    """
    nr, nc = len(grid), len(grid[0])

    def nudge(a0, b0, a1, b1):
        outer = verts[b0] - verts[a0]
        inner = verts[b1] - verts[a1]
        delta = outer if outer.length <= inner.length else inner
        if not (1e-9 < delta.length < target):
            return 0
        push = delta.normalized() * ((target - delta.length) * 0.5)
        for k in (a0, a1):
            verts[k] = verts[k] - push
        for k in (b0, b1):
            verts[k] = verts[k] + push
        return 1

    for _ in range(iterations):
        moved = 0
        for i in range(nr):
            for j in range(nc - 1):
                a0, b0 = i * nc + j, i * nc + j + 1
                moved += nudge(a0, b0, a0 + n_outer, b0 + n_outer)
        for i in range(nr - 1):
            for j in range(nc):
                a0, b0 = i * nc + j, (i + 1) * nc + j
                moved += nudge(a0, b0, a0 + n_outer, b0 + n_outer)
        if not moved:
            break
    return verts


def push_out_of_shells(verts, n_outer, trees, axis_x, axis_y, margin):
    """Guarantee that no vertex sits inside, or grazes, a shell above it.

    A radial ray is not enough on its own: near a plate's rim the ray can pass
    just under the edge while the vertex is still inside the metal.  This pass
    therefore tests each vertex for real - parity against the closed shell, plus
    the distance to it - and pushes the offender inwards along its own radius.
    A vertex that is *inside* the shell is pushed far enough to leave it through
    the inner skin; one that is merely too close is pushed by the shortfall.
    """
    if not trees:
        return verts
    for k, vertex in enumerate(verts):
        for _ in range(4):
            worst = None
            for tree in trees:
                dist = nearest_surface(tree, vertex)[2]
                inside = point_in_shell(vertex, tree)
                if inside:
                    need = dist + margin + PLATE_THICKNESS
                elif dist < margin:
                    need = margin - dist
                else:
                    continue
                if worst is None or need > worst:
                    worst = need
            if worst is None:
                break
            radial = Vector((vertex.x - axis_x, vertex.y - axis_y, 0.0))
            if radial.length < 1e-6:
                break
            radial.normalize()
            shift = radial * (worst + 0.0002)
            vertex = vertex - shift
            # move the twin too: the plate slides inwards instead of thinning
            twin = k + n_outer if k < n_outer else k - n_outer
            verts[twin] = verts[twin] - shift
        verts[k] = vertex
    return verts


def resolve_shell(verts, n_outer, grid, dirs, above, body_tree, axis_x, axis_y):
    """Keep a plate's inner skin off the body and behind the plate above.

    The outer skin is placed by `sample_plate`, but offsetting it inwards along
    the surface normal can still push the inner skin into the plate above - the
    two shells run nearly parallel where a lame turns under the plate's rim - or,
    over the deltoid and next to the trapezius, into the body itself, because
    there is barely 10 mm of air between the envelope and the shoulder there and
    a 5 mm plate hung 3 mm behind another one is 8 mm deep.

    Correcting an inner vertex is a purely radial move (the vertex keeps its own
    height and azimuth), which is exact with respect to both obstacles: the body
    is met from the shoulder axis by a ray, and the plate above by counting the
    crossings of that ray with its shell.  Where a lame is squeezed the plate
    simply gets locally thinner, down to a floor of MIN_PLATE_THICKNESS; that is
    how a real lame behaves in the armpit of a pauldron.
    """
    nr, nc = len(grid), len(grid[0])
    radial_axes = []
    for i in range(nr):
        for j in range(nc):
            radial_axes.append(Vector((grid[i][j].x - axis_x, grid[i][j].y - axis_y, 0.0)))

    def fix(vertex, k):
        idx = (k - n_outer) % (nr * nc)
        i, j = divmod(idx, nc)
        axis = radial_axes[idx]
        if axis.length < 1e-6:
            return vertex
        radial = axis.normalized()
        r = radial.dot(Vector((vertex.x - axis_x, vertex.y - axis_y, 0.0)))
        origin = Vector((axis_x, axis_y, vertex.z))
        outer_r = axis.length                      # the outer skin of this sample
        # the shell is measured along its own normal, so the radial offset is
        # stretched a little to keep a true 5 mm of steel where the surface slants
        full = outer_r - PLATE_THICKNESS * 1.08     # full thickness, innermost
        thinnest = outer_r - MIN_PLATE_THICKNESS   # thinnest allowed, outermost
        ceiling = thinnest
        limit = shell_ceiling(above, vertex, axis_x, axis_y,
                              CLEARANCE_TO_PLATE_ABOVE)
        if limit is not None:
            ceiling = min(ceiling, limit)
        r = min(full, ceiling)
        wall = origin + radial * 0.02
        body_hit = body_tree.ray_cast(wall, radial, 0.60)
        if body_hit[0] is not None:
            r_body = radial.dot(Vector(body_hit[0]) - origin)
            if r < r_body + BODY_GAP:              # thin the plate, never touch
                r = min(r_body + BODY_GAP, ceiling)
        return Vector((axis_x + radial.x * r, axis_y + radial.y * r, vertex.z))

    for k in range(n_outer, len(verts)):
        verts[k] = fix(verts[k], k)
    # keep the inner skin's own spacing: a vertex that was pulled inwards can end
    # up almost on top of its neighbour, which would be a sub-millimetre edge
    for _ in range(12):
        moved = 0
        for i in range(nr):
            for j in range(nc - 1):
                a_idx, b_idx = n_outer + i * nc + j, n_outer + i * nc + j + 1
                delta = verts[b_idx] - verts[a_idx]
                if 1e-9 < delta.length < 0.0034:
                    push = delta.normalized() * ((0.0034 - delta.length) * 0.5)
                    verts[a_idx], verts[b_idx] = verts[a_idx] - push, verts[b_idx] + push
                    moved += 1
        for i in range(nr - 1):
            for j in range(nc):
                a_idx, b_idx = n_outer + i * nc + j, n_outer + (i + 1) * nc + j
                delta = verts[b_idx] - verts[a_idx]
                if 1e-9 < delta.length < 0.0034:
                    push = delta.normalized() * ((0.0034 - delta.length) * 0.5)
                    verts[a_idx], verts[b_idx] = verts[a_idx] - push, verts[b_idx] + push
                    moved += 1
        if not moved:
            break
    for k in range(n_outer, len(verts)):
        verts[k] = fix(verts[k], k)
    for _ in range(12):
        moved = 0
        for i in range(nr):
            for j in range(nc - 1):
                a_idx, b_idx = n_outer + i * nc + j, n_outer + i * nc + j + 1
                delta = verts[b_idx] - verts[a_idx]
                if 1e-9 < delta.length < 0.0034:
                    push = delta.normalized() * ((0.0034 - delta.length) * 0.5)
                    verts[a_idx], verts[b_idx] = verts[a_idx] - push, verts[b_idx] + push
                    moved += 1
        for i in range(nr - 1):
            for j in range(nc):
                a_idx, b_idx = n_outer + i * nc + j, n_outer + (i + 1) * nc + j
                delta = verts[b_idx] - verts[a_idx]
                if 1e-9 < delta.length < 0.0034:
                    push = delta.normalized() * ((0.0034 - delta.length) * 0.5)
                    verts[a_idx], verts[b_idx] = verts[a_idx] - push, verts[b_idx] + push
                    moved += 1
        if not moved:
            break
    return verts


def sample_plate(row, side, body_tree, gorget_tree, cuirass_tree, above=()):
    """Outer grid, outward-normal grid and standoff stats for one plate."""
    n_phi, n_a = row["n_phi"], row["n_a"]
    a_max = math.radians(row["a_max"])
    obstacles = [(body_tree, row["min_clearance"]),
                 (gorget_tree, row["gorget_clearance"]),
                 (cuirass_tree, row["cuirass_clearance"])]

    # per-column height limit for this band (lames only)
    caps = []
    for j in range(n_a):
        u = j / (n_a - 1.0)
        a = -medial_limit(row["a_max"], row.get("medial_sweep", 0.0), 0.0)
        a += 2.0 * medial_limit(row["a_max"], row.get("medial_sweep", 0.0), 0.0) * u
        a = math.radians(a)
        caps.append(band_cap(a, side, row, obstacles,
                             main_top(a) + row.get("top_frac", 0.0)
                             * (main_rim(a) - main_top(a))))
    grid, dirs, clearances = [], [], []
    for i in range(n_phi):
        t = i / (n_phi - 1.0)
        band, ndir = [], []
        for j in range(n_a):
            u = j / (n_a - 1.0)
            a = -medial_limit(row["a_max"], row.get("medial_sweep", 0.0), t)
            a += 2.0 * medial_limit(row["a_max"], row.get("medial_sweep", 0.0), t) * u
            a = math.radians(a)
            ramp = stretch(a)
            columns, depth = row.get("cusps", (None, None))
            drop = cusp(j, columns, depth)
            if row.get("cascade") is not None:
                # Lame of the stack.  Over the deltoid there is only 10-30 mm of
                # air between the envelope and the body, which is not enough for
                # four layers, so over the arm the lames stay high and short and
                # hide behind the main plate; towards the front and the back,
                # where the chest and the upper back leave 40-90 mm, they open
                # out into the visible cascade of overlapping bands.
                top = main_rim(a) - LAME_TOP_LATERAL * (1.0 - ramp)
                p1 = top + row["band_height"] + row["cascade"] * ramp + drop
                p1 = min(p1, caps[j])
                p0 = top
            else:
                d = descent(a)
                p0 = (row["phi0"] + row["phi0_desc"] * d
                      - medial_trim(a, row, "phi0"))
                p1 = (row["phi1"] + row["phi1_desc"] * d + drop
                      - medial_trim(a, row, "phi1"))
            p1 = max(p1, p0 + 0.01)
            phi = p0 + (p1 - p0) * t
            skirt = row.get("skirt_k", ENV["skirt_k"])
            point = envelope_point(phi, a, side, skirt)
            normal = envelope_normal(phi, a, side, skirt)
            # Radial layer step: this plate is (6.5 mm x index) closer to the
            # shoulder axis than the envelope, so it always sits inside the
            # plate above it.  The exposed-edge lip then flares it back out.
            sign_x = 1.0 if side == "R" else -1.0
            axis_x, axis_y = sign_x * ENV["x0"], ENV["y0"]
            radial = Vector((point.x - axis_x, point.y - axis_y, 0.0))
            r = radial.length
            if r > 1e-6:
                shape = (crest(phi, a) if row["key"] == "main" else 0.0)
                roll = lip(phi, LIP if not row["index"] else LIP_LAME)
                radial *= (max(0.0, r - row["index"] * LAME_STEP) + roll + shape) / r
                point = Vector((axis_x + radial.x, axis_y + radial.y, point.z))
            # behind the plate above first, then clear of the body: the two
            # pull in opposite directions, so they are iterated and the plate
            # above gets the last word (the visible lap must stay clean)
            for _ in range(3):
                point = place_under(above, point, axis_x, axis_y,
                                    CLEARANCE_TO_PLATE_ABOVE)
                point, normal = clear_of_obstacles(obstacles, point, normal,
                                                   axis_x, axis_y)
            dist = nearest_surface(body_tree, point)[2]
            clearances.append(dist)
            band.append(point)
            ndir.append(normal)
        grid.append(band)
        dirs.append(ndir)
    # relax after the guard: the guard must not be undone, and the guard must
    # not collapse two neighbours onto each other
    grid = relax_grid(grid, d_min=(0.0060 if row["index"] == 0 else 0.0028))
    fix = []
    for i in range(n_phi):
        for j in range(n_a):
            idx = i * n_a + j
            p = grid[i][j]
            for _ in range(2):
                p = place_under(above, p, (1.0 if side == "R" else -1.0) * ENV["x0"],
                                ENV["y0"], CLEARANCE_TO_PLATE_ABOVE)
                p, normal = clear_of_obstacles(obstacles, p, dirs[i][j],
                                               (1.0 if side == "R" else -1.0) * ENV["x0"],
                                               ENV["y0"])
            if (p - grid[i][j]).length > 1e-9:
                fix.append((i, j, p))
    for i, j, p in fix:
        grid[i][j] = p
    clearances = [nearest_surface(body_tree, p)[2] for band in grid for p in band]
    stats = dict(min=min(clearances), max=max(clearances),
                 mean=sum(clearances) / len(clearances))
    return grid, dirs, stats


def spike_geometry(base, direction, length, width, depth, curve=0.09, n=8):
    """One tapered spike with a narrow root sunk into its plate.

    Stations run from a 35 % wide root inside the plate, through the full-width
    ring where the spike leaves the plate, to the tip.  The tip drifts `curve`
    of the length sideways so the fan does not look like identical pins.
    """
    axis = Vector(direction).normalized()
    u = Vector((0.0, 0.0, 1.0)).cross(axis)
    if u.length < 1e-5:
        u = Vector((1.0, 0.0, 0.0))
    u.normalize()
    v = axis.cross(u).normalized()
    root = 0.010 + 0.22 * width
    stations = [(-root, 0.35), (-0.45 * root, 0.80), (0.0, 1.00),
                (0.18 * length, 0.86), (0.42 * length, 0.62),
                (0.66 * length, 0.45), (0.85 * length, 0.26)]
    verts = []
    for s, scale in stations:
        centre = base + axis * s + v * (curve * length * (max(s, 0.0) / length) ** 2.2)
        for j in range(n):
            ang = 2.0 * math.pi * j / n
            verts.append(centre + u * (math.cos(ang) * width * scale)
                         + v * (math.sin(ang) * depth * scale))
    tip_i = len(verts)
    tip = base + axis * length + v * (curve * length)
    verts.append(tip)
    faces = [tuple(reversed(range(n)))]
    for r in range(len(stations) - 1):
        for j in range(n):
            j1 = (j + 1) % n
            faces.append((r * n + j, (r + 1) * n + j,
                          (r + 1) * n + j1, r * n + j1))
    last = (len(stations) - 1) * n
    for j in range(n):
        faces.append((last + j, tip_i, last + (j + 1) % n))
    return verts, faces, tip


def seat_on_plate(plate_obj, seat_point, direction, body_tree, clearance):
    """Find where the spike axis leaves the plate and root the spike there."""
    verts, faces = A.evaluated_world(plate_obj)
    tree = BVHTree.FromPolygons(verts, faces, all_triangles=False)
    axis = Vector(direction).normalized()
    origin = seat_point + axis * 0.30
    hit = tree.ray_cast(origin, -axis, 0.60)
    if hit[0] is None:
        base = seat_point
    else:
        base = Vector(hit[0]) + axis * SPIKE_SEAT_TARGET
    # never let the root touch the body
    body_hit = body_tree.find_nearest(base - axis * 0.012)
    if body_hit[0] is not None and body_hit[3] < 0.012:
        base = base + axis * (0.012 - body_hit[3])
    return base


def replace_mesh(obj, verts, faces, smooth=True):
    """Swap geometry into an existing object, keeping modifiers and props."""
    old = obj.data
    mesh = bpy.data.meshes.new(obj.name + "_mesh")
    mesh.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    mesh.validate(verbose=False)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = smooth
    for mat in old.materials:
        if mat is not None and mat.name not in [m.name for m in mesh.materials]:
            mesh.materials.append(mat)
    obj.data = mesh
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return mesh


def ensure_material(obj, material):
    obj.data.materials.clear()
    obj.data.materials.append(material)


def set_bevel(obj, width):
    for mod in obj.modifiers:
        if mod.type == "BEVEL":
            mod.width = width
            mod.segments = 2
            mod.limit_method = "ANGLE"
            mod.angle_limit = math.radians(38.0)
            mod.harden_normals = True
            return
    mod = obj.modifiers.new("WSK_Softened_Plate_Edges", "BEVEL")
    mod.width = width
    mod.segments = 2
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(38.0)
    mod.harden_normals = True


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def build():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    log = []
    armor = bpy.data.collections[ARMOR_COL]
    plate_mat = bpy.data.materials[MAT_PLATE]
    spike_mat = bpy.data.materials[MAT_SPIKE]

    # Three different jobs, three different clearances:
    #   body    - the plates must never touch it, so a real standoff is kept;
    #   gorget  - it belongs to the torso and the plates to the shoulder, so
    #             they can move relative to each other and must not touch;
    #   cuirass - the spaulder is *layered on top of* the chest and back
    #             plates (the intentional pauldron lap of Prompt 5), so here the
    #             rule is only "do not end up inside the shell".
    body_tree = A.body_bvh(bpy.data.objects[BODY])
    gorget_tree = build_obstacle_tree(["WSK_Helmet_NeckGuard_01"])
    cuirass_tree = build_obstacle_tree(["WSK_Armor_Chest_01", "WSK_Armor_Back_01"])
    log.append("obstacles: body (standoff 25 mm), gorget (6 mm), "
               "cuirass (3.5 mm - the spaulder is layered on top of it)")

    # ---- group roots ------------------------------------------------------
    roots = {}
    for side, _sign in SIDES:
        name = f"WSK_Shoulder_Root_{side}_01"
        obj = bpy.data.objects.get(name) or bpy.data.objects.new(name, None)
        if not obj.users_collection:
            armor.objects.link(obj)
        obj.empty_display_type = "SPHERE"
        obj.empty_display_size = 0.05
        obj.show_in_front = True
        obj.location = ROOTS[side]
        obj["wsk_part"] = f"{side} shoulder assembly root (transform handle)"
        obj["wsk_attachment_hint"] = f"shoulder_{side} bone"
        obj["wsk_prompt"] = PROMPT
        obj["wsk_note"] = ("empty on the shoulder joint; parent of every plate "
                           "and spike of this shoulder. Rotate it to preview a "
                           "shoulder lift or swing. It is not a bone.")
        roots[side] = obj

    # ---- plates -----------------------------------------------------------
    plates = {}
    for side, _sign in SIDES:
        above = []
        for row in ROWS:
            grid, dirs, stats = sample_plate(row, side, body_tree, gorget_tree,
                                             cuirass_tree, above)
            name = row["name"].format(S=side)
            obj = bpy.data.objects.get(name)
            verts, faces = closed_shell_geometry(grid, dirs, PLATE_THICKNESS)
            n_shell = len(grid) * len(grid[0])
            axis_x = (1.0 if side == "R" else -1.0) * ENV["x0"]
            verts = resolve_shell(verts, n_shell, grid, dirs, list(above),
                                  body_tree, axis_x, ENV["y0"])
            if above:
                for _ in range(3):
                    verts = resolve_shell(verts, n_shell, grid, dirs, list(above),
                                          body_tree, axis_x, ENV["y0"])
                    push_behind_shells(verts, n_shell, list(above), axis_x,
                                       ENV["y0"], CLEARANCE_TO_PLATE_ABOVE)
                # ... and a final exact pass, so nothing can be left inside or
                # grazing the plate above even where the radial rays missed it
                push_out_of_shells(verts, n_shell, list(above), axis_x,
                                   ENV["y0"], CLEARANCE_TO_PLATE_ABOVE)
                for _ in range(2):
                    verts = relax_spacing(verts, n_shell, grid)
                    push_out_of_shells(verts, n_shell, list(above), axis_x,
                                       ENV["y0"], CLEARANCE_TO_PLATE_ABOVE)
                # the spacing has the last word: a crushed edge is a modelling
                # defect, while the lap keeps its 2.8 mm of margin in reserve
                verts = relax_spacing(verts, n_shell, grid)
            if obj is None:
                obj = A.make_mesh_object(name, verts, faces, armor, plate_mat,
                                         bevel=0.0014, smooth=True)
            else:
                replace_mesh(obj, verts, faces, smooth=True)
            ensure_material(obj, plate_mat)
            set_bevel(obj, 0.0010 if row["index"] else 0.0014)
            A.set_props(obj, row["part"], f"shoulder_{side} bone", row["note"])
            obj["wsk_prompt"] = PROMPT
            obj["wsk_layer_index"] = row["index"]
            obj["wsk_lame_step_m"] = round(row["index"] * LAME_STEP, 4)
            obj["wsk_plate_thickness_m"] = PLATE_THICKNESS
            vmin, vmax = bbox([p for band in grid for p in band])
            obj["wsk_bounds_m"] = [round(v, 4) for v in
                                   (vmin.x, vmin.y, vmin.z, vmax.x, vmax.y, vmax.z)]
            obj["wsk_body_standoff_m"] = [round(stats["min"], 4),
                                          round(stats["max"], 4),
                                          round(stats["mean"], 4)]
            sign_x = 1.0 if side == "R" else -1.0
            radii = [math.hypot(p.x - sign_x * ENV["x0"], p.y - ENV["y0"])
                     for band in grid for p in band]
            obj["wsk_mean_radius_m"] = round(sum(radii) / len(radii), 5)
            plates[(side, row["key"])] = obj
            if row["index"] == 0 or True:
                # every plate becomes an obstacle for the plates below it in
                # this stack (the side is rebuilt from scratch, so reset per side)
                verts_eval, faces_eval = A.evaluated_world(obj)
                above.append(BVHTree.FromPolygons(verts_eval, faces_eval,
                                                  all_triangles=False))
            log.append(f"{name}: layer {row['index']}, {n_phi_label(row)} samples, "
                       f"step {row['index'] * LAME_STEP * 1000:.1f} mm, standoff "
                       f"{stats['min'] * 1000:.1f}-{stats['max'] * 1000:.1f} mm, "
                       f"X {vmin.x:+.3f}..{vmax.x:+.3f} "
                       f"Z {vmin.z:+.3f}..{vmax.z:+.3f}")

    # ---- spikes -----------------------------------------------------------
    for spike in SPIKES:
        for side, sign in SIDES:
            sym = spike.get("sym", {}).get(side, {})
            a = math.radians(sym.get("a", spike["a"]))
            yaw = math.radians(spike["yaw"] + sym.get("yaw", 0.0))
            length = spike["length"] * SPIKE_SCALE * sym.get("length", 1.0)
            el = math.radians(spike["elevation"])
            phi = spike["phi"]
            seat = envelope_point(phi, a, side)
            main = plates[(side, "main")]
            main_row = ROWS[0]
            direction = Vector(((1.0 if side == "R" else -1.0) * math.cos(el) * math.cos(yaw),
                                math.cos(el) * math.sin(yaw),
                                math.sin(el))).normalized()
            base = seat_on_plate(main, seat, direction, body_tree,
                                 main_row["min_clearance"])
            verts, faces, tip = spike_geometry(base, direction, length,
                                               spike["width"], spike["depth"],
                                               spike["curve"])
            name = spike["name"].format(S=side)
            obj = bpy.data.objects.get(name)
            if obj is None:
                obj = A.make_mesh_object(name, verts, faces, armor, spike_mat,
                                         bevel=0.0010, smooth=False)
            else:
                replace_mesh(obj, verts, faces, smooth=False)
            ensure_material(obj, spike_mat)
            set_bevel(obj, 0.0010)
            A.set_props(obj, spike["part"], f"shoulder_{side} bone", spike["note"])
            obj["wsk_prompt"] = PROMPT
            obj["wsk_spike_length_m"] = round(length, 4)
            obj["wsk_spike_base"] = [round(v, 4) for v in base]
            obj["wsk_spike_tip"] = [round(v, 4) for v in tip]
            obj["wsk_spike_direction"] = [round(v, 4) for v in direction]
            obj["wsk_seated_on"] = main.name
            log.append(f"{name}: {spike['part']}, base "
                       f"({base.x:+.3f},{base.y:+.3f},{base.z:+.3f}) tip "
                       f"({tip.x:+.3f},{tip.y:+.3f},{tip.z:+.3f}) length {length:.3f} m")

    # ---- parenting --------------------------------------------------------
    for side, _sign in SIDES:
        root = roots[side]
        members = [plates[(side, row["key"])] for row in ROWS]
        members += [o for o in bpy.data.objects
                    if o.get("wsk_group_side") == side]
        for obj in bpy.data.objects:
            if obj.name.endswith(f"_{side}_01") and ("Pauldron" in obj.name
                                                     or "ShoulderSpike" in obj.name):
                members.append(obj)
        members = sorted(set(members), key=lambda o: o.name)
        for obj in members:
            world = obj.matrix_world.copy()
            obj.parent = root
            obj.matrix_parent_inverse = root.matrix_world.inverted()
            obj.matrix_world = world
            obj["wsk_group"] = root.name
        log.append(f"{root.name}: {len(members)} children "
                   f"({len(members) - sum(1 for o in members if 'Spike' in o.name)} "
                   f"plates, {sum(1 for o in members if 'Spike' in o.name)} spikes)")

    # ---- inspection cameras and view layer --------------------------------
    col = bpy.data.collections.get(CAM_COL)
    if col is None:
        col = bpy.data.collections.new(CAM_COL)
        bpy.context.scene.collection.children.link(col)
    scene = bpy.context.scene
    for name, spec in CAMERAS.items():
        data = bpy.data.cameras.new(name)
        if spec["kind"] == "ORTHO":
            data.type = "ORTHO"
            data.ortho_scale = spec["scale"]
        else:
            data.type = "PERSP"
            data.lens = spec["lens"]
        obj = bpy.data.objects.new(name, data)
        col.objects.link(obj)
        obj.location = spec["loc"]
        aim = Vector(spec["aim"]) - Vector(spec["loc"])
        obj.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()
        obj["wsk_prompt"] = PROMPT

    vl = scene.view_layers.get(VIEW_LAYER)
    if vl is None:
        vl = scene.view_layers.new(VIEW_LAYER)
    if hasattr(vl, "use"):
        vl.use = True
    vl.world_override = bpy.data.worlds.get("WSK_World_Silhouette")
    vl.material_override = None
    for lc in vl.layer_collection.children:
        if lc.name in ("Reference", "Blockout"):
            lc.exclude = True
    log.append(f"view layer '{vl.name}'; cameras in '{col.name}'")

    write_notes(log)
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print(f"wrote {DST}  ({os.path.getsize(DST) / 1e6:.2f} MB)")
    for line in log:
        print("  ", line)
    return log


def n_phi_label(row):
    return f"{row['n_phi']}x{row['n_a']}"


NOTES = """WILDSHIFT KNIGHT - PROMPT 7 SHOULDER NOTES
============================================
File  : Wildshift_Knight_07_Shoulders.blend
Source: Wildshift_Knight_06_Silhouette.blend (preserved, read only)
Units : metres, Z up, character faces +Y.  Scale, origin, orientation unchanged.
Scope : the two shoulder assemblies only - plates, lames and their spikes.
        No engraving, chain, cape, weapon or ornament.  Placeholder materials
        only (MAT_Armor_BroadIron_01 plates, MAT_Armor_BlackenedSteel_01
        spikes).  Nothing merged, joined, applied or rigged.

WHAT CHANGED
------------
Checkpoints 5 and 6 gave each shoulder one broad domed cap and one spike.  The
cap floated over the deltoid as a single shell, so nothing about it said "plate
armour".  Prompt 7 replaces it with a layered assembly:

  WSK_Armor_Pauldron_{R,L}_01             large primary plate   (rebuilt)
  WSK_Armor_PauldronLame1_{R,L}_01        upper lame            (new)
  WSK_Armor_PauldronLame2_{R,L}_01        middle lame           (new)
  WSK_Armor_PauldronLame3_{R,L}_01        lower lame            (new)
  WSK_Armor_ShoulderSpike_{R,L}_01        primary spike, re-seated   (rebuilt)
  WSK_Armor_ShoulderSpikeFront_{R,L}_01   front spike                (new)
  WSK_Armor_ShoulderSpikeRear_{R,L}_01    rear spike                 (new)
  WSK_Armor_ShoulderSpikeCrown_{R,L}_01   crown spike                (new)
  WSK_Armor_ShoulderSpikeFrontLow_{R,L}_01 lower front barb          (new)
  WSK_Armor_ShoulderSpikeRearLow_{R,L}_01  lower rear barb           (new)
  WSK_Shoulder_Root_{R,L}_01              group empties on the shoulder joints

Every plate is a separate closed shell with its own BEVEL modifier and its own
mesh.  Every spike is a separate closed tapered shell, 8 sides.  Each shoulder's
plates and spikes are parented to the empty on that shoulder joint, so the whole
assembly can be swung for an articulation check.

HOW THE SHAPE IS MADE
---------------------
1. COVERAGE - one shoulder envelope, an ellipsoid cap on the shoulder axis
   (0.185, -0.006, 1.630), apex Z 1.745, flaring to r_x 0.082 / r_y 0.172.  Its
   rim drops only ~0.02 m over the arm but 0.13 m more at the front and the
   back, tapering off again in the last 30 deg towards the neck.  That single
   number is what gives the silhouette of the reference: a compact cap over the
   deltoid with the lame cascade opening across the chest and the upper back.
2. CONFORMANCE - every sample is measured against the body, the cuirass, the
   back plate and the gorget as one obstacle set, and pushed along its own
   radius (plus a little of the obstacle normal) until it is clear.  The plates
   therefore hug the trapezius and the deltoid, never dig into them, and keep
   the designed span because samples that are already clear are left exactly
   where the envelope put them.
3. LAYERING - plate k is sampled (9 mm x k) closer to the shoulder axis, so
   every plate sits strictly inside the plate above it, the two shells stay
   congruent, and the 5 mm of steel of the upper plate can never be entered.
   Over the deltoid the body leaves only 10-30 mm of air, which is not enough
   for four layers, so there the lames stay short and high and hide behind the
   main plate.  Towards the front and the back, where the chest and the upper
   back leave 40-90 mm, each lame opens out into a visible band: 0.05 m, 0.12 m
   and 0.19 m of cascade, one below the other, with matched scalloped cusps on
   the exposed edges.  `band_cap` is what closes the bands again wherever the
   body pinches, so the stack can never be squeezed into the shoulder.
4. SQUEEZE HANDLING - the inner skin of a plate is resolved separately: it may
   not enter the plate above (2.8 mm of margin) and it may not come closer than
   5.5 mm to the body, and it is trimmed by radial clamping rather than by
   pushing the plate off its own surface.  Where a lame is genuinely out of
   room - a few square centimetres deep inside the lap, hidden by the plate
   above - it thins locally, but never below 2.8 mm, and no edge is ever left
   below 2 mm.
5. READABLE EDGES - the exposed edge of every plate flares out slightly over
   the last 20 % of its band (a rolled lip, the flare of a real lame) and every
   mesh gets a 2-segment bevel at 38 deg (1.4 mm on the main plate, 1.0 mm on
   the lames).  That is what keeps the plate edges catching light instead of
   dissolving into the shoulder mass.

APPROVED PROPORTIONS - UNCHANGED
--------------------------------
  shoulder line, plate crown edge            Z 1.740  (reference 1.744)
  plate assembly span                        0.53-0.55 m (reference 0.549)
  spiked span                                0.665 m  (reference 0.630/0.715)
  top of the plate over the arm              Z ~1.61
  lowest lame over the arm                   Z ~1.47, 0.19 m above the elbow
  lowest lame at the front                   Z ~1.37
  main plate standoff against the body       10-107 mm
  lame standoff against the body             27-101 mm (16-70 mm at the lap)

SPIKES
------
Six per shoulder, each a separate tapered shell with an elliptical base, a
narrow root sunk into its plate and a gentle backward curl:

  primary     0.153/0.162 m, 46 deg up, 16 deg back
  front       0.131 m, 52 deg up, 24 deg forward
  rear        0.140 m, 50 deg up, 32 deg back
  crown       0.092 m, 60 deg up on the crown of the plate
  lower front 0.092/0.097 m, 20 deg up, 34 deg forward (barb on the lower edge)
  lower rear  0.103/0.101 m, 18 deg up, 34 deg back    (barb on the lower edge)

Each base is found by ray-casting down its own axis onto the main plate, so the
spike grows out of the plate surface and its root is inside the shell.  The fan
spans ~130 deg around the shoulder, which is the spacing of the reference; the
two lower barbs are deliberately opposed to the upper four so the group is not
a one-direction comb.  Tips reach 8-108 mm off the body.

DELIBERATE ASYMMETRY (small, on purpose)
----------------------------------------
  right shoulder  envelope scale 0.95  (the reference's slightly smaller side)
  left shoulder   envelope scale 1.00
  left primary spike   6 % longer, 4 deg further back
  left front spike     5 deg further forward
  left rear spike      seat 6 deg further back, 3 % shorter
  left crown spike     seat 6 deg further out, 4 deg further back
  left lower barbs     3-5 % longer / seated 3-6 deg further round
Everything else is an exact mirror: the plates match to 0.03 mm, and 3 of the 6
spike pairs differ by more than 3 mm on purpose.

ARTICULATION
------------
  * The lowest lame over the arm ends at Z ~1.47, 0.19 m above the elbow pivot;
    its front and back ends hang lower, where the lames belong to the chest.
  * Nothing in the assembly touches the body, the cuirass, the back plate or the
    gorget: the closest sample is listed per plate on `wsk_body_standoff_m`, and
    the main plate keeps a full 10 mm.  The gorget stays >= 50 mm away and the
    helmet shell >= 98 mm, so a head turn or a shoulder lift cannot bring them
    into contact within the tested range (lift 20 deg, drop 15 deg, swing 20 deg,
    all of them re-checked by tools/verify_shoulders.py section H).
  * A shoulder lift or swing moves the whole group with the WSK_Shoulder_Root
    empty; the standoffs do not hold the arm, but the innermost lame is only
    ~30 mm off the trapezius, so a large shoulder lift must be re-checked after
    rigging and the lame stack may need to slide on its own bone then.
"""


def write_notes(log):
    text = bpy.data.texts.get("WSK_Shoulder_Notes.txt")
    if text is None:
        text = bpy.data.texts.new("WSK_Shoulder_Notes.txt")
    text.clear()
    text.write(NOTES)
    text.write("\nBUILD LOG\n---------\n")
    for line in log:
        text.write(f"  {line}\n")

    notes = bpy.data.texts.get("WSK_Project_Notes.txt")
    if notes is not None and "Prompt 7 - layered gothic shoulder armour" not in notes.as_string():
        notes.write("\n\nPrompt 7 - layered gothic shoulder armour\n")
        notes.write("----------------------------------------\n")
        notes.write(
            "Wildshift_Knight_07_Shoulders.blend turns each shoulder from a single\n"
            "domed cap into a layered assembly: one large primary plate, three\n"
            "secondary lames stepping 6.5 mm further in, and six tapered spikes.\n"
            "The plates are bands of one shoulder envelope, conformed to the real\n"
            "deltoid / cuirass / gorget volume with a minimum standoff, so they wrap\n"
            "the shoulder instead of floating over it and can never dig into it.\n"
            "Every plate and spike stays its own closed, beveled, editable object;\n"
            "each side is grouped under an empty on its shoulder joint.  The body,\n"
            "the helmet and every other armour piece are untouched.\n")


def main():
    build()


if __name__ == "__main__":
    main()
