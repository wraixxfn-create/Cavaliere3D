"""Prompt 11 - read the sun-like waist motif off the supplied reference views.

The reference shows one circular sun motif twice: on the front tabard panel and
on the back cape.  This probe measures the front copy, which is the legible one
(the back copy sits in shadow behind the cape chains), and prints its parts in
millimetres using Prompt 2's calibration (the front view's body height spans
7.5 % to 88.7 % of the image height and is 2.00 m tall, so 1.9049 mm/px).

How it measures
---------------
The panel around the motif is nearly as dark as the motif itself, so the centre
is not found by dark-pixel centroid.  Instead a small search over centre and
radius finds the circle that best explains the bronze bezel:

    score = gold fraction on the bezel annulus
            - 0.9 x dark fraction inside it - 0.3 x gold fraction inside it

`gold` is the classic warm-metal test (R-B > 18, R > 55, R > G).  With the
centre and bezel fixed, the parts are read as radial profiles:

    core radius    the last radius whose ring is more than 55 % dark
    bezel          the gold peak and the radii where the gold fraction is high
    ray tips       the outermost radius that still carries gold spokes
    ray count      gold clusters on a circle just outside the bezel

Run: .venv/bin/python tools/medallion_reference_probe.py
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = "/home/user/Cavaliere3D"
OUT = os.path.join(ROOT, "analysis/medallion")
REPORT = os.path.join(ROOT, "analysis/verify/medallion_reference_probe.txt")
FRONT = os.path.join(ROOT, "reference/ref_front.png")
BACK = os.path.join(ROOT, "reference/ref_back.png")

# Prompt 2 calibration: helmet dome to ground contact, in image-height fractions.
FRONT_FRAME = dict(y_top=0.075, y_ground=0.887, height=2.00)
BACK_FRAME = dict(y_top=0.080, y_ground=0.887, height=2.00)

GOLD = dict(rb=18.0, r=55.0, rg=3.0)
BEZEL_R, CORE_R, TIP_R = 35.0, 24.2, 48.0   # checkpoint 11's own numbers
DARK_LUM = 19.0

lines = []


def say(text=""):
    lines.append(text)
    print(text)


def font(size, bold=False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else "")
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default(size=size)


def masks(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    gold = (r - b > GOLD["rb"]) & (r > GOLD["r"]) & (r - g > GOLD["rg"])
    return gold, rgb.mean(axis=2) < DARK_LUM


def fit_bezel(gold, dark, cx0, cy0, r_lo, r_hi, win=12.0):
    """Search centre and bezel radius for the circle that best explains a ring."""
    best = None
    for cy in np.arange(cy0 - win, cy0 + win + 0.5, 1.0):
        for cx in np.arange(cx0 - win, cx0 + win + 0.5, 1.0):
            y0, y1, x0, x1 = int(cy - r_hi - 4), int(cy + r_hi + 5), int(cx - r_hi - 4), int(cx + r_hi + 5)
            if y0 < 0 or x0 < 0 or y1 >= gold.shape[0] or x1 >= gold.shape[1]:
                continue
            yy, xx = np.mgrid[y0:y1, x0:x1]
            d = np.hypot(xx - cx, yy - cy)
            G, D = gold[y0:y1, x0:x1], dark[y0:y1, x0:x1]
            for rr in np.arange(r_lo, r_hi + 0.01, 0.5):
                band = (d >= rr - 1.5) & (d < rr + 1.5)
                inside = d < rr - 3.0
                if band.sum() < 12 or inside.sum() < 12:
                    continue
                score = G[band].mean() - 0.9 * D[inside].mean() - 0.3 * G[inside].mean()
                if best is None or score > best[0]:
                    best = (score, cx, cy, rr, G[band].mean(), D[inside].mean())
    return dict(score=best[0], cx=best[1], cy=best[2], r=best[3],
                gold_band=best[4], dark_inside=best[5])


def profile(gold, dark, cx, cy, rmax):
    y0, y1 = int(cy - rmax - 3), int(cy + rmax + 4)
    x0, x1 = int(cx - rmax - 3), int(cx + rmax + 4)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    d = np.hypot(xx - cx, yy - cy)
    G, D = gold[y0:y1, x0:x1], dark[y0:y1, x0:x1]
    rows = []
    for r in np.arange(2.0, rmax + 0.25, 0.5):
        band = (d >= r - 0.75) & (d < r + 0.75)
        if band.sum() < 6:
            continue
        rows.append((r, G[band].mean(), D[band].mean()))
    return rows, (yy - cy, xx - cx, G, D, d)


def clusters(ang, hit, tol_deg=2.0):
    o = np.argsort(ang)
    a, h = ang[o], hit[o].astype(int)
    runs = int(np.sum(h[1:] > h[:-1])) + int(h[0] == 1)
    spans, start = [], None
    for i, flag in enumerate(h):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            spans.append((a[start], a[i - 1]))
            start = None
    if start is not None:
        spans.append((a[start], a[-1]))
    if len(spans) > 1 and spans[0][0] < -np.pi + 0.3 and spans[-1][1] > np.pi - 0.3:
        first, last = spans.pop(0), spans.pop(-1)
        spans.append((first[0] + 2 * np.pi, last[1]))
    return runs, spans


def measure(path, frame, guess, name, r_lo=12.0, r_hi=26.0, rmax=46.0):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    rgb = np.asarray(im).astype(float)
    mm = frame["height"] * 1000.0 / ((frame["y_ground"] - frame["y_top"]) * h)
    gold, dark = masks(rgb)
    fit = fit_bezel(gold, dark, guess[0] * w, guess[1] * h, r_lo, r_hi)
    rows, (dy, dx, G, D, d) = profile(gold, dark, fit["cx"], fit["cy"], rmax)

    core_r = max([r for r, _g, dd in rows if dd > 0.55] or [0.0])
    ring_peak = max(rows, key=lambda t: t[1])
    peak_r = ring_peak[0]
    # bezel outer edge: last radius (beyond the peak) still at half the peak height
    outer = max([r for r, g, _d in rows if r >= peak_r and g > ring_peak[1] * 0.45] or [peak_r])
    inner = min([r for r, g, _d in rows if r <= peak_r and g > ring_peak[1] * 0.45] or [peak_r])
    tail = [r for r, g, _x in rows if r > peak_r + 1.5 and g > 0.035]
    ray_r = max(tail) if tail else 0.0
    # Ray reach is not the same in every direction: the tabard's blades run long
    # up and down the panel and short across it.  Measure the reach in 8 sectors.
    sectors = []
    ang_all = np.arctan2(dy, dx)
    for k in range(8):
        a0 = -np.pi + k * np.pi / 4.0
        sel = (ang_all >= a0) & (ang_all < a0 + np.pi / 4.0) & (d > peak_r + 1.5) & (d < rmax)
        if sel.sum() < 8:
            sectors.append(0.0)
            continue
        dk = d[sel]
        gk = G[sel]
        bins = np.arange(peak_r + 1.5, rmax, 0.5)
        reach = 0.0
        for r in bins:
            m = (dk >= r - 0.75) & (dk < r + 0.75)
            if m.sum() and gk[m].mean() > 0.035:
                reach = r
        sectors.append(reach)
    vert = max(sectors[1], sectors[2], sectors[5], sectors[6])
    horiz = max(sectors[0], sectors[3], sectors[4], sectors[7])
    # count spokes in three bands outside the bezel and report the median
    counts = []
    for r in (peak_r + 3, peak_r + 5, peak_r + 7):
        band = (d >= r - 0.8) & (d < r + 0.8)
        if band.sum() < 16:
            continue
        ang = np.arctan2(dy[band], dx[band])
        counts.append(clusters(ang, G[band])[0])
    n_rays = sorted(counts)[len(counts) // 2] if counts else 0

    say(f"--- {name}  ({os.path.basename(path)}, {w}x{h} px, {mm:.4f} mm/px)")
    say(f"    bezel fit       score {fit['score']:.3f} at centre ({fit['cx']:.1f}, {fit['cy']:.1f})"
        f" = x {fit['cx'] / w * 100:.1f} %, y {fit['cy'] / h * 100:.1f} % of the image")
    say(f"                    gold on the ring {fit['gold_band']:.2f},"
        f" dark inside {fit['dark_inside']:.2f}")
    say(f"    core radius     {core_r:5.1f} px = {core_r * mm:5.1f} mm"
        f"   (dark fraction drops below 0.55)")
    say(f"    bezel           {inner:5.1f}-{outer:.1f} px = {inner * mm:5.1f}-{outer * mm:.1f} mm"
        f"  (peak {ring_peak[1]:.2f} gold at {peak_r:.1f} px)")
    say(f"    ray tips        {ray_r:5.1f} px = {ray_r * mm:5.1f} mm"
        f"   (gold spokes still present)")
    say(f"    ray reach by sector (mm): "
        + ", ".join(f"{s * mm:.0f}" for s in sectors))
    say(f"                    top/bottom {vert * mm:.0f} mm vs left/right {horiz * mm:.0f} mm"
        f"  = {vert / max(horiz, 1e-9):.2f} x")
    say("                    the blades are hand-drawn embroidery, so their reach is uneven")
    say("                    all round; checkpoint 11 replaces that with three evenly graded")
    say("                    tiers, which is what makes an ornament read as designed")
    say(f"    spokes outside the bezel: {n_rays}"
        + (f"  (band counts {counts})" if counts else ""))
    say(f"    ratios          core/bezel {core_r / outer:.2f},"
        f" tips/bezel {ray_r / outer:.2f} (vertical)")
    out = annotate(path, (int(fit["cx"] - 62), int(fit["cy"] - 62),
                          int(fit["cx"] + 62), int(fit["cy"] + 62)),
                   fit["cx"], fit["cy"], core_r, inner, peak_r, outer, ray_r, name)
    say(f"    annotated crop -> {os.path.relpath(out, ROOT)}")
    return dict(core=core_r, inner=inner, peak=peak_r, outer=outer, ray=ray_r,
                rays=n_rays, mm=mm, sectors=sectors, vert=vert, horiz=horiz)


def annotate(path, box, cx, cy, core_r, inner, peak_r, outer, ray_r, title, scale=4):
    im = Image.open(path).convert("RGB")
    crop = im.crop(box).resize(((box[2] - box[0]) * scale, (box[3] - box[1]) * scale),
                               Image.LANCZOS)
    d = ImageDraw.Draw(crop)
    ox, oy = (cx - box[0]) * scale, (cy - box[1]) * scale
    for k, (r, colour, label) in enumerate(((core_r, (0, 220, 255), "core"),
                                            (inner, (120, 255, 120), "bezel inner"),
                                            (peak_r, (255, 90, 90), "bezel peak"),
                                            (outer, (255, 160, 60), "bezel outer"),
                                            (ray_r, (255, 230, 60), "ray tips"))):
        d.ellipse([ox - r * scale, oy - r * scale, ox + r * scale, oy + r * scale],
                  outline=colour, width=2)
        d.text((ox + r * scale + 4, oy - 42 + k * 19), label, font=font(13, True), fill=colour)
    d.line([ox - 6, oy, ox + 6, oy], fill=(0, 255, 0), width=2)
    d.line([ox, oy - 6, ox, oy + 6], fill=(0, 255, 0), width=2)
    d.rectangle([3, 3, 360, 22], fill=(20, 20, 24))
    d.text((8, 6), title, font=font(14, True), fill=(240, 240, 240))
    out = os.path.join(OUT, os.path.basename(path).replace(".png", "_motif.png"))
    crop.save(out)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    say("WILDSHIFT KNIGHT - REFERENCE READ OF THE SUN MOTIF (Prompt 11)")
    say("=" * 68)
    say("gold test: R-B > %.0f, R > %.0f, R > G;  dark test: luminance < %.0f"
        % (GOLD["rb"], GOLD["r"], DARK_LUM))
    say()
    front = measure(FRONT, FRONT_FRAME, (0.505, 0.559), "front tabard motif")
    say()
    back = measure(BACK, BACK_FRAME, (0.507, 0.358), "back cape motif (shadowed copy)")
    say()
    say("--- what that means at the waist (the numbers checkpoint 11 is built to)")
    mount_r = 43.0
    bezel = BEZEL_R         # chosen inside the mount radius so the mount rim stays visible
    core_ratio = front["core"] / front["outer"]
    tip_ratio = front["ray"] / front["outer"]
    say(f"    checkpoint-10 mount: radius {mount_r:.0f} mm, face at Y 0.1430,"
        f" belt band Z 1.005-1.105 (belt height 100 mm)")
    say(f"    reference motif:     core {front['core'] * front['mm']:.0f} mm,"
        f" bezel {front['inner'] * front['mm']:.0f}-{front['outer'] * front['mm']:.0f} mm,"
        f" rays to {front['ray'] * front['mm']:.0f} mm"
        f" ({front['ray'] * front['mm'] * 2:.0f} mm across), ~{front['rays']} spokes")
    say(f"    ratios to copy:      core = {core_ratio:.2f} x the bezel radius")
    say(f"    ratio NOT to copy:   blades = {tip_ratio:.2f} x the bezel radius, which at"
        f" this size is a")
    say(f"                         {tip_ratio * bezel * 2:.0f} mm emblem on a 100 mm belt")
    say(f"    checkpoint 11:       bezel {bezel:.0f} mm ({bezel / mount_r:.2f} of the mount radius, so"
        f" the mount's rim stays visible),")
    say(f"                         core {CORE_R:.1f} mm ({CORE_R / bezel:.2f} x against the reference's"
        f" {core_ratio:.2f} x, kept to within")
    say(f"                         {(CORE_R / bezel - core_ratio):.0%} of it), blades out to 45.5-{TIP_R:.1f} mm")
    say(f"                         ({TIP_R / bezel:.2f} x the bezel instead of {tip_ratio:.2f} x, cropped), and 12")
    say("                         blades instead of ~20, so the ornament stays inside")
    say("                         the belt it is mounted on and reads as a deliberate")
    say("                         waist ornament rather than the tabard emblem.")
    report = REPORT
    os.makedirs(os.path.dirname(report), exist_ok=True)
    with open(report, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("WROTE", report)


if __name__ == "__main__":
    main()
