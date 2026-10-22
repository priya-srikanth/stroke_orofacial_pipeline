# PS46-55 histology panels
Run on the Mac (reads the VS200 scans from MICROSCOPE and Byungwoo's LB-Priya folder):
1. `par.py OUTDIR N` renders whole sections (jobs in configs/histology_map/PS46-55/histology_panels/jobs_final.json).
2. `zoom2.py OUTDIR thal_align_all.json` exports the thalamus zooms from Priya's box placements.
3. `plate_svgs.py` (cloud: needs the Paxinos PDFs and the v3 outlines) writes plates/plate_full_fig*.svg and plate_zoom_fig*.svg.
4. `compose_grid.py OUTDIR` assembles PS46-55_histology_overview.* and PS46-55_thalamus_zooms.*.
`render.py` reads .ets tiles directly (channels 0-2 only); `compose.py`/`build.py` hold the display rules.
