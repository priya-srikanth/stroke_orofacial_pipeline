"""Assembled figures (Priya 10-22): rows = animals (mild -> severe), columns = Paxinos plates (rostral -> caudal), the
plate schematic heading each column, every section at one mm scale, a scale bar on every panel.
  PS46-55_histology_overview.{svg,pdf,png}  whole sections, 11 pt/mm, 1 mm bars
  PS46-55_thalamus_zooms.{svg,pdf,png}      thalamus zooms (+GFAP row, no-GFAP row per animal), 27.6 pt/mm, 500 um bars
Open the SVG or PDF in Illustrator to edit (images stay at ~300 dpi at this size; full-resolution panels sit beside them)."""
import os, re, io, json, base64, sys
from PIL import Image
D = sys.argv[1]; man = json.load(open(f'{D}/manifest.json')); BR = {int(k): v for k, v in json.load(open(f'{D}/plates/plate_bregma.json')).items()}
ORDER = ['PS47', 'PS48', 'PS49', 'PS50', 'PS46', 'PS51', 'PS54', 'PS55']
NAME = {'PS47': 'Mild #1', 'PS48': 'Mild #2', 'PS49': 'Mild #3', 'PS50': 'Mild #4', 'PS46': 'Moderate #1', 'PS51': 'Moderate #2', 'PS54': 'Severe #1', 'PS55': 'Severe #2'}
FONT = 'font-family="Arial, Helvetica, sans-serif"'
def nested(path, x, y, w):
    s = open(path).read(); m = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([\d.]+) ([\d.]+)"', s); vw, vh = float(m.group(3)), float(m.group(4))
    h = w * vh / vw; s = re.sub(r'<svg [^>]*?width="[\d.]+" height="[\d.]+"', f'<svg x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}"', s, count=1)
    s = s.replace('xmlns="http://www.w3.org/2000/svg" ', ''); return s, h
def img(path, x, y, w, h, pxmm, mm_w):
    I = Image.open(path).convert('RGB'); I = I.resize((max(1, int(mm_w * pxmm)), max(1, int(mm_w * pxmm * I.size[1] / I.size[0]))), Image.LANCZOS)
    b = io.BytesIO(); I.save(b, 'JPEG', quality=90)
    return f'<image x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" preserveAspectRatio="none" xlink:href="data:image/jpeg;base64,{base64.b64encode(b.getvalue()).decode()}"/>'
def bar(x, y, w, h, ptmm, um):
    L = um / 1000 * ptmm; x1 = x + w - 0.06 * w; x0 = x1 - L; yb = y + h - 0.07 * h; fs = max(5.0, 0.055 * h)
    lab = f'{um / 1000:g} mm' if um >= 1000 else f'{um:g} µm'
    return (f'<g class="scale_bar"><line x1="{x0:.2f}" y1="{yb:.2f}" x2="{x1:.2f}" y2="{yb:.2f}" stroke="#fff" stroke-width="{max(0.8, 0.012 * h):.2f}"/>'
            f'<text x="{(x0 + x1) / 2:.2f}" y="{yb - 0.025 * h:.2f}" fill="#fff" font-size="{fs:.1f}" text-anchor="middle" {FONT}>{lab}</text></g>')
def grid(cells, plate_kind, ptmm, pxmm, um_bar, rows, out, title, MAXW=2600):
    figs = sorted({c['fig'] for c in cells if c['fig']}, key=lambda f: -BR[f]) + ([None] if any(c['fig'] is None for c in cells) else [])
    GAP, LABW, TOP = 6.0, 96.0, 10.0
    colw = {}
    for f in figs:
        pw = 0
        if f:
            vb = re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+)', open(f'{D}/plates/plate_{plate_kind}_fig{f}.svg').read()); pw = float(vb.group(1)) * ptmm
        cw = [sum(c['w_mm'] * ptmm + GAP for c in cells if c['fig'] == f and c['row'] == r) - GAP for r in rows]
        colw[f] = max([pw] + cw)
    bands, cur, wsum = [], [], LABW                       # wrap the plate columns into stacked bands no wider than MAXW
    for f in figs:
        if cur and wsum + colw[f] + GAP * 2 > MAXW: bands.append(cur); cur, wsum = [], LABW
        cur.append(f); wsum += colw[f] + GAP * 2
    if cur: bands.append(cur)
    W = max(LABW + sum(colw[f] + GAP * 2 for f in bd) for bd in bands); parts = []; y = TOP
    for bi, bd in enumerate(bands):
        X = {}; x = LABW
        for f in bd: X[f] = x; x += colw[f] + GAP * 2
        ph = 0; parts.append(f'<g id="band_{bi + 1}">')
        for f in bd:
            if f:
                pw = float(re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+)', open(f'{D}/plates/plate_{plate_kind}_fig{f}.svg').read()).group(1)) * ptmm
                sv, h = nested(f'{D}/plates/plate_{plate_kind}_fig{f}.svg', X[f], y, pw)
                parts.append(f'<g id="plate_fig{f}">' + sv + '</g>'); ph = max(ph, h)
            else:
                parts.append(f'<text x="{X[f]:.1f}" y="{y + 12:.1f}" font-size="7" {FONT}>no plate chosen</text>')
        y += ph + GAP * 2
        for r in rows:
            rc = [c for c in cells if c['row'] == r and c['fig'] in bd]
            if not rc: continue
            rh = max(c['h_mm'] * ptmm for c in rc)
            parts.append(f'<g id="row_{re.sub(r"[^A-Za-z0-9]", "_", r)}_{bi + 1}"><text x="4" y="{y + rh / 2:.1f}" font-size="8" {FONT}>{r}</text>')
            for f in bd:
                xx = X[f]
                for c in [c for c in rc if c['fig'] == f]:
                    w, h = c['w_mm'] * ptmm, c['h_mm'] * ptmm
                    parts.append(img(c['png'], xx, y, w, h, pxmm, c['w_mm']) + bar(xx, y, w, h, ptmm, um_bar))
                    parts.append(f'<text x="{xx:.1f}" y="{y + h + 6:.1f}" font-size="5" fill="#555" {FONT}>{c["cap"]}</text>')
                    xx += w + GAP
            parts.append('</g>'); y += rh + 14
        parts.append('</g>'); y += 18
    if plate_kind == 'full':
        LG = [('Mild #1', '#f2c12e', ''), ('Mild #2', '#f2c12e', '4 2.5'), ('Mild #3', '#f2c12e', '1 1.8'), ('Mild #4', '#f2c12e', '4 1.8 1 1.8'),
              ('Moderate #1', '#f0822e', ''), ('Moderate #2', '#f0822e', '4 2.5'), ('Severe #1', '#b4001e', ''), ('Severe #2', '#b4001e', '4 2.5')]
        lx = LABW; parts.append('<g id="legend">' + f'<text x="{lx:.1f}" y="{y + 8:.1f}" font-size="7" {FONT}>Stroke extent on the plates (from the schematic):</text>')
        lx += 150
        for n, c, d in LG:
            parts.append(f'<line x1="{lx:.1f}" y1="{y + 5.5:.1f}" x2="{lx + 22:.1f}" y2="{y + 5.5:.1f}" stroke="{c}" stroke-width="1.6"' + (f' stroke-dasharray="{d}"' if d else '') + '/>'
                         f'<text x="{lx + 26:.1f}" y="{y + 8:.1f}" font-size="7" {FONT}>{n}</text>'); lx += 80
        parts.append('</g>'); y += 16
    H = y + 6
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W:.1f}" height="{H:.1f}" viewBox="0 0 {W:.1f} {H:.1f}">'
           f'<rect width="100%" height="100%" fill="#ffffff"/>' + ''.join(parts) + '</svg>')
    open(f'{D}/{out}.svg', 'w').write(svg)
    import cairosvg
    cairosvg.svg2pdf(bytestring=svg.encode(), write_to=f'{D}/{out}.pdf')
    cairosvg.svg2png(bytestring=svg.encode(), write_to=f'{D}/{out}.png', output_width=int(W * 2))
    print(out, round(W), 'x', round(H), 'pt')
# overview: whole sections
cells = []
for r in man.values():
    I = Image.open(f'{D}/' + r['files']['whole'].replace('.svg', '.png')); wmm = I.size[0] * r['um_px'] / 1000; hmm = I.size[1] * r['um_px'] / 1000
    cells.append(dict(row=f"{NAME[r['animal']]} ({r['animal']})", fig=r.get('atlas_fig'), w_mm=wmm, h_mm=hmm, png=f'{D}/' + r['files']['whole'].replace('.svg', '.png'),
                      cap=r['pick'].split(':')[1] + (' thal.' if r['row'] == 'thalamus' else '')))
rows = [f'{NAME[a]} ({a})' for a in ORDER]
grid(cells, 'full', 11.0, 46, 1000, rows, 'PS46-55_histology_overview', 'overview')
# thalamus zooms
cells = []; zrows = []
for a in ORDER:
    th = [r for r in man.values() if r['animal'] == a and r['row'] == 'thalamus']
    if not th: continue
    for k, lab in (('zoom', '+GFAP'), ('zoom_noGFAP', 'no GFAP')):
        rn = f'{NAME[a]} ({a}) {lab}'; zrows.append(rn)
        for r in th:
            cells.append(dict(row=rn, fig=r.get('atlas_fig'), w_mm=5.8, h_mm=4.2, png=f'{D}/' + r['files'][k].replace('.svg', '.png'), cap=r['pick'].split(':')[1]))
grid(cells, 'zoom', 27.6, 115, 500, zrows, 'PS46-55_thalamus_zooms', 'zooms')
