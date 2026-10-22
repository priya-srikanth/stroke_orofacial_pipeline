"""Section px -> plate mm. mode 'ipsi' (Priya 10-21: place the stroke by striatal anatomy): the whole ipsi striatum
(surviving + stroke outline) registered onto the plate's left CPu; else the contra/midline transform."""
import numpy as np
from wfield_local.histology_map import fit as F
_orig = F.to_mm
def to_mm(x, y, rec):
    if rec.get('mode') == 'ipsi':
        s = F.UM / 1000
        return rec['tx'] + (np.asarray(x) - rec['cx0']) * rec['ikx'] * s, rec['ity'] + (np.asarray(y) - rec['cy0']) * rec['iky'] * s
    return _orig(x, y, rec)
F.to_mm = to_mm

_LX = {}
def latx(f, PL):
    """Atlas region lateral to the left CPu's lateral border (+0.05 mm), row by row: nothing is drawn past the
    corpus callosum / external capsule (Priya 10-21)."""
    if f not in _LX:
        from shapely.geometry import box
        from shapely.ops import unary_union
        from wfield_local.histology_map import plates as PLT
        R = PLT.raster(PL[f]); ppm = R['ppm']; c = R['cpu'].copy(); c[:, int(6 * ppm):] = False
        _LX[f] = unary_union([box(-7, r / ppm, np.nonzero(c[r])[0].min() / ppm - 6.05, (r + 1) / ppm)
                              for r in np.nonzero(c.any(1))[0]]).buffer(0.01)
    return _LX[f]
