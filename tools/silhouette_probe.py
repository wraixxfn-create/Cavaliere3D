"""Silhouette probe: use local high-frequency detail energy to separate the
detailed figure (armour, cloth, chains) from the smooth sky / ground.

Prints, for a set of rows expressed as a percentage of image height, the
left/right extent and total width of the figure band, in percent of image width.
These are measurement aids; the reference is an AI render with perspective and
the numbers are only used as corroboration for the visual grid readings.
"""
import os

import numpy as np
from PIL import Image

ROOT = "/home/user/Cavaliere3D"
VIEWS = {
    "front": "reference/ref_front.png",
    "back": "reference/ref_back.png",
    "side": "reference/ref_side.png",
}


def detail_map(path, win=9):
    im = Image.open(os.path.join(ROOT, path)).convert("L")
    a = np.asarray(im).astype(np.float32) / 255.0
    # local mean and local variance via box blur
    k = win
    pad = k // 2
    p = np.pad(a, pad, mode="edge")


def local_std(a, win=11):
    """Local standard deviation via uniform filter (integral-image style)."""
    pad = win // 2
    p = np.pad(a, pad, mode="reflect")
    c = np.cumsum(np.cumsum(p, axis=0), axis=1)
    c = np.pad(c, ((1, 0), (1, 0)))
    H, W = a.shape
    def boxsum(y0, x0):
        return (c[y0 + win, x0 + win] - c[y0, x0 + win] - c[y0 + win, x0] + c[y0, x0])
    ys = np.arange(H)[:, None]
    xs = np.arange(W)[None, :]
    S = boxsum(ys, xs)
    # second moment
    c2 = np.cumsum(np.cumsum(p * p, axis=0), axis=1)
    c2 = np.pad(c2, ((1, 0), (1, 0)))
    S2 = (c2[ys + win, xs + win] - c2[ys, xs + win] - c2[ys + win, xs] + c2[ys, xs])
    n = win * win
    m1 = S / n
    m2 = S2 / n
    var = np.clip(m2 - m1 * m1, 0, None)
    return np.sqrt(var)


def analyse(name, path, rows, thresh_frac=0.45):
    im = Image.open(os.path.join(ROOT, path)).convert("L")
    a = np.asarray(im).astype(np.float32) / 255.0
    sd = local_std(a, 13)
    H, W = sd.shape
    thr = sd.max() * thresh_frac
    mask = sd > thr
    print(f"\n=== {name}  {W}x{H}  thr={thr:.4f} (max sd {sd.max():.4f}) ===")
    for pct in rows:
        y = int(pct / 100 * H)
        row = mask[y]
        idx = np.nonzero(row)[0]
        if len(idx) < 3:
            print(f"  {pct:5.1f}%  (no band)")
            continue
        # widest contiguous-ish extent: 2nd..98th percentile of active columns
        lo = int(np.percentile(idx, 1))
        hi = int(np.percentile(idx, 99))
        # find largest gap to split body vs background clutter
        print(f"  {pct:5.1f}%  x=[{lo/W*100:5.1f}% .. {hi/W*100:5.1f}%]  "
              f"width={(hi-lo)/W*100:5.1f}%   active={row.mean()*100:4.1f}%")


if __name__ == "__main__":
    rows = list(range(2, 100, 2))
    for nm, p in VIEWS.items():
        analyse(nm, p, rows)
