"""Final PS46-55 histology panels. Display parameters (black/white point per channel, flip, tilt, midline) are
measured on the level-6 image and applied to the level-4 (whole section, 5.2 um/px) and level-3 (thalamus zoom,
2.6 um/px) crops, so every resolution of a section looks the same. DAPI blue, GFAP green, NeuN red; Cy5 never read.
Per-section, per-channel gain overrides in OVR (>1 = brighter). Usage: build.py picks.json OUTDIR"""
import os, sys, json, base64, io, numpy as np
sys.path.insert(0, os.path.expanduser('~/hist'))
from compose import tissue, K, LO, SAT
import render
from ets import ETS
from PIL import Image
from scipy import ndimage as ndi
CH = ['DAPI', 'GFAP', 'NeuN']
TARGET = {'NeuN': 0.26, 'DAPI': 0.17}           # mean display value over tissue (median of the striatal sections was 0.25 / 0.16)
def params(img6, ovr):
    m = tissue(img6, 6); P = {}
    for i, c in enumerate(CH):
        t = img6[i][m].astype(float); lo = np.percentile(t, LO[c])
        ref = np.median(t) if LO[c] < 50 else lo + (np.percentile(t, 75) - lo)
        hi = max(lo + K[c] * (ref - lo), np.percentile(t, 100 * (1 - SAT[c])))
        if c in TARGET:                                  # equalise mean tissue brightness (Priya 10-22: caudal / thalamic sections read as less red)
            for _ in range(4):
                mu = np.clip((t - lo) / (hi - lo), 0, 1).mean(); hi = lo + (hi - lo) * float(np.clip(mu / TARGET[c], 0.5, 2.0))
        hi = lo + (hi - lo) / ovr.get(c, 1.0); P[c] = (float(lo), float(hi))
    return m, P
def show(img, m, P, gfap=True):
    out = np.zeros(img.shape[1:] + (3,), float)
    for i, c in enumerate(CH):
        if c == 'GFAP' and not gfap: continue
        lo, hi = P[c]; v = np.clip((img[i].astype(float) - lo) / (hi - lo), 0, 1)
        out[..., {'NeuN': 0, 'GFAP': 1, 'DAPI': 2}[c]] = v
    out[~m] = 0
    return (out * 255).astype(np.uint8)
def tilt(m6, red):
    """Angle that makes the section most left-right symmetric (degrees, PIL rotate convention) and the axis x (level-6 px, after rotation)."""
    best = (-1, 0, 0)
    for ang in np.arange(-15, 15.1, 1.0):
        I = np.asarray(Image.fromarray((m6 * (0.5 + red)).astype(np.float32)).rotate(ang, expand=True, resample=Image.BILINEAR))
        F = np.fft.rfft(I, n=2 * I.shape[1], axis=1); G = np.fft.rfft(I[:, ::-1], n=2 * I.shape[1], axis=1)
        cc = np.fft.irfft(F * np.conj(G), axis=1).sum(0); s = int(np.argmax(cc)); v = cc[s] / (I ** 2).sum()
        if v > best[0]:
            sh = s if s < I.shape[1] else s - 2 * I.shape[1]
            best = (v, float(ang), (I.shape[1] - 1 + sh) / 2.0)
    return best[1], best[2]
VFLIP = {'PS47:e58'} | set(['PS47:e40', 'PS47:e61', 'PS48:e26', 'PS48:e29'])   # upside down: PS47 e58 (Priya 10-22) + the outline editor's flips                           # mounted upside down (Priya 10-22)
def level_img(pk, L, cache):
    return _level_img(pk, L, cache)[:, ::-1, :] if pk in VFLIP else _level_img(pk, L, cache)
def _level_img(pk, L, cache):
    f = f"{cache}/{pk.replace(':', '_')}_L{L}.npz"
    if not os.path.exists(f):
        a, eid, vsi, w, h, sc = render.entry(pk); e = ETS(render.ets_for(a, eid, vsi, w, h, sc))
        np.savez_compressed(f, img=render.crop3(e, w, h, L), entry=eid)
    return np.load(f)['img']
def place(img, m6, flip, ang):
    """flip -> rotate (expand) -> crop to tissue bbox; returns array and the transform for the mask."""
    if flip: img = img[:, ::-1]
    return np.asarray(Image.fromarray(img).rotate(ang, expand=True, resample=Image.BICUBIC))
def svg(png, w_px, um_px, bar_um, path, label=''):
    W, H = w_px; b64 = base64.b64encode(png).decode(); bl = bar_um / um_px
    x0, y0 = W - bl - 0.04 * W, H - 0.05 * H
    s = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
         f'<g id="image"><image width="{W}" height="{H}" xlink:href="data:image/png;base64,{b64}"/></g>'
         f'<g id="scale_bar"><line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x0 + bl:.1f}" y2="{y0:.1f}" stroke="#ffffff" stroke-width="{max(H * 0.008, 3):.1f}"/>'
         f'<text x="{x0 + bl / 2:.1f}" y="{y0 - H * 0.015:.1f}" fill="#ffffff" font-family="Arial" font-size="{H * 0.035:.1f}" text-anchor="middle">'
         f'{bar_um / 1000:g} mm</text></g></svg>') if bar_um >= 1000 else (
         f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
         f'<g id="image"><image width="{W}" height="{H}" xlink:href="data:image/png;base64,{b64}"/></g>'
         f'<g id="scale_bar"><line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x0 + bl:.1f}" y2="{y0:.1f}" stroke="#ffffff" stroke-width="{max(H * 0.008, 3):.1f}"/>'
         f'<text x="{x0 + bl / 2:.1f}" y="{y0 - H * 0.015:.1f}" fill="#ffffff" font-family="Arial" font-size="{H * 0.035:.1f}" text-anchor="middle">'
         f'{bar_um:g} µm</text></g></svg>')
    open(path, 'w').write(s)
def build(job, out, cache, levels=(4,)):
    pk = job['pick']; img6 = level_img(pk, 6, cache)
    m6, P = params(img6, job.get('ovr', {}))
    g = np.clip((img6[1].astype(float) - P['GFAP'][0]) / (P['GFAP'][1] - P['GFAP'][0]), 0, 1)
    flip = job.get('flip')
    if flip is None:
        hot = (g > 0.5) & m6; W6 = g.shape[1]; flip = bool(hot[:, W6 // 2:].sum() > hot[:, :W6 // 2].sum())
    if job.get('flip_invert'): flip = not flip                # Priya's left-right flip in the outline editor
    r6 = np.clip((img6[2].astype(float) - P['NeuN'][0]) / (P['NeuN'][1] - P['NeuN'][0]), 0, 1)
    mm, rr = (m6[:, ::-1], r6[:, ::-1]) if flip else (m6, r6)
    ang, ax6 = (job['tilt'], None) if 'tilt' in job else tilt(mm, rr)
    if ax6 is None: _, ax6 = 0, None
    rec = dict(job, flip=flip, tilt=ang, params=P, files={})
    name = f"{job['label']}_{pk.replace(':', '_')}"
    for L in levels:
        img = level_img(pk, L, cache); s = 2 ** (6 - L)
        m = np.asarray(Image.fromarray(m6.astype(np.uint8) * 255).resize((img.shape[2], img.shape[1]), Image.BILINEAR)) > 127
        rgbim = show(img, m, P)
        A = place(rgbim, None, flip, ang); M = place((m * 255).astype(np.uint8), None, flip, ang) > 127
        ys, xs = np.nonzero(M); pad = int(0.02 * A.shape[1])
        y0, y1, x0, x1 = max(ys.min() - pad, 0), ys.max() + pad, max(xs.min() - pad, 0), xs.max() + pad
        A = A[y0:y1, x0:x1]; um = 0.325 * 2 ** L
        buf = io.BytesIO(); Image.fromarray(A).save(buf, 'PNG'); Image.fromarray(A).save(f'{out}/{name}.png')
        svg(buf.getvalue(), (A.shape[1], A.shape[0]), um, 1000, f'{out}/{name}.svg')
        rec['files']['whole'] = f'{name}.svg'; rec['whole_px'] = [A.shape[1], A.shape[0]]; rec['um_px'] = um
        if job.get('zoom'):
            # thalamus window, as in Priya's examples: centred on the midline, 59% of section width, from 32% to 97% of its height
            Wd, Hd = A.shape[1], A.shape[0]; cx = (ax6 * s - x0) if ax6 is not None else Wd / 2
            zx0, zx1 = int(cx - 0.295 * Wd), int(cx + 0.295 * Wd); zy0, zy1 = int(0.32 * Hd), int(0.97 * Hd)
            rec['zoom_box_frac'] = [zx0 / Wd, zy0 / Hd, zx1 / Wd, zy1 / Hd]
            Lz = 3; imz = level_img(pk, Lz, cache); f = 2 ** (L - Lz)
            mz = np.asarray(Image.fromarray(m6.astype(np.uint8) * 255).resize((imz.shape[2], imz.shape[1]), Image.BILINEAR)) > 127
            for gf in (True, False):
                Z = place(show(imz, mz, P, gfap=gf), None, flip, ang)[y0 * f:y1 * f, x0 * f:x1 * f][zy0 * f:zy1 * f, max(zx0, 0) * f:zx1 * f]
                zn = f"{name}_thalamus_zoom{'' if gf else '_noGFAP'}"
                b = io.BytesIO(); Image.fromarray(Z).save(b, 'PNG'); Image.fromarray(Z).save(f'{out}/{zn}.png')
                svg(b.getvalue(), (Z.shape[1], Z.shape[0]), 0.325 * 2 ** Lz, 500, f'{out}/{zn}.svg')
                rec['files']['zoom' if gf else 'zoom_noGFAP'] = f'{zn}.svg'
    return rec
if __name__ == '__main__':
    jobs = json.load(open(sys.argv[1])); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
    cache = os.path.expanduser('~/hist/L6'); only = sys.argv[3:]
    man = f'{out}/manifest.json'; done = json.load(open(man)) if os.path.exists(man) else {}
    for j in jobs:
        if only and j['pick'] not in only: continue
        if j['pick'] in done and not only: print('skip', j['pick']); continue
        r = build(j, out, cache); done[j['pick']] = r; json.dump(done, open(man, 'w'), indent=1)
        print(j['pick'], 'flip' if r['flip'] else '', 'tilt', r['tilt'], flush=True)
