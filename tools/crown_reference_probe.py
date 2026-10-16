"""Overlay a model-space metric grid on the reference head crops (Prompt 10).

Calibration taken from Prompt 4's `reference_sheet`: on `ref_front.png`,
chin y=282 px <-> z 1.736 m, centre x=429 px <-> x 0 m, 1.832 mm/px.
The back and three-quarter views reuse the same scale with their own centre.

Usage: .venv/bin/python tools/crown_reference_probe.py
"""
import os

from PIL import Image, ImageDraw

ROOT = "/home/user/Cavaliere3D"
OUT = os.path.join(ROOT, "analysis/crown")
MPP = 1.8323e-3          # metres per pixel on ref_front.png (Prompt 4 fit)
CHIN_Y = 282.0           # ref_front.png row of the chin, z = 1.736 m
CHIN_Z = 1.736
CX = 429.0               # ref_front.png column of the centre line

VIEWS = {
    "front": dict(file="ref_front.png", cx=CX, box=(310, 0, 560, 340)),
    "back": dict(file="ref_back.png", cx=420.0, box=(300, 0, 550, 340)),
    "side": dict(file="ref_side.png", cx=430.0, box=(300, 40, 570, 340)),
}


def z_of(y, chin_y=CHIN_Y, chin_z=CHIN_Z):
    return chin_z - (y - chin_y) * MPP


def y_of(z, chin_y=CHIN_Y, chin_z=CHIN_Z):
    return chin_y - (z - chin_z) / MPP


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, cfg in VIEWS.items():
        im = Image.open(os.path.join(ROOT, "reference", cfg["file"])).convert("RGB")
        box = cfg["box"]
        crop = im.crop(box)
        scale = 3.0
        crop = crop.resize((int(crop.width * scale), int(crop.height * scale)),
                           Image.LANCZOS)
        ov = Image.new("RGBA", crop.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)

        def px(x_m, z_m, cx=cfg["cx"]):
            return ((cx + x_m / MPP - box[0]) * scale,
                    (y_of(z_m) - box[1]) * scale)

        z = 1.70
        while z <= 2.50 + 1e-9:
            _, yy = px(0.0, z)
            if -2 <= yy <= crop.height + 2:
                major = abs(z * 20 - round(z * 20)) < 1e-6
                d.line([(0, yy), (crop.width, yy)],
                       fill=(255, 40, 40, 200) if major else (0, 220, 255, 120), width=1)
                if major:
                    d.text((3, yy + 1), f"z={z:.2f}", fill=(255, 255, 0, 255))
            z += 0.02
        x = -0.30
        while x <= 0.30 + 1e-9:
            xx, _ = px(x, 1.9)
            if -2 <= xx <= crop.width + 2:
                major = abs(x * 100 - round(x * 100)) < 1e-6 and abs(x * 20 - round(x * 20)) < 1e-6
                d.line([(xx, 0), (xx, crop.height)],
                       fill=(255, 40, 40, 200) if major else (0, 220, 255, 120), width=1)
                if major:
                    d.text((xx + 1, 2), f"{x:+.2f}", fill=(255, 255, 0, 255))
            x += 0.02
        out = Image.alpha_composite(crop.convert("RGBA"), ov).convert("RGB")
        path = os.path.join(OUT, f"ref_{name}_grid.png")
        out.save(path)
        print("wrote", path, out.size)


if __name__ == "__main__":
    main()
