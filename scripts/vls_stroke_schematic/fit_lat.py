"""Placement v3 (Priya 10-21: strokes sat too medial; 'lateral stroke edge up against the lateral border of striatum';
'is this scaled correctly? looks much wider'). Scale = the contra-hemisphere fit (physical scale, never stretched to
fill the CPu); translation = align the LATERAL half of the ipsi striatal territory (surviving outline + stroke outline)
to the lateral border of the plate's left CPu."""
import sys, os, json, pickle, numpy as np
sys.path.insert(0, '/home/claude/widefield_pipeline')
from scipy import ndimage as ndi
from shapely.ops import unary_union
from wfield_local.histology_map import fit as F, plates as PLT
from wfield_local.histology_map.sections import rasterize
PL = PLT.load_plates('/mnt/user-data/uploads/Documents/data/Immuno/PS92-95_widefield_stroke_cohort/lesion_map_work/paxinos_p63-98.pdf')
D = pickle.load(open('prep4.pkl', 'rb')); FT = pickle.load(open('fit_priya.pkl', 'rb')); s = F.UM / 1000
out = pickle.load(open('fit_lat.pkl', 'rb')) if os.path.exists('fit_lat.pkl') and '--fresh' not in sys.argv else {}
for k in [a for a in sys.argv[1:] if not a.startswith('--')]:
    d = D[k]; T = d['T']; sh = T['tissue'].shape; b = FT[k]['best']; f = b['figure']; kx, ky = b['kx'], b['ky']
    G = unary_union([T['gi']] + ([d['gl']] if d['gl'] is not None else [])).buffer(3).buffer(-3)
    m = ndi.binary_fill_holes(rasterize(G, sh)); ey, ex = np.nonzero(F._edge(m)); cy0, cx0 = ey.mean(), ex.mean()
    lat = ex < cx0; ey, ex = ey[lat], ex[lat]                       # lateral half of the ipsi territory
    R = PLT.raster(PL[f]); ppm = R['ppm']; c = R['cpu'].copy(); c[:, int(6 * ppm):] = False
    E = F._edge(c); yy, xx = np.nonzero(c); ccx = xx.mean(); E[:, int(ccx):] = False   # lateral border only
    dc = ndi.distance_transform_edt(~E); ccy, ccxm = yy.mean() / ppm, ccx / ppm - 6
    def score(tx, ty):
        q = ((ex - cx0) * kx * s + tx + 6) * ppm; r = ((ey - cy0) * ky * s + ty) * ppm
        ok = (r >= 0) & (r < dc.shape[0]) & (q >= 0) & (q < dc.shape[1])
        return np.median(dc[r[ok].astype(int), q[ok].astype(int)]) / ppm if ok.mean() > 0.9 else 1e9
    best = min((score(tx, ty), tx, ty) for tx in np.arange(ccxm - 0.8, ccxm + 0.81, 0.04) for ty in np.arange(ccy - 0.8, ccy + 0.81, 0.04))
    v, tx0, ty0 = best
    best = min((score(tx, ty), tx, ty) for tx in np.arange(tx0 - 0.04, tx0 + 0.041, 0.01) for ty in np.arange(ty0 - 0.04, ty0 + 0.041, 0.01))
    out[k] = dict(err_mm=float(best[0]), figure=f, kx=kx, ky=ky, tx=float(best[1]), ty=float(best[2]), cx0=float(cx0), cy0=float(cy0))
    print(k, d['xlsx'], {a: round(v, 3) for a, v in out[k].items()}, flush=True)
pickle.dump(out, open('fit_lat.pkl', 'wb'))
