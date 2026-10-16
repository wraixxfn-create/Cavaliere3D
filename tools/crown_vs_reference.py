"""Compare the Prompt-10 crown with the reference views at a matched metric scale.

Reference calibration (Prompt 4's fit, re-checked in `crown_reference_probe.py`):
`ref_front.png` chin row 282 px <-> Z 1.736 m, centre column 429 px <-> X 0,
1.8323 mm/px.  The same scale and framing are assumed for the back and side
views, with their own centre columns.  The renders are the Prompt-10 inspection
views (0.62 m orthographic height over 1000 px, centred on Z 1.94).

Run: .venv/bin/python tools/crown_vs_reference.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = "/home/user/Cavaliere3D"
OUT = os.path.join(ROOT, "analysis/crown/crown_vs_reference.png")
REF = os.path.join(ROOT, "reference")

MPP_REF = (1.998 - 1.736) / (282.0 - 139.0)     # 1.8323 mm/px
CHIN_Y, CHIN_Z = 282.0, 1.736
ORTHO, RES_H, VIEW_Z = 0.62, 1000, 1.94
MPP_RENDER = ORTHO / RES_H

JOBS = [
    ("ref_front.png", 429.0, 40.0, 200.0, "front", "FRONT"),
    ("ref_back.png", 420.0, 40.0, 200.0, "rear", "REAR"),
    ("ref_side.png", 430.0, 10.0, 200.0, "side_left", "SIDE (ref: rear-left oblique)"),
]
TILE_H = 430
TITLE_H = 28


def font(size, bold=False):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else "")
    try:
        return ImageFont.truetype(p, size)
    except OSError:
        return ImageFont.load_default(size=size)


def crop_reference(im, cx, z_top, z_bottom):
    y0 = int(round(CHIN_Y - (z_top - CHIN_Z) / MPP_REF))
    y1 = int(round(CHIN_Y - (z_bottom - CHIN_Z) / MPP_REF))
    return im.crop((0, y0, im.width, y1)), (y0, y1)


def crop_render(im, z_top, z_bottom):
    y0 = int(round(RES_H / 2.0 - (z_top - VIEW_Z) / MPP_RENDER))
    y1 = int(round(RES_H / 2.0 - (z_bottom - VIEW_Z) / MPP_RENDER))
    return im.crop((0, y0, im.width, y1))


def main():
    z_top, z_bottom = 2.24, 1.86
    tiles = []
    for fname, cx, _y, _h, view, title in JOBS:
        ref = Image.open(os.path.join(REF, fname)).convert("RGB")
        ref_crop, _rows = crop_reference(ref, cx, z_top, z_bottom)
        ours = Image.open(os.path.join(ROOT, "analysis/crown", f"p10_crown_{view}.png")).convert("RGB")
        ours_crop = crop_render(ours, z_top, z_bottom)
        # crop both to the head's width so the vertical scale is what is compared
        half_w_m = 0.22
        ref_half = int(round(half_w_m / MPP_REF))
        rcx = int(round(cx))
        ref_crop = ref_crop.crop((rcx - ref_half, 0, rcx + ref_half, ref_crop.height))
        ren_half = int(round(half_w_m / MPP_RENDER))
        rxc = ours_crop.width // 2
        ours_crop = ours_crop.crop((rxc - ren_half, 0, rxc + ren_half, ours_crop.height))
        tiles.append((title, ref_crop, ours_crop))

    tw = int(sum(t[1].width for t in tiles) / len(tiles))
    canvas = Image.new("RGB", (tw * len(tiles), (TILE_H + TITLE_H) * 2 + 80),
                       (235, 235, 238))
    d = ImageDraw.Draw(canvas)
    d.text((20, 12), "reference crown (top) vs checkpoint 10, same metric scale",
           font=font(26, True), fill=(25, 25, 28))
    d.text((20, 46), f"2.24 m down to 1.86 m, +/-0.22 m about the centre line; "
                     f"reference 1.832 mm/px, render 0.620 mm/px",
           font=font(17), fill=(70, 70, 78))
    y_ref = 76 + TITLE_H
    y_ours = y_ref + TILE_H + TITLE_H + 8
    for i, (title, ref, ours) in enumerate(tiles):
        x = i * tw
        d.text((x + 8, 78), title + "  -  reference", font=font(17, True), fill=(25, 25, 28))
        canvas.paste(ref.resize((tw, TILE_H), Image.LANCZOS), (x, y_ref))
        d.text((x + 8, y_ref + TILE_H + 6), "checkpoint 10", font=font(17, True),
               fill=(25, 25, 28))
        canvas.paste(ours.resize((tw, TILE_H), Image.LANCZOS), (x, y_ours))
    canvas.save(OUT)
    print("wrote", OUT, canvas.size)


if __name__ == "__main__":
    main()
