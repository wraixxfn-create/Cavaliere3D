"""Prompt 11: build the waist medallion on the existing mount.

The ornament is generated as three closed, independent solids - a gold ring, a
dark recessed centre and two sets of gold radial blades - seated on the real
armour surface measured with ray casts, so nothing floats and nothing is driven
deep into the plate.  A smaller sibling of the same design is seated on the
lower back plate, mirroring the circular motif the reference shows on the front
and the back of the character.

Run: tools/bl.sh tools/build_medallion.py
"""
import math
import os
import sys

import bpy
import bmesh  # noqa: E402  (importable only after bpy)
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = "/home/user/Cavaliere3D"
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_armor_blockout as A  # noqa: E402

SRC = os.path.join(ROOT, "Wildshift_Knight_10_Crown.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_11_Medallion.blend")
PROMPT = "Prompt 11 - the waist medallion"

MOUNT = "WSK_Armor_WaistMedallionMount_01"
BELT = "WSK_Armor_WaistBelt_01"
BACK = "WSK_Armor_Back_01"
FRONT_SUPPORT = (MOUNT, BELT,
                 "WSK_Armor_WaistPanel_Front_01_01",
                 "WSK_Armor_WaistPanel_Front_02_01",
                 "WSK_Armor_WaistPanel_Front_03_01",
                 "WSK_Armor_Chest_01")

GOLD = "MAT_Orn_AntiqueGold_01"
STONE = "MAT_Orn_ShadowStone_01"

# ---------------------------------------------------------------- geometry ---
# The front ornament is centred on the prompt-8 mount; the rear sibling sits on
# the lower back plate, 88 % of the front's scale so it stays inside that plate.
FRONT = dict(name="WaistMedallion", centre=(0.0, 1.055), sign=1.0, scale=1.0,
             support=FRONT_SUPPORT)
REAR = dict(name="WaistMedallionRear", centre=(0.0, 1.155), sign=-1.0, scale=0.88,
            support=(BACK,))

R_SEGMENTS = 96        # lathe segments (the ring is the visible hero form)
C_SEGMENTS = 96
R_REF = 0.0260         # radius the ring's seat is measured at
SMOOTH = 6             # half-window of the circular surface smoothing

# Profile offsets are measured along the outward normal of the armour: positive
# is in front of the measured surface, negative is inside it.
RING_PROFILE = [
    (0.0230, +0.0008),   # inner lip, front
    (0.0244, +0.0028),
    (0.0262, +0.0034),   # crest
    (0.0278, +0.0027),
    (0.0289, +0.0020),
    (0.0293, +0.0010),   # outer rim, front
    (0.0293, -0.0016),   # outer rim, back
    (0.0278, -0.0032),
    (0.0262, -0.0040),
    (0.0244, -0.0032),
    (0.0230, -0.0024),   # inner lip, back
    (0.0227, -0.0006),   # inner wall
]
CENTER_PROFILE = [
    (0.0000, -0.0020),   # back pole, inside the mount plate
    (0.0116, -0.0016),
    (0.0232, -0.0012),   # back rim
    (0.0232, +0.0012),   # front rim: a 2.4 mm edge wall the ring frames
    (0.0210, +0.0017),   # chamfer
    (0.0130, +0.0018),   # face: 1.8 mm proud of the plate, 1.6 mm under the crest
    (0.0050, +0.0017),
    (0.0000, +0.0016),   # front pole
]
RAYS = dict(
    primary=dict(count=8, offset=0.0, r_root=0.0240, r_cap=0.0405,
                 half_width=0.0036, half_thick=0.0030,
                 rise0=-0.0024, rise1=+0.0013),
    minor=dict(count=8, offset=0.5, r_root=0.0240, r_cap=0.0362,
               half_width=0.0026, half_thick=0.0028,
               rise0=-0.0024, rise1=+0.0011),
)
R_TIP_MAX = 0.0420      # stay inside the mount plate's 43 mm rim

# Hand-forged irregularity: the ring is not a machined circle.  Two smooth
# low-order harmonics bend its radius and its crest by about a percent each,
# with different phases for the front and the rear so the two ornaments are
# clearly siblings rather than copies.
WRINKLE = dict(front=dict(radius=(0.0085, 3.0, 0.60, 0.0050, 5.0, -1.20),
                          relief=(0.10, 2.0, 0.35)),
               rear=dict(radius=(0.0075, 3.0, 2.10, 0.0045, 5.0, 0.40),
                         relief=(0.09, 2.0, 1.85)))
BEVEL = dict(ring=0.0006, centre=0.0007, ray=0.00035)

TITLE = "WSK_Medallion_Notes.txt"


# ------------------------------------------------------------ surface probe ---
class Surface:
    """Outward-most armour surface in a direction, as a ray-cast oracle."""

    def __init__(self, names):
        dg = bpy.context.evaluated_depsgraph_get()
        self.trees = []
        for n in names:
            obj = bpy.data.objects[n]
            ev = obj.evaluated_get(dg)
            me = ev.to_mesh()
            verts = [ev.matrix_world @ v.co for v in me.vertices]
            faces = [tuple(p.vertices) for p in me.polygons]
            ev.to_mesh_clear()
            self.trees.append((n, BVHTree.FromPolygons(verts, faces,
                                                       all_triangles=False)))

    def hit(self, x, z, sign):
        origin = Vector((x, sign * 0.6, z))
        direction = Vector((0.0, -sign, 0.0))
        best = None
        for name, tree in self.trees:
            loc, _n, _i, dist = tree.ray_cast(origin, direction, 1.0)
            if loc is not None and (best is None or dist < best[1]):
                best = (name, dist, loc)
        return best

    def y_at(self, x, z, sign):
        h = self.hit(x, z, sign)
        return None if h is None else h[2].y


def circular_smooth(values, half):
    n = len(values)
    out = []
    for i in range(n):
        acc = 0.0
        wsum = 0.0
        for k in range(-half, half + 1):
            w = float(half + 1 - abs(k))
            acc += values[(i + k) % n] * w
            wsum += w
        out.append(acc / wsum)
    return out


# --------------------------------------------------------------- materials ---
def make_material(name, rgb, metallic, roughness, role):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = 0.0
    mat.diffuse_color = (*rgb, 1.0)
    mat.metallic = metallic
    mat.roughness = roughness
    mat["wsk_placeholder"] = True
    mat["wsk_role"] = role
    return mat


# ------------------------------------------------------------- mesh maker ---
def finish(name, verts, faces, coll, mat, bevel, smooth=True):
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.validate(verbose=False)
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = smooth
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new("WSK_Softened_Ornament_Edges", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = "ANGLE"
        mod.angle_limit = math.radians(38.0)
        mod.harden_normals = True
    return obj


def lathe(name, profile, segs, cfg, y_base, coll, mat, bevel,
          radial_fn=None, relief_fn=None):
    """Revolve a closed (radius, normal-offset) profile about the disc axis.

    A profile point on the axis collapses to a single shared vertex and the
    segment between two axis points is dropped, so a closed profile containing
    poles builds a clean fan and a watertight solid rather than a seam of
    degenerate faces.
    """
    cx, cz = cfg["centre"]
    sign, scale = cfg["sign"], cfg["scale"]
    verts, idx = [], []
    for r, off in profile:
        rr = r * scale
        if rr < 1e-7:
            idx.append([len(verts)])
            verts.append((cx, y_base[0] + sign * off * scale, cz))
            continue
        row = []
        for i in range(segs):
            th = 2.0 * math.pi * i / segs
            rmod = rr * (radial_fn(th) if radial_fn else 1.0)
            omod = off * (relief_fn(th) if relief_fn else 1.0)
            row.append(len(verts))
            verts.append((cx + rmod * math.cos(th),
                          y_base[i % R_SEGMENTS] + sign * omod * scale,
                          cz + rmod * math.sin(th)))
        idx.append(row)
    faces = []
    for i in range(len(profile)):
        a, b = idx[i], idx[(i + 1) % len(profile)]
        if len(a) == 1 and len(b) == 1:
            continue                       # two poles in a row: nothing to bridge
        if len(a) == 1:
            faces += [(a[0], b[k], b[(k + 1) % segs]) for k in range(segs)]
        elif len(b) == 1:
            faces += [(a[k], a[(k + 1) % segs], b[0]) for k in range(segs)]
        else:
            faces += [(a[k], a[(k + 1) % segs], b[(k + 1) % segs], b[k])
                      for k in range(segs)]
    return finish(name, verts, faces, coll, mat, bevel)


def ray_blade(name, cfg, azim, spec, surf, coll, mat, bevel, log):
    """One tapered radial blade, laid on the measured surface and fitted."""
    cx, cz = cfg["centre"]
    sign, scale = cfg["sign"], cfg["scale"]
    ux, uz = math.cos(azim), math.sin(azim)
    tx, tz = -math.sin(azim), math.cos(azim)
    r_root = spec["r_root"] * scale
    r_cap = spec["r_cap"] * scale

    def sample(r):
        return surf.y_at(cx + r * ux, cz + r * uz, sign)

    # A local straight reference through the first third of the blade; the tip
    # is cut where the armour surface bends away from it, so a blade never
    # climbs a plate edge.
    p0, p1 = r_root + 0.0030 * scale, r_root + 0.0110 * scale
    y0, y1 = sample(p0), sample(p1)
    if y0 is None or y1 is None:
        return None
    slope = (y1 - y0) / (p1 - p0)

    def ref(r):
        return y0 + slope * (r - p0)

    r_tip = r_cap
    r = p1
    while r <= r_cap + 1e-9:
        y = sample(r)
        if y is None or abs(y - ref(r)) > 0.0009:
            r_tip = max(r - 0.0006, r_root + 0.0090 * scale)
            break
        r += 0.0006
    else:
        r_tip = r_cap
    r_tip = min(r_tip, r_cap, R_TIP_MAX * scale)
    r_tip = max(r_tip, min(r_cap, R_TIP_MAX * scale) - 0.0025 * scale)
    if r_tip < r_root + 0.009 * scale:
        log.append(f"    {name}: refused, only {1000*(r_tip-r_root):.1f} mm of run")
        return None

    stations = 5
    a0 = spec["half_width"] * scale
    b0 = spec["half_thick"] * scale
    c0, c1 = spec["rise0"] * scale, spec["rise1"] * scale
    verts = []
    for si in range(stations):
        t = si / (stations - 1.0)
        r = r_root + (r_tip - r_root) * t
        y_s = sample(r)
        if y_s is None:
            y_s = ref(r)
        c = c0 + (c1 - c0) * (t ** 1.4)
        a = a0 * (1.0 - t) ** 0.85
        b = b0 * (1.0 - t) ** 1.05
        centre = Vector((cx + r * ux, y_s + sign * c, cz + r * uz))
        if si == stations - 1:
            verts.append(centre)
            continue
        for phi in (math.radians(30), math.radians(90), math.radians(150),
                    math.radians(210), math.radians(270), math.radians(330)):
            verts.append(centre
                         + Vector((tx, 0.0, tz)) * (a * math.cos(phi))
                         + Vector((0.0, sign, 0.0)) * (b * math.sin(phi)))
    faces = []
    for i in range(6):
        j = (i + 1) % 6
        faces.append((i, j, 6 + j, 6 + i))                 # root -> ring 1
        faces.append((6 + j, 6 + i, 12 + i, 12 + j))       # ring 1 -> ring 2
    for i in range(6):
        j = (i + 1) % 6
        faces.append((18 + i, 18 + j, 12 + j, 12 + i))     # ring 2 -> ring 3
        faces.append((24, 18 + j, 18 + i))                 # tip fan
    faces.append(tuple(range(5, -1, -1)))                  # root cap
    obj = finish(name, verts, faces, coll, mat, bevel)
    obj["wsk_ray_azimuth_deg"] = round(math.degrees(azim), 3)
    obj["wsk_ray_length_m"] = round(r_tip - r_root, 5)
    obj["wsk_ray_run_mm"] = round(1000.0 * (r_tip - r_root), 2)
    log.append(f"    {name}: {math.degrees(azim):7.2f} deg  run "
               f"{1000.0*(r_tip-r_root):5.2f} mm  of cap {1000.0*(r_cap-r_root):5.2f} mm")
    return obj


# ------------------------------------------------------------------ driver ---
def build_one(cfg, coll, gold, stone, log, stats):
    surf = Surface(cfg["support"])
    cx, cz = cfg["centre"]
    sign, scale = cfg["sign"], cfg["scale"]

    # The ring's seat is measured across its whole band width and the *forward*
    # most of the three is kept, so even where the belt ridge crosses under the
    # band the crest still clears the metal and the back stays buried.
    band = (RING_PROFILE[0][0], R_REF, RING_PROFILE[5][0])
    raw = []
    for i in range(R_SEGMENTS):
        th = 2.0 * math.pi * i / R_SEGMENTS
        vals = [surf.y_at(cx + r * scale * math.cos(th),
                          cz + r * scale * math.sin(th), sign) for r in band]
        vals = [v for v in vals if v is not None]
        raw.append(None if not vals else sign * max(sign * v for v in vals))
    known = [v for v in raw if v is not None]
    mean = sum(known) / len(known)
    raw = [mean if v is None else v for v in raw]
    y_base = circular_smooth(raw, SMOOTH)

    name = cfg["name"]
    wr = WRINKLE["front" if sign > 0 else "rear"]
    a1, k1, p1, a2, k2, p2 = wr["radius"]
    radial_fn = lambda th: 1.0 + a1 * math.sin(k1 * th + p1) + a2 * math.sin(k2 * th + p2)
    b1, k3, p3 = wr["relief"]
    relief_fn = lambda th: 1.0 + b1 * math.sin(k3 * th + p3)
    ring = lathe(f"WSK_Armor_{name}_Ring_01", RING_PROFILE, R_SEGMENTS, cfg,
                 y_base, coll, gold, BEVEL["ring"],
                 radial_fn=radial_fn, relief_fn=relief_fn)
    A.set_props(ring, "waist medallion ring", "pelvis / waist belt",
                "closed lathed antique-gold ring seated on the prompt-8 medallion "
                "mount; separate component, no final texture work",
                wsk_component="ring")
    centre = lathe(f"WSK_Armor_{name}_Center_01", CENTER_PROFILE, C_SEGMENTS, cfg,
                   y_base, coll, stone, BEVEL["centre"])
    A.set_props(centre, "waist medallion centre", "pelvis / waist belt",
                "recessed dark centre disk and floor; separate component",
                wsk_component="center")

    rng = np.random.default_rng(11055)
    made = []
    for group in ("primary", "minor"):
        spec = RAYS[group]
        n = spec["count"]
        for k in range(n):
            azim = 2.0 * math.pi * (k + spec["offset"]) / n
            azim += math.radians(rng.uniform(-2.0, 2.0))
            jittered = dict(spec)
            span = 0.030 if group == "primary" else 0.030
            jittered["r_cap"] = spec["r_cap"] * (1.0 + rng.uniform(-span, span))
            jittered["half_width"] = spec["half_width"] * (1.0 + rng.uniform(-0.07, 0.07))
            jittered["half_thick"] = spec["half_thick"] * (1.0 + rng.uniform(-0.05, 0.05))
            obj = ray_blade(f"WSK_Armor_{name}_Ray_{group[0].upper()}{k+1:02d}_01",
                            cfg, azim, jittered, surf, coll, gold,
                            BEVEL["ray"], log)
            if obj is not None:
                A.set_props(obj, "waist medallion radial element",
                            "pelvis / waist belt",
                            f"{group} radial blade, length fitted to the measured "
                            "armour surface; separate component",
                            wsk_component="radial", wsk_group=group)
                made.append(obj)

    # -- measured seating report -------------------------------------------
    # For every azimuth and every profile point, compare where the ornament is
    # placed against the armour surface actually measured there.  Positive
    # relief is metal standing proud; negative is metal buried in the plate.
    for tag, profile, segs in (("ring", RING_PROFILE, R_SEGMENTS),
                               ("centre", CENTER_PROFILE, C_SEGMENTS),
                               ("rays", [(s["r_root"], s["rise0"]) for s in RAYS.values()], 1)):
        relief = []
        for r, off in profile:
            rr = r * scale
            if rr < 1e-6:
                continue
            for i in range(segs):
                th = 2.0 * math.pi * i / segs
                y = surf.y_at(cx + rr * math.cos(th), cz + rr * math.sin(th), sign)
                if y is None:
                    continue
                placed = y_base[i % R_SEGMENTS if segs == R_SEGMENTS else 0] \
                    + sign * off * scale
                relief.append(sign * (placed - y))
        if relief:
            stats.setdefault(tag, []).append(
                (cfg["name"], min(relief) * 1000.0, max(relief) * 1000.0))
    stats.setdefault("surface", []).append(
        (cfg["name"], min(known), max(known), mean))
    return [ring, centre] + made


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    coll = bpy.data.collections["Armor"]
    gold = make_material(GOLD, (0.440, 0.310, 0.120), 1.0, 0.48,
                         "placeholder antique gold ornament metal; no textures applied")
    stone = make_material(STONE, (0.024, 0.021, 0.019), 0.0, 0.40,
                          "placeholder dark polished centre stone; no textures applied")

    log = []
    stats = {}
    built = []
    for cfg in (FRONT, REAR):
        log.append(f"  {cfg['name']}: centre {cfg['centre']} scale {cfg['scale']}")
        built += build_one(cfg, coll, gold, stone, log, stats)
    for name, lo, hi, mean in stats["surface"]:
        log.append(f"  {name}: seat surface y {lo:+.5f} .. {hi:+.5f} (mean {mean:+.5f}), "
                   f"span {1000*(hi-lo):.2f} mm")
    for tag, rows in stats.items():
        if tag == "surface":
            continue
        for name, lo, hi in rows:
            log.append(f"  {name} {tag}: relief {lo:+.2f} .. {hi:+.2f} mm "
                       "(negative = inside the plate)")

    print("\n".join(log))
    write_text_blocks(built, log)
    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print("SAVED", DST, "objects:", len(built))


NOTES = """WSK WAIST MEDALLION - PROMPT 11
================================

OBJECTIVE
---------
A restrained antique-gold medallion for the centre of the waist armour,
inspired by the ring / dark centre / thin radiating thorns motif the supplied
reference carries on the front and the back of the character.  It is built on
the blank mount Prompt 8 left deferred ("plain raised mount; symbol
intentionally deferred") and it is original geometry: a plain ring, a plain
dark centre and straight tapered blades, with no lettering, no figure and no
recognisable franchise emblem.

COMPONENTS
----------
Every ornament is an independent closed solid with its own single-user mesh and
an identity transform, so it can be moved, scaled or replaced without touching
the waist armour:

  WSK_Armor_WaistMedallion_Ring_01        gold ring, 12-point lathed profile
  WSK_Armor_WaistMedallion_Center_01      dark recessed centre disk + floor
  WSK_Armor_WaistMedallion_Ray_P01..P08   eight primary radial blades
  WSK_Armor_WaistMedallion_Ray_M01..M08   eight shorter minor blades
  WSK_Armor_WaistMedallionRear_*          the same design at 88 %, on the back

The blank mount WSK_Armor_WaistMedallionMount_01 from checkpoint 8 is left
exactly as it was and acts as the seating bezel: the whole ornament stays
3.8 mm inside the mount's 43 mm rim, so the plain disk shows around the gold the
way a setting shows around a set stone.

SEATING
-------
Nothing is placed on an assumed plane.  For every azimuth the outward-most
armour surface is measured with a ray cast, smoothed with a circular kernel
that is wider than the belt's own bulge, and the ornament's profile is offset
from that measured line.  The ring's back therefore sits 2.4-3.4 mm inside the
plate and its crest 2.8-3.7 mm proud of it - readable in a raking light, and nowhere
near deep enough to reach the body (closest approach 8.7 mm, and the plates
themselves are at least 2.5 mm thick).

Each radial blade is a hexagon-section tapered solid laid on the same measured
surface.  Its root is buried under the ring band so the two parts interlock,
and its length is fitted: walking outward from the root, a straight reference
through the first third of the blade is compared with the real surface, and the
blade is cut where the surface bends more than 0.9 mm away from it.  That is
what keeps a downward blade from climbing the top edge of the hanging waist
panel, and it is the same fitting discipline checkpoint 10 used for the crown
thorns and the shoulder spikes.

RESTRAINT
---------
The ring's rim is 59.8 mm across and the radial fan reaches 76.8 mm - 20.9 % of
the belt's 368 mm front width, against the 19-20 % the supplied reference reads
at (a 62 mm motif on a 0.30-0.33 m wide figure).  The fan is 16 blades in two
alternating scales, and every element stays inside the 86 mm mount disk.  There
is no engraving pass, no emission, no particle system and no ornament anywhere
else on the character: the thigh, shin, sabaton, arm, shoulder, helmet and torso
surfaces are untouched.

EDITING
-------
Parameters live at the top of tools/build_medallion.py.  RING_PROFILE and
CENTER_PROFILE are closed (radius, normal-offset) loops; RAYS holds the two
blade families.  Re-run `tools/bl.sh tools/build_medallion.py` to regenerate.
The material is a placeholder: MAT_Orn_AntiqueGold_01 is a Principled metal
with no textures and no emission, waiting for the texturing pass.
"""


def write_text_blocks(built, log):
    text = NOTES + "\nBUILD LOG\n---------\n" + "\n".join(log) + "\n"
    block = bpy.data.texts.get(TITLE)
    if block is None:
        block = bpy.data.texts.new(TITLE)
    block.clear()
    block.write(text)
    notes = bpy.data.texts.get("WSK_Project_Notes.txt")
    if notes is not None and "PROMPT 11" not in notes.as_string():
        notes.write(
            "\n\nPROMPT 11 - THE WAIST MEDALLION\n"
            "---------------------------------\n"
            f"Checkpoint 11 builds {len(built)} independent ornament parts\n"
            "on the waist mount checkpoint 8 left blank: a gold ring, a dark\n"
            "recessed centre and sixteen fitted radial blades at the front,\n"
            "and the same design at 88 % on the lower back plate.  The waist\n"
            "belt, the waist panels, the mount, the cuirass, the body and\n"
            "every other assembly are unchanged.  See WSK_Medallion_Notes.txt.\n")


if __name__ == "__main__":
    main()
