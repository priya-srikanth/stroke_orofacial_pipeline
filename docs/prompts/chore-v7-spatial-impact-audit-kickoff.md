# chore/v7-spatial-impact-audit — kickoff

**Status:** DRAFT — kickoff posted, audit compute pending Priya inputs (threshold
+ acute-session dates).
**Branch:** `chore/v7-spatial-impact-audit`
**Worktree:** `C:\Users\sabatini\GitHub\stroke_orofacial_pipeline-spatial-audit`
**Sibling work:** Phase 7e cleaned_traces cohort (`v7e` cleaned_traces + Phase 7e.x
same-class fixes) merged via PRs #133 / #137 / #140 / #141 / #143 / #144 / #145
(2026-05-25 → 2026-05-26).
**Parent ticket:** F-P-1 (spatial-impact audit driver from Cowork prompt 2026-05-26).

---

## 1. Question this audit answers

> *Does the v7 cleaned_traces cleanup logic (interpolation fill + baseline-fill
> placeholder masking) change the on-disk spatial heatmap outputs that
> `dlc_spatial` produces today from Phase 4 centered parquets?*

If yes (and the magnitude exceeds a Priya-set threshold), production
`dlc_spatial.render_on_demand` should adopt the cleaned_traces filter pattern
(read `~is_baseline_fill` mask + drop the per-bp `likelihood_threshold` gate)
as a Phase 7e.x extension. If no, the kinematic-side cleanup is irrelevant to
spatial outputs and the current production pipeline can stay as-is.

The question matters now because Phase 7e closed the *kinematic* side of the
v7 cleanup (lick1_y_peak / mean_sem / cumulative-y all consume cleaned_traces
with NaN-masking on `is_baseline_fill`), but the *spatial* side
(`dlc_spatial.render_on_demand` + `pixel_bins.build_histogram`) still reads
Phase 4 centered parquets directly and filters frames only by per-bodypart
`likelihood_threshold = 0.80`. That gate is *not* what Phase 7e converged on
for the kinematic side.

---

## 2. Production filter chain we are auditing

Source: `src/stroke_orofacial/dlc_spatial/pixel_bins.py::get_masked_xy` (consumed
by `build_histogram`, which is consumed by `render_on_demand.render_*` and
`heatmaps.plot_heatmap`).

```
m  = np.isfinite(x) & np.isfinite(y)
m &= likelihood_raw >= likelihood_threshold     # per-bp config; default 0.80
m &= frame_mask                                 # tone-aligned window (or None)
m &= (x in x_range)                             # optional per-family x_range
```

The Phase 4 centered parquet (`pipeline_outputs/dlc_analysis/centered/<center_mode>/<animal>/...`)
provides `{bp}_x_centered_{mode}`, `{bp}_y_centered_{mode}`, and `{bp}_likelihood`
for every camera frame. **No** `is_baseline_fill` column lives here — that
membership flag is only on cleaned_traces.

---

## 3. Cleaned_traces parquet (v7) — the audit reference

Path: `pipeline_outputs/dlc_kinematics/cleaned_traces/{tongue,jaw}/<animal>/<YYYYMMDD>.parquet`

Schema (verified 2026-05-27 on PS54 / 2025-05-06):

| column | dtype | semantics |
|---|---|---|
| `frame_idx` | int64 | 0..N-1 dense, 1:1 with Phase 4 centered parquet row index |
| `x_final` | float64 | post-cleanup x (centered px) |
| `y_final` | float64 | post-cleanup y (centered px); 0.0 placeholder where `is_baseline_fill=True` |
| `likelihood_raw` | float64 | raw DLC likelihood (same value as centered parquet's `{bp}_likelihood`) |
| `is_interp_fill` | bool | filled from interpolation across an unlabeled gap |
| `is_baseline_fill` | bool | y=0 placeholder; bodypart was not detected at this frame |
| `fill_method` | int8 | enum of cleanup decisions |

Frame-count anchor: PS54 / 2025-05-06 → 906,555 rows for both bodyparts (matches
the cleaned_traces parquet length one-to-one with the Phase 4 centered parquet
frame count; same DLC h5 source).

PS54 / 2025-05-06 cleanup census (sanity check the audit's tongue-vs-jaw
contrast lands as expected):

| bodypart | n_frames | baseline_fill | interp_fill | real detections |
|---|---:|---:|---:|---:|
| tongue | 906,555 | 899,069 (99.17%) | 1,740 (0.19%) | ~7,486 (~0.83%) |
| jaw    | 906,555 |   2,115 (0.23%)  | 6,352 (0.70%) | ~904,440 (~99.77%) |

→ Tongue cleanup mass is dominated by `is_baseline_fill=True` (frame absent);
jaw is overwhelmingly real. We expect R1 vs R3 distance to be *large* for
tongue and *small* for jaw. If we see the opposite pattern, the audit driver
itself is broken.

---

## 4. Three render variants

We re-render the same (animal, date, bodypart, scope) cell three ways:

| variant | filter chain | reads from |
|---|---|---|
| **R1** | `lik >= 0.80` (production today) | centered parquet only |
| **R2** | `lik >= 0.80` AND `~is_baseline_fill` | centered parquet + cleaned_traces (mask join on frame_idx) |
| **R3** | `~is_baseline_fill` (lik gate dropped) | centered parquet + cleaned_traces (mask join on frame_idx); pass `likelihood_threshold=0.0` |

- **R1** is the current production output (no change from existing
  whole-session / tone-aligned heatmap PNGs).
- **R2** isolates the baseline-fill contribution: same likelihood gate as R1
  but with placeholder-y=0 frames removed. Pixels at the centered-y=0 spout
  baseline that come from "bodypart absent" frames should disappear.
- **R3** is the Phase-7e-aligned filter: trust the cleaned_traces' "is this
  frame a real detection?" classifier (`~is_baseline_fill`) instead of the
  per-bodypart likelihood threshold. This matches what the kinematic
  consumers (mean_sem, lick1_y_peak, cumulative-y) converged on in Phase 7e.

R3 IS the production behavior we'd ship if the audit finds the change is
meaningful. R2 is included as a diagnostic to disentangle "baseline-fill
removal" from "dropping the lik gate" — the difference (R2 vs R3) tells us
whether the likelihood threshold was doing real work above and beyond the
baseline-fill mask.

---

## 5. Audit matrix (compute size)

```
3 sessions × 4 scopes × 3 render variants × 2 bodyparts = 72 PNG renders
                                                        + 24 metric values
```

- **3 sessions** — one acute (≤14 days post-stroke) session per animal,
  chosen for phenotype coverage: severe (PS54), mod-severe (PS51), mild
  (PS47). Specific dates TBD (Step 9 — ask Priya).
- **4 scopes** — `whole_session` + `tone_aligned (all, L, R)` with the
  Phase 7c.2 single window `(0, 8000) ms`.
- **3 render variants** — R1 / R2 / R3 as above.
- **2 bodyparts** — `tongue` (center_mode `spout_midpoint`), `jaw`
  (center_mode `eye_midpoint`). These are the two bodyparts the Phase 7e
  cleanup applies to — the audit is scoped to the bodyparts whose
  cleaned_traces would be the upstream input under R3.

### Metric

For each `(session, scope, bodypart)` cell (= 24 cells) we compute on the
`H_proportion` arrays (normalized so total = 1):

1. **Wasserstein-1** (`scipy.stats.wasserstein_distance_nd`) between R1 and
   R3 distributions. Pixel-coordinate ground space; units are centered px.
2. **KL divergence** `KL(R3 ‖ R1)` with `epsilon = 1e-12` added to R1 to
   avoid log-of-zero where R1 has zero mass but R3 does not. (`R3 ‖ R1`
   direction: R3 is the cleaner reference; KL tells us how much "extra
   information" R1's distribution carries that R3 doesn't agree with.)

We also record per-cell:

- `n_frames_R1` / `n_frames_R2` / `n_frames_R3` — frames passing each filter,
  to interpret the metric in context.
- `baseline_fill_fraction` — `is_baseline_fill.mean()` over the scope's
  selected frames; tongue should be ~99% per the §3 census; jaw should be
  ~0.2%.
- `lik_below_threshold_among_real` — fraction of frames where
  `~is_baseline_fill AND lik < 0.80`; this is the population R3 admits that
  R1 excludes.

### Verdict logic

Threshold `W_max` and `KL_max` TBD by Priya (Step 9). Default proposal:
W_max = 5 px, KL_max = 0.1 nats. Per-cell verdict:

- `max(W_cell) < W_max` AND `max(KL_cell) < KL_max` → **PASS**: production
  R1 spatial outputs are not meaningfully different from R3; no action.
- Either exceeded → **FAIL**: open a Phase 7e.x ticket to wire
  `~is_baseline_fill` into `pixel_bins.get_masked_xy` + drop the
  `likelihood_threshold` gate from `render_on_demand` callers.

The verdict is a single OR over all 24 cells, but we surface every cell's
(W, KL) value in the audit report so a partial result (e.g. tongue FAILs,
jaw PASSes) supports a bodypart-scoped fix rather than a wholesale change.

---

## 6. Worktree + branch isolation

Per CLAUDE.md Ground Rule 9 (added 2026-05-26 after the Phase 7e ×
jaw-quality-audit branch-tangle incident), all F-P-1 audit work happens in
the dedicated worktree `C:\Users\sabatini\GitHub\stroke_orofacial_pipeline-spatial-audit`
on branch `chore/v7-spatial-impact-audit`. The main worktree
(`C:\Users\sabatini\GitHub\stroke_orofacial_pipeline`) continues to host
unrelated parallel work without collision.

Teardown after PR merge: `git worktree remove ...-spatial-audit` from the
main worktree + `git branch -d chore/v7-spatial-impact-audit` once `gh pr
view` confirms MERGED.

---

## 7. Inputs needed from Priya before audit compute (Step 9 STOP)

1. **`W_max` (Wasserstein threshold)** — proposed default 5.0 px. Override?
2. **`KL_max` (KL threshold)** — proposed default 0.1 nats. Override?
3. **3 acute-session dates**:
   - PS54 (severe phenotype): one acute date (≤14 days post-stroke).
   - PS51 (mod-severe): one acute date.
   - PS47 (mild): one acute date.
4. **Bodypart × center_mode pinning** — confirm `tongue / spout_midpoint`
   and `jaw / eye_midpoint`. (Other center_modes exist; this matches what
   the kinematic consumers in Phase 7e use, but spatial defaults may
   differ.)

No compute runs until these are pinned in writing. Threshold + dates land
as an Addendum #1 to this kickoff doc; this section then closes.

---

## 8. Output tree

```
.scratch_v7_spatial_audit/
  README.md                       # this doc + addenda summary
  audit_manifest.csv              # per-(session, scope, bp, variant) row
                                  # with status + paths + per-cell metrics
  renders/
    {animal}/{date}/{bp}/{scope}/{variant}.png
  metrics/
    wasserstein_kl.csv            # 24 rows (one per cell)
    verdict.json                  # PASS/FAIL + per-cell summary
  diff_maps/                      # optional R3 - R1 heatmaps for visual
    {animal}/{date}/{bp}/{scope}.png
```

`.scratch_v7_spatial_audit/` is `.gitignore`-d (scratch tree convention
from Phase 7e). The kickoff doc + audit driver script + verdict JSON
(committed copy) are the PR's only tracked artifacts.

---

## 9. Driver script outline (post-Step-9)

```
scripts/v7_spatial_audit/audit.py
    --sessions  PS54:YYYYMMDD,PS51:YYYYMMDD,PS47:YYYYMMDD
    --bodyparts tongue,jaw
    --scopes    whole_session,tone_all,tone_L,tone_R
    --variants  R1,R2,R3
    --w-max     5.0
    --kl-max    0.1
    --out-root  .scratch_v7_spatial_audit
```

Implementation outline:

1. For each (animal, date), load Phase 4 centered parquet (production input)
   AND cleaned_traces parquet (audit input) for both bodyparts. Sanity-
   check `len(centered_df) == len(cleaned_df)` and that the cleaned_df's
   `frame_idx` is 0..N-1 dense.
2. Build per-variant `frame_mask` by joining cleaned_df's `is_baseline_fill`
   onto centered_df by row position (= frame_idx, by construction). Pass
   to `build_histogram` via `window=` (using a thin `WindowSelector`
   subclass that wraps the boolean array) and override per-bp
   `likelihood_threshold=0.0` for R3 via the `config_for_hist` deepcopy
   pattern already used in `render_on_demand.render_tone_aligned_heatmap_session`.
3. Render PNGs via `render_h_counts_panel` (production renderer; ensures
   audit visuals are apples-to-apples with current production outputs).
4. Compute Wasserstein + KL on the `H_proportion` arrays. Wasserstein-1
   needs `(N, 2)` sample arrays — sample `H_proportion` via multinomial
   draw at fixed seed (or use SciPy's grid-aware solver if available in
   this env).
5. Emit `metrics/wasserstein_kl.csv` + `verdict.json`; print one-line
   verdict summary to stdout for PR comment.

---

## 10. Out-of-scope (intentional)

- Other bodyparts (`L_spout`, `R_spout`, `L_eye`, `R_eye`, whiskers).
  Phase 7e cleanup applies only to tongue + jaw; auditing the rest is a
  separate ticket.
- Pre-stroke (baseline) sessions. Audit focuses on acute sessions because
  that's where tongue mostly-absent frames + jaw movement-dropouts are
  expected to load the cleanup mask hardest; if R1 vs R3 differ
  meaningfully anywhere, it'll show up here.
- Aggregated (multi-session) renders. Audit is per-session to keep the
  visual contrast crisp; if we ship the R3 fix to production,
  `compute_animal_aggregated_histogram` will pick it up via the same
  `build_histogram` call.
- Pattern B composite (whiskers / fiducial pairs) renders. Single-bp
  only.
- Stats grid (`build_stats_grid`) audit. Same filter chain underneath, so
  the verdict carries over; rendering it separately is wasted compute.

---

## 11. Addenda

(none yet — Addendum #1 will record Priya's Step-9 inputs once provided)
