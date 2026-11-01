"""Combine Blender preview renders (qa/out/street-props/<id>.png) into a labelled contact sheet.
python3 blender/props/contact_sheet.py [out.png] [id1,id2,...] [--cols N]"""
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QA = os.path.join(ROOT, "qa", "out", "street-props")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
out = args[0] if args else os.path.join(QA, "sheet.png")
ids = args[1].split(",") if len(args) > 1 else None
cols = int(sys.argv[sys.argv.index("--cols") + 1]) if "--cols" in sys.argv else 5
files = sorted(f for f in os.listdir(QA) if f.endswith(".png") and "sheet" not in f and "labels" not in f)
if ids:
    files = [f + ".png" for f in ids if os.path.exists(os.path.join(QA, f + ".png"))]
tw, th = 384, 288
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * tw, rows * (th + 18)), (40, 40, 40))
for i, f in enumerate(files):
    im = Image.open(os.path.join(QA, f)).convert("RGB")
    im.thumbnail((tw, th))
    x, y = (i % cols) * tw, (i // cols) * (th + 18)
    sheet.paste(im, (x, y))
    ImageDraw.Draw(sheet).text((x + 4, y + th + 3), f[:-4], fill=(240, 240, 240))
sheet.save(out)
print("SHEET", out, len(files))
