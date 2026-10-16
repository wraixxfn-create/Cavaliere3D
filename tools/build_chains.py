"""Prompt 16 - two fitted ceremonial waist chains and their belt eyelets.

Builds on `Wildshift_Knight_15_Polearm.blend`, adds two independently
adjustable, static chain groups to the existing `Accessories` collection, and
saves `Wildshift_Knight_16_Chains.blend`.  Every Prompt 15 object is left
untouched.

Each chain is one low-poly mesh containing a modest run of alternating oval
links.  The curve is sampled against the visible front surfaces of the belt,
fauld and body, then held a small, consistent distance off the armor.  The
ends meet small belt-mounted eyelets.  Sag is authored directly into the
neutral-pose curve; there is no simulation or animation.

Run:  tools/bl.sh tools/build_chains.py
"""
import bisect
import math
import os

import bpy          # noqa: F401  (must be imported first: sets module paths)
import bmesh        # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_15_Polearm.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_16_Chains.blend")

ACCESSORIES = "Accessories"
BELT = "WSK_Armor_WaistBelt_01"
GOLD = "MAT_Armor_AntiqueGold_01"
BODY_AND_WAIST = (
    "WSK_Armor_WaistBelt_01",
    "WSK_Armor_WaistPanel_Front_01_01",
    "WSK_Armor_WaistPanel_Front_02_01",
    "WSK_Armor_WaistPanel_Front_03_01",
    "WSK_Body_Base_01",
)

# Endpoints sit on the front face of the waist belt.  The first chain drops
# farther and is a little longer; the right-hand chain is a shorter, higher
# swag.  X signs are scene-space, since the knight faces +Y.
CHAINS = (
    dict(
        side="Left",
        collection="Chain 01 - Left Waist",
        object="WSK_Chain_Waist_Left_01",
        fittings="WSK_Chain_Fittings_Left_01",
        pivot="WSK_Chain_Pivot_Left_01",
        x0=-0.166,
        x1=-0.068,
        z0=1.074,
        z1=1.067,
        sag=0.079,
    ),
    dict(
        side="Right",
        collection="Chain 02 - Right Waist",
        object="WSK_Chain_Waist_Right_01",
        fittings="WSK_Chain_Fittings_Right_01",
        pivot="WSK_Chain_Pivot_Right_01",
        x0=0.073,
        x1=0.166,
        z0=1.066,
        z1=1.077,
        sag=0.047,
    ),
)

# All dimensions are metres.  Each link is an oval ring, not a separate scene
# object.  Adjacent links alternate their plane by 90 degrees around the chain
# tangent, like a simple reusable chain-link construction.
CENTER_OFFSET = 0.0125
LINK_MAJOR = 0.0128
LINK_MINOR = 0.0060
LINK_WIRE = 0.00175
LINK_PITCH = 0.0155
LINK_MAJOR_STEPS = 16
LINK_MINOR_STEPS = 6
PATH_STEPS = 401

ANCHOR_STUD_R = 0.0052
ANCHOR_STUD_DEPTH = 0.0027
ANCHOR_EYELET_R = 0.0068
ANCHOR_EYELET_WIRE = 0.00175
ANCHOR_EYELET_STEPS = 16


def set_props(obj, **props):
    for key, value in props.items():
        obj[key] = value


def evaluated_world_mesh(obj):
    """Get a modifier-evaluated mesh in world space without changing the file."""
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    matrix = evaluated.matrix_world.copy()
    verts = [matrix @ vert.co for vert in mesh.vertices]
    faces = [tuple(poly.vertices) for poly in mesh.polygons]
    evaluated.to_mesh_clear()
    return verts, faces


def surface_tree(object_names):
    verts, faces = [], []
    for name in object_names:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            raise RuntimeError(f"Required chain host is missing: {name}")
        part_verts, part_faces = evaluated_world_mesh(obj)
        offset = len(verts)
        verts.extend(part_verts)
        faces.extend(tuple(index + offset for index in face) for face in part_faces)
    return BVHTree.FromPolygons(verts, faces, all_triangles=False)


def sample_host_point(tree, x, z):
    """Closest visible front-side point on the belt/fauld/body under (x, z)."""
    origin = Vector((x, 0.75, z))
    hit, _normal, _face, _distance = tree.ray_cast(origin, Vector((0.0, -1.0, 0.0)), 2.0)
    if hit is None:
        raise RuntimeError(f"No visible waist surface beneath chain path at x={x:.4f}, z={z:.4f}")
    return hit


def smooth_front_normal(tree, x, z, step=0.008):
    """Estimate a stable outward normal from the fitted front surface.

    BVH ray casts return the flat normal of whichever low-poly triangle was
    hit.  Offsetting every path sample by those faceted normals makes the path
    jump at quad boundaries.  Finite differences of the visible front surface
    give a smooth, reproducible fitted normal instead.
    """
    y_x0 = sample_host_point(tree, x - step, z).y
    y_x1 = sample_host_point(tree, x + step, z).y
    y_z0 = sample_host_point(tree, x, z - step).y
    y_z1 = sample_host_point(tree, x, z + step).y
    dy_dx = (y_x1 - y_x0) / (2.0 * step)
    dy_dz = (y_z1 - y_z0) / (2.0 * step)
    return Vector((-dy_dx, 1.0, -dy_dz)).normalized()


def curve_xz(spec, t):
    x = spec["x0"] + (spec["x1"] - spec["x0"]) * t
    z = spec["z0"] + (spec["z1"] - spec["z0"]) * t - spec["sag"] * 4.0 * t * (1.0 - t)
    return x, z


def build_fitted_path(spec, tree):
    path = []
    for i in range(PATH_STEPS):
        t = i / (PATH_STEPS - 1)
        x, z = curve_xz(spec, t)
        host_point = sample_host_point(tree, x, z)
        normal = smooth_front_normal(tree, x, z)
        path.append({
            "base": host_point,
            "normal": normal,
            "center": host_point + normal * CENTER_OFFSET,
            "t": t,
            "x": x,
            "z": z,
        })
    cumulative = [0.0]
    for a, b in zip(path, path[1:]):
        cumulative.append(cumulative[-1] + (b["center"] - a["center"]).length)
    return path, cumulative


def sample_path_at(path, cumulative, distance):
    distance = max(0.0, min(distance, cumulative[-1]))
    index = bisect.bisect_right(cumulative, distance) - 1
    index = max(0, min(index, len(path) - 2))
    lo, hi = cumulative[index], cumulative[index + 1]
    factor = 0.0 if hi - lo < 1e-12 else (distance - lo) / (hi - lo)
    a, b = path[index], path[index + 1]
    center = a["center"].lerp(b["center"], factor)
    normal = a["normal"].lerp(b["normal"], factor).normalized()
    base = a["base"].lerp(b["base"], factor)
    return center, normal, base


def sample_path_frame(path, cumulative, distance, length):
    center, normal, base = sample_path_at(path, cumulative, distance)
    epsilon = min(0.0015, max(0.0004, length * 0.012))
    p0, _n0, _b0 = sample_path_at(path, cumulative, max(0.0, distance - epsilon))
    p1, _n1, _b1 = sample_path_at(path, cumulative, min(length, distance + epsilon))
    tangent = (p1 - p0).normalized()
    side = normal.cross(tangent)
    if side.length < 1e-8:
        fallback = Vector((1.0, 0.0, 0.0))
        side = normal.cross(fallback)
        if side.length < 1e-8:
            side = normal.cross(Vector((0.0, 0.0, 1.0)))
    side.normalize()
    plane_normal = tangent.cross(side).normalized()
    if plane_normal.dot(normal) < 0.0:
        side.negate()
        plane_normal.negate()
    return center, tangent, side, plane_normal, normal, base


def append_oval_torus(verts, faces, center, long_axis, short_axis, plane_normal,
                      major_radius, minor_radius, wire_radius,
                      major_steps=LINK_MAJOR_STEPS, minor_steps=LINK_MINOR_STEPS):
    """Append one closed tube swept around an oval centreline."""
    t = Vector(long_axis).normalized()
    s = Vector(short_axis).normalized()
    n = Vector(plane_normal).normalized()
    first = len(verts)
    for i in range(major_steps):
        phi = 2.0 * math.pi * i / major_steps
        radial_center = t * (major_radius * math.cos(phi)) + s * (minor_radius * math.sin(phi))
        derivative = t * (-major_radius * math.sin(phi)) + s * (minor_radius * math.cos(phi))
        loop_tangent = derivative.normalized()
        radial = loop_tangent.cross(n).normalized()
        for j in range(minor_steps):
            theta = 2.0 * math.pi * j / minor_steps
            offset = (radial * math.cos(theta) + n * math.sin(theta)) * wire_radius
            verts.append(center + radial_center + offset)
    for i in range(major_steps):
        i2 = (i + 1) % major_steps
        for j in range(minor_steps):
            j2 = (j + 1) % minor_steps
            faces.append((
                first + i * minor_steps + j,
                first + i2 * minor_steps + j,
                first + i2 * minor_steps + j2,
                first + i * minor_steps + j2,
            ))


def append_oriented_cylinder(verts, faces, center, axis_u, axis_v, normal,
                             radius, depth, segments=12):
    """Append a closed, low-poly cylinder whose local Z follows `normal`."""
    u = Vector(axis_u).normalized()
    v = Vector(axis_v).normalized()
    n = Vector(normal).normalized()
    first = len(verts)
    for side in (-1.0, 1.0):
        for i in range(segments):
            angle = 2.0 * math.pi * i / segments
            verts.append(center + u * (radius * math.cos(angle))
                         + v * (radius * math.sin(angle))
                         + n * (side * depth * 0.5))
    bottom_center = len(verts)
    verts.append(center - n * (depth * 0.5))
    top_center = len(verts)
    verts.append(center + n * (depth * 0.5))
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((first + i, first + j, first + segments + j, first + segments + i))
        faces.append((bottom_center, first + j, first + i))
        faces.append((top_center, first + segments + i, first + segments + j))


def mesh_object(name, world_verts, faces, pivot, collection, material, smooth=True):
    """Create one joined, manifold mesh with coordinates local to its group pivot."""
    pivot_world = pivot.matrix_world.translation.copy()
    local_verts = [tuple(Vector(v) - pivot_world) for v in world_verts]
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(local_verts, [], faces)
    mesh.validate(verbose=False)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = smooth
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.parent = pivot
    obj.location = (0.0, 0.0, 0.0)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)
    mesh.materials.append(material)
    return obj


def build_chain_mesh(path, cumulative, spec, material, pivot, collection):
    length = cumulative[-1]
    link_count = max(5, int(round(length / LINK_PITCH)))
    verts, faces = [], []
    for i in range(link_count):
        # Half-pitch offsets put each end link through its belt eyelet.  Links
        # are one mesh object, with each oval kept as its own closed component.
        distance = length * (i + 0.5) / link_count
        center, tangent, side, plane_normal, _normal, _base = sample_path_frame(
            path, cumulative, distance, length)
        if i % 2 == 0:
            # First link is edge-on to the armor face and threads the eyelet.
            short_axis = plane_normal
            link_normal = -side
        else:
            short_axis = side
            link_normal = plane_normal
        append_oval_torus(
            verts, faces, center, tangent, short_axis, link_normal,
            LINK_MAJOR, LINK_MINOR, LINK_WIRE,
        )
    chain = mesh_object(spec["object"], verts, faces, pivot, collection, material)
    chain["wsk_part"] = "static alternating oval-link waist chain"
    chain["wsk_prompt"] = "Prompt 16 - chains and selected metal accessories"
    chain["wsk_host_object"] = BELT
    chain["wsk_attachment_hint"] = "two eyelets seated on the front waist belt"
    chain["wsk_link_count"] = link_count
    chain["wsk_curve_length_m"] = length
    chain["wsk_link_pitch_m"] = length / link_count
    chain["wsk_curve_sag_m"] = spec["sag"]
    chain["wsk_chain_center_offset_m"] = CENTER_OFFSET
    return chain, link_count, length


def build_fittings(path, cumulative, pivot, collection, material, chain_name):
    length = cumulative[-1]
    verts, faces = [], []
    for distance in (0.0, length):
        _center, tangent, side, plane_normal, normal, base = sample_path_frame(
            path, cumulative, distance, length)
        # Small round bosses sit on the belt face.  The low-profile eyelet loop
        # overlaps each boss and the end link, making the attachment legible.
        stud_center = base + normal * (ANCHOR_STUD_DEPTH * 0.5 + 0.0001)
        append_oriented_cylinder(
            verts, faces, stud_center, tangent, side, normal,
            ANCHOR_STUD_R, ANCHOR_STUD_DEPTH, segments=12,
        )
        eyelet_center = base + normal * 0.00405
        append_oval_torus(
            verts, faces, eyelet_center, tangent, side, normal,
            ANCHOR_EYELET_R, ANCHOR_EYELET_R, ANCHOR_EYELET_WIRE,
            major_steps=ANCHOR_EYELET_STEPS, minor_steps=6,
        )
    fittings = mesh_object(chain_name, verts, faces, pivot, collection, material)
    fittings["wsk_part"] = "two belt eyelets and their low-profile studs"
    fittings["wsk_prompt"] = "Prompt 16 - chains and selected metal accessories"
    fittings["wsk_host_object"] = BELT
    fittings["wsk_anchor_count"] = 2
    return fittings


def add_group(spec, path, cumulative, gold):
    accessories = bpy.data.collections.get(ACCESSORIES)
    if accessories is None:
        raise RuntimeError("The existing Accessories collection is missing")
    group_collection = bpy.data.collections.new(spec["collection"])
    accessories.children.link(group_collection)
    group_collection["wsk_group"] = "independently adjustable static waist chain"

    start_center, _t, _s, _pn, _n, _base = sample_path_frame(
        path, cumulative, 0.0, cumulative[-1])
    pivot = bpy.data.objects.new(spec["pivot"], None)
    pivot.empty_display_type = "PLAIN_AXES"
    pivot.empty_display_size = 0.035
    pivot.location = start_center
    belt = bpy.data.objects[BELT]
    pivot.parent = belt
    pivot.matrix_parent_inverse = belt.matrix_world.inverted()
    group_collection.objects.link(pivot)
    # Parent/world matrices are evaluated lazily in headless bpy; update before
    # converting world-space chain vertices into pivot-local mesh coordinates.
    bpy.context.view_layer.update()

    chain, link_count, length = build_chain_mesh(
        path, cumulative, spec, gold, pivot, group_collection)
    fittings = build_fittings(
        path, cumulative, pivot, group_collection, gold, spec["fittings"])
    set_props(
        pivot,
        wsk_group=spec["collection"],
        wsk_host_object=BELT,
        wsk_curve_length_m=length,
        wsk_curve_sag_m=spec["sag"],
        wsk_link_count=link_count,
        wsk_adjustment_note="Move/rotate this pivot to adjust this chain group; edit the chain mesh to alter its drape.",
    )
    print(f"  {spec['object']}: {link_count} oval links, "
          f"curve {length:.3f} m, sag {spec['sag']:.3f} m")
    return pivot, chain, fittings


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    scene = bpy.context.scene
    if bpy.data.objects.get(BELT) is None:
        raise RuntimeError(f"Belt host not found: {BELT}")
    gold = bpy.data.materials.get(GOLD)
    if gold is None:
        raise RuntimeError(f"Existing antique-gold material not found: {GOLD}")

    tree = surface_tree(BODY_AND_WAIST)
    groups = []
    for spec in CHAINS:
        path, cumulative = build_fitted_path(spec, tree)
        groups.append(add_group(spec, path, cumulative, gold))

    notes = """Wildshift Knight 16 - Chains and Selected Metal Accessories
============================================================

Built from checkpoint 15.  All Prompt 15 objects and materials are unchanged.

Two static chain swags are attached to the front waist belt, each in its own
nested Accessories collection and under its own pivot parented to the belt.
The left chain drops lower and is longer; the right chain is shorter and
shallower.  The chain is one joined mesh object per group, with alternating
low-poly oval links, not a swarm of per-link scene objects.  Each group also
contains one small fitting mesh combining two eyelets and their belt studs.

Construction: each link is an oval torus with a 26 mm long centreline, 12 mm
wide centreline and 3.5 mm wire.  Links alternate their plane by 90 degrees.
A 401-sample gravity-sag path is fitted to the evaluated belt/fauld/body front
surface, with the centreline held 12.5 mm off it.  The two end loops attach to small eyelets on
the belt face.  Both swags hang downward in the neutral pose.  No simulation,
collision system, animation, textures, or extra decoration is used.
"""
    text = bpy.data.texts.new("WSK_Accessory_Chains_Notes.txt")
    text.from_string(notes)
    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print("SAVED", DST)


if __name__ == "__main__":
    main()
