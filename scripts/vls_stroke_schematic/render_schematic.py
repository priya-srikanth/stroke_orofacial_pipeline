"""PS46-55 stroke-extent schematic (VLS stroke paper) from Priya's hand-edited atlas polygons.

    python scripts/vls_stroke_schematic/render_schematic.py <out_stem> [outline]

Draws configs/histology_map/PS46-55/atlas_polygons/*.json (plate mm; x from midline, negative = left; y from page
top) onto outline-only Paxinos & Franklin plates, animals overlaid with transparency, levels between an animal's
measured sections filled by signed-distance interpolation (dashed). Plate drawing / interpolation come from
widefield_pipeline's wfield_local.histology_map (installed alongside); the atlas PDF path is PAXINOS_PLATES_PDF.
"""
import os, sys
from pathlib import Path
from wfield_local.histology_map import schematic as SC
REPO = Path(__file__).resolve().parents[2]
PDF = os.environ.get('PAXINOS_PLATES_PDF',
                     '/Users/Priya2/Documents/data/Immuno/PS92-95_widefield_stroke_cohort/lesion_map_work/paxinos_p63-98.pdf')
COLORS = dict(PS46='#1f77b4', PS47='#ff7f0e', PS48='#2ca02c', PS49='#d62728', PS50='#9467bd', PS51='#8c564b',
              PS54='#e377c2', PS55='#17becf')
if __name__ == '__main__':
    SC.render({}, None, PDF, COLORS, sys.argv[1], 'Stroke extent, PS46-55 (lesion left; Paxinos & Franklin outlines)',
              ncol=5, polygons_dir=REPO / 'configs/histology_map/PS46-55/atlas_polygons',
              style=sys.argv[2] if len(sys.argv) > 2 else 'filled')   # 'outline': coloured outlines, interpolated levels dashed
