"""PS46-55 stroke schematic from Priya's hand-edited atlas polygons (mm, plate frame) with her AP review picks."""
import sys, json, glob, copy
sys.path.insert(0, '/home/claude/widefield_pipeline')
from shapely.geometry import Polygon
from wfield_local.histology_map import schematic as SC
POLY = sys.argv[1]; CHO = sys.argv[2]; OUT = sys.argv[3]; STYLE = sys.argv[4] if len(sys.argv) > 4 else "filled"
P = {}
for f in glob.glob(POLY + '/*.json'):
    d = json.load(open(f)); d = d.get('data', d); P[d['section_id']] = d
for f in glob.glob(CHO + '/*.json'):
    d = json.load(open(f)); d = d.get('data', d); P[d['section_id']]['figure'] = d['figure']
byplate, rows = {}, []
for k, d in sorted(P.items()):
    if d.get('exclude'): continue
    g = Polygon(d['poly']).buffer(0)
    byplate.setdefault(int(d['figure']), {}).setdefault(d['animal'], []).append(g)
    rows.append(dict(section=k, name=d.get('name', k), animal=d['animal'], figure=int(d['figure']), area_mm2=round(g.area, 3)))
SC.footprints = lambda sections, masks_dir: (copy.deepcopy(byplate), rows)
PDF = '/mnt/user-data/uploads/Documents/data/Immuno/PS92-95_widefield_stroke_cohort/lesion_map_work/paxinos_p63-98.pdf'
colors = dict(PS46='#1f77b4', PS47='#ff7f0e', PS48='#2ca02c', PS49='#d62728', PS50='#9467bd', PS51='#8c564b', PS54='#e377c2', PS55='#17becf')
r, interp = SC.render({}, None, PDF, colors, OUT, 'Stroke extent, PS46-55 (lesion left; Paxinos & Franklin outlines)', ncol=5, style=STYLE)
json.dump(rows, open(OUT + '_sections.json', 'w'), indent=1)
print(sorted(byplate), 'interp', len(interp))
