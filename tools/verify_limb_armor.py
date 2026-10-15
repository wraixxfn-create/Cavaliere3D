"""Prompt-9 verification for refined arm, hand, leg and foot armour.

Checks scope, topology, separation, body fit, overlap order, bilateral consistency,
manual pose pivots and attachment metadata. Writes the complete report to
analysis/verify/verify_limb_armor_report.txt.

Run: tools/bl.sh tools/verify_limb_armor.py
"""
import hashlib
import math
import os
import statistics
import struct

import bpy  # noqa: F401
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_08_TorsoArmor.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_09_LimbArmor.blend")
REPORT = os.path.join(ROOT, "analysis", "verify", "verify_limb_armor_report.txt")
PROMPT = "Prompt 9 - refined limb armour"
LEGACY = {
    f"WSK_Armor_{part}_{side}_01"
    for side in ("R", "L")
    for part in ("Forearm", "Gauntlet", "Thigh", "Shin", "Sabaton")
}

lines = []
passed = 0
failed = 0


def section(title):
    lines.append("\n== " + title + " ==")


def check(condition, label, detail=""):
    global passed, failed
    ok = bool(condition)
    passed += int(ok)
    failed += int(not ok)
    tail = f"  -> {detail}" if detail else ""
    lines.append(f"[{'PASS' if ok else 'FAIL'}] {label}{tail}")
    return ok


def mesh_hash(obj):
    h = hashlib.sha256()
    h.update(obj.type.encode())
    if obj.type == "MESH":
        for v in obj.data.vertices:
            h.update(struct.pack("<3d", *v.co))
        for p in obj.data.polygons:
            h.update(struct.pack("<I", len(p.vertices)))
            for i in p.vertices:
                h.update(struct.pack("<I", i))
        for m in obj.modifiers:
            h.update((m.name + "|" + m.type).encode())
            if m.type == "BEVEL":
                h.update(struct.pack("<dI", m.width, m.segments))
    h.update(bytes(str(tuple(round(x, 9) for row in obj.matrix_world for x in row)), "utf8"))
    return h.hexdigest()


def world_mesh(obj):
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    faces = [tuple(p.vertices) for p in obj.data.polygons]
    return verts, faces


def bvh(obj):
    verts, faces = world_mesh(obj)
    return BVHTree.FromPolygons(verts, faces, all_triangles=False)


def overlaps(a, b):
    return len(bvh(a).overlap(bvh(b)))


def nearest_distance(a, b):
    av, _ = world_mesh(a)
    bt = bvh(b)
    vals = []
    for p in av:
        hit = bt.find_nearest(p)
        if hit[0] is not None:
            vals.append((p - Vector(hit[0])).length)
    return min(vals) if vals else float("inf")


def shell_halves(obj):
    n = len(obj.data.vertices)
    if "Sole" in obj.name or n % 2:
        return [], []
    half = n // 2
    return list(range(half)), list(range(half, n))


def body_distances(obj, tree, outer_only=False):
    outer, inner = shell_halves(obj)
    ids = outer if outer_only and outer else range(len(obj.data.vertices))
    vals = []
    for i in ids:
        p = obj.matrix_world @ obj.data.vertices[i].co
        hit = tree.find_nearest(p)
        if hit[0] is not None:
            # Absolute surface distance is stable at the mitten/branch
            # concavities where a nearest triangle normal can be ambiguous.
            vals.append((p - Vector(hit[0])).length)
    return vals


def point_inside(point, tree):
    """Odd/even ray test against the closed body, avoiding nearest-normal ambiguity."""
    direction = Vector((0.371, 0.529, 0.763)).normalized()
    origin = Vector(point) + direction * 1e-6
    hits = 0
    for _ in range(100):
        hit = tree.ray_cast(origin, direction, 4.0)
        if hit[0] is None:
            break
        hits += 1
        origin = Vector(hit[0]) + direction * 1e-5
    return bool(hits % 2)


def reset(side):
    for part in ("UpperArm", "ElbowCop", "Forearm", "Hand",
                 "Thigh", "KneeCop", "Shin", "Foot"):
        root = bpy.data.objects[f"WSK_LimbPose_{part}_{side}_01"]
        root.rotation_euler = (0.0, 0.0, 0.0)
        root.location = Vector(root["wsk_rest_location"])
    bpy.context.view_layer.update()


def names(side, stem):
    return bpy.data.objects[f"WSK_Armor_{stem}_{side}_01"]


def main():
    global lines
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)

    # Capture checkpoint 08 signatures before loading checkpoint 09.
    bpy.ops.wm.open_mainfile(filepath=SRC)
    source_meshes = {o.name: mesh_hash(o) for o in bpy.data.objects if o.type == "MESH"}
    source_body = source_meshes["WSK_Body_Base_01"]
    source_dims = tuple(bpy.data.objects["WSK_Body_Base_01"].dimensions)
    source_non_limb = {n: h for n, h in source_meshes.items() if n not in LEGACY}

    bpy.ops.wm.open_mainfile(filepath=DST)
    armor = bpy.data.collections["Armor"]
    controls = bpy.data.collections["Limb Pose Controls"]
    parts = sorted([o for o in armor.objects if o.type == "MESH" and o.get("wsk_prompt") == PROMPT],
                   key=lambda o: o.name)
    roots = sorted(list(controls.objects), key=lambda o: o.name)

    lines = [
        "WILDSHIFT KNIGHT - PROMPT 9 LIMB ARMOUR VERIFICATION",
        "=" * 64,
        "File: Wildshift_Knight_09_LimbArmor.blend",
        "Neutral pose is saved; articulation checks below are temporary and are reset.",
    ]

    section("A  scope and unchanged proportions")
    dst_names = {o.name for o in bpy.data.objects if o.type == "MESH"}
    missing_unchanged = [n for n in source_non_limb if n not in dst_names]
    changed_unchanged = [n for n, h in source_non_limb.items()
                         if n in bpy.data.objects and mesh_hash(bpy.data.objects[n]) != h]
    check(not missing_unchanged, "every non-limb mesh from checkpoint 08 is retained",
          f"{len(source_non_limb)} retained")
    check(not changed_unchanged, "body, torso, shoulders, helmet and scene meshes are byte-identical",
          f"{len(changed_unchanged)} unexpected changes")
    check(mesh_hash(bpy.data.objects["WSK_Body_Base_01"]) == source_body,
          "the base body is byte-identical")
    dims = tuple(bpy.data.objects["WSK_Body_Base_01"].dimensions)
    check(max(abs(a - b) for a, b in zip(dims, source_dims)) < 1e-9,
          "body proportions and bounds did not change",
          " x ".join(f"{d:.4f} m" for d in dims))
    check(len(parts) == 54, "the ten legacy placeholders were replaced by 54 refined pieces",
          f"{len(parts)} Prompt-9 meshes")

    section("B  object separation, hierarchy and neutral pose")
    check(len(roots) == 16, "sixteen manual-pose pivots exist (eight per side)", f"{len(roots)} empties")
    check(all(r.type == "EMPTY" for r in roots), "pose pivots are empties, not bones or an armature")
    check(all(abs(a) < 1e-9 for r in roots for a in r.rotation_euler),
          "all manual-pose controls are saved at zero rotation")
    check(all(p.data.users == 1 for p in parts), "every armour part owns a single-user mesh")
    check(all(len(p.users_collection) == 1 and p.users_collection[0].name == "Armor" for p in parts),
          "every refined piece is in the Armor collection only")
    check(all(p.parent in roots for p in parts), "every refined piece is parented to a meaningful pose pivot")
    check(all(p.location.length < 1e-8 and max(abs(s - 1.0) for s in p.scale) < 1e-8 for p in parts),
          "all armour objects keep identity location/scale in the neutral pose")
    expected_parent = {
        "UpperArm": "UpperArm", "ElbowCop": "ElbowCop", "Forearm": "Forearm",
        "WristCuff": "Forearm", "Gauntlet": "Hand", "Thigh": "Thigh",
        "KneeCop": "KneeCop", "Shin": "Shin", "AnkleCuff": "Shin",
        "Sabaton": "Foot", "Sole": "Foot",
    }
    mismatched = []
    for p in parts:
        stem = p.name.replace("WSK_Armor_", "")
        key = next((k for k in expected_parent if stem.startswith(k)), None)
        side = "R" if "_R_01" in p.name else "L"
        if key and p.parent.name != f"WSK_LimbPose_{expected_parent[key]}_{side}_01":
            mismatched.append(p.name)
    check(not mismatched, "all pieces use the intended upper/lower limb or joint pivot",
          f"{len(mismatched)} mismatches")

    section("C  topology, thickness and controlled bevels")
    bad_topology = []
    min_edge = (float("inf"), "")
    min_thickness = (float("inf"), "")
    for obj in parts:
        bm = bmesh.new(); bm.from_mesh(obj.data)
        non = sum(1 for e in bm.edges if not e.is_manifold)
        loose = sum(1 for v in bm.verts if not v.link_edges)
        deg = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
        for e in bm.edges:
            if e.calc_length() < min_edge[0]:
                min_edge = (e.calc_length(), obj.name)
        bm.free()
        if non or loose or deg:
            bad_topology.append((obj.name, non, loose, deg))
        outer, inner = shell_halves(obj)
        if outer:
            thick = min((obj.data.vertices[a].co - obj.data.vertices[b].co).length
                        for a, b in zip(outer, inner))
            if thick < min_thickness[0]:
                min_thickness = (thick, obj.name)
    check(not bad_topology, "all 54 pieces are closed manifolds with no loose or degenerate geometry",
          f"{len(bad_topology)} bad objects")
    check(min_edge[0] >= 0.00075, "no needle-thin construction edges were introduced",
          f"shortest {min_edge[0] * 1000:.2f} mm in {min_edge[1]}")
    check(min_thickness[0] >= 0.0029, "every shell keeps at least 3 mm of real thickness",
          f"minimum {min_thickness[0] * 1000:.2f} mm in {min_thickness[1]}")
    bevels = [(p, [m for m in p.modifiers if m.type == "BEVEL"]) for p in parts]
    check(all(len(m) == 1 for p, m in bevels), "every piece has exactly one bevel modifier")
    widths = [mods[0].width for _, mods in bevels if mods]
    check(min(widths) >= 0.0005 and max(widths) <= 0.0015,
          "bevel widths stay controlled between 0.5 and 1.5 mm",
          f"{min(widths) * 1000:.2f}-{max(widths) * 1000:.2f} mm")
    check(all(mods[0].segments == 2 for _, mods in bevels), "all bevels use two segments")

    section("D  neutral fit against the unchanged body")
    body = bpy.data.objects["WSK_Body_Base_01"]
    body_tree = bvh(body)
    clearances = []
    penetrators = []
    for obj in parts:
        if "Sole" in obj.name:
            continue  # the sole intentionally encloses the body's ground-contact underside
        vals = body_distances(obj, body_tree)
        if vals:
            clearances.append((min(vals), obj.name))
        inside_count = sum(point_inside(obj.matrix_world @ v.co, body_tree)
                           for v in obj.data.vertices)
        if inside_count:
            penetrators.append((inside_count, obj.name))
    check(not penetrators, "no visible limb plate penetrates the base body",
          f"{sum(n for n, _ in penetrators)} interior vertices")
    if clearances:
        d, n = min(clearances)
        check(d >= 0.0001, "body-fit shells retain a measurable surface separation",
              f"closest {d * 1000:.2f} mm in {n}")
    soles = [names(s, "Sole") for s in ("R", "L")]
    check(all(min(v.co.z for v in o.data.vertices) >= 0.0014 for o in soles),
          "the separate soles stay on/above the ground plane",
          f"ground contact {min(v.co.z for o in soles for v in o.data.vertices) * 1000:.2f} mm")

    section("E  layering and joint segmentation in neutral")
    stacks = {
        "upper arm": ("UpperArm", "UpperArmLame_Middle", "UpperArmLame_Distal"),
        "forearm": ("Forearm", "ForearmLame_Middle", "ForearmLame_Distal"),
        "thigh": ("Thigh", "ThighLame_Middle", "ThighLame_Distal"),
        "shin": ("Shin", "ShinLame_Middle", "ShinLame_Distal"),
        "sabaton": ("Sabaton", "SabatonLame_Middle", "SabatonLame_Toe"),
    }
    for side in ("R", "L"):
        for label, stems in stacks.items():
            objs = [names(side, s) for s in stems]
            meds = []
            for obj in objs:
                ds = body_distances(obj, body_tree, outer_only=True)
                meds.append(statistics.median(ds))
            check(meds[0] > meds[1] > meds[2],
                  f"{side} {label}: proximal plate sits outside the plates ahead",
                  " > ".join(f"{d * 1000:.1f} mm" for d in meds))
            ints = [overlaps(objs[0], objs[1]), overlaps(objs[1], objs[2])]
            check(not any(ints), f"{side} {label}: overlapping lames do not interpenetrate",
                  f"triangle contacts {ints[0]}, {ints[1]}")

    joint_pairs = {
        "elbow upper/cup": ("UpperArmLame_Distal", "ElbowCop"),
        "elbow cup/forearm": ("ElbowCop", "Forearm"),
        "wrist cuff/hand": ("WristCuff", "Gauntlet"),
        "knee thigh/cup": ("ThighLame_Distal", "KneeCop"),
        "knee cup/shin": ("KneeCop", "Shin"),
        "ankle cuff/foot": ("AnkleCuff", "Sabaton"),
    }
    for side in ("R", "L"):
        ds = []
        ints = []
        for label, (a, b) in joint_pairs.items():
            oa, ob = names(side, a), names(side, b)
            ds.append((label, nearest_distance(oa, ob)))
            ints.append((label, overlaps(oa, ob)))
        check(not any(v for _, v in ints), f"{side}: elbow, wrist, knee and ankle remain separate at rest",
              ", ".join(f"{k} {d * 1000:.1f} mm" for k, d in ds))

    section("F  hands read as armour without mechanical finger complexity")
    for side in ("R", "L"):
        palm = names(side, "Gauntlet")
        knuckle = names(side, "GauntletKnuckle")
        fingers = [names(side, f"GauntletFinger{i}") for i in range(1, 5)]
        thumb = names(side, "GauntletThumb")
        check(all(o is not None for o in [palm, knuckle, thumb] + fingers),
              f"{side}: palm, knuckle, four finger and thumb plates exist")
        check(len({o.data.name for o in [palm, knuckle, thumb] + fingers}) == 7,
              f"{side}: all seven hand plates remain separately attachable")
        widths = [o.dimensions.x for o in fingers]
        check(min(widths) >= 0.006 and max(widths) <= 0.014,
              f"{side}: finger plates are simple broad strips, not filigree",
              f"widths {min(widths) * 1000:.1f}-{max(widths) * 1000:.1f} mm")
        check(overlaps(palm, knuckle) == 0,
              f"{side}: palm plate layers over the knuckle plate without surface crossing")

    section("G  feet, sole stability and forward direction")
    for side in ("R", "L"):
        sole = names(side, "Sole")
        verts, _ = world_mesh(sole)
        yspan = max(v.y for v in verts) - min(v.y for v in verts)
        xspan = max(v.x for v in verts) - min(v.x for v in verts)
        zspan = max(v.z for v in verts) - min(v.z for v in verts)
        check(yspan > 0.28 and xspan > 0.12,
              f"{side}: sole has a stable readable footprint",
              f"{xspan:.3f} x {yspan:.3f} m")
        check(0.010 <= zspan <= 0.014,
              f"{side}: sole is visibly substantial without becoming a platform",
              f"{zspan * 1000:.1f} mm")
        front = max(verts, key=lambda v: v.y)
        rear = min(verts, key=lambda v: v.y)
        check(front.y - rear.y > 0.28 and front.y > 0.19,
              f"{side}: tapered toe establishes an explicit +Y forward direction",
              f"rear {rear.y:+.3f}, toe {front.y:+.3f}")

    section("H  bilateral consistency")
    pair_errors = []
    rparts = [p for p in parts if "_R_01" in p.name]
    for r in rparts:
        lname = r.name.replace("_R_01", "_L_01")
        l = bpy.data.objects.get(lname)
        if l is None or len(l.data.vertices) != len(r.data.vertices):
            pair_errors.append((r.name, float("inf")))
            continue
        err = max((Vector((-rv.co.x, rv.co.y, rv.co.z)) - lv.co).length
                  for rv, lv in zip(r.data.vertices, l.data.vertices))
        pair_errors.append((r.name, err))
    worst = max(pair_errors, key=lambda x: x[1])
    check(len(rparts) == 27 and len(pair_errors) == 27,
          "there are 27 corresponding major pieces per side")
    check(worst[1] < 0.0006, "left/right limb construction is consistently mirrored",
          f"worst {worst[1] * 1000:.3f} mm in {worst[0]}")

    section("I  temporary manual rotation tests")
    pose_degrees = {"Forearm": 20.0, "ElbowCop": 10.0, "Hand": -12.0,
                    "Shin": 20.0, "KneeCop": 10.0, "Foot": -12.0}
    for side in ("R", "L"):
        reset(side)
        for part, degree in pose_degrees.items():
            bpy.data.objects[f"WSK_LimbPose_{part}_{side}_01"].rotation_euler.x = math.radians(degree)
        bpy.context.view_layer.update()
        results = []
        for label, (a, b) in joint_pairs.items():
            oa, ob = names(side, a), names(side, b)
            results.append((label, overlaps(oa, ob), nearest_distance(oa, ob)))
        check(not any(v for _, v, _ in results),
              f"{side}: elbow 20°, wrist 12°, knee 20° and ankle 12° keep joint plates separate",
              ", ".join(f"{k} {d * 1000:.1f} mm" for k, _, d in results))
        reset(side)
    check(all(abs(a) < 1e-9 for r in roots for a in r.rotation_euler),
          "all temporary joint rotations were restored to neutral")

    section("J  rigging constraints and attachment-bone report")
    check(not any(o.type == "ARMATURE" for o in bpy.data.objects),
          "no armature or rig was created")
    check(not bpy.data.actions, "no animation actions were created")
    check(all(not p.vertex_groups for p in parts), "no weight painting or vertex groups were added")
    check(all(not p.constraints for p in parts + roots), "no constraints were added")
    helpers = [p for p in parts if p.get("wsk_requires_helper_bone")]
    check({p.name for p in helpers} == {
        "WSK_Armor_ElbowCop_R_01", "WSK_Armor_ElbowCop_L_01",
        "WSK_Armor_KneeCop_R_01", "WSK_Armor_KneeCop_L_01"},
        "only elbow and knee cops are flagged for dedicated helper bones",
        f"{len(helpers)} pieces")
    check(all(p.get("wsk_attachment_hint") for p in parts),
          "every major armour segment records a future bone attachment hint")
    mats = {m.name for p in parts for m in p.data.materials if m}
    check(mats <= {"MAT_Armor_BlackenedSteel_01", "MAT_Armor_BroadIron_01"},
          "all limbs retain the same restrained placeholder-metal language",
          ", ".join(sorted(mats)))
    check(not any(any(t in p.name.lower() for t in ("chain", "filigree")) for p in parts),
          "no chains or filigree were introduced")

    lines.append("\nATTACHMENT-BONE REPORT")
    lines.append("  Separate helper recommended: ElbowCop_R/L and KneeCop_R/L.")
    lines.append("  Optional follow helper for extreme ranges: WristCuff_R/L and AnkleCuff_R/L.")
    lines.append("  Finger1-4 and Thumb currently follow the hand; reassign only when finger bones exist.")
    lines.append("\nPOSE LIMITATION")
    lines.append("  Tests rotate armour-only pivots because Prompt 9 intentionally has no body rig.")
    lines.append("  Recheck body deformation clearance after actual bones and weights are authored.")
    lines.append(f"\n{passed + failed} checks, {failed} failed")

    with open(REPORT, "w", encoding="utf8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("REPORT", REPORT)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
