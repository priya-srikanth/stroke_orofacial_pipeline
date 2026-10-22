"""Render PS46-55 sections from the VS200 .ets pyramids: DAPI (c0) blue, GFAP (c1, FITC) green, NeuN (c2, TRITC) red.
Cy5 (DARPP32, c3) is never read. Usage: render.py LEVEL OUTDIR PICK [PICK ...]   (PICK = PS51_2_8 = slide 2, scene 8)"""
import os, re, sys, json, numpy as np
sys.path.insert(0, os.path.expanduser('~/mnt/Documents/data/Immuno/PS46-55_stroke_map_work'))
from ets import ETS
H = os.path.expanduser('~'); B = H + '/mnt/Documents/data/Immuno'
PROJ = {'PS46': '2025_04_03_PS46-48', 'PS47': '2025_04_03_PS46-48', 'PS48': '2025_04_03_PS46-48', 'PS49': '2026_03_16_PS49-50',
        'PS50': '2026_03_16_PS49-50', 'PS51': '2025_08_30_PS51-55', 'PS54': '2025_08_30_PS51-55', 'PS55': '2025_08_30_PS51-55'}
FIX = {('PS55', 83): 10047, ('PS55', 85): 10053, ('PS51', 135): 10002}      # from crop_fixed.py (no unique size match)
def local(u):
    u = u.replace('file:', '')
    for a, b in [('/Volumes/Neurobio/MICROSCOPE/Byungwoo/histology/LB-Priya', H + '/mnt/LB-Priya'),
                 ('/Volumes/Neurobio/MICROSCOPE/Priya', H + '/mnt/Priya'), ('/Users/Priya2/Documents', H + '/mnt/Documents'),
                 ('/sessions/rcw-01pkikjnjb6yj1gkfxgjsrm5', H)]:
        u = u.replace(a, b)
    return u
def key(a, n):
    m = re.search(a + r'_(\d)_GFAP_Neun(?:_(\d+))?\.vsi', n)
    if m: return int(m.group(1)), int(m.group(2) or 0)
    m = re.search(a + r'_(\d)_488|DARPP32_(\d)\.vsi', n); sl = int(m.group(1) or m.group(2))
    return sl, int(re.search(r'_(\d+)$', n).group(1))
def entry(pick):
    if ':e' in pick:                                             # PS54:e225 = QuPath entry id
        a, eid = pick.split(':e'); p = PROJ[a]
        for e in json.load(open(f'{B}/{p}/project.qpproj'))['images']:
            if e['entryID'] == int(eid):
                b = e['serverBuilder']; b = b.get('builder', b)
                s = json.load(open(f"{B}/{p}/data/{e['entryID']}/summary.json"))['server']
                return a, e['entryID'], local(b['uri']), s['width'], s['height'], key(a, e['imageName'])[1]
        raise KeyError(pick)
    a, sl, sc = pick.split('_'); p = PROJ[a]
    for e in json.load(open(f'{B}/{p}/project.qpproj'))['images']:
        n = e['imageName']
        if a in n and '20x' in n and key(a, n) == (int(sl), int(sc)):
            b = e['serverBuilder']; b = b.get('builder', b)
            s = json.load(open(f"{B}/{p}/data/{e['entryID']}/summary.json"))['server']
            return a, e['entryID'], local(b['uri']), s['width'], s['height'], int(sc)
    raise KeyError(pick)
def ets_for(a, eid, vsi, w, h, sc=None):
    d = os.path.join(os.path.dirname(vsi), '_' + os.path.splitext(os.path.basename(vsi))[0] + '_')
    if (a, eid) in FIX:
        dd = os.path.join(d, f'stack{FIX[(a, eid)]}'); return os.path.join(dd, [f for f in os.listdir(dd) if f.endswith('.ets')][0])
    c = []
    for r, _, fs in os.walk(d):
        for f in fs:
            if f.endswith('.ets'):
                e = ETS(os.path.join(r, f)); H0, W0 = e.level_shape(0)
                if 0 <= W0 - w < 512 and 0 <= H0 - h < 512: c.append(os.path.join(r, f))
    if len(c) > 1 and sc:                                      # same-size scenes: series _N -> stack 10002 + 3(N-1) (verified in crop_fixed.py)
        c = [x for x in c if f'stack{10002 + 3 * (sc - 1)}' in x]
    if len(c) != 1: raise RuntimeError(f'{a} e{eid}: {len(c)} size matches')
    return c[0]
def crop3(e, w, h, L):
    ds, t = 2 ** L, e.tile; W, Hh = w // ds, h // ds
    out = np.zeros((3, Hh, W), np.uint16)
    for ty in range(0, (Hh - 1) // t + 1):
        for tx in range(0, (W - 1) // t + 1):
            for c in range(3):                                   # DAPI, GFAP, NeuN only
                a = e.tile_img(tx, ty, c, L); y1, x1 = min(Hh, (ty + 1) * t), min(W, (tx + 1) * t)
                out[c, ty * t:y1, tx * t:x1] = a[:y1 - ty * t, :x1 - tx * t]
    return out
if __name__ == '__main__':
    L, out = int(sys.argv[1]), sys.argv[2]; os.makedirs(out, exist_ok=True)
    for pk in sys.argv[3:]:
        o = f"{out}/{pk.replace(':', '_')}_L{L}.npz"
        if os.path.exists(o): print('skip', pk); continue
        try:
            a, eid, vsi, w, h, sc = entry(pk); p = ets_for(a, eid, vsi, w, h, sc); e = ETS(p)
        except Exception as ex:
            print("FAIL", pk, ex); continue
        assert e.nc >= 3
        img = crop3(e, w, h, L)
        np.savez_compressed(o, img=img, entry=eid, ets=p, px_um=0.325 * 2 ** L, channels=np.array(['DAPI', 'GFAP', 'NeuN']))
        print(pk, f'e{eid}', img.shape, flush=True)
