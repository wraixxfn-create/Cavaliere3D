"""Per-image calibration: where is the head top and the ground line?

Every supplied image is its own render with its own framing (the contact sheet's
panels are cropped differently from the standalone screenshots), so the 2 m
scale has to be re-derived image by image. This script reports, for each image:

  dome_y   - top of the helmet/hood mass          (warm + dark detector)
  ground_y - lowest contact of the figure         (structured-bright detector)
  implied body height in metres if the helmet dome is taken as exactly 2.00 m
  the resulting mm-per-pixel

The numbers feed `REFERENCE_VIEWS` in tools/build_proportions.py so the image
empties line up with the mannequin, and analysis/reference_measurements.md.
"""
import os

import numpy as np
from PIL import Image

ROOT = "/home/user/Cavaliere3D"

IMAGES = {
    "front": ("reference/ref_front.png", (0.40, 0.60), (0.28, 0.72)),
    "back": ("reference/ref_back.png", (0.40, 0.60), (0.28, 0.72)),
    "side": ("reference/ref_side.png", (0.35, 0.60), (0.25, 0.65)),
    "threequarter": ("reference/ref_threequarter.png", (0.35, 0.65), (0.25, 0.75)),
    "sheet_front": ("reference/ref_4view_grid_original.png", (0.40, 0.60), (0.30, 0.70)),
}

# 2 m is the provisional scale: the helmet dome top is the highest point of the
# body (the crown spikes above it are guide-only detail).


def load(rel, panel=None):
    img = Image.open(os.path.join(ROOT, rel)).convert("RGB")
    if panel:
        img = img.crop(panel)
    return img


def dome_row(img, xband):
    a = np.asarray(img).astype(np.int16)
    H, W, _ = a.shape
    band = a[:, int(xband[0] * W):int(xband[1] * W), :]
    R, G, B = band[..., 0], band[..., 1], band[..., 2]
    warm_dark = ((R - B) > 6) & (((R + G + B) / 3.0) < 120)
    score = warm_dark.sum(axis=1)
    need = max(5, int(0.12 * band.shape[1]))
    rows = np.nonzero(score > need)[0]
    return rows[0] / H if len(rows) else float("nan")


def ground_row(img, xband):
    """Lowest row where the figure still shows bright, structured detail.

    The wet floor below the feet is very dark and smooth; the sabatons and the
    cloth tips above it are brighter and textured, so the last row with a
    decent count of mid-bright pixels inside the figure band is the ground
    contact.
    """
    a = np.asarray(img.convert("L")).astype(np.float32) / 255.0
    H, W = a.shape
    band = a[:, int(xband[0] * W):int(xband[1] * W)]
    bright = ((band > 0.28) & (band < 0.85)).sum(axis=1)
    need = max(4, int(0.02 * band.shape[1]))
    rows = np.nonzero(bright > need)[0]
    rows = rows[rows > 0.6 * H]
    if not len(rows):
        return float("nan")
    # walk down while the figure is still present, allow short gaps
    last = rows[0]
    for r in rows:
        if r - last <= 0.03 * H:
            last = r
    return last / H


def main():
    print(f"{'view':14s} {'size':>11s} {'dome_y':>7s} {'ground_y':>9s} "
          f"{'body':>7s} {'mm/px':>7s} {'implied h':>10s}")
    for name, (rel, xb, gb) in IMAGES.items():
        img = load(rel)
        H = img.size[1]
        dom = dome_row(img, xb)
        grd = ground_row(img, gb)
        body_frac = grd - dom
        mm = 2.0 / (body_frac * H)
        print(f"{name:14s} {img.size[0]:5d}x{H:<5d} {dom*100:6.1f}% {grd*100:8.1f}% "
              f"{body_frac*100:6.1f}% {mm*1000:7.2f} {2.0:9.3f} m")


if __name__ == "__main__":
    main()
