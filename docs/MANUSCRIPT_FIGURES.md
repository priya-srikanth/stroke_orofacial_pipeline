# Manuscript figures (VLS stroke orofacial paper): locations and code

Last updated 2026-09-17.

## Where the files live

| Copy | Path | Notes |
|---|---|---|
| Local working copy (source of truth for manuscript assets) | `/Users/Priya2/Documents/Sabatini Lab/Manuscripts/VLS stroke methods paper/` | Illustrator `.ai` masters, figure decks (`VLS_stroke_figures_compilation_v*.pptx`), manuscript drafts, `overleaf_project/`, panel folders |
| Server mirror | `smb://research.files.med.harvard.edu/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper/` (mounted at `/Volumes/Priya/...` or `/Volumes/Neurobio/MICROSCOPE/Priya/...`) | Synced from local 2026-09-17 (missing files copied; stale server copies replaced with the newer local versions, except `VLS_stroke_manuscript_revised_v3.docx` where the server copy is newer). The server is slow (~150 KB/s): copy large files in resumable chunks |
| Overleaf | cloud project; bundle = `VLS_stroke_overleaf.zip` / `overleaf_project/` | Manuscript text source of truth. Re-upload to update |

Server-only items: `traj_panels_regenerated/`, `phase_panels/` (2026-09-16 regenerations, see below),
`VLS_stroke_figures_compilation_v4.pptx` (0 bytes, failed copy; no intact v4 exists locally).

## Panel folders and the code that made them

| Folder | Content | Code | Input data |
|---|---|---|---|
| `traj_panels/` | Phase-aligned first-lick / all-lick delta tongue-angle trajectories, ipsi + contra, cluster-permutation shading (June-30 originals) | Original script NOT saved (one-off session scratch). Reproduced exactly by `scripts/manuscript/plot_traj_panels.py` | `stats/results/phenotype_pooled/phase_aligned_trajectories[_all_licks]/3_tier/v3/{phenotype_pooled_phase_bin_mean_sem,trajectory_cluster_permutation_bh_fdr}.csv` |
| `traj_panels_regenerated/` (server) | Output of `plot_traj_panels.py` (same 4 manuscript panels + `extra/` for tongue x/y and raw variants) | `scripts/manuscript/plot_traj_panels.py` | as above |
| `phase_panels/` (server) | First-pass regeneration (first-lick only; smaller fonts) | `scripts/manuscript/plot_phase_traj_clustersig.py` (superseded by `plot_traj_panels.py`) | first-lick CSVs above |
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
