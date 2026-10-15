"""Crop a normalised region of a reference view with a sparse 5% grid + 1% ticks.

Usage: python tools/crop_grid2.py <view> <x0> <x1> <y0> <y1> <out> [scale_px]
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

    ov = Image.new("RGBA", crop.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    cw, ch = crop.size
    for pct in range(0, 101):
        y = (pct / 100.0 * H - box[1]) * scale
        if -1 <= y <= ch + 1:
            if pct % 5 == 0:
                d.line([(0, y), (cw, y)], fill=(255, 0, 0, 200), width=1)
                d.text((3, y + 1), f"y{pct}", fill=(255, 255, 0, 255))
            else:
                d.line([(cw - 22, y), (cw, y)], fill=(0, 230, 255, 200), width=1)
    for pct in range(0, 101):
        x = (pct / 100.0 * W - box[0]) * scale
        if -1 <= x <= cw + 1:
            if pct % 5 == 0:
                d.line([(x, 0), (x, ch)], fill=(255, 0, 0, 200), width=1)
                d.text((x + 1, 2), f"{pct}", fill=(255, 255, 0, 255))
            else:
                d.line([(x, ch - 22), (x, ch)], fill=(0, 230, 255, 200), width=1)

    out_img = Image.alpha_composite(crop.convert("RGBA"), ov).convert("RGB")
    path = os.path.join(OUT, out)
    out_img.save(path)
    print("wrote", path, out_img.size, "source", W, "x", H, "box", box)


if __name__ == "__main__":
    main()
