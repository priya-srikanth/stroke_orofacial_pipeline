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
PDF = '/mnt/user-data/uploads/Documents/data/Immuno/PS92-95_widefield_stroke_cohort/lesion_map_work/paxinos_p63-98.pdf'
# target plate: (fallback plate for real data or None, interpolation allowed)
LEVELS = [(21, None, False), (23, 24, True), (25, 26, False), (27, 28, False), (29, None, False),
          (30, None, False), (31, None, False), (32, 33, False), (34, None, False)]
COLORS = dict(PS46='#1f77b4', PS47='#ff7f0e', PS48='#2ca02c', PS49='#d62728', PS50='#9467bd', PS51='#8c564b',
              PS54='#e377c2', PS55='#17becf')
real, rows = SC.footprints_from_polygons(POLY)
interp_all = copy.deepcopy(real); flags = SC.fill_gaps(interp_all)
PL = PLT.load_plates(PDF)
fig, axs = plt.subplots(1, len(LEVELS), figsize=(18, 2.9))
log = []
for ax, (f, fb, allow_interp) in zip(axs, LEVELS):
    P = PL[f]; R = PLT.raster(P); LB = PLT.left_brain_polygon(R)
    PLT.draw(ax, P, lw=0.35, color='0.25', brain=R['brain'], ppm=R['ppm'], fill_color='0.9')
    for a in sorted(COLORS):
        src, kind = None, None
        if a in real.get(f, {}): src, kind = real[f][a], 'real'
        elif fb and a in real.get(fb, {}): src, kind = real[fb][a], f'real from {PL[fb]["bregma"]:+.2f}'
        elif allow_interp and flags.get((f, a)): src, kind = interp_all[f][a], 'interpolated'
        if src is None: continue
        U = unary_union(src).intersection(LB); log.append(dict(level=P['bregma'], figure=f, animal=a, source=kind))
        for g in getattr(U, 'geoms', [U]):
            if g.is_empty or not hasattr(g, 'exterior'): continue
            x, y = g.exterior.xy
            ax.plot(x, y, color=COLORS[a], lw=1.2 if kind != 'interpolated' else 0.9,
                    ls=(0, (2.5, 1.5)) if kind == 'interpolated' else '-', solid_joinstyle='round')
    yy, xx = np.nonzero(R['brain']); pp = R['ppm']
    ax.set_xlim(xx.min() / pp - 6.1, 0.15); ax.set_ylim(yy.max() / pp + 0.1, yy.min() / pp - 0.1)
    ax.set_title(f"{P['bregma']:+.2f} mm", fontsize=9)
h = [Line2D([0], [0], color=COLORS[a], lw=1.6, label=a) for a in sorted(COLORS)]
if any(r['source'] == 'interpolated' for r in log):
    h.append(Line2D([0], [0], color='0.3', lw=0.9, ls=(0, (2.5, 1.5)), label='interpolated'))
fig.legend(handles=h, loc='lower center', ncol=len(h), frameon=False, fontsize=8)
plt.tight_layout(rect=(0, 0.08, 1, 0.94), w_pad=0.2)
for e in ('png', 'svg', 'pdf'): fig.savefig(f'{OUT}.{e}', dpi=400)
json.dump(log, open(f'{OUT}_sources.json', 'w'), indent=1)
import collections
for lv in collections.OrderedDict((r['level'], 1) for r in log):
    print(f"{lv:+.2f}", '; '.join(f"{r['animal']}{'' if r['source']=='real' else ' ('+r['source']+')'}" for r in log if r['level'] == lv))
