"""Cross-check the body-height calibration against the original 4-view sheet.

The standalone screenshots and the contact sheet are the same renders at
different sizes, so the *fractions* of image height for the head top and the
ground line must agree. If they do, the 2 m scale used for every measurement
is safe.
"""
import os

import numpy as np
from PIL import Image

ROOT = "/home/user/Cavaliere3D"

SHEET = "reference/ref_4view_grid_original.png"
STANDALONE = {
    "front": "reference/ref_front.png",
    "back": "reference/ref_back.png",
    "side": "reference/ref_side.png",
    "threequarter": "reference/ref_threequarter.png",
}
# panel bounds measured from the sheet's divider lines
PANELS = {
    "front": (4, 4, 638, 974),
    "back": (648, 4, 1279, 974),
    "side": (4, 978, 638, 1852),
    "threequarter": (648, 978, 1279, 1852),
}


def head_top_fraction(img, x0f=0.42, x1f=0.58):
    """Top of the warm, dark helmet/hood mass in the centre column band."""
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    H, W, _ = a.shape
    band = a[:, int(x0f * W):int(x1f * W), :]
    R, G, B = band[..., 0], band[..., 1], band[..., 2]
    warmish = (R - B > 4) | ((R + G + B) / 3.0 < 90)
    score = warmish.sum(axis=1)
    need = max(4, int(0.10 * band.shape[1]))
    rows = np.nonzero(score > need)[0]
    return rows[0] / H if len(rows) else float("nan")


def ground_fraction(img, x0f=0.3, x1f=0.7):
    """Lowest row that still contains the bright, structured sabaton/cloth mass.

    Uses brightness against the very dark wet floor instead of warmth, which
    the floor reflections also produce.
    """
    a = np.asarray(img.convert("L")).astype(np.float32) / 255.0
    H, W = a.shape
    dark = (a < 0.16)[:, int(x0f * W):int(x1f * W)]
    frac = dark.mean(axis=1)
    rows = np.nonzero(frac > 0.9)[0]
    # first row after the figure where the band goes almost fully dark and stays
    for r in rows:
        if r > 0.6 * H and frac[r:min(H, r + 30)].mean() > 0.9:
            return r / H
    return float("nan")


def main():
    sheet = Image.open(os.path.join(ROOT, SHEET))
    for name, box in PANELS.items():
        panel = sheet.crop(box)
        panel.save(os.path.join(ROOT, "analysis", f"panel_{name}.png"))
        ht = head_top_fraction(panel)
        print(f"sheet panel {name:13s} {panel.size}  head top y={ht*100:5.1f}%")

    for name, rel in STANDALONE.items():
        img = Image.open(os.path.join(ROOT, rel))
        ht = head_top_fraction(img)
        print(f"standalone {name:13s} {img.size}  head top y={ht*100:5.1f}%")


if __name__ == "__main__":
    main()
