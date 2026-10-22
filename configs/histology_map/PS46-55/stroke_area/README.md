# PS46-55 striatal ipsi/contra % area (VLS stroke paper, Fig 1F)

- `Stroke_quantification.xlsx` — Priya's source workbook (QuPath areas per section; "Use?" = inclusion note; "Stroke area" sheet = values plotted in Fig 1F).
- `stroke_area_raw_PS46-55.csv` — the "Stroke area raw" sheet as CSV (per section: ipsi, contra and stroke-outline areas in um2, ipsi/contra %, Use?).
- `stroke_area_fig1F_PS46-55.csv` — the "Stroke area" sheet (per-animal values used for Fig 1F).
- `Stroke_area_quantification_plots.ipynb` — Priya's notebook that draws Fig 1F (and the weight plot).
- Areas come from the QuPath projects 2025_04_03_PS46-48, 2026_03_16_PS49-50, 2025_08_30_PS51-55 (Documents/data/Immuno).
  Each section has three outlines: contra striatum, surviving ipsi striatum, stroke outline. ipsi % = surviving ipsi / contra.
  Checked 2026-10-21: re-reading the QuPath projects reproduces every xlsx value exactly once ipsi vs stroke are taken
  from the xlsx areas (the stroke outline is larger than the surviving ipsi in PS54 1_19 on and PS55, so they cannot be
  told apart by size). Matched table: configs/histology_map/PS46-55/section_table.csv.
