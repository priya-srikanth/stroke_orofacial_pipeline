"""PS46-55: standardise all sections, seed = Priya's QuPath stroke outline, grow into absent territory."""
import sys, pickle, numpy as np, pandas as pd
from pathlib import Path
from shapely import affinity
sys.path.insert(0, '/home/claude/widefield_pipeline')
from wfield_local import qupath_io
from wfield_local.histology_map import sections as S, footprint as FP
from wfield_local.histology_map.sections import rasterize
from scipy import ndimage as ndi
from skimage import morphology, measure
U = Path('/mnt/user-data/uploads/Documents/data/Immuno')
tab = pd.read_csv('/tmp/claude-0/lm/ps46_55_table_v2.csv')
ann = {p: qupath_io.project_annotations(U / p, keep_geometry=True) for p in tab.project.unique()}
only = sys.argv[1:]
out = {}
for _, r in tab.iterrows():
    sid = f"{r.animal}_e{r.entry_id}"
    if only and sid not in only: continue
    a = ann[r.project]; a = a[a.entry_id == r.entry_id].copy()
    um2 = a.area_um2 / 1e6
    pick = lambda A: a.geometry.iloc[int(np.argmin(np.abs(um2.values - A)))]
    gc, gi = pick(r.contra_mm2), pick(r.ipsi_mm2)
    gl = pick(r.lesion_mm2) if r.n_ann >= 3 else None
    z = np.load(U / 'PS46-55_stroke_map_work/crops' / f'{sid}_L4.npz', allow_pickle=True)
    img = z['img'].astype(np.float32)[:3]; org = z['origin']; ds = int(z['ds'])
    tf = lambda g: affinity.scale(affinity.translate(g, -org[0], -org[1]), 1 / ds, 1 / ds, origin=(0, 0))
    gc, gi = tf(gc), tf(gi); gl = tf(gl) if gl is not None else None
    W = img.shape[2]
    Sx = S.section(img, gi, gc)
    tmk = S.tissue_mask(Sx['img'][0]); lab = measure.label(tmk)
    ov = rasterize(Sx['gi'], tmk.shape) | rasterize(Sx['gc'], tmk.shape)
    keep = [l for l in np.unique(lab[ov & tmk]) if l and (lab == l).sum() > 2000]
    Sx['tissue'] = ndi.binary_fill_holes(np.isin(lab, keep))
    if Sx['tissue'].sum() < 1.5 * (Sx['gi'].area + Sx['gc'].area):     # DAPI mask failed: use all channels
        allc = np.mean([S.stretch(ch) for ch in Sx['img']], 0)
        tmk = S.tissue_mask(allc); lab = measure.label(tmk)
        keep = [l for l in np.unique(lab[ov & tmk]) if l and (lab == l).sum() > 2000]
        Sx['tissue'] = ndi.binary_fill_holes(np.isin(lab, keep)); print(sid, 'tissue from all channels', flush=True)
    if Sx['flip'] and gl is not None:
        gl = affinity.scale(gl, -1, 1, origin=(W / 2, 0))
    M = S.symmetry_midline(Sx)
    T = S.standardise(Sx, M['angle'], M['cx'], M['cy'])
    gi_, gc_ = T['gi'], T['gc']
    lo, hi = gi_.bounds[2], gc_.bounds[0]           # medial edges of the two striata
    xg = (lo + hi) / 2
    T['x0'] = S.fissure_x(T['tissue'], xg, half_um=max(300, (hi - lo) * 5.2 / 2))
    if not (lo < T['x0'] < hi):
        T['x0'] = xg; print(sid, 'midline = midpoint of striatal medial edges', flush=True)
    if gl is not None:
        gl = affinity.rotate(gl, -M['angle'], origin=(M['cx'], M['cy']))
    flags = []
    from grow import grow
    from shapely.geometry import Polygon
    sh = T['tissue'].shape
    try:
        mirror = FP.anchor_mirror(T['gc'], T['gi'], T['x0'])
        if mirror.centroid.distance(T['gi'].centroid) * 5.2 > 1000: raise ValueError('anchor far')
    except Exception as ex:
        mirror = affinity.scale(T['gc'], -1, 1, origin=(T['x0'], 0)); flags.append('plain mirror')
    tm = T['tissue']; xs = np.arange(sh[1])[None, :]; x0 = T['x0']
    xm = np.clip(np.round(2 * x0 - xs).astype(int), 0, sh[1] - 1)[0]
    frame = ndi.binary_fill_holes(tm[:, xm] & (xs < x0))      # mirrored contralesional hemisphere
    frame = ndi.binary_dilation(frame, iterations=6)
    left = (xs < x0) & np.ones(sh, bool)
    mcm = rasterize(mirror, sh); im = rasterize(T['gi'], sh)
    seed = rasterize(gl, sh) if gl is not None else np.zeros(sh, bool)
    surv = im & ~seed
    if not seed.any():
        flags.append('no stroke outline'); seed = (mcm & ~surv & left)
    target = rasterize(T['gc'], sh).sum() - surv.sum()
    domain = ((mcm & ~surv) | seed) & frame & left
    fallback = frame & left & ~surv
    s = grow(seed, domain, fallback, target)
    missing = mcm & ~surv
    if s.sum() < 0.9 * target: flags.append(f"footprint {s.sum()/target:.0%} of lost area")
    if T['gi'].centroid.x > T['x0'] or T['gc'].centroid.x < T['x0']: flags.append('midline between outlines FAILED')
    out[sid] = dict(T=dict(img=T['img'][:, ::2, ::2].astype(np.float16), tissue=T['tissue'], gi=T['gi'], gc=T['gc'], x0=T['x0']),
                    gl=gl, mirror=mirror, missing=missing, stroke=s,
                    target_px=int(target), rec=dict(flip=Sx['flip'], angle=M['angle'], cx=M['cx'], cy=M['cy'], x_sym=M['x_sym'], midline_x=T['x0']),
                    flags=flags, animal=r.animal, use=r.use, xlsx=r.xlsx_image)
    print(sid, r.xlsx_image, flags, flush=True)
pickle.dump(out, open('/tmp/claude-0/lm/p46/prep2.pkl', 'wb'))
