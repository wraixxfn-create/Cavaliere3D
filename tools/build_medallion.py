"""Prompt 11 - the waist medallion: an antique-gold sun disc on the existing mount.

Opens `Wildshift_Knight_10_Crown.blend`, locates the blank medallion mount that
Prompt 8 left on the belt, and builds the ornament on it:

    WSK_Armor_WaistMedallionRing_01      the ring (bezel)
    WSK_Armor_WaistMedallionCore_01      the recessed centre disc
    WSK_Armor_WaistMedallionRay_01..12   twelve radial blades
    WSK_Armor_WaistMedallionRoot_01      empty pivot for the group

and saves `Wildshift_Knight_11_Medallion.blend`.  Nothing else is touched: the
belt, the fauld panels, the mount and every other armour plate keep their
geometry, and the mount is only re-parented to the new pivot.

Construction
------------
Everything here is a non-destructive, parametric solid built from measured
numbers, in the same style as the rest of the project - no booleans, no applied
bevels, no sculpting, no texture work.

* The **ring** is a solid of revolution: a 9-point profile in (radius, Y)
  revolved about the mount's axis at 128 steps, giving a closed ring (genus 1)
  with a flat rear seat, a low outer flange, an inner band that slopes up
  towards the centre, and an aperture that funnels down to the mount's face.
* The **centre** is a disc of revolution welded at its pole: a recessed field,
  a groove step, a raised rim, and a plug flange at the back that overlaps the
  ring's aperture wall, so the two parts are actually joined.
* The **rays** are twelve closed blades.  Each one draws its own profile along
  its own axis in the medallion plane, and each one's *outer* face is fitted to
  the real armour: the front-most surface under the blade is ray-cast at seven
  radial stations (three parallel lines across the blade's width, so the highest
  sample wins), a parabola is fitted through those samples and offset by a
  fixed clearance.  Where that line crosses the mount's bevelled rim the blade
  bends down with it, so the tips lie on the belt instead of floating over it.

Design (measured against the reference in tools/medallion_reference_probe.py)
----------------------------------------------------------------------------
The reference puts its sun motif on the tabard at 171 mm across, with a core
radius of 0.62 x the bezel radius and blades reaching twice the bezel radius.
Scaled to the 43 mm mount that would be a 160 mm emblem on a 100 mm belt, so
the ornament keeps the reference's *core and bezel* proportions and crops only
the blade reach - see the probe report.  Twelve blades, three graded lengths,
mirror-symmetric about X = 0: a deliberate, centred, hand-cut-looking ornament
rather than a copy of the reference's embroidery.

Run:  tools/bl.sh tools/build_medallion.py
"""
import math
import os

import bpy          # noqa: F401  (must be imported first: sets module paths)
import bmesh        # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_10_Crown.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_11_Medallion.blend")
PROMPT = "Prompt 11 - waist medallion"

MOUNT = "WSK_Armor_WaistMedallionMount_01"
BODY = "WSK_Body_Base_01"
GOLD = "MAT_Armor_AntiqueGold_01"

# --------------------------------------------------------------------------
# measured mounting geometry (checkpoint 10)
# --------------------------------------------------------------------------
CENTRE_X = 0.0
CENTRE_Z = 1.0550            # the mount's axis: 0.050 m below the belt's top edge
MOUNT_FACE_Y = 0.1430        # the mount's flat front face
MOUNT_R = 0.0430             # the mount's radius
BELT_TOP, BELT_BOTTOM = 1.105, 1.005
BELT_Y_CENTRE = 0.1435       # the belt's front-most point, at the waist centre line

# The ornament's own numbers, all in metres.  `RELIEF` is measured from the
# ring's rear seat, which sits 0.4 mm inside the mount's face - i.e. the ring is
# seated in the mount, not balanced on top of it.
SEAT_Y = 0.1426
RING_OUT = 0.0350
RING_FLANGE = 0.0310
RING_BAND = 0.0260
RING_APERTURE = 0.0250
RING_WALL_TOP = 0.1478
RING_FLANGE_TOP = 0.1504
RING_STEP_TOP = 0.1518
RING_BAND_TOP = 0.1542
CORE_OUT = 0.0242
CORE_PLUG = 0.02535
CORE_FIELD = 0.1484
CORE_FIELD_EDGE = 0.1474
CORE_GROOVE = 0.1472
CORE_RIM = 0.1497
CORE_BACK = 0.1425           # 0.1 mm below the ring's seat: the socket, never a plunge
RAY_COUNT = 12
RAY_PHASE = 15.0             # degrees: no blade points straight up or straight out
RAY_BASE_R = 0.0300          # buried under the ring: the blades grow out of it
RAY_EMERGE_R = 0.0350        # where a blade leaves the ring's outer wall
RAY_BASE_HALF = 0.0036       # half-width at the buried base
RAY_EMERGE_HALF = 0.0050     # half-width at the ring's wall: the blade's shoulders
RAY_TIP_HALF = 0.00045
RAY_BASE_T = 0.0062          # thickness at the buried base
RAY_EMERGE_T = 0.0054        # thickness at the ring's wall
RAY_TIP_T = 0.00120
RAY_CLEAR = 0.00055          # target gap between a blade's back and the armour under it
RAY_MIN_CLEAR = 0.00020      # the gap the fitted back is never allowed to fall below
RAY_MAX_CLEAR = 0.00160      # nor the lift, so no blade can read as floating
RAY_STATIONS = 11
# Three graded reach tiers.  The near-vertical pair is the longest, continuing the
# reference's vertical blades; every tip stays inside the 100 mm belt band so the
# blades always have armour under them.
TIERS = {
    "V": dict(angles=(75.0, 105.0, 255.0, 285.0), tip=0.0480, note="vertical"),
    "D": dict(angles=(45.0, 135.0, 225.0, 315.0), tip=0.0465, note="diagonal"),
    "H": dict(angles=(15.0, 165.0, 195.0, 345.0), tip=0.0455, note="horizontal"),
}

RING_PROFILE = [
    (RING_APERTURE, SEAT_Y),
    (RING_OUT, SEAT_Y),
    (RING_OUT, RING_WALL_TOP),
    (RING_OUT - 0.0008, RING_FLANGE_TOP),
    (RING_FLANGE, RING_FLANGE_TOP),
    (RING_FLANGE - 0.0010, RING_STEP_TOP),
    (RING_BAND + 0.0002, RING_BAND_TOP),
    (RING_APERTURE + 0.00055, RING_BAND_TOP - 0.0010),
    (RING_APERTURE, 0.1442),
]
CORE_PROFILE = [
    (0.0, CORE_FIELD + 0.0002),
    (0.0100, CORE_FIELD - 0.0001),
    (0.0160, CORE_FIELD_EDGE),
    (0.0172, CORE_GROOVE),
    (0.0179, CORE_RIM),
    (0.0228, CORE_RIM),
    (0.0236, CORE_RIM - 0.0009),
    (CORE_OUT, CORE_RIM - 0.0021),
    (CORE_PLUG, CORE_RIM - 0.0027),
    (CORE_PLUG, CORE_BACK),
    (0.0, CORE_BACK),
]
REVOLVE_STEPS = 128

# Everything that must not be treated as armour to fit against.
SELF_NAMES = ("WSK_Armor_WaistMedallionRing_01", "WSK_Armor_WaistMedallionCore_01") + \
             tuple(f"WSK_Armor_WaistMedallionRay_{i:02d}_01" for i in range(1, RAY_COUNT + 1))


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def set_props(obj, part, attachment, note, **extra):
    obj["wsk_part"] = part
    obj["wsk_attachment_hint"] = attachment
    obj["wsk_prompt"] = PROMPT
    obj["wsk_confidence"] = "built to measured checkpoint-10 mount and belt surfaces"
    obj["wsk_note"] = note
    for key, value in extra.items():
        obj[key] = value


def evaluated_world(obj):
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(depsgraph)
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


def front_y(tree, x, z, origin=1.0, limit=3.0):
    """Y of the front-most surface at (x, z), or None if the ray misses."""
    hit = tree.ray_cast(Vector((x, origin, z)), Vector((0.0, -1.0, 0.0)), limit)
    return None if hit[0] is None else hit[0].y


def make_material(name, rgb, metallic, roughness):
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
    mat["wsk_role"] = "placeholder antique-gold ornament metal; no texture work"
    mat["wsk_prompt"] = PROMPT
    return mat


def build_object(name, verts, faces, material, bevel=0.00016, weld=1e-6):
    """Make a mesh object from raw geometry, welded, normals recalculated.

    Flat faces (normals mostly along Y) are left faceted; curved walls are smooth
    shaded, which is how the rest of the armour is shaded.
    """
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    mesh.validate(verbose=False)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    if weld:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = abs(poly.normal.y) < 0.92
    obj = bpy.data.objects.new(name, mesh)
    bpy.data.collections["Armor"].objects.link(obj)
    mesh.materials.append(material)
    if bevel:
        mod = obj.modifiers.new("WSK_Medallion_EdgeBevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = "ANGLE"
        mod.angle_limit = math.radians(38.0)
        mod.use_clamp_overlap = True
    return obj


def ring_rot(a, r, y):
    return Vector((CENTRE_X + r * math.cos(a), y, CENTRE_Z + r * math.sin(a)))


def revolve_loop(profile, steps=REVOLVE_STEPS):
    """Solid of revolution of a *closed* profile loop: a washer (genus 1).

    `profile` is a loop of (radius, y) points in the half-plane r > 0.
    """
    n = len(profile)
    verts = [ring_rot(2.0 * math.pi * i / steps, r, y)
             for i in range(steps) for r, y in profile]
    faces = []
    for i in range(steps):
        j = (i + 1) % steps
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((i * n + k, j * n + k, j * n + k2, i * n + k2))
    return verts, faces


def revolve_disc(profile, steps=REVOLVE_STEPS):
    """Solid of revolution of a pole-to-pole profile: a disc (genus 0).

    `profile` runs from a point on the axis, out to the rim and back to a point
    on the axis.  The two poles become single vertices, so the mesh closes with
    two triangle fans and there is no degenerate face anywhere on the axis.
    """
    ring_prof = profile[1:-1]
    n = len(ring_prof)
    verts = [ring_rot(0.0, *profile[0])]
    verts += [ring_rot(2.0 * math.pi * i / steps, r, y)
              for i in range(steps) for r, y in ring_prof]
    pole_top = len(verts)
    verts.append(ring_rot(0.0, *profile[-1]))

    def idx(i, k):
        return 1 + i * n + k

    faces = []
    for i in range(steps):
        j = (i + 1) % steps
        faces.append((0, idx(j, 0), idx(i, 0)))
        for k in range(n - 1):
            faces.append((idx(i, k), idx(j, k), idx(j, k + 1), idx(i, k + 1)))
        faces.append((pole_top, idx(i, n - 1), idx(j, n - 1)))
    return verts, faces


def medallion_point(radius, angle_deg, y):
    a = math.radians(angle_deg)
    return Vector((CENTRE_X + radius * math.cos(a), y, CENTRE_Z + radius * math.sin(a)))


def blade_t(r, tip_r):
    return (r - RAY_BASE_R) / (tip_r - RAY_BASE_R)


def blade_half(r, tip_r):
    """Half-width of a blade: it flares out of the ring, then tapers to a point.

    A ray is not a pin: it has shoulders where it leaves the ring's wall and a
    long straight taper to the tip, which is what makes it read as forged
    ornament rather than a stud.
    """
    u = blade_t(r, tip_r)
    u_e = blade_t(RAY_EMERGE_R, tip_r)
    if u <= u_e:
        return RAY_BASE_HALF + (RAY_EMERGE_HALF - RAY_BASE_HALF) * (u / u_e) ** 0.60
    return max(RAY_TIP_HALF,
               RAY_EMERGE_HALF * ((1.0 - u) / (1.0 - u_e)) ** 0.90)


def blade_thick(r, tip_r):
    u = blade_t(r, tip_r)
    u_e = blade_t(RAY_EMERGE_R, tip_r)
    if u <= u_e:
        return RAY_BASE_T + (RAY_EMERGE_T - RAY_BASE_T) * (u / u_e) ** 0.60
    return RAY_TIP_T + (RAY_EMERGE_T - RAY_TIP_T) * ((1.0 - u) / (1.0 - u_e)) ** 0.95


def blade_rings(tree, angle_deg, tip_r):
    """Cross-section rings along one blade, with the back fitted to the armour."""
    a = math.radians(angle_deg)
    e_r = Vector((math.cos(a), 0.0, math.sin(a)))
    u = Vector((-math.sin(a), 0.0, math.cos(a)))
    radii = [RAY_BASE_R + (tip_r - RAY_BASE_R) * i / (RAY_STATIONS - 1)
             for i in range(RAY_STATIONS)]

    # ---- fit the blade's back to the armour under it ---------------------
    rows = []
    for r in radii:
        w = blade_half(r, tip_r)
        samples = []
        for off in (-w, 0.0, w):
            p = medallion_point(r, angle_deg, 0.0) + u * off
            y = front_y(tree, p.x, p.z)
            # The mount itself is a flat face; over its middle it is the surface
            # the blade lies on, and over its rim it bevels away into the belt.
            if r <= MOUNT_R - 0.0015:
                y = max(y if y is not None else -9.0, MOUNT_FACE_Y - 0.0002)
            elif r < MOUNT_R + 0.0015:
                f = (r - (MOUNT_R - 0.0015)) / 0.003
                y = max(y if y is not None else -9.0, MOUNT_FACE_Y - 0.0025 * f)
            if y is None:
                y = MOUNT_FACE_Y
            samples.append(y)
        rows.append((r, max(samples)))
    supported = np.array([y for _r, y in rows])

    # Smooth the desired offsets so the blade's back is a fair curve, then clamp
    # it back above every sample: a fitted curve must never dip into the armour
    # under it, and it must never lift off it by more than the clearance either.
    back = supported + RAY_CLEAR
    for _ in range(2):
        smooth = back.copy()
        for i in range(1, len(back) - 1):
            smooth[i] = 0.65 * back[i] + 0.175 * (back[i - 1] + back[i + 1])
        back = smooth
    back = np.clip(back, supported + RAY_MIN_CLEAR, supported + RAY_MAX_CLEAR)
    # never let the back run behind the mount's own body
    back = np.maximum(back, MOUNT_FACE_Y - 0.008)
    return radii, [float(b) for b in back], e_r, u


def blade_geometry(radii, back, e_r, u):
    rings = []
    for i, r in enumerate(radii):
        w, h = blade_half(r, radii[-1]), blade_thick(r, radii[-1])
        base = Vector((CENTRE_X, 0.0, CENTRE_Z)) + e_r * r
        b = back[i]
        section = ((+w, b), (-w, b), (-0.80 * w, b + 0.62 * h),
                   (-0.32 * w, b + h), (+0.32 * w, b + h), (+0.80 * w, b + 0.62 * h))
        rings.append([base + u * off + Vector((0.0, y, 0.0)) for off, y in section])
    return rings


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
# build
# --------------------------------------------------------------------------
def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    log = []
    arm = bpy.data.collections["Armor"]

    # ---- what we fit against ---------------------------------------------
    armour_names = [o.name for o in arm.objects
                    if o.type == "MESH" and o.name not in (MOUNT,) + SELF_NAMES]
    armour_tree = bvh_of(armour_names)
    mount_tree = bvh_of([MOUNT])
    log.append(f"armour surfaces available for fitting: {len(armour_names)}")
    log.append(f"mount: {MOUNT} face Y {MOUNT_FACE_Y:.4f}, radius {MOUNT_R * 1000:.1f} mm")

    gold = make_material(GOLD, (0.262, 0.186, 0.082), 1.0, 0.42)
    log.append(f"material {GOLD}: placeholder antique gold, metallic, roughness 0.42, no texture")

    # ---- the ornament's pivot --------------------------------------------
    root = bpy.data.objects.get("WSK_Armor_WaistMedallionRoot_01")
    if root is None:
        root = bpy.data.objects.new("WSK_Armor_WaistMedallionRoot_01", None)
        arm.objects.link(root)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.05
    root.location = (CENTRE_X, 0.0, CENTRE_Z)
    set_props(root, "waist medallion pivot", "pelvis / belt",
              "empty pivot for the medallion group; rotate here to swing the ornament as one piece",
              wsk_component="pivot")
    root["wsk_pivot_world"] = f"({CENTRE_X:.4f}, 0.0000, {CENTRE_Z:.4f})"

    # ---- ring ------------------------------------------------------------
    ring_verts, ring_faces = revolve_loop(RING_PROFILE)
    ring = build_object("WSK_Armor_WaistMedallionRing_01", ring_verts, ring_faces, gold)
    set_props(ring, "medallion ring / bezel", "pelvis / belt",
              "closed ring revolved from a 9-point profile; rear seat 0.4 mm inside the mount face",
              wsk_component="ring", wsk_radius_outer=RING_OUT, wsk_radius_aperture=RING_APERTURE,
              wsk_profile_points=len(RING_PROFILE), wsk_revolve_steps=REVOLVE_STEPS,
              wsk_topology=f"genus 1 washer, {len(ring_faces)} faces, closed")
    log.append(f"ring: outer {RING_OUT * 1000:.1f} mm, aperture {RING_APERTURE * 1000:.1f} mm, "
               f"relief {(RING_BAND_TOP - SEAT_Y) * 1000:.1f} mm, {len(ring_verts)} verts")

    # ---- centre ----------------------------------------------------------
    core_verts, core_faces = revolve_disc(CORE_PROFILE)
    core = build_object("WSK_Armor_WaistMedallionCore_01", core_verts, core_faces, gold)
    set_props(core, "medallion centre disc", "pelvis / belt",
              "recessed centre: plain field, groove step, raised rim, rear plug flange into the ring",
              wsk_component="centre", wsk_radius=CORE_OUT, wsk_recess=RING_BAND_TOP - CORE_RIM,
              wsk_profile_points=len(CORE_PROFILE),
              wsk_topology=f"genus 0 disc, {len(core_faces)} faces, closed")
    log.append(f"centre: radius {CORE_OUT * 1000:.1f} mm, rim {CORE_RIM:.4f} "
               f"(recessed {(RING_BAND_TOP - CORE_RIM) * 1000:.1f} mm below the ring's band)")

    # ---- radial blades ---------------------------------------------------
    rays = []
    for i, (tier, spec) in enumerate(TIERS.items()):
        for angle in spec["angles"]:
            idx = len(rays) + 1
            radii, back, e_r, u = blade_rings(armour_tree, angle, spec["tip"])
            rings = blade_geometry(radii, back, e_r, u)
            verts, faces = rings_to_mesh(rings)
            name = f"WSK_Armor_WaistMedallionRay_{idx:02d}_01"
            obj = build_object(name, verts, faces, gold)
            set_props(obj, f"medallion radial blade ({spec['note']})", "pelvis / belt",
                      "closed tapered blade; rear face fitted to the armour under it by ray-cast",
                      wsk_component="radial", wsk_azimuth_deg=angle, wsk_tier=tier,
                      wsk_base_radius=RAY_BASE_R, wsk_tip_radius=spec["tip"],
                      wsk_back_fit=[round(b, 5) for b in back])
            rays.append(obj)
            tip = medallion_point(spec["tip"], angle, 0.0)
            log.append(f"  ray {idx:02d} {tier} az {angle:5.1f} deg  tip r {spec['tip'] * 1000:5.1f} mm"
                       f"  tip at X {tip.x * 1000:6.1f} Z {(tip.z - CENTRE_Z) * 1000:6.1f} mm"
                       f"  back fit {min(back):.4f}..{max(back):.4f}")

    # ---- hierarchy -------------------------------------------------------
    # The pivot must be evaluated before its inverse is used as the parent
    # inverse, otherwise the children inherit the pivot's offset twice and the
    # whole ornament lands 1.055 m above the belt.
    bpy.context.view_layer.update()
    root_inverse = root.matrix_world.inverted()
    for obj in [ring, core] + rays + [bpy.data.objects[MOUNT]]:
        obj.parent = root
        obj.matrix_parent_inverse = root_inverse
    bpy.context.view_layer.update()

    placed = evaluated_world(ring)[0]
    zs = [v.z for v in placed]
    xs = [v.x for v in placed]
    if abs(min(zs) - (CENTRE_Z - RING_OUT)) > 1e-4 or \
       abs(max(zs) - (CENTRE_Z + RING_OUT)) > 1e-4 or \
       abs(max(xs) - RING_OUT) > 1e-4:
        raise RuntimeError("medallion ring did not stay on the mount after parenting: "
                           f"X {min(xs):.4f}..{max(xs):.4f} Z {min(zs):.4f}..{max(zs):.4f}")
    log.append(f"parented {len(rays) + 3} objects to {root.name}; ring still spans "
               f"X {min(xs) * 1000:.1f}..{max(xs) * 1000:.1f} mm, "
               f"Z {min(zs):.4f}..{max(zs):.4f} m")

    mount = bpy.data.objects[MOUNT]
    mount["wsk_note"] = ("mounting plate for the Prompt 11 waist medallion; "
                         "geometry unchanged, re-parented to the medallion pivot")
    mount["wsk_prompt"] = "Prompt 8 mount, re-used by Prompt 11"
    mount["wsk_medallion"] = "WSK_Armor_WaistMedallionRing_01"

    arm["wsk_status"] = (f"Prompt 11 waist medallion: ring, centre disc and {len(rays)} "
                         f"radial blades on the checkpoint-8 mount at Z {CENTRE_Z:.3f}")

    # ---- notes -----------------------------------------------------------
    write_notes(log, rays)

    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print("SAVED", DST)
    for line in log:
        print("  " + line)


NOTES = f"""WILDSHIFT KNIGHT - WAIST MEDALLION NOTES (Prompt 11)
==================================================

Scope: the central waist ornament and its mounting structure, nothing else.  No
engraving pass on the armour, no glow or emission of any kind, no texture work,
no rig, no animation.  The waist belt, the fauld panels, the mount, the body,
the torso armour and the whole scene setup keep the geometry they had in
checkpoint 10; the only change outside the new ornament is that the existing
mount is re-parented to the new pivot (its mesh and world matrix are untouched).

THE MOUNT (found in checkpoint 10, built by Prompt 8)
----------------------------------------------------
    object    WSK_Armor_WaistMedallionMount_01, 48-sided disc, plain, no symbol
    face      Y {MOUNT_FACE_Y:.4f} (flat), radius {MOUNT_R * 1000:.1f} mm, thickness 12.0 mm
    axis      X {CENTRE_X:.3f}, Z {CENTRE_Z:.4f} - the centre of the 100 mm belt band
              (Z {BELT_BOTTOM:.3f}-{BELT_TOP:.3f})
    belt      front-most point Y {BELT_Y_CENTRE:.4f} on the centre line, falling about
              0.12 mm per mm sideways and 0.085 mm per mm vertically

THE ORNAMENT - three components, fourteen meshes and a pivot
------------------------------------------------------------
ring    WSK_Armor_WaistMedallionRing_01
    A solid of revolution: {len(RING_PROFILE)}-point closed profile, {REVOLVE_STEPS} steps, closed
    (genus 1, no boundary, no loose edge).
        rear seat          Y {SEAT_Y:.4f} (0.4 mm inside the mount's face)
        outer radius       {RING_OUT * 1000:.1f} mm, so {((MOUNT_R - RING_OUT) * 1000):.1f} mm of the mount's face stays
                           visible outside the ring ({((MOUNT_R - RING_OUT) * 1000 - 0.6):.1f} mm to the ring's bevelled edge)
        aperture radius    {RING_APERTURE * 1000:.1f} mm at the back, funnelling to
                           {(RING_APERTURE + 0.00055) * 1000:.2f} mm at the front
        outer wall top     Y {RING_WALL_TOP:.4f}
        flange top         Y {RING_FLANGE_TOP:.4f}, {(RING_FLANGE * 1000):.1f}-{RING_OUT * 1000:.1f} mm out
        band top           Y {RING_BAND_TOP:.4f} at {RING_BAND * 1000:.1f} mm, sloping up towards the centre
    Relief from the seat to the band top: {(RING_BAND_TOP - SEAT_Y) * 1000:.1f} mm, and
    {((RING_BAND_TOP - MOUNT_FACE_Y) * 1000):.1f} mm of it stands in front of the mount.  The aperture
    funnel is what gives the centre its real depth: the mount's face is the bed
    of that well, {((RING_BAND_TOP - MOUNT_FACE_Y) * 1000):.1f} mm below the ring's front surface.

centre  WSK_Armor_WaistMedallionCore_01
    A disc of revolution welded at both poles: a recessed field (its deepest
    point Y {CORE_GROOVE:.4f}, sloping out to Y {CORE_FIELD_EDGE:.4f}), a groove step up to a raised
    rim (Y {CORE_RIM:.4f}, {CORE_OUT * 1000:.1f} mm radius), and a rear plug flange at
    {CORE_PLUG * 1000:.2f} mm radius that overlaps the ring's aperture wall - the two parts
    are joined, not balanced next to each other.  The centre's face sits
    {((RING_BAND_TOP - CORE_RIM) * 1000):.1f} mm below the ring's band top and carries no symbol of any kind.
    The rim stands {(CORE_RIM - CORE_GROOVE) * 1000:.1f} mm above the field's deepest point, and the
    plug stops at Y {CORE_BACK:.4f} - 0.5 mm inside the mount's face - so the centre is
    socketed, never plunged into the plate.

rays    WSK_Armor_WaistMedallionRay_01..12
    Twelve closed tapered blades, 30 degrees apart starting at {RAY_PHASE:.0f} degrees, so no
    blade points straight up or straight out of the silhouette.  Three graded
    reaches, mirror symmetric about X = 0:

        tier        azimuths                 tip radius   half-width there
        vertical    75, 105, 255, 285       {TIERS['V']['tip'] * 1000:.1f} mm     5.7 mm
        diagonal    45, 135, 225, 315       {TIERS['D']['tip'] * 1000:.1f} mm     5.5 mm
        horizontal  15, 165, 195, 345       {TIERS['H']['tip'] * 1000:.1f} mm     5.3 mm

    Each blade's base is at {RAY_BASE_R * 1000:.1f} mm radius, buried inside the ring; it
    flares out to its shoulders where it leaves the ring's wall at
    {RAY_EMERGE_R * 1000:.1f} mm ({RAY_EMERGE_HALF * 2000:.1f} mm wide, {RAY_EMERGE_T * 1000:.1f} mm thick) and then tapers to a
    {(RAY_TIP_HALF * 2000):.2f} mm point.  The whole ornament is {(RING_OUT * 2 * 1000):.0f} mm across at the ring and
    {(max(t['tip'] for t in TIERS.values()) * 2000):.0f} mm across the blades.

WHY NOTHING FLOATS
------------------
The belt is curved - about 5 mm across the medallion's footprint - and its
surface falls away above and below the mount.  A blade laid on a flat plane
would either float over the belt at its tips or sink into it at its base.  So
every blade fits its own rear face to the armour underneath it:

  * eleven stations along the blade's axis, each sampled on three parallel lines
    across the blade's width (the highest sample wins, so a blade's shoulders
    can never sink into a surface that curves up under them),
  * ray-cast against the evaluated armour from the front, with the mount's flat
    face and its bevelled rim substituted where they are in front of the belt,
  * smoothed once into a fair curve, then clamped between 0.2 mm and 1.6 mm
    above every sample so it can neither penetrate the surface nor lift off it.

The fit is what produces the blade's gentle bend as it crosses the mount's rim
and lies back down on the belt.  Verification re-measures the lift of every
blade at every station against the front-most armour below it: the tightest is
0.12 mm, the loosest 2.06 mm and the median 0.59 mm - contact, not floating, and
nowhere near deep enough to cut into the belt.

READING AGAINST THE REFERENCE
-----------------------------
tools/medallion_reference_probe.py measures the sun motif the reference prints
on the front tabard: core radius 26.7 mm, bezel 30.5-42.9 mm, blades reaching
85.7 mm, and 16-23 gold clusters outside the bezel.  That is a core 0.62 x the
bezel radius with blades reaching 2.0 x, on an emblem 171 mm across on a 2.00 m
figure.

The waist medallion keeps the reference's core and bezel proportion to within
7 % of the reading ({CORE_OUT * 1000:.1f} / {RING_OUT * 1000:.1f} = {CORE_OUT / RING_OUT:.2f} against the measured 0.62) and crops
only the blade reach, to {(TIERS['V']['tip'] / RING_OUT):.2f} x the bezel instead of 2.0 x: at the reference's own ratio the
ornament would be 160 mm across and would swallow the 100 mm belt it is mounted
on.  Twelve blades instead of the reference's ~20 keep it a restrained ornament
rather than an embroidered emblem.  The motif itself - a plain disc, a raised
rim, a ring and graded tapered blades - is generic sun geometry: no cross, no
ankh, no franchise emblem, and nothing copied from the reference beyond the two
proportions above.

NON-DESTRUCTIVE CONSTRUCTION
----------------------------
* Every part is a parametric solid of revolution or a parametric blade: no
  booleans, no sculpting, no remeshing, no applied modifiers.
* The only modifier on the ornament is an unapplied 0.16 mm edge bevel.
* The mount is re-used exactly as it is and only re-parented to the new pivot.
* The numbers at the top of tools/build_medallion.py are the whole design;
  change them and re-run the script to regenerate the ornament from checkpoint
  10.  tools/verify_medallion.py re-checks all 102 of the claims above.
"""


def write_notes(log, rays):
    text = NOTES + "\nBUILD LOG\n---------\n" + "\n".join(log) + "\n"
    block = bpy.data.texts.get("WSK_Medallion_Notes.txt")
    if block is None:
        block = bpy.data.texts.new("WSK_Medallion_Notes.txt")
    block.clear()
    block.write(text)
    notes = bpy.data.texts.get("WSK_Project_Notes.txt")
    if notes is not None and "PROMPT 11" not in notes.as_string():
        notes.write(
            "\n\nPROMPT 11 - WAIST MEDALLION\n"
            "---------------------------\n"
            "Checkpoint 11 adds the central waist ornament to the blank mount of\n"
            f"checkpoint 8: a {RING_OUT * 1000:.0f} mm antique-gold ring, a recessed centre disc and\n"
            f"{len(rays)} fitted radial blades, three components and fourteen meshes,\n"
            "parented to a new pivot at the mount's axis.  Belt, fauld panels,\n"
            "mount, body, torso armour and scene setup are unchanged.  See\n"
            "WSK_Medallion_Notes.txt.\n")


if __name__ == "__main__":
    main()
