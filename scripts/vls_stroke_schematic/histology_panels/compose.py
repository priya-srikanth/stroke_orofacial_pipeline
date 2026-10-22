"""Matched display for DAPI/GFAP/NeuN (Cy5/DARPP32 never read). Each channel is scaled against its own section's
tissue background (lo = 1st pct of tissue, ref = median; white = lo + K*(ref - lo)) so batches look alike and gliosis
keeps its contrast to background; the white point is raised if more than SAT of the tissue would clip (stops the
strongly glial PS49/PS50 sections saturating). Colours: NeuN red, GFAP green, DAPI blue. Lesion flipped to the left."""
import numpy as np
from scipy import ndimage as ndi
K = {'DAPI': 5.2, 'GFAP': 8.0, 'NeuN': 3.0}
LO = {'DAPI': 1, 'GFAP': 50, 'NeuN': 5}   # black point percentile of tissue: GFAP background sits at black (as in Priya's QuPath exports)
SAT = {'DAPI': 0.002, 'GFAP': 0.012, 'NeuN': 0.004}
def tissue(img, level):
    s = sum(img[i].astype(float) / max(np.percentile(img[i], 99), 1) for i in (0, 2))
    s = ndi.gaussian_filter(s, 2.0 * 2 ** (6 - level))
    b, t = np.percentile(s, 3), np.percentile(s, 97)
    m = ndi.binary_fill_holes(s > b + 0.12 * (t - b))
    lab, n = ndi.label(m)
    if n:
        sz = ndi.sum(m, lab, range(1, n + 1)); m = np.isin(lab, 1 + np.flatnonzero(sz > 0.01 * m.sum()))
    return m if m.sum() > 100 else np.ones_like(m)
def norm(ch, m, c):
    v = ch.astype(float); t = v[m]; lo = np.percentile(t, LO[c]); ref = max(np.median(t), lo + 1); ref = np.median(t) if LO[c] < 50 else lo + (np.percentile(t, 75) - lo)
    hi = max(lo + K[c] * (ref - lo), np.percentile(t, 100 * (1 - SAT[c])))
    return np.clip((v - lo) / max(hi - lo, 1e-6), 0, 1)
def rgb(img, flip=None, level=6, gfap=True):
    m = tissue(img, level); d, g, n = (norm(img[i], m, c) for i, c in enumerate(['DAPI', 'GFAP', 'NeuN']))
    if not gfap: g = g * 0
    if flip is None:
        W = g.shape[1]; hot = (norm(img[1], m, 'GFAP') > 0.5) & m
        flip = hot[:, W // 2:].sum() > hot[:, :W // 2].sum()
    out = np.stack([n, g, d], -1); out[~m] = 0
    out = (out * 255).astype(np.uint8)
    return (out[:, ::-1] if flip else out), flip
