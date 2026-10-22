# PS46-55 stroke-extent schematic (VLS stroke paper)

Built with Priya 2026-10-21/22. Outputs: `MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper/stroke_schematic/`
and the local paper folder `VLS stroke methods paper/stroke_schematic/`.

**Published footprints = `configs/histology_map/PS46-55/atlas_polygons/`**, Priya's hand-edited shapes on the
Paxinos plates (one JSON per section; `figure` = plate number after her ±2 level review; `ap_review_from` = the
level before review). Render with `scripts/vls_stroke_schematic/render_schematic.py`.

How they were made (scripts in `scripts/vls_stroke_schematic/`, working copies; they read crops and QuPath
projects from Priya's Mac):
- Sections: the 47 sections listed in `Stroke quantification.xlsx` (QuPath projects 2025_04_03_PS46-48,
  2026_03_16_PS49-50, 2025_08_30_PS51-55), table in `configs/histology_map/PS46-55/section_table.csv`. Each section
  has three outlines (contra striatum, surviving ipsi striatum, stroke). The stroke outline can be LARGER than the
  surviving ipsi (PS54 1_19 on, PS55) — never assign them by area alone.
- Level-4 VS200 crops (5.2 um/px); lesion flipped to the left; midline from the dorsal fissure.
- Automatic starting footprint: Priya's stroke outline grown into the lost striatum (contra minus surviving ipsi)
  until area-matched, cheapest laterally / dorsolaterally, a little ventral, confined to the ipsi striatal
  territory. Placement: contra-hemisphere scale, translated so the ipsi striatum's lateral border meets the
  plate CPu's lateral border.
- Priya then edited every shape in the atlas editor (`atlas_editor_template.html`) and reviewed levels in
  `level_review_template.html`. Her rules: lateral stroke edge at the striatum's lateral border (corpus callosum /
  external capsule); blob extending dorsolaterally from the core, only a touch ventral; never a crescent.
