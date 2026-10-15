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

## Reproducing

```bash
tools/setup_headless_blender.sh        # once: venv + bpy + generated GL stubs
tools/bl.sh tools/build_proportions.py        # writes checkpoint 2
tools/bl.sh tools/verify_proportions.py       # 62 checks + silhouette renders
tools/bl.sh tools/render_progress_checks.py   # orthographic progress renders
tools/bl.sh tools/make_proportion_diagram.py  # annotated diagrams
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
tools/                     build, verification and measurement scripts
tools/bl.sh                run a script with the headless Blender
Wildshift_Knight_0*.blend  checkpoints
setup_blend.py             checkpoint 1 script
```
