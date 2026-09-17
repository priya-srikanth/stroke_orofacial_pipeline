# Manuscript figures (VLS stroke orofacial paper): locations and code

Last updated 2026-09-17.

## Where the files live

| Copy | Path | Notes |
|---|---|---|
| Local working copy (source of truth for manuscript assets) | `/Users/Priya2/Documents/Sabatini Lab/Manuscripts/VLS stroke methods paper/` | Illustrator `.ai` masters, figure decks (`VLS_stroke_figures_compilation_v*.pptx`), manuscript drafts, `overleaf_project/`, panel folders |
| Server mirror | `smb://research.files.med.harvard.edu/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper/` (mounted at `/Volumes/Priya/...` or `/Volumes/Neurobio/MICROSCOPE/Priya/...`) | Synced from local 2026-09-17 (missing files copied; stale server copies replaced with the newer local versions, except `VLS_stroke_manuscript_revised_v3.docx` where the server copy is newer). The server is slow (~150 KB/s): copy large files in resumable chunks |
| Overleaf | cloud project; bundle = `VLS_stroke_overleaf.zip` / `overleaf_project/` | Manuscript text source of truth. Re-upload to update |

Server-only items: `traj_panels_regenerated/`, `phase_panels/` (2026-09-16 regenerations; see
"Phase-aligned trajectory figures" below),
`VLS_stroke_figures_compilation_v4.pptx` (0 bytes, failed copy; no intact v4 exists locally).

## Panel folders and the code that made them

| Folder | Content | Code | Input data |
|---|---|---|---|
| Trajectory folders (`traj_panels*/`, `phase_panels/`) | Phase-aligned tongue trajectories | See "Phase-aligned trajectory figures" below | |
| `meanSEM_sig_panels/`, `meanSEM_abs_panels/`, `median_CI_panels_v3/`, `angle_panels/` | Per-epoch endpoint panels (mean +/- SEM with `**` significance, absolute, median + CI, tongue-angle scalars) | Not in repo (session scratch; see each folder's README for the conventions) | `stats/results/phenotype_pooled/pooled_phenotype_stats` (3-tier) + per-session metric tables |
| `vector_main_figures/`, `histology_panels/`, `severity_figures/`, `vfss_examples/` | Assembled main/supp figures, histology montages, severity clustering, VFSS examples | Not in repo, except: severity PNGs match `scripts/run_severity_figures.py` outputs (SVG versions were a session export); VFSS from `~/Github/mouse_vfss` | various |

### Rerun the trajectory panels

```bash
python3 scripts/manuscript/plot_traj_panels.py \
  <outputs>/stats/results/phenotype_pooled  <out_dir>
```

Style (measured from the June-30 SVGs): title 24 bold, column titles 21, row labels / x-label 18,
ticks 15, n-labels 12, y-label 19, caption 13; mean lw 2.6, SEM band alpha 0.25, shading alpha 0.16;
colors mild `#f2c12e`, moderate `#f0822e`, severe `#b4001e`.
Shading = clusters with `reject == True` (Maris-Oostenveld cluster permutation vs pre-stroke, BH-FDR q<0.05).

### Metric definitions used in these figures
- Tongue angle: signed angle between eye-midpoint→spout-midpoint and eye-midpoint→tongue
  (`src/stroke_orofacial/dlc_kinematics/_angle.py`, `sign_flip = -1`, 8 ms Gaussian smoothing).
- d′ / criterion c: `src/stroke_orofacial/spout_behavior/sdt.py`.

## Phase-aligned trajectory figures: versions, provenance, manuscript choice (2026-09-17)

All sets plot the same data: 3-tier phenotypes, v3 substrate (v7-cleaned tongue trace +
filtered_v1 DLC trial/session filters), phase-bin mean +/- SEM across trials from
`stats/results/phenotype_pooled/phase_aligned_trajectories[_all_licks]/3_tier/v3/phenotype_pooled_phase_bin_mean_sem.csv`.
They differ in the shading (which significance test, if any), the variant plotted, and the style.

| Set | Where | Variant(s) | Shading (stats file) | Made by | Status |
|---|---|---|---|---|---|
| Pipeline renders | `stats/figures/phenotype_pooled/phase_aligned_trajectories[_all_licks]/3_tier/v3/` (+ `sd_band/`) | delta + raw; angle, x, y | none | `figures/phase_aligned_trajectories.py` via `scripts/chore_dlc_pooled_phenotype/q13_traj_v2_emit.py` | QC / archive; not manuscript style |
| **June-30 originals** | `vls_stroke_paper/traj_panels/` (local + server) | delta, tongue angle only (first-lick / all-lick x ipsi / contra) | pooled cluster permutation (`trajectory_cluster_permutation_bh_fdr.csv`) | one-off session script (not saved) | **Manuscript Figure 3 R-U** (placed in `DLC.ai`) |
| Regenerated originals | `vls_stroke_paper/traj_panels_regenerated/` (server only) | delta angle (4 panels) + `extra/` (x, y, raw) | pooled (same CSV) | `scripts/manuscript/plot_traj_panels.py` (default `--test pooled`) | Reproduces the originals (same data, shading, style); use to rebuild or edit |
| First-pass regeneration | `vls_stroke_paper/phase_panels/` (server only) | delta + raw, first-lick only | pooled (same CSV) | `scripts/manuscript/plot_phase_traj_clustersig.py` | Superseded (smaller fonts); do not use |
| Within-animal sensitivity | `vls_stroke_paper/traj_panels_within_animal/` (local + server) | delta angle (4 panels) + `extra/` (x, y, **raw**) | within-animal cluster permutation (`trajectory_cluster_permutation_within_animal_bh_fdr.csv`, rows `variant == delta` or `raw`) | `plot_traj_panels.py --test within_animal`; stats from `scripts/manuscript/run_within_animal_cluster_perm.py` | Supplementary / sensitivity |

Stats files (both in each `3_tier/v3/` results dir; each holds raw and delta rows, all signals):
- `trajectory_cluster_permutation_bh_fdr.csv`: pooled shuffle (labels exchanged across animals), Welch t per bin, |t| > 2, mixed-sign clusters, p = k/N, BH-FDR across the family. Published.
- `trajectory_cluster_permutation_within_animal_bh_fdr.csv`: labels exchanged only within each animal, animal-balanced t, same-sign clusters, p = (1+k)/(1+N), BH-FDR across the family; adds `n_animals`, `min_attainable_p`.
- Substrate cache for reruns: `trial_bin_substrate.parquet` (same dirs).

How the shading differs:
- **Delta, pooled vs within-animal:** every manuscript window is significant under both, with near-identical extents. Exception worth knowing: first-lick, moderate, contralesional, sub-acute, bins 32-47 (phase ~0.44-0.67) are not significant within-animal because PS46 (about -2 deg) and PS51 (about +4.8 deg) move in opposite directions and the pooled test is dominated by PS51's 10 sub-acute sessions (PS46 has 3). Other small changes: severe contra chronic 0-71 -> 17-71; mild contra sub-acute 13-71 -> 15-54; all-lick mild contra sub-acute 0-71 -> 1-22 + 49-71.
- **Raw vs delta, within-animal:** identical clusters (a per-animal, per-bin baseline cancels in within-animal contrasts). Only the curves differ: raw curves are pooled across animals without baseline removal, so the pre-stroke curve is not flat (about -2 deg mid-phase in mild/moderate) and the mean can shift when the animal mix changes between epochs.
- **Raw, pooled:** not valid inference (between-animal offsets enter the pooled shuffle); never shade raw curves with the pooled CSV.

### Manuscript choice (decided 2026-09-17)
- **Main text, Figure 3 R-U:** delta tongue angle with **pooled** shading (`traj_panels/`, reproducible with `plot_traj_panels.py`). Methods describe the pooled test and its null calibration.
- **Sensitivity (Methods sentence and/or Supplement):** within-animal delta panels (`traj_panels_within_animal/`), stating that all shaded windows survive, and noting that the moderate contralesional sub-acute mid-phase window is carried by PS51.
- **Raw angle trajectories:** not in the main figures. If shown (Supplement, absolute angle), use only `traj_panels_within_animal/extra/traj_*_angle_deg_raw_*` (within-animal shading).
- Do not use `phase_panels/` or the unshaded pipeline renders in the manuscript.

## Trajectory significance tests

- **Pooled shuffle (current CSVs, headline)**: `compute_trajectory_cluster_permutation_stats`
  (`figures/phase_aligned_trajectories.py`) permutes pre/post session labels across animals,
  but the plotted/tested `delta` variant is already within-animal adjusted (each animal's
  own pre-stroke baseline per side x phase bin is subtracted), and the Q13 null calibration
  (DECISIONS 2026-05-28, labels shuffled within animal) gave 0% false positives.
  Simulations at the cohort's real session counts (2026-09-17) agreed: delta variant pooled
  test 0-2/20 false positives. It is only anticonservative for the RAW variant with
  between-animal offsets (20/20), or with extreme imbalance plus very few pre sessions per
  animal (8/20 at 2 pre / 10 post). Do not use raw-variant clusters for inference.
- **Within-animal shuffle (sensitivity analysis, optional)**: `stats/trajectory_within_animal_cluster.py`.
  Session unit (trials averaged), animal-balanced per-bin t with pooled within-animal
  variance, labels shuffled only within each animal, same-sign clusters,
  p = (1+k)/(1+N), BH-FDR over the same family. Inference is conditional on the
  animals studied (n = 2-4 per 3-tier phenotype).
  Run on the Mac (needs the raw session substrate; ~30-60 min per lick set,
  cached to `trial_bin_substrate.parquet` for reruns):
  `python -m scripts.manuscript.run_within_animal_cluster_perm --lick-set both`
  then `python scripts/manuscript/plot_traj_panels.py <stats/results/phenotype_pooled> <out> --test within_animal`.
  Tests: `tests/test_trajectory_within_animal_cluster.py`.

## Wasserstein (W-2) self-inclusion bias (2026-09-17)

Published per-session W-2 (`<scope>/v2/`) compares each PRE session against a pre pool
that includes that session, biasing pre W-2 toward 0. Sensitivity (3-tier, inflating
pre W-2 by the convexity lower bound sqrt(n/(n-1))): 157 -> 155 significant cells
(4 lost: jaw mild contra sub-acute raw + normalized, eye mild acute, whisker severe ipsi
sub-acute; 2 gained: eye moderate sub-acute/chronic); no tongue cell changed. With a
x1.25 inflation, 29 cells are lost, including mild tongue, so run the exact version:

```bash
python -m scripts.chore_dlc_pooled_phenotype.q12_v2_emit --remap-phenotypes both --w2-pre-leave-one-out
python -m scripts.chore_whisker_nose_spatial.emit_cohort --cohort-scope both --w2-pre-leave-one-out
python scripts/phase_9_stats/build_pooled_phenotype_stats.py --w2-version v2_loo
```
Writes `<scope>/v2_loo/` and `pooled_phenotype_stats_w2loo.csv`; published files untouched.

## Manuscript statistics wording (2026-09-17)

Methods/legends corrected to match the code (effect = post - pre difference in session
means with an unpaired session bootstrap, not a "median paired difference"; explicit
within-animal baseline correction; null-calibration evidence; cluster-permutation details;
W-2 bias statement). Updated: `overleaf_project/main.tex` + `references.bib` (maris2007),
`VLS_stroke_manuscript_compiled_v2.pdf`, `VLS_stroke_overleaf_v2.zip`,
`VLS_stroke_manuscript_revised_v6.docx`, `meanSEM_sig_panels/README.txt` (local and server).
Pre-edit copies: `overleaf_backup_2026-09-17/`. Not updated (need Illustrator): the
"bootstrap CI of the median ... difference" footer baked into `Figure1_behavior.pdf`
(Behavior.ai) and the matplotlib footers in `vector_main_figures/*.svg`.

## Within-animal sensitivity for scalar `**` (2026-09-17)

`build_pooled_phenotype_stats.py --within-animal` adds `wa_*` columns (see DECISIONS
2026-09-17). Scalar + W-2 result (3-tier): 544 shared calls, 26 published-only,
54 within-animal-only (34 of them with animals moving in opposite directions);
92 of 570 published `**` calls have direction disagreement among animals. File:
`stats/results/phenotype_pooled/3_tier/pooled_phenotype_stats_within_animal_scalar_w2_only.csv`.

## Results-text corrections (2026-09-17, v7)

See DECISIONS 2026-09-17 "Manuscript consequences". Files: `VLS_stroke_manuscript_revised_v7.docx`,
`VLS_stroke_manuscript_compiled_v3.pdf`, `VLS_stroke_overleaf_v3.zip`, `overleaf_project/main.tex`
(pre-edit copy: `overleaf_backup_2026-09-17/main_after_stats_wording.tex`). Local and server match.

## Within-animal trajectory shading (2026-09-17)

Ran `run_within_animal_cluster_perm.py --lick-set both` (cached substrate:
`trial_bin_substrate.parquet` in each `3_tier/v3/` results dir). All manuscript shaded
windows survive with near-identical extents (details in DECISIONS 2026-09-17). Figures:
`vls_stroke_paper/traj_panels_within_animal/` (made with `plot_traj_panels.py --test within_animal`).

## Figure 1 / Figure 3 legend update (2026-09-17)

Legends edited in `Behavior.ai` / `DLC.ai`; `overleaf_project/figures/Figure1_behavior.pdf` and
`Figure3_dlc.pdf` regenerated from the .ai files (Ghostscript pdfwrite; previous versions in
`overleaf_backup_2026-09-17/`). Figure 3 was re-lettered (J-K first-lick timing, L-M within-bout ILI,
N-Q angle scalars, R-U trajectories); main.tex + docx legends updated to match.
Current versions: `VLS_stroke_manuscript_revised_v8.docx`, `VLS_stroke_manuscript_compiled_v5.pdf`,
`VLS_stroke_overleaf_v5.zip`.

Current manuscript versions (2026-09-17, after the full within-animal run): `VLS_stroke_manuscript_revised_v9.docx`, `VLS_stroke_manuscript_compiled_v6.pdf`, `VLS_stroke_overleaf_v6.zip`.

After the full W-2 leave-one-out run: `VLS_stroke_manuscript_revised_v10.docx`, `VLS_stroke_manuscript_compiled_v7.pdf`, `VLS_stroke_overleaf_v7.zip` (occupancy reported with the LOO reference).

## W-2 occupancy panels, leave-one-out (2026-09-17)

`scripts/manuscript/plot_w2_meansem_panels.py` rebuilds the manuscript `meanSEM_sig_panels`
style for the W-2 families (the original W-2 panel script was never saved; `wass_panels/` is
empty). Style measured from `meanSEM_sig_panels/*.svg`: title 14 bold, subtitles 7 italic,
panel titles 13, ticks 13, axis labels 15, `**` 12, legend 10; colors mild `#f2c12e`,
moderate `#f0822e`, severe `#b4001e`; session dots alpha 0.16; `**` stacked severe/moderate/mild.

```bash
python scripts/manuscript/plot_w2_meansem_panels.py \
  <outputs>/stats/results/phenotype_pooled pooled_phenotype_stats_w2loo_within_animal.csv \
  <out_dir> [--w2-version v2_loo] [--sig-col headline_and_bootstrap_sig|wa_sig]
```

Outputs (local + server): `vls_stroke_paper/wass_panels_loo/meanSEM_<family>_<bodypart>.{svg,png,pdf}`
for all six bodyparts, raw and normalized, plus the script and a README.
Deck: `VLS_stroke_figures_compilation_v9.pptx` = v8 with the five W-2 slides (22, 65-68:
tongue raw + normalized, jaw, nose, whisker) swapped to the `v2_loo` pipeline figures and their
slide notes repointed to `3_tier/v2_loo/`. Figure 3 H/I in `DLC.ai` still holds the published
(v2) panels — swap in `wass_panels_loo/meanSEM_wasserstein_recovery_tongue.svg` in Illustrator.
