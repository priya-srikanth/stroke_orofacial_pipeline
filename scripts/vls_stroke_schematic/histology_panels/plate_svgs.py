"""Plate schematics as SVG (vector line art, region labels, Bregma caption), in mm: plate_full_fig{f}.svg (whole
section, for the overview grid) and plate_zoom_fig{f}.svg (cropped to the 5.8 x 4.2 mm thalamus box, for the zoom grid)."""
import sys, json, glob, numpy as np
POLY = {}
for _f in glob.glob('/tmp/claude-0/lm/ed/saved5/atlas_polygons/*.json'):
    _d = json.load(open(_f)); _d = _d.get('data', _d)
    if not _d.get('exclude'): POLY.setdefault(int(_d['figure']), []).append(_d)
GRP = {'PS47': ('#f2c12e', 0), 'PS48': ('#f2c12e', 1), 'PS49': ('#f2c12e', 2), 'PS50': ('#f2c12e', 3), 'PS46': ('#f0822e', 0), 'PS51': ('#f0822e', 1), 'PS54': ('#b4001e', 0), 'PS55': ('#b4001e', 1)}
DASH = ['', ' stroke-dasharray="0.12 0.07"', ' stroke-dasharray="0.03 0.05"', ' stroke-dasharray="0.12 0.05 0.03 0.05"']
def strokes(f):
    o = ['<g id="stroke_extent" fill="none" stroke-width="0.035" stroke-linejoin="round" opacity="0.9">']
    for d in POLY.get(f, []):
        c, k = GRP[d['animal']]; pts = ' '.join(f'{x:.3f},{y:.3f}' for x, y in d['poly'])
        o.append(f'<polygon points="{pts}" stroke="{c}"{DASH[k]}><title>{d["animal"]} {d["section_id"]}</title></polygon>')
    return o + ['</g>']
sys.path.insert(0, '/home/claude/widefield_pipeline')
from scipy import ndimage as ndi
from wfield_local.histology_map import plates as PLT
OUT = '/mnt/user-data/outputs/hist/plates'; ZW, ZH = 5.8, 4.2
SRC = ['/mnt/user-data/uploads/Documents/data/Immuno/PS92-95_widefield_stroke_cohort/lesion_map_work/paxinos_p63-98.pdf',
       '/mnt/user-data/uploads/Documents/data/Immuno/PS46-55_stroke_map_work/atlas/paxinos_ext.pdf',
       '/mnt/user-data/uploads/Documents/data/Immuno/PS46-55_stroke_map_work/atlas/paxinos_p81-106.pdf']
esc = lambda t: t.replace('&', '&amp;').replace('<', '&lt;')
info = {}
for src in SRC:
    PL = PLT.load_plates(src)
    for f in [k for k in PL if isinstance(k, int) and 13 <= k <= 66 and k not in info]:
        P = PL[f]; R = PLT.raster(P); keep, fills, _ = PLT.brain_lines(P); ppm = R['ppm']
        bd = ndi.binary_dilation(R['brain'], iterations=4)
        mm = lambda a: np.c_[(a[:, 0] - P['midline_x']) / P['pt_per_mm'], a[:, 1] / P['pt_per_mm']]
        def inside(b):
            c = np.clip(((b[:, 0] + 6) * ppm).astype(int), 0, bd.shape[1] - 1); r = np.clip((b[:, 1] * ppm).astype(int), 0, bd.shape[0] - 1)
            return bd[r, c].mean() > 0.5
        if not R['brain'].any(): continue
        lines = [(mm(a), L['dashed']) for L in keep for a in L['polys'] if inside(mm(a))]
        labs = []
        for w in P['page'].get_text('words'):
            x = ((w[0] + w[2]) / 2 - P['midline_x']) / P['pt_per_mm']; y = (w[1] + w[3]) / 2 / P['pt_per_mm']
            c, r = int((x + 6) * ppm), int(y * ppm)
            if 0 <= r < bd.shape[0] and 0 <= c < bd.shape[1] and bd[r, c] and len(w[4]) <= 8: labs.append((x, y, w[4]))
        yy, xx = np.nonzero(R['brain']); x0, y0, x1, y1 = xx.min() / ppm - 6, yy.min() / ppm, xx.max() / ppm - 6, yy.max() / ppm
        def body(clip=None):
            o = ['<g id="atlas" fill="none" stroke="#1d232b" stroke-linejoin="round">']
            for b, d in lines:
                pts = ' '.join(f'{x:.3f},{y:.3f}' for x, y in b[::max(1, len(b) // 400)])
                o.append(f'<polyline points="{pts}" stroke-width="{0.008 if d else 0.016}"' + (' stroke-dasharray="0.04 0.03" opacity="0.6"' if d else '') + '/>')
            o.append('</g><g id="labels" font-family="Arial" font-size="0.11" fill="#5a6572" text-anchor="middle">')
            for x, y, t in labs:
                if clip is None or (clip[0] <= x <= clip[2] and clip[1] <= y <= clip[3]): o.append(f'<text x="{x:.3f}" y="{y + 0.04:.3f}">{esc(t)}</text>')
            o.append('</g>'); return o
        cap = f'Bregma {P["bregma"]:+.2f} mm'
        # whole plate
        pad = 0.15; W, H = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad + 0.45
        s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W * 100:.0f}" height="{H * 100:.0f}" viewBox="{x0 - pad:.3f} {y0 - pad - 0.45:.3f} {W:.3f} {H:.3f}">'] + body() + strokes(f) + \
            [f'<g id="caption"><text x="0" y="{y0 - 0.12:.3f}" font-family="Arial" font-size="0.3" text-anchor="middle" fill="#1d232b">{cap}</text></g></svg>']
        open(f'{OUT}/plate_full_fig{f}.svg', 'w').write('\n'.join(s))
        # thalamus box crop (same box as the zooms: midline-centred, bottom 0.12 mm below the ventral surface)
        by = y1 + 0.12 - ZH; cl = (-ZW / 2, by, ZW / 2, by + ZH)
        s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{ZW * 100:.0f}" height="{(ZH + 0.45) * 100:.0f}" viewBox="{-ZW / 2:.3f} {by - 0.45:.3f} {ZW:.3f} {ZH + 0.45:.3f}">',
             f'<defs><clipPath id="c"><rect x="{-ZW / 2}" y="{by:.3f}" width="{ZW}" height="{ZH}"/></clipPath></defs><g clip-path="url(#c)">'] + body(cl) + \
            [f'</g><rect x="{-ZW / 2}" y="{by:.3f}" width="{ZW}" height="{ZH}" fill="none" stroke="#1d232b" stroke-width="0.02"/>',
             f'<g id="caption"><text x="0" y="{by - 0.12:.3f}" font-family="Arial" font-size="0.3" text-anchor="middle" fill="#1d232b">{cap}</text></g></svg>']
        open(f'{OUT}/plate_zoom_fig{f}.svg', 'w').write('\n'.join(s))
        info[f] = P['bregma']; print(f, P['bregma'])
json.dump(info, open(f'{OUT}/plate_bregma.json', 'w'))
