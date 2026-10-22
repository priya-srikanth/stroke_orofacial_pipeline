"""AP review data: per section the plain immuno image + Priya's saved polygon/figure; per figure (18-37) plate line art
(mm) and the atlas photomicrograph (odd = Nissl, even = AChE) as a small JPEG."""
import sys, io, json, glob, base64, pickle, numpy as np
sys.path.insert(0, '/home/claude/widefield_pipeline'); sys.path.insert(0, '/tmp/claude-0/lm/ed')
from PIL import Image
from scipy import ndimage as ndi
from wfield_local.histology_map import plates as PLT
sys.path.insert(0, '/tmp/claude-0/lm/ed/ap'); import exlib as EX   # reuses plate() line-art export and loaded sections
PH = '/mnt/user-data/uploads/Documents/data/Immuno/PS92-95_widefield_stroke_cohort/lesion_map_work/ache'
def photo(f):
    a = np.asarray(Image.open(glob.glob(f'{PH}/fig{f}-*.png')[0]).convert('RGB')); g = a.mean(2).copy(); g[:60] = 255
    t = ndi.binary_fill_holes(ndi.binary_opening(g < 235, iterations=2)); lab, n = ndi.label(t)
    t = lab == np.argmax(np.bincount(lab.ravel())[1:]) + 1; ys, xs = np.nonzero(t)
    im = Image.fromarray(a[ys.min():ys.max(), xs.min():xs.max()]); im.thumbnail((520, 520))
    b = io.BytesIO(); im.save(b, 'JPEG', quality=70); return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
FIGS = range(18, 38)
plates = {}
for f in FIGS:
    p = dict(EX.plate(f)); p['photo'] = photo(f); p['stain'] = 'Nissl' if f % 2 else 'AChE'; plates[str(f)] = p
saved = {}
for fp in glob.glob('/tmp/claude-0/lm/ed/saved/atlas_polygons/*.json'):
    d = json.load(open(fp)); d = d.get('data', d); saved[d['section_id']] = d
secs = []
for s in EX.secs:
    sv = saved.get(s['id'], {})
    d = EX.D[s['id']]; T = d['T']; im = T['img'].astype(np.float32); ys, xs = np.nonzero(T['tissue'][::2, ::2])
    rgb = (np.dstack([EX.st(im[2]), EX.st(im[1]), EX.st(im[0]) * 0.8])[ys.min():ys.max(), xs.min():xs.max()] * 255).astype(np.uint8)
    img = Image.fromarray(rgb); img.thumbnail((620, 620)); b = io.BytesIO(); img.save(b, 'JPEG', quality=72)
    secs.append(dict(id=s['id'], name=s['name'], animal=s['animal'], use=s['use'], yours=s['yours'],
                     figure=int(sv.get('figure', s['figure'])), poly=sv.get('poly', s['poly']), exclude=bool(sv.get('exclude')),
                     img='data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()))
secs.sort(key=lambda s: (s['figure'], s['name']))
json.dump(dict(sections=secs, plates=plates), open('/tmp/claude-0/lm/ed/ap/ap_data.json', 'w'))
print(len(secs), 'MB', round(len(open('/tmp/claude-0/lm/ed/ap/ap_data.json').read()) / 1e6, 2))
