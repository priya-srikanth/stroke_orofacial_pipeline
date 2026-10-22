import sys, json, pickle
sys.path.insert(0, '/home/claude/widefield_pipeline')
from wfield_local.histology_map import fit as F, plates as PLT
PDF = '/mnt/user-data/uploads/Documents/data/Immuno/PS92-95_widefield_stroke_cohort/lesion_map_work/paxinos_p63-98.pdf'
PL = PLT.load_plates(PDF); AP = json.load(open('ap_priya.json')); D = pickle.load(open('prep4.pkl', 'rb'))
try: out = pickle.load(open('fit_priya.pkl', 'rb'))
except FileNotFoundError: out = {}
R = {}
for k, d in D.items():
    x = d['xlsx'] if isinstance(d['xlsx'], str) else None
    if x not in AP or (k in out and out[k]['figs'] == AP[x]): continue
    for f in AP[x]: R.setdefault(f, PLT.raster(PL[f]))
    res, yt = F.fit_section(dict(tissue=d['T']['tissue'], gc=d['T']['gc'], x0=d['T']['x0']), R, AP[x])
    out[k] = dict(figs=AP[x], best=res[0], y_top=yt, all=res); print(k, x, res[0], flush=True)
pickle.dump(out, open('fit_priya.pkl', 'wb'))
