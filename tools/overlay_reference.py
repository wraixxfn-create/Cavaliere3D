"""Overlay a rendered orthographic mannequin silhouette on the reference view.

This is the cross-check for "is the mannequin the right size and shape against
the picture?". The render is an orthographic projection of a 2 m figure; the
reference is a perspective render, so the overlay can only be trusted for
global height and for landmarks that sit near the camera's optical axis.

Calibration used (see analysis/reference_measurements.md):
  front: ground at y 88.7 %, helmet dome top at y 7.5 % of the image height
  back : ground at y 88.7 %, same body height
  side : ground at y 98.6 %, figure top at y 5.0 %
`--scale` shifts the overlay vertically before compositing; that is applied
automatically, the two points above define the mapping.

Usage: python tools/overlay_reference.py <front|back|side> [guides]
"""
import os
import sys

import numpy as np
from PIL import Image

ROOT = "/home/user/Cavaliere3D"
CALIB = {
    "front": ("reference/ref_front.png", 0.887, 0.075),
    "back": ("reference/ref_back.png", 0.887, 0.075),
    # side: the boot's toe tip is the lowest character contact (the floor pattern
    # continues below it), so the ground line sits at y 89.7 %, not 98.6 %
    "side": ("reference/ref_side.png", 0.897, 0.055),
}
SIL = {"front": "silhouette_front.png", "back": "silhouette_back.png",
       "side": "silhouette_side.png"}


def main():
    view = sys.argv[1]
    ref_rel, y_ground, y_top = CALIB[view]
    ref = Image.open(os.path.join(ROOT, ref_rel)).convert("RGB")
    sil = Image.open(os.path.join(ROOT, "analysis/verify", SIL[view])).convert("RGBA")
    print("reference", ref.size, "silhouette", sil.size)

    W, H = ref.size
    ground_px = y_ground * H
    top_px = y_top * H
    body_px_ref = ground_px - top_px            # reference body height in px
    m_per_px = 2.0 / body_px_ref

    # the orthographic silhouette frame: find its own body height in px
    a = np.asarray(sil)[..., 3] > 0.5
    ys = np.nonzero(a.any(axis=1))[0]
    sil_h = ys.max() - ys.min() + 1
    target_h = body_px_ref
    scale = target_h / sil_h
    new = sil.resize((max(1, int(sil.width * scale)), max(1, int(sil_h * scale))),
                     Image.LANCZOS)

    # place the silhouette so that its top row lands on the reference's helmet top
    canvas = Image.new("RGBA", ref.size, (0, 0, 0, 0))
    cx = int(W * 0.5)
    canvas.paste(new, (cx - new.width // 2, int(round(top_px))), new)

    arr = np.asarray(canvas).astype(np.float32)
    mask = arr[..., 3] > 0.4

    base = np.asarray(ref).astype(np.float32)
    # ghost the reference, then draw the mannequin silhouette in cyan
    ghost = 255.0 - (255.0 - base) * 0.55
    cyan = np.zeros_like(ghost)
    cyan[..., 0] = 20
    cyan[..., 1] = 235
    cyan[..., 2] = 255
    out = np.where(mask[..., None], ghost * 0.35 + cyan * 0.65, ghost)
    out = np.clip(out, 0, 255).astype(np.uint8)

    # ground line + 1 m tick, drawn on the composite for reading
    img = Image.fromarray(out)
    p = np.asarray(img).copy()
    gy = int(round(ground_px))
    p[gy - 1:gy + 2, :, 0] = 255
    p[gy - 1:gy + 2, :, 1] = 0
    p[gy - 1:gy + 2, :, 2] = 0
    for metres in (0.5, 1.0, 1.5, 2.0):
        y = int(round(ground_px - metres / m_per_px))
        p[y, 0:40, :] = [255, 255, 0]
        p[y, W - 40:W, :] = [255, 255, 0]
    img = Image.fromarray(p)

    path = os.path.join(ROOT, "analysis", f"overlay_{view}.png")
    img.save(path)
    print(f"wrote {path}  body {body_px_ref:.0f} px, {m_per_px * 1000:.2f} mm/px, "
          f"silhouette scaled x{scale:.3f} -> {new.width}x{new.height}")


if __name__ == "__main__":
    main()
