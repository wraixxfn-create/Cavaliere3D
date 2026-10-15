"""Colour-based landmark probe.

The armour, hood and cloth all read warm (R > B); the sky, the moon glow and
most of the background architecture read cool or neutral. That difference is
used to find the top of the helmet/hood and the bottom of the sabatons, which
is what the whole 2 m calibration hangs on.

Prints, per row, the count of warm-dark pixels in a given x band.
"""
import os
import sys

import numpy as np
from PIL import Image

ROOT = "/home/user/Cavaliere3D"
VIEWS = {
    "front": ("reference/ref_front.png", 0.40, 0.60),
    "back": ("reference/ref_back.png", 0.40, 0.60),
    "side": ("reference/ref_side.png", 0.30, 0.60),
}


def main():
    for name, (rel, x0f, x1f) in VIEWS.items():
        a = np.asarray(Image.open(os.path.join(ROOT, rel)).convert("RGB")).astype(np.int16)
        H, W, _ = a.shape
        x0, x1 = int(x0f * W), int(x1f * W)
        band = a[:, x0:x1, :]
        R, G, B = band[..., 0], band[..., 1], band[..., 2]
        warm = (R - B > 10) & (G < R + 4)
        dark = (R + G + B) / 3.0 < 150
        score = (warm & dark).sum(axis=1)
        print(f"\n=== {name}  band x {x0f:.2f}-{x1f:.2f}  ({x1 - x0} px) ===")
        for pct in range(2, 100, 2):
            row = int(pct / 100 * H)
            s = score[row - 3:row + 4].max()      # small vertical window
            bar = "#" * min(60, int(s))
            print(f"  {pct:5.1f}%  {s:5d}  {bar}")


if __name__ == "__main__":
    main()
