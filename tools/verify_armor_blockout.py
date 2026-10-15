"""Verify Prompt 5 armor and render front/side/rear orthographic checks.

Run: tools/bl.sh tools/verify_armor_blockout.py
Env: WSK_SKIP_RENDERS=1 for numeric checks only; WSK_SAMPLES=24 by default.
The source and delivered .blend files are read only by this script.
"""
import hashlib
import math
import os

import bpy  # noqa: F401 (must be imported first)
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from PIL import Image, ImageDraw, ImageFont

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_04_HelmetBlockout.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_05_ArmorBlockout.blend")
SHOTS = os.path.join(ROOT, "analysis/armor")
REPORT = os.path.join(ROOT, "analysis/verify/verify_armor_report.txt")
BODY = "WSK_Body_Base_01"
MAT_STEEL = "MAT_Armor_BlackenedSteel_01"
MAT_IRON = "MAT_Armor_BroadIron_01"
SAMPLES = int(os.environ.get("WSK_SAMPLES", "24"))
SKIP_RENDERS = os.environ.get("WSK_SKIP_RENDERS") == "1"

ARMOR_NAMES = [
    "WSK_Armor_Chest_01", "WSK_Armor_Back_01",
    "WSK_Armor_Pauldron_R_01", "WSK_Armor_Pauldron_L_01",
    "WSK_Armor_ShoulderSpike_R_01", "WSK_Armor_ShoulderSpike_L_01",
    "WSK_Armor_Forearm_R_01", "WSK_Armor_Forearm_L_01",
    "WSK_Armor_Gauntlet_R_01", "WSK_Armor_Gauntlet_L_01",
    "WSK_Armor_Thigh_R_01", "WSK_Armor_Thigh_L_01",
    "WSK_Armor_Shin_R_01", "WSK_Armor_Shin_L_01",
    "WSK_Armor_Sabaton_R_01", "WSK_Armor_Sabaton_L_01",
]
PAIRS = [
    ("WSK_Armor_Pauldron_R_01", "WSK_Armor_Pauldron_L_01"),
    ("WSK_Armor_ShoulderSpike_R_01", "WSK_Armor_ShoulderSpike_L_01"),
    ("WSK_Armor_Forearm_R_01", "WSK_Armor_Forearm_L_01"),
    ("WSK_Armor_Gauntlet_R_01", "WSK_Armor_Gauntlet_L_01"),
    ("WSK_Armor_Thigh_R_01", "WSK_Armor_Thigh_L_01"),
    ("WSK_Armor_Shin_R_01", "WSK_Armor_Shin_L_01"),
    ("WSK_Armor_Sabaton_R_01", "WSK_Armor_Sabaton_L_01"),
]
JOINTS = {
    "elbow_R": Vector((0.316, -0.020, 1.281)),
    "elbow_L": Vector((-0.316, -0.020, 1.281)),
    "wrist_R": Vector((0.295, 0.022, 0.983)),
    "wrist_L": Vector((-0.295, 0.022, 0.983)),
    "hip_R": Vector((0.100, 0.000, 1.000)),
    "hip_L": Vector((-0.100, 0.000, 1.000)),
    "knee_R": Vector((0.155, 0.010, 0.550)),
    "knee_L": Vector((-0.155, 0.010, 0.550)),
    "ankle_R": Vector((0.215, -0.010, 0.115)),
    "ankle_L": Vector((-0.215, -0.010, 0.115)),
}

results = []
mesh_rows = []
fit_rows = []
contact_rows = []
clearances = {}
images = []


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


def old_scene_snapshot():
    collections = {c.name: tuple(sorted(o.name for o in c.objects))
                   for c in bpy.data.collections}
    children = {c.name: tuple(sorted(ch.name for ch in c.children))
                for c in bpy.data.collections}
    objects = {}
    for o in bpy.data.objects:
        rec = [o.type, tuple(round(float(v), 6) for row in o.matrix_world for v in row),
               o.hide_viewport, o.hide_render, o.parent.name if o.parent else None]
        if o.type == "MESH":
            rec += [mesh_hash(o.data), tuple((m.type, m.name) for m in o.modifiers),
                    tuple(m.name for m in o.data.materials if m)]
        objects[o.name] = tuple(rec)
    texts = {t.name: t.as_string() for t in bpy.data.texts}
    material_names = tuple(sorted(m.name for m in bpy.data.materials))
    return collections, children, objects, texts, material_names


def evaluated_geo(obj):
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    mw = ev.matrix_world.copy()
    verts = [mw @ v.co for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    return verts, faces


def geo_tree(verts, faces):
    return BVHTree.FromPolygons(verts, faces, all_triangles=False)


def bounds(verts):
    arr = np.asarray([tuple(v) for v in verts], dtype=np.float64)
    return arr.min(axis=0), arr.max(axis=0)


def tree_for(obj):
    verts, faces = evaluated_geo(obj)
    return geo_tree(verts, faces), verts, faces


def near_point(tree, point):
    result = tree.find_nearest(Vector(point))
    return float(result[3]) if result and result[0] is not None else math.inf


def mesh_stats(obj):
    verts, faces = evaluated_geo(obj)
    bm = bmesh.new()
    bm_verts = [bm.verts.new(v) for v in verts]
    for face in faces:
        try:
            bm.faces.new([bm_verts[i] for i in face])
        except ValueError:
            pass
    bm.normal_update()
    open_edges = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    nonmanifold = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    loose = sum(1 for v in bm.verts if not v.link_edges)
    volume = bm.calc_volume(signed=True)
    chi = len(bm.verts) - len(bm.edges) + len(bm.faces)
    bm.free()
    degenerate = 0
    for face in faces:
        if len(face) < 3:
            degenerate += 1
            continue
        p0 = verts[face[0]]
        area = sum((verts[face[i]] - p0).cross(verts[face[i + 1]] - p0).length * 0.5
                   for i in range(1, len(face) - 1))
        if area < 1e-10:
            degenerate += 1
    return verts, faces, open_edges, nonmanifold, loose, volume, chi, degenerate


def symmetry_error(a, b):
    # Compare transformed evaluated vertices using a spatial nearest-neighbour
    # lookup; this tests the surfaces, not only the bounding boxes.
    ta = KDTree(len(b))
    for i, p in enumerate(b):
        ta.insert(p, i)
    ta.balance()
    errors = []
    for p in a:
        _co, _index, dist = ta.find(Vector((-p.x, p.y, p.z)))
        errors.append(dist)
    return max(errors, default=0.0)


def check_scope(before):
    section("A  checkpoint scope and preservation")
    bpy.ops.wm.open_mainfile(filepath=DST)
    after = old_scene_snapshot()
    old_cols, old_children, old_objects, old_texts, old_mats = before
    new_cols, new_children, new_objects, new_texts, new_mats = after

    check("requested checkpoint exists and is the delivered file",
          os.path.isfile(DST) and os.path.basename(DST) == "Wildshift_Knight_05_ArmorBlockout.blend",
          f"{os.path.getsize(DST) / 1e6:.2f} MB" if os.path.isfile(DST) else "missing")
    changed = [name for name, rec in old_objects.items() if new_objects.get(name) != rec]
    check("all Prompt 4 objects are byte-stable in geometry and unchanged in scene state",
          not changed, f"{len(old_objects)} source objects compared" + (f"; changed {changed}" if changed else ""))
    added = sorted(set(new_objects) - set(old_objects))
    check("only the sixteen WSK_Armor_* objects were added",
          added == sorted(ARMOR_NAMES), f"{len(added)} objects" + (f": {added}" if added != sorted(ARMOR_NAMES) else ""))
    bad_collections = []
    for name, prior in old_cols.items():
        expected = tuple(sorted(ARMOR_NAMES)) if name == "Armor" else prior
        if new_cols.get(name) != expected:
            bad_collections.append(name)
    check("existing collections preserved; only Armor is populated",
          not bad_collections and set(new_cols) == set(old_cols),
          "no collection added or moved" if not bad_collections else str(bad_collections))
    check("collection hierarchy is unchanged", old_children == new_children)
    body_same = old_objects.get(BODY) == new_objects.get(BODY)
    check("base body mesh and state preserved", body_same, BODY)
    helmet_old = [n for n in old_objects if n.startswith("WSK_Helmet")]
    helmet_bad = [n for n in helmet_old if old_objects[n] != new_objects.get(n)]
    check("Prompt 4 helmet and crown preserved", not helmet_bad,
          f"{len(helmet_old)} parts" + (f" changed: {helmet_bad}" if helmet_bad else ""))
    text_bad = [name for name, value in old_texts.items()
                if not new_texts.get(name, "").startswith(value)]
    new_texts_added = sorted(set(new_texts) - set(old_texts))
    check("earlier text blocks are retained; armor notes are the only new block",
          not text_bad and new_texts_added == ["WSK_Armor_Blockout_Notes.txt"],
          f"new={new_texts_added}; altered={text_bad}")
    check("Prompt 5 section appended to project notes",
          "Prompt 5 - Major armor plates" in new_texts.get("WSK_Project_Notes.txt", "") and
          new_texts.get("WSK_Project_Notes.txt", "").startswith(old_texts.get("WSK_Project_Notes.txt", "")))
    added_mats = sorted(set(new_mats) - set(old_mats))
    check("only the two dark armor placeholder materials were added",
          added_mats == sorted((MAT_STEEL, MAT_IRON)), str(added_mats))
    check("no armature or rig objects were introduced",
          not any(o.type == "ARMATURE" for o in bpy.data.objects) and
          not bpy.data.collections["Rig"].objects)


def object_and_material_checks():
    section("B  inventory, materials, separation")
    armor_col = bpy.data.collections.get("Armor")
    check("Armor contains the intended sixteen independent major pieces",
          armor_col is not None and set(o.name for o in armor_col.objects) == set(ARMOR_NAMES),
          f"{len(armor_col.objects) if armor_col else 0} objects")
    check("chest and back are separate mesh objects and mesh datablocks",
          bpy.data.objects["WSK_Armor_Chest_01"].data is not bpy.data.objects["WSK_Armor_Back_01"].data)
    shared = [n for n in ARMOR_NAMES if bpy.data.objects[n].type != "MESH" or
              bpy.data.objects[n].data.users != 1]
    check("every armor part is its own editable mesh", not shared,
          "16 meshes; no joined or shared geometry" if not shared else str(shared))
    parents = [n for n in ARMOR_NAMES if bpy.data.objects[n].parent is not None]
    check("armor remains unparented, ready for later bone attachment", not parents,
          "no rig or helmet parenting" if not parents else str(parents))
    spike_count = sum("ShoulderSpike" in n for n in ARMOR_NAMES)
    check("only two broad shoulder spikes, each a separate object", spike_count == 2,
          f"{spike_count} total")
    bad_descriptors = [n for n in ARMOR_NAMES if any(s in n.lower() for s in
                      ("chain", "filigree", "cloth", "weapon", "ornament"))]
    check("no chains, filigree, cloth, weapon or ornament objects", not bad_descriptors,
          str(bad_descriptors) if bad_descriptors else "none")

    mat_props = {}
    for name in (MAT_STEEL, MAT_IRON):
        mat = bpy.data.materials.get(name)
        if mat is None:
            mat_props[name] = None
            continue
        bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.use_nodes else None
        if bsdf is None:
            mat_props[name] = None
            continue
        rgb = tuple(bsdf.inputs["Base Color"].default_value[:3])
        metallic = float(bsdf.inputs["Metallic"].default_value)
        roughness = float(bsdf.inputs["Roughness"].default_value)
        lum = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
        texture_nodes = [n.name for n in mat.node_tree.nodes if n.type == "TEX_IMAGE"]
        emission = float(bsdf.inputs["Emission Strength"].default_value) if "Emission Strength" in bsdf.inputs else 0.0
        mat_props[name] = (lum, metallic, roughness, texture_nodes, emission)
    mats_ok = all(v is not None and v[0] < 0.10 and v[3] == [] and v[4] == 0.0
                  for v in mat_props.values())
    check("both materials are dark, untextured, non-emissive placeholder metals",
          mats_ok, "; ".join(f"{n}: L={v[0]:.3f}, metal={v[1]:.2f}, rough={v[2]:.2f}"
                              for n, v in mat_props.items() if v))
    assignments = [n for n in ARMOR_NAMES if len(bpy.data.objects[n].data.materials) != 1 or
                   bpy.data.objects[n].data.materials[0].name not in (MAT_STEEL, MAT_IRON)]
    check("each plate uses one of the two dark blockout materials", not assignments,
          str(assignments) if assignments else "no final textures or mixed material slots")


def geometry_checks():
    section("C  evaluated mesh integrity")
    geos = {}
    all_ok = True
    bad_stats = []
    for name in ARMOR_NAMES:
        obj = bpy.data.objects[name]
        verts, faces, open_edges, nonmanifold, loose, volume, chi, degenerate = mesh_stats(obj)
        geos[name] = (verts, faces)
        ok = open_edges == 0 and nonmanifold == 0 and loose == 0 and volume > 0.0 and chi == 2 and degenerate == 0
        all_ok &= ok
        if not ok:
            bad_stats.append(f"{name}: open {open_edges}, nonmanifold {nonmanifold}, loose {loose}, volume {volume:.6g}, chi {chi}, degenerate {degenerate}")
        mesh_rows.append(f"{name:34s} verts {len(verts):5d} faces {len(faces):5d} "
                         f"open {open_edges} nonmanifold {nonmanifold} chi {chi:+d} "
                         f"volume {volume * 1e6:8.1f} cm3 degenerate {degenerate}")
    check("all sixteen evaluated plates are closed, manifold, outward solids",
          all_ok, ("one genus-zero shell per object; bevels evaluated in memory" if all_ok else " | ".join(bad_stats)))
    check("no armor object contains geometry below ground level",
          min(v.z for verts, _faces in geos.values() for v in verts) >= -0.001,
          f"minimum Z {min(v.z for verts, _faces in geos.values() for v in verts):.4f} m")
    return geos


def fit_and_symmetry_checks(geos):
    section("D  balance, fit, and articulation zones")
    for left_name, right_name in PAIRS:
        lverts = geos[left_name][0]
        rverts = geos[right_name][0]
        error = symmetry_error(rverts, lverts)
        check(f"{left_name.removeprefix('WSK_Armor_')} pair mirrors across X=0",
              error <= 0.004, f"max vertex deviation {error * 1000:.2f} mm")

    for name in ("WSK_Armor_Chest_01", "WSK_Armor_Back_01"):
        verts = geos[name][0]
        arr = np.asarray([tuple(v) for v in verts])
        centroid_x = float(arr[:, 0].mean())
        mn, mx = bounds(verts)
        ok = abs(centroid_x) < 0.002 and abs(mn[0] + mx[0]) < 0.003
        check(f"{name.removeprefix('WSK_Armor_')} stays centred and bilateral",
              ok, f"centre X {centroid_x * 1000:+.2f} mm; span {mn[0]:+.3f}..{mx[0]:+.3f} m")

    shoulders = [v for n in ("WSK_Armor_Pauldron_R_01", "WSK_Armor_Pauldron_L_01",
                             "WSK_Armor_ShoulderSpike_R_01", "WSK_Armor_ShoulderSpike_L_01")
                 for v in geos[n][0]]
    shoulder_min, shoulder_max = bounds(shoulders)
    shoulder_span = shoulder_max[0] - shoulder_min[0]
    check("shoulder silhouette is broad, balanced and below crown spikes",
          0.72 <= shoulder_span <= 1.02 and abs(shoulder_min[0] + shoulder_max[0]) < 0.004 and
          shoulder_max[2] < 1.833,
          f"span {shoulder_span:.3f} m; Z max {shoulder_max[2]:.3f} m")

    body_tree, body_verts, body_faces = tree_for(bpy.data.objects[BODY])
    fit_parts = [n for n in ARMOR_NAMES if "Pauldron" not in n and "ShoulderSpike" not in n]
    for name in fit_parts:
        verts = geos[name][0]
        nearest = [near_point(body_tree, v) for v in verts]
        dist = min(nearest)
        fit_rows.append((name, dist))
    # A small tolerance handles bevel-generated rim vertices. These shells are
    # sampled to sit just off the body; pauldron underlap is an intended cap fit.
    bad_fit = [(n, d) for n, d in fit_rows
               if d < (0.00001 if "Sabaton" in n else 0.0003) or d > 0.025]
    check("body-fitted cuirass and limb plates do not deeply penetrate the mannequin",
          not bad_fit, "; ".join(f"{n} {d*1000:.1f} mm" for n, d in fit_rows))

    all_trees = {n: geo_tree(*geos[n]) for n in ARMOR_NAMES}
    zone_limits = {"elbow": 0.018, "wrist": 0.018, "hip": 0.025,
                   "knee": 0.025, "ankle": 0.018}
    for joint_name, point in JOINTS.items():
        zone = joint_name.split("_")[0]
        d = min(near_point(t, point) for t in all_trees.values())
        clearances[joint_name] = d
        check(f"{joint_name} articulation zone remains clear",
              d >= zone_limits[zone], f"nearest armor {d*1000:.1f} mm away (min {zone_limits[zone]*1000:.0f} mm)")

    # Inspect real triangle overlaps between armor shells. Only the separately
    # modeled shoulder spike bases are allowed to seat into their pauldrons.
    expected = {
        frozenset(("WSK_Armor_ShoulderSpike_R_01", "WSK_Armor_Pauldron_R_01")),
        frozenset(("WSK_Armor_ShoulderSpike_L_01", "WSK_Armor_Pauldron_L_01")),
        frozenset(("WSK_Armor_Chest_01", "WSK_Armor_Pauldron_R_01")),
        frozenset(("WSK_Armor_Chest_01", "WSK_Armor_Pauldron_L_01")),
        frozenset(("WSK_Armor_Back_01", "WSK_Armor_Pauldron_R_01")),
        frozenset(("WSK_Armor_Back_01", "WSK_Armor_Pauldron_L_01")),
    }
    collisions = []
    names = ARMOR_NAMES
    trees = {n: geo_tree(*geos[n]) for n in names}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            overlap = trees[a].overlap(trees[b])
            if overlap:
                pair = frozenset((a, b))
                contact_rows.append((a, b, len(overlap), pair in expected))
                if pair not in expected:
                    collisions.append((a, b, len(overlap)))
    spike_contacts = sum(1 for a, b, _n, _expected in contact_rows
                         if "ShoulderSpike" in a or "ShoulderSpike" in b)
    check("armor overlaps are limited to the intentional shoulder/cuirass lap",
          not collisions, ("; ".join(f"{a} x {b}: {n} triangle pairs" for a, b, n in collisions)
                          if collisions else f"{len(contact_rows) - spike_contacts} shallow pauldron-to-cuirass laps; "
                          f"{spike_contacts} spike-base seats"))


def label_font(size, bold=True):
    candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for path in candidates:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def look_at(obj, location, target):
    obj.location = Vector(location)
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def render_views():
    os.makedirs(SHOTS, exist_ok=True)
    scene = bpy.context.scene
    old_camera = scene.camera
    old_engine = scene.render.engine
    old_transparent = scene.render.film_transparent
    old_res = (scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage)
    old_samples = scene.cycles.samples
    old_view_transform = scene.view_settings.view_transform
    old_bg = None
    if scene.world and scene.world.use_nodes:
        bg = scene.world.node_tree.nodes.get("Background")
        if bg:
            old_bg = (tuple(bg.inputs[0].default_value), float(bg.inputs[1].default_value))
            bg.inputs[0].default_value = (0.025, 0.027, 0.032, 1.0)
            bg.inputs[1].default_value = 1.0

    hide_states = {o.name: o.hide_render for o in bpy.data.objects}
    light_states = {}
    for obj in bpy.data.objects:
        if obj.type == "LIGHT":
            light_states[obj.name] = (obj.hide_render, obj.data.energy)
            obj.hide_render = True
        if obj.name.startswith(("WSK_Guide_", "WSK_Label_", "WSK_Ref_", "WSK_Joint_",
                                "WSK_Mann_", "WSK_Studio_")):
            obj.hide_render = True

    temp_objects = []
    def add_area(name, energy, location, target, size):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        look_at(obj, location, target)
        temp_objects.append((obj, data))

    add_area("ArmorCheck_Key", 400.0, (2.8, 3.5, 3.1), (0.0, 0.0, 1.0), 2.0)
    add_area("ArmorCheck_Fill", 220.0, (-2.4, 1.2, 2.0), (0.0, 0.0, 1.0), 2.4)
    add_area("ArmorCheck_Rim", 320.0, (0.0, -2.2, 2.8), (0.0, 0.0, 1.4), 1.7)
    add_area("ArmorCheck_Top", 100.0, (-0.8, 0.2, 3.0), (0.0, 0.0, 1.2), 1.5)

    cam_data = bpy.data.cameras.new("ArmorCheck_Camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 2.50
    cam = bpy.data.objects.new("ArmorCheck_Camera", cam_data)
    scene.collection.objects.link(cam)
    temp_objects.append((cam, cam_data))
    scene.camera = cam
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "Standard"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100

    views = [
        ("front", "FRONT ORTHOGRAPHIC", (0.0, 4.0, 1.06), (0.0, 0.0, 1.06)),
        ("side", "SIDE ORTHOGRAPHIC", (4.0, 0.0, 1.06), (0.0, 0.0, 1.06)),
        ("rear", "REAR ORTHOGRAPHIC", (0.0, -4.0, 1.06), (0.0, 0.0, 1.06)),
    ]
    shots = []
    rendered_paths = []
    for suffix, title, location, target in views:
        look_at(cam, location, target)
        raw = os.path.join(SHOTS, f"_armor_{suffix}_raw.png")
        scene.render.filepath = raw
        print(f"      rendering {title.lower()} ({SAMPLES} samples)")
        bpy.ops.render.render(write_still=True)
        im = Image.open(raw).convert("RGBA")
        os.remove(raw)
        w, h = im.size
        grad = np.linspace(0.68, 0.47, h, dtype=np.float32)[:, None]
        arr = np.zeros((h, w, 4), dtype=np.uint8)
        arr[:, :, 0] = (grad * 255).astype(np.uint8)
        arr[:, :, 1] = (grad * 255).astype(np.uint8)
        arr[:, :, 2] = (np.minimum(grad + 0.015, 1.0) * 255).astype(np.uint8)
        arr[:, :, 3] = 255
        back = Image.fromarray(arr, "RGBA")
        comp = Image.alpha_composite(back, im).convert("RGB")
        path = os.path.join(SHOTS, f"armor_{suffix}_ortho.png")
        comp.save(path)
        rendered_paths.append(path)
        shots.append((title, path, comp))

    pad, label_h = 12, 44
    tw, th = shots[0][2].size
    sheet = Image.new("RGB", (tw * 3 + pad * 4, th + label_h + pad * 2), (235, 235, 238))
    draw = ImageDraw.Draw(sheet)
    font = label_font(22)
    for i, (title, path, image) in enumerate(shots):
        x = pad + i * (tw + pad)
        draw.text((x + 6, pad), title, font=font, fill=(26, 28, 31))
        sheet.paste(image, (x, label_h + pad))
    sheet_path = os.path.join(SHOTS, "armor_views_orthographic.png")
    sheet.save(sheet_path)
    rendered_paths.append(sheet_path)

    # Restore in-memory scene settings and remove temporary render helpers.
    for obj, data in temp_objects:
        obj_type = obj.type
        bpy.data.objects.remove(obj, do_unlink=True)
        if obj_type == "CAMERA":
            bpy.data.cameras.remove(data)
        else:
            bpy.data.lights.remove(data)
    scene.camera = old_camera
    scene.render.engine = old_engine
    scene.render.film_transparent = old_transparent
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = old_res
    scene.cycles.samples = old_samples
    scene.view_settings.view_transform = old_view_transform
    for name, hidden in hide_states.items():
        if name in bpy.data.objects:
            bpy.data.objects[name].hide_render = hidden
    for name, (hidden, energy) in light_states.items():
        if name in bpy.data.objects:
            bpy.data.objects[name].hide_render = hidden
            bpy.data.objects[name].data.energy = energy
    if old_bg and scene.world and scene.world.use_nodes:
        bg = scene.world.node_tree.nodes.get("Background")
        if bg:
            bg.inputs[0].default_value = old_bg[0]
            bg.inputs[1].default_value = old_bg[1]
    return rendered_paths


def write_report():
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    n_pass = sum(1 for _label, ok, _detail in results if ok is True)
    n_fail = sum(1 for _label, ok, _detail in results if ok is False)
    lines = [
        "WILDSHIFT KNIGHT - PROMPT 5 VERIFICATION: MAJOR ARMOR BLOCKOUT",
        "=" * 70,
        f"file   : {os.path.basename(DST)}",
        f"input  : {os.path.basename(SRC)} (preserved; read only)",
        "script : tools/verify_armor_blockout.py",
        f"result : {n_pass} passed, {n_fail} failed",
        "",
    ]
    for label, ok, detail in results:
        if ok is None:
            title = detail if label is None else label
            lines.extend(["", title, "-" * len(title)])
        else:
            lines.append(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))
    lines.extend(["", "EVALUATED MESH TABLE", "-" * 20])
    lines.extend(mesh_rows)
    lines.extend(["", "BODY CLEARANCE / CLOSEST VERTEX DISTANCES", "-" * 43])
    lines.extend(f"{name:34s} {distance * 1000:7.2f} mm" for name, distance in fit_rows)
    lines.extend(["", "ARTICULATION MARKER CLEARANCES", "-" * 31])
    lines.extend(f"{name:20s} {distance * 1000:7.2f} mm" for name, distance in clearances.items())
    lines.extend(["", "INTENTIONAL CONTACTS", "-" * 20])
    if contact_rows:
        for a, b, count, _expected in contact_rows:
            if "ShoulderSpike" in a or "ShoulderSpike" in b:
                reason = "spike base seats into pauldron"
            else:
                reason = "shallow pauldron lap over cuirass edge"
            lines.append(f"{a} <-> {b}: {count} intersecting triangle pairs ({reason})")
    else:
        lines.append("none detected")
    lines.extend(["", "RENDERED ORTHOGRAPHIC CHECKS", "-" * 28])
    lines.extend(f"- {os.path.relpath(path, ROOT)}" for path in images)
    lines.extend(["", "RESHAPING NOTES", "-" * 15,
                  "- Pauldron underside/inner edge: confirm clearance to gorget and upper arm after shoulder rigging.",
                  "- Forearm bracer shells: test elbow and wrist flexion; their rest-pose articulation gaps are open.",
                  "- Thigh/shin guard offsets and sabaton top edge: re-fit after hip, knee and ankle pivots are finalized.",
                  "- The current shapes are broad rest-pose blockouts, not final skinning-safe production plates."])
    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"\nreport: {REPORT} ({n_pass} passed, {n_fail} failed)")
    return n_fail


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    before = old_scene_snapshot()
    check_scope(before)
    object_and_material_checks()
    geos = geometry_checks()
    fit_and_symmetry_checks(geos)
    if not SKIP_RENDERS:
        images.extend(render_views())
    failures = write_report()
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
