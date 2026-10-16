"""Prompt 10 - thorn crown for the helmet, and refined shoulder spikes.

Opens `Wildshift_Knight_09_LimbArmor.blend`, replaces the nine flat radial
crown spikes of checkpoint 4 with a designed thorn crown, re-cuts the six
spikes of each pauldron in the same profile, and saves
`Wildshift_Knight_10_Crown.blend`.  Nothing else changes: the helmet shell,
crest, face plate, gorget, band, halo, spine, mount, body, every other armour
plate and the whole scene setup keep their geometry.

The crown
---------
21 separate thorns in two rows.  Every thorn is *planted*, never placed: its
base is found by ray-casting the evaluated helmet (shell, crest and band) along
the thorn's own azimuth and height, so the base ring always sits on real metal.
The thorn is then drawn along its axis with one shared profile:

    buried root  ->  flared base  ->  concave taper  ->  needle tip

`thorn_geometry` solves the root depth from the angle between the thorn and the
surface normal, so a thorn that leaves the surface at 58 degrees is buried just
as deeply as one that leaves it square on.  `fit_length` then walks the axis
outward and stops the thorn 2 mm before the band, the crest, the face plate,
the gorget, the halo, the spine, the mount, the shoulders, the chest, the back
or the body.

The fan is a composition, not a radial repeat: one dominant centre blade, five
graded pairs behind it, a lower row of barbs that hangs past the cheek line, and
five hand-written asymmetries.  Nothing is random.

Run:  tools/bl.sh tools/build_crown_thorns.py
"""
import math
import os

import bpy          # noqa: F401  (must be imported first: sets module paths)
import bmesh        # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_09_LimbArmor.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_10_Crown.blend")
PROMPT = "Prompt 10 - crown thorns and refined armour spikes"
BODY = "WSK_Body_Base_01"

SHELL = "WSK_Helmet_Shell_01"
FACE = "WSK_Helmet_Faceplate_01"
CREST = "WSK_Helmet_Crest_01"
GORGET = "WSK_Helmet_NeckGuard_01"
BAND = "WSK_Helmet_CrownBand_01"
HALO = "WSK_Helmet_CrownHalo_01"
SPINE = "WSK_Helmet_CrownSpine_01"
MOUNT = "WSK_Helmet_CrownMount_01"
HEAD_ROOT = "WSK_Helmet_Root_01"
IRON = "MAT_Helmet_CrownIron_01"
ARMOR_MAT = "MAT_Armor_BlackenedSteel_01"

OLD_SPIKES = [f"WSK_Helmet_CrownSpike_{s}_01"
              for s in ("C", "R1", "L1", "R2", "L2", "R3", "L3", "R4", "L4")]

# --------------------------------------------------------------------------
# the crown design
# --------------------------------------------------------------------------
# Each thorn is planted on a horizontal ray that starts 0.45 m outside the head
# at height `z` and azimuth `theta` (0 = front, positive = the character's
# right, +/-180 = nape), so the base lands on the real, evaluated surface.  It
# then leaves along
#
#     tilt   degrees away from vertical
#     lean   azimuth it leans towards, same convention as theta
#
# so the fan is designed in the two numbers a crown is actually designed in,
# and the shape of the helmet cannot bend it out of shape.
#
# Row A: the circlet fan - planted immediately above the top edge of the brow
#   band, the way a thorn crown grows out of a circlet.  The centre blade is
#   planted on the crest's front face (the crest is what is there at the front
#   centre) and continues the crest line, exactly as in the reference.
# Row B: the under-row - shorter barbs below the band.  The front pairs hang
#   down beside the cheek, the rear pairs sweep back under the halo.
#
# `lean` holds the hand-written asymmetries: the two sides agree in design but
# not to the millimetre.
ROW_A = [
    dict(name="C", theta=0.0, z=1.945, tilt=4.0, lean=180.0, length=0.195,
         w_ratio=0.030, d_ratio=2.60, curve=("back", 0.02),
         note="centre blade: planted on the crest's front face, a flat sagittal "
              "blade continuing the crest line above the dome"),
    dict(name="1", theta=24.0, z=1.9135, tilt=30.0, lean=105.0, length=0.165,
         w_ratio=0.075, curve=("back", 0.05),
         note="first pair: the tallest secondary thorns, leaning out and back"),
    dict(name="2", theta=56.0, z=1.9170, tilt=44.0, lean=112.0, length=0.142,
         w_ratio=0.075, curve=("back", 0.06),
         lean_sym=dict(L=dict(length=1.04, tilt=2.0)),
         note="second pair: the widest reach of the crown"),
    dict(name="3", theta=92.0, z=1.9208, tilt=52.0, lean=125.0, length=0.125,
         w_ratio=0.085, curve=("back", 0.06),
         lean_sym=dict(L=dict(lean=128.0, curve=("back", 0.05))),
         note="third pair: at the widest point of the head, standing well out"),
    dict(name="4", theta=120.0, z=1.9235, tilt=62.0, lean=145.0, length=0.115,
         w_ratio=0.085, curve=("back", 0.05),
         lean_sym=dict(L=dict(length=1.05)),
         note="fourth pair: over the nape, sweeping back"),
    dict(name="5", theta=149.0, z=1.9252, tilt=70.0, lean=157.0, length=0.105,
         w_ratio=0.090, curve=("back", 0.045),
         lean_sym=dict(R=dict(length=0.96, lean=154.0)),
         note="fifth pair: the rear of the fan, laid back along the nape"),
]
ROW_B = [
    dict(name="1", theta=42.0, z=1.8752, tilt=122.0, lean=72.0, length=0.112,
         w_ratio=0.074, curve=("down", 0.055),
         note="front barb: hangs out and forward past the cheek guard"),
    dict(name="2", theta=70.0, z=1.8799, tilt=124.0, lean=100.0, length=0.108,
         w_ratio=0.076, curve=("down", 0.055),
         lean_sym=dict(L=dict(length=1.05, curve=("down", 0.062))),
         note="side barb: the widest lower thorn, level with the temple"),
    dict(name="3", theta=98.0, z=1.8831, tilt=120.0, lean=122.0, length=0.102,
         w_ratio=0.080, curve=("down", 0.050),
         lean_sym=dict(L=dict(theta=100.0, length=0.96)),
         note="side barb behind the widest point, sweeping back and down"),
    dict(name="4", theta=126.0, z=1.8857, tilt=118.0, lean=142.0, length=0.104,
         w_ratio=0.078, curve=("down", 0.050),
         note="rear barb: passes through the halo's opening"),
    dict(name="5", theta=152.0, z=1.8872, tilt=115.0, lean=162.0, length=0.108,
         w_ratio=0.075, curve=("back", 0.050),
         lean_sym=dict(R=dict(length=0.94, lean=159.0)),
         note="last barb: the lowest and rearmost of the crown"),
]
# The band's centre line runs from BAND_Z_FRONT at the brow to BAND_Z_BACK at
# the nape, and is BAND_HALF high; row A is planted ROW_A_LIP above its top
# edge and row B ROW_B_DROP below its bottom edge.
BAND_Z_FRONT = 1.896
BAND_Z_BACK = 1.914
BAND_HALF = 0.010
ROW_A_LIP = 0.007          # row A is planted this far above the band's top edge
ROW_B_DROP = 0.012         # ... and row B this far below its bottom edge

# Profile, as fractions of the thorn's own base half width `w`:
PROFILE = [
    ("root", -1.00, 0.50),      # t is a multiple of the solved root depth ...
    ("root", -0.55, 0.85),
    ("width", 0.00, 1.25),      # ... and here a multiple of `w`.
    ("width", 0.38, 1.12),      # The 1.25 ring is the visible flared base.
    ("width", 0.85, 1.00),
]
TAPER = [(0.10, 0.88), (0.24, 0.72), (0.40, 0.56), (0.58, 0.40),
         (0.74, 0.26), (0.88, 0.13)]
SIDES = 6
DEPTH_RATIO = 0.86         # cross-section: a little thinner than it is wide
TIP_CLEARANCE = 0.0020     # the length fit keeps this much clear of obstacles
ROOT_CLEARANCE = 0.0020    # every buried ring is at least this deep
SHELL_MARGIN = 0.0006      # clearance kept off the mounting surface itself

# Shoulder spikes.  The seats, elevations, yaws and left/right differences are
# Prompt 7's approved ones; what changes here is the profile (a planted,
# flared-base thorn instead of a pin), a 12 % length reduction and a 12 %
# slimmer base, so the shoulder fan is unmistakably the *smaller* of the two
# thorn scales.  `el` is elevation above horizontal, `yaw` is toward the front.
SHOULDER_SHORTEN = 0.65
SHOULDER_LOW_SHORTEN = 0.65      # the two lower barbs, same scale
SHOULDER_W_RATIO = 0.135
SHOULDER_D_RATIO = 0.76
SHOULDER_SPIKES = [
    dict(name="WSK_Armor_ShoulderSpike_{S}_01", el=46.0, yaw=-20.0, length=0.178,
         low=False, sym=dict(L=dict(length=1.06, yaw=4.0))),
    dict(name="WSK_Armor_ShoulderSpikeFront_{S}_01", el=54.0, yaw=31.0,
         length=0.152, low=False, sym=dict(L=dict(yaw=5.0))),
    dict(name="WSK_Armor_ShoulderSpikeRear_{S}_01", el=52.0, yaw=-40.0,
         length=0.142, low=False, sym=dict(L=dict(yaw=5.0, length=0.97))),
    dict(name="WSK_Armor_ShoulderSpikeCrown_{S}_01", el=64.0, yaw=13.0,
         length=0.107, low=False, sym=dict(L=dict(yaw=4.0))),
    dict(name="WSK_Armor_ShoulderSpikeFrontLow_{S}_01", el=31.0, yaw=24.0,
         length=0.107, low=True, sym=dict(L=dict(length=1.05, yaw=3.0))),
    dict(name="WSK_Armor_ShoulderSpikeRearLow_{S}_01", el=29.0, yaw=-28.0,
         length=0.120, low=True, sym=dict(L=dict(length=0.98, yaw=4.0))),
]

GROUPS = (("R", 1.0), ("L", -1.0))

# --------------------------------------------------------------------------
# scene helpers - world-space meshes and identity transforms, as in every
# earlier build script
# --------------------------------------------------------------------------


def evaluated_world(obj):
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    eo = obj.evaluated_get(deps)
    me = eo.to_mesh()
    mw = eo.matrix_world.copy()
    verts = [mw @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    eo.to_mesh_clear()
    return verts, polys


def bvh_of(names):
    """One BVH over one object or a list of objects (concatenated geometry)."""
    if isinstance(names, str):
        names = [names]
    verts, faces = [], []
    for name in names:
        v, f = evaluated_world(bpy.data.objects[name])
        off = len(verts)
        verts += v
        faces += [tuple(i + off for i in face) for face in f]
    return BVHTree.FromPolygons(verts, faces, all_triangles=False)


def nearest(tree, point):
    hit = tree.find_nearest(point)
    if hit[0] is None:
        return None, None, None
    return hit[0].copy(), hit[1].copy(), hit[3]


PARITY_DIRS = (Vector((0.577, 0.577, 0.577)),
               Vector((-0.707, 0.500, 0.500)),
               Vector((0.267, -0.802, 0.535)))
NEAR_LIMIT = 0.045         # beyond this a point is outside, whatever the sign


def parity_inside(tree, point, directions=PARITY_DIRS, max_hits=16):
    """Ray-crossing parity test: a reliable inside/outside answer.

    The cheaper `(point - nearest) . normal` sign is only trustworthy within
    roughly the local feature size: a point 0.7 m above the middle of the crown
    band's ring reports "inside" with that test, because the nearest piece of
    band is the far side.  Parity is used instead, with three directions and a
    majority vote so a ray that grazes an edge cannot flip the answer.
    """
    votes = 0
    for d in directions:
        n = 0
        t = 0.0
        while n < max_hits:
            hit = tree.ray_cast(point + d * t, d, 5.0)
            if hit[0] is None:
                break
            t = (hit[0] - point).dot(d) + 1e-4
            n += 1
        votes += int(n % 2 == 1)
    return votes >= 2


def inside_or_near(tree, point, margin):
    """True when `point` is inside the closed shell or closer than `margin`."""
    loc, nrm, dist = nearest(tree, point)
    if loc is None:
        return False, 9.9
    if dist < margin:
        return True, dist
    if dist >= NEAR_LIMIT:
        return False, dist
    return parity_inside(tree, point), dist


def new_mesh_object(name, verts, faces, collection, material):
    me = bpy.data.meshes.new(name + "_mesh")
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate(verbose=False)
    me.update()
    me.polygons.foreach_set("use_smooth", [False] * len(me.polygons))
    obj = bpy.data.objects.new(name, me)
    collection.objects.link(obj)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def replace_mesh(obj, verts, faces, smooth=False):
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
        if mat is not None:
            mesh.materials.append(mat)
    obj.data = mesh
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return mesh


def recalc_normals(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()


def set_bevel(obj, width):
    for mod in obj.modifiers:
        if mod.type == "BEVEL":
            mod.width = width
            mod.segments = 2
            return mod
    mod = obj.modifiers.new("WSK_Softened_Thorn_Edges", "BEVEL")
    mod.width = width
    mod.segments = 2
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(38.0)
    mod.harden_normals = True
    return mod


def set_props(obj, part, confidence, note, **extra):
    obj["wsk_part"] = part
    obj["wsk_confidence"] = confidence
    obj["wsk_prompt"] = PROMPT
    obj["wsk_note"] = note
    for key, value in extra.items():
        obj[key] = value


# --------------------------------------------------------------------------
# the thorn profile - one function, shared by the crown and the shoulder spikes
# --------------------------------------------------------------------------


def thorn_geometry(base, normal, direction, length, width, depth, curve=None,
                   max_root=None):
    """A planted thorn: buried root, flared base on the surface, concave taper.

    `base` is where the thorn's axis leaves the mounting surface and `normal`
    is the surface normal there.  The root depth is solved from the angle
    between the thorn and that normal, so however obliquely the thorn leaves
    the metal, the rings below the base stay at least ROOT_CLEARANCE under it -
    the reason a leaning thorn looks mounted instead of stuck on.

    Returns (verts, faces, root_depth, cos_alpha, tip).
    """
    d = Vector(direction).normalized()
    n = Vector(normal).normalized()
    cos_a = max(d.dot(n), 0.20)
    sin_a = math.sqrt(max(0.0, 1.0 - cos_a * cos_a))
    u = d.cross(Vector((0.0, 0.0, 1.0)))
    if u.length < 1e-5:
        u = d.cross(Vector((1.0, 0.0, 0.0)))
    u.normalize()
    v = d.cross(u).normalized()
    cvec = Vector(curve) if curve else Vector((0.0, 0.0, 0.0))

    w_max = max(width, depth)
    root = max((ROOT_CLEARANCE + 0.85 * w_max * sin_a) / cos_a / 0.55, 0.004)
    # The solved root buries the base rings properly, but it must not run into
    # the head or any other part: the caller caps it with the room actually
    # available behind the surface.
    if max_root is not None:
        root = max(min(root, max_root), 0.0035)

    def axis(t):
        s = max(t, 0.0)
        return base + d * t + cvec * (length * (s / length) ** 2.2)

    stations = []
    for kind, t, rf in PROFILE:
        stations.append((t * root if kind == "root" else t * width,
                         rf * width, rf * depth))
    for tf, rf in TAPER:
        stations.append((tf * length, rf * width, rf * depth))

    verts, faces, rings = [], [], []
    for t, ru, rv in stations:
        p = axis(t)
        ids = []
        for k in range(SIDES):
            a = 2.0 * math.pi * k / SIDES + math.pi / SIDES
            ids.append(len(verts))
            verts.append(p + u * (ru * math.cos(a)) + v * (rv * math.sin(a)))
        rings.append(ids)
    tip = len(verts)
    verts.append(axis(length))
    faces.append(tuple(reversed(rings[0])))
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(SIDES):
            faces.append((a[k], a[(k + 1) % SIDES], b[(k + 1) % SIDES], b[k]))
    last = rings[-1]
    for k in range(SIDES):
        faces.append((last[k], last[(k + 1) % SIDES], tip))
    return verts, faces, root, cos_a, axis(length)


# --------------------------------------------------------------------------
# planting and length fitting
# --------------------------------------------------------------------------


def plant(mount_tree, theta_deg, z, standoff=0.45):
    """Base point and outward surface normal on the helmet at (theta, z).

    Where the ray lands on a knife edge - the crest's leading edge, for the
    centre blade - the triangle normal is sideways and useless as a mounting
    normal.  Those hits fall back to the ray direction itself, which is the
    surface a blade mounted there really is seated against.
    """
    th = math.radians(theta_deg)
    hdir = Vector((math.sin(th), math.cos(th), 0.0))
    origin = Vector((0.0, 0.0, z)) + hdir * standoff
    hit = mount_tree.ray_cast(origin, -hdir, standoff * 2.0)
    if hit[0] is None:
        return None, None, False
    p, n = hit[0].copy(), hit[1].copy()
    if n.length < 1e-6:
        n = hdir
    n.normalize()
    if n.dot(hdir) < 0.0:          # the outward normal points back at the ray
        n = -n
    fallback = n.dot(hdir) < 0.45  # a knife edge: normal across the ray
    if fallback:
        n = hdir
    return p, n.normalized(), fallback


def direction_from(tilt_deg, lean_deg):
    """A thorn direction from a tilt away from vertical and a lean azimuth."""
    t = math.radians(tilt_deg)
    p = math.radians(lean_deg)
    return Vector((math.sin(t) * math.sin(p), math.sin(t) * math.cos(p),
                   math.cos(t))).normalized()


def fit_length(base, direction, length, obstacles, clearance=0.0):
    """Longest thorn that clears every obstacle.

    The axis is walked outward in 1.5 mm steps; the first step that is inside an
    obstacle, or nearer to one than that obstacle's own margin, ends the thorn.
    The mounting surface carries a zero margin, so it is a penetration test
    rather than a clearance one.
    """
    d = Vector(direction).normalized()
    step = 0.0015
    t = 0.006
    while t <= length + 1e-9:
        p = base + d * t
        for name, tree, extra in obstacles:
            bad, _dist = inside_or_near(tree, p, clearance + extra)
            if bad:
                return max(t - step, 0.35 * length), name
        t += step
    return length, None


def room_behind(base, direction, obstacles, clearance):
    """How far the axis can run *backwards* from the base before it meets
    another part.  Keeps solved roots out of the head and the armour."""
    d = Vector(direction).normalized()
    step = 0.0015
    t = 0.002
    while t <= 0.25:
        p = base - d * t
        for name, tree, extra in obstacles:
            bad, _dist = inside_or_near(tree, p, clearance + extra)
            if bad:
                return max(t - step, 0.0), name
        t += step
    return 0.25, None


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    crown_col = bpy.data.collections["Crown"]
    root = bpy.data.objects[HEAD_ROOT]
    iron = bpy.data.materials[IRON]
    steel = bpy.data.materials[ARMOR_MAT]

    log, warnings = [], []
    mount_tree = bvh_of([SHELL, CREST, BAND])
    trees = {n: bvh_of(n) for n in (SHELL, CREST, BAND, FACE, GORGET, HALO,
                                    SPINE, MOUNT, BODY,
                                    "WSK_Armor_Chest_01", "WSK_Armor_Back_01")}
    for side in ("R", "L"):
        for part in ("Pauldron", "PauldronLame1", "PauldronLame2",
                     "PauldronLame3", "ShoulderSpike", "ShoulderSpikeFront",
                     "ShoulderSpikeRear", "ShoulderSpikeCrown",
                     "ShoulderSpikeFrontLow", "ShoulderSpikeRearLow"):
            name = f"WSK_Armor_{part}_{side}_01"
            if name in bpy.data.objects:
                trees[name] = bvh_of(name)
    # The mounting surfaces are tested for *penetration* only, not for
    # clearance: a thorn starts inside the shell, so a distance test would fire
    # on its own base.  Everything else keeps the full tip clearance.
    mount_names = (SHELL, CREST, BAND)
    obstacles = [(n, t, 0.0 if n in mount_names else TIP_CLEARANCE)
                 for n, t in trees.items()]

    # ---- remove the checkpoint-4 radial spikes ---------------------------
    removed = []
    for name in OLD_SPIKES:
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        mesh = obj.data
        removed.append(name)
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    log.append(f"removed {len(removed)} checkpoint-4 flat radial crown spikes")

    # ---- the crown -------------------------------------------------------
    thorns = []
    for row, table in (("A", ROW_A), ("B", ROW_B)):
        for spec in table:
            for side in ("C", "R", "L"):
                if (side == "C") != (spec["name"] == "C"):
                    continue
                sign = {"R": 1.0, "L": -1.0, "C": 0.0}[side]
                sym = spec.get("lean_sym", {}).get(side, {})
                # `theta` and `lean` are absolute side overrides, `tilt` and
                # `length` are deltas: a lean of 128 on the left means 128, not
                # 125 + 128
                theta = sym.get("theta", spec["theta"]) * sign
                tilt = spec["tilt"] + sym.get("tilt", 0.0)
                length_spec = spec["length"] * sym.get("length", 1.0)
                if row == "A":
                    # the base ring flares to 1.25 x the shaft radius, so the
                    # plant has to sit high enough above the band's top edge
                    # for that flare to clear it
                    flare = 1.25 * spec["w_ratio"] * length_spec * \
                        math.sin(math.radians(tilt))
                    z = spec["z"] + max(0.0, flare + 0.0045 - ROW_A_LIP)
                else:
                    z = spec["z"]
                lean = sym.get("lean", spec["lean"]) * sign
                length = spec["length"] * sym.get("length", 1.0)
                base, nrm, edge_hit = plant(mount_tree, theta, z)
                if base is None:
                    warnings.append(f"{side} row {row} {spec['name']}: no mount hit"
                                    f" at theta {theta:+.1f}, z {z:.3f}")
                    continue
                d = direction_from(tilt, lean)
                if not edge_hit and d.dot(nrm) < 0.22:   # keep the base seated
                    d = (d + nrm * (0.22 - d.dot(nrm))).normalized()
                width = spec["w_ratio"] * length
                depth = width * spec.get("d_ratio", DEPTH_RATIO)
                cdir = None
                if spec.get("curve"):
                    key, mag = spec["curve"]
                    cdir = {"back": Vector((0.0, -1.0, 0.0)),
                            "down": Vector((0.0, 0.0, -1.0)),
                            "out": Vector((nrm.x, nrm.y, 0.0)),
                            "up": Vector((0.0, 0.0, 1.0))}[key].normalized()
                    cdir = cdir * (length * mag)
                fit, blocker = fit_length(base, d, length, obstacles)
                if fit < length - 1e-6:
                    warnings.append(f"{side} row {row} {spec['name']}: length "
                                    f"{length:.3f} -> {fit:.3f} m (blocked by "
                                    f"{blocker})")
                if row == "A":
                    name = ("WSK_Helmet_CrownThorn_C_01" if side == "C" else
                            f"WSK_Helmet_CrownThorn_{side}{spec['name']}_01")
                else:
                    name = f"WSK_Helmet_CrownBarb_{side}{spec['name']}_01"
                # which of the three mounting surfaces this thorn actually
                # grows out of: its own wall may be crossed by the root, the
                # other two may not
                mount_here = min(mount_names,
                                 key=lambda n: nearest(trees[n], base)[2])
                room, blocker_b = room_behind(
                    base, d, [o for o in obstacles
                              if o[0] not in (mount_here,)],
                    0.5 * max(width, depth) + 0.002)
                verts, faces, root_depth, cos_a, tip = thorn_geometry(
                    base, nrm, d, fit, width, depth, curve=cdir, max_root=room)
                obj = new_mesh_object(name, verts, faces, crown_col, iron)
                recalc_normals(obj)
                set_bevel(obj, min(0.0009, 0.085 * width))
                obj.parent = root
                obj.matrix_parent_inverse = root.matrix_world.inverted()
                set_props(
                    obj,
                    ("crown thorn" if row == "A" else "crown barb") +
                    (", centre blade" if side == "C" else f", {side} side"),
                    "planted on the evaluated helmet (ray cast base); length "
                    "fitted against the helmet, the shoulders and the body",
                    spec["note"] + f".  Base ({base.x:+.4f}, {base.y:+.4f}, "
                    f"{base.z:+.4f}), axis ({d.x:+.3f}, {d.y:+.3f}, {d.z:+.3f}). "
                    "Scale local Z to change the length, rotate to re-aim.",
                    wsk_row=row, wsk_plant_theta_deg=round(theta, 2),
                    wsk_plant_z=round(z, 4), wsk_tilt_deg=round(tilt, 1),
                    wsk_lean_deg=round(lean, 1), wsk_length_m=round(fit, 4),
                    wsk_length_nominal_m=round(length, 4),
                    wsk_base_radius_m=round(width, 5),
                    wsk_base_depth_m=round(depth, 5),
                    wsk_root_depth_m=round(root_depth, 5),
                    wsk_mount=mount_here,
                    wsk_base=[round(v, 5) for v in base],
                    wsk_normal=[round(v, 5) for v in nrm],
                    wsk_axis=[round(v, 4) for v in d],
                    wsk_tip=[round(v, 4) for v in tip],
                    wsk_curve_m=round(cdir.length, 4) if cdir else 0.0)
                thorns.append(obj)
                log.append(f"{name}: L {fit:.3f} m ({length:.3f} nominal), "
                           f"base ({base.x:+.3f},{base.y:+.3f},{base.z:+.3f}) "
                           f"tilt {tilt:.0f} lean {lean:+.0f}  tip "
                           f"({tip.x:+.3f},{tip.y:+.3f},{tip.z:+.3f})")
    log.append(f"built {len(thorns)} crown thorns")

    # ---- shoulder spikes --------------------------------------------------
    shoulder = []
    for side, sign in GROUPS:
        pauldron = bpy.data.objects[f"WSK_Armor_Pauldron_{side}_01"]
        plate = bvh_of(pauldron.name)
        # a spike may not be stopped by the plate it grows out of, nor by its
        # neighbours in the same stack
        own = {n for n in trees if n.endswith(f"_{side}_01")}
        spike_obstacles = [(n, t, 0.0025) for n, t in trees.items()
                           if n not in own]
        for spec in SHOULDER_SPIKES:
            name = spec["name"].format(S=side)
            obj = bpy.data.objects.get(name)
            if obj is None or "wsk_spike_base" not in obj:
                warnings.append(f"{name}: missing or has no prompt-7 seat")
                continue
            sym = spec.get("sym", {}).get(side, {})
            seat = Vector(obj["wsk_spike_base"])          # prompt-7 seat point
            el = math.radians(spec["el"])
            yaw = math.radians(spec["yaw"] + sym.get("yaw", 0.0))
            d = Vector((sign * math.cos(el) * math.cos(yaw),
                        math.cos(el) * math.sin(yaw),
                        math.sin(el))).normalized()
            # re-seat: the point where this axis leaves the pauldron
            hit = plate.ray_cast(seat + d * 0.30, -d, 0.60)
            if hit[0] is None:
                p, n = seat + d * 0.010, Vector((d.x, d.y, 0.0)).normalized()
            else:
                p, n = hit[0].copy(), hit[1].copy()
                if n.dot(d) < 0.0:
                    n = -n
                n.normalize()
            target = (spec["length"] * sym.get("length", 1.0)
                      * (SHOULDER_LOW_SHORTEN if spec["low"] else SHOULDER_SHORTEN))
            fit, blocker = fit_length(p, d, target, spike_obstacles)
            width = fit * (SHOULDER_W_RATIO * (0.80 if spec["low"] else 1.0))
            depth = width * SHOULDER_D_RATIO
            cdir = Vector((sign * 0.55, -0.35, 0.0)).normalized() * (fit * 0.09)
            room, blocker_b = room_behind(p, d, spike_obstacles,
                                          0.5 * max(width, depth) + 0.002)
            verts, faces, root_depth, cos_a, tip = thorn_geometry(
                p, n, d, fit, width, depth, curve=cdir, max_root=room)
            # the spike objects keep the identity world matrix prompt 7 gave
            # them (parent inverse = root inverse), so mesh space is world space
            replace_mesh(obj, verts, faces, smooth=False)
            recalc_normals(obj)
            set_bevel(obj, min(0.0009, 0.085 * width))
            set_props(obj, obj.get("wsk_part", "shoulder thorn") +
                      " (re-cut as a thorn in prompt 10)",
                      "planted on the evaluated pauldron (ray cast seat); length "
                      "fitted against the helmet, crown, torso and body",
                      f"re-cut in the crown's thorn profile at "
                      f"{SHOULDER_LOW_SHORTEN if spec['low'] else SHOULDER_SHORTEN:.0%} "
                      f"of the prompt-6 length, base radius {width * 1000:.1f} mm, "
                      f"root {root_depth * 1000:.1f} mm.  Seat ({p.x:+.4f}, "
                      f"{p.y:+.4f}, {p.z:+.4f}), axis ({d.x:+.3f}, {d.y:+.3f}, "
                      f"{d.z:+.3f}) - the prompt-7 elevation and yaw.",
                      wsk_length_m=round(fit, 4),
                      wsk_length_before_m=round(obj["wsk_spike_length_m"], 4),
                      wsk_base_radius_m=round(width, 5),
                      wsk_root_depth_m=round(root_depth, 5),
                      wsk_elevation_deg=spec["el"],
                      wsk_yaw_deg=round(spec["yaw"] + sym.get("yaw", 0.0), 1),
                      wsk_mount=pauldron.name,
                      wsk_axis=[round(v, 4) for v in d],
                      wsk_base=[round(v, 5) for v in p],
                      wsk_normal=[round(v, 5) for v in n],
                      wsk_tip=[round(v, 4) for v in tip])
            shoulder.append(obj)
            log.append(f"{name}: L {obj['wsk_length_before_m']:.3f} -> {fit:.3f} m, "
                       f"seat ({p.x:+.3f},{p.y:+.3f},{p.z:+.3f}), el {spec['el']:.0f} "
                       f"yaw {spec['yaw'] + sym.get('yaw', 0.0):+.0f}"
                       + (f", fitted against {blocker}" if blocker else ""))
    log.append(f"re-cut {len(shoulder)} shoulder spikes")

    crown_col["wsk_status"] = (f"Prompt 10 thorn crown: band, halo, spine, mount, "
                              f"{len(thorns)} planted thorns")
    write_text_blocks(thorns, shoulder, log + ["warning: " + w for w in warnings])
    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print("SAVED", DST)
    for line in log:
        print("  " + line)
    for w in warnings:
        print("  WARNING " + w)


# --------------------------------------------------------------------------
# text blocks
# --------------------------------------------------------------------------
NOTES = """WILDSHIFT KNIGHT - CROWN AND THORN NOTES (Prompt 10)
=====================================================

Scope: the helmet crown and the six spikes of each pauldron, nothing else.  No
particle effect, no glow, no texture work, no rig.  The helmet shell, crest,
face plate, gorget, band, halo, spine and mount keep the geometry they had in
checkpoint 9; the nine flat radial crown spikes of checkpoint 4 are gone.

THE CROWN - 21 planted thorns in two rows
-----------------------------------------
row A  11 crowns  WSK_Helmet_CrownThorn_{C,R1..R5,L1..L5}_01
  A circlet fan growing from the helmet immediately above the top edge of the
  brow band, the way a thorn crown grows out of a circlet:

      element       length   tilt   lean azimuth   base radius   root
      centre blade  0.195 m   4 deg  vertical        5.9 mm      27 mm
      pair 1        0.165 m  30 deg  +/-105 deg     12.4 mm    14-31 mm
      pair 2        0.142 m  44 deg  +/-112 deg     10.7 mm    16-17 mm
      pair 3        0.125 m  52 deg  +/-125 deg     10.6 mm    13-15 mm
      pair 4        0.115 m  62 deg  +/-145 deg    10.0 mm    13-14 mm
      pair 5        0.101 m  70 deg  +/-157 deg     9.2 mm     8-9 mm

  The centre blade is the design's peak (1.18 x the next element) and continues
  the crest line over the dome: it is planted on the crest's leading edge, which
  is what is really there at the front centre.  Reach then falls off steadily
  outwards while every pair leans further back than the pair in front of it.

row B  10 barbs   WSK_Helmet_CrownBarb_{R1..R5,L1..L5}_01
  Shorter barbs from below the band, 0.098-0.113 m long at 115-124 degrees of
  tilt with base radii of 7.8-8.6 mm: the front pairs hang down and forward past
  the cheek line, the rear pairs sweep back under and through the halo opening.

Band, halo, spine and mount are unchanged, so the ring still frames the head
from the front and still reads as the crown's backdrop from behind.  The thorns
are the crown; the ring is its setting.

WHY NOTHING FLOATS
------------------
1. The base is a ray cast.  `plant()` fires a horizontal ray from 0.45 m out at
   the thorn's azimuth and height and takes the first hit on the EVALUATED
   helmet (subdivided, solidified, mirrored) - shell, crest or band - so the
   base coordinate is a real point on a surface that is actually rendered.
2. The root depth is solved, not guessed.  A thorn leaving the surface at 60
   degrees needs a deeper root than one leaving it square on, or its base disc
   hangs in the air.  The depth comes from the angle between the thorn and the
   surface normal, and is then capped by the room actually available behind the
   surface, so no root can reach the head (closest approach 5.3 mm) while the
   shaft still crosses the wall it is mounted on.
3. The base flares.  The profile widens to 1.25 x the shaft radius at the
   surface and narrows again over the next few millimetres, so each thorn shows
   a forged foot instead of a cylinder pushed into the shell.  The plant height
   of row A is raised by the flare's own reach, so even the widest, most-tilted
   thorns keep air between their foot and the circlet (worst case 1.6 mm).
4. The length is fitted.  Before a thorn is built, its axis is walked outward in
   1.5 mm steps and stopped 2 mm before the first obstacle: band, crest, face
   plate, gorget, halo, spine, mount, shoulder armour, chest, back or body.
   Nothing was placed by eye and then found to intersect.

READING AGAINST THE REFERENCE
-----------------------------
`tools/crown_reference_probe.py` and `tools/crown_silhouette_read.py` put a
metric grid on the supplied views using Prompt 4's calibration (chin 1.736 m,
1.8323 mm/px, centre x = 429 px).  Read that way the reference crown is a dark
circlet band at Z 1.92-1.95 with thorns reaching +/-0.19 m sideways and up to
2.18-2.23 m - larger and much denser than the Prompt 6 schedule, which is why
Prompt 6 recorded a "head is narrow" deviation and asked for the hood, not a
crown rescale, to close it.  Checkpoint 10 keeps the approved silhouette budget
and spends it differently: tips 2.134 m (was 2.115), fan span 0.352 m (was
0.361, reference 0.42), lowest crown element 1.819 m (was 1.833, reference
1.80-1.82), and 21 planted thorns instead of 9 flat rays.

EDITING
-------
Each thorn is its own object with its own single-user mesh and an identity
transform, parented to WSK_Helmet_Root_01, so world space is its mesh space and
every thorn carries its base point, axis, tilt, lean, length, base radius and
root depth as custom properties.  Twelve distinct tilts, uneven azimuths and
five hand-written asymmetries keep the fan from reading as a mechanical repeat:
the left second and fourth thorns are 4-5 % longer, the left third barb 4 %
shorter and 2 degrees round, the left fourth thorn leans 3 degrees further
back, the right fifth thorn is 4 % shorter with its lean 3 degrees forward.
To change one thorn, scale its local Z (length) or rotate it (aim); to re-plant
it, edit its entry in ROW_A / ROW_B and re-run
`tools/bl.sh tools/build_crown_thorns.py`.

THE SHOULDER SPIKES
-------------------
The six spikes of each pauldron keep the seats, directions and left/right
differences Prompt 7 approved and are re-cut in the crown's thorn profile at
65 % of their prompt-6 length with a 13.5 % base radius: 0.070-0.123 m against
the crown's 0.098-0.195 m, so the shoulder fan is unmistakably the smaller
scale of the two.  Every spike keeps at least 12.7 mm of air to the body, the
torso armour, the helmet and its neighbours.  The upper arm, forearm, thigh,
shin and sabaton plates deliberately stay plain: the thorn language belongs to
the crown and the shoulder crown line only.
"""


def write_text_blocks(thorns, shoulder, log):
    text = NOTES + "\nBUILD LOG\n---------\n" + "\n".join(log) + "\n"
    block = bpy.data.texts.get("WSK_Crown_Thorn_Notes.txt")
    if block is None:
        block = bpy.data.texts.new("WSK_Crown_Thorn_Notes.txt")
    block.clear()
    block.write(text)
    notes = bpy.data.texts.get("WSK_Project_Notes.txt")
    if notes is not None and "PROMPT 10" not in notes.as_string():
        notes.write(
            "\n\nPROMPT 10 - CROWN AND ARMOUR SPIKES\n"
            "------------------------------------\n"
            f"Checkpoint 10 replaces the nine flat radial crown spikes of\n"
            f"checkpoint 4 with {len(thorns)} planted thorns in two rows and\n"
            f"re-cuts the {len(shoulder)} shoulder spikes of checkpoint 7 in the\n"
            "same profile.  The helmet shell, crest, face plate, gorget, band,\n"
            "halo, spine, mount, body, all other armour and the scene setup are\n"
            "unchanged.  See WSK_Crown_Thorn_Notes.txt.\n")


if __name__ == "__main__":
    main()
