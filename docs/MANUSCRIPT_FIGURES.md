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

Panel geometry (2026-09-17): the panels are sized to be drop-in replacements inside the
multi-panel `.ai` files. Canvas and axes fractions are copied from `meanSEM_sig_panels/*.svg`:
720.0 x 331.2 pt with axes at left 0.110 / 0.49469 and width 0.30531 for two-side endpoints,
424.8 x 331.2 pt with axes at left 0.185 and width 0.47500 for the single-panel ones
(eye, spout); both use bottom 0.145, height 0.575, and the legend "center left" at x 0.82
(two-panel) or 0.70 (one-panel). `tight_layout` and `bbox_inches="tight"` are deliberately not
used, since either resizes the canvas (the first pass came out 773.5 x 332.9 pt). The
first-pass files are kept in `wass_panels_loo/superseded_tightbbox/`.

Outputs (local + server): `vls_stroke_paper/wass_panels_loo/meanSEM_<family>_<bodypart>.{svg,png,pdf}`
for all six bodyparts, raw and normalized, plus the script and a README.
Deck: `VLS_stroke_figures_compilation_v9.pptx` = v8 with the five W-2 slides (22, 65-68:
tongue raw + normalized, jaw, nose, whisker) swapped to the `v2_loo` pipeline figures and their
slide notes repointed to `3_tier/v2_loo/`. Figure 3 H/I in `DLC.ai` still holds the published
(v2) panels — swap in `wass_panels_loo/meanSEM_wasserstein_recovery_tongue.svg` in Illustrator.

## Archive of retired material (2026-09-17)

`vls_stroke_paper/_archive_2026-09-17/` (local and server) holds everything retired from the
working folder. Nothing was deleted; each item can be moved back. See its README for the
full list. Summary:

* `manuscript_versions/` - every build older than the current one: docx v3-v9, compiled PDFs
  (unversioned and v2-v7), overleaf zips (unversioned and v2-v7), figure decks v2, v3, v4, v7, v8.
  Current and left in place: `VLS_stroke_manuscript_revised_v11.docx` (with v10),
  `VLS_stroke_manuscript_compiled_v8.pdf`, `VLS_stroke_overleaf_v8.zip`,
  `VLS_stroke_figures_compilation_v9.pptx`.
* `panels/` - `meanSEM_sig_panels` (-> `_v2`), `angle_panels` (-> `_v2`), `median_CI_panels`,
  `_v2`, `_v3` (obsolete median+CI convention), `meanSEM_abs_panels` (not in the manuscript;
  regenerate with `--absolute`), and the server-only `phase_panels`,
  `traj_panels_regenerated`, `wass_panels`. Also the `superseded_tightbbox_*` first-pass
  renders whose canvas was a few points off the published size.
* `drafts/` - the draft figure deck, the two methods drafts and the paper outline.

Six stale Office/Illustrator lock files (`~$*.docx`, `~$*.pptx`, `~ai-*.tmp`) were deleted
rather than archived; they hold no content. `fr_stroke menu of options.pptx` was kept in the
working folder at Priya's request.

The working folder is now 479 MB (was 863 MB) and every remaining figure folder is either
current or has a saved generator.

## Figure-code audit (2026-09-17)

Every manuscript figure panel now has code in this repo that regenerates it.

| folder in `vls_stroke_paper/` | manuscript panels | generator |
|---|---|---|
| `meanSEM_sig_panels_v2` | Fig 1 SDT, Fig 3 B-M | `scripts/manuscript/plot_scalar_meansem_panels.py` |
| `angle_panels_v2` | Fig 3 N-Q | same script, `--family phase_aligned_endpoints[_all_licks]` |
| `wass_panels_loo` | Fig 3 H, I | `scripts/manuscript/plot_w2_meansem_panels.py` |
| `traj_panels`, `traj_panels_within_animal` | Fig 3 R-U | `scripts/manuscript/plot_traj_panels.py` (+ `run_within_animal_cluster_perm.py`) |
| `recovered_panels` | Fig 1 F/G, Fig 2 VFSS quant, Fig S5 | `scripts/manuscript/plot_recovered_panels.py` (data via `extract_svg_series.py`) |
| `severity_figures` | Supp S2-S4 | `scripts/run_severity_figures.py` |
| `meanSEM_abs_panels` | not used in the manuscript | `plot_scalar_meansem_panels.py --absolute` |
| `median_CI_panels_v3` | superseded by the meanSEM convention | not rebuilt (obsolete convention) |
| `histology_panels` | Fig 1 histology | photomicrographs: no code can regenerate the images; the montage lives in `.ai` |

The pipeline-side figures (`stats/figures/...`) have always had code under
`src/stroke_orofacial/figures/` and the `scripts/phase_*` emitters; the table above is about
the manuscript-specific renders.

### Why the angle panels have no severe acute point (2026-09-17)

PS51, PS54 and PS55 have **zero acute sessions that pass the DLC session QC gate**
(`stats.dlc_session_filter.dlc_tongue_trajectory_metrics.min_trials_with_detected_lick = 10`,
tongue, v7 DLC-detected licks). Acutely those animals barely lick, so no session reaches ten
trials with a detected lick. The phase-aligned families and the consolidated stats sheet are
both built on filtered_v1, so there is no severe acute cell in the statistics either, and the
published `angle_panels` have always shown a dashed bridge across it. This is not a change
introduced by the new generator.

The scalar per-trial angle panels (`tongue_lick1_angle_at_ypeak`,
`tongue_lick2_angle_at_ypeak`) do show a severe acute point, because the June-30 panels were
drawn from `no_filter`. That point rests on 46 trials spread over sessions with **1 to 6 usable
trials each** (PS51 12, PS54 26, PS55 20), whose per-session means range from -5.6 to +8.9 deg.
It carries no `**` because the sheet has no severe acute row to test. Regenerating from
filtered_v1 (the default of `plot_scalar_meansem_panels.py`) removes it, which is the
self-consistent choice: figure and statistics then see the same sessions.

The Results text already reports only mild and moderate acute angle values and flags the
moderate one as coming from the single moderate animal licking acutely, so no wording change
is needed.

### Recovered figure data (2026-09-17)

Figure 1 F/G (caudoputamen area, body weights) and the videofluoroscopy panels were produced
outside this repository and their plotting code was not preserved. `extract_svg_series.py`
reads a published matplotlib SVG, calibrates the pixel -> data transform from the axis ticks,
and writes every plotted point (lines, markers, scatter, bars, with the artist colour that
identifies the series) to a tidy CSV; `plot_recovered_panels.py` redraws the panel from it.
Tables live at `data/recovered_figure_series/*.csv` (84 KB, committed) and are copied beside
the panels in `vls_stroke_paper/recovered_panels/recovered_data/`.

What survives recovery: the drawn values, at matplotlib's path precision (far finer than a
plotting pixel). The weight figure comes back as 8 per-animal trajectories over day -7 to +14
with the phenotype colours intact; the VFSS panels as PS89/PS90/PS91 across pre1/pre2/post1/post2.
What does not: anything the figure did not draw (excluded points, replicates behind a mean,
units converted before plotting), and the statistical annotations, which are text in the
published SVGs and are not recomputed. **These CSVs are a recovery of what the figure drew,
not the upstream measurements.** If the real source tables are found (infarct/gliosis
measurements, the body-weight log, the VFSS scoring sheet), dropping them in with the same
columns makes these panels reproducible from source.

## Scalar meanSEM panel generator (2026-09-17)

`scripts/manuscript/plot_scalar_meansem_panels.py` regenerates the
`meanSEM_sig_panels` figures, whose original script was never saved. It rebuilds the
per-session values the same way the stats build does (per-trial -> per-(animal, date, side)
mean -> minus that animal's own pre-stroke mean per side) and reads `**` from
`pooled_phenotype_stats*.csv` (`headline_and_bootstrap_sig`, or `wa_sig` for the
within-animal variant). Output: `vls_stroke_paper/meanSEM_sig_panels_v2/` (local + server),
30 endpoints, svg + png + pdf, at the published 720 x 331.2 pt (424.8 for `d_prime` /
`criterion_c`) geometry. All 30 panels carry exactly the same `**` marks as the June-30
files, verified mark-for-mark.

```bash
python scripts/manuscript/plot_scalar_meansem_panels.py \
  <outputs>/stats <outputs>/stats/results/phenotype_pooled/3_tier/pooled_phenotype_stats.csv \
  <out_dir> [--endpoints <slug> ...] [--sig-col headline_and_bootstrap_sig|wa_sig] \
  [--filter-variant auto|no_filter]
```

Two substantive differences from the published files:

1. The italic subtitle now reads "session-bootstrap CI of the post-pre difference in means",
   which is what the code computes; the old files said "bootstrap CI of median diff". This
   closes the open item about stale footers on the scalar panels.
2. **Input precedence.** The June-30 panels were drawn from `stats/inputs/no_filter/` for
   every endpoint, while the significance sheet uses `filtered_v1` when that tree exists.
   The script now follows the sheet's precedence, so a panel can no longer show a point in a
   cell that has no row in the sheet. The clearest case is the severe ACUTE point of
   `tongue_mean_within_bout_ili_ms`: it rests on 11 QC-failing trials (PS54 n=3, PS55 n=8),
   is absent from the stats sheet, and is absent here. `--filter-variant no_filter`
   reproduces the old look.

SVG text is emitted as real text (`svg.fonttype=none`) rather than outlined glyphs, so labels
stay editable in Illustrator; use the `.pdf` if DejaVu Sans is not installed.

The same script also makes the **angle panels** (Figure 3 N-Q) with
`--family phase_aligned_endpoints` (first-lick) and `--family phase_aligned_endpoints_all_licks`
(all-lick), reading `stats/results/phenotype_pooled/<family>/3_tier/v3/per_session_means.csv`
and mapping its ipsi/contra sides to the sheet's L/R. Output: `vls_stroke_paper/angle_panels_v2/`.
Verified against the published `angle_panels`: same canvas, same axes geometry, same `**` counts
(first-lick 15, all-lick 13).

A **dashed segment** now bridges any epoch with no qualifying sessions (the severe/acute cell),
which was the published convention in the angle panels and is now applied to the scalar panels
too; `--solid-gaps` restores the old solid bridge. Among the scalar panels this changes only
`tongue_mean_within_bout_ili_ms`, whose severe line has no acute point under filtered_v1.

### Within-bout ILI direction (2026-09-17)

Checked because the panels read as a post-stroke decrease. The effect is biphasic and not
consistent across animals: ILI rises acutely (+13 to +22 ms in mild and moderate; severe
animals contribute no acute data), then falls a few ms below baseline sub-acutely and
chronically. Chronic per-animal deltas split 3 down (PS48, PS51, PS55, -7 to -17 ms) against
5 flat-to-up (PS46 +12, PS47, PS49, PS50, PS54). Of the chronic `**` calls only severe
ipsilesional (-8.3 ms) has both its animals moving the same way and survives the within-animal
permutation; moderate contralesional (-10 ms) is carried entirely by PS51 (PS46 is +7.1) and
fails it (q = 0.15). Magnitude is 3-4% of a ~160 ms baseline.

Two mechanisms were checked. Selection: post-stroke yield of a valid ILI falls to 57-80% in
the impaired animals (99% pre-stroke), but restricting to trials with >= 8 or >= 12 licks
leaves the deltas essentially unchanged, so it is not simply weak trials dropping out.
Censoring: the endpoint is the mean ILI inside the FIRST multi-lick bout with intervals
censored to <= `bout.max_ili_ms` (300 ms), so long intervals both split the bout and are
excluded; this caps how slow the measure can look but not how fast, and therefore biases
toward the observed decrease. Also, pre-stroke ILI drifts upward in all 8 animals during
baseline (+0.5 to +2.9 ms/session), so a negative chronic delta runs against the baseline
trend rather than continuing it. The manuscript's current wording ("changes in within-bout
inter-lick interval were small and not consistent in direction across animals and epochs")
matches this and needs no change.

## Trajectory panel geometry (2026-09-17)

`scripts/manuscript/plot_traj_panels.py` now renders at exactly **1149.84 x 648.98 pt**, the size
of the published pipeline trajectory figures
(`stats/figures/phenotype_pooled/phase_aligned_trajectories/3_tier/v3/angle_deg_*_mean_sem_cleaned_trace.svg`),
so the manuscript panels are drop-in replacements in the `.ai` files. `bbox_inches="tight"` was
removed: it retrimmed every figure separately, which is why the first passes came out
1126.7-1126.9 x 648.9 pt (pooled) and 1114.2 x 627.0 pt (within-animal), all slightly different
from each other. Both `traj_panels/` and `traj_panels_within_animal/` (main four + `extra/`)
were regenerated at the matched size; the earlier files are kept in each folder's
`superseded_tightbbox/`. `angle_panels/` needed no change: those were already 720 x 331.2 pt
with the `meanSEM_sig_panels` axes fractions.

## Wasserstein terminology (2026-09-17, v11 / v8)

The manuscript now uses **"Wasserstein-2"** everywhere (previously mixed with
"2-Wasserstein": `main.tex` lines 776 and 881, and the matching docx paragraphs 85
Statistical analysis and 90 Figure 3 legend). Figure axes use **"W-2"** as the shorthand
("Δ W-2 from pre-stroke (px)", "Δ W-2 (x pre-stroke baseline)"), which is what
`scripts/manuscript/plot_w2_meansem_panels.py` writes; no code change was needed.

Two stale "2-Wasserstein" strings remain **inside `DLC.ai`** and therefore inside
`overleaf_project/figures/Figure3_dlc.pdf`: the H and I panel titles
("2-Wasserstein distance, tongue") and the older in-figure legend block, which also still
reads "peak tongue velocity" and uses the pre-relettering D-I panel letters. These are
Illustrator edits; once `DLC.ai` is updated, re-export `Figure3_dlc.pdf` and recompile.

Current manuscript versions: `VLS_stroke_manuscript_revised_v11.docx`,
`VLS_stroke_manuscript_compiled_v8.pdf`, `VLS_stroke_overleaf_v8.zip`.
The pre-rename tex is kept at `overleaf_backup_2026-09-17/main.tex.pre_wasserstein2_naming`.
