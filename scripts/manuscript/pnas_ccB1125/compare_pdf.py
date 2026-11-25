"""Compare two matplotlib PDFs byte for content (CreationDate stripped) and, if they differ, by raster (pypdfium2).

Usage: python compare_pdf.py <a.pdf> <b.pdf> [...pairs]
"""
import re
import sys

import numpy as np


def strip(p):
    b = open(p, "rb").read()
    return re.sub(rb"/CreationDate \([^)]*\)", b"", b)


def raster(p, dpi=300):
    import pypdfium2 as pdfium
    return np.asarray(pdfium.PdfDocument(p)[0].render(scale=dpi / 72).to_pil().convert("RGB"), dtype=int)


def compare(a, b):
    if strip(a) == strip(b):
        return "identical (bytes, CreationDate stripped)"
    ra, rb = raster(a), raster(b)
    if ra.shape != rb.shape:
        return f"DIFFER: raster shape {ra.shape} vs {rb.shape}"
    d = np.abs(ra - rb).max(axis=2)
    return f"bytes differ; raster 300 dpi: {int((d > 0).sum())} px differ, max {int(d.max())}"


if __name__ == "__main__":
    args = sys.argv[1:]
    for a, b in zip(args[::2], args[1::2]):
        print(a.split("/")[-1], "|", compare(a, b))
