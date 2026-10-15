"""Crop a normalised region of a reference view and overlay translucent gridlines.

Gridlines are labelled with their position as a percentage of the FULL image
height/width, so readings from different crops can be combined directly.

Usage: python tools/crop_grid.py <view> <x0> <x1> <y0> <y1> <out> [scale_px]
"""
import os
import sys

from PIL import Image, ImageDraw

ROOT = "/home/user/Cavaliere3D"
OUT = os.path.join(ROOT, "analysis")
VIEWS = {
    "front": "reference/ref_front.png",
    "back": "reference/ref_back.png",
    "side": "reference/ref_side.png",
    "threequarter": "reference/ref_threequarter.png",
}

MINOR = (0, 220, 255, 90)     # translucent cyan
MAJOR = (255, 60, 60, 170)    # translucent red
LABEL = (255, 255, 0, 255)
MINOR_STEP = 1


def main():
    view, x0, x1, y0, y1, out = sys.argv[1], *map(float, sys.argv[2:6]), sys.argv[6]
    target_w = int(sys.argv[7]) if len(sys.argv) > 7 else 1000

    im = Image.open(os.path.join(ROOT, VIEWS[view])).convert("RGB")
    W, H = im.size
    box = (int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))
    crop = im.crop(box)
    cw, ch = crop.size
    scale = target_w / cw
    crop = crop.resize((int(cw * scale), int(ch * scale)), Image.LANCZOS)

    overlay = Image.new("RGBA", crop.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cw, ch = crop.size

    for pct in range(0, 101, MINOR_STEP):
        y = (pct / 100.0 * H - box[1]) * scale
        if -1 <= y <= ch + 1:
            if pct % 5 == 0:
                draw.line([(0, y), (cw, y)], fill=MAJOR, width=1)
                draw.text((2, y + 1), f"{pct}", fill=LABEL)
            elif pct % 5 == 1:
                draw.line([(0, y), (cw, y)], fill=MINOR, width=1)
    for pct in range(0, 101, MINOR_STEP):
        x = (pct / 100.0 * W - box[0]) * scale
        if -1 <= x <= cw + 1:
            if pct % 5 == 0:
                draw.line([(x, 0), (x, ch)], fill=MAJOR, width=1)
                draw.text((x + 1, 1), f"{pct}", fill=LABEL)
            elif pct % 5 == 1:
                draw.line([(x, 0), (x, ch)], fill=MINOR, width=1)

    out_img = Image.alpha_composite(crop.convert("RGBA"), overlay).convert("RGB")
    path = os.path.join(OUT, out)
    out_img.save(path)
    print("wrote", path, out_img.size, "source", W, "x", H, "box", box)


if __name__ == "__main__":
    main()
