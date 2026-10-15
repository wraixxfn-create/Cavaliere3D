# Reference measurement log — Prompt 2

## Source images

Copied into `reference/` from the user's uploads.

| file | content | px |
|---|---|---|
| `ref_4view_grid_original.png` | contact sheet, 4 panels (2 × 2) | 1280 × 1856 |
| `ref_front.png` | front view | 849 × 1293 |
| `ref_back.png` | back view | 846 × 1290 |
| `ref_side.png` | side view (character facing image-left) | 931 × 1278 |
| `ref_threequarter.png` | three-quarter rear-left view | 930 × 1277 |

The contact sheet and the four screenshots are **the same renders at different
framings**, not five views of a turntable. The sheet's panels are cropped
differently from the standalone screenshots: the front panel of the sheet is
634 × 970 px versus 849 × 1293 px standalone, and its ground line is cut off.

## Tooling

* `tools/crop_grid.py`, `tools/crop_grid2.py` — crop a normalised region of a
  view and overlay translucent gridlines labelled as a percentage of the **full**
  image, so readings from different crops combine directly.
* `tools/silhouette_probe.py` — local standard deviation of luminance, used as a
  detail-energy silhouette detector to corroborate the visual readings.
* `tools/probe_landmarks.py` — warm-vs-cool colour probe, used to look for the
  helmet mass independently.
* `tools/calibrate_views.py` — attempts automatic per-image calibration; its
  automated detectors are **not** reliable on this material (see below), so the
  numbers actually used are the hand-read values in this document.

## Scale

Two landmarks per image: the top of the helmet dome (the highest point of the
**body**) and the ground contact under the feet. Crown spikes above the dome are
decoration and are excluded from the body height.

| view | helmet dome | ground contact | body height | mm/px |
|---|---|---|---|---|
| front | y 7.5 % | y 88.7 % | 81.2 % of 1293 px = 1050 px | 1.904 |
| back | y 8.0 % | y 88.7 % | 80.7 % of 1290 px = 1041 px | 1.921 |
| side | y 6.4 % | y 89.7 % | 83.3 % of 1278 px = 1065 px | 1.878 |
| sheet, front panel | y 12.0 % | y 90.7 % | 78.7 % of 970 px = 763 px | 2.621 |

So for the standalone front view: 1 % of image height = 20.9 mm, 1 % of image
width = 13.7 mm; for the side view 1 % of height = 18.8 mm and 1 % of width =
17.5 mm.

**Cross-check.** The sheet's front panel and the standalone front render disagree
by 3 % on the body-height fraction (78.7 % vs 81.2 %). That is the floor on the
accuracy of this whole exercise.

**The head-top landmark is the weak link.** In the front view the hood/dome
crown sits at y ≈ 9.5–12 %, but a thin helmet spike continues up to y ≈ 8.5 %
and crown-ring spikes reach y ≈ 5 %. Reading y = 12 % instead of 7.5 % would
shorten every dimension below by 4.5 %. **All lengths in this document are
± 5 % unless stated otherwise, and ± 10 % for anything taken from the side.**

## Front view readings (x = % of image width, y = % of image height)

| feature | reading | metres |
|---|---|---|
| ground contact (soles) | y 88.7 % | Z = 0 |
| helmet dome top | y 7.5 % | Z = 2.00 |
| crown spike tips (top) | y 2.2 % | Z = 2.11 |
| crown ring (spiked halo) outer | x 40 … 60.5 %, y 7 … 15 % | 0.28 m span |
| helmet / hood width | x 44.5 … 58 % | 0.19 m |
| eyes | y 14 % | Z = 1.77 |
| chin / hood bottom | y 16.5 % | Z = 1.74 |
| shoulder line (pauldron top edge) | y 17.9 % | Z = 1.6675 |
| pauldron plate outer edges at Z 1.63 | x 33 … 67 % | 0.46 m |
| pauldron *spiked* extent at Z 1.35 | x 30.5 … 69.5 % | 0.52–0.54 m |
| at Z 1.60 the pauldrons merge into the cape | — | not measurable |
| breastplate outer edges | x 42 … 58 % | 0.22 m |
| waist / cinched armour | y 32 %, x 43 … 57 % | Z = 1.35, 0.19 m |
| tassets / hip plates | y 38 … 42 %, x 40 … 60 % | 0.27 m |
| sun emblem (front tabard) | x 50.5 %, y 53.5 % | Z = 0.83 |
| right hand (relaxed arm) | x 28 … 31 %, y 43 … 50 % | X ≈ 0.28, Z ≈ 0.88 |
| elbow (sword arm) | x 77 %, y 25 % | X ≈ 0.37, Z = 1.42 |
| wrist / gauntlet (sword grip) | x 80.5 %, y 30 % | X ≈ 0.42, Z = 1.32 |
| sword grip centre | y 30 % | Z = 1.30 |
| sword crossguard | y 34 %, x 72 … 86 % | Z = 1.24, span 0.19 m |
| sword axis | x 74 … 76 % | X ≈ 0.35 off centre |
| sword tip | y 88.5 % | Z ≈ 0 |
| cape widest (solid cloth) | x 21 … 79 % | 1.10 m, at Z ≈ 0.75 |
| cape widest (frayed tips) | x 8 … 92 % | 1.15 m |
| cape hem (solid cloth) | y 80 % | Z ≈ 0.19 |
| left sabaton | x 29.5 … 37.5 %, y 77 … 88 % | centre X ≈ 0.24 |
| right sabaton | x 60 … 70 %, y 77 … 88 % | centre X ≈ 0.20 |

## Back view readings

| feature | reading | metres |
|---|---|---|
| hood / helmet top | y 8.0 % | Z = 2.00 |
| crown ring + spikes | x 31 … 69 % | 0.52 m across |
| spiked pauldron extent | x 30 … 74 % | 0.61 m (wider than the front view) |
| sun emblem (back cape) | x 50.5 %, y ~34 % | Z ≈ 1.30 |
| sabaton | x 60 … 65 %, y 81 … 88.5 % | Z ≈ 0 … 0.15 |
| ground contact | y 88.7 % | Z = 0 |

The back view also shows the **cape centre chains** hanging from the shoulder
line to the sun emblem, and the sun emblem sitting about 0.7 m below the
shoulder line — useful for the Cape/Armor steps, not needed for proportions.

## Side view readings

+ 1 % of image height = 18.8 mm; the figure faces image-left, so image x
  increases toward the **back** of the character.

| feature | reading | metres |
|---|---|---|
| helmet dome top | y 6.4 % | Z = 2.00 |
| helmet beak / face front | x ~36 % | in front of the chest line |
| back of the pauldron | x 55 % | ≈ 0.15 m behind the torso centre |
| chest front | x 34 % | ≈ 0.18 m in front of the torso centre |
| boot: toe tip | x ~26 % | Y ≈ +0.17 |
| boot: heel | x ~40 % | Y ≈ −0.05 |
| cape rear extent (mid) | x 92 %, y 55 … 65 % | ≈ 0.72 m behind the torso centre |
| cape rear extent (hem) | x 88 %, y 75 % | ≈ 0.63 m |
| sabaton ground contact | y 89.7 % | Z = 0 |
| sword tip | ~y 89 % | Z ≈ 0 |
| sword pommel top | ~y 22 % | Z ≈ 1.40 |

The "ground" detector is confused by the ritual circle and the floor pattern,
which continue for another 9 % of the image below the boot. The boot toe tip at
y 89.7 % is the real contact.

## Corroborating probe

`tools/silhouette_probe.py` (detail-energy mask, 13 px window, threshold 45 % of
maximum) reports the figure band on the front view as y 12 % → x 43.8–75.3 %,
y 26 % → x 31.3–83.7 %, y 66 % → x 32.9–83.2 %, and finds nothing below y 68 %.
The lower half of the reference is genuinely low-contrast dark cloth over dark
floor, which is exactly why the body underneath has to be assumed rather than
measured.

The warm-colour probe (`tools/probe_landmarks.py`) puts the helmet mass top at
y 7.4 % of the front image, agreeing with the grid reading of 7.5 %.

## Ambiguities carried into the proportion sheet

1. **The views are not one consistent 3D object.** They are AI renders;
   crown spike counts, chain layout and tabard embroidery differ between views.
2. **No orthographic reference exists.** Every view is perspective with a low
   camera, so the upper body reads systematically large.
3. **The body under the armour is invisible.** Torso taper, waist, hips, knees
   and ankles are assumed standard 2 m human proportions, not measured.
4. **Shoulder width is a decision, not a measurement.** The only readable
   shoulder evidence is armour: 0.46 m of pauldron plate at Z 1.63 and 0.52–0.54 m
   of spikes at Z 1.35. The mannequin's body shoulder width was set to 0.46 m on
   that basis.
5. **Sword handedness is inconsistent.** Front, side and three-quarter views put
   the sword on the image-right (character's *left* hand). The back view also
   puts it on the image-right, which for a back view means the character's
   *right* hand — so the back view is mirrored relative to the others. The front
   view was treated as authoritative: **sword in the LEFT hand.**
6. **Feet.** The side view suggests a short foot (0.15–0.25 m); armoured sabatons
   on a 2 m figure should be ≈ 0.30 m, so 0.30 m was used, marked *assumed*.
7. **Arm pose.** The reference pose is asymmetric (left arm raised, elbow bent,
   gripping the sword; right arm hanging at about 18°). This is pose, not
   proportion, so the mannequin is built in a mirrored neutral A-pose and the
   reference pose is recorded with the `WSK_Guide_RefPose_*` empties.
8. **Back-view widths disagree with the front.** The spiked pauldrons read
   0.52 m in the front view and 0.61 m in the back view. Front was used.
