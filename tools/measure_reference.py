"""Overlay measurement grids on the reference views and probe silhouette extents.

Outputs go to analysis/. This is a measurement aid only: the reference is a set of
AI renders with perspective and inconsistent detail, so numbers are read visually
off the grid and cross-checked against a rough silhouette probe.
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = "/home/user/Cavaliere3D"
OUT = os.path.join(ROOT, "analysis")
os.makedirs(OUT, exist_ok=True)

VIEWS = {
    "front": "reference/ref_front.png",
    "back": "reference/ref_back.png",
    "side": "reference/ref_side.png",
    "threequarter": "reference/ref_threequarter.png",
}


def grid_overlay(name, rel_path, max_dim=1100, step=0.05):
    im = Image.open(os.path.join(ROOT, rel_path)).convert("RGB")
    w, h = im.size
    scale = max_dim / max(w, h)
    if scale < 1:
        im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    w, h = im.size
    draw = ImageDraw.Draw(im)

    label_x = int(w * 0.005)
    for i in range(1, int(1 / step)):
        frac = i * step
        y = int(round(frac * h))
        major = abs(frac * 100 - round(frac * 100 / 10) * 10) < 1e-6
        colour = (255, 60, 60) if major else (0, 200, 255)
        draw.line([(0, y), (w, y)], fill=colour, width=2 if major else 1)
        if major or abs(frac * 100 - round(frac * 100 / 5) * 5) < 1e-6:
            draw.text((label_x, y - 12), f"{frac*100:.0f}%", fill=(255, 255, 0))
    # vertical 5% lines
    for i in range(1, int(1 / step)):
        frac = i * step
        x = int(round(frac * w))
        major = abs(frac * 100 - round(frac * 100 / 10) * 10) < 1e-6
        draw.line([(x, 0), (x, h)], fill=(255, 60, 60) if major else (80, 220, 120),
                  width=2 if major else 1)
        if major:
            draw.text((x - 10, 4), f"{frac*100:.0f}%", fill=(255, 255, 0))
    out = os.path.join(OUT, f"grid_{name}.png")
    im.save(out)
    return out, (w, h)


def probe(name, rel_path):
    """Rough row/column probe: where is the silhouette darkest vs the sky?"""
    im = Image.open(os.path.join(ROOT, rel_path)).convert("RGB")
    a = np.asarray(im).astype(np.float32) / 255.0
    lum = a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722
    h, w = lum.shape
    print(f"\n=== {name} {w}x{h} ===")
    # column-wise mean luminance in the top 60% (sky region) to find figure darkness
    for r in range(0, h, max(1, h // 20)):
        row = lum[r]
        dark = row < 0.12
        print(f"  y={r:5d} ({r/h*100:5.1f}%)  dark_frac={dark.mean():.3f} "
              f"min={row.min():.3f} mean={row.mean():.3f}")
    cols = lum.mean(axis=0)
    print("  column luminance (10 samples):",
          " ".join(f"{c:.2f}" for c in cols[:: max(1, w // 10)][:10]))


if __name__ == "__main__":
    for name, rel in VIEWS.items():
        out, size = grid_overlay(name, rel)
        print("wrote", out, size)
    for name in ("front", "side"):
        probe(name, VIEWS[name])
