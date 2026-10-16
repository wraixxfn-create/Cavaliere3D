"""Extract the crown silhouette from the reference views in model coordinates.

Calibration: ref_front.png, chin y=282 px <-> z 1.736 m, centre x=429 px <-> 0,
1.8323 mm/px (Prompt 4's fit; it puts the hood top on 1.998 m, matching the
Prompt 6 note that the 2.00 m envelope belongs to the helmet).

Prints one line per 1 cm of height: the dark runs inside |x| < 0.26 m, in cm.

Usage: .venv/bin/python tools/crown_silhouette_read.py
"""
import os
import sys

import numpy as np
from PIL import Image

ROOT = "/home/user/Cavaliere3D"
MPP = 1.8323e-3
CHIN_Y = 282.0
CHIN_Z = 1.736
VIEWS = {
    "front": dict(file="ref_front.png", cx=429.0, thr=95.0),
    "back": dict(file="ref_back.png", cx=420.0, thr=95.0),
}


def read(view, thr, x_lim=0.26, z_lo=1.82, z_hi=2.32, step=0.01):
    cfg = VIEWS[view]
    a = np.asarray(Image.open(os.path.join(ROOT, "reference", cfg["file"]))
                   .convert("L")).astype(float)
    H, W = a.shape
    dark = a < thr
    print(f"== {view} ({cfg['file']} {W}x{H})  thr={thr}  centre x={cfg['cx']}")
    z = z_hi
    while z >= z_lo - 1e-9:
        y = int(round(CHIN_Y - (z - CHIN_Z) / MPP))
        if 0 <= y < H:
            row = dark[y]
            xs = np.where(row)[0]
            runs = []
            if len(xs):
                start = prev = xs[0]
                for x in xs[1:]:
                    if x != prev + 1:
                        runs.append((start, prev))
                        start = x
                    prev = x
                runs.append((start, prev))
            keep = []
            for r0, r1 in runs:
                a0 = (r0 - cfg["cx"]) * MPP
                a1 = (r1 - cfg["cx"]) * MPP
                if a0 > x_lim or a1 < -x_lim:
                    continue
                keep.append((max(a0, -x_lim), min(a1, x_lim)))
            bar = ""
            n = 52
            for k in range(n):
                x0 = -x_lim + (2 * x_lim) * k / n
                x1 = -x_lim + (2 * x_lim) * (k + 1) / n
                hit = any(not (b1 < x0 or b0 > x1) for b0, b1 in keep)
                bar += "#" if hit else "."
            txt = " ".join(f"{b0 * 100:+.1f}..{b1 * 100:+.1f}" for b0, b1 in keep[:6])
            print(f"  z={z:5.2f} |{bar}| {txt}")
        z -= step


if __name__ == "__main__":
    for v in (sys.argv[1:] or ["front", "back"]):
        read(v, VIEWS[v]["thr"])
        print()
