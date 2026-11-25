"""Review sheet: rows of (live | new) PDFs rasterised at the same scale (pypdfium2), with the page edge drawn.

Usage: python side_by_side.py <out.png> <dpi> <live.pdf> <new.pdf> [...pairs]   ('-' as live = none)
"""
import sys

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageDraw


def ras(p, dpi):
    im = pdfium.PdfDocument(p)[0].render(scale=dpi / 72).to_pil().convert("RGB")
    ImageDraw.Draw(im).rectangle([0, 0, im.width - 1, im.height - 1], outline=(0, 160, 255))
    return im


out, dpi, a = sys.argv[1], float(sys.argv[2]), sys.argv[3:]
rows = []
for live, new in zip(a[::2], a[1::2]):
    ims = ([ras(live, dpi)] if live != '-' else []) + [ras(new, dpi)]
    w = sum(i.width for i in ims) + 20 * len(ims); h = max(i.height for i in ims) + 10
    r = Image.new("RGB", (w, h), "white"); x = 0
    for i in ims:
        r.paste(i, (x, 5)); x += i.width + 20
    rows.append(r)
W = max(r.width for r in rows); H = sum(r.height for r in rows)
sheet = Image.new("RGB", (W, H), "white"); y = 0
for r in rows:
    sheet.paste(r, (0, y)); y += r.height
sheet.save(out)
print(out, sheet.size)
