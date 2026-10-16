"""Prompt 12 - selective engravings and gothic trim on the checkpoint-11 knight.

Opens `Wildshift_Knight_11_Medallion.blend` and adds a small, sparse set of
antique-gold trim ornaments at five chosen locations - and nowhere else:

    chest       WSK_Decor_ChestKeelTrim_01        a narrow gold line down the keel
                WSK_Decor_ChestChevron_L/R_01     one shallow chevron on the upper chest
    waist       WSK_Decor_BeltTrimTop_L/R_01      top-edge trim flanking the medallion
    helmet brow WSK_Decor_BrowTrim_L/R_01         trim along the brow band, flanking the crest
    knee        WSK_Decor_KneeRidge_L/R_01        a lanceolate boss on each knee cop
    shin        WSK_Decor_ShinRidge_L/R_01        a lanceolate ridge down each shin plate

and saves `Wildshift_Knight_12_ArmorDetails.blend`.  The eleven ornaments are
separate meshes in the Armor collection, each parented to the plate it decorates
with an identity local transform; every existing mesh - chest, belt, medallion,
crown, limbs, body, cape and weapon guides - keeps its geometry, its modifiers
and its material.  Nothing is applied, nothing is baked, no UVs or textures.

Construction
------------
Everything is a parametric swept solid built from measured numbers, in the same
style as the rest of the project - no booleans, no sculpting, no applied bevels.

* Each ornament is one reusable sweep: a six-point trim profile (flat seated
  back, drafted sides, chamfered crown) swept along a fitted path and capped at
  both ends, so every piece is a closed manifold solid.
* Every station of a path is a ray cast against the *evaluated* host plate.  The
  swept back face is seated 0.35-0.45 mm into the metal along the host's own
  surface normal, sampled across the full width so the trim follows the plate's
  rake and curvature instead of floating over it or diving into it.
* Widths, relief and end fades live in the constants at the top of the file;
  the knee and shin motifs are lens-tapered lanceolates (the crown thorn and
  medallion blade language), the rest are constant-width trims with faded ends.
* The only modifier is an unapplied 0.16 mm edge bevel on each ornament.

Design rules (the prompt's "sparse and readable" budget)
--------------------------------------------------------
* Five decorated locations out of the whole figure: chest, waist band, helmet
  brow, one knee pair, one shin pair.  No limb plate under the knee, no
  pauldron, no back, no fauld, no gauntlet, no sabaton is decorated.
* The trim is narrow (5.4-11 mm), shallow (1.6-2.2 mm of relief) and mirror
  symmetric about the centre line; the motifs are pure geometry - lines, one
  chevron, two lanceolates - no text, no emblems, no accidental lettering.
* One restrained placeholder material, MAT_Armor_AntiqueGold_01, already used
  by the Prompt 11 medallion, so the decoration reads against the blackened
  steel without any texture work.

Run:  tools/bl.sh tools/build_armor_details.py
"""
import math
import os

import bpy          # noqa: F401  (must be imported first: sets module paths)
import bmesh        # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_11_Medallion.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_12_ArmorDetails.blend")
PROMPT = "Prompt 12 - selective engravings and gothic trim"

GOLD = "MAT_Armor_AntiqueGold_01"
BEVEL_W = 0.00016

# hosts and the ornaments built on them
CHEST = "WSK_Armor_Chest_01"
BELT = "WSK_Armor_WaistBelt_01"
BAND = "WSK_Helmet_CrownBand_01"
KNEE_L, KNEE_R = "WSK_Armor_KneeCop_L_01", "WSK_Armor_KneeCop_R_01"
SHIN_L, SHIN_R = "WSK_Armor_Shin_L_01", "WSK_Armor_Shin_R_01"

# --------------------------------------------------------------------------
# measured host geometry (checkpoint 11, tools/probe_detail_surfaces*.py)
# --------------------------------------------------------------------------
# chest keel: front face Y 0.1409 (z 1.15) -> 0.1713 (z 1.56), meandering crest
KEEL_Z0, KEEL_Z1 = 1.155, 1.600
# chevron arm: apex next to the keel trim, arm climbing over the pectoral plane
CHEV_X0, CHEV_Z0 = 0.010, 1.450
CHEV_X1, CHEV_Z1 = 0.112, 1.560
# belt top edge at Z 1.105 (bevel above 1.1035); trim sits on the flat face below
BELT_TRIM_Z = 1.0965
BELT_TRIM_THETA0, BELT_TRIM_THETA1 = 10.0, 80.0    # degrees from +Y front
# brow band: front face lower edge Z 1.887-1.889, front top ~1.910, crest to |x| 0.0036
BROW_TRIM_Z = 1.8935
BROW_X0, BROW_X1 = 0.006, 0.082
# knee cop face (dome): available z 0.505-0.590 at x = +/-0.150
KNEE_X, KNEE_Z0, KNEE_Z1 = 0.150, 0.505, 0.590
# shin plate face: available z 0.372-0.470 at x = +/-0.170
SHIN_X, SHIN_Z0, SHIN_Z1 = 0.170, 0.372, 0.470

# --------------------------------------------------------------------------
# the ornament's own numbers (metres).  `seat` is how far the swept back face
# sinks into the host along the host normal, so nothing can read as floating.
# --------------------------------------------------------------------------
TRIM_PROFILE = ((-1.0, 0.0), (1.0, 0.0), (0.82, 0.62),
                (0.36, 1.0), (-0.36, 1.0), (-0.82, 0.62))
SPECS = {
    "keel":    dict(w=0.0032, h=0.0026, seat=0.00040),
    "chevron": dict(w=0.0028, h=0.0022, seat=0.00040),
    "belt":    dict(w=0.0030, h=0.0019, seat=0.00040),
    "brow":    dict(w=0.0027, h=0.0019, seat=0.00035),
    "knee":    dict(w=0.0050, h=0.0024, seat=0.00045),
    "shin":    dict(w=0.0055, h=0.0024, seat=0.00045),
}
LENS_TIP_W = 0.0005           # lanceolate tips never close to zero width
END_FADE = (0.50, 0.80)       # height scale of the first/last two stations
ORIGIN_OFF = 0.25             # how far the fitting ray starts outside the surface


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def set_props(obj, part, host, attachment, note, **extra):
    obj["wsk_part"] = part
    obj["wsk_host"] = host
    obj["wsk_attachment_hint"] = attachment
    obj["wsk_prompt"] = PROMPT
    obj["wsk_note"] = note
    for key, value in extra.items():
        obj[key] = value


def evaluated_world(obj):
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    mw = ev.matrix_world.copy()
    verts = [mw @ v.co for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    return verts, faces


def bvh_of(names):
    verts, faces = [], []
    for name in names:
        v, f = evaluated_world(bpy.data.objects[name])
        off = len(verts)
        verts += v
        faces += [tuple(i + off for i in face) for face in f]
    return BVHTree.FromPolygons(verts, faces, all_triangles=False)


def build_object(name, verts, faces, material):
    """Welded, outward-normaled mesh with one unapplied edge bevel."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    mesh.validate(verbose=False)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = abs(poly.normal.y) < 0.92
    obj = bpy.data.objects.new(name, mesh)
    bpy.data.collections["Armor"].objects.link(obj)
    mesh.materials.append(material)
    mod = obj.modifiers.new("WSK_Decor_EdgeBevel", "BEVEL")
    mod.width = BEVEL_W
    mod.segments = 2
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(38.0)
    mod.use_clamp_overlap = True
    return obj


def rings_to_mesh(rings):
    verts = [v for ring in rings for v in ring]
    n = len(rings[0])
    faces = []
    for i in range(len(rings) - 1):
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((i * n + k, (i + 1) * n + k, (i + 1) * n + k2, i * n + k2))
    faces.append(tuple(range(n - 1, -1, -1)))
    off = (len(rings) - 1) * n
    faces.append(tuple(off + k for k in range(n)))
    return verts, faces


# --------------------------------------------------------------------------
# reusable fitted trim sweep
# --------------------------------------------------------------------------
class Station:
    """One path station: nominal point, outward direction, width and height.

    `cast_dir` points away from the host surface; the fitting ray starts at
    `p + cast_dir * ORIGIN_OFF` and travels back along -cast_dir.
    """

    def __init__(self, p, cast_dir, w, h):
        self.p = Vector(p)
        self.cast_dir = Vector(cast_dir).normalized()
        self.w = w
        self.h = h


def sweep_trim(name, stations, tree, spec, material, log):
    """Sweep the trim profile along a fitted path; return the object.

    Every station is ray-cast against `tree` (the evaluated host plate).  The
    swept back face is seated `spec['seat']` into the metal along the host's own
    normal, so the trim follows the plate instead of floating above it.
    """
    seat = spec["seat"]
    fitted = []
    for i, st in enumerate(stations):
        # --- station frame -------------------------------------------------
        hit0 = tree.ray_cast(st.p + st.cast_dir * ORIGIN_OFF, -st.cast_dir, 2.0)
        if hit0[0] is None:
            raise RuntimeError(f"{name}: station {i} at {tuple(round(c, 4) for c in st.p)} misses its host")
        h0, n0 = hit0[0], hit0[1].normalized()
        if i + 1 < len(stations):
            t = stations[i + 1].p - st.p
        else:
            t = st.p - stations[i - 1].p
        t = t - n0 * t.dot(n0)
        if t.length < 1e-7:
            raise RuntimeError(f"{name}: station {i} path tangent parallel to the surface normal")
        t.normalize()
        u = n0.cross(t).normalized()
        # --- fit the back across the full width ---------------------------
        rear = []
        for s in (-1.0, 1.0):
            anchor = h0 + u * (s * st.w)
            hit = tree.ray_cast(anchor + n0 * ORIGIN_OFF, -n0, 0.5)
            if hit[0] is None:
                raise RuntimeError(f"{name}: station {i} width sample {s:+.0f} runs off the host")
            rear.append(hit[0] - hit[1].normalized() * seat)
        a, b = rear
        # never let the chord between the edge samples float over a concave
        # middle: sink the chord until it is at most 0.02 mm above the surface
        mid = (a + b) * 0.5
        float_mid = (mid - h0).dot(n0)
        if float_mid > 0.00002:
            sink = min(float_mid - 0.00002, 0.0013 - seat)   # bite stays < 1.3 mm
            a = a - n0 * sink
            b = b - n0 * sink
        fitted.append((a, b, n0))
    # --- build the rings --------------------------------------------------
    rings = []
    for st, (a, b, n0) in zip(stations, fitted):
        chord = b - a
        ring = []
        for u_frac, out_frac in TRIM_PROFILE:
            base = a + chord * ((u_frac + 1.0) * 0.5)
            ring.append(base + n0 * (out_frac * st.h))
        rings.append(ring)
    verts, faces = rings_to_mesh(rings)
    obj = build_object(name, verts, faces, material)
    log.append(f"  {name}: {len(stations)} stations, {len(verts)} verts, "
               f"w {max(s.w for s in stations) * 1000:.1f} mm, "
               f"h {max(s.h for s in stations) * 1000:.1f} mm, seat {seat * 1000:.1f} mm")
    return obj


def fade_stations(n):
    """Height-scale list with faded ends (constant-width trims)."""
    scales = [1.0] * n
    for i in range(min(2, n // 2)):
        scales[i] = END_FADE[i]
        scales[-1 - i] = END_FADE[i]
    return scales


def lens_shape(t):
    """Lanceolate width and height scale at path parameter t in [0, 1]."""
    lens = max(0.0, 4.0 * t * (1.0 - t))
    w_scale = max(LENS_TIP_W, lens ** 0.5)
    h_scale = 0.35 + 0.65 * lens ** 0.35
    return w_scale, h_scale


# --------------------------------------------------------------------------
# the five ornament groups
# --------------------------------------------------------------------------
def build_chest(log, tree, gold):
    spec = SPECS["keel"]
    n = 33
    zs = [KEEL_Z0 + (KEEL_Z1 - KEEL_Z0) * i / (n - 1) for i in range(n)]
    scales = fade_stations(n)
    stations = [Station((0.0, 1.0, z), (0.0, 1.0, 0.0), spec["w"], spec["h"] * s)
                for z, s in zip(zs, scales)]
    keel = sweep_trim("WSK_Decor_ChestKeelTrim_01", stations, tree, spec, gold, log)
    set_props(keel, "chest centre keel trim", CHEST, "chest / upper torso",
              "narrow antique-gold line seated on the cuirass keel crest, "
              f"Z {KEEL_Z0:.3f}-{KEEL_Z1:.3f}, faded ends",
              wsk_motif="line", wsk_host_object=CHEST, wsk_width_m=2 * spec["w"],
              wsk_relief_m=spec["h"], wsk_seat_m=spec["seat"])

    spec = SPECS["chevron"]
    n = 13
    chevrons = []
    for sign, label in ((1.0, "R"), (-1.0, "L")):
        stations = []
        scales = fade_stations(n)
        for i in range(n):
            t = i / (n - 1)
            x = sign * (CHEV_X0 + (CHEV_X1 - CHEV_X0) * t)
            z = CHEV_Z0 + (CHEV_Z1 - CHEV_Z0) * t
            stations.append(Station((x, 1.0, z), (0.0, 1.0, 0.0),
                                    spec["w"], spec["h"] * scales[i]))
        arm = sweep_trim(f"WSK_Decor_ChestChevron_{label}_01", stations, tree,
                         spec, gold, log)
        set_props(arm, f"upper chest chevron arm ({label})", CHEST, "chest / upper torso",
                  "shallow chevron arm over the pectoral plane, apex beside the "
                  "keel trim and faded ends",
                  wsk_motif="chevron", wsk_host_object=CHEST, wsk_width_m=2 * spec["w"],
                  wsk_relief_m=spec["h"], wsk_seat_m=spec["seat"],
                  wsk_mirror_pair=f"WSK_Decor_ChestChevron_{'L' if label == 'R' else 'R'}_01")
        chevrons.append(arm)
    return keel, chevrons


def build_belt(log, tree, gold):
    spec = SPECS["belt"]
    n = 16
    out = []
    for sign, label in ((1.0, "R"), (-1.0, "L")):
        stations = []
        scales = fade_stations(n)
        for i in range(n):
            t = i / (n - 1)
            deg = sign * (BELT_TRIM_THETA0 + (BELT_TRIM_THETA1 - BELT_TRIM_THETA0) * t)
            a = math.radians(deg)
            d = Vector((math.sin(a), math.cos(a), 0.0))
            stations.append(Station(d * 0.35 + Vector((0.0, 0.0, BELT_TRIM_Z)), d,
                                    spec["w"], spec["h"] * scales[i]))
        trim = sweep_trim(f"WSK_Decor_BeltTrimTop_{label}_01", stations, tree,
                          spec, gold, log)
        set_props(trim, f"waist band top-edge trim ({label})", BELT, "pelvis / waist",
                  f"narrow antique-gold edge trim on the belt's top edge, "
                  f"azimuth {sign * BELT_TRIM_THETA0:.0f}-{sign * BELT_TRIM_THETA1:.0f} deg, "
                  f"stopping clear of the medallion",
                  wsk_motif="edge trim", wsk_host_object=BELT, wsk_width_m=2 * spec["w"],
                  wsk_relief_m=spec["h"], wsk_seat_m=spec["seat"],
                  wsk_mirror_pair=f"WSK_Decor_BeltTrimTop_{'L' if label == 'R' else 'R'}_01")
        out.append(trim)
    return out


def build_brow(log, tree, gold):
    spec = SPECS["brow"]
    n = 10
    out = []
    for sign, label in ((1.0, "R"), (-1.0, "L")):
        stations = []
        scales = fade_stations(n)
        for i in range(n):
            t = i / (n - 1)
            x = sign * (BROW_X0 + (BROW_X1 - BROW_X0) * t)
            stations.append(Station((x, 0.6, BROW_TRIM_Z), (0.0, 1.0, 0.0),
                                    spec["w"], spec["h"] * scales[i]))
        trim = sweep_trim(f"WSK_Decor_BrowTrim_{label}_01", stations, tree,
                          spec, gold, log)
        set_props(trim, f"helmet brow band trim ({label})", BAND, "helmet brow",
                  f"narrow antique-gold trim along the brow band's front arc at "
                  f"Z {BROW_TRIM_Z:.4f}, clear of the centre crest",
                  wsk_motif="edge trim", wsk_host_object=BAND, wsk_width_m=2 * spec["w"],
                  wsk_relief_m=spec["h"], wsk_seat_m=spec["seat"],
                  wsk_mirror_pair=f"WSK_Decor_BrowTrim_{'L' if label == 'R' else 'R'}_01")
        out.append(trim)
    return out


def build_lanceolates(log, gold):
    """Knee and shin lanceolates; returns {host_name: ornament}."""
    out = {}
    for kind, x, z0, z1, hosts, attach in (
            ("KneeRidge", KNEE_X, KNEE_Z0, KNEE_Z1, (KNEE_R, KNEE_L), "knee"),
            ("ShinRidge", SHIN_X, SHIN_Z0, SHIN_Z1, (SHIN_R, SHIN_L), "shin / greave")):
        spec = SPECS["knee" if kind.startswith("Knee") else "shin"]
        n = 11 if kind.startswith("Knee") else 13
        for sign, host, label in ((1.0, hosts[0], "R"), (-1.0, hosts[1], "L")):
            tree = bvh_of([host])
            stations = []
            for i in range(n):
                t = i / (n - 1)
                w_scale, h_scale = lens_shape(t)
                z = z0 + (z1 - z0) * t
                stations.append(Station((sign * x, 1.0, z), (0.0, 1.0, 0.0),
                                        spec["w"] * w_scale, spec["h"] * h_scale))
            ridge = sweep_trim(f"WSK_Decor_{kind}_{label}_01", stations, tree,
                               spec, gold, log)
            set_props(ridge, f"{attach} lanceolate ridge ({label})", host, attach,
                      "lens-tapered antique-gold boss seated on the plate face; "
                      "same tapered-blade language as the crown thorns and the "
                      "medallion rays",
                      wsk_motif="lanceolate", wsk_host_object=host,
                      wsk_width_m=2 * spec["w"], wsk_relief_m=spec["h"],
                      wsk_seat_m=spec["seat"],
                      wsk_mirror_pair=f"WSK_Decor_{kind}_{'L' if label == 'R' else 'R'}_01")
            out[host] = ridge
    return out


# --------------------------------------------------------------------------
# notes
# --------------------------------------------------------------------------
NOTES = """WILDSHIFT KNIGHT - ARMOUR DETAIL NOTES (Prompt 12)
=================================================

Scope: a small, selective set of decorative trim on five chosen locations and
nothing else.  No UV work, no baked maps, no texture or complex material nodes,
no text or emblem, no change to the cape or the weapon.  Every checkpoint-11
mesh - the cuirass, the belt, the medallion, the crown, the limb plates, the
body, the guides - keeps its geometry, its modifiers and its material; the
eleven ornaments are new, separate meshes and the only modifier on them is an
unapplied 0.16 mm edge bevel.

WHERE THE DECORATION IS (and where it deliberately is not)
---------------------------------------------------------
    chest        WSK_Decor_ChestKeelTrim_01     6.4 mm gold line on the keel crest,
                                                Z 1.155-1.600, faded ends
                 WSK_Decor_ChestChevron_L/R_01  one shallow chevron over the
                                                pectoral planes, apex beside the
                                                keel trim at Z 1.450, arms out to
                                                |X| 0.112 at Z 1.560
    waist band   WSK_Decor_BeltTrimTop_L/R_01   6.0 mm edge trim on the belt's
                                                top edge at Z 1.0965, azimuth
                                                10-80 deg each side, stopping
                                                clear of the medallion
    helmet brow  WSK_Decor_BrowTrim_L/R_01      5.4 mm trim on the brow band's
                                                front arc at Z 1.8935, from
                                                |X| 0.006 (clear of the centre
                                                crest) to |X| 0.082
    knees        WSK_Decor_KneeRidge_L/R_01     10 mm lanceolate boss on the knee
                                                cop face, Z 0.505-0.590
    shins        WSK_Decor_ShinRidge_L/R_01     11 mm lanceolate ridge down the
                                                shin plate, Z 0.372-0.470

Nothing is decorated on the pauldrons, the upper arms, the forearms, the
gauntlets, the thighs, the sabatons, the back plate, the fauld panels or the
medallion itself: the waist already carries the sun ornament, and the crown
already carries the thorn language.

HOW THE TRIM SITS ON THE PLATES
-------------------------------
Each ornament is one reusable sweep of a six-point trim profile (flat seated
back, drafted sides, chamfered crown) along a path fitted to the host plate.
Every station ray-casts the *evaluated* host across the ornament's full width,
and the swept back face is seated 0.35-0.45 mm into the metal along the host's
own surface normal, so the trim follows the plate's rake and curvature - it is
grown out of the plate rather than balanced on it.  Where the host is convex
(across the keel crest or the knee dome) the swept back chord sinks a little
further into the metal; it is never allowed to lift more than 0.02 mm.

Each ornament is parented to the plate it decorates with an identity local
transform, so moving or posing a plate (the knee and shin plates already have
pose pivots) carries its trim with it.

MATERIAL
--------
One restrained placeholder: MAT_Armor_AntiqueGold_01, already used by the
Prompt 11 medallion (metallic 1.0, roughness 0.42, dark antique base, no
emission, no textures).  The trim reads against the blackened steel and the
broad iron without any texture work.
"""


def write_notes(log, ornaments):
    txt = bpy.data.texts.get("WSK_ArmorDetails_Notes.txt") or \
        bpy.data.texts.new("WSK_ArmorDetails_Notes.txt")
    body = NOTES + "\nBUILD LOG\n---------\n" + "\n".join("  " + line for line in log)
    body += "\n\nORNAMENT INVENTORY\n------------------\n"
    for o in ornaments:
        body += (f"  {o.name}: {len(o.data.vertices)} verts, "
                 f"{len(o.data.polygons)} faces, host {o['wsk_host']}\n")
    txt.from_string(body)


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------
def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    log = []
    gold = bpy.data.materials[GOLD]
    log.append(f"material {GOLD}: re-used Prompt 11 antique gold "
               f"(metallic {gold.metallic:.1f}, roughness {gold.roughness:.2f}), no new material")

    chest_tree = bvh_of([CHEST])
    belt_tree = bvh_of([BELT])
    band_tree = bvh_of([BAND])

    keel, chevrons = build_chest(log, chest_tree, gold)
    belt_trims = build_belt(log, belt_tree, gold)
    brow_trims = build_brow(log, band_tree, gold)
    lanceolates = build_lanceolates(log, gold)

    ornaments = [keel] + chevrons + belt_trims + brow_trims + list(lanceolates.values())
    hosts = {CHEST: [keel] + chevrons, BELT: belt_trims, BAND: brow_trims}
    hosts.update({host: [obj] for host, obj in lanceolates.items()})

    # ---- parenting: each ornament follows its own plate --------------------
    bpy.context.view_layer.update()
    before = {}
    for o in ornaments:
        step = max(1, len(o.data.vertices) // 8)
        before[o.name] = [tuple(round(c, 6) for c in (o.matrix_world @ v.co))
                          for v in list(o.data.vertices)[::step]]
    for host_name, objs in hosts.items():
        host = bpy.data.objects[host_name]
        inv = host.matrix_world.inverted()
        for obj in objs:
            obj.parent = host
            obj.matrix_parent_inverse = inv
    bpy.context.view_layer.update()
    for obj in ornaments:
        step = max(1, len(obj.data.vertices) // 8)
        after = [tuple(round(c, 6) for c in (obj.matrix_world @ v.co))
                 for v in list(obj.data.vertices)[::step]]
        if after != before[obj.name]:
            raise RuntimeError(f"{obj.name} moved when parented to its host")
    log.append(f"parented {len(ornaments)} ornaments to their host plates "
               f"with identity local transforms; world placement unchanged")

    # ---- notes -----------------------------------------------------------
    write_notes(log, ornaments)

    arm = bpy.data.collections["Armor"]
    arm["wsk_status"] = ("Prompt 12 selective trim: 11 antique-gold ornament meshes "
                         "at five locations (chest, waist band, helmet brow, knees, shins)")
    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print("SAVED", DST)
    for line in log:
        print("  " + line)


if __name__ == "__main__":
    main()
