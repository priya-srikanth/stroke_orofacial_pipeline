"""VLS manuscript stroke-extent figure, PS46-55: nine Paxinos levels, coloured outlines per animal.
Per level and animal: the real section on that plate; else a real section from the named neighbouring plate
(drawn on the target plate in the same mm coordinates); else, where allowed, the signed-distance interpolation."""
import sys, json, copy
sys.path.insert(0, '/home/claude/widefield_pipeline')
import numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from shapely.ops import unary_union
from wfield_local.histology_map import schematic as SC, plates as PLT
matplotlib.rcParams.update({'svg.fonttype': 'none', 'pdf.fonttype': 42, 'font.size': 8})
POLY, OUT = sys.argv[1], sys.argv[2]
COHORT = sys.argv[3] if len(sys.argv) > 3 else 'PS46-55'
SCHEME = sys.argv[4] if len(sys.argv) > 4 else 'animal'
FILL = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
INTERP_ALL = len(sys.argv) > 6 and sys.argv[6] == 'interp'   # fill any remaining gap between an animal's labelled sections (dashed)   # alpha of a light fill under each outline (0 = none)   # 'severity': paper phenotype colours
PDF = '/mnt/user-data/uploads/Documents/data/Immuno/PS92-95_widefield_stroke_cohort/lesion_map_work/paxinos_p63-98.pdf'
# target plate: (fallback plate for real data or None, interpolation allowed)
LEVELS = [(21, None, False), (23, 24, True), (25, 26, False), (27, 28, False), (29, None, False),
          (30, None, False), (31, None, False), (32, 33, False), (34, None, False)]
COLORS = dict(PS46='#1f77b4', PS47='#ff7f0e', PS48='#2ca02c', PS49='#d62728', PS50='#9467bd', PS51='#8c564b',
              PS54='#e377c2', PS55='#17becf')
if COHORT == 'PS92-95':   # Priya 2026-10-22: +0.86, +0.62, +0.38 (from +0.50), +0.26 (from +0.14), +0.02, -0.10
    LEVELS = [(24, None, False), (26, None, False), (28, 27, False), (29, 30, False), (31, None, False), (32, None, False)]
    from wfield_local import config
    COLORS = config.animal_color()
STYLE = {a: '-' for a in COLORS}
if SCHEME == 'severity':   # VLS paper phenotype groups + manuscript colours (scripts/manuscript/*: mild #f2c12e, moderate #f0822e, severe #b4001e)
    import colorsys
    from matplotlib.colors import to_rgb
    GROUPS = {'mild': ['PS47', 'PS48', 'PS49', 'PS50'], 'moderate': ['PS46', 'PS51'], 'severe': ['PS54', 'PS55']}
    BASE = {'mild': '#f2c12e', 'moderate': '#f0822e', 'severe': '#b4001e'}
    if FILL:   # Priya 10-22: brighter, more lemon yellow for mild in the filled version so it separates from moderate orange
        BASE['mild'] = '#ffd60a'
    DASH = ['-', (0, (5, 1.6)), (0, (1.2, 1.2)), (0, (5, 1.4, 1.2, 1.4))]
    COLORS, STYLE = {}, {}
    for g, animals in GROUPS.items():
        h, l, s_ = colorsys.rgb_to_hls(*to_rgb(BASE[g]))
        for i, a in enumerate(animals):
            dl = (i - (len(animals) - 1) / 2) * 0.07          # small lightness steps around the paper colour
            COLORS[a] = colorsys.hls_to_rgb(h, min(max(l - dl, 0.15), 0.8), s_); STYLE[a] = DASH[i]
EXTRA_FB = {}   # (was PS51 at -0.10 from +0.02; replaced by the real PS51_2_10 section, 2026-10-22)
HATCH = ['|||', '---', '\\\\\\', '///']
matplotlib.rcParams['hatch.linewidth'] = 0.6
real, rows = SC.footprints_from_polygons(POLY)
interp_all = copy.deepcopy(real); flags = SC.fill_gaps(interp_all)
PL = PLT.load_plates(PDF)
NC = int(np.ceil(len(LEVELS) / 2))   # Priya 10-22: two rows
fig, axs = plt.subplots(2, NC, figsize=(2.3 * NC, 6.6)); axs = axs.ravel()
for ax in axs[len(LEVELS):]: ax.axis('off')
log = []
for ax, (f, fb, allow_interp) in zip(axs, LEVELS):
    P = PL[f]; R = PLT.raster(P); LB = PLT.left_brain_polygon(R)
    PLT.draw(ax, P, lw=0.35, color='0.25', brain=R['brain'], ppm=R['ppm'], fill_color='0.9')
    for a in (sorted(COLORS, key=lambda a: -list(COLORS).index(a)) if SCHEME == 'severity' else sorted(COLORS)):
        src, kind = None, None
        if a in real.get(f, {}): src, kind = real[f][a], 'real'
        elif fb and a in real.get(fb, {}): src, kind = real[fb][a], f'real from {PL[fb]["bregma"]:+.2f}'
        elif (f, a) in EXTRA_FB and a in real.get(EXTRA_FB[(f, a)], {}):
            src, kind = real[EXTRA_FB[(f, a)]][a], f'real from {PL[EXTRA_FB[(f, a)]]["bregma"]:+.2f}'
        elif (allow_interp or INTERP_ALL) and flags.get((f, a)): src, kind = interp_all[f][a], 'interpolated'
        if src is None: continue
        U = unary_union(src).intersection(LB); log.append(dict(level=P['bregma'], figure=f, animal=a, source=kind))
        for g in getattr(U, 'geoms', [U]):
            if g.is_empty or not hasattr(g, 'exterior'): continue
            x, y = g.exterior.xy
            if FILL and kind != 'interpolated' and not (SCHEME == 'severity' and a not in GROUPS['mild'] + GROUPS['moderate'][:1]):   # Priya 10-22: fill mild only
                grp = next((g for g, an in GROUPS.items() if a in an), None) if SCHEME == 'severity' else None
                if grp == 'mild':   # Priya 10-22: hatched fill, one direction per mild animal (#1 vertical, #2 horizontal, #3 up-left, #4 up-right)
                    ax.fill(x, y, facecolor='none', edgecolor=COLORS[a], hatch=HATCH[GROUPS['mild'].index(a)], lw=0, alpha=0.5)
                elif a == GROUPS['moderate'][0]:   # Priya 10-22: sparse dots for Moderate #1
                    ax.fill(x, y, facecolor='none', edgecolor=COLORS[a], hatch='o', lw=0, alpha=0.6)   # lighter under the big severe strokes so the small mild/moderate ones stay readable
            ax.plot(x, y, color=COLORS[a], lw=(1.4 if SCHEME == 'severity' else 1.2) if kind != 'interpolated' else 1.4,
                    ls=STYLE[a], alpha=0.4 if kind == 'interpolated' else 0.75,   # Priya 10-22: more transparent so overlaps show
                    solid_joinstyle='round')   # interpolated = same line style, faded
    yy, xx = np.nonzero(R['brain']); pp = R['ppm']
    ax.set_xlim(xx.min() / pp - 6.1, 0.15); ax.set_ylim(yy.max() / pp + 0.1, yy.min() / pp - 0.1)
    ax.set_title(f"{P['bregma']:+.2f} mm", fontsize=9)
if SCHEME == 'severity':
    from matplotlib.patches import Patch
    h = [(Patch(facecolor='none', edgecolor=COLORS[a], hatch=(HATCH[i] if g == 'mild' else 'o'), lw=1.4, ls=STYLE[a], label=f'{g.capitalize()} #{i + 1}') if (FILL and (g == 'mild' or (g == 'moderate' and i == 0))) else
          Line2D([0], [0], color=COLORS[a], lw=1.8, ls=STYLE[a], label=f'{g.capitalize()} #{i + 1}')) for g, an in GROUPS.items() for i, a in enumerate(an)]
    json.dump({f'{g.capitalize()} #{i + 1}': a for g, an in GROUPS.items() for i, a in enumerate(an)}, open(f'{OUT}_animal_key.json', 'w'), indent=1)
else:
    h = [Line2D([0], [0], color=COLORS[a], lw=1.6, label=a) for a in sorted(COLORS)]
# Origin of every shape that is not a section cut at that level (Priya 10-22: text, not a grey legend line)
NAME = ({a: f'{g.capitalize()} #{i + 1}' for g, an in GROUPS.items() for i, a in enumerate(an)} if SCHEME == 'severity' else {a: a for a in COLORS})
notes = []
for lv in sorted({r['level'] for r in log}, reverse=True):
    parts = [f"{NAME[r['animal']]} " + ('interpolated (faded)' if r['source'] == 'interpolated' else r['source'].replace('real from', '(section at') + ' mm)')
             for r in sorted(log, key=lambda r: list(NAME).index(r['animal'])) if r['level'] == lv and r['source'] != 'real']
    if parts: notes.append(f"{lv:+.2f} mm: " + ', '.join(parts))
NOTE = notes
H0 = fig.get_figheight(); EXTRA = 0.2 * (len(NOTE) + 1) if NOTE else 0.0
fig.set_figheight(H0 + EXTRA)
fb = EXTRA / (H0 + EXTRA)                        # fraction of the figure taken by the origin notes
fig.legend(handles=h, loc='lower center', ncol=int(np.ceil(len(h) / 2)), frameon=False, fontsize=8, handlelength=3.2, bbox_to_anchor=(0.5, fb))
if NOTE:
    fig.text(0.5, fb - 0.01, 'Outlines are sections cut at the labelled level, except:', ha='center', va='top', fontsize=7.5, color='0.15')
    for i, line in enumerate(NOTE):
        fig.text(0.5, fb - 0.01 - (i + 1) * 0.2 / (H0 + EXTRA), line, ha='center', va='top', fontsize=7.5, color='0.25')
plt.tight_layout(rect=(0, fb + 0.5 / (H0 + EXTRA), 1, 0.98), w_pad=0.2, h_pad=4.0)
fig.subplots_adjust(hspace=0.32)   # room for the AP labels between rows
for e in ('png', 'svg', 'pdf'): fig.savefig(f'{OUT}.{e}', dpi=400)
json.dump(log, open(f'{OUT}_sources.json', 'w'), indent=1)
import collections
for lv in collections.OrderedDict((r['level'], 1) for r in log):
    print(f"{lv:+.2f}", '; '.join(f"{r['animal']}{'' if r['source']=='real' else ' ('+r['source']+')'}" for r in log if r['level'] == lv))
