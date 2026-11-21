<!-- Repo copy (2026-11-20, Priya: "add the other scripts you wrote to the repo") of
     vls_stroke_paper/review/c2_treadmill_2026-11-20/c1/README.md. The scripts are in
     scripts/manuscript/engagement_movement/ (byte-identical copies of the review folder's c1_*.py, final revision
     2026-11-20). Every script takes the output folder <c1> as its first argument and writes only under it
     (data/, tables[_whole]/, glmhmm/, cache_me/, figures/), refusing to overwrite; the review run used
     <c1> = vls_stroke_paper/review/c2_treadmill_2026-11-20/c1. In the commands below read $C1/c1_*.py as
     scripts/manuscript/engagement_movement/c1_*.py with $C1 still the output folder. c1_glmhmm.py --wf names the
     widefield_pipeline checkout providing wfield_local.glm_hmm (default: the read-only c2stats clone). -->

# Two-tone cohort (#1-#8 = PS46-PS55): treadmill, running, GLM-HMM engagement, confound and within-engaged checks

Item 8 (+ 10a, 11c treadmill part, 11d) of `PROMPT_engagement_movement_both_cohorts.md`. Review output only: no repo
commit, no manuscript file touched. Everything here is reproducible from the scripts in this folder.

## Environment
```
cd C:/Users/SabatiniLab/Github/stroke_orofacial_pipeline-ps47          # branch ps47-chronic-day5, read-only
W=$(pwd -W); export PYTHONPATH="$W/src;$W"; export MKL_THREADING_LAYER=SEQUENTIAL
P=C:/Users/SabatiniLab/miniconda3/envs/stroke_orofacial/python.exe
C1=M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper/review/c2_treadmill_2026-11-20/c1
```
The GLM-HMM imports `wfield_local.glm_hmm` (and TIM `wfield_local.task_independent_movement`) unchanged from the
read-only clone `C:/Users/SabatiniLab/Github/widefield_pipeline_c2stats` (49283ea2); both run in the stroke_orofacial env.

## Run order (what was run, in order)
| step | command | time | writes |
|---|---|---|---|
| 1 | `$P $C1/c1_extract_sessions.py $C1 --jobs 8` | 3 min | data/trials.parquet, traces.npz, extract_meta.csv (+ sessions_running.parquet, superseded by step 2) |
| 2 | `$P $C1/c1_running.py $C1 --jobs 8` | 1.5 min | data/running_sessions.parquet, running_trials.parquet, running_meta.json (N) |
| 3 | `$P $C1/c1_glmhmm.py $C1 --variant primary` (+ `ipsi_only`, `no_cue`) | ~1 h each | glmhmm/<variant>_K5_states.csv.gz, _params.json, _profile.csv |
| 4 | `$P $C1/c1_analysis.py $C1 --part movement` then `--part engagement` | 2 + ~5 min | tables/tests_*.csv, session_values_*.csv, ... |
| 5 | `MC=.../manuscript_code $P $C1/c1_figures.py $C1` | 1 min | figures/C1_*_row.{pdf,svg,png}, C1_severity_key |

Every writer refuses to overwrite its outputs.

## Deferred (Priya 2026-11-20 00:05): keypoint motion energy and TIM — prepared, tested, one command each
Both need only the DLC keypoints already on M: (no FaceRhythm input); they are held so that all motion-energy
measures (keypoint + FaceRhythm) run together once the colleague's two-tone FaceRhythm data arrive.
```
# keypoint motion energy (11a) + keypoint stillness (11c); tested on PS46_20250310 + PS46_20250315 (25 s / session)
$P $C1/c1_keypoint_me.py $C1 --stage cache --jobs 6      # -> cache_me/<label>.npz (40-ms bin ME per part, ~4 MB each)
$P $C1/c1_keypoint_me.py $C1 --stage measures            # -> data/me_trials.parquet, me_sessions.parquet
$P $C1/c1_keypoint_me.py $C1 --stage stats               # -> tables/tests_keypoint_me.csv, _by_state, ME vs P(engaged)
# TIM (4 / 10b); tested on the same two sessions (~20 s / session)
$P $C1/c1_tim.py $C1 --stage trials --jobs 6             # -> data/tim_trials.parquet
$P $C1/c1_tim.py $C1 --stage stats                       # -> tables/tests_tim.csv, tests_tim_engaged.csv, tim_pre_disengaged_vs_engaged.csv
```
Inputs: data/trials.parquet + data/running_meta.json + glmhmm/primary_K5_states.csv.gz (this folder);
dlc_analysis/interpolated_traces/{tongue,jaw}, dlc_analysis/centered_eye_midpoint (nose, whiskers, eyes),
dlc_analysis/alignment_templates/cam2 (frame -> wavesurfer clock). Not covered: PS48 2025-03-14 (multi-half session).
Still MISSING for the full item 11 / composite (item 5) in this cohort: the two-tone FaceRhythm outputs (FR motion
energy 11b, FR non-lick factors for the composite index). The keypoint ME / TIM scripts do not depend on them.

## Exact definitions used (two-tone, cue at 0)
- Treadmill: `Treadmill_smoothed` from spout_behavior/treadmill_signals_preprocessed, mm/s, + = forward:
  (V - 1.2588 V) / 0.382 V·s/rot × 29.25 mm/rot, Gaussian σ 0.15 s, 1 kHz. Identical constants to the six-position rig.
  Checked against Rich's treadmill_calibration recordings: one wheel rotation integrates to +27.0/+28.5 mm (forward)
  and -28.4/-30.6 mm (reverse) vs 29.25 mm nominal.
- Push = backward speed > 0.5 mm/s at any sample in -0.25..0.75 s; control -2..-1 s; push rate cue minus control.
  Walking = fraction of 2..3.5 s with forward speed > 3 mm/s (behavior_states: fraction of window time, averaged over
  trials); control -2..-1 s. All trials of the first N min (primary). Lick-working-period trials = sensitivity.
- Running bouts: forward > 3 mm/s, gaps < 0.3 s filled, bouts ≥ 2 s. Stillness: |speed| < 1 mm/s.
  Running / stillness windows: ITI -3..-2 s, pre-cue -2..0 s, response 0..3.5 s. Whole session: first cue → +N min.
- N = 50.5 min = 10th percentile of first→last-cue session length (256 sessions, 48.4-71.2 min; 23 shorter
  sessions enter whole; no animal dropped). Unmatched (all trials / first cue → last cue + 8 s) reported as *_unmatched.
- Sessions = the cohort-1 scalar-family set (`iter_cohort_a_sessions`, 256 sessions, 24,793 trials); recomputed
  first_lick_accuracy_all matches stats/inputs exactly, num_correct_licks_per_trial_rw within 0.02 licks.
- Epochs: `assign_epoch_label` with ps47-chronic-day5 animals.yaml. Grades: mild #1-#4 (PS47-50), moderate #5-#6
  (PS46, PS51), severe #7-#8 (PS54, PS55). Sides: all strokes left, so L cue = ipsilesional, R cue = contralesional.
- Statistics: c1_stats.run_family = compute_endpoint_cell_suite(test_set="c2_aligned") per grade × side × epoch on the
  change from the animal's own pre mean; BH within each tests_<family>.csv; star = q < 0.05 AND nested CI excludes 0.

## Revision 2026-11-20 (Priya's decisions on the first report) — WHOLE-SESSION primary
1. Trial set: ALL trials of ALL sessions (no 50.5-min match) is primary. New outputs: `tables_whole/`, `figures_whole/`
   (the first-pass `tables/`, `figures/` are the time-matched version, kept).
   `$P c1_analysis.py $C1 --part movement --trialset whole`, `... --part engagement --trialset whole`,
   `$P c1_keypoint_me.py $C1 --stage stats --trialset whole`, `$P c1_tim.py $C1 --stage stats --trialset whole`,
   `MC=... $P c1_figures.py $C1 --whole`. Running "whole session" = first cue -> last cue + 8 s.
2. Engagement occupancy per cue side: `tables_whole/tests_engagement_<variant>_bycue.csv` (own BH family per variant),
   figure `figures_whole/C1_engagement_bycue_row[_<variant>]`.
3. Jaw-based GLM-HMM: `c1_jaw_trials.py` (pipeline per-trial jaw_pass_qc -> data/jaw_trials.parquet; 248/256 sessions)
   then `c1_glmhmm.py --variant jaw3` (attempt / jaw-only / no response) and `--variant init` (lick OR jaw vs none).
   Per-state rates: glmhmm/<variant>_K5_profile.csv; jaw opening on no-lick trials by role x grade x epoch:
   `tables_whole/jaw_on_nolick_trials_by_role[_byside]_<variant>.csv`.
4. 0.9 partial cut and K = 5 kept.
5. Treadmill: pipeline calibration kept (identical to the six-position constants).
TIM stats: the pre-stroke disengaged-vs-engaged step now writes a "not estimable" row (no pre-stroke disengaged trials).
Cohort speed check (pre-stroke): cue-aligned forward speed (-1..3 s, session-mean trace) two-tone 0.32-0.65 mm/s
(mean 0.47) vs six-position 0.28-0.62 mm/s (mean 0.39, treadmill_traces_by_epoch.csv); two-tone whole-session mean
forward speed 0.96 mm/s (animal means 0.37-2.41; PS54/PS55 = 1.37/2.41), 8.7 % of time > 3 mm/s, 88 % still.

## 60-min recording window (Priya 2026-11-20; manuscript treadmill / running figure)
`c1_sync60.py <c1> <out>`: treadmill push / walking and running / stillness on each session's 60-min recording, first to
last sync pulse (see docs/DECISIONS.md 2026-11-20). `--stats-only` reruns the statistics from an existing <out>.
