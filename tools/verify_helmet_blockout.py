"""Verify Prompt 4 (helmet base and head silhouette) and render the checks.

Run:   tools/bl.sh tools/verify_helmet_blockout.py
Env:   WSK_SAMPLES=64        render samples for the shaded views
       WSK_SKIP_RENDERS=1    numeric checks only (no images)

Opens checkpoint 03 first to snapshot everything Prompt 4 must leave alone,
then checkpoint 04, and checks
  A  scope: earlier checkpoints, body, reference, other collections untouched
  B  objects: names, hierarchy, separate editable meshes, dark materials, no rig
  C  evaluated-mesh integrity: closed, manifold, outward, no self-intersection
  D  symmetry and crown balance
  E  fit: helmet <-> head clearances, only intended contacts, nothing floating
  F  dimensions against the Prompt 2 guide envelope
  G  rig: static placement and a head-motion sweep against torso + neck guard
  H  silhouettes: renders, masks, section plots, comparison with the reference
All geometric checks use the EVALUATED meshes (modifiers applied in memory).
Writes analysis/verify/verify_helmet_report.txt and images in analysis/helmet/.
The .blend files are only read, never saved.
"""
import glob
import hashlib
import math
import os
import re
import subprocess

import bpy          # noqa: F401 (must be first)
import bmesh        # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402
from mathutils.kdtree import KDTree  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

ROOT = "/home/user/Cavaliere3D"
SRC = os.path.join(ROOT, "Wildshift_Knight_03_BaseBody.blend")
DST = os.path.join(ROOT, "Wildshift_Knight_04_HelmetBlockout.blend")
OUT = os.path.join(ROOT, "analysis/verify")
SHOTS = os.path.join(ROOT, "analysis/helmet")
REF = os.path.join(ROOT, "reference")
REPORT = os.path.join(OUT, "verify_helmet_report.txt")
BODY = "WSK_Body_Base_01"
SAMPLES = int(os.environ.get("WSK_SAMPLES", "64"))
SKIP_RENDERS = os.environ.get("WSK_SKIP_RENDERS") == "1"

ROOT_OBJ = "WSK_Helmet_Root_01"
SHELL = "WSK_Helmet_Shell_01"
FACE = "WSK_Helmet_Faceplate_01"
CREST = "WSK_Helmet_Crest_01"
GORGET = "WSK_Helmet_NeckGuard_01"
BAND = "WSK_Helmet_CrownBand_01"
HALO = "WSK_Helmet_CrownHalo_01"
SPINE = "WSK_Helmet_CrownSpine_01"
MOUNT = "WSK_Helmet_CrownMount_01"
SPIKE_IDS = ("C", "R1", "L1", "R2", "L2", "R3", "L3", "R4", "L4")
SPIKES = [f"WSK_Helmet_CrownSpike_{s}_01" for s in SPIKE_IDS]
HELMET_SET = {ROOT_OBJ, SHELL, FACE, CREST, GORGET}
CROWN_SET = {BAND, HALO, SPINE, MOUNT, *SPIKES}
CROWN_PARTS = [BAND, HALO, SPINE, MOUNT] + SPIKES
HEAD_MOVING = [SHELL, FACE, CREST] + CROWN_PARTS      # turns with the head
MESHES = [SHELL, FACE, CREST, GORGET] + CROWN_PARTS

STEEL, VOID, IRON = "MAT_Helmet_DarkSteel_01", "MAT_Helmet_FaceVoid_01", "MAT_Helmet_CrownIron_01"
MATERIAL = {SHELL: STEEL, CREST: STEEL, GORGET: STEEL, FACE: VOID,
            **{n: IRON for n in CROWN_PARTS}}
PARENT = {ROOT_OBJ: None, GORGET: None, SHELL: ROOT_OBJ, FACE: ROOT_OBJ, CREST: ROOT_OBJ,
          BAND: ROOT_OBJ, HALO: ROOT_OBJ, SPINE: HALO, MOUNT: HALO, **{s: HALO for s in SPIKES}}
# Euler characteristic of each closed evaluated surface: thickened disc = 2,
# thickened tube / ring = 0 (genus 1)
EXPECTED_CHI = {SHELL: 2, FACE: 2, CREST: 2, GORGET: 0, BAND: 0, HALO: 0, SPINE: 2,
                MOUNT: 2, **{s: 2 for s in SPIKES}}

# Prompt 2 guide envelope (WSK_Proportion_Sheet.txt / guide silhouette frames)
GUIDE = dict(helmet_half_w=0.095, dome_top=2.000, chin=1.740, ring_half_w=0.140,
             ring_bottom=1.790, ring_frame_top=1.930, spike_half_w=0.180,
             spike_top=2.110, spike_bottom=1.760, neck_joint=(0.0, 0.0, 1.780))
HEAD_PIVOT = Vector((0.0, 0.0, 1.780))      # guide WSK_Joint_Neck
NECK_PIVOT = Vector((0.0, 0.004, 1.690))    # base-body neck-base ring centre
TORSO_TOP = 1.690                           # body faces at/below this are "torso"

# contacts that are part of the design (parts sunk into / resting on each other)
INTENDED = {frozenset(p) for p in [(CREST, FACE), (CREST, SHELL), (CREST, BAND),
                                   (MOUNT, BAND), (MOUNT, SPINE), (SPINE, HALO)]}
INTENDED |= {frozenset((s, HALO)) for s in SPIKES}
INTENDED |= {frozenset((s, SPINE)) for s in ("WSK_Helmet_CrownSpike_C_01",)}
REQUIRED = [(CREST, FACE), (CREST, SHELL), (MOUNT, BAND), (MOUNT, SPINE), (SPINE, HALO)] + \
           [(s, HALO) for s in SPIKES]

results = []
notes = []
deviations = []


def check(label, ok, detail=""):
    results.append((label, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))


def note(text):
    notes.append(text)
    print(f"      note: {text}")


def section(title):
    results.append((None, None, title))
    print(f"\n== {title} ==")


def mm(v):
    return f"{v * 1000.0:.1f} mm"


# --------------------------------------------------------------------------
# snapshot of what Prompt 4 must not touch
# --------------------------------------------------------------------------
def mesh_hash(me):
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    return hashlib.sha1(np.round(co, 6).tobytes()).hexdigest()


def layer_states(lc, out=None):
    out = {} if out is None else out
    for ch in lc.children:
        out[ch.name] = (ch.exclude, ch.hide_viewport)
        layer_states(ch, out)
    return out


def snapshot():
    scene = bpy.context.scene
    snap = {"collections": {c.name: sorted(o.name for o in c.objects) for c in bpy.data.collections},
            "children": {c.name: sorted(ch.name for ch in c.children) for c in bpy.data.collections},
            "objects": {}, "texts": {t.name: t.as_string() for t in bpy.data.texts},
            "layers": layer_states(bpy.context.view_layer.layer_collection),
            "unit": (scene.unit_settings.system, round(scene.unit_settings.scale_length, 6)),
            "render": (scene.render.engine, scene.render.resolution_x, scene.render.resolution_y,
                       scene.camera.name if scene.camera else None),
            "materials": sorted(m.name for m in bpy.data.materials)}
    for o in bpy.data.objects:
        if o.name.startswith("WSK_Helmet"):
            continue
        rec = (o.type, tuple(round(v, 6) for row in o.matrix_world for v in row), o.hide_render,
               o.hide_viewport, o.parent.name if o.parent else None)
        if o.type == "MESH":
            rec += (mesh_hash(o.data), tuple((m.type, m.name) for m in o.modifiers),
                    tuple(m.name for m in o.data.materials if m))
        snap["objects"][o.name] = rec
    return snap


def scope_checks(before, after):
    section("A  scope - nothing outside the helmet changed")
    earlier = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "Wildshift_Knight_0[123]*.blend")))
    r = subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--", *earlier],
                       capture_output=True, text=True)
    check("earlier checkpoints are untouched in git (01, 02, 03)",
          r.returncode == 0 and r.stdout.strip() == "" and len(earlier) == 3,
          ", ".join(earlier) + ("" if not r.stdout.strip() else f" | {r.stdout.strip()}"))
    check("output file exists with the requested name",
          os.path.basename(DST) == "Wildshift_Knight_04_HelmetBlockout.blend" and os.path.isfile(DST),
          f"{os.path.basename(DST)} ({os.path.getsize(DST) / 1e6:.1f} MB)")
    changed = [n for n, rec in before["objects"].items() if after["objects"].get(n) != rec]
    added = [n for n in after["objects"] if n not in before["objects"]]
    check("every pre-existing object is unchanged (mesh, transform, visibility, modifiers)",
          not changed, f"{len(before['objects'])} objects compared" + (f"; changed {changed}" if changed else ""))
    check("no new objects outside WSK_Helmet_*", not added, str(added) if added else "none")
    body_same = before["objects"].get(BODY) == after["objects"].get(BODY)
    check("base body kept as the scale reference, mesh identical to checkpoint 03", body_same,
          BODY)
    bad = []
    for c, objs in before["collections"].items():
        if c == "Helmet":
            continue
        if after["collections"].get(c) != objs:
            bad.append(c)
    check("all other collections hold exactly the same objects", not bad,
          "Reference, Blockout, Body, Armor, Cape, Accessories, Weapon, Rig, Lighting and Cameras"
          + (f"; differ: {bad}" if bad else ""))
    empty = [c for c in ("Armor", "Cape", "Accessories", "Weapon", "Rig") if after["collections"].get(c)]
    check("later-stage collections still empty (Armor, Cape, Accessories, Weapon, Rig)", not empty,
          str(empty) if empty else "")
    check("Crown is a new child collection of Helmet",
          after["children"].get("Helmet") == ["Crown"] and "Crown" not in before["collections"])
    lay_bad = [k for k, v in before["layers"].items() if after["layers"].get(k) != v]
    check("view-layer states unchanged (Blockout still excluded, Reference visible)", not lay_bad,
          str(lay_bad) if lay_bad else "")
    check("scene units / render settings unchanged",
          before["unit"] == after["unit"] and before["render"] == after["render"],
          f"{after['unit']}, {after['render']}")
    t_bad = [n for n, s in before["texts"].items()
             if not after["texts"].get(n, "").startswith(s.rstrip())]
    check("earlier text blocks preserved (project notes only appended to)", not t_bad,
          str(t_bad) if t_bad else ", ".join(sorted(before["texts"])))
    new_texts = sorted(set(after["texts"]) - set(before["texts"]))
    check("helmet notes text block added", new_texts == ["WSK_Helmet_Blockout_Notes.txt"],
          str(new_texts))
    pn_old, pn_new = before["texts"].get("WSK_Project_Notes.txt", ""), after["texts"].get("WSK_Project_Notes.txt", "")
    check("project notes carry a Prompt 4 section", "Prompt 4" in pn_new[len(pn_old) - 2:],
          f"+{len(pn_new) - len(pn_old)} characters")
    mats_new = sorted(set(after["materials"]) - set(before["materials"]))
    check("only the three helmet placeholder materials were added",
          mats_new == sorted([STEEL, VOID, IRON]), str(mats_new))


# --------------------------------------------------------------------------
# B objects, hierarchy, materials
# --------------------------------------------------------------------------
NAME_RE = re.compile(r"^WSK_Helmet_[A-Z][A-Za-z]+(_[A-Z][A-Z0-9]?\d?)?_\d{2}$")


def lum(rgb):
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def object_checks():
    section("B  objects, hierarchy, materials, no rig")
    objs = bpy.data.objects
    helm = bpy.data.collections.get("Helmet")
    crown = bpy.data.collections.get("Crown")
    check("Helmet collection = root + shell + face plate + crest + neck guard",
          helm is not None and {o.name for o in helm.objects} == HELMET_SET,
          ", ".join(sorted(o.name for o in helm.objects)) if helm else "missing")
    check("Crown collection = band + halo + spine + mount + 9 spikes (all separate objects)",
          crown is not None and {o.name for o in crown.objects} == CROWN_SET,
          f"{len(crown.objects)} objects" if crown else "missing")
    allnames = sorted(HELMET_SET | CROWN_SET)
    bad = [n for n in allnames if not NAME_RE.match(n)]
    check("names follow WSK_<Category>_<Descriptor>_<Index>", not bad, str(bad) if bad else
          "e.g. WSK_Helmet_CrownSpike_R2_01")
    shared = [n for n in MESHES if objs[n].data.users != 1]
    check("every part has its own mesh datablock (independently editable)", not shared,
          str(shared) if shared else f"{len(MESHES)} meshes, 1 user each")
    wrong_par = [n for n, p in PARENT.items()
                 if (objs[n].parent.name if objs[n].parent else None) != p]
    check("hierarchy: head parts -> root, spine/mount/spikes -> halo, neck guard unparented",
          not wrong_par, str(wrong_par) if wrong_par else "")
    root = objs[ROOT_OBJ]
    joint = objs.get("WSK_Joint_Neck")
    jloc = joint.matrix_world.translation if joint else Vector(GUIDE["neck_joint"])
    check("root empty sits on the guide neck joint, unrotated, unit scale",
          root.type == "EMPTY" and (root.matrix_world.translation - jloc).length < 1e-6
          and root.rotation_euler.to_quaternion().angle < 1e-9
          and (Vector(root.scale) - Vector((1, 1, 1))).length < 1e-9,
          f"root {tuple(round(c, 4) for c in root.matrix_world.translation)}, "
          f"WSK_Joint_Neck {tuple(round(c, 4) for c in jloc)}")
    mods = {n: [m.type for m in objs[n].modifiers] for n in (SHELL, FACE, GORGET)}
    check("shell / face plate / neck guard keep live modifiers (Mirror > Solidify > Subsurf)",
          all(v == ["MIRROR", "SOLIDIFY", "SUBSURF"] for v in mods.values()), str(mods))
    props = [n for n in HELMET_SET | CROWN_SET
             if not all(k in objs[n] for k in ("wsk_part", "wsk_confidence", "wsk_prompt"))]
    check("every object carries wsk_part / wsk_confidence / wsk_prompt", not props,
          str(props) if props else "")
    wrong_mat = [n for n in MESHES if [m.name for m in objs[n].data.materials] != [MATERIAL[n]]]
    check("one placeholder material per part, as assigned", not wrong_mat,
          str(wrong_mat) if wrong_mat else "steel: shell/crest/neck guard, void: face plate, iron: crown")
    for mname in (STEEL, VOID, IRON):
        m = bpy.data.materials[mname]
        nodes = m.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        base = bsdf.inputs["Base Color"].default_value
        em_s = bsdf.inputs["Emission Strength"].default_value
        em_c = bsdf.inputs["Emission Color"].default_value
        types = sorted(n.type for n in nodes)
        dark = lum(base) <= 0.06 and lum(m.diffuse_color) <= 0.06
        glow = em_s > 0.0 and lum(em_c) > 0.0
        check(f"{mname}: dark, untextured, non-emissive",
              dark and not glow and types == ["BSDF_PRINCIPLED", "OUTPUT_MATERIAL"],
              f"base lum {lum(base):.4f}, metallic {bsdf.inputs['Metallic'].default_value:.2f}, "
              f"roughness {bsdf.inputs['Roughness'].default_value:.2f}, emission {em_s:g}")
    void = bpy.data.materials[VOID].node_tree.nodes["Principled BSDF"]
    check("face void is near-black and non-metallic (reads as darkness, not a face)",
          lum(void.inputs["Base Color"].default_value) <= 0.01
          and void.inputs["Metallic"].default_value == 0.0)
    rig = [o.name for o in objs if o.type == "ARMATURE"]
    keys = [n for n in MESHES if objs[n].data.shape_keys]
    cons = [n for n in HELMET_SET | CROWN_SET if objs[n].constraints or objs[n].animation_data]
    lights = [o.name for o in (list(helm.all_objects) if helm else []) if o.type == "LIGHT"]
    check("no rig, shape keys, constraints, drivers or lights (no facial animation, no glowing eyes)",
          not (rig or keys or cons or lights), f"armatures {rig}, keys {keys}, cons {cons}, lights {lights}")
    note(f"crown = {len(CROWN_SET)} objects: 4 structural (band, halo, spine, mount) + "
         f"{len(SPIKES)} broad spikes - no small thorns yet (deferred detail)")


# --------------------------------------------------------------------------
# evaluated geometry
# --------------------------------------------------------------------------
class Geo:
    """Evaluated mesh of one object, world space, with topology stats."""

    def __init__(self, obj, dg):
        ev = obj.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        mw = np.array(ev.matrix_world)
        self.co = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
        nr = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("normal", nr)
        self.nrm = nr.reshape(-1, 3) @ mw[:3, :3].T
        t = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
        me.loop_triangles.foreach_get("vertices", t)
        self.tris = t.reshape(-1, 3)
        bm = bmesh.new()
        bm.from_mesh(me)
        self.n_boundary = sum(1 for e in bm.edges if e.is_boundary)
        self.n_nonmanifold = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
        self.chi = len(bm.verts) - len(bm.edges) + len(bm.faces)
        self.n_loose = sum(1 for v in bm.verts if not v.link_faces)
        self.n_faces = len(bm.faces)
        bm.free()
        ev.to_mesh_clear()
        self.name = obj.name
        self.bvh = BVHTree.FromPolygons(self.co.tolist(), self.tris.tolist(), all_triangles=True)
        self.min = self.co.min(axis=0)
        self.max = self.co.max(axis=0)

    def volume_and_centroid(self):
        a, b, c = (self.co[self.tris[:, k]] for k in range(3))
        v = np.einsum("ij,ij->i", a, np.cross(b, c)) / 6.0
        vol = v.sum()
        cen = ((a + b + c) / 4.0 * v[:, None]).sum(axis=0) / vol if vol else np.zeros(3)
        return vol, cen

    def self_intersections(self):
        pairs = self.bvh.overlap(self.bvh)
        tris = self.tris
        n = 0
        for i, j in pairs:
            if i >= j:
                continue
            if set(tris[i]) & set(tris[j]):
                continue
            n += 1
        return n

    def degenerate(self):
        a, b, c = (self.co[self.tris[:, k]] for k in range(3))
        area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
        return int((area < 1e-10).sum())


def nearest_dist(points, bvh):
    best = math.inf
    for p in points:
        hit = bvh.find_nearest(Vector(p))
        if hit[0] is not None and hit[3] < best:
            best = hit[3]
    return best


def gap(A, B, margin=0.06, sel_a=None, sel_b=None):
    """(intersects, n_pairs, min distance) between two evaluated meshes."""
    pairs = A.bvh.overlap(B.bvh)
    if pairs:
        return True, len(pairs), 0.0
    if np.any(A.min - margin > B.max) or np.any(B.min - margin > A.max):
        d = float(np.max(np.maximum(A.min - B.max, B.min - A.max)))
        return False, 0, d
    pa = A.co if sel_a is None else A.co[sel_a]
    pb = B.co if sel_b is None else B.co[sel_b]
    return False, 0, min(nearest_dist(pa, B.bvh), nearest_dist(pb, A.bvh))


def mesh_checks(geo):
    section("C  evaluated-mesh integrity (modifiers applied in memory)")
    rows = []
    bad = []
    for n in MESHES:
        g = geo[n]
        vol, _ = g.volume_and_centroid()
        si = g.self_intersections()
        dg = g.degenerate()
        ok = (g.n_boundary == 0 and g.n_nonmanifold == 0 and g.chi == EXPECTED_CHI[n]
              and vol > 0 and si == 0 and dg == 0 and g.n_loose == 0)
        rows.append(f"{n:34s} faces {g.n_faces:6d}  open {g.n_boundary}  non-manifold "
                    f"{g.n_nonmanifold}  chi {g.chi:+d}  vol {vol * 1e6:9.1f} cm3  self-x {si}  degen {dg}")
        if not ok:
            bad.append(n)
    for r in rows:
        print("      " + r)
    check("all 17 parts are closed, manifold solids with the expected topology", not bad,
          str(bad) if bad else "no open edges, no non-manifold edges")
    check("outward normals on every part (positive enclosed volume)",
          all(geo[n].volume_and_centroid()[0] > 0 for n in MESHES))
    check("no self-intersections, degenerate faces or loose vertices", not bad)
    return rows


# --------------------------------------------------------------------------
# D symmetry and balance
# --------------------------------------------------------------------------
def mirror_dev(pts_a, pts_b):
    kd = KDTree(len(pts_b))
    for i, p in enumerate(pts_b):
        kd.insert(Vector(p), i)
    kd.balance()
    worst = 0.0
    for p in pts_a:
        _co, _i, d = kd.find(Vector((-p[0], p[1], p[2])))
        worst = max(worst, d)
    return worst


def symmetry_checks(geo):
    section("D  symmetry and crown balance")
    sym = [SHELL, FACE, CREST, GORGET, BAND, HALO, SPINE, MOUNT, "WSK_Helmet_CrownSpike_C_01"]
    worst = {n: mirror_dev(geo[n].co, geo[n].co) for n in sym}
    w = max(worst.values())
    check("symmetric parts mirror onto themselves across X = 0 (evaluated)", w <= 5e-4,
          f"worst {mm(w)} ({max(worst, key=worst.get)})")
    pw = {}
    for k in ("1", "2", "3", "4"):
        r, l = f"WSK_Helmet_CrownSpike_R{k}_01", f"WSK_Helmet_CrownSpike_L{k}_01"
        pw[k] = mirror_dev(geo[r].co, geo[l].co)
    check("left/right spikes are exact mirror pairs", max(pw.values()) <= 5e-4,
          f"worst {mm(max(pw.values()))}")
    tot_v, mom = 0.0, np.zeros(3)
    for n in CROWN_PARTS:
        v, c = geo[n].volume_and_centroid()
        tot_v += v
        mom += v * c
    cc = mom / tot_v
    check("crown centre of mass on the centre line (left/right balance)", abs(cc[0]) <= 5e-4,
          f"x {mm(cc[0])}")
    hv, hm = 0.0, np.zeros(3)
    for n in (SHELL, FACE, CREST):
        v, c = geo[n].volume_and_centroid()
        hv += v
        hm += v * c
    hc = hm / hv
    check("helmet centre of mass on the centre line", abs(hc[0]) <= 5e-4, f"x {mm(hc[0])}")
    note(f"crown centre of mass ({cc[0]:+.3f}, {cc[1]:+.3f}, {cc[2]:.3f}) - "
         f"{abs(cc[1] - HEAD_PIVOT.y) * 100:.1f} cm behind and {(cc[2] - HEAD_PIVOT.z) * 100:.1f} cm "
         f"above the neck joint; carried by the spine + mount on the back of the band")
    lengths = {}
    halo = bpy.data.objects[HALO]
    centre = halo.matrix_world.translation
    for s in SPIKE_IDS:
        g = geo[f"WSK_Helmet_CrownSpike_{s}_01"]
        lengths[s] = max(np.linalg.norm(g.co - np.array(centre), axis=1))
    order = [lengths["C"], lengths["R1"], lengths["R2"], lengths["R3"], lengths["R4"]]
    check("spike reach falls off steadily from the top to the sides (organised, not random)",
          all(order[i] > order[i + 1] for i in range(4)),
          " > ".join(f"{v * 100:.1f}" for v in order) + " cm from the halo centre")
    return cc


# --------------------------------------------------------------------------
# E fit and contacts
# --------------------------------------------------------------------------
def fit_checks(geo, body):
    section("E  fit - clearances, contacts, enclosure")
    head_sel = body.co[:, 2] > 1.70
    clear = {}
    for n, need in ((SHELL, 0.005), (FACE, 0.005), (CREST, 0.005), (GORGET, 0.005)):
        x, k, d = gap(body, geo[n], sel_a=head_sel if n != GORGET else body.co[:, 2] > 1.60)
        clear[n] = d
        check(f"{n} clears the body by >= {mm(need)}", not x and d >= need,
              "INTERSECTS" if x else mm(d))
    dmin = math.inf
    for n in CROWN_PARTS:
        x, k, d = gap(body, geo[n], sel_a=head_sel)
        dmin = min(dmin, 0.0 if x else d)
    clear["crown"] = dmin
    check("crown clears the body by >= 10 mm", dmin >= 0.010, mm(dmin))

    # every pair: only intended contacts may touch
    names = MESHES
    stray = []
    pair_gap = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            x, k, d = gap(geo[a], geo[b], margin=0.02)
            pair_gap[frozenset((a, b))] = (x, d)
            if x and frozenset((a, b)) not in INTENDED:
                stray.append(f"{a}/{b} ({k})")
    check("no unintended intersections between any two parts", not stray,
          f"{len(names) * (len(names) - 1) // 2} pairs tested" + (f"; {stray}" if stray else ""))
    missing = [f"{a}/{b}" for a, b in REQUIRED if not pair_gap[frozenset((a, b))][0]
               and pair_gap[frozenset((a, b))][1] > 5e-4]
    check("intended joints really connect (spikes/spine sunk in the halo, mount in band + spine, "
          "crest in face plate + shell)", not missing, str(missing) if missing else
          f"{len(REQUIRED)} joints")
    xb, db = pair_gap[frozenset((SHELL, BAND))]
    check("crown band rests on the shell (0.5 - 3 mm gap, no intersection)",
          not xb and 0.0005 <= db <= 0.003, "INTERSECTS" if xb else mm(db))
    xs, ds = pair_gap[frozenset((SHELL, GORGET))]
    check("neck guard nests under the helmet rim without touching (>= 3 mm)",
          not xs and ds >= 0.003, "INTERSECTS" if xs else mm(ds))
    xf, df = pair_gap[frozenset((FACE, GORGET))]
    check("face plate chin clears the neck guard (>= 3 mm)", not xf and df >= 0.003,
          "INTERSECTS" if xf else mm(df))
    hal = min(pair_gap[frozenset((SHELL, n))][1] for n in [HALO, SPINE] + SPIKES)
    check("halo, spine and spikes stand off the shell (>= 8 mm)", hal >= 0.008, mm(hal))
    xfs, dfs = pair_gap[frozenset((SHELL, FACE))]
    note(f"face plate sits {mm(dfs)} behind the shell's slot edges - a recessed plate held by "
         f"the crest keel")

    # enclosure: every head vertex is hidden from front, back, sides and top
    tree_parts = [geo[n] for n in (SHELL, FACE, CREST, GORGET)]
    head = body.co[body.co[:, 2] >= 1.755]
    dirs = {"front": (0, 1, 0), "back": (0, -1, 0), "right": (1, 0, 0), "left": (-1, 0, 0),
            "top": (0, 0, 1)}
    seen = {}
    for k, d in dirs.items():
        dv = Vector(d)
        vis = 0
        for p in head:
            o = Vector(p) + dv * 1e-4
            if not any(t.bvh.ray_cast(o, dv, 2.0)[0] is not None for t in tree_parts):
                vis += 1
        seen[k] = vis
    check("head fully enclosed (helmet + neck guard): no head vertex visible from front, back, sides or top",
          all(v == 0 for v in seen.values()),
          f"{len(head)} head vertices; visible {seen}")

    # featureless face: the plate's front centre-line profile has a single
    # gentle bulge - no nose, lips, brow or chin bumps
    g = geo[FACE]
    sel = (np.abs(g.co[:, 0]) < 1e-4) & (g.nrm[:, 1] > 0.5)
    keel = g.co[sel]
    keel = keel[np.argsort(keel[:, 2])]
    ys = keel[:, 1]
    peaks = [i for i in range(1, len(ys) - 1)
             if ys[i] >= ys[i - 1] and ys[i] >= ys[i + 1]
             and ys[i] - min(ys[:i].min(), ys[i + 1:].min()) > 3e-4]
    dips = [i for i in range(1, len(ys) - 1) if ys[i] < ys[i - 1] - 2e-4 and ys[i] < ys[i + 1] - 2e-4]
    check("face plate is featureless (one smooth bulge on its front centre line: no nose, "
          "lips or brow)", len(peaks) <= 1 and not dips,
          f"{len(peaks)} bulge, {len(dips)} hollows over {len(ys)} samples "
          f"(z {keel[0, 2]:.3f}-{keel[-1, 2]:.3f})")
    return clear, pair_gap


def see_through_check():
    """Rays through the helmet silhouette (side + front) at RENDER-level
    subdivision: any opening of >= 1 x 1 mm inside the silhouette between the
    first and last hit of a row is a hole (e.g. a gap at the face-slot corner)."""
    keep = (SHELL, FACE, CREST, BAND)
    for n in keep:
        for m in bpy.data.objects[n].modifiers:
            if m.type == "SUBSURF":
                m.levels = m.render_levels
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    trees = [Geo(bpy.data.objects[n], dg).bvh for n in keep]
    step = 0.0005
    found = {}
    for label, d, mk, urange in (
            ("side", Vector((1.0, 0.0, 0.0)), lambda u, z: Vector((-0.4, u, z)), (-0.12, 0.15)),
            ("front", Vector((0.0, -1.0, 0.0)), lambda u, z: Vector((u, 0.5, z)), (-0.11, 0.11))):
        us = np.arange(urange[0], urange[1], step)
        rows = []
        for z in np.arange(1.770, 1.950, step):
            hit = np.array([any(t.ray_cast(mk(u, z), d, 1.0)[0] is not None for t in trees) for u in us])
            inside = np.zeros_like(hit)
            if hit.any():
                i0, i1 = np.nonzero(hit)[0][[0, -1]]
                inside[i0:i1 + 1] = ~hit[i0:i1 + 1]
            rows.append(inside)
        g = np.array(rows)
        block = g[:-1, :-1] & g[1:, :-1] & g[:-1, 1:] & g[1:, 1:]   # >= 2x2 cells
        found[label] = (int(block.sum()), int(g.sum()))
    check("no see-through holes in the helmet silhouette (side + front, render subdivision)",
          all(v[0] == 0 for v in found.values()),
          ", ".join(f"{k}: {v[0]} hole cells ({v[1]} grazing rays)" for k, v in found.items()))


# --------------------------------------------------------------------------
# F dimensions
# --------------------------------------------------------------------------
def dimension_checks(geo):
    section("F  dimensions against the Prompt 2 guide envelope")
    sh = geo[SHELL]
    half_w = max(abs(sh.min[0]), abs(sh.max[0]))
    check("helmet width (shell) within 5 % of the guide 0.190 m",
          abs(half_w - GUIDE["helmet_half_w"]) <= 0.05 * GUIDE["helmet_half_w"],
          f"{2 * half_w:.4f} m ({(half_w / GUIDE['helmet_half_w'] - 1) * 100:+.1f} %)")
    check("helmet dome top on the guide 2.000 m (+- 10 mm)",
          abs(sh.max[2] - GUIDE["dome_top"]) <= 0.010, f"{sh.max[2]:.4f} m")
    chin = min(geo[FACE].min[2], geo[CREST].min[2])
    check("helmet chin on the guide 1.740 m (+- 10 mm)", abs(chin - GUIDE["chin"]) <= 0.010,
          f"{chin:.4f} m")
    halo = geo[HALO]
    rw = max(abs(halo.min[0]), abs(halo.max[0]))
    check("halo outer width within 5 % of the guide crown ring 0.280 m",
          abs(rw - GUIDE["ring_half_w"]) <= 0.05 * GUIDE["ring_half_w"],
          f"{2 * rw:.4f} m ({(rw / GUIDE['ring_half_w'] - 1) * 100:+.1f} %)")
    check("halo bottom on the guide ring frame 1.790 m (+- 10 mm)",
          abs(halo.min[2] - GUIDE["ring_bottom"]) <= 0.010, f"{halo.min[2]:.4f} m")
    sp_x = max(max(abs(geo[s].min[0]), abs(geo[s].max[0])) for s in SPIKES)
    check("spike span within 5 % of the guide +-0.180 m",
          abs(sp_x - GUIDE["spike_half_w"]) <= 0.05 * GUIDE["spike_half_w"], f"+-{sp_x:.4f} m")
    r1 = geo["WSK_Helmet_CrownSpike_R1_01"].max[2]
    check("upper side spikes (+-30 deg) reach the guide spike top 2.110 m (+- 10 mm)",
          abs(r1 - GUIDE["spike_top"]) <= 0.010, f"{r1:.4f} m")
    c_top = geo["WSK_Helmet_CrownSpike_C_01"].max[2]
    ring_top = halo.max[2]
    low = min(geo[s].min[2] for s in SPIKES)
    deviations.append(f"central spike tip at {c_top:.3f} m, {(c_top - GUIDE['spike_top']) * 100:+.1f} cm "
                      f"over the guide's 2.11 (marked 'guide only / not measured'); the reference's "
                      f"top spike is clearly the tallest element - scale WSK_Helmet_CrownSpike_C_01 "
                      f"in local Z to {(GUIDE['spike_top'] - (c_top - 0.145)) / 0.145:.2f} to sit on the guide")
    deviations.append(f"halo top at {ring_top:.3f} m vs the guide ring frame top 1.930: the guide frame "
                      f"only covers the ring's sides; in the reference the ring clears the hood by ~4 cm "
                      f"(here {(ring_top - sh.max[2]) * 100:.1f} cm over the dome)")
    deviations.append(f"lowest spike tips at {low:.3f} m vs the guide spike frame bottom 1.760: the "
                      f"lower spikes sweep back (cone) rather than down, keeping them off the "
                      f"pauldrons-to-come")
    for d in deviations:
        note("deviation: " + d)
    dims = dict(helmet_w=2 * half_w, dome=sh.max[2], chin=chin, ring_w=2 * rw,
                ring_bottom=halo.min[2], ring_top=ring_top, spike_x=sp_x, r1_top=r1,
                c_top=c_top, low_spike=low,
                depth=max(geo[n].max[1] for n in (SHELL, FACE, CREST)) - sh.min[1],
                front=max(geo[n].max[1] for n in (SHELL, FACE, CREST)),
                back_crown=min(geo[n].min[1] for n in CROWN_PARTS))
    return dims


# --------------------------------------------------------------------------
# G rig
# --------------------------------------------------------------------------
def rot_about(pivot, axis, deg):
    return (Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(deg), 4, axis)
            @ Matrix.Translation(-pivot))


class Sweep:
    def __init__(self, geo, body):
        cos, tris, off = [], [], 0
        for n in HEAD_MOVING:
            g = geo[n]
            cos.append(g.co)
            tris.append(g.tris + off)
            off += len(g.co)
        self.mov = np.vstack(cos)
        self.mtris = np.vstack(tris).tolist()
        bt = body.tris[(body.co[body.tris][:, :, 2] <= TORSO_TOP).all(axis=1)]
        used = np.unique(bt)
        remap = -np.ones(len(body.co), dtype=np.int64)
        remap[used] = np.arange(len(used))
        tco = body.co[used]
        g = geo[GORGET]
        sco = np.vstack([tco, g.co])
        stris = np.vstack([remap[bt], g.tris + len(tco)])
        self.static_co = sco
        self.static = BVHTree.FromPolygons(sco.tolist(), stris.tolist(), all_triangles=True)
        self.static_probe = sco[sco[:, 2] > 1.62]

    def clearance(self, M):
        m = np.array(M)
        p = self.mov @ m[:3, :3].T + m[:3, 3]
        bvh = BVHTree.FromPolygons(p.tolist(), self.mtris, all_triangles=True)
        if bvh.overlap(self.static):
            return 0.0
        sel = p[p[:, 2] < 1.86]
        return min(nearest_dist(sel, self.static), nearest_dist(self.static_probe, bvh))

    def limit(self, pivot, axis, sign, start=0.0, stop=90.0, step=2.0):
        a_ok, a = start, start
        while a < stop:
            a = min(a + step, stop)
            if self.clearance(rot_about(pivot, axis, sign * a)) <= 0.0:
                lo, hi = a_ok, a
                for _ in range(4):
                    mid = 0.5 * (lo + hi)
                    if self.clearance(rot_about(pivot, axis, sign * mid)) <= 0.0:
                        hi = mid
                    else:
                        lo = mid
                return lo
            a_ok = a
        return None


MOTIONS = [("flexion (chin down)", "X", -1), ("extension (look up)", "X", +1),
           ("turn to character right", "Z", -1), ("turn to character left", "Z", +1),
           ("tilt to right shoulder", "Y", +1), ("tilt to left shoulder", "Y", -1)]
# head bone alone, about the guide neck joint (atlanto-occipital/-axial range:
# nod ~15-20 deg, tilt ~5-10 deg, turn ~40-50 deg - asked for more where cheap)
HEAD_LIMITS = (15, 20, 60, 60, 10, 10)
HEAD_POSES = [("flexion 15", [("X", -15)]), ("extension 20", [("X", 20)]),
              ("turn R 60", [("Z", -60)]), ("turn L 60", [("Z", 60)]),
              ("tilt R 10", [("Y", 10)]), ("tilt L 10", [("Y", -10)]),
              ("flex 10 + turn R 45", [("X", -10), ("Z", -45)]),
              ("flex 10 + turn L 45", [("X", -10), ("Z", 45)]),
              ("ext 15 + turn R 45", [("X", 15), ("Z", -45)]),
              ("ext 15 + turn L 45", [("X", 15), ("Z", 45)]),
              ("tilt R 8 + turn L 30", [("Y", 8), ("Z", 30)]),
              ("tilt L 8 + turn R 30", [("Y", -8), ("Z", -30)])]
# neck bone (pivot at the neck base) carrying the head bone: everyday ranges
CHAIN_POSES = [("look down 30 (neck 18 + head 12)", [("X", -18)], [("X", -12)]),
               ("look up 45 (neck 25 + head 20)", [("X", 25)], [("X", 20)]),
               ("tilt R 30 (neck 20 + head 10)", [("Y", 20)], [("Y", 10)]),
               ("tilt L 30 (neck 20 + head 10)", [("Y", -20)], [("Y", -10)]),
               ("over R shoulder 80 (30 + 50)", [("Z", -30)], [("Z", -50)]),
               ("over L shoulder 80 (30 + 50)", [("Z", 30)], [("Z", 50)]),
               ("down-left (neck 15 + head 10, turn 45)", [("X", -15)], [("X", -10), ("Z", 45)]),
               ("up-right (neck 15 + head 15, turn 45)", [("X", 15)], [("X", 15), ("Z", -45)])]


def pose_matrix(pivot, seq):
    m = Matrix.Identity(4)
    for axis, deg in seq:                     # applied in order (nod, then turn)
        m = rot_about(pivot, axis, deg) @ m
    return m


def chain_matrix(neck_seq, head_seq):
    """Head bone rotates about its rest pivot, then the neck bone carries it."""
    return pose_matrix(NECK_PIVOT, neck_seq) @ pose_matrix(HEAD_PIVOT, head_seq)


def rig_checks(geo, body, dims):
    section("G  rig - placement and head-motion sweep")
    low = min(geo[n].min[2] for n in (SHELL, FACE, CREST))
    check("helmet does not reach down onto the chest/shoulders (lowest point >= 1.73 m)",
          low >= 1.73, f"{low:.4f} m; {(low - 1.63) * 100:.1f} cm above the shoulder joints (1.63)")
    check("helmet does not project far forward (front <= 0.150 m, guide head front 0.132)",
          dims["front"] <= 0.150, f"{dims['front']:.4f} m")
    sh = geo[SHELL]
    inside = (sh.min[0] < HEAD_PIVOT.x < sh.max[0] and sh.min[1] < HEAD_PIVOT.y < sh.max[1]
              and sh.min[2] < HEAD_PIVOT.z < sh.max[2])
    check("head pivot (neck joint) lies inside the helmet volume, root empty on it", inside,
          str(tuple(HEAD_PIVOT)))
    neck = body.co[(body.co[:, 2] > 1.70) & (body.co[:, 2] < 1.755)]
    d_neck = nearest_dist(neck, sh.bvh)
    check("neck passes through the helmet opening with room to turn (>= 10 mm)", d_neck >= 0.010,
          mm(d_neck))

    sw = Sweep(geo, body)
    base = sw.clearance(Matrix.Identity(4))
    check("rest pose: head assembly clears torso + neck guard", base > 0.0, mm(base))
    rows = []
    fails = []
    for label, seq in HEAD_POSES:
        d = sw.clearance(pose_matrix(HEAD_PIVOT, seq))
        rows.append(("head  " + label, d))
        if d < 0.002:
            fails.append(label)
    check("head bone alone clears (>= 2 mm): flex 15, ext 20, turn 60, tilt 10 and combinations",
          not fails, ", ".join(f"{l[6:]} {mm(d)}" for l, d in rows[-len(HEAD_POSES):]))
    fails = []
    for label, nseq, hseq in CHAIN_POSES:
        d = sw.clearance(chain_matrix(nseq, hseq))
        rows.append(("neck+head  " + label, d))
        if d < 0.002:
            fails.append(label)
    check("neck + head bones clear (>= 2 mm): look down 30, up 45, tilt 30, over the shoulder 80",
          not fails, ", ".join(f"{l[11:]} {mm(d)}" for l, d in rows[-len(CHAIN_POSES):]))
    limits = {}
    for label, axis, sign in MOTIONS:
        limits[label] = sw.limit(HEAD_PIVOT, axis, sign)
    txt = ", ".join(f"{k} {'> 90' if v is None else f'{v:.1f}'} deg" for k, v in limits.items())
    check("head-bone first-contact angles beyond the tested range "
          "(flex >= 15, ext >= 20, turn >= 60, tilt >= 10)",
          all((v is None) or v >= need for v, need in zip(limits.values(), HEAD_LIMITS)), txt)
    neck_lim = {}
    for label, axis, sign in MOTIONS:
        neck_lim[label] = sw.limit(NECK_PIVOT, axis, sign, stop=60.0)
    lo, hi = 0.0, 60.0
    for _ in range(12):                      # chained look-down, neck:head = 3:2
        mid = 0.5 * (lo + hi)
        if sw.clearance(chain_matrix([("X", -0.6 * mid)], [("X", -0.4 * mid)])) > 0.0:
            lo = mid
        else:
            hi = mid
    neck_lim["chained look-down (neck:head 3:2)"] = lo
    note(f"chained look-down limit {lo:.1f} deg total: the helmet chin meets the neck guard / "
         f"upper chest - expected for a closed helmet whose chin sits ~4 cm ahead of the throat")
    note("neck bone alone (whole head about the neck base (0, 0.004, 1.69)), neck guard static: "
         + ", ".join(f"{k} {'> 60' if v is None else f'{v:.1f}'} deg" for k, v in neck_lim.items()))
    return rows, limits, neck_lim


# --------------------------------------------------------------------------
# H rendering and images
# --------------------------------------------------------------------------
def font(size, bold=False):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else "")
    try:
        return ImageFont.truetype(p, size)
    except OSError:
        return ImageFont.load_default(size=size)


VIEW_CENTRE_Z = 1.94
ORTHO = 0.62
RES = (800, 1000)
VIEWS = {
    "front": dict(loc=(0.0, 3.0, VIEW_CENTRE_Z), tgt=(0.0, 0.0, VIEW_CENTRE_Z), ortho=ORTHO),
    "side_left": dict(loc=(-3.0, -0.035, VIEW_CENTRE_Z), tgt=(0.0, -0.035, VIEW_CENTRE_Z), ortho=ORTHO),
    "rear": dict(loc=(0.0, -3.0, VIEW_CENTRE_Z), tgt=(0.0, 0.0, VIEW_CENTRE_Z), ortho=ORTHO),
    "side_right": dict(loc=(3.0, -0.035, VIEW_CENTRE_Z), tgt=(0.0, -0.035, VIEW_CENTRE_Z), ortho=ORTHO),
    "threequarter": dict(loc=(-1.55, 2.05, 2.20), tgt=(0.0, -0.02, 1.93), lens=140),
    "threequarter_rear": dict(loc=(1.75, -1.85, 2.25), tgt=(0.0, -0.05, 1.93), lens=140),
}
HIDE_PREFIX = ("WSK_Guide_", "WSK_Label_", "WSK_Ref_", "WSK_Joint_", "WSK_Mann_", "WSK_Studio_")


def look_at(cam, loc, target):
    cam.location = loc
    d = (Vector(target) - Vector(loc)).normalized()
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "Standard"
    for o in bpy.data.objects:
        if o.name.startswith(HIDE_PREFIX):
            o.hide_render = True
    # dark surroundings so the dark metals reflect darkness (as they would on
    # set); the light backdrop is composited behind the alpha afterwards
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.030, 0.030, 0.034, 1.0)
    bg.inputs[1].default_value = 1.0
    rim = bpy.data.lights.new("VerifyRim", "AREA")
    rim.energy = 60.0
    rim.size = 0.6
    rim_o = bpy.data.objects.new("VerifyRim", rim)
    scene.collection.objects.link(rim_o)
    look_at(rim_o, (0.9, -1.3, 2.5), (0.0, 0.0, 1.95))
    top = bpy.data.lights.new("VerifyTop", "AREA")
    top.energy = 25.0
    top.size = 0.8
    top_o = bpy.data.objects.new("VerifyTop", top)
    scene.collection.objects.link(top_o)
    look_at(top_o, (-0.6, 0.9, 2.8), (0.0, 0.0, 1.95))
    cam = bpy.data.objects.new("VerifyCam", bpy.data.cameras.new("VerifyCam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = RES
    return scene, cam


def set_view(cam, v):
    if "ortho" in v:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = v["ortho"]
    else:
        cam.data.type = "PERSP"
        cam.data.lens = v["lens"]
    look_at(cam, v["loc"], v["tgt"])


def backdrop(size):
    w, h = size
    g = np.linspace(0.66, 0.44, h)[:, None] * np.ones((1, w))
    arr = np.dstack([g * 255, g * 255, (g + 0.015) * 255, np.full((h, w), 255)]).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def render(scene, path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    im = Image.open(path).convert("RGBA")
    comp = Image.alpha_composite(backdrop(im.size), im)
    return im, comp


def label(img, text, xy=(14, 10), size=24, fill=(20, 20, 22)):
    d = ImageDraw.Draw(img)
    d.text(xy, text, font=font(size, True), fill=fill)
    return img


def render_views(scene, cam):
    os.makedirs(SHOTS, exist_ok=True)
    shots, alphas = {}, {}
    for name, v in VIEWS.items():
        set_view(cam, v)
        path = os.path.join(SHOTS, f"helmet_{name}.png")
        print(f"      rendering {name}")
        im, comp = render(scene, path)
        comp.convert("RGB").save(path)
        shots[name] = comp.convert("RGB")
        alphas[name] = np.asarray(im)[..., 3] > 127
    return shots, alphas


def contact_sheet(shots):
    names = ["front", "side_left", "rear", "threequarter"]
    titles = ["FRONT", "SIDE (left)", "REAR", "THREE-QUARTER"]
    w, h = RES
    s = 0.6
    tw, th = int(w * s), int(h * s)
    sheet = Image.new("RGB", (tw * 4, th + 56), (235, 235, 238))
    for i, (n, t) in enumerate(zip(names, titles)):
        sheet.paste(shots[n].resize((tw, th), Image.LANCZOS), (i * tw, 56))
        ImageDraw.Draw(sheet).text((i * tw + 12, 14), t, font=font(26, True), fill=(25, 25, 28))
    path = os.path.join(SHOTS, "helmet_views_sheet.png")
    sheet.save(path)
    return path


def silhouette_sheet(alphas):
    names = [("front", "FRONT"), ("side_left", "SIDE (left)"), ("rear", "REAR")]
    w, h = RES
    s = 0.6
    tw, th = int(w * s), int(h * s)
    sheet = Image.new("RGB", (tw * 3, th + 56), (255, 255, 255))
    for i, (n, t) in enumerate(names):
        m = Image.fromarray(np.where(alphas[n], 18, 255).astype(np.uint8), "L").convert("RGB")
        sheet.paste(m.resize((tw, th), Image.LANCZOS), (i * tw, 56))
        ImageDraw.Draw(sheet).text((i * tw + 12, 14), t, font=font(26, True), fill=(25, 25, 28))
    path = os.path.join(SHOTS, "helmet_silhouettes.png")
    sheet.save(path)
    return path


def mask_checks(scene, cam, alphas):
    section("H  silhouettes (rendered masks)")
    for n in ("front", "rear"):
        m = alphas[n]
        mir = m[:, ::-1]
        iou = (m & mir).sum() / max(1, (m | mir).sum())
        check(f"{n} silhouette is left/right symmetric (IoU with its mirror >= 0.98)", iou >= 0.98,
              f"IoU {iou:.4f}")
    # crown alone, front view: balance of the halo silhouette
    keep = CROWN_SET
    hidden = {}
    for o in bpy.data.objects:
        if o.type in ("MESH", "CURVE") and o.name not in keep:
            hidden[o.name] = o.hide_render
            o.hide_render = True
    old = scene.cycles.samples
    scene.cycles.samples = 4
    set_view(cam, VIEWS["front"])
    path = os.path.join(SHOTS, "_crown_mask_front.png")
    im, _ = render(scene, path)
    os.remove(path)
    for n, h in hidden.items():
        bpy.data.objects[n].hide_render = h
    scene.cycles.samples = old
    m = np.asarray(im)[..., 3] > 127
    ys, xs = np.nonzero(m)
    cx = (RES[0] - 1) / 2.0
    left, right = (xs < cx).sum(), (xs > cx).sum()
    off_px = xs.mean() - cx
    mpp = ORTHO / RES[1]
    check("crown silhouette balanced left/right (front view)",
          abs(off_px) <= 1.0 and abs(left / right - 1.0) <= 0.02,
          f"centroid offset {off_px * mpp * 1000:+.2f} mm, area L/R {left / right:.4f}")
    span = (xs.max() - xs.min() + 1) * mpp
    top = VIEW_CENTRE_Z + (RES[1] / 2.0 - ys.min()) * mpp
    note(f"crown silhouette (front): span {span:.3f} m, top {top:.3f} m, "
         f"{m.sum() * mpp * mpp * 1e4:.0f} cm2")
    return m


def section_plot(geo, body, axis, value, title, path, view_axes, extent, centre, flip_u=False):
    """Slice the evaluated meshes with the plane coord[axis] = value."""
    colours = {BODY: (205, 205, 205), SHELL: (95, 155, 235), FACE: (190, 120, 240),
               CREST: (245, 155, 60), GORGET: (95, 205, 125)}
    for n in CROWN_PARTS:
        colours[n] = (238, 205, 85)
    size = 900
    scale = size / extent
    img = Image.new("RGB", (size, size + 70), (24, 24, 28))
    d = ImageDraw.Draw(img)
    u_ax, v_ax = view_axes
    sgn = -1.0 if flip_u else 1.0

    def px(p):
        return ((p[u_ax] - centre[0]) * scale * sgn + size / 2.0,
                size / 2.0 - (p[v_ax] - centre[1]) * scale + 70)

    # grid: 1 cm faint, 5 cm stronger
    for k in range(-40, 41):
        c = (40, 40, 46) if k % 5 else (62, 62, 70)
        u = centre[0] + k * 0.01
        x = (u - centre[0]) * scale + size / 2.0
        d.line([(x, 70), (x, size + 70)], fill=c)
        v = centre[1] + k * 0.01
        y = size / 2.0 - (v - centre[1]) * scale + 70
        d.line([(0, y), (size, y)], fill=c)
    items = [(BODY, body)] + [(n, geo[n]) for n in MESHES]
    for n, g in items:
        co, tris = g.co, g.tris
        dist = co[:, axis] - value
        dt = dist[tris]
        mixed = ~(((dt > 0).all(axis=1)) | ((dt < 0).all(axis=1)))
        for t, dd in zip(tris[mixed], dt[mixed]):
            pts = []
            for a, b in ((0, 1), (1, 2), (2, 0)):
                if (dd[a] > 0) != (dd[b] > 0):
                    u = dd[a] / (dd[a] - dd[b])
                    pts.append(co[t[a]] + u * (co[t[b]] - co[t[a]]))
            if len(pts) == 2:
                d.line([px(pts[0]), px(pts[1])], fill=colours[n], width=2)
    d.text((14, 12), title, font=font(24, True), fill=(235, 235, 240))
    legend = [("body", colours[BODY]), ("shell", colours[SHELL]), ("face plate", colours[FACE]),
              ("crest", colours[CREST]), ("neck guard", colours[GORGET]), ("crown", colours[BAND])]
    x = 14
    for t, c in legend:
        d.rectangle([x, 46, x + 14, 60], fill=c)
        d.text((x + 20, 43), t, font=font(17), fill=(220, 220, 225))
        x += 30 + int(d.textlength(t, font=font(17)))
    d.text((size - 210, 43), "grid 1 cm / 5 cm", font=font(17), fill=(170, 170, 180))
    img.save(path)
    return path


def reference_sheet(shots):
    """Reference head crops above the blockout at a matched metric scale.
    Calibration from the front reference: chin y=282 px <-> z 1.736 m,
    centre x=429 px <-> x 0, 1.832 mm/px (hood top 139 px <-> dome 1.998 m).
    The other views assume the same framing - approximate by nature."""
    mpp_ref = (1.998 - 1.736) / (282 - 139)
    jobs = [("ref_front.png", (330, 20, 520, 300), 429, "front", "FRONT"),
            ("ref_side.png", (330, 10, 560, 300), 445, "side_left", "SIDE (ref: rear-left oblique)"),
            ("ref_back.png", (300, 20, 540, 300), 420, "rear", "REAR")]
    w, h = RES
    ppm = h / ORTHO
    tiles = []
    for fname, box, cx_ref, view, title in jobs:
        ref = Image.open(os.path.join(REF, fname)).convert("RGB").crop(box)
        z_top = 1.736 + (282 - box[1]) * mpp_ref
        z_bot = 1.736 - (box[3] - 282) * mpp_ref
        u_l = (box[0] - cx_ref) * mpp_ref
        u_r = (box[2] - cx_ref) * mpp_ref
        x0 = w / 2.0 + u_l * ppm
        x1 = w / 2.0 + u_r * ppm
        y0 = h / 2.0 - (z_top - VIEW_CENTRE_Z) * ppm
        y1 = h / 2.0 - (z_bot - VIEW_CENTRE_Z) * ppm
        ours = shots[view].crop((int(x0), int(y0), int(x1), int(y1)))
        th = 560
        tw = int(ref.width * th / ref.height)
        tiles.append((title, ref.resize((tw, th), Image.LANCZOS), ours.resize((tw, th), Image.LANCZOS)))
    W = sum(t[1].width for t in tiles) + 20 * (len(tiles) + 1)
    H = 560 * 2 + 140
    sheet = Image.new("RGB", (W, H), (235, 235, 238))
    d = ImageDraw.Draw(sheet)
    x = 20
    for title, ref, ours in tiles:
        d.text((x, 12), title, font=font(24, True), fill=(25, 25, 28))
        sheet.paste(ref, (x, 50))
        sheet.paste(ours, (x, 50 + 560 + 30))
        x += ref.width + 20
    d.text((20, 50 + 560 + 4), "blockout (same metric framing, calibrated on the front view; "
           "hood/cape/armour come in later prompts)", font=font(18), fill=(60, 60, 66))
    path = os.path.join(SHOTS, "helmet_vs_reference.png")
    sheet.save(path)
    return path


def split_body_for_poses(scene):
    """Temporary head/torso copies of the body so the head can turn with the
    helmet in the pose renders (the real body is never modified)."""
    body = bpy.data.objects[BODY]
    parts = {}
    for tag, keep_head in (("head", True), ("torso", False)):
        o = body.copy()
        o.data = body.data.copy()
        o.name = f"VerifyBody_{tag}"
        scene.collection.objects.link(o)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        mw = o.matrix_world
        cut = 1.715
        kill = [v for v in bm.verts if ((mw @ v.co).z < cut) == keep_head]
        bmesh.ops.delete(bm, geom=kill, context="VERTS")
        bm.to_mesh(o.data)
        bm.free()
        parts[tag] = o
    body.hide_render = True
    root = bpy.data.objects[ROOT_OBJ]
    h = parts["head"]
    mw = h.matrix_world.copy()
    h.parent = root
    h.matrix_parent_inverse = root.matrix_world.inverted()
    h.matrix_world = mw
    return parts, body


def pose_renders(scene, cam):
    parts, body = split_body_for_poses(scene)
    root = bpy.data.objects[ROOT_OBJ]
    old_samples = scene.cycles.samples
    scene.cycles.samples = max(16, SAMPLES // 3)
    scene.render.resolution_x, scene.render.resolution_y = 560, 700
    poses = [("REST", (0, 0, 0), "side_left"), ("FLEXION 20", (-20, 0, 0), "side_left"),
             ("EXTENSION 20", (20, 0, 0), "side_left"), ("TURN 60", (0, 0, 60), "front"),
             ("TILT 15", (0, 15, 0), "front")]
    tiles = []
    for title, (rx, ry, rz), view in poses:
        root.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
        bpy.context.view_layer.update()
        v = dict(VIEWS[view])
        v["ortho"] = 0.70
        set_view(cam, v)
        path = os.path.join(SHOTS, "_pose.png")
        _im, comp = render(scene, path)
        os.remove(path)
        tiles.append(label(comp.convert("RGB"), title, size=26))
    root.rotation_euler = (0.0, 0.0, 0.0)
    for o in parts.values():
        bpy.data.objects.remove(o, do_unlink=True)
    body.hide_render = False
    scene.cycles.samples = old_samples
    scene.render.resolution_x, scene.render.resolution_y = RES
    tw, th = tiles[0].size
    sheet = Image.new("RGB", (tw * len(tiles), th), (235, 235, 238))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * tw, 0))
    path = os.path.join(SHOTS, "helmet_rig_poses.png")
    sheet.save(path)
    return path


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------
def write_report(mesh_rows, dims, clear, sweep_rows, limits, neck_lim, images, cc):
    os.makedirs(OUT, exist_ok=True)
    n_pass = sum(1 for r in results if r[1] is True)
    n_fail = sum(1 for r in results if r[1] is False)
    L = ["WILDSHIFT KNIGHT - PROMPT 4 VERIFICATION: HELMET BASE AND HEAD SILHOUETTE",
         "=" * 76,
         f"file    : {os.path.basename(DST)}",
         f"input   : {os.path.basename(SRC)} (snapshot compared, never modified)",
         "script  : tools/verify_helmet_blockout.py   (geometry = evaluated meshes)",
         f"result  : {n_pass} passed, {n_fail} failed",
         ""]
    for label_, ok, detail in results:
        if ok is None:
            L += ["", detail, "-" * len(detail)]
            continue
        L.append(f"[{'PASS' if ok else 'FAIL'}] {label_}" + (f"  -> {detail}" if detail else ""))
    L += ["", "MESH TABLE (evaluated)", "-" * 22] + mesh_rows
    L += ["", "KEY DIMENSIONS", "-" * 14,
          f"helmet width {dims['helmet_w']:.3f} m | dome top {dims['dome']:.3f} | chin {dims['chin']:.3f} | "
          f"depth incl. crest {dims['depth']:.3f} | front {dims['front']:.3f}",
          f"halo outer width {dims['ring_w']:.3f} | halo {dims['ring_bottom']:.3f} - {dims['ring_top']:.3f}",
          f"spike span +-{dims['spike_x']:.3f} | +-30 deg tips {dims['r1_top']:.3f} | central tip "
          f"{dims['c_top']:.3f} | lowest tips {dims['low_spike']:.3f} | crown rear {dims['back_crown']:.3f}",
          f"crown centre of mass ({cc[0]:+.3f}, {cc[1]:+.3f}, {cc[2]:.3f})",
          "", "CLEARANCES (min distance, evaluated)", "-" * 36]
    L += [f"{k:34s} {mm(v)}" for k, v in clear.items()]
    L += ["", "POSE SWEEP - head bone about the neck joint (0, 0, 1.78), neck bone about the",
          "neck base (0, 0.004, 1.69); torso below Z 1.69 and the neck guard static", "-" * 76]
    L += [f"{l:52s} clearance {mm(d)}" for l, d in sweep_rows]
    L += ["head bone first contact: " + ", ".join(
        f"{k} {'> 90' if v is None else f'{v:.1f}'} deg" for k, v in limits.items())]
    L += ["neck bone first contact: " + ", ".join(
        f"{k} {'> 60' if v is None else f'{v:.1f}'} deg" for k, v in neck_lim.items())]
    L += ["", "DEVIATIONS FROM THE GUIDE (deliberate, reference-driven)", "-" * 56]
    L += [f"- {d}" for d in deviations]
    L += ["", "NOTES", "-" * 5] + [f"- {n}" for n in notes if not n.startswith("deviation")]
    L += ["", "IMAGES", "-" * 6] + [f"- {os.path.relpath(p, ROOT)}" for p in images]
    with open(REPORT, "w") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"\nreport: {REPORT}")
    return n_fail


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    before = snapshot()
    bpy.ops.wm.open_mainfile(filepath=DST)
    after = snapshot()
    scope_checks(before, after)
    object_checks()

    dg = bpy.context.evaluated_depsgraph_get()
    geo = {n: Geo(bpy.data.objects[n], dg) for n in MESHES}
    body = Geo(bpy.data.objects[BODY], dg)
    mesh_rows = mesh_checks(geo)
    cc = symmetry_checks(geo)
    clear, _pairs = fit_checks(geo, body)
    dims = dimension_checks(geo)
    sweep_rows, limits, neck_lim = rig_checks(geo, body, dims)
    section("E2 silhouette integrity")
    see_through_check()

    images = []
    if not SKIP_RENDERS:
        os.makedirs(SHOTS, exist_ok=True)
        images.append(section_plot(geo, body, 0, 1e-5, "MID-SAGITTAL SECTION  x = 0  (character faces right)",
                                   os.path.join(SHOTS, "helmet_section_sagittal.png"), (1, 2), 0.50,
                                   (-0.03, 1.93)))
        images.append(section_plot(geo, body, 1, 0.004, "CORONAL SECTION  y = 0.004 (neck joint), seen from the front",
                                   os.path.join(SHOTS, "helmet_section_coronal.png"), (0, 2), 0.50,
                                   (0.0, 1.93), flip_u=True))
        images.append(section_plot(geo, body, 2, 1.855, "TRANSVERSE SECTION  z = 1.855 (widest skull)  front up",
                                   os.path.join(SHOTS, "helmet_section_transverse.png"), (0, 1), 0.36,
                                   (0.0, -0.02)))
        scene, cam = setup_render()
        shots, alphas = render_views(scene, cam)
        images += [os.path.join(SHOTS, f"helmet_{n}.png") for n in VIEWS]
        images.append(contact_sheet(shots))
        images.append(silhouette_sheet(alphas))
        mask_checks(scene, cam, alphas)
        images.append(reference_sheet(shots))
        images.append(pose_renders(scene, cam))
    n_fail = write_report(mesh_rows, dims, clear, sweep_rows, limits, neck_lim, images, cc)
    if n_fail:
        raise SystemExit(1)


main()
