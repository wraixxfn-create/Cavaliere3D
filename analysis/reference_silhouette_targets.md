# Reference silhouette targets - Prompt 6

Derived from the raw percentage readings in
`analysis/reference_measurements.md` with **one** consistent calibration.

## Why the numbers in that document were re-derived

`analysis/reference_measurements.md` anchors the body height at
2.00 m = 81.2 % of 1293 px = 1050 px, i.e. **1.905 mm/px**, but converts
its width readings with "1 % of image width = 13.7 mm", i.e.
**1.615 mm/px**.  Those two scales disagree by 17.9 %, so every width in
that document is about 15 % short of the figure it describes.  The metres
column and the mm/px column cannot both be right.

The Prompt 3 verification (`tools/verify_base_body.py`) composites the body
on the reference using `m_per_px = 2.0 / body_px` = **1.905 mm/px**, so the
overlay that every checkpoint was checked against already used the larger
scale.  Prompt 6 therefore re-derives every width with 1.905 mm/px and
square pixels.

Width / height **ratios** are calibration free, and they are the safest
readings:

| feature | raw reading | / body height | metres at 2.00 m | document said |
|---|---|---|---|---|
| crown spike tips (top) | y 2.2 % | 1.066 | 2.131 m | 2.11 |
| crown ring outer span | x 40.0 - 60.5 % | 0.166 | 0.331 m | 0.28 |
| helmet / hood width | x 44.5 - 58.0 % | 0.109 | 0.218 m | 0.19 |
| shoulder line (pauldron top edge) | y 17.9 % | 0.872 | 1.744 m | 1.6675 |
| pauldron plate outer edges | x 33.0 - 67.0 % | 0.275 | 0.549 m | 0.46 |
| spiked shoulder extent, front | x 30.5 - 69.5 % | 0.315 | 0.630 m | 0.52 - 0.54 |
| spiked shoulder extent, rear | x 30.0 - 74.0 % | 0.358 | 0.715 m | 0.61 |
| breastplate outer edges | x 42.0 - 58.0 % | 0.129 | 0.259 m | 0.22 |
| waist / cinched armour | x 43.0 - 57.0 % | 0.113 | 0.226 m | 0.19 |
| tassets / hip plates | x 40.0 - 60.0 % | 0.162 | 0.324 m | 0.27 |
| foot centres (stance) | x 29.5-37.5 / 60-70 % | 0.255 | 0.510 m | 0.47 |
| sabaton width | x 8.0 % | 0.065 | 0.129 m | (not given) |
| cape widest, solid cloth | x 21.0 - 79.0 % | 0.469 | 0.938 m | 1.10 |

Body height per view: front 81.2 % of 1293 px, rear 80.7 % of 1290 px,
side 83.3 % of 1278 px.  Readings are +/- 5 % at best and +/- 10 % from
the side view.

## Approved targets used by checkpoint 6

| feature | model | target | note |
|---|---|---|---|
| pauldron plate span | 0.530 m | 0.549 m | |
| spiked shoulder span | 0.637 m | 0.670 m | |
| helmet shell width | 0.195 m | 0.218 m | |
| crown halo outer span | 0.269 m | 0.331 m | |
| foot centre offset (stance / 2) | 0.236 m | 0.255 m | |
| shoulder line Z | 1.740 m | 1.744 m | |
| crown spike tips Z | 2.115 m | 2.131 m | |
| helmet dome top Z | 1.995 m | 2.000 m | |
| lowest armor point Z | -0.000 m | 0.000 m | |

## Measured silhouette profile of checkpoint 6

| Z | front width | X range | side depth | Y range |
|---|---|---|---|---|
| 2.10 | 0.003 m | -0.003 .. +0.000 | - | - |
| 2.05 | 0.163 m | -0.083 .. +0.080 | 0.018 m | -0.168 .. -0.150 |
| 2.00 | 0.297 m | -0.150 .. +0.147 | 0.270 m | -0.180 .. +0.090 |
| 1.95 | 0.258 m | -0.130 .. +0.128 | 0.268 m | -0.150 .. +0.118 |
| 1.90 | 0.263 m | -0.133 .. +0.130 | 0.280 m | -0.143 .. +0.138 |
| 1.80 | 0.182 m | -0.092 .. +0.090 | 0.265 m | -0.128 .. +0.138 |
| 1.74 | 0.627 m | -0.315 .. +0.312 | 0.148 m | -0.065 .. +0.083 |
| 1.70 | 0.587 m | -0.295 .. +0.292 | 0.200 m | -0.103 .. +0.098 |
| 1.60 | 0.522 m | -0.263 .. +0.260 | 0.302 m | -0.147 .. +0.155 |
| 1.50 | 0.637 m | -0.320 .. +0.318 | 0.297 m | -0.143 .. +0.155 |
| 1.40 | 0.712 m | -0.357 .. +0.355 | 0.275 m | -0.130 .. +0.145 |
| 1.30 | 0.742 m | -0.372 .. +0.370 | 0.253 m | -0.115 .. +0.138 |
| 1.20 | 0.735 m | -0.367 .. +0.367 | 0.245 m | -0.113 .. +0.133 |
| 1.10 | 0.712 m | -0.357 .. +0.355 | 0.247 m | -0.113 .. +0.135 |
| 1.00 | 0.688 m | -0.345 .. +0.343 | 0.230 m | -0.107 .. +0.122 |
| 0.90 | 0.643 m | -0.323 .. +0.320 | 0.210 m | -0.090 .. +0.120 |
| 0.80 | 0.603 m | -0.302 .. +0.300 | 0.220 m | -0.098 .. +0.122 |
| 0.70 | 0.427 m | -0.215 .. +0.212 | 0.205 m | -0.090 .. +0.115 |
| 0.60 | 0.445 m | -0.223 .. +0.223 | 0.188 m | -0.080 .. +0.107 |
| 0.50 | 0.473 m | -0.238 .. +0.235 | 0.173 m | -0.070 .. +0.103 |
| 0.40 | 0.492 m | -0.247 .. +0.245 | 0.165 m | -0.070 .. +0.095 |
| 0.30 | 0.512 m | -0.258 .. +0.255 | 0.150 m | -0.068 .. +0.083 |
| 0.20 | 0.528 m | -0.265 .. +0.263 | 0.135 m | -0.068 .. +0.068 |
| 0.10 | 0.538 m | -0.270 .. +0.268 | 0.133 m | -0.072 .. +0.060 |
| 0.02 | 0.627 m | -0.315 .. +0.312 | 0.275 m | -0.092 .. +0.182 |

## Known deviations kept on purpose

* **helmet width**: model 0.194 m, reference 0.218 m (-11 %).
* **crown halo span**: model 0.269 m, reference 0.331 m (-19 %).
* **stance between foot centres**: model 0.472 m, reference 0.510 m (-7 %).
* **sabaton width**: model 0.163 m, reference 0.129 m (+26 %).
* **chest depth front-to-back**: model 0.314 m, reference 0.368 m (-15 %).
* **foot length**: model 0.303 m, reference 0.220 m (+38 %).

The head width and crown span deviations come from Prompt 4, which sized
the helmet off the 0.172 m Prompt 3 skull.  They are left for the hood
step rather than fixed by rescaling the crown now.

