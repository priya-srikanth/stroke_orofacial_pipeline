"""Per animal: each section with its stroke mask (left) next to its Paxinos plate with the mapped mask (right)."""
import sys, json, re, pickle, numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from pathlib import Path
sys.path.insert(0, '/home/claude/widefield_pipeline')
from shapely import transform as sxf
from shapely.geometry import Polygon
from shapely.ops import unary_union
from skimage import measure
from wfield_local.histology_map import plates as PLT, fit as F
sys.path.insert(0, '/tmp/claude-0/lm/p46'); import tomm  # noqa
PDF = '/mnt/user-data/uploads/Documents/data/Immuno/PS92-95_widefield_stroke_cohort/lesion_map_work/paxinos_p63-98.pdf'
PL = PLT.load_plates(PDF); RR = {}
def st(a):
    p = np.percentile(a[a > 0] if (a > 0).any() else a, (1, 99.5)); return np.clip((a - p[0]) / (p[1] - p[0] + 1e-9), 0, 1)
def to_mm_poly(P, rec):
    return sxf(P, lambda c: np.c_[F.to_mm(c[:, 0], c[:, 1], rec)])
TGT = np.load('/tmp/claude-0/lm/pairs/targets.npy')   # PS46-55 display level of contra striatum per channel (dapi, gfap, neun)
def matched(a, ref_mask, t):
    """Window so the contra striatum median lands where it does on the PS46-55 sheets (Priya: match intensities)."""
    lo = np.percentile(a[a > 0], 1); med = np.median(a[ref_mask]); hi = lo + (med - lo) / t
    return np.clip((a - lo) / (hi - lo + 1e-9), 0, 1)
def draw_pair(axL, axR, img, tissue, polys, polys_sec, rec, title, outline=None, color='orange', ref=None):
    ys, xs = np.nonzero(tissue); y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    if ref is not None:
        ch = [matched(img[c], ref, TGT[c]) for c in range(3)]
        axL.imshow(np.dstack([ch[2], ch[1], ch[0] * 0.8])[y0:y1, x0:x1])
    else:
        axL.imshow(np.dstack([st(img[2]), st(img[1]), st(img[0]) * 0.8])[y0:y1, x0:x1])
    axL.axis('off')
    for P in polys:
        for g in getattr(P, 'geoms', [P]):
            x, y = g.exterior.xy; axL.fill(np.array(x) - x0, np.array(y) - y0, color=color, alpha=0.3, lw=0)
            axL.plot(np.array(x) - x0, np.array(y) - y0, color=color, lw=1.2)
    if outline is not None:
        for g in getattr(outline, 'geoms', [outline]):
            x, y = g.exterior.xy; axL.plot(np.array(x) - x0, np.array(y) - y0, 'w', lw=0.8)
    axL.set_title(title, fontsize=9.5)
    f = rec['figure']; RR.setdefault(f, PLT.raster(PL[f])); R = RR[f]
    PLT.draw(axR, PL[f], lw=0.4, brain=R['brain'], ppm=R['ppm']); LB = PLT.left_brain_polygon(R)
    for P in polys_sec:
        U = to_mm_poly(P, rec).buffer(0).intersection(LB)
        if rec.get('mode') == 'ipsi': U = U.difference(tomm.latx(f, PL))
        for g in getattr(U, 'geoms', [U]):
            if g.is_empty or not hasattr(g, 'exterior'): continue
            x, y = g.exterior.xy; axR.fill(x, y, color=color, alpha=0.35, lw=0); axR.plot(x, y, color=color, lw=1)
    yy, xx = np.nonzero(R['brain']); pp = R['ppm']
    axR.set_xlim(xx.min() / pp - 6.1, xx.max() / pp - 5.9); axR.set_ylim(yy.max() / pp + 0.1, yy.min() / pp - 0.1)
    axR.set_title(f"Fig {f}  Bregma {PL[f]['bregma']:+.2f} mm" + (f"  (you: {'/'.join(map(str, rec['priya_figures']))})" if len(rec.get('priya_figures', [])) > 1 else ''), fontsize=9.5)
def sheet(animal, items, out, legend):
    n = len(items); nc = 2 if n > 3 else 1; nr = int(np.ceil(n / nc))
    fig, axs = plt.subplots(nr, 2 * nc, figsize=(8.6 * nc, 3.3 * nr), gridspec_kw=dict(width_ratios=[1.15, 1] * nc))
    axs = np.atleast_2d(axs)
    for ax in axs.ravel(): ax.axis('off')
    for i, it in enumerate(items):
        r, c = divmod(i, nc); draw_pair(axs[r, 2 * c], axs[r, 2 * c + 1], **it)
    fig.suptitle(f"{animal}: {legend}", fontsize=11); plt.tight_layout(rect=(0, 0, 1, 0.97), h_pad=1.5)
    plt.savefig(out, dpi=80); plt.close()

if sys.argv[1] == '46':
    D = pickle.load(open('/tmp/claude-0/lm/p46/prep4.pkl', 'rb')); S = pickle.load(open('/tmp/claude-0/lm/p46/render46.pkl', 'rb'))['sections']
    def poly(m):
        cs = [c for c in measure.find_contours(np.pad(m, 1).astype(float), 0.5) if len(c) > 10]
        return unary_union([Polygon([(x - 1, y - 1) for y, x in c]).buffer(0) for c in cs]).buffer(0)
    ks = sorted(S, key=lambda k: (S[k]['figure'], S[k]['xlsx']))   # atlas order (Priya)
    for a in sorted({S[k]['animal'] for k in ks}):
        items = []
        for k in [k for k in ks if S[k]['animal'] == a]:
            d = D[k]; T = d['T']; img = T['img'].astype(np.float32)
            full = poly(d['stroke'])
            items.append(dict(img=img, tissue=T['tissue'][::2, ::2], polys=[sxf(full, lambda c: c / 2)], polys_sec=[full],
                              rec=S[k], outline=sxf(d['gl'], lambda c: c / 2) if d['gl'] is not None else None,
                              title=f"{S[k]['xlsx']}  [{S[k]['use']}]"))
        sheet(a, items, f'/mnt/user-data/outputs/PS46-55_sections_atlas_{a}.png',
              'section with suggested footprint (orange; white = your stroke outline) | the same footprint on its Paxinos plate')
        print(a, flush=True)

if sys.argv[1] == '92':
    from wfield_local.histology_map.__main__ import load_cohort, _table, cohort_dir
    from wfield_local.histology_map import sections as SEC, painter
    from wfield_local import qupath_io
    U = '/mnt/user-data/uploads/Documents/data/Immuno/PS92-95_widefield_stroke_cohort'
    cfg, sections, _ = load_cohort('PS92-95', dict(crops_dir=U + '/lesion_map_work/crops', qupath_project=U))
    ann = qupath_io.project_annotations(U, keep_geometry=True); tab = _table(cfg)
    for a in sorted(tab.animal.unique()):
        items = []
        for _, row in tab[tab.animal == a].iterrows():
            sid = f"{row.animal}_s{int(row.section)}"; rec = sections.get(sid)
            mp = cohort_dir('PS92-95') / 'masks' / f'{sid}.json'
            if rec is None or 'figure' not in rec or not mp.exists(): continue
            img, gi, gc = SEC.load_raw(Path(cfg['crops_dir']) / f'{sid}_L3.npz', ann, row)
            T, _ = SEC.prepare(img, gi, gc, stored=rec)
            P = unary_union(painter.mask_polygons_px(json.loads(mp.read_text()), rec)).buffer(0)
            items.append(dict(img=T['img'], tissue=T['tissue'], polys=[P], polys_sec=[P], rec=rec, color='crimson', ref=SEC.rasterize(T['gc'], T['tissue'].shape),
                              title=f"{sid}  ({row.image.replace('.vsi', '')} #{int(row.slide_section)})"))
        items.sort(key=lambda it: it['rec']['figure'])
        sheet(a, items, f'/mnt/user-data/outputs/PS92-95_sections_atlas_{a}.png',
              'section with your painted stroke mask (red) | the same mask on its Paxinos plate (atlas order)')
        print(a, len(items), flush=True)

