import sys, json, pickle, numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
sys.path.insert(0, '/home/claude/widefield_pipeline')
from shapely.geometry import Polygon
from shapely.ops import unary_union, transform as stf
from skimage import measure
from wfield_local.histology_map import plates as PLT, schematic as SC, fit as F
sys.path.insert(0, '/tmp/claude-0/lm/p46'); import tomm  # noqa
NUDGE = {'PS49_1_2': (0.0, -0.6)}   # Priya 10-21 review: 'needs to be moved up' (mm; x lateral-, y up-)
IP = pickle.load(open('/tmp/claude-0/lm/p46/fit_lat.pkl', 'rb'))
PDF = '/mnt/user-data/uploads/Documents/data/Immuno/PS92-95_widefield_stroke_cohort/lesion_map_work/paxinos_p63-98.pdf'
PL = PLT.load_plates(PDF); D = pickle.load(open('prep4.pkl', 'rb')); FT = pickle.load(open('fit_priya.pkl', 'rb'))
def mask_poly(m):
    cs = [c for c in measure.find_contours(np.pad(m, 1).astype(float), 0.5) if len(c) > 10]
    return unary_union([Polygon([(x - 1, y - 1) for y, x in c]).buffer(0) for c in cs]).buffer(0)
sections, byplate, rows = {}, {}, []
for k, v in FT.items():
    d = D[k]; b = v['best']
    rec = dict(animal=d['animal'], xlsx=d['xlsx'], use=d['use'], figure=b['figure'], bregma=PL[b['figure']]['bregma'],
               kx=b['kx'], ky=b['ky'], ty=b['ty'], y_top=v['y_top'], midline_x=d['T']['x0'], fit_err_mm=b['err_mm'],
               priya_figures=v['figs'], flags=d['flags'], **{k2: d['rec'][k2] for k2 in ('flip', 'angle', 'cx', 'cy', 'x_sym')})
    if k in IP:
        q = dict(IP[k]); q['ty'] += NUDGE.get(d['xlsx'], (0, 0))[1]; q['tx'] += NUDGE.get(d['xlsx'], (0, 0))[0]; rec.update(mode='ipsi', tx=q['tx'], ity=q['ty'], ikx=q['kx'], iky=q['ky'], cx0=q['cx0'], cy0=q['cy0'], ipsi_err_mm=q['err_mm'])
    sections[k] = rec
    mm = stf(lambda x, y, rec=rec: F.to_mm(x, y, rec), mask_poly(d['stroke'])).buffer(0).difference(tomm.latx(rec['figure'], PL))
    byplate.setdefault(rec['figure'], {}).setdefault(rec['animal'], []).append(mm)
    rows.append(dict(section=k, xlsx=d['xlsx'], animal=rec['animal'], figure=rec['figure'], bregma=rec['bregma'], area_mm2=round(mm.area, 3)))
pickle.dump(dict(sections=sections, byplate=byplate), open('render46.pkl', 'wb'))
json.dump(sections, open('/mnt/user-data/outputs/PS46-55_sections.json', 'w'), indent=1, default=float)
print(sorted(byplate))
