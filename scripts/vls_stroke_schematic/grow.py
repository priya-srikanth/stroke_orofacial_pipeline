"""Area-matched footprint (Priya: the stroke-affected area is bigger than the outlined stroke because of atrophy,
so paint outward from the stroke core until it matches the striatal area lost).
  target  = contra striatum - surviving ipsi striatum (ipsi outline minus her stroke outline)
  domain  = her stroke outline + (anchored mirror of contra striatum - surviving ipsi), clipped to the mirrored
            contralesional hemisphere (the normal-brain frame); if that is smaller than the target, the rest of the
            lesioned hemisphere within that frame
  order   = anisotropic distance from the stroke outline: lateral cheapest, then dorsal; medial and ventral costly
"""
import numpy as np
from scipy import ndimage as ndi
from skimage import morphology, measure
# Priya 10-21: a shell around the core that extends mostly DORSOLATERALLY (up-left diagonal and leftward), only a
# touch ventrally. Direction-dependent cost: weight 1 at THETA0 (between left and up-left), ~1.8 dorsal,
# ~2.7 ventral, ~3.4 medial.
THETA0, SPREAD = np.deg2rad(157.5), 1.25

def aniso_cost(seed, ds=3):
    s = seed[::ds, ::ds]
    b = s & ~ndi.binary_erosion(s)
    by, bx = np.nonzero(b)
    if len(by) > 600:
        k = np.linspace(0, len(by) - 1, 600).astype(int); by, bx = by[k], bx[k]
    H, W = s.shape; yy, xx = np.mgrid[0:H, 0:W]
    best = np.full((H, W), np.inf, np.float32)
    for i in range(0, len(by), 50):
        dx = xx[..., None] - bx[None, None, i:i + 50]; dy = yy[..., None] - by[None, None, i:i + 50]
        th = np.arctan2(-dy, dx)                        # image y is down; th measured with up positive
        w = 1 + SPREAD * (1 - np.cos(th - THETA0))      # cheapest toward lateral / dorsolateral
        c = (np.hypot(dx, dy) * w).min(-1)
        best = np.minimum(best, c)
    best[s] = 0
    full = np.repeat(np.repeat(best, ds, 0), ds, 1)[:seed.shape[0], :seed.shape[1]]
    return full

def grow(seed, domain, fallback, target_px, off_domain_penalty=0.0):
    """Take the cheapest pixels (aniso distance from the stroke outline; +penalty outside the absent-territory
    domain) until the cleaned, seed-connected blob reaches the target area."""
    cost = aniso_cost(seed) + np.where(domain, 0, off_domain_penalty)
    allowed = (domain | fallback) & ~seed
    idx = np.flatnonzero(allowed.ravel()); idx = idx[np.argsort(cost.ravel()[idx])]
    need = max(int(target_px - seed.sum()), 0); fp = seed
    for _ in range(8):
        fp = seed.copy(); fp.ravel()[idx[:need]] = True
        fp = morphology.closing(fp, morphology.disk(4)); fp = morphology.opening(fp, morphology.disk(3))
        fp = ndi.binary_fill_holes(fp | seed)
        lab = measure.label(fp); keep = np.unique(lab[seed & (lab > 0)])
        fp = np.isin(lab, keep) if len(keep) else fp
        if fp.sum() >= 0.97 * target_px or need >= len(idx):
            break
        need = int(need + (target_px - fp.sum()) * 1.1)
    return fp
