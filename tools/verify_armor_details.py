"""Prompt-12 verification for the selective engravings and gothic trim.

Checks scope (what changed and what did not), the placement of every ornament on
its host plate - the part the prompt asks for explicitly: details must follow the
underlying shape instead of visibly floating - the design budget (sparse, narrow,
shallow, mirrored), mesh quality, foreign clearance, and a gameplay-distance
render read (visible gold, silhouette unchanged).

Writes analysis/verify/verify_armor_details_report.txt.

Run: tools/bl.sh tools/verify_armor_details.py
"""
import hashlib
import math
import os
import struct

import bpy  # noqa: F401
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_11_Medallion.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_12_ArmorDetails.blend")
SHOTS = os.path.join(ROOT, "analysis/armor_details")
REPORT = os.path.join(ROOT, "analysis/verify/verify_armor_details_report.txt")

GOLD = "MAT_Armor_AntiqueGold_01"
ORNAMENTS = {
    "WSK_Decor_ChestKeelTrim_01": "WSK_Armor_Chest_01",
    "WSK_Decor_ChestChevron_L_01": "WSK_Armor_Chest_01",
    "WSK_Decor_ChestChevron_R_01": "WSK_Armor_Chest_01",
    "WSK_Decor_BeltTrimTop_L_01": "WSK_Armor_WaistBelt_01",
    "WSK_Decor_BeltTrimTop_R_01": "WSK_Armor_WaistBelt_01",
    "WSK_Decor_BrowTrim_L_01": "WSK_Helmet_CrownBand_01",
    "WSK_Decor_BrowTrim_R_01": "WSK_Helmet_CrownBand_01",
    "WSK_Decor_KneeRidge_L_01": "WSK_Armor_KneeCop_L_01",
    "WSK_Decor_KneeRidge_R_01": "WSK_Armor_KneeCop_R_01",
    "WSK_Decor_ShinRidge_L_01": "WSK_Armor_Shin_L_01",
    "WSK_Decor_ShinRidge_R_01": "WSK_Armor_Shin_R_01",
}
PAIRS = [
    ("WSK_Decor_ChestChevron_L_01", "WSK_Decor_ChestChevron_R_01"),
    ("WSK_Decor_BeltTrimTop_L_01", "WSK_Decor_BeltTrimTop_R_01"),
    ("WSK_Decor_BrowTrim_L_01", "WSK_Decor_BrowTrim_R_01"),
    ("WSK_Decor_KneeRidge_L_01", "WSK_Decor_KneeRidge_R_01"),
    ("WSK_Decor_ShinRidge_L_01", "WSK_Decor_ShinRidge_R_01"),
]
MEDALLION = [f"WSK_Armor_WaistMedallionRay_{i:02d}_01" for i in range(1, 13)] + \
    ["WSK_Armor_WaistMedallionRing_01", "WSK_Armor_WaistMedallionCore_01"]

# placement budgets (metres)
REAR_MIN, REAR_MAX = -0.0013, 0.00005     # seated: at most 1.3 mm into the plate
LIFT_MIN, LIFT_MAX = 0.0008, 0.0032       # mid-path crown relief
CHAMFER_MIN = 0.0000                      # chamfer ring never below the surface
ALL_MIN, ALL_MAX = -0.0013, 0.0032
FOREIGN_CLEAR = 0.0008                    # to any non-host armour
WIDTH_BUDGET = (0.005, 0.0115)            # full width
RELIEF_BUDGET = (0.0015, 0.0027)

lines = []
passed = failed = warned = 0


def section(title):
    lines.append("\n== " + title + " ==")


def check(cond, label, detail=""):
    global passed, failed
    ok = bool(cond)
    passed += int(ok)
    failed += int(not ok)
    lines.append(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))
    return ok


def note(text):
    lines.append("      " + text)


def warn(cond, label, detail=""):
    global warned
    if not cond:
        warned += 1
    lines.append(f"[{'WARN' if not cond else 'OK  '}] {label}" + (f"  -> {detail}" if detail else ""))


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
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
            h.update(m.type.encode())
            for attr in ("width", "thickness", "levels", "angle_limit", "segments",
                         "use_clamp_overlap", "limit_method"):
                if hasattr(m, attr):
                    value = getattr(m, attr)
                    if isinstance(value, (int, float)):
                        h.update(struct.pack("<d", float(value)))
                    elif isinstance(value, str):
                        h.update(value.encode())
    for row in obj.matrix_world:
        h.update(struct.pack("<4d", *row))
    h.update((obj.parent.name if obj.parent else "").encode())
    return h.hexdigest()


_EVAL_CACHE = {}


def evaluated(obj):
    key = (obj.name, bpy.data.filepath)
    if key not in _EVAL_CACHE:
        bpy.context.view_layer.update()
        deps = bpy.context.evaluated_depsgraph_get()
        eo = obj.evaluated_get(deps)
        me = eo.to_mesh()
        mw = eo.matrix_world.copy()
        verts = [mw @ v.co for v in me.vertices]
        faces = [tuple(p.vertices) for p in me.polygons]
        eo.to_mesh_clear()
        _EVAL_CACHE[key] = (verts, faces)
    return _EVAL_CACHE[key]


def bvh_of(names, skip=()):
    verts, faces = [], []
    for name in names:
        if name in skip:
            continue
        v, f = evaluated(bpy.data.objects[name])
        off = len(verts)
        verts += v
        faces += [tuple(i + off for i in face) for face in f]
    return BVHTree.FromPolygons(verts, faces, all_triangles=False), len(verts)


def all_armor_names():
    names = []
    for col in ("Armor", "Helmet", "Crown", "Body"):
        for o in bpy.data.collections[col].objects:
            if o.type == "MESH":
                names.append(o.name)
    return names


def signed_distances(tree, verts):
    out = []
    for v in verts:
        hit = tree.find_nearest(v)
        if hit[0] is None:
            out.append(None)
        else:
            out.append(((v - hit[0]).dot(hit[1].normalized()), hit[3]))
    return out


def mesh_extent(obj):
    """World-space base-mesh vertices (the designed surface, bevel not applied)."""
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


def render_setup(scene, res=(460, 575), samples=8):
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    for o in bpy.data.objects:
        if o.name.startswith(("WSK_Guide_", "WSK_Label_", "WSK_Ref_", "WSK_Joint_",
                              "WSK_Mann_", "WSK_Studio_", "WSK_Blockout")):
            o.hide_render = True


def alpha_mask(path):
    im = np.asarray(Image.open(path).convert("RGBA"), dtype=np.int16)
    return im[:, :, 3] > 127


def gold_pixels(path):
    im = np.asarray(Image.open(path).convert("RGBA"), dtype=np.int16)
    r, g, b, a = im[:, :, 0], im[:, :, 1], im[:, :, 2], im[:, :, 3]
    gold = (a > 127) & (r - b > 18) & (r > 45) & (r >= g) & (g >= b - 6)
    return int(gold.sum()), int((a > 127).sum())


# --------------------------------------------------------------------------
def main():
    os.makedirs(SHOTS, exist_ok=True)

    # ---- scope: what changed ---------------------------------------------
    section("scope - checkpoint 11 is untouched")
    bpy.ops.wm.open_mainfile(filepath=SRC)
    src_hashes = {o.name: mesh_hash(o) for o in bpy.data.objects}
    src_mats = sorted(m.name for m in bpy.data.materials)
    src_cols = sorted(c.name for c in bpy.data.collections)
    src_cam = sorted(o.name for o in bpy.data.objects if o.type in ("CAMERA", "LIGHT"))
    n_src = len(src_hashes)

    bpy.ops.wm.open_mainfile(filepath=DST)
    dst_hashes = {o.name: mesh_hash(o) for o in bpy.data.objects}
    dst_mats = sorted(m.name for m in bpy.data.materials)
    dst_cols = sorted(c.name for c in bpy.data.collections)
    dst_cam = sorted(o.name for o in bpy.data.objects if o.type in ("CAMERA", "LIGHT"))

    new_names = sorted(set(dst_hashes) - set(src_hashes))
    check(new_names == sorted(ORNAMENTS),
          "exactly the eleven ornaments were added",
          f"{len(new_names)} new: {', '.join(n.replace('WSK_Decor_', '') for n in new_names)}")
    check(not (set(src_hashes) - set(dst_hashes)), "nothing was deleted",
          f"{n_src} checkpoint-11 objects all still present")
    changed = [n for n in src_hashes if dst_hashes.get(n) != src_hashes[n]]
    check(not changed,
          f"all {n_src} checkpoint-11 objects byte-identical (mesh, modifiers, matrix, parent)",
          f"changed: {changed}" if changed else "no host plate, medallion part, limb, body or guide moved")
    check(dst_mats == src_mats, "no material added or removed",
          f"{len(dst_mats)} materials, identical set")
    check(dst_cols == src_cols, "no collection added or removed",
          f"{len(dst_cols)} collections, identical set")
    check(dst_cam == src_cam, "no camera or light added or removed", f"{len(dst_cam)} entries")

    gold = bpy.data.materials[GOLD]
    bsdf = gold.node_tree.nodes.get("Principled BSDF")
    emis = [i.default_value for i in bsdf.inputs if i.name == "Emission Strength"]
    check(all(abs(float(e)) < 1e-9 for e in emis), f"{GOLD} carries no emission")
    note(f"{GOLD}: metallic {gold.metallic:.1f}, roughness {gold.roughness:.2f}, "
         f"base {tuple(round(float(c), 3) for c in bsdf.inputs['Base Color'].default_value[:3])}")

    # ---- materials on the ornaments --------------------------------------
    section("components and material")
    ok_mat = True
    for name in ORNAMENTS:
        o = bpy.data.objects[name]
        mats = [m.name for m in o.data.materials]
        if mats != [GOLD]:
            ok_mat = False
    check(ok_mat, "every ornament wears only the antique-gold placeholder", GOLD)
    parents_ok = all(bpy.data.objects[n].parent and bpy.data.objects[n].parent.name == h
                     for n, h in ORNAMENTS.items())
    check(parents_ok, "every ornament is parented to the plate it decorates",
          ", ".join(sorted({f"{h}" for h in ORNAMENTS.values()})))
    identity_ok = all(
        all(abs(bpy.data.objects[n].matrix_parent_inverse[r][c] - (1.0 if r == c else 0.0)) < 1e-9
            for r in range(4) for c in range(4))
        for n in ORNAMENTS)
    check(identity_ok, "identity local transforms after parenting (world placement kept)")
    bevel_ok = all(
        [m.type for m in bpy.data.objects[n].modifiers] == ["BEVEL"] and
        bpy.data.objects[n].modifiers[0].name == "WSK_Decor_EdgeBevel"
        for n in ORNAMENTS)
    check(bevel_ok, "one unapplied edge bevel per ornament, nothing destructive")

    # ---- mesh quality -----------------------------------------------------
    section("mesh quality")
    bad_closed, bad_norm, bad_genus, tot_verts = [], [], [], 0
    for name in ORNAMENTS:
        o = bpy.data.objects[name]
        verts = mesh_extent(o)
        faces = [tuple(p.vertices) for p in o.data.polygons]
        tot_verts += len(verts)
        edges = set()
        degree_sum = 0
        for f in faces:
            for i in range(len(f)):
                edges.add(tuple(sorted((f[i], f[(i + 1) % len(f)]))))
            degree_sum += len(f)
        boundary = [e for e in edges if sum(1 for f in faces if e[0] in f and e[1] in f) < 2]
        if boundary or 2 * len(edges) != degree_sum:
            bad_closed.append(name)
        v, e, f = len(verts), len(edges), len(faces)
        if v - e + f != 2:
            bad_genus.append(f"{name} (V-E+F={v - e + f})")
        # signed volume > 0 -> outward normals (fan triangulation of each face)
        vol = 0.0
        for face in faces:
            p0 = verts[face[0]]
            for k in range(1, len(face) - 1):
                vol += p0.dot(verts[face[k]].cross(verts[face[k + 1]]))
        vol /= 6.0
        if vol <= 0:
            bad_norm.append(name)
        if len(verts) % 6:
            bad_closed.append(f"{name} (verts {len(verts)} not a 6-point sweep)")
    check(not bad_closed, "every ornament is a closed sweep solid (no boundary, no loose edge)",
          str(bad_closed) if bad_closed else f"{tot_verts} verts total")
    check(not bad_norm, "outward normals (positive enclosed volume)", str(bad_norm) if bad_norm else "all 11")
    check(not bad_genus, "genus 0 topology (V-E+F=2) on every piece",
          str(bad_genus) if bad_genus else "all 11")
    check(tot_verts <= 1200, "surface density stays low", f"{tot_verts} ornament vertices in total")

    # ---- placement: seated, not floating ---------------------------------
    section("placement - details follow the host shape, nothing floats")
    worst_rear_max = worst_rear_min = 0.0
    global_min_lift = 10.0
    worst_all_min, worst_all_max = 10.0, -10.0
    worst_name = ""
    for name, host in ORNAMENTS.items():
        o = bpy.data.objects[name]
        verts = mesh_extent(o)
        tree, _ = bvh_of([host])
        dists = [s if s is not None else (9.0, 9.0)
                 for s in signed_distances(tree, verts)]
        n_st = len(verts) // 6
        rear = [d for i, (d, _u) in enumerate(dists) if i % 6 < 2]
        chamfer = [d for i, (d, _u) in enumerate(dists) if i % 6 in (2, 5)]
        tops = [(d, i // 6) for i, (d, _u) in enumerate(dists) if i % 6 in (3, 4)]
        alls = [d for d, _u in dists]
        mid_tops = [d for d, st in tops if n_st * 0.25 <= st <= n_st * 0.75]
        if rear and max(rear) > worst_rear_max:
            worst_rear_max, worst_name = max(rear), name
        if rear:
            worst_rear_min = min(worst_rear_min, min(rear))
        global_min_lift = min(global_min_lift, min(mid_tops))
        worst_all_min = min(worst_all_min, min(alls))
        worst_all_max = max(worst_all_max, max(alls))
        check(max(rear) <= REAR_MAX and min(rear) >= REAR_MIN,
              f"{name}: swept back seated in {host.replace('WSK_Armor_', '').replace('WSK_Helmet_', '')}",
              f"rear signed {min(rear) * 1000:+.2f}..{max(rear) * 1000:+.2f} mm")
        check(min(mid_tops) >= LIFT_MIN and max(alls) <= LIFT_MAX,
              f"{name}: crown relief readable and shallow",
              f"mid-path crown {min(mid_tops) * 1000:.2f}..{max(d for d, _ in tops) * 1000:.2f} mm above the plate")
        check(min(chamfer) >= CHAMFER_MIN,
              f"{name}: chamfer ring never sinks below the plate",
              f"chamfer {min(chamfer) * 1000:+.2f} mm")
    check(worst_rear_max <= REAR_MAX and worst_rear_min >= REAR_MIN,
          "no ornament floats and none plunges deep (all rear faces)",
          f"tightest rear {worst_rear_max * 1000:+.3f} mm, deepest bite {worst_rear_min * 1000:+.2f} mm at {worst_name}")
    check(worst_all_min >= ALL_MIN and worst_all_max <= ALL_MAX,
          "every ornament vertex lies in the shallow band above its host",
          f"signed {worst_all_min * 1000:+.2f}..{worst_all_max * 1000:+.2f} mm")

    # ---- foreign clearance ----------------------------------------------
    section("clearance to everything else")
    armour = all_armor_names()
    worst_gap = 10.0
    worst_pair = ""
    for name, host in ORNAMENTS.items():
        o = bpy.data.objects[name]
        verts = mesh_extent(o)
        skip = {name} | set(ORNAMENTS) | {host}
        tree, _ = bvh_of(armour, skip=skip)
        gaps = [s[1] for s in signed_distances(tree, verts) if s is not None]
        gap = min(gaps, default=9.0)
        if gap < worst_gap:
            worst_gap, worst_pair = gap, name
    check(worst_gap >= FOREIGN_CLEAR,
          "no ornament touches armour it does not decorate (medallion, crest, other plates)",
          f"tightest gap {worst_gap * 1000:.1f} mm at {worst_pair}")

    # ---- design budget ----------------------------------------------------
    section("design - sparse, narrow, aligned, mirrored")
    widths = {n: float(o["wsk_width_m"]) for n, o in
              ((n, bpy.data.objects[n]) for n in ORNAMENTS)}
    reliefs = {n: float(o["wsk_relief_m"]) for n, o in
               ((n, bpy.data.objects[n]) for n in ORNAMENTS)}
    check(all(WIDTH_BUDGET[0] <= w <= WIDTH_BUDGET[1] for w in widths.values()),
          "every trim is narrow (5.0-11.5 mm wide)",
          f"{min(widths.values()) * 1000:.1f}..{max(widths.values()) * 1000:.1f} mm")
    check(all(RELIEF_BUDGET[0] <= h <= RELIEF_BUDGET[1] for h in reliefs.values()),
          "every trim is shallow (1.5-2.7 mm of relief)",
          f"{min(reliefs.values()) * 1000:.1f}..{max(reliefs.values()) * 1000:.1f} mm")

    belt_l = mesh_extent(bpy.data.objects["WSK_Decor_BeltTrimTop_L_01"])
    belt_r = mesh_extent(bpy.data.objects["WSK_Decor_BeltTrimTop_R_01"])
    belt_min_x = min(v.x for v in belt_r)
    check(belt_min_x >= 0.018,
          "belt trim stops clear of the medallion (>= 18 mm from centre)",
          f"nearest belt-trim vertex at X {belt_min_x * 1000:.1f} mm")
    brow_l = mesh_extent(bpy.data.objects["WSK_Decor_BrowTrim_L_01"])
    brow_min_x = min(abs(v.x) for v in brow_l)
    check(brow_min_x >= 0.005,
          "brow trim stops clear of the centre crest (>= 5 mm from centre)",
          f"nearest brow-trim vertex at |X| {brow_min_x * 1000:.1f} mm")
    keel = mesh_extent(bpy.data.objects["WSK_Decor_ChestKeelTrim_01"])
    keel_len = max(v.z for v in keel) - min(v.z for v in keel)
    check(keel_len >= 0.40, "the chest line runs the keel (>= 400 mm)", f"{keel_len * 1000:.0f} mm")

    mirror_err = 0.0
    for left, right in PAIRS:
        lv = [(v.x, v.y, v.z) for v in mesh_extent(bpy.data.objects[left])]
        rv = [(-v.x, v.y, v.z) for v in mesh_extent(bpy.data.objects[right])]
        if len(lv) != len(rv):
            mirror_err = 9.0
            break

        def hausdorff(a, b):
            return max(min((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2
                           for q in b) ** 0.5 for p in a)

        mirror_err = max(mirror_err, hausdorff(lv, rv), hausdorff(rv, lv))
    check(mirror_err <= 0.0025,
          "left/right pairs mirror each other about X = 0 (two-sided Hausdorff)",
          f"worst vertex deviation {mirror_err * 1000:.2f} mm")

    motifs = sorted({o["wsk_motif"] for o in (bpy.data.objects[n] for n in ORNAMENTS)})
    check(set(motifs) <= {"line", "chevron", "edge trim", "lanceolate"},
          "motifs are pure geometry - no text, no emblem, no lettering",
          ", ".join(motifs))

    # ---- silhouette and gameplay read ------------------------------------
    if os.environ.get("WSK_SKIP_RENDERS") == "1":
        note("renders skipped (WSK_SKIP_RENDERS=1)")
    else:
        section("gameplay-distance read (rendered)")
        scene = bpy.context.scene
        render_setup(scene)
        cam = bpy.data.objects["WSK_Cam_Front_Ortho"]
        scene.camera = cam
        path_after = os.path.join(SHOTS, "verify_gameplay_after.png")
        scene.render.filepath = path_after
        bpy.ops.render.render(write_still=True)

        for n in ORNAMENTS:
            bpy.data.objects[n].hide_render = True
        path_before = os.path.join(SHOTS, "verify_gameplay_before.png")
        scene.render.filepath = path_before
        bpy.ops.render.render(write_still=True)
        for n in ORNAMENTS:
            bpy.data.objects[n].hide_render = False

        mask_after, mask_before = alpha_mask(path_after), alpha_mask(path_before)
        area_before, area_after = int(mask_before.sum()), int(mask_after.sum())
        growth = (area_after - area_before) / max(1, area_before)
        check(growth <= 0.0035,
              "the trim does not grow the silhouette",
              f"front mask {area_before} -> {area_after} px ({growth * 100:.3f} %)")
        gold_after, fig_after = gold_pixels(path_after)
        gold_before, fig_before = gold_pixels(path_before)
        new_gold = gold_after - gold_before
        check(new_gold >= 120,
              "the decoration reads at gameplay distance",
              f"{new_gold} gold pixels added at ortho scale 2.5")
        check(new_gold <= 0.04 * fig_after,
              "the decoration does not dominate the figure",
              f"{100.0 * new_gold / max(1, fig_after):.2f} % of the figure's pixels")

        cam = bpy.data.objects["WSK_Cam_ThreeQuarter"]
        scene.camera = cam
        scene.render.filepath = os.path.join(SHOTS, "verify_gameplay_threequarter.png")
        bpy.ops.render.render(write_still=True)
        note("renders: verify_gameplay_before/after.png (front), verify_gameplay_threequarter.png")

    # ---- report ------------------------------------------------------------
    lines.append(f"\n{passed} passed, {failed} failed, {warned} warnings")
    text = "\n".join(lines) + "\n"
    with open(REPORT, "w") as fh:
        fh.write(text)
    print(text)
    print("REPORT", REPORT)


if __name__ == "__main__":
    main()
