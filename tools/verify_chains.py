"""Prompt 16 verification - static waist chains and selected fittings.

Checks the saved checkpoint 16 against checkpoint 15 for scope, group
structure, link topology/budget, attachment points, unequal gravity-sagged
curves, medallion clearance, and intersections with nearby major forms.

Writes `analysis/verify/verify_chains_report.txt`.

Run: tools/bl.sh tools/verify_chains.py
"""
import os

import bpy            # noqa: F401
import bmesh          # noqa: E402
from mathutils import Vector, geometry  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_15_Polearm.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_16_Chains.blend")
REPORT = os.path.join(ROOT, "analysis/verify/verify_chains_report.txt")

BELT = "WSK_Armor_WaistBelt_01"
ACCESSORIES = "Accessories"
GROUPS = (
    dict(
        side="Left",
        collection="Chain 01 - Left Waist",
        pivot="WSK_Chain_Pivot_Left_01",
        chain="WSK_Chain_Waist_Left_01",
        fittings="WSK_Chain_Fittings_Left_01",
        low_z_expected=0.99,
    ),
    dict(
        side="Right",
        collection="Chain 02 - Right Waist",
        pivot="WSK_Chain_Pivot_Right_01",
        chain="WSK_Chain_Waist_Right_01",
        fittings="WSK_Chain_Fittings_Right_01",
        low_z_expected=1.03,
    ),
)
HOST_SURFACES = (
    "WSK_Armor_WaistBelt_01",
    "WSK_Armor_WaistPanel_Front_01_01",
    "WSK_Armor_WaistPanel_Front_02_01",
    "WSK_Armor_WaistPanel_Front_03_01",
    "WSK_Body_Base_01",
)

results = []
lines = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    tag = "PASS" if ok else "FAIL"
    line = f"[{tag}] {name}" + (f" - {detail}" if detail else "")
    print(line)
    lines.append(line)


def fingerprint(objects):
    result = {}
    for obj in objects:
        matrix = tuple(round(value, 6) for row in obj.matrix_world for value in row)
        modifiers = tuple((mod.type, mod.name) for mod in obj.modifiers)
        materials = tuple(slot.material.name if slot.material else None for slot in obj.material_slots)
        collections = tuple(sorted(col.name for col in obj.users_collection))
        parent = obj.parent.name if obj.parent else None
        coordinates = None
        if obj.type == "MESH":
            coordinates = tuple(round(value, 6) for vert in obj.data.vertices for value in vert.co)
        result[obj.name] = (obj.type, parent, collections, matrix, modifiers, materials, coordinates)
    return result


def evaluated_world_mesh(obj):
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    matrix = evaluated.matrix_world.copy()
    verts = [matrix @ vert.co for vert in mesh.vertices]
    faces = [tuple(poly.vertices) for poly in mesh.polygons]
    evaluated.to_mesh_clear()
    return verts, faces


def object_bounds(obj):
    verts, _faces = evaluated_world_mesh(obj)
    if not verts:
        return None
    low = Vector(tuple(min(v[i] for v in verts) for i in range(3)))
    high = Vector(tuple(max(v[i] for v in verts) for i in range(3)))
    return low, high


def bounds_overlap(a, b, pad=0.0):
    alo, ahi = a
    blo, bhi = b
    return all(alo[i] - pad <= bhi[i] and blo[i] - pad <= ahi[i] for i in range(3))


def component_stats(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    boundaries = sum(1 for edge in bm.edges if len(edge.link_faces) != 2)
    nonmanifold = sum(1 for vert in bm.verts if not vert.is_manifold)
    loose = sum(1 for vert in bm.verts if len(vert.link_faces) == 0)
    seen = set()
    components = 0
    for vert in bm.verts:
        if vert in seen:
            continue
        components += 1
        seen.add(vert)
        stack = [vert]
        while stack:
            current = stack.pop()
            for edge in current.link_edges:
                other = edge.other_vert(current)
                if other not in seen:
                    seen.add(other)
                    stack.append(other)
    v, e, f = len(bm.verts), len(bm.edges), len(bm.faces)
    bm.free()
    return dict(V=v, E=e, F=f, chi=v - e + f, boundary=boundaries,
                nonmanifold=nonmanifold, loose=loose, components=components)


def triangulated_world(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    matrix = evaluated.matrix_world.copy()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    verts = [matrix @ vert.co for vert in bm.verts]
    faces = [tuple(vert.index for vert in face.verts) for face in bm.faces]
    bm.free()
    evaluated.to_mesh_clear()
    return verts, faces


def segment_hits_triangle(start, end, tri):
    direction = end - start
    length = direction.length
    if length < 1e-10:
        return False
    hit = geometry.intersect_ray_tri(tri[0], tri[1], tri[2], direction / length, start, False)
    if hit is None:
        return False
    along = (hit - start).dot(direction)
    return -1e-8 <= along <= direction.length_squared + 1e-8


def triangles_intersect(first, second):
    for a, b in ((first[0], first[1]), (first[1], first[2]), (first[2], first[0])):
        if segment_hits_triangle(a, b, second):
            return True
    for a, b in ((second[0], second[1]), (second[1], second[2]), (second[2], second[0])):
        if segment_hits_triangle(a, b, first):
            return True
    return False


def min_vertex_distance(points, tree):
    best = 1e9
    for point in points:
        nearest = tree.find_nearest(point)
        if nearest[0] is not None and nearest[3] < best:
            best = nearest[3]
    return best


# ---------------------------------------------------------------------------
# Scope against the Prompt 15 checkpoint
# ---------------------------------------------------------------------------
bpy.ops.wm.open_mainfile(filepath=SRC)
old_objects = list(bpy.data.objects)
old_fp = fingerprint(old_objects)
old_materials = {material.name for material in bpy.data.materials}
old_collections = {collection.name for collection in bpy.data.collections}
old_accessory_children = {child.name for child in bpy.data.collections[ACCESSORIES].children}

bpy.ops.wm.open_mainfile(filepath=DST)
new_objects = list(bpy.data.objects)
new_fp = fingerprint(new_objects)
removed = sorted(set(old_fp) - set(new_fp))
changed = sorted(name for name in old_fp if name in new_fp and old_fp[name] != new_fp[name])
added = sorted(set(new_fp) - set(old_fp))
expected_added = sorted(name for group in GROUPS for name in
                        (group["pivot"], group["chain"], group["fittings"]))
check("scope: no Prompt 15 objects removed", not removed, f"removed={removed}")
check("scope: every Prompt 15 object is unchanged",
      not changed, f"{len(old_fp)} source objects compared; changed={changed[:5]}")
check("scope: exactly two chain pivots, two chain meshes and two fitting meshes added",
      added == expected_added, f"added={added}")
new_materials = {material.name for material in bpy.data.materials} - old_materials
check("scope: existing antique-gold material reused; no new materials",
      not new_materials, f"new materials={sorted(new_materials)}")
new_collections = {collection.name for collection in bpy.data.collections} - old_collections
expected_collections = {group["collection"] for group in GROUPS}
check("scope: only two nested chain collections added",
      new_collections == expected_collections, f"new collections={sorted(new_collections)}")
accessory_children = {child.name for child in bpy.data.collections[ACCESSORIES].children}
check("structure: chain groups are nested under Accessories",
      accessory_children - old_accessory_children == expected_collections,
      f"Accessories children={sorted(accessory_children)}")

# ---------------------------------------------------------------------------
# Group structure, editable pivots, materials and complexity
# ---------------------------------------------------------------------------
expected_gold = "MAT_Armor_AntiqueGold_01"
gold = bpy.data.materials.get(expected_gold)
check("material: chain and fittings reuse the waist medallion antique gold",
      gold is not None)

chain_bounds = {}
chain_stats = {}
all_link_count = 0
all_new_vertices = 0
for group in GROUPS:
    group_col = bpy.data.collections.get(group["collection"])
    pivot = bpy.data.objects.get(group["pivot"])
    chain = bpy.data.objects.get(group["chain"])
    fittings = bpy.data.objects.get(group["fittings"])
    if not all((group_col, pivot, chain, fittings)):
        check(f"structure: {group['collection']} group exists", False)
        continue
    check(f"structure: {group['collection']} contains only its pivot, chain and fittings",
          {obj.name for obj in group_col.objects} == {group["pivot"], group["chain"], group["fittings"]},
          f"objects={sorted(obj.name for obj in group_col.objects)}")
    check(f"structure: {group['pivot']} is parented to the waist belt",
          pivot.parent is bpy.data.objects.get(BELT),
          f"parent={pivot.parent.name if pivot.parent else None}")
    child_parents_ok = chain.parent == pivot and fittings.parent == pivot
    ident = lambda obj: max(abs(obj.matrix_basis[r][c] - (1.0 if r == c else 0.0))
                            for r in range(4) for c in range(4)) < 1e-8
    check(f"structure: chain and fittings follow the group pivot with identity local transforms",
          child_parents_ok and ident(chain) and ident(fittings))
    check(f"structure: {group['pivot']} is an unanimated plain-axes adjustment pivot",
          pivot.type == "EMPTY" and pivot.empty_display_type == "PLAIN_AXES"
          and pivot.animation_data is None and len(pivot.constraints) == 0)
    check(f"geometry: {group['chain']} is one unmodified static mesh",
          chain.type == "MESH" and not chain.modifiers and chain.animation_data is None
          and len(chain.constraints) == 0 and chain.rigid_body is None,
          f"vertices={len(chain.data.vertices)}, modifiers={len(chain.modifiers)}")
    check(f"geometry: {group['fittings']} is one low-poly static mesh",
          fittings.type == "MESH" and not fittings.modifiers
          and fittings.animation_data is None and fittings.rigid_body is None,
          f"vertices={len(fittings.data.vertices)}")
    check(f"material: {group['chain']} and its fittings use only antique gold",
          [mat.name for mat in chain.data.materials] == [expected_gold]
          and [mat.name for mat in fittings.data.materials] == [expected_gold])

    stats = component_stats(chain.data)
    chain_stats[group["side"]] = stats
    link_count = int(chain.get("wsk_link_count", 0))
    all_link_count += link_count
    all_new_vertices += len(chain.data.vertices) + len(fittings.data.vertices)
    check(f"topology: every oval link of {group['side']} chain is a closed manifold torus",
          stats["boundary"] == 0 and stats["nonmanifold"] == 0 and stats["loose"] == 0
          and stats["components"] == link_count and stats["chi"] == 0,
          f"links={link_count}, V={stats['V']} E={stats['E']} F={stats['F']} "
          f"components={stats['components']} chi={stats['chi']} boundary={stats['boundary']}")
    fitting_stats = component_stats(fittings.data)
    check(f"topology: {group['side']} anchor mesh contains two closed studs and two eyelets",
          fitting_stats["components"] == 4 and fitting_stats["boundary"] == 0
          and fitting_stats["nonmanifold"] == 0 and fittings.get("wsk_anchor_count") == 2,
          f"components={fitting_stats['components']} boundary={fitting_stats['boundary']}")
    check(f"complexity: {group['side']} chain link count stays modest",
          7 <= link_count <= 18,
          f"links={link_count}, curve={chain.get('wsk_curve_length_m', 0.0):.3f} m, "
          f"pitch={chain.get('wsk_link_pitch_m', 0.0) * 1000:.1f} mm")
    world_verts, _faces = evaluated_world_mesh(chain)
    lo = Vector(tuple(min(v[i] for v in world_verts) for i in range(3)))
    hi = Vector(tuple(max(v[i] for v in world_verts) for i in range(3)))
    chain_bounds[group["side"]] = (lo, hi)
    chain_stats[group["side"]]["world_low_z"] = lo.z
    chain_stats[group["side"]]["world_high_z"] = hi.z
    check(f"shape: {group['side']} chain drops below its belt anchors with authored gravity sag",
          lo.z < group["low_z_expected"] and hi.z > 1.06
          and chain.get("wsk_curve_sag_m", 0.0) >= 0.04,
          f"world Z {lo.z:.3f}..{hi.z:.3f} m, sag={chain.get('wsk_curve_sag_m', 0.0):.3f} m")

check("complexity: both chains use one mesh each and fewer than 32 total links",
      all_link_count < 32 and len(expected_added) == 6,
      f"total links={all_link_count}, new objects={len(added)}")
check("complexity: new chain and fitting geometry stays under 4000 vertices",
      all_new_vertices < 4000, f"total new accessory vertices={all_new_vertices}")
if len(chain_stats) == 2:
    left = chain_stats["Left"]
    right = chain_stats["Right"]
    left_len = float(bpy.data.objects[GROUPS[0]["chain"]].get("wsk_curve_length_m", 0.0))
    right_len = float(bpy.data.objects[GROUPS[1]["chain"]].get("wsk_curve_length_m", 0.0))
    check("shape: chain lengths and placements are intentionally unequal",
          abs(left_len - right_len) > 0.05 and left["world_low_z"] < right["world_low_z"] - 0.02
          and chain_bounds["Left"][1].x < chain_bounds["Right"][0].x,
          f"left {left_len:.3f} m / bottom Z {left['world_low_z']:.3f}; "
          f"right {right_len:.3f} m / bottom Z {right['world_low_z']:.3f}")

# ---------------------------------------------------------------------------
# Attachment and clearance
# ---------------------------------------------------------------------------

def build_tree(obj):
    verts, faces = triangulated_world(obj)
    return BVHTree.FromPolygons(verts, faces, all_triangles=True), verts, faces

belt_tree, _belt_verts, _belt_faces = build_tree(bpy.data.objects[BELT])
host_parts = [bpy.data.objects[name] for name in HOST_SURFACES]
host_verts, host_faces = [], []
for obj in host_parts:
    v, f = triangulated_world(obj)
    offset = len(host_verts)
    host_verts.extend(v)
    host_faces.extend(tuple(index + offset for index in face) for face in f)
host_tree = BVHTree.FromPolygons(host_verts, host_faces, all_triangles=True)

for group in GROUPS:
    chain = bpy.data.objects[group["chain"]]
    fittings = bpy.data.objects[group["fittings"]]
    fitting_verts, _ = evaluated_world_mesh(fittings)
    anchor_distance = min_vertex_distance(fitting_verts, belt_tree)
    check(f"attachment: {group['side']} eyelet/stud mesh is seated on the waist belt",
          anchor_distance < 0.0015, f"nearest fitting-to-belt distance={anchor_distance * 1000:.2f} mm")
    chain_verts, chain_faces = triangulated_world(chain)
    chain_box = object_bounds(chain)
    nearby = []
    for obj in bpy.data.objects:
        if obj.type != "MESH" or obj.name in (chain.name, fittings.name):
            continue
        if not any(col.name in ("Armor", "Body", "Cape") for col in obj.users_collection):
            continue
        bounds = object_bounds(obj)
        if bounds and bounds_overlap(chain_box, bounds, pad=0.005):
            nearby.append(obj)
    intersects = []
    chain_tree = BVHTree.FromPolygons(chain_verts, chain_faces, all_triangles=True)
    for obj in nearby:
        other_verts, other_faces = triangulated_world(obj)
        other_tree = BVHTree.FromPolygons(other_verts, other_faces, all_triangles=True)
        candidate_pairs = chain_tree.overlap(other_tree)
        if not candidate_pairs:
            continue
        for i, j in candidate_pairs:
            tri_a = [chain_verts[index] for index in chain_faces[i]]
            tri_b = [other_verts[index] for index in other_faces[j]]
            if triangles_intersect(tri_a, tri_b):
                intersects.append(obj.name)
                break
    check(f"clearance: {group['side']} chain links do not pass through armor, body or cape",
          not intersects,
          f"nearby meshes={sorted(obj.name for obj in nearby)}; intersections={sorted(set(intersects))}")

# The chains remain outside the medallion rays and boss in X; this clear gap is
# measured on the full mesh bounds, not only at the two endpoint anchors.
medallion_names = [obj.name for obj in bpy.data.objects
                   if obj.name.startswith("WSK_Armor_WaistMedallion") and obj.type == "MESH"]
med_x = []
for name in medallion_names:
    low, high = object_bounds(bpy.data.objects[name])
    med_x.extend((low.x, high.x))
med_left, med_right = min(med_x), max(med_x)
medallion_clearances = []
for side, (low, high) in chain_bounds.items():
    gap = med_left - high.x if high.x < 0 else low.x - med_right
    medallion_clearances.append(gap)
min_med_clear = min(medallion_clearances)
check("clearance: both chain groups remain at least 10 mm outside the medallion silhouette",
      min_med_clear >= 0.010,
      f"medallion X {med_left:.3f}..{med_right:.3f} m; nearest chain gap={min_med_clear * 1000:.1f} mm")

# ---------------------------------------------------------------------------
# Reports and preview checks
# ---------------------------------------------------------------------------
preview_files = [
    "analysis/chains/p16_front.png",
    "analysis/chains/p16_rear.png",
    "analysis/chains/p16_side_left.png",
    "analysis/chains/p16_side_right.png",
    "analysis/chains/p16_waist_front.png",
    "analysis/chains/p16_waist_threequarter.png",
    "analysis/chains/p16_waist_side.png",
]
missing_previews = [path for path in preview_files if not os.path.exists(os.path.join(ROOT, path))]
check("verification views: front, rear, both sides and waist close-ups rendered",
      not missing_previews, f"missing={missing_previews}")

passed = sum(1 for _name, ok, _detail in results if ok)
summary = f"{passed} / {len(results)} checks passing"
print(summary)
header = [
    "Prompt 16 - chains and selected metal accessories: verification report",
    "source: Wildshift_Knight_15_Polearm.blend",
    "target: Wildshift_Knight_16_Chains.blend",
    "",
]
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
with open(REPORT, "w") as report:
    report.write("\n".join(header + lines + ["", summary]) + "\n")
print("REPORT", REPORT)
if passed != len(results):
    raise SystemExit(1)
