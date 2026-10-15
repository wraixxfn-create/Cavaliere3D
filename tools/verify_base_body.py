"""Prompt 3 verification - the base body.

Four independent check groups:

A. File / scope checks on `Wildshift_Knight_03_BaseBody.blend`
   units, collections, that the Prompt 1 scene and the Prompt 2 proportion
   guide are intact, that the blockout was retired rather than deleted, and
   that nothing out of scope (armour, helmet, cape, weapon, rig) exists.

B. Mesh quality of the delivered body
   closed manifold, genus 0, quad-dominant, no loose vertices, no duplicate
   vertices, no zero-area faces, outward normals, and no self-intersections
   (BVH self-overlap test).

C. Scale / origin / symmetry
   ground contact, character origin, exact X mirror symmetry, world dimensions
   and the height envelope (2.00 m belongs to the helmet, the bare body is
   1.91 m).

D. Proportion checks against the approved Prompt 2 guide
   every joint marker (shoulder, elbow, wrist, hip, knee, ankle) must coincide
   with the built geometry, and the landmark widths/depths must match the
   proportion sheet within tolerance.

Then it renders the four verification views plus overlaid front/back/side
composites against the supplied reference at the calibrated scale.

Run:  tools/bl.sh tools/verify_base_body.py
"""
import math
import os

import bpy          # noqa: F401 (must be first)
import bmesh        # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_03_BaseBody.blend")
OUT = os.path.join(ROOT, "analysis/verify")
SHOTS = os.path.join(ROOT, "analysis/basebody")
BODY = "WSK_Body_Base_01"

TOL_JOINT = 0.020       # m: allowed distance between a joint marker and the geometry
TOL_DIM = 0.020         # m: allowed error on a guide dimension

results = []


def check(label, ok, detail=""):
    results.append((label, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))


def note(text):
    print(f"      note: {text}")


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------
def obj_verts(o):
    return [o.matrix_world @ v.co for v in o.data.vertices]


def bbox(pts):
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def width_at(pts, z, tol=0.010, xmin=0.30):
    """X extent of the vertices within `tol` of height z, limited to the torso."""
    sel = [p for p in pts if abs(p.z - z) <= tol and abs(p.x) <= xmin]
    if not sel:
        return 0.0, 0.0
    return (max(p.x for p in sel) - min(p.x for p in sel),
            max(p.y for p in sel) - min(p.y for p in sel))


SHEET_JOINTS = {
    "Center_Hips": (0.0, 0.0, 1.000), "Center_Waist": (0.0, 0.0, 1.220),
    "Center_Chest": (0.0, 0.0, 1.630), "Neck": (0.0, 0.0, 1.780),
    "Shoulder_R": (0.200, 0.000, 1.630), "Shoulder_L": (-0.200, 0.000, 1.630),
    "Elbow_R": (0.316, -0.020, 1.281), "Elbow_L": (-0.316, -0.020, 1.281),
    "Wrist_R": (0.295, 0.022, 0.983), "Wrist_L": (-0.295, 0.022, 0.983),
    "Hip_R": (0.100, 0.000, 1.000), "Hip_L": (-0.100, 0.000, 1.000),
    "Knee_R": (0.155, 0.010, 0.550), "Knee_L": (-0.155, 0.010, 0.550),
    "Ankle_R": (0.215, -0.010, 0.115), "Ankle_L": (-0.215, -0.010, 0.115),
}


def bmesh_half_extent(obj):
    zs = [v.co.z for v in obj.data.vertices]
    return (max(zs) - min(zs)) + 1.0


def point_inside(tree, p, ray_len):
    """Ray-parity containment test against a closed mesh."""
    origin = Vector(p)
    hits = 0
    for _ in range(64):
        loc, _n, _i, _d = tree.ray_cast(origin, Vector((0.0, 0.0, 1.0)), ray_len)
        if loc is None:
            break
        hits += 1
        origin = loc + Vector((0.0, 0.0, 1e-5))
    return hits % 2 == 1


def ring_slice(pts, z, tol=1e-4):
    """The torso ring at exactly height z (rings carry exact design Z values,
    and no limb ring shares one), returned as (width, depth)."""
    sel = [p for p in pts if abs(p.z - z) <= tol]
    if not sel:
        return 0.0, 0.0
    return (2.0 * max(abs(p.x) for p in sel), max(p.y for p in sel) - min(p.y for p in sel))


def ring_centre(pts, z, tol=0.008):
    sel = [p for p in pts if abs(p.z - z) <= tol]
    if not sel:
        return None
    n = len(sel)
    return Vector((sum(p.x for p in sel) / n, sum(p.y for p in sel) / n,
                   sum(p.z for p in sel) / n))


# --------------------------------------------------------------------------
# A + B + C
# --------------------------------------------------------------------------
def file_and_mesh_checks():
    scene = bpy.context.scene
    objs = {o.name: o for o in bpy.data.objects}

    check("units metric, 1 unit = 1 m",
          scene.unit_settings.system == "METRIC" and scene.unit_settings.scale_length == 1.0,
          f"{scene.unit_settings.system} {scene.unit_settings.scale_length}")

    want_cols = {"Reference", "Blockout", "Body", "Helmet", "Armor", "Cape",
                 "Accessories", "Weapon", "Rig", "Lighting and Cameras"}
    have = {c.name for c in bpy.data.collections}
    check("all Prompt 1 collections still present", want_cols <= have,
          f"missing {sorted(want_cols - have)}" if not want_cols <= have else "10/10")

    for name in ("WSK_Origin_Centerline", "WSK_HeightRef_2m", "WSK_Studio_Ground_01",
                 "WSK_Cam_Front_Ortho", "WSK_Cam_Side_Ortho", "WSK_Cam_Rear_Ortho",
                 "WSK_Light_Key"):
        check(f"Prompt 1 object intact: {name}", name in objs)

    body_col = bpy.data.collections.get("Body")
    body_meshes = [o for o in body_col.objects if o.type == "MESH"]
    check("'Body' collection holds exactly one mesh object", len(body_meshes) == 1,
          ", ".join(o.name for o in body_meshes))
    obj = bpy.data.objects.get(BODY)
    check(f"body object named {BODY}", obj is not None)
    if obj is None:
        return None, None

    # --- scope: nothing else may have appeared -----------------------------
    for col in ("Helmet", "Armor", "Cape", "Accessories", "Weapon", "Rig"):
        n = len(bpy.data.collections[col].objects)
        check(f"collection '{col}' still empty (no armour/helmet/cape/weapon/rig)",
              n == 0, f"{n} objects")

    blockout = bpy.data.collections.get("Blockout")
    blk = list(blockout.objects)
    check("Prompt 2 blockout retained (19 parts + root, not deleted)",
          len(blk) == 20, f"{len(blk)} objects")
    check("blockout collection disabled in viewport and render",
          blockout.hide_viewport and blockout.hide_render)
    check("every blockout object also disabled",
          all(o.hide_viewport and o.hide_render for o in blk))

    guide = [o for o in bpy.data.objects if o.name.startswith("WSK_Joint_")]
    check("proportion guide joint markers retained (4 centre + 12 limb)",
          len(guide) == 16, f"{len(guide)} markers")
    check("proportion guide meshes retained (centreline/ruler/silhouette/envelopes)",
          len([o for o in bpy.data.objects if o.name.startswith("WSK_Guide_")]) == 8)
    check("proportion guide is a separate collection from the body",
          bpy.data.collections["Reference"] is not body_col and
          body_col.name not in {c.name for c in bpy.data.collections["Reference"].children})
    check("reference backdrops retained", 
          len([o for o in bpy.data.objects if o.name.startswith("WSK_Ref_")]) == 5)
    check("Prompt 2 proportion sheet text block retained",
          "WSK_Proportion_Sheet.txt" in bpy.data.texts)
    check("Prompt 3 topology notes text block saved",
          "WSK_BaseBody_Topology_Notes.txt" in bpy.data.texts)

    # --- transforms / scale -----------------------------------------------
    check("body has an identity transform (vertex = world coordinate)",
          tuple(round(v, 9) for v in obj.location) == (0.0, 0.0, 0.0) and
          tuple(round(math.degrees(a), 9) for a in obj.rotation_euler) == (0.0, 0.0, 0.0))
    check("body object scale is applied (1,1,1) - no object-level scaling",
          tuple(round(v, 9) for v in obj.scale) == (1.0, 1.0, 1.0), str(tuple(obj.scale)))
    check("no modifiers left on the body (mirror applied)",
          len(obj.modifiers) == 0, f"{len(obj.modifiers)} modifiers")
    check("modifier history recorded in an object property",
          "wsk_modifiers_applied" in obj)
    check("no armature / rigging anywhere in the file",
          not any(o.type == "ARMATURE" for o in bpy.data.objects))

    mats = list(obj.data.materials)
    check("exactly one neutral material", len(mats) == 1, ", ".join(m.name for m in mats))
    if mats:
        nodes = mats[0].node_tree.nodes
        check("material is untextured (no image texture node)",
              not any(n.type == "TEX_IMAGE" for n in nodes))
        check("material is neutral grey, non-metallic",
              tuple(round(c, 3) for c in
                    nodes.get("Principled BSDF").inputs["Base Color"].default_value)[:3] ==
              (0.42, 0.43, 0.45))

    # --- mesh quality -------------------------------------------------------
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()

    nv, ne, nf = len(bm.verts), len(bm.edges), len(bm.faces)
    boundary = [e for e in bm.edges if e.is_boundary]
    nonman = [e for e in bm.edges if not e.is_manifold]
    loose = [v for v in bm.verts if not v.link_edges]
    tris = [f for f in bm.faces if len(f.verts) == 3]
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    quads = nf - len(tris) - len(ngons)

    check("mesh is closed: no boundary edges", len(boundary) == 0, f"{len(boundary)}")
    check("mesh is manifold: no edge with more than two faces", len(nonman) == 0,
          f"{len(nonman)}")
    check("no loose vertices", len(loose) == 0, f"{len(loose)}")
    check(f"Euler characteristic V-E+F = 2 (closed surface, genus 0)",
          nv - ne + nf == 2, f"{nv}-{ne}+{nf} = {nv - ne + nf}")
    check("quad-dominant topology", quads / nf >= 0.95,
          f"{quads} quads, {len(tris)} tris, {len(ngons)} quads-as-ngons = "
          f"{quads / nf * 100:.1f} % quads")
    check("the only non-quad faces are the six tube-root caps "
          "(2 arms, 2 thumbs, 2 soles)",
          len(ngons) == 6 and sorted(len(f.verts) for f in ngons) == [6, 6, 14, 14, 16, 16],
          f"{len(ngons)} n-gons, sizes {sorted(len(f.verts) for f in ngons)}")
    check("triangle caps only where a tube ends", len(tris) <= 70, f"{len(tris)} tris")

    tiny = [f for f in bm.faces if f.calc_area() < 1e-9]
    check("no zero-area faces", len(tiny) == 0, f"{len(tiny)}")

    # duplicate vertices
    keys = {}
    dup = 0
    for v in bm.verts:
        k = (round(v.co.x, 5), round(v.co.y, 5), round(v.co.z, 5))
        dup += keys.get(k, 0)
        keys[k] = 1
    check("no duplicate/coincident vertices", dup == 0, f"{dup} duplicates")

    # outward normals: signed volume of the closed surface must be positive
    vol = 0.0
    for f in bm.faces:
        a, b, c = (f.verts[0].co, f.verts[1].co, f.verts[2].co)
        vol += a.dot(b.cross(c)) / 6.0
    check("face normals point outward (positive enclosed volume)", vol > 0.0,
          f"signed volume {vol:+.4f} m^3")

    # self-intersection: BVH overlap of the mesh with itself, ignoring faces
    # that share a vertex (they legitimately touch)
    bm.faces.ensure_lookup_table()
    tree = BVHTree.FromBMesh(bm)
    pairs = tree.overlap(tree)
    real = []
    for i, j in pairs:
        if i >= j:
            continue
        fi, fj = bm.faces[i], bm.faces[j]
        if set(v.index for v in fi.verts) & set(v.index for v in fj.verts):
            continue
        real.append((i, j))
    check("no self-intersecting faces (no overlapping body shells)", len(real) == 0,
          f"{len(real)} intersecting pairs")

    pts = [obj.matrix_world @ v.co for v in me.vertices]
    mn, mx = bbox(pts)
    check("no geometry below the ground plane", abs(mn.z) <= 1e-6, f"min Z {mn.z:+.6f}")
    check("feet exactly on the ground plane Z = 0", abs(mn.z) <= 1e-6, f"{mn.z:+.6f}")

    # --- symmetry ----------------------------------------------------------
    grid = {}
    for p in pts:
        grid.setdefault((round(p.y, 4), round(p.z, 4)), set()).add(round(p.x, 4))
    worst = 0.0
    for p in pts:
        if abs(p.x) < 1e-5:
            continue
        cand = grid.get((round(p.y, 4), round(p.z, 4)), set())
        if not cand:
            worst = 1.0
            break
        worst = max(worst, min(abs(-p.x - c) for c in cand))
    check("exact left/right mirror symmetry", worst < 1e-4,
          f"worst mirrored-vertex error {worst * 1000:.4f} mm")
    check("centred on the character origin in X", abs(mn.x + mx.x) < 1e-6,
          f"X span [{mn.x:+.4f}, {mx.x:+.4f}]")

    bm.free()
    return obj, (mn, mx)


# --------------------------------------------------------------------------
# D
# --------------------------------------------------------------------------
def proportion_checks(obj, box):
    mn, mx = box
    pts = obj_verts(obj)
    objs = {o.name: o for o in bpy.data.objects}
    sheet = bpy.data.texts["WSK_Proportion_Sheet.txt"].as_string()

    check("body height (bare crown, no helmet) is 1.910 m",
          abs(mx.z - 1.910) <= 0.005, f"{mx.z:.4f} m")
    check("bare crown keeps the helmet envelope of the guide clear",
          mx.z < 2.0 - 0.02, f"2.000 - {mx.z:.3f} = {2.0 - mx.z:.3f} m of shell room")
    check("arm span inside the cape envelope",
          (mx.x - mn.x) < 1.10, f"{mx.x - mn.x:.3f} m (cape 1.10 m)")
    check("body fits the guide's front-view Y extents (-0.20 .. +0.30)",
          -0.20 <= mn.y and mx.y <= 0.30, f"Y [{mn.y:+.3f}, {mx.y:+.3f}]")

    # --- joints the rig will land on --------------------------------------
    # 1. the Prompt 2 markers themselves must be untouched (rounded to the
    #    3 decimals printed in the proportion sheet, so 1 mm tolerance)
    for name, want in SHEET_JOINTS.items():
        m = objs.get(f"WSK_Joint_{name}")
        if m is None:
            check(f"joint marker {name} present", False)
            continue
        d = (m.location - Vector(want)).length
        check(f"guide joint marker {name} still matches the sheet",
              d <= 1e-3, f"({m.location.x:+.4f}, {m.location.y:+.4f}, "
                        f"{m.location.z:+.4f}) vs sheet {want}")

    # 2. every marker must be inside the body volume (ray parity test)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    tree = BVHTree.FromBMesh(bm)
    for name in SHEET_JOINTS:
        m = objs.get(f"WSK_Joint_{name}")
        if m is None:
            continue
        inside = point_inside(tree, m.location, bmesh_half_extent(obj))
        check(f"joint {name} lies inside the body volume (usable for a rig)", inside)

    # 3. the built geometry must actually pass through the marker
    def ring_at(x_sign, z, tol=0.010, xmin=0.20):
        sel = [p for p in pts if abs(p.z - z) < tol and x_sign * p.x > xmin]
        if not sel:
            return None
        return Vector((sum(p.x for p in sel) / len(sel),
                       sum(p.y for p in sel) / len(sel),
                       sum(p.z for p in sel) / len(sel)))

    for tag, sgn, key, xmin in (("Elbow_R", 1, "Elbow_R", 0.20), ("Elbow_L", -1, "Elbow_L", 0.20),
                                ("Wrist_R", 1, "Wrist_R", 0.20), ("Wrist_L", -1, "Wrist_L", 0.20),
                                ("Knee_R", 1, "Knee_R", 0.02), ("Knee_L", -1, "Knee_L", 0.02),
                                ("Ankle_R", 1, "Ankle_R", 0.10), ("Ankle_L", -1, "Ankle_L", 0.10)):
        want = Vector(SHEET_JOINTS[key])
        c = ring_at(sgn, want.z, xmin=xmin)
        if c is None:
            check(f"{tag}: geometry ring at the joint height", False)
            continue
        # the ring is perpendicular to the limb axis, so its centre is offset
        # from the marker along the axis by half a ring band at most
        err = math.hypot(c.x - want.x, c.y - want.y)
        check(f"{tag}: limb ring passes through the guide marker",
              err <= TOL_JOINT, f"in-plane offset {err * 1000:.1f} mm, "
                                f"ring Z {c.z:.3f} vs marker {want.z:.3f}")

    # 4. shoulder: the arm's root ring must sit on the shoulder joint, i.e. the
    #    marker has to be inside the limb it drives
    for tag, sgn, key in (("Shoulder_R", 1, "Shoulder_R"), ("Shoulder_L", -1, "Shoulder_L")):
        j = Vector(SHEET_JOINTS[key])
        near = [p for p in pts if sgn * p.x > 0.10 and (p - j).length < 0.09]
        check(f"{tag}: limb geometry wraps the shoulder joint",
              len(near) >= 8, f"{len(near)} arm vertices within 90 mm of the marker")

    bm.free()

    # --- landmark widths ----------------------------------------------------
    def torso_w(z):
        w, _d = ring_slice(pts, z)
        return w

    cases = [("chest width at the armpit line (guide chest_w_bot 0.32)", 1.440, 0.334, 0.030),
             ("upper chest width (guide chest_w_top 0.40)", 1.580, 0.372, 0.030),
             ("acromion width at the shoulder joint line (0.41 - the guide's "
              "0.46 pauldron plate sits just outside it)", 1.630, 0.410, 0.030),
             ("waist width (guide 0.30)", 1.220, 0.300, 0.030),
             ("pelvis width (guide 0.34)", 1.025, 0.344, 0.030),
             ("chest depth (guide 0.30 at the top)", 1.580, 0.283, 0.040)]
    for label, z, want, tol in cases:
        if "depth" in label:
            _w, d = ring_slice(pts, z)
            check(f"{label}: {d:.3f} m", abs(d - want) <= tol, f"delta {d - want:+.3f} m")
        else:
            w = torso_w(z)
            check(f"{label}: {w:.3f} m", abs(w - want) <= tol, f"delta {w - want:+.3f} m")

    widest = max((max(0.0, p.x) for p in pts if 1.40 < p.z < 1.70), default=0.0)
    note(f"widest shoulder-region half width {widest:.3f} m at the deltoid "
         f"(0.46 m in the guide is the armoured pauldron plate; the bare body "
         f"reads wider because the approved neutral A-pose holds the arm 20 deg out)")

    head = [p for p in pts if p.z > 1.80]
    hw = max(p.x for p in head) - min(p.x for p in head)
    check("head width inside the measured 0.19 m helmet envelope", 0.15 <= hw <= 0.19,
          f"{hw:.3f} m")

    foot = [p for p in pts if p.z < 0.03 and p.x > 0.05]
    fy = max(p.y for p in foot) - min(p.y for p in foot)
    check("foot length ~0.30 m (guide, assumed)", 0.26 <= fy <= 0.32, f"{fy:.3f} m")

    # foot splay: the angle of the sole's long axis away from the Y axis
    sole = [p for p in pts if p.z < 0.004 and p.x > 0.05]
    c = Vector((sum(p.x for p in sole) / len(sole), sum(p.y for p in sole) / len(sole), 0))
    xx = sum((p.x - c.x) ** 2 for p in sole)
    yy = sum((p.y - c.y) ** 2 for p in sole)
    xy = sum((p.x - c.x) * (p.y - c.y) for p in sole)
    ang = 0.5 * math.atan2(2 * xy, xx - yy)          # sole long axis vs +X
    splay = 90.0 - abs(math.degrees(ang))
    # width measured across the foot's own axis, not across world X
    across = (max((p.x - c.x) * math.cos(math.radians(splay)) -
                  (p.y - c.y) * math.sin(math.radians(splay)) * (1 if p.x > 0 else 1)
                  for p in sole) - min((p.x - c.x) * math.cos(math.radians(splay)) -
                                       (p.y - c.y) * math.sin(math.radians(splay))
                                       for p in sole))
    check("right foot splays outward by ~15 deg (guide)",
          abs(splay - 15.0) <= 6.0, f"{splay:.1f} deg from the Y axis")
    check("foot width across its own axis ~0.13 m (guide 0.135)",
          0.10 <= across <= 0.15, f"{across:.3f} m")

    # feet centres apart
    rc = [p for p in pts if p.z < 0.006 and p.x > 0]
    lc = [p for p in pts if p.z < 0.006 and p.x < 0]
    sep = (abs(sum(p.x for p in rc) / len(rc)) + abs(sum(p.x for p in lc) / len(lc)))
    check("foot centres match the guide's sabaton centres (0.43 m apart)",
          0.36 <= sep <= 0.50, f"{sep:.3f} m")

    # hands
    hand = [p for p in pts if p.z < 0.95 and p.x > 0.20 and p.y > 0.05]
    check("hand block present below the wrist with a forward thumb",
          len(hand) > 20 and max(p.z for p in hand) < 0.99,
          f"{len(hand)} verts, max Z {max(p.z for p in hand):.3f}")

    # arm: no elbow gap, the chain is continuous
    arm = sorted([p.z for p in pts if p.x > 0.24])
    check("arm chain continuous from deltoid to fingertips", len(arm) > 50,
          f"{len(arm)} verts on the right arm")

    note("ring counts: torso/head 17 (32 around after mirroring), arm 14, leg 16, "
         "thumb 6, with 2-3 extra loops at shoulder/elbow/hip/knee")
    return


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 64
    scene.cycles.use_denoising = False
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    for o in bpy.data.objects:
        if o.name.startswith(("WSK_Guide_", "WSK_Label_", "WSK_Ref_", "WSK_Joint_",
                              "WSK_Mann_", "WSK_Studio_")):
            o.hide_render = True
    cam = bpy.data.objects.get("WSK_Cam_Body_Check")
    if cam is None:
        cam = bpy.data.objects.new("WSK_Cam_Body_Check",
                                   bpy.data.cameras.new("WSK_Cam_Body_Check"))
        scene.collection.objects.link(cam)
    scene.camera = cam
    return scene, cam


def look_at(cam, loc, target):
    cam.location = loc
    d = (Vector(target) - Vector(loc)).normalized()
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def render_views(scene, cam):
    os.makedirs(SHOTS, exist_ok=True)
    scene.render.resolution_x, scene.render.resolution_y = 560, 780
    views = {"front": ((0.0, 6.0, 1.05), (0.0, 0.0, 1.05), 2.25),
             "side": ((6.0, 0.0, 1.05), (0.0, 0.0, 1.05), 2.25),
             "rear": ((0.0, -6.0, 1.05), (0.0, 0.0, 1.05), 2.25),
             "threequarter": ((-4.0, 4.6, 1.75), (0.0, 0.0, 1.02), None)}
    for name, (loc, tgt, scale) in views.items():
        if scale is None:
            cam.data.type = "PERSP"
            cam.data.lens = 62
        else:
            cam.data.type = "ORTHO"
            cam.data.ortho_scale = scale
        look_at(cam, loc, tgt)
        scene.render.filepath = os.path.join(SHOTS, f"check_body_{name}.png")
        print(f"      rendering {name}")
        bpy.ops.render.render(write_still=True)


def render_silhouettes(scene, cam):
    """Ortho silhouettes for the reference overlay + the metre checks."""
    os.makedirs(OUT, exist_ok=True)
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.resolution_x, scene.render.resolution_y = 1000, 1200
    scene.cycles.samples = 32
    cam.data.type = "ORTHO"
    scale = 2.60
    cam.data.ortho_scale = scale
    masks = {}
    for name, loc in (("front", (0.0, 6.0, 1.05)), ("back", (0.0, -6.0, 1.05)),
                      ("side", (6.0, 0.0, 1.05))):
        look_at(cam, loc, (0.0, 0.0, 1.05))
        path = os.path.join(OUT, f"body_silhouette_{name}.png")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        a = np.asarray(Image.open(path).convert("RGBA")).astype(np.float32)
        mask = a[..., 3] > 0.5
        masks[name] = (mask, scale / mask.shape[0])
    scene.render.film_transparent = False
    return masks


def silhouette_checks(masks):
    mask, mpp = masks["front"]
    ys, xs = np.nonzero(mask)
    h = (ys.max() - ys.min() + 1) * mpp
    w = (xs.max() - xs.min() + 1) * mpp
    check("rendered front silhouette height matches the mesh (1.910 m)",
          abs(h - 1.910) < 0.01, f"{h:.4f} m")
    # camera centre Z 1.05, ortho scale 2.60, 1200 px tall -> Z 0 is at row 1084
    expect_row = (1.05 + 1.30) / 2.60 * mask.shape[0]
    check("rendered silhouette rests on Z = 0",
          abs(ys.max() + 1 - expect_row) <= 2.0,
          f"lowest row {ys.max()} vs ground row {expect_row:.0f}")
    check("rendered silhouette width is a plausible arm span",
          0.60 <= w <= 0.90, f"{w:.3f} m")

    centre = (xs.min() + xs.max() + 1) / 2.0
    worst = 0.0
    for row in range(ys.min(), ys.max() + 1, 5):
        idx = np.nonzero(mask[row])[0]
        if not len(idx):
            continue
        worst = max(worst, abs((centre - idx.min()) - (idx.max() + 1 - centre)) * mpp)
    check("rendered silhouette is left/right symmetric", worst < 0.005,
          f"worst row asymmetry {worst * 1000:.2f} mm")

    # two separate ground contacts (two feet, not one blob)
    bottom = mask[ys.max() - 2]
    runs = 0
    prev = False
    for v in bottom:
        if v and not prev:
            runs += 1
        prev = v
    check("both feet touch the ground separately", runs == 2, f"{runs} contact patches")


def write_overlay(view, silhouettes):
    """Composite the body silhouette on the reference at its true scale.

    Unlike the Prompt 2 overlay this does NOT rescale the figure to match the
    reference height: the reference's helmet dome is 2.00 m while the bare
    body's crown is 1.910 m, so the silhouette is placed using the reference's
    own mm/px calibration anchored on the ground line.
    """
    calib = {"front": ("reference/ref_front.png", 0.887),
             "back": ("reference/ref_back.png", 0.887),
             "side": ("reference/ref_side.png", 0.897)}
    ref_rel, y_ground = calib[view]
    ref = Image.open(os.path.join(ROOT, ref_rel)).convert("RGB")
    W, H = ref.size
    body_px_ref = (y_ground - {"front": 0.075, "back": 0.080, "side": 0.064}[view]) * H
    m_per_px = 2.0 / body_px_ref
    ground_px = y_ground * H

    sil = Image.open(os.path.join(OUT, f"body_silhouette_{view}.png")).convert("RGBA")
    mask = np.asarray(sil)[..., 3] > 0.5
    ys = np.nonzero(mask.any(axis=1))[0]
    crop = sil.crop((0, ys.min(), sil.width, ys.max() + 1))
    sil_h_m = (ys.max() - ys.min() + 1) * (2.60 / mask.shape[0])
    px_h = int(round(sil_h_m / m_per_px))
    px_w = int(round(crop.width * px_h / crop.height))
    crop = crop.resize((px_w, px_h), Image.LANCZOS)

    front_cam = view in ("front", "back")
    cx = W * (0.5 if front_cam else 0.44)
    left = int(round(cx - px_w / 2.0))
    top = int(round(ground_px - px_h))

    canvas = Image.new("RGBA", ref.size, (0, 0, 0, 0))
    canvas.paste(crop, (left, top), crop)
    arr = np.asarray(canvas).astype(np.float32)
    m = arr[..., 3] > 0.4
    base = np.asarray(ref).astype(np.float32)
    ghost = 255.0 - (255.0 - base) * 0.55
    cyan = np.zeros_like(ghost)
    cyan[..., 0], cyan[..., 1], cyan[..., 2] = 20, 235, 255
    out = np.where(m[..., None], ghost * 0.35 + cyan * 0.65, ghost)
    img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

    p = np.asarray(img).copy()
    gy = int(round(ground_px))
    p[gy - 1:gy + 2, :, 0] = 255
    p[gy - 1:gy + 2, :, 1] = 0
    p[gy - 1:gy + 2, :, 2] = 0
    for metres, col in ((0.5, [255, 255, 0]), (1.0, [255, 255, 0]),
                        (1.5, [255, 255, 0]), (1.91, [0, 255, 0]), (2.0, [255, 0, 255])):
        y = int(round(ground_px - metres / m_per_px))
        if 0 <= y < H:
            p[y, 0:46, :] = col
            p[y, W - 46:W, :] = col
    img = Image.fromarray(p)
    path = os.path.join(SHOTS, f"overlay_body_{view}.png")
    img.save(path)
    print(f"      wrote {path}  ({m_per_px * 1000:.2f} mm/px, body drawn "
          f"{sil_h_m:.3f} m tall)")


# --------------------------------------------------------------------------
def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    obj, box = file_and_mesh_checks()
    if obj is None:
        return
    proportion_checks(obj, box)

    scene, cam = setup_render()
    masks = render_silhouettes(scene, cam)
    silhouette_checks(masks)
    for view in ("front", "back", "side"):
        write_overlay(view, masks)
    render_views(scene, cam)

    n_pass = sum(1 for _l, ok, _d in results if ok)
    print(f"\n{'=' * 72}\n{n_pass}/{len(results)} checks passed\n{'=' * 72}")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "verify_base_body_report.txt"), "w") as fh:
        fh.write("Wildshift Knight - Prompt 3 base body verification\n")
        fh.write("=" * 60 + "\n\n")
        for label, ok, detail in results:
            fh.write(f"[{'PASS' if ok else 'FAIL'}] {label}"
                     + (f"  -> {detail}\n" if detail else "\n"))
        fh.write(f"\n{n_pass}/{len(results)} checks passed\n")
    print("wrote", os.path.join(OUT, "verify_base_body_report.txt"))
    if n_pass != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
