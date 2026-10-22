"""Data for the atlas polygon editor: per section (atlas order) a reference JPEG (section + footprint + stroke
outline), the current atlas polygon (mm) and figure; per figure the plate line art in mm."""
import sys, io, json, base64, pickle, numpy as np
sys.path.insert(0, '/home/claude/widefield_pipeline'); sys.path.insert(0, '/tmp/claude-0/lm/p46')
from PIL import Image, ImageDraw
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely import transform as sxf
from skimage import measure
from wfield_local.histology_map import plates as PLT, fit as F
import tomm
PL = PLT.load_plates('/mnt/user-data/uploads/Documents/data/Immuno/PS92-95_widefield_stroke_cohort/lesion_map_work/paxinos_p63-98.pdf')
D = pickle.load(open('/tmp/claude-0/lm/p46/prep4.pkl', 'rb')); S = pickle.load(open('/tmp/claude-0/lm/p46/render46.pkl', 'rb'))['sections']
def st(a):
    p = np.percentile(a[a > 0] if (a > 0).any() else a, (1, 99.5)); return np.clip((a - p[0]) / (p[1] - p[0] + 1e-9), 0, 1)
def poly(m):
    cs = [c for c in measure.find_contours(np.pad(m, 1).astype(float), 0.5) if len(c) > 10]
    return unary_union([Polygon([(x - 1, y - 1) for y, x in c]).buffer(0) for c in cs]).buffer(0)
RR = {}
def plate(f):
    if f in RR: return RR[f]
    P = PL[f]; R = PLT.raster(P); keep, fills, _ = PLT.brain_lines(P)
    bd = __import__('scipy.ndimage', fromlist=['x']).binary_dilation(R['brain'], iterations=4); ppm = R['ppm']
    mm = lambda a: np.c_[(a[:, 0] - P['midline_x']) / P['pt_per_mm'], a[:, 1] / P['pt_per_mm']]
    def inside(b):
        c = np.clip(((b[:, 0] + 6) * ppm).astype(int), 0, bd.shape[1] - 1); r = np.clip((b[:, 1] * ppm).astype(int), 0, bd.shape[0] - 1)
        return bd[r, c].mean() > 0.5
    lines = []
    for L in keep:
        for a in L['polys']:
            b = mm(a)
            if inside(b): lines.append(dict(d=' '.join(f'{x:.3f},{y:.3f}' for x, y in b[::max(1, len(b) // 300)]), dash=bool(L['dashed'])))
    fl = [' '.join(f'{x:.3f},{y:.3f}' for x, y in mm(a)) for f_ in fills for a in f_ if inside(mm(a))]
    yy, xx = np.nonzero(R['brain'])
    lx = tomm.latx(f, PL); cpu = R['cpu'].copy(); cpu[:, int(6 * ppm):] = False
    RR[f] = dict(bregma=P['bregma'], lines=lines, fills=fl, box=[xx.min() / ppm - 6, yy.min() / ppm, xx.max() / ppm - 6, yy.max() / ppm])
    return RR[f]
secs = []
for k in sorted(S, key=lambda k: (S[k]['figure'], S[k]['xlsx'])):
    rec = S[k]; d = D[k]; T = d['T']; f = rec['figure']
    full = poly(d['stroke'])
    mm = sxf(full, lambda c: np.c_[F.to_mm(c[:, 0], c[:, 1], rec)]).buffer(0).difference(tomm.latx(f, PL))
    R = PLT.raster(PL[f]); mm = mm.intersection(PLT.left_brain_polygon(R))
    gs = [g for g in getattr(mm, 'geoms', [mm]) if g.geom_type == 'Polygon' and g.area > 0.005]
    g = max(gs, key=lambda q: q.area).simplify(0.015)
    pts = [[round(x, 3), round(y, 3)] for x, y in list(g.exterior.coords)[:-1]]
    im = T['img'].astype(np.float32); ys, xs = np.nonzero(T['tissue'][::2, ::2])
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    rgb = (np.dstack([st(im[2]), st(im[1]), st(im[0]) * 0.8])[y0:y1, x0:x1] * 255).astype(np.uint8)
    img = Image.fromarray(rgb); sc = 560 / img.width; img = img.resize((560, int(img.height * sc)), Image.LANCZOS); dr = ImageDraw.Draw(img)
    def draw(G, col, w):
        for p in getattr(G, 'geoms', [G]):
            if p.geom_type != 'Polygon': continue
            dr.line([((x / 2 - x0) * sc, (y / 2 - y0) * sc) for x, y in p.exterior.coords], fill=col, width=w)
    draw(full, (255, 160, 40), 2)
    if d['gl'] is not None: draw(d['gl'], (255, 255, 255), 1)
    b = io.BytesIO(); img.save(b, 'JPEG', quality=72)
    plate(f)
    for ff in (f - 1, f + 1):
        if ff in PL: plate(ff)
    secs.append(dict(id=k, name=d['xlsx'], animal=rec['animal'], use=rec['use'] if isinstance(rec['use'], str) else '',
                     figure=f, yours=rec['priya_figures'], poly=pts, img='data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()))
    print(k, d['xlsx'], f, len(pts), flush=True)
json.dump(dict(sections=secs, plates={str(k): v for k, v in RR.items()}), open('editor_data.json', 'w'))
print('MB', round(len(open('editor_data.json').read()) / 1e6, 2))
