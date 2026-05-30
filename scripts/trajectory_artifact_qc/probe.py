"""Trajectory artifact QC probe — provenance + morphology of the mod-severe /
severe acute *contra* phase-aligned tongue-Y cells.

READ-ONLY DIAGNOSTIC (chore/trajectory-artifact-qc). Reads shipped pipeline
products only; writes exclusively under
``pipeline_outputs/stats/sensitivity/trajectory_qc/``. Touches NO v2 emit
code, runners, aggregators, or cohort_filters.

WHAT THIS PROBE FOUND (headline)
================================
The Q13c v2 phase-aligned tongue-Y trajectory figures (and the Q13b scalar
endpoints) are built from ``TongueVisualBundle.df_trials.{y_snip,x_snip}``,
which are sliced from the **INTERPOLATED** trace
(``_build_tongue_pertrial_core`` →
``_load_tongue_centered_trace`` → ``resolver.interpolated_trace``;
``tongue_pertrial.py`` ~L3307) and have peaks detected by the LEGACY
``_slope_detect_lick_peaks`` on that signal. The Phase 7e v7 pipeline
(preclean → detect_v2 → gates F/D/E/M) runs in PARALLEL and its cleaned
output feeds ONLY the ``cleaned_traces`` / ``lick_events`` parquets — it is
NOT fed into the phase-aligned trajectory / endpoint substrate.

Consequence, verified on PS51 (mod-severe) 2025-05-04 contra (R):
  - 11 of the 12 trials feeding the cell have their contributing protrusion
    BASELINE-FILLED TO 0 in the v7 cleaned trace (the v7 gates rejected
    them) and are ABSENT from the v7-gated ``lick_events``.
  - The 1 survivor (t77) is itself an "acute jump" (single-frame
    0→~120px step, no physiological rise).
  - The <10-trials session filter did NOT discard this session: it counts
    ``n_licks_family.n_licks`` (the SAME legacy/interpolated path),
    n_trials_with_detected_lick(R)=19 ≥ 10. On v7-gated counts R≈1 → would
    discard. So the filter inherits the same provenance defect.

This probe therefore reports two per-trial diagnostics, NOT a generic
"spike width":
  (1) PROVENANCE — does the figure's first-lick peak survive v7 cleaning
      (cleaned-trace y non-zero at the peak frame AND present in
      ``lick_events``), or is it interpolated-only (v7-rejected)?
  (2) MORPHOLOGY — "acute jump": fraction of the protrusion amplitude that
      appears in a single frame at the rising edge of the interpolated
      trace (≈1.0 = non-physiological single-frame jump).

Trial membership: contra = mouse-R for all L-stroke cohort animals
(``figures/_layout.SIDE_TO_PANEL_LABEL = {"L":"ipsi","R":"contra"}``).
mod-severe = PS51 (4-tier only); severe = PS54+PS55. Roster read from the
authoritative v2 ``per_trial_trajectory_scalar.csv`` (signal=y_centered,
side=R, epoch=acute).

EMITS (all under stats/sensitivity/trajectory_qc/)
--------------------------------------------------
- ``trial_grid_mod_severe_acute.svg`` — 12 panels (PS51), interp(blue) vs
  cleaned(red) tongue-y at each suspect peak; provenance + acute-jump in
  the title; baseline-fill ticks; likelihood overlay.
- ``trial_grid_severe_acute_page<N>.svg`` — paginated 12/page (PS54+PS55).
- ``provenance_by_phenotype.svg`` — % v7-rejected by phenotype (incl. mild +
  moderate reference) — shows the bug's differential impact.
- ``trial_classification.csv`` — per-trial provenance + acute-jump +
  sustain width + peak values.
- ``summary_qc_report.md`` — counts + method + the root-cause writeup.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from stroke_orofacial.animals import get_animal
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
    _derive_trial_events_from_spout_behavior,
    _trial_arrays,
    build_tongue_visual_bundle_by_animal_date,
)
from stroke_orofacial.manifest import build_manifest
from stroke_orofacial.paths import PathResolver

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

V2_4TIER_REL = (
    "stats/results/phenotype_pooled/phase_aligned_trajectories/4_tier/v2/"
    "per_trial_trajectory_scalar.csv"
)
PHENOTYPE_ANIMALS = {
    "mild": ["PS47", "PS48", "PS49", "PS50"],
    "moderate": ["PS46"],
    "moderate-severe": ["PS51"],
    "severe": ["PS54", "PS55"],
}
SUSPECT_PHENOTYPES = ["moderate-severe", "severe"]
REFERENCE_PHENOTYPES = ["mild", "moderate"]
SIDE = "R"          # contra for all L-stroke cohort animals
EPOCH = "acute"
SIGNAL = "y_centered"
FPS = 250.0

# "acute jump": >= this fraction of the protrusion amplitude appearing in a
# single rising-edge frame of the interpolated trace => non-physiological.
ACUTE_JUMP_FRAC = 0.5
# v7-cleaned trace counts as "kept at the peak" if |y| exceeds this (px).
CLEANED_NONZERO_PX = 1.0

REFERENCE_SAMPLE_N = 200
REFERENCE_RNG_SEED = 0


# ---------------------------------------------------------------------------
# Output dir guard
# ---------------------------------------------------------------------------

def _resolve_out_dir(resolver: PathResolver) -> Path:
    out = resolver.pipeline_outputs().parent / "stats" / "sensitivity" / "trajectory_qc"
    out.mkdir(parents=True, exist_ok=True)
    suffix = (Path("stats") / "sensitivity" / "trajectory_qc").as_posix()
    if not out.as_posix().endswith(suffix):
        raise RuntimeError(f"Refusing to write outside sanctioned dir: {out}")
    return out


# ---------------------------------------------------------------------------
# Roster
# ---------------------------------------------------------------------------

def _load_roster(resolver: PathResolver) -> pd.DataFrame:
    csv = resolver.pipeline_outputs().parent / V2_4TIER_REL
    df = pd.read_csv(csv)
    df = df[(df["epoch_label"] == EPOCH) & (df["side"] == SIDE) & (df["signal"] == SIGNAL)]
    df = df[["animal", "date", "trial_index"]].drop_duplicates()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    animal_to_pheno = {a: p for p, ans in PHENOTYPE_ANIMALS.items() for a in ans}
    df["phenotype"] = df["animal"].map(animal_to_pheno)
    return df.sort_values(["animal", "date", "trial_index"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Per-session loaders (cached)
# ---------------------------------------------------------------------------

class _SessionData:
    """Bundle + interp + cleaned + lick_events + tone-frame map for a session."""

    def __init__(self, resolver: PathResolver, animal: str, date: dt.date):
        self.animal, self.date = animal, date
        self.bundle = build_tongue_visual_bundle_by_animal_date(animal, date, resolver)
        self.interp = pd.read_parquet(
            resolver.interpolated_trace("tongue", animal, date)
        ).set_index("frame_idx").sort_index()
        self.cleaned = pd.read_parquet(
            resolver.cleaned_trace("tongue", animal, date)
        ).set_index("frame_idx").sort_index()
        le = pd.read_parquet(resolver.lick_events("tongue", animal, date))
        self.kept_keys = set(zip(le["trial"].tolist(), le["side"].tolist()))
        info = get_animal(animal)
        manifest = build_manifest(
            animal, date, resolver, info,
            analysis_context="dlc.kinematics.tongue_pertrial",
        )
        events = _derive_trial_events_from_spout_behavior(
            animal=animal, date=date, resolver=resolver, manifest=manifest,
        )
        self.tone = {(e.trial_index, e.side): e.tone_frame_idx for e in events}


class _SessionCache:
    def __init__(self, resolver: PathResolver):
        self.resolver = resolver
        self._c: dict[tuple[str, dt.date], _SessionData] = {}

    def get(self, animal: str, date: dt.date) -> _SessionData:
        key = (animal, date)
        if key not in self._c:
            self._c[key] = _SessionData(self.resolver, animal, date)
        return self._c[key]


# ---------------------------------------------------------------------------
# Per-trial measurement
# ---------------------------------------------------------------------------

def _acute_jump_frac(t_ms: np.ndarray, y: np.ndarray, peak_t_ms: float) -> tuple[float, float, float]:
    """Single-frame rising-edge fraction of the protrusion amplitude.

    Returns (jump_frac, peak_y, baseline). The rising edge is located as the
    largest positive single-frame increment within +-40 ms of the detected
    peak; jump_frac = that increment / (peak - baseline). ~1.0 means the
    whole protrusion appears in one frame (a baseline-fill->protrusion step,
    not a physiological rise).
    """
    if not np.isfinite(peak_t_ms) or t_ms.size == 0:
        return np.nan, np.nan, np.nan
    i = int(np.argmin(np.abs(t_ms - peak_t_ms)))
    win = (t_ms >= peak_t_ms - 300.0) & (t_ms <= peak_t_ms + 300.0)
    yw = y[win][np.isfinite(y[win])]
    baseline = float(np.nanmin(yw)) if yw.size else 0.0
    peak_y = float(y[i])
    amp = peak_y - baseline
    if amp <= 0:
        return np.nan, peak_y, baseline
    # Largest single-frame positive increment on the rising edge near the peak.
    edge = (t_ms >= peak_t_ms - 40.0) & (t_ms <= peak_t_ms + 1.0)
    idxs = np.where(edge)[0]
    max_inc = 0.0
    for j in idxs:
        if j > 0 and np.isfinite(y[j]) and np.isfinite(y[j - 1]):
            max_inc = max(max_inc, y[j] - y[j - 1])
    return float(max_inc / amp), peak_y, baseline


def _sustain_width_frames(t_ms: np.ndarray, y: np.ndarray, peak_t_ms: float, baseline: float) -> float:
    if not np.isfinite(peak_t_ms) or t_ms.size == 0:
        return np.nan
    i = int(np.argmin(np.abs(t_ms - peak_t_ms)))
    peak_y = float(y[i])
    if not np.isfinite(peak_y) or peak_y <= baseline:
        return 0.0
    hm = baseline + (peak_y - baseline) / 2.0
    lo = i
    while lo > 0 and np.isfinite(y[lo - 1]) and y[lo - 1] >= hm:
        lo -= 1
    hi = i
    n = len(y)
    while hi < n - 1 and np.isfinite(y[hi + 1]) and y[hi + 1] >= hm:
        hi += 1
    return float(hi - lo + 1)


def _measure(session: _SessionData, trial: int) -> dict | None:
    arrs = _trial_arrays(session.bundle.df_trials, trial, SIDE)
    if arrs is None:
        return None
    t_ms, _ang, x, y = arrs
    if y is None:
        return None
    pk = session.bundle.df_bouts[
        (session.bundle.df_bouts.trial_index == trial)
        & (session.bundle.df_bouts.side == SIDE)
        & (session.bundle.df_bouts.peak_t_ms.notna())
    ]
    peaks = sorted(float(v) for v in pk.peak_t_ms.to_numpy())
    if not peaks:
        return None
    first = peaks[0]
    jump_frac, peak_y, baseline = _acute_jump_frac(t_ms, y, first)
    width = _sustain_width_frames(t_ms, y, first, baseline if np.isfinite(baseline) else 0.0)
    # Provenance: cleaned-trace value at the peak's session frame + lick_events.
    tone = session.tone.get((trial, SIDE))
    cleaned_peak = np.nan
    if tone is not None:
        pf = int(tone + round(first / 1000.0 * FPS))
        if session.cleaned.index.min() <= pf <= session.cleaned.index.max():
            cleaned_peak = float(session.cleaned.loc[pf, "y_final"])
    in_lick_events = (trial, SIDE) in session.kept_keys
    v7_kept = bool(in_lick_events and np.isfinite(cleaned_peak) and abs(cleaned_peak) > CLEANED_NONZERO_PX)
    provenance = "v7_kept" if v7_kept else "v7_rejected_interp_only"
    acute_jump = bool(np.isfinite(jump_frac) and jump_frac >= ACUTE_JUMP_FRAC)
    return {
        "animal": session.animal,
        "date": session.date.isoformat(),
        "trial_index": trial,
        "side": SIDE,
        "first_peak_t_ms": first,
        "n_v7_peaks_this_side": len(peaks),
        "ysnip_peak_px": peak_y,
        "cleaned_peak_px": cleaned_peak,
        "in_lick_events": in_lick_events,
        "provenance": provenance,
        "acute_jump_frac": jump_frac,
        "acute_jump": acute_jump,
        "sustain_width_frames": width,
        "sustain_width_ms": width / FPS * 1000.0 if np.isfinite(width) else np.nan,
        "_t": t_ms, "_x": x, "_y": y, "_peaks": peaks,
        "_tone": tone, "_session": session,
    }


# ---------------------------------------------------------------------------
# Plotting — interp(blue) vs cleaned(red) per trial
# ---------------------------------------------------------------------------

def _plot_trial(ax, rec: dict) -> None:
    t, y = rec["_t"], rec["_y"]
    first = rec["first_peak_t_ms"]
    tone = rec["_tone"]
    session = rec["_session"]
    win = (t >= first - 120) & (t <= first + 120)
    rel = t[win] - first
    ax.plot(rel, y[win], "-", color="tab:blue", lw=1.0, label="interp y (figure substrate)")
    # cleaned y at the same session frames
    if tone is not None:
        frames = (tone + np.round((t[win]) / 1000.0 * FPS)).astype(int)
        ok = (frames >= session.cleaned.index.min()) & (frames <= session.cleaned.index.max())
        cy = np.full(frames.shape, np.nan)
        cy[ok] = session.cleaned.reindex(frames[ok])["y_final"].to_numpy()
        bf = np.zeros(frames.shape, dtype=bool)
        bf[ok] = session.cleaned.reindex(frames[ok])["is_baseline_fill"].to_numpy().astype(bool)
        ax.plot(rel, cy, "-", color="tab:red", lw=1.0, label="cleaned y (v7)")
        if bf.any():
            ax.plot(rel[bf], np.full(bf.sum(), -8.0), "|", color="0.55", ms=6)
    ax.axhline(20, color="green", lw=0.5, ls="--")  # min_peak_y_abs
    ax.axvline(0, color="k", lw=0.5, ls=":")
    for p in rec["_peaks"]:
        if rel.size and rel.min() <= (p - first) <= rel.max():
            j = int(np.argmin(np.abs(t - p)))
            ax.plot(p - first, y[j], "o", color="darkblue", ms=3, zorder=5)
    color = "red" if rec["provenance"] == "v7_rejected_interp_only" else "darkorange"
    jflag = " JUMP" if rec["acute_jump"] else ""
    ax.set_title(
        f"{rec['animal']}_{rec['date']}_t{rec['trial_index']}{SIDE}  "
        f"[{rec['provenance']}{jflag}]\n"
        f"y={rec['ysnip_peak_px']:.0f} clean={rec['cleaned_peak_px']:.0f} "
        f"jumpfrac={rec['acute_jump_frac']:.2f}",
        fontsize=5.6, color=color,
    )
    ax.tick_params(labelsize=5)
    ax.set_xlabel("ms rel. peak", fontsize=5)
    ax.set_ylabel("y (px)", fontsize=5)


def _plot_grid(recs: list[dict], n_cols: int, n_rows: int, title: str, out: Path):
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * 2.6, n_rows * 1.9))
    axes = np.atleast_1d(axes).ravel()
    for k, rec in enumerate(recs):
        _plot_trial(axes[k], rec)
        if k == 0:
            axes[k].legend(fontsize=4.5, loc="upper right")
    for k in range(len(recs), len(axes)):
        axes[k].axis("off")
    fig.suptitle(title, fontsize=9)
    fig.text(0.5, 0.004,
             "blue = interpolated y (what the figure plots); red = v7 cleaned y "
             "(red flat at 0 => v7 rejected this protrusion); gray ticks = "
             "cleaned baseline-fill. jumpfrac~1.0 = single-frame acute jump.",
             ha="center", fontsize=5.2, color="0.3")
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    fig.savefig(out, format="svg", bbox_inches="tight")
    plt.close(fig)


def _plot_provenance(by_pheno: dict[str, dict], out: Path):
    order = ["mild", "moderate", "moderate-severe", "severe"]
    order = [p for p in order if p in by_pheno]
    rej = [by_pheno[p]["rejected"] / max(1, by_pheno[p]["n"]) * 100 for p in order]
    jump = [by_pheno[p]["acute_jump"] / max(1, by_pheno[p]["n"]) * 100 for p in order]
    fig, ax = plt.subplots(figsize=(7, 4))
    xpos = np.arange(len(order))
    ax.bar(xpos - 0.2, rej, width=0.4, color="tab:red", label="% v7-rejected (interp-only)")
    ax.bar(xpos + 0.2, jump, width=0.4, color="tab:purple", label="% acute-jump")
    for i, p in enumerate(order):
        ax.text(i, max(rej[i], jump[i]) + 2, f"n={by_pheno[p]['n']}", ha="center", fontsize=8)
    ax.set_xticks(xpos)
    ax.set_xticklabels(order, rotation=15)
    ax.set_ylabel("% of acute contra trials")
    ax.set_ylim(0, 105)
    ax.set_title("Phase-aligned tongue-Y acute contra: v7-rejected & acute-jump rate by phenotype")
    ax.legend(fontsize=8)
    fig.savefig(out, format="svg", bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _write_report(out: Path, recs_by_pheno: dict[str, list[dict]], by_pheno: dict[str, dict]):
    L = []
    L.append("# Trajectory artifact QC — provenance + morphology report\n")
    L.append("Branch `chore/trajectory-artifact-qc` (READ-ONLY).\n")
    L.append("## Root cause (confirmed)\n")
    L.append(
        "The Q13c v2 phase-aligned tongue-Y **trajectories** and the Q13b "
        "scalar **endpoints** are built from `TongueVisualBundle.df_trials."
        "{y_snip,x_snip}`, which `_build_tongue_pertrial_core` slices from the "
        "**interpolated** trace (`_load_tongue_centered_trace` → "
        "`resolver.interpolated_trace`, ~`tongue_pertrial.py:3307`), with peaks "
        "from the legacy `_slope_detect_lick_peaks`. The Phase 7e v7 pipeline "
        "(preclean → detect_v2 → gates F/D/E/M) runs in parallel and feeds "
        "**only** the `cleaned_traces`/`lick_events` parquets — never this "
        "substrate. So the figure plots protrusions that the v7 gates rejected.\n"
    )
    L.append(
        "Two contributing mechanisms: (a) the figure path has **no preclean** "
        "shape-gate (v7's preclean is what rejects these); (b) the legacy "
        "detector smooths y over `smooth_ms_detect_y=12ms` before computing "
        "slope, so a single-frame baseline-fill→protrusion **step** is smeared "
        "into a multi-frame ramp that satisfies the `rise_min_n=4` check on a "
        "fabricated rise. The `<10` session filter inherits the defect: it "
        "counts `n_licks_family.n_licks` from the same legacy path "
        "(PS51-R n_trials_with_detected_lick=19≥10 → kept; v7-gated≈1 → would "
        "discard).\n"
    )
    L.append("## Per-phenotype counts (acute, contra=R)\n")
    L.append("| phenotype | n trials | v7-rejected (interp-only) | % | acute-jump | % |")
    L.append("|---|---|---|---|---|---|")
    for p in ["mild", "moderate", "moderate-severe", "severe"]:
        if p not in by_pheno:
            continue
        b = by_pheno[p]
        n = max(1, b["n"])
        L.append(
            f"| {p} | {b['n']} | {b['rejected']} | {b['rejected'] / n * 100:.0f}% | "
            f"{b['acute_jump']} | {b['acute_jump'] / n * 100:.0f}% |"
        )
    L.append("")
    L.append(
        "**Read:** a high v7-rejected % means the cell's trajectory is built "
        "mostly on protrusions the v7 cleaning discarded. The suspect cells "
        "(moderate-severe, severe) are expected to be far worse than the mild/"
        "moderate reference — the bug bites hardest where licking is sparse / "
        "degraded.\n"
    )
    L.append("## Artifacts\n")
    L.append(
        "- `trial_grid_mod_severe_acute.svg` / `trial_grid_severe_acute_page*.svg`"
        " — interp(blue) vs cleaned(red) per trial.\n"
        "- `provenance_by_phenotype.svg` — rejected/acute-jump rates.\n"
        "- `trial_classification.csv` — per-trial provenance + morphology.\n"
        "- `diag_interp_vs_cleaned_mod_severe.png/.svg`, `diag_zoom_mod_severe.png`"
        " — exploratory overlays (PS51).\n"
        "- `FIX_PROPOSAL.md` — root cause + remediation options (no code edits).\n"
    )
    (out / "summary_qc_report.md").write_text("\n".join(L), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    resolver = PathResolver()
    out = _resolve_out_dir(resolver)
    roster = _load_roster(resolver)
    cache = _SessionCache(resolver)

    def collect(phenos: list[str], sample: int | None = None) -> list[dict]:
        sub = roster[roster["phenotype"].isin(phenos)].reset_index(drop=True)
        if sample is not None and len(sub) > sample:
            rng = np.random.default_rng(REFERENCE_RNG_SEED)
            sub = sub.iloc[np.sort(rng.choice(len(sub), size=sample, replace=False))]
        recs: list[dict] = []
        for (animal, date), grp in sub.groupby(["animal", "date"], sort=True):
            sess = cache.get(animal, date)
            for trial in sorted(grp["trial_index"].tolist()):
                rec = _measure(sess, int(trial))
                if rec is not None:
                    rec["phenotype"] = grp["phenotype"].iloc[0]
                    recs.append(rec)
            print(f"  {animal} {date}: {len(grp)} trials")
        return recs

    print("mod-severe (PS51):")
    mod = collect(["moderate-severe"])
    print("severe (PS54+PS55):")
    sev = collect(["severe"])
    print("reference mild:")
    mild = collect(["mild"], sample=REFERENCE_SAMPLE_N)
    print("reference moderate:")
    moderate = collect(["moderate"], sample=REFERENCE_SAMPLE_N)

    recs_by_pheno = {
        "moderate-severe": mod, "severe": sev, "mild": mild, "moderate": moderate,
    }
    by_pheno = {}
    for p, recs in recs_by_pheno.items():
        by_pheno[p] = {
            "n": len(recs),
            "rejected": sum(r["provenance"] == "v7_rejected_interp_only" for r in recs),
            "acute_jump": sum(r["acute_jump"] for r in recs),
        }

    print("Rendering grids ...")
    _plot_grid(mod, 3, 4, "mod-severe (PS51) acute contra — interp vs cleaned tongue-Y",
               out / "trial_grid_mod_severe_acute.svg")
    page = 12
    for pi in range((len(sev) + page - 1) // page):
        chunk = sev[pi * page:(pi + 1) * page]
        _plot_grid(chunk, 3, 4,
                   f"severe (PS54+PS55) acute contra — interp vs cleaned (page {pi + 1})",
                   out / f"trial_grid_severe_acute_page{pi + 1}.svg")
    _plot_provenance(by_pheno, out / "provenance_by_phenotype.svg")

    print("Writing CSV + report ...")
    cols = ["phenotype", "animal", "date", "trial_index", "side", "first_peak_t_ms",
            "n_v7_peaks_this_side", "ysnip_peak_px", "cleaned_peak_px",
            "in_lick_events", "provenance", "acute_jump_frac", "acute_jump",
            "sustain_width_frames", "sustain_width_ms"]
    all_recs = mod + sev + mild + moderate
    pd.DataFrame([{k: r[k] for k in cols} for r in all_recs]).to_csv(
        out / "trial_classification.csv", index=False)
    _write_report(out, recs_by_pheno, by_pheno)
    print("DONE:", out)
    for p in ["moderate-severe", "severe", "mild", "moderate"]:
        b = by_pheno[p]
        print(f"  {p}: n={b['n']} v7-rejected={b['rejected']} acute-jump={b['acute_jump']}")


if __name__ == "__main__":
    main()
