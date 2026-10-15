# Cavaliere3D — Wildshift Knight

Modelling project for a dark-fantasy knight character, built step by step in
Blender. Each step is a saved checkpoint (`.blend`) plus the script that
produced it, so every stage is reproducible and the earlier stages are never
disturbed.

## Checkpoints

| stage | file | content |
|---|---|---|
| 1 | `Wildshift_Knight_01.blend` | empty project: metric units, 1 unit = 1 m, origin/ground, studio lights, orthographic front/side/rear cameras, named collections, naming convention |
| 2 | `Wildshift_Knight_02_Proportions.blend` | measured proportion sheet, blockout mannequin, joint markers, silhouette/cape/weapon guides, reference views as aligned backdrops |
| 3 | `Wildshift_Knight_03_BaseBody.blend` | clean base body: one closed quad-dominant humanoid mesh (torso, pelvis, neck, head blank, arms, hands with thumbs, legs, feet), neutral material, proportion guide retained |

## Prompt 2 — proportions

Deliverables:

* **`Wildshift_Knight_02_Proportions.blend`** — the proportioned blockout.
  * `Blockout` collection: `WSK_Mann_*`, 19 edit-friendly parts + a root empty.
    Each part is its own object with an identity transform, so a coordinate read
    in Edit mode *is* a world coordinate and X mirroring is exact.
  * `Reference` collection: `WSK_Joint_*` joint markers, `WSK_Guide_*`
    centreline / height ruler / silhouette / cape / weapon guides, `WSK_Label_*`
    ruler labels and `WSK_Ref_*` reference-view backdrops.
  * Text blocks `WSK_Proportion_Sheet.txt` (the sheet itself) and
    `WSK_Project_Notes.txt` (project conventions).
* **`analysis/diagram_front.png`, `analysis/diagram_side.png`** — annotated
  orthographic diagrams with the landmark heights and joint positions.
* **`analysis/reference_measurements.md`** — every reading taken off the
  reference, with its uncertainty.
* **`analysis/overlay_{front,back,side}.png`** — the rendered silhouette laid
  over the reference view at the calibrated scale.
* **`analysis/verify/verify_report.txt`** — 62 automated checks.

### Numbers

Body height 2.00 m ground → helmet dome (crown spikes add 0.11 m and are
guide-only). Shoulder joints at Z 1.63 (±0.20), hips at Z 1.00 (±0.10), knees
0.55, ankles 0.115. Upper arm 0.34 m, forearm 0.30 m, thigh 0.45 m, shank
0.44 m. Cape envelope 1.10 m wide, hem at Z 0.06, rear extent Y −0.72. Weapon
envelope 1.39 m long, crossguard 0.19 m, axis 0.36 m to the character's left.
Everything is marked *measured* or *assumed* in
`WSK_Proportion_Sheet.txt`, and lengths are ± 5 % at best (see the
uncertainties section of that text block).

## Prompt 3 — base body

Deliverable: **`Wildshift_Knight_03_BaseBody.blend`**

* `Body` collection — **`WSK_Body_Base_01`**, a single closed manifold mesh:
  1832 verts / 1838 faces, 96 % quads, V−E+F = 2, no loose or duplicate
  vertices, no self-intersections, only six n-gons (the tube-root caps).
* The Prompt 2 blockout and the whole proportion guide are **retained**:
  `Blockout` (`WSK_Mann_*`, 20 objects) is disabled in the viewport and in
  renders, `Reference` (`WSK_Joint_*`, `WSK_Guide_*`, `WSK_Label_*`,
  `WSK_Ref_*`) is still enabled and separate from the body.  Nothing was deleted.
* `Helmet`, `Armor`, `Cape`, `Accessories`, `Weapon` and `Rig` are still empty:
  no armour, helmet, cape, chains, weapon, rig or animation was created.
* Text blocks `WSK_BaseBody_Topology_Notes.txt` (the topology report below) and
  `WSK_Project_Notes.txt`.

### How the body is built

The torso/neck/head is a lofted **half shell** (rings of 17 verts from the
crotch to the crown). Where a limb attaches, a rectangular **patch of quads is
deleted and its boundary loop becomes the first ring of the limb tube**, so
every limb is continuous with the torso — no bridging, no overlapping shells,
no interior geometry. Ring angles are eased from the irregular cut boundary
onto an even spacing, and each ring's "front" axis is pinned to +Y so no tube
twists. The +X half is then mirrored with an applied Mirror modifier
(clip + 0.5 mm merge): left/right are exact and the centreline is welded.

Everything is in world space with an identity object transform, so a
coordinate read in Edit mode *is* a world coordinate — the same convention as
the Prompt 2 blockout.

### Numbers

Origin, orientation and scale are unchanged. Feet on Z = 0, crown (no helmet)
**1.910 m**, i.e. 0.09 m of shell clearance under the guide's 2.00 m helmet
dome — the 2.00 m envelope belongs to the helmet, not the bare skull. Torso
0.326 × 0.283 m at the armpit, 0.30 m at the waist, 0.344 × 0.26 m at the
pelvis, acromion 0.41 m wide so the guide's 0.46 m pauldron plate lands just
outside it. Every guide joint marker (shoulder, elbow, wrist, hip, knee,
ankle) is inside the body volume and every limb ring passes through its
marker; the markers themselves were not moved.

### Verification

* `analysis/basebody/check_body_*.png` — front, side, rear and three-quarter
  renders of the delivered body.
* `analysis/basebody/sheet_reference_overlay.png` — the body silhouette
  composited on the reference front/back/side at the reference's own mm/px
  calibration (anchored on the ground line, **not** rescaled to match the
  figure) — the proportion cross-check.
* `analysis/basebody/sheet_body_views.png`, `cl_*.png` — joint close-ups for
  shoulder, hip, knee, head, hand, foot.
* `analysis/verify/verify_base_body_report.txt` — **113 automated checks**
  (file scope, mesh quality, self-intersection, scale/origin/symmetry, guide
  proportions and joint alignment).

### Topology limitations to know before rigging

1. Elbows and knees are straight in the rest pose and there is no carrying
   angle on the arm chain. An IK rig wants a small forward offset on the
   elbow/knee bones, and the first bend may pinch on the inner side — there
   are three loops across each joint, which is the minimum. Add 1–2 more if a
   pose needs it.
2. There is **no clavicle topology**. The deltoid is part of the chest and
   deforms with it: fine for an FK arm, less good for a full shoulder rig.
3. Hands are **mitten blocks** (palm, knuckles, thumb): no finger or knuckle
   loops. Fingers are a separate, later decision.
4. The head is a cranium blank with no face/jaw/eye topology and the neck is
   short (Z 1.690–1.755). It exists to carry a helmet.
5. Vertex count is blockout density — enough for proportion and armour-fit
   checks, not for skin sliding.
6. The body is **bilaterally symmetric by construction**. The reference's
   asymmetric pose is recorded by the Prompt 2 empties `WSK_Guide_RefPose_*`
   and is deliberately not baked in; author any real asymmetry after this
   checkpoint.
7. Limbs attach by branch (5-sided) poles at the armpit and groin, and the
   crown/crotch/thumb/fingertip ends are triangle fans — normal for this
   construction, but they are the spots to watch if the mesh is ever
   subdivided hard.

## Reproducing

```bash
tools/setup_headless_blender.sh        # once: venv + bpy + generated GL stubs
tools/bl.sh tools/build_proportions.py        # writes checkpoint 2
tools/bl.sh tools/verify_proportions.py       # 62 checks + silhouette renders
tools/bl.sh tools/render_progress_checks.py   # orthographic progress renders
tools/bl.sh tools/make_proportion_diagram.py  # annotated diagrams
tools/bl.sh tools/build_base_body.py          # writes checkpoint 3
tools/bl.sh tools/verify_base_body.py         # 113 checks + views + overlays
```

This sandbox has no Blender install and no X11/OpenGL/EGL runtime, so Blender is
used as the official `bpy` Python module (4.5.0) with tiny generated stub
libraries standing in for the missing GL/X11 sonames. Headless scene editing,
the Python API and Cycles CPU rendering all work that way; EEVEE and any OpenGL
viewport feature do not, which is why every render here uses Cycles on CPU.

## Repository layout

```
reference/                 the supplied reference images (inputs)
analysis/                  measurements, diagrams, verification (outputs)
analysis/basebody/         Prompt 3 body renders, joint close-ups, overlays
tools/                     build, verification and measurement scripts
tools/bl.sh                run a script with the headless Blender
tools/build_proportions.py checkpoint 2: proportion sheet + blockout
tools/build_base_body.py   checkpoint 3: the base body
tools/verify_proportions.py / verify_base_body.py   the two check suites
Wildshift_Knight_0*.blend  checkpoints
setup_blend.py             checkpoint 1 script
```
