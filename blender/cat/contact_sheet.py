"""Compose PNGs into a contact sheet (system python3 + Pillow).
Usage: python3 blender/cat/contact_sheet.py out.jpg cols img1 img2 ..."""
import sys
from PIL import Image, ImageDraw
out, cols, files = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
ims = [Image.open(f).convert("RGB") for f in files]
w = max(i.width for i in ims); h = max(i.height for i in ims)
rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (w * cols, h * rows), (20, 20, 20))
for k, (im, f) in enumerate(zip(ims, files)):
    x, y = (k % cols) * w, (k // cols) * h
    sheet.paste(im, (x, y))
    ImageDraw.Draw(sheet).text((x + 6, y + 4), f.split("/")[-1], fill=(255, 255, 0))
sheet.save(out, quality=88)
print("sheet", out, sheet.size)
