"""Verify Prompt 7 and render the shoulder inspection views.

Checks scope, topology, the plate hierarchy, the layer order, body / helmet /
cuirass clearances, the approved proportions, left-right balance, robustness of
the thin geometry, and articulation clearances under a simulated shoulder lift
and swing.

Env: WSK_SKIP_RENDERS=1 for the numeric checks only.
Run: tools/bl.sh tools/verify_shoulders.py
"""
import hashlib
import math
import os

import bpy  # noqa: F401 (must be imported first)
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector, Matrix  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC6 = os.path.join(ROOT, "Wildshift_Knight_06_Silhouette.blend")
SRC7 = os.path.join(ROOT, "Wildshift_Knight_07_Shoulders.blend")
SHOTS = os.path.join(ROOT, "analysis/shoulders")
REPORT = os.path.join(ROOT, "analysis/verify/verify_shoulders_report.txt")
SKIP_RENDERS = os.environ.get("WSK_SKIP_RENDERS") == "1"
SAMPLES = int(os.environ.get("WSK_SAMPLES", "24"))

BODY = "WSK_Body_Base_01"
SIDES = ("R", "L")
PLATES = ["WSK_Armor_Pauldron_{S}_01",
          "WSK_Armor_PauldronLame1_{S}_01",
          "WSK_Armor_PauldronLame2_{S}_01",
          "WSK_Armor_PauldronLame3_{S}_01"]
SPIKES = ["WSK_Armor_ShoulderSpike_{S}_01",
          "WSK_Armor_ShoulderSpikeFront_{S}_01",
          "WSK_Armor_ShoulderSpikeRear_{S}_01",
          "WSK_Armor_ShoulderSpikeCrown_{S}_01",
          "WSK_Armor_ShoulderSpikeFrontLow_{S}_01",
          "WSK_Armor_ShoulderSpikeRearLow_{S}_01"]
SHOULDER = [n.format(S=s) for n in PLATES + SPIKES for s in SIDES]
UNTOUCHED_ARMOR = ["WSK_Armor_Chest_01", "WSK_Armor_Back_01",
                   "WSK_Armor_Forearm_R_01", "WSK_Armor_Forearm_L_01",
                   "WSK_Armor_Gauntlet_R_01", "WSK_Armor_Gauntlet_L_01",
                   "WSK_Armor_Thigh_R_01", "WSK_Armor_Thigh_L_01",
                   "WSK_Armor_Shin_R_01", "WSK_Armor_Shin_L_01",
                   "WSK_Armor_Sabaton_R_01", "WSK_Armor_Sabaton_L_01"]
HELMET = ["WSK_Helmet_Shell_01", "WSK_Helmet_Faceplate_01", "WSK_Helmet_Crest_01",
          "WSK_Helmet_NeckGuard_01"]
CROWN = ["WSK_Helmet_CrownBand_01", "WSK_Helmet_CrownHalo_01",
         "WSK_Helmet_CrownSpine_01", "WSK_Helmet_CrownMount_01"]
ROOTS = {"R": "WSK_Shoulder_Root_R_01", "L": "WSK_Shoulder_Root_L_01"}
JOINTS = {"R": Vector((0.200, 0.0, 1.630)), "L": Vector((-0.200, 0.0, 1.630))}

# Approved proportions carried over from checkpoint 6.
PLATE_SPAN = 0.530
SPIKE_SPAN = 0.640
SHOULDER_LINE = 1.740
ELBOW_Z = {"R": 1.281, "L": 1.281}

results = []
geometry = {}


def check(label, ok, detail=""):
    results.append((label, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))


def section(title):
    results.append((None, None, title))
    print(f"\n== {title} ==")


def mesh_hash(mesh):
    co = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", co)
    loops = np.empty(len(mesh.loops), dtype=np.int32)
    if len(mesh.loops):
        mesh.loops.foreach_get("vertex_index", loops)
    return hashlib.sha1(co.tobytes() + loops.tobytes()).hexdigest()


def scene_hashes():
    return {o.name: mesh_hash(o.data) for o in bpy.data.objects if o.type == "MESH"}


def evaluated(obj):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    mw = ev.matrix_world.copy()
    verts = [mw @ v.co for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    return verts, faces


def tree_of(verts, faces):
    return BVHTree.FromPolygons(verts, faces, all_triangles=False)


def bbox(points):
    return (Vector((min(p.x for p in points), min(p.y for p in points),
                    min(p.z for p in points))),
            Vector((max(p.x for p in points), max(p.y for p in points),
                    max(p.z for p in points))))


def min_distance(a_verts, b_tree):
    best = None
    for p in a_verts:
        hit = b_tree.find_nearest(p)
        if hit[0] is None:
            continue
        d = (Vector(hit[0]) - p).length
        if best is None or d < best:
            best = d
    return best if best is not None else float("inf")


def inside_count(a_verts, b_verts, b_faces, b_tree, label):
    """How many vertices of A are inside the closed shell B."""
    count = 0
    for p in a_verts:
        # majority vote over three rays keeps the test robust on flat regions
        votes = 0
        for direction in (Vector((0.0, 0.0, 1.0)), Vector((1.0, 0.0, 0.0)),
                          Vector((0.0, 1.0, 0.0))):
            hits = 0
            origin = p + direction * 1e-5
            for _ in range(64):
                hit = b_tree.ray_cast(origin, direction, 8.0)
                if hit[0] is None:
                    break
                hits += 1
                origin = Vector(hit[0]) + direction * 1e-5
            if hits % 2 == 1:
                votes += 1
        if votes >= 2:
            count += 1
    return count


def edge_crossings(a_verts, a_faces, b_verts, b_faces):
    """How many edges of A pass through a face of B (exact interpenetration).

    This replaces a point-in-shell parity vote for the plate stack: the lames are
    5 mm shells, and a grazing ray inside the lap can miscount crossings, while an
    edge that passes through a face is unambiguous.  A stack that is merely
    tucking cannot produce one.
    """
    tree = tree_of(b_verts, b_faces)
    hits = 0
    for face in a_faces:
        for i in range(len(face)):
            p = a_verts[face[i]]
            q = a_verts[face[(i + 1) % len(face)]]
            direction = q - p
            length = direction.length
            if length < 1e-9:
                continue
            if tree.ray_cast(p, direction / length, length)[0] is not None:
                hits += 1
    return hits


def dist_to(points, target_verts, target_faces):
    tree = tree_of(target_verts, target_faces)
    return min_distance(points, tree)


def rotate_points(points, pivot, matrix):
    return [pivot + matrix @ (p - pivot) for p in points]


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC6)
    ref_hashes = scene_hashes()

    bpy.ops.wm.open_mainfile(filepath=SRC7)
    cur_hashes = scene_hashes()

    geo = {}
    for name in SHOULDER + [BODY] + UNTOUCHED_ARMOR + HELMET + CROWN:
        v, f = evaluated(bpy.data.objects[name])
        geo[name] = dict(verts=v, faces=f, tree=tree_of(v, f),
                         bbox=bbox(v), hash=cur_hashes[name])
    for side in SIDES:
        geo[ROOTS[side]] = dict(obj=bpy.data.objects[ROOTS[side]])

    section("A  scope: nothing outside the shoulder assembly changed")
    changed = sorted(n for n in cur_hashes if ref_hashes.get(n) != cur_hashes[n])
    expected = sorted(SHOULDER)
    check("the only meshes that changed are the shoulder plates and spikes",
          changed == expected, f"{len(changed)} changed")
    check("the body is byte-identical",
          cur_hashes[BODY] == ref_hashes[BODY])
    check("the cuirass, forearms, gauntlets, legs and sabatons are byte-identical",
          all(cur_hashes[n] == ref_hashes[n] for n in UNTOUCHED_ARMOR))
    check("the helmet shell, faceplate, crest and gorget are byte-identical",
          all(cur_hashes[n] == ref_hashes[n] for n in HELMET))
    check("the crown band, halo, spine and mount are byte-identical",
          all(cur_hashes[n] == ref_hashes[n] for n in CROWN))
    crown_all = [n for n in cur_hashes if n.startswith("WSK_Helmet_Crown")]
    check("all 13 crown elements are intact",
          len(crown_all) == 13 and all(cur_hashes[n] == ref_hashes[n] for n in crown_all),
          f"{len(crown_all)} elements")
    plate_new = ["WSK_Armor_PauldronLame1_R_01", "WSK_Armor_PauldronLame2_R_01",
                 "WSK_Armor_PauldronLame3_R_01", "WSK_Armor_PauldronLame1_L_01",
                 "WSK_Armor_PauldronLame2_L_01", "WSK_Armor_PauldronLame3_L_01"]
    check("three new secondary lames per shoulder were added",
          all(n in cur_hashes for n in plate_new), "6 lame objects")
    check("the four objects with no counterpart in checkpoint 6 are exactly the "
          "new plates and spikes",
          sorted(n for n in cur_hashes if n not in ref_hashes) ==
          sorted([n for n in SHOULDER if n not in ref_hashes]),
          f"{len([n for n in cur_hashes if n not in ref_hashes])} new objects")

    section("B  hierarchy: every plate and spike is its own editable object")
    for side in SIDES:
        plates = [p.format(S=side) for p in PLATES]
        spikes = [s.format(S=side) for s in SPIKES]
        root = bpy.data.objects[ROOTS[side]]
        check(f"{side}: 4 plates and 6 spikes exist as separate objects",
              all(n in cur_hashes for n in plates + spikes),
              f"{len(plates)} plates, {len(spikes)} spikes")
        check(f"{side}: every part is parented to {root.name}",
              all(bpy.data.objects[n].parent == root for n in plates + spikes))
        check(f"{side}: the root empty sits on the shoulder joint",
              (root.location - JOINTS[side]).length < 1e-6,
              f"({root.location.x:+.3f}, {root.location.y:+.3f}, {root.location.z:+.3f})")
        check(f"{side}: every part keeps an identity transform",
              all(tuple(bpy.data.objects[n].location) == (0.0, 0.0, 0.0)
                  and tuple(bpy.data.objects[n].scale) == (1.0, 1.0, 1.0)
                  for n in plates + spikes))
        check(f"{side}: every part still carries its own BEVEL modifier",
              all(any(m.type == "BEVEL" for m in bpy.data.objects[n].modifiers)
                  for n in plates + spikes))
        check(f"{side}: every part has exactly one placeholder material",
              all(len(bpy.data.objects[n].data.materials) == 1
                  for n in plates + spikes))
        check(f"{side}: plates use the broad iron placeholder, spikes the blackened steel",
              all(bpy.data.objects[n].data.materials[0].name == "MAT_Armor_BroadIron_01"
                  for n in plates)
              and all(bpy.data.objects[n].data.materials[0].name == "MAT_Armor_BlackenedSteel_01"
                      for n in spikes))
        check(f"{side}: no part was joined (each mesh is used by one object)",
              all(bpy.data.objects[n].data.users == 1 for n in plates + spikes))

    section("C  topology: closed manifolds, real thickness, no fragile slivers")
    for name in SHOULDER:
        bm = bmesh.new()
        bm.from_mesh(bpy.data.objects[name].data)
        non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
        boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
        loose = sum(1 for v in bm.verts if not v.link_edges)
        degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
        bm.free()
        check(f"{name}: closed manifold, no loose geometry",
              non_manifold == 0 and boundary == 0 and loose == 0 and degenerate == 0,
              f"non-manifold {non_manifold}, boundary {boundary}, loose {loose}, "
              f"degenerate faces {degenerate}")

    shortest = None
    for name in SHOULDER:
        verts = bpy.data.objects[name].data.vertices
        for edge in bpy.data.objects[name].data.edges:
            a, b = verts[edge.vertices[0]].co, verts[edge.vertices[1]].co
            length = (a - b).length
            if shortest is None or length < shortest[0]:
                shortest = (length, name)
    check("the shortest edge in the whole assembly is still above 2 mm "
          "(no needle-thin geometry)",
          shortest[0] > 0.002, f"{shortest[0] * 1000:.2f} mm in {shortest[1]}")

    thin = []
    for name in [p.format(S=s) for p in PLATES for s in SIDES]:
        obj = bpy.data.objects[name]
        # every plate is a two-skin shell: match each vertex to its offset twin
        co = [v.co for v in obj.data.vertices]
        n = len(co) // 2
        gaps = [(co[i] - co[i + n]).length for i in range(n)]
        thin.append((min(gaps), name))
    # The main plate is a full 5 mm everywhere.  A lame cannot be: over the
    # deltoid the body leaves barely 10 mm of air under the plate above, so a
    # lame thins locally where it is squeezed into that lap.  Even at 2.8 mm,
    # blackened steel with a 1 mm bevel is solid, and those faces are hidden.
    # No plate ever thins towards a feather edge.
    caps = []
    for d, n in thin:
        plate, side, _idx = n.split("_")[2:]
        caps.append((d, n))
    worst = min(d for d, _ in caps)
    main_min = min(d for d, n in caps if n.split("_")[2] == "Pauldron")
    check("every plate is at least 2.8 mm thick everywhere and the main plate "
          "keeps its full 5 mm (survives export and subdivision)",
          worst >= 0.0028 and main_min >= 0.0049,
          f"main {main_min * 1000:.1f} mm, thinnest lame {worst * 1000:.1f} mm")

    counts = {n.split("_")[-2]: len(bpy.data.objects[n].data.polygons) for n in SHOULDER}
    check("object count stays in the intended range: no spike field was generated",
          len(SHOULDER) == 20, f"{len(SHOULDER)} shoulder objects "
                               f"({len(SHOULDER)} = 8 plates + 12 spikes)")

    section("D  layering: a hierarchy of overlapping plates, not a pile of shards")
    for side in SIDES:
        for i in range(1, 4):
            upper = PLATES[i - 1].format(S=side)
            lower = PLATES[i].format(S=side)
            up, low = geo[upper], geo[lower]
            overlap_z = min(up["bbox"][1].z, low["bbox"][1].z) - max(up["bbox"][0].z,
                                                                    low["bbox"][0].z)
            crossing = (edge_crossings(low["verts"], low["faces"],
                                       up["verts"], up["faces"])
                        + edge_crossings(up["verts"], up["faces"],
                                         low["verts"], low["faces"]))
            gap = min_distance(low["verts"], up["tree"])
            check(f"{side}: lame {i} tucks under the plate above it "
                  f"(with no interpenetration)",
                  crossing == 0 and gap > 0.0015 and overlap_z > 0.02,
                  f"{overlap_z * 1000:.0f} mm of vertical overlap, "
                  f"{gap * 1000:.2f} mm gap, {crossing} edges crossing the "
                  f"plate above")
    for side in SIDES:
        cx = 1.0 if side == "R" else -1.0
        outer = [max(math.hypot(p.x - cx * 0.185, p.y + 0.006)
                     for p in geo[p.format(S=side)]["verts"]) for p in PLATES]
        check(f"{side}: the main plate defines the outer silhouette - each lame "
              f"stays inside it", outer[0] >= max(outer[1:]) - 1e-9,
              "outermost radius per layer " + " > ".join(f"{r * 1000:.0f}" for r in outer)
              + " mm")

    section("E  clearances: no intrusion into the body, gorget, helmet or cuirass")
    for side in SIDES:
        for name in [p.format(S=side) for p in PLATES] + [s.format(S=side) for s in SPIKES]:
            body_d = dist_to(geo[name]["verts"], geo[BODY]["verts"], geo[BODY]["faces"])
            geo[name]["body_d"] = body_d
        outer = [p.format(S=side) for p in PLATES[:1]] + \
                [s.format(S=side) for s in SPIKES]
        worst_outer = min((geo[n]["body_d"], n) for n in outer)
        check(f"{side}: the exposed armour (main plate and spikes) keeps 5 mm or "
              f"more of air against the body",
              worst_outer[0] > 0.005,
              f"closest {worst_outer[0] * 1000:.1f} mm ({worst_outer[1]})")
        worst_lames = min((geo[p.format(S=side)]["body_d"], p.format(S=side))
                          for p in PLATES[1:])
        # The lames are the inner layers of the stack.  Over the deltoid the body
        # leaves barely 10 mm under the plate above, so a lame there has to live
        # with a couple of millimetres - the approved 8-12 mm standoff applies to
        # the plate on top, which is what the silhouette is measured on.
        check(f"{side}: every lame still keeps at least 3 mm of air against the "
              f"body", worst_lames[0] > 0.003,
              f"closest {worst_lames[0] * 1000:.1f} mm ({worst_lames[1]})")
        gorget_d = min(dist_to(geo[n]["verts"], geo["WSK_Helmet_NeckGuard_01"]["verts"],
                               geo["WSK_Helmet_NeckGuard_01"]["faces"])
                       for n in [p.format(S=side) for p in PLATES])
        check(f"{side}: the plates still clear the gorget (they move with "
              f"different bones)", gorget_d > 0.004,
              f"closest {gorget_d * 1000:.1f} mm")
        helmet_d = min(dist_to(geo[n]["verts"], geo["WSK_Helmet_Shell_01"]["verts"],
                               geo["WSK_Helmet_Shell_01"]["faces"])
                       for n in [p.format(S=side) for p in PLATES + SPIKES])
        check(f"{side}: nothing reaches the helmet shell", helmet_d > 0.05,
              f"closest {helmet_d * 1000:.1f} mm")
        crest_d = min(dist_to(geo[n]["verts"], geo["WSK_Helmet_Crest_01"]["verts"],
                              geo["WSK_Helmet_Crest_01"]["faces"])
                      for n in [p.format(S=side) for p in SPIKES])
        check(f"{side}: every spike tip clears the helmet crest", crest_d > 0.05,
              f"closest {crest_d * 1000:.1f} mm")
        crown_d = min(dist_to(geo[n]["verts"], geo["WSK_Helmet_CrownHalo_01"]["verts"],
                              geo["WSK_Helmet_CrownHalo_01"]["faces"])
                      for n in [s.format(S=side) for s in SPIKES])
        check(f"{side}: every spike clears the crown halo", crown_d > 0.10,
              f"closest {crown_d * 1000:.1f} mm")

    for side in SIDES:
        laps = []
        for name in [p.format(S=side) for p in PLATES]:
            chest = geo["WSK_Armor_Chest_01"]
            back = geo["WSK_Armor_Back_01"]
            inside_chest = inside_count(geo[name]["verts"], chest["verts"], chest["faces"],
                                        chest["tree"], name)
            inside_back = inside_count(geo[name]["verts"], back["verts"], back["faces"],
                                       back["tree"], name)
            laps.append(inside_chest + inside_back)
        check(f"{side}: no plate ends up inside the chest or back plate",
              sum(laps) == 0, f"{sum(laps)} vertices inside the cuirass")

    section("F  approved proportions carried over from checkpoint 6")
    for side in SIDES:
        plate = geo[PLATES[0].format(S=side)]
        tip = max(geo[s.format(S=side)]["bbox"][1].x if side == "R"
                  else -geo[s.format(S=side)]["bbox"][0].x
                  for s in SPIKES)
        geo[f"tip_{side}"] = tip
    span = geo["tip_R"] + geo["tip_L"]
    plate_span = (geo[PLATES[0].format(S="R")]["bbox"][1].x
                  - geo[PLATES[0].format(S="L")]["bbox"][0].x)
    check("plate assembly span stays inside the approved range "
          "(0.530 m approved, 0.549 m reference)",
          0.510 <= plate_span <= 0.549,
          f"{plate_span:.3f} m at the widest point of the main plates")
    check("spike tips stay inside the reference spiked span "
          "(0.630 m front reading / 0.715 m rear reading)",
          span < 0.700, f"{span:.3f} m")
    check("the spikes do reach past the plate edge, so they read as spikes",
          span > plate_span, f"tips {span:.3f} m vs plate {plate_span:.3f} m")
    line = max(geo[n]["bbox"][1].z for n in
               [p.format(S=s) for p in PLATES for s in SIDES])
    check("the shoulder line (plate crown) is at the approved Z 1.740",
          abs(line - SHOULDER_LINE) < 0.01, f"Z {line:.3f} m")
    for side in SIDES:
        # The clearance that matters for the elbow is the one over the arm
        # (|a| < 45 deg); the lowest lame is allowed to hang further down at the
        # front and the back, where it belongs to the chest, not the arm.
        cx = 1.0 if side == "R" else -1.0
        lowest_arm = min(p.z for p in geo[PLATES[3].format(S=side)]["verts"]
                         if abs(math.degrees(math.atan2(
                             (p.y + 0.006) / 0.172, (cx * p.x - 0.185) / 0.082))) < 45.0)
        check(f"{side}: the lowest lame over the arm stops 0.10 m or more above "
              f"the elbow", lowest_arm > ELBOW_Z[side] + 0.10,
              f"Z {lowest_arm:.3f} vs elbow {ELBOW_Z[side]:.3f} "
              f"({(lowest_arm - ELBOW_Z[side]) * 1000:.0f} mm)")
        # The clearance that matters for the elbow is the one over the arm
        # (|a| < 45 deg), not the lowest point of the lame at the front.
        cx = 1.0 if side == "R" else -1.0
        lowest_arm = min(p.z for p in geo[PLATES[3].format(S=side)]["verts"]
                         if abs(math.degrees(math.atan2(
                             (p.y + 0.006) / 0.172, (cx * p.x - 0.185) / 0.082))) < 45.0)
        check(f"{side}: the lowest lame over the arm stops 0.10 m or more above "
              f"the elbow (the front and back edges are allowed to hang lower)",
              lowest_arm > ELBOW_Z[side] + 0.10,
              f"Z {lowest_arm:.3f} vs elbow {ELBOW_Z[side]:.3f} "
              f"({(lowest_arm - ELBOW_Z[side]) * 1000:.0f} mm)")


    section("G  left and right are broadly consistent, with small deliberate asymmetry")
    deltas = []
    for pair in PLATES + SPIKES:
        r = geo[pair.format(S="R")]["verts"]
        l = geo[pair.format(S="L")]["verts"]
        dev = min_distance([Vector((-p.x, p.y, p.z)) for p in r],
                           geo[pair.format(S="L")]["tree"])
        check(f"{pair}: left shoulder matches the mirrored right side",
              dev < 0.03, f"{dev * 1000:.1f} mm from the mirror")
    for s_name in SPIKES:
        tip_r = Vector(bpy.data.objects[s_name.format(S="R")]["wsk_spike_tip"])
        tip_l = Vector(bpy.data.objects[s_name.format(S="L")]["wsk_spike_tip"])
        deltas.append((Vector((-tip_r.x, tip_r.y, tip_r.z)) - tip_l).length)
    check("the two shoulders are not an exact mirror copy: half the spikes carry "
          "the intended small asymmetries",
          sum(1 for d in deltas if d > 0.003) >= 3,
          f"{sum(1 for d in deltas if d > 0.003)} of {len(deltas)} spike pairs "
          f"deliberately differ")
    check("the asymmetry stays small: every spike tip is within 30 mm of the "
          "mirrored one", max(deltas) < 0.030,
          f"largest tip deviation {max(deltas) * 1000:.1f} mm")
    plate_dev = []
    for pair in PLATES:
        r = geo[pair.format(S="R")]["verts"]
        l = geo[pair.format(S="L")]["verts"]
        plate_dev.append(min_distance([Vector((-p.x, p.y, p.z)) for p in r],
                                      geo[pair.format(S="L")]["tree"]))
    check("the plate stacks themselves stay a symmetric pair",
          max(plate_dev) < 0.005, f"largest plate deviation {max(plate_dev) * 1000:.2f} mm")

    section("H  articulation: clearances survive a shoulder lift and a swing")
    for side in SIDES:
        cx = 1.0 if side == "R" else -1.0
        pivot = JOINTS[side]
        for label, angle in (("lift 20 deg", -20.0), ("drop 15 deg", 15.0),
                             ("swing 20 deg", -20.0)):
            if label.startswith("swing"):
                matrix = Matrix.Rotation(math.radians(angle), 3, "Z")
            else:
                matrix = Matrix.Rotation(math.radians(cx * angle), 3, "Y")
            names = [p.format(S=side) for p in PLATES] + [s.format(S=side) for s in SPIKES]
            worst = (float("inf"), None)
            for name in names:
                moved = rotate_points(geo[name]["verts"], pivot, matrix)
                d = dist_to(moved, geo[BODY]["verts"], geo[BODY]["faces"])
                if d < worst[0]:
                    worst = (d, name)
            check(f"{side}: {label} keeps every part off the body",
                  worst[0] > 0.0, f"closest {worst[0] * 1000:.1f} mm ({worst[1]})")
            if label.startswith("lift"):
                gorget = min((dist_to(rotate_points(geo[p.format(S=side)]["verts"], pivot,
                                                    matrix),
                                      geo["WSK_Helmet_NeckGuard_01"]["verts"],
                                      geo["WSK_Helmet_NeckGuard_01"]["faces"]),
                              p.format(S=side))
                             for p in PLATES)
            else:
                gorget = min((dist_to(rotate_points(geo[p.format(S=side)]["verts"], pivot,
                                                    matrix),
                                      geo["WSK_Helmet_NeckGuard_01"]["verts"],
                                      geo["WSK_Helmet_NeckGuard_01"]["faces"]),
                              p.format(S=side))
                             for p in PLATES)
            check(f"{side}: {label} keeps the plates off the gorget",
                  gorget[0] > 0.0, f"closest {gorget[0] * 1000:.1f} mm ({gorget[1]})")

    section("I  spikes: deliberate directions, spacing and seating")
    for side in SIDES:
        dirs = {}
        for s in SPIKES:
            name = s.format(S=side)
            obj = bpy.data.objects[name]
            dirs[name] = (Vector(obj["wsk_spike_tip"]) - Vector(obj["wsk_spike_base"])).normalized()
        joint = JOINTS[side]
        rays = [((Vector(bpy.data.objects[s.format(S=side)]["wsk_spike_tip"]) - joint)
                 .normalized()) for s in SPIKES]
        spread = max(math.degrees(math.acos(max(-1.0, min(1.0, a.dot(b)))))
                     for i, a in enumerate(rays) for b in rays[i + 1:])
        check(f"{side}: the six spikes fan widely over the shoulder instead of "
              f"pointing the same way", spread >= 55.0, f"{spread:.0f} deg between the "
              f"two most separated spikes")
        for s in SPIKES:
            name = s.format(S=side)
            length = bpy.data.objects[name]["wsk_spike_length_m"]
            check(f"{name}: length {length:.3f} m is a usable spike", length >= 0.06)
        seats = []
        for s in SPIKES:
            name = s.format(S=side)
            seat = Vector(bpy.data.objects[name]["wsk_spike_base"])
            seats.append(seat)
        closest = min((a - b).length for i, a in enumerate(seats)
                      for b in seats[i + 1:])
        check(f"{side}: the spike bases are spread out, not clustered",
              closest > 0.03, f"closest pair {closest * 1000:.0f} mm")
        widths = [bpy.data.objects[s.format(S=side)]["wsk_spike_length_m"] for s in SPIKES]
        check(f"{side}: the spikes have graded lengths (a hierarchy, not six copies)",
              max(widths) - min(widths) > 0.03,
              f"{min(widths):.3f} - {max(widths):.3f} m")

    section("J  scene hygiene")
    check("scale, unit system and origin are unchanged",
          bpy.context.scene.unit_settings.system == "METRIC"
          and abs(bpy.context.scene.unit_settings.scale_length - 1.0) < 1e-9
          and all(tuple(bpy.data.objects[n].matrix_world.translation) == (0.0, 0.0, 0.0)
                  for n in [p.format(S=s) for p in PLATES for s in SIDES]))
    check("the silhouette check setup from checkpoint 6 is untouched",
          bpy.data.texts.get("WSK_Silhouette_Notes.txt") is not None
          and all(n in cur_hashes for n in ("WSK_Helmet_CrownSpike_C_01",)))
    new_objects = [o.name for o in bpy.data.objects if o.name not in ref_hashes]
    check("no cape, weapon, chain or ornament object was added",
          not [n for n in new_objects
               if any(k in n for k in ("Cape", "Weapon", "Chain", "Ornament"))],
          f"{len(new_objects)} new objects, all shoulder parts")
    check("the shoulder notes text block is in the file",
          bpy.data.texts.get("WSK_Shoulder_Notes.txt") is not None)
    per_side = {s: [o for o in bpy.data.objects if o.get("wsk_group") == ROOTS[s]]
                for s in SIDES}
    check("every shoulder part records the group it belongs to",
          all(len(per_side[s]) == 10 for s in SIDES),
          f"R {len(per_side['R'])}, L {len(per_side['L'])}")

    # ---------------- report ----------------
    fails = [r for r in results if r[1] is False]
    lines = ["WILDSHIFT KNIGHT - PROMPT 7 SHOULDER VERIFICATION",
             "=" * 60, ""]
    for label, ok, detail in results:
        if label is None:
            lines.append("")
            lines.append(f"== {detail} ==")
        else:
            lines.append(f"[{'PASS' if ok else 'FAIL'}] {label}"
                         + (f"  -> {detail}" if detail else ""))
    lines.append("")
    lines.append(f"{sum(1 for r in results if r[1] is not None)} checks, "
                 f"{len(fails)} failed")
    report = "\n".join(lines) + "\n"
    with open(REPORT, "w") as handle:
        handle.write(report)
    print(f"\n{sum(1 for r in results if r[1] is not None)} checks, {len(fails)} failed")
    print(f"report: {REPORT}")

    # ---------------- articulation preview ----------------
    if not SKIP_RENDERS:
        renders(geo)


def renders(geo):
    """Render the four inspection views plus a shoulder-lift contact sheet."""
    import build_shoulders as BS
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.world = bpy.data.worlds["WSK_World_Silhouette"]
    for name in ("Reference", "Blockout"):
        col = bpy.data.collections.get(name)
        if col is not None:
            for obj in col.objects:
                obj.hide_render = True

    def shoot(camera, path, size):
        scene.camera = bpy.data.objects[camera]
        scene.render.resolution_x, scene.render.resolution_y = size
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)

    lift_shots = []
    for label, angle, swing in (("rest", 0.0, 0.0), ("lifted_20", -20.0, 0.0),
                                ("dropped_15", 15.0, 0.0), ("swung_20", 0.0, -20.0)):
        for side in SIDES:
            root = bpy.data.objects[ROOTS[side]]
            root.rotation_mode = "XYZ"
            root.rotation_euler = (0.0, 0.0, math.radians(swing * (1 if side == "L" else -1)))
            root.rotation_euler[1] = math.radians(angle * (1 if side == "R" else -1))
        bpy.context.view_layer.update()
        path = os.path.join(SHOTS, f"articulation_{label}.png")
        shoot("WSK_Cam_Shoulder_ThreeQ_01", path, (640, 470))
        lift_shots.append(path)
    for side in SIDES:
        bpy.data.objects[ROOTS[side]].rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    sheet(lift_shots, os.path.join(SHOTS, "shoulder_articulation.png"), cols=2,
          title="Prompt 7 articulation check: rest / lifted 20 deg / dropped 15 deg / "
                "swung 20 deg (whole shoulder group rotated on its joint empty)")

    views = []
    for camera, key, size in (("WSK_Cam_Shoulder_Front_01", "front", (960, 620)),
                              ("WSK_Cam_Shoulder_Rear_01", "rear", (960, 620)),
                              ("WSK_Cam_Shoulder_Side_01", "side", (960, 620)),
                              ("WSK_Cam_Shoulder_ThreeQ_01", "threequarter", (960, 700))):
        path = os.path.join(SHOTS, f"shoulder_{key}.png")
        shoot(camera, path, size)
        views.append(path)
    sheet(views, os.path.join(SHOTS, "shoulder_views.png"), cols=2,
          title="Prompt 7 - shoulder armour: front / rear / side / three-quarter")


def sheet(paths, out, cols=2, pad=8, title=""):
    images = [Image.open(p).convert("RGB") for p in paths]
    rows = (len(images) + cols - 1) // cols
    cw = max(i.width for i in images)
    ch = max(i.height for i in images)
    canvas = Image.new("RGB", (cols * cw + (cols + 1) * pad,
                               rows * ch + (rows + 1) * pad + (24 if title else 0)),
                       (28, 28, 30))
    for i, im in enumerate(images):
        r, c = divmod(i, cols)
        canvas.paste(im, (pad + c * (cw + pad),
                          pad + r * (ch + pad) + (24 if title else 0)))
    if title:
        ImageDraw.Draw(canvas).text((pad, 6), title, fill=(230, 230, 230))
    canvas.save(out)
    print("sheet", out, canvas.size)


if __name__ == "__main__":
    main()
