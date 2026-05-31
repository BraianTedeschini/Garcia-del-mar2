#!/usr/bin/env python3
"""
optimize_assets.py — re-optimiza imágenes en frontend/assets/

Uso:
    python3 tools/optimize_assets.py

Convierte PNG sin transparencia a JPG, genera WebP responsive,
y deja PNG sólo donde hay alpha real (logo, fondo).
"""
import os
import sys
from PIL import Image

ASSETS = os.path.join(os.path.dirname(__file__), "..", "frontend", "assets")
ASSETS = os.path.abspath(ASSETS)

MAX_W = 1600
JPG_Q  = 82
WEBP_Q = 80

def has_real_alpha(img):
    if img.mode in ("RGBA", "LA"):
        # ¿realmente usa transparencia?
        alpha = img.getchannel("A")
        return alpha.getextrema() != (255, 255)
    if img.mode == "P":
        return "transparency" in img.info
    return False

def resize(img, max_w):
    if img.width <= max_w:
        return img
    new_h = int(img.height * max_w / img.width)
    return img.resize((max_w, new_h), Image.LANCZOS)

def main():
    if not os.path.isdir(ASSETS):
        print(f"No existe {ASSETS}", file=sys.stderr)
        sys.exit(1)

    total_in = total_out = 0
    for fn in sorted(os.listdir(ASSETS)):
        if not fn.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        path = os.path.join(ASSETS, fn)
        size_in = os.path.getsize(path)
        total_in += size_in
        try:
            img = Image.open(path)
        except Exception as exc:
            print(f"  ! No se pudo abrir {fn}: {exc}")
            continue

        base = os.path.splitext(fn)[0]
        keep_png = has_real_alpha(img)

        img2 = resize(img, MAX_W if not keep_png else min(800, MAX_W))

        # WebP siempre
        webp_path = os.path.join(ASSETS, base + ".webp")
        webp_img = img2 if img2.mode in ("RGB", "RGBA") else img2.convert("RGBA")
        webp_img.save(webp_path, "WEBP", quality=WEBP_Q, method=6)

        if keep_png:
            png_path = os.path.join(ASSETS, base + ".png")
            img2.save(png_path, "PNG", optimize=True)
            total_out += os.path.getsize(png_path)
        else:
            jpg_path = os.path.join(ASSETS, base + ".jpg")
            (img2 if img2.mode == "RGB" else img2.convert("RGB")).save(
                jpg_path, "JPEG", quality=JPG_Q, optimize=True, progressive=True
            )
            total_out += os.path.getsize(jpg_path)

        total_out += os.path.getsize(webp_path)
        print(f"  {fn:20} -> {base}.{'png' if keep_png else 'jpg'} + .webp")

    print(f"\nIN : {total_in/1024/1024:.2f} MB")
    print(f"OUT: {total_out/1024/1024:.2f} MB")

if __name__ == "__main__":
    main()
