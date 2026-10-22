"""Thalamus zooms from Priya's alignment page (thal_align.json, 2026-10-22): box centre (cx, cy in mm, on the
lesion-left section), rotation (deg, counter-clockwise) and Paxinos figure. Box is 5.8 x 4.2 mm for every section
(one figure scale), 500 um scale bar on each."""
import os, sys, json, io, numpy as np
sys.path.insert(0, os.path.expanduser('~/hist'))
import build
from PIL import Image
ZW, ZH, LZ = 5.8, 4.2, 3
ZGAIN = {'NeuN': 1.45, 'DAPI': 1.2}     # Priya 10-22: brighter NeuN and DAPI in the thalamus zooms
O = sys.argv[1]; A = {a['pick']: a for a in json.load(open(sys.argv[2]))}
man = json.load(open(f'{O}/manifest.json')); cache = os.path.expanduser('~/hist/L6')
for pk, r in man.items():
    if r['row'] != 'thalamus' or pk not in A: continue
    if r.get('zoom_align') == A[pk] and len(sys.argv) < 4: continue
    a = A[pk]; img6 = build.level_img(pk, 6, cache); m6, P = build.params(img6, {c: r.get('ovr', {}).get(c, 1.0) * ZGAIN.get(c, 1.0) for c in ('DAPI', 'GFAP', 'NeuN')})
    imz = build.level_img(pk, LZ, cache); um = 0.325 * 2 ** LZ
    mz = np.asarray(Image.fromarray(m6.astype(np.uint8) * 255).resize((imz.shape[2], imz.shape[1]), Image.BILINEAR)) > 127
    cx, cy = a['cx_mm'] * 1000 / um, a['cy_mm'] * 1000 / um; hw, hh = ZW * 500 / um, ZH * 500 / um
    for gf in (True, False):
        im = build.show(imz, mz, P, gfap=gf)
        if r['flip']: im = im[:, ::-1]
        R = Image.fromarray(np.ascontiguousarray(im)).rotate(a['rot_deg'], center=(cx, cy), resample=Image.BICUBIC)
        Z = np.asarray(R.crop((int(round(cx - hw)), int(round(cy - hh)), int(round(cx + hw)), int(round(cy + hh)))))
        name = r['files']['whole'].replace('.svg', '') + ('_thalamus_zoom' if gf else '_thalamus_zoom_noGFAP')
        b = io.BytesIO(); Image.fromarray(Z).save(b, 'PNG'); Image.fromarray(Z).save(f'{O}/{name}.png')
        build.svg(b.getvalue(), (Z.shape[1], Z.shape[0]), um, 500, f'{O}/{name}.svg')
        r['files']['zoom' if gf else 'zoom_noGFAP'] = f'{name}.svg'
    r['zoom_align'] = a; r['atlas_fig'] = a.get('figure')
    print(pk, a.get('figure'), Z.shape, flush=True); json.dump(man, open(f'{O}/manifest.json', 'w'), indent=1)
json.dump(man, open(f'{O}/manifest.json', 'w'), indent=1)
