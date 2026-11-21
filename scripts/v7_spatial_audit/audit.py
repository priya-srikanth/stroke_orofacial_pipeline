"""F-P-1 v7 spatial-impact audit driver.

Re-renders dlc_spatial heatmaps under three filter variants
(R1=production, R2=+baseline-fill mask, R3=cleaned-only / drop lik gate)
across 3 acute sessions × 4 scopes × 2 bodyparts = 24 cells, then computes
Wasserstein-1, Wasserstein-2, KL(R3 ‖ R1) for each cell.

See ``docs/prompts/chore-v7-spatial-impact-audit-kickoff.md`` for design.
Outputs go to ``.scratch_v7_spatial_audit/`` (gitignored).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import ot
import pandas as pd

from stroke_orofacial.animals import get_animal
from stroke_orofacial.config_loader import load_defaults, lookup_tone_family
from stroke_orofacial.dlc_io.parquet import _param_sig, read_centered_parquet
from stroke_orofacial.dlc_spatial.pixel_bins import build_histogram
from stroke_orofacial.dlc_spatial.tone_aligned import (
    build_tone_aligned_window,
    load_tone_events,
)
from stroke_orofacial.dlc_spatial.window_selector import WindowSelector
from stroke_orofacial.manifest import build_manifest
from stroke_orofacial.paths import PathResolver

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("v7_spatial_audit")

# Locked in Addendum #1 (Priya 2026-05-27).
W1_MAX = 5.0     # px
W2_MAX = 5.0     # px
KL_MAX = 0.1     # nats
KL_EPS = 1e-12

TONE_WINDOW_MS = (0.0, 8000.0)

# (animal, acute date, severity label)
SESSIONS: list[tuple[str, dt.date, str]] = [
    ("PS54", dt.date(2025, 5, 6),  "severe"),
    ("PS51", dt.date(2025, 5, 6),  "mod-severe"),
    ("PS47", dt.date(2025, 3, 19), "mild"),
]

# (bodypart, center_mode) — locked in Addendum #1.
BODYPARTS: list[tuple[str, str]] = [
    ("tongue", "spout_midpoint"),
    ("jaw",    "eye_midpoint"),
]

SCOPES: list[str] = ["whole_session", "tone_all", "tone_L", "tone_R"]
VARIANTS: list[str] = ["R1", "R2", "R3"]


class MaskWindow(WindowSelector):
    """Thin WindowSelector wrapping a precomputed boolean frame mask."""

    def __init__(self, mask: np.ndarray, label_str: str) -> None:
        self._mask = np.asarray(mask, dtype=bool)
        self._label = label_str
        self._n_events = 0  # not event-anchored
        self._n_selected = int(self._mask.sum())

    def select_frames(self, df: pd.DataFrame) -> np.ndarray:
        if len(df) != len(self._mask):
            raise ValueError(
                f"MaskWindow: df length {len(df)} != mask length {len(self._mask)}"
            )
        return self._mask

    @property
    def label(self) -> str:
        return self._label

    @property
    def n_events(self) -> int:
        return self._n_events

    @property
    def n_selected(self) -> int:
        return self._n_selected


@dataclass
class CellResult:
    animal: str
    date: str
    severity: str
    bodypart: str
    center_mode: str
    scope: str
    n_frames_total: int
    n_frames_R1: int
    n_frames_R2: int
    n_frames_R3: int
    baseline_fill_frac: float       # over scope-selected frames
    lik_below_thresh_among_real: float  # over ~baseline_fill within scope
    W1_R1_R3: float
    W2_R1_R3: float
    KL_R3_R1: float
    verdict: str


def _load_centered_df(animal: str, date: dt.date, center_mode: str,
                      resolver: PathResolver) -> pd.DataFrame:
    """Locate + load the Phase 4 centered parquet via the manifest."""
    animal_info = get_animal(animal)
    manifest = build_manifest(animal, date, resolver, animal_info,
                              analysis_context="dlc.spatial")
    if not manifest.dlc_h5_files:
        raise FileNotFoundError(
            f"{animal}/{date}: manifest.dlc_h5_files is empty"
        )
    lik_thr_centering = 0.7  # Phase 4 centering threshold
    sig = _param_sig(center_mode, lik_thr_centering)
    parquet_dir = resolver.dlc_centered_parquet_dir(center_mode, animal)
    parquet_path = parquet_dir / (
        f"{manifest.dlc_h5_files[0].name}.intermediate.{sig}.parquet"
    )
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"{animal}/{date}/{center_mode}: centered parquet missing at {parquet_path}"
        )
    return read_centered_parquet(parquet_path)


def _load_cleaned_baseline_mask(animal: str, date: dt.date, bodypart: str,
                                resolver: PathResolver,
                                expected_n_frames: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (is_baseline_fill, likelihood_raw) aligned to centered-parquet rows.

    Cleaned-traces parquet has dense frame_idx 0..N-1 (verified 2026-05-27
    on PS54/2025-05-06 for both bodyparts), so row i of the centered
    parquet corresponds to cleaned_df.iloc[i].
    """
    path = resolver.cleaned_trace(bodypart, animal, date)
    if not path.exists():
        raise FileNotFoundError(
            f"{animal}/{date}/{bodypart}: cleaned_trace parquet missing at {path}"
        )
    cdf = pd.read_parquet(path)
    if len(cdf) != expected_n_frames:
        raise ValueError(
            f"{animal}/{date}/{bodypart}: cleaned_traces len {len(cdf)} != "
            f"centered parquet len {expected_n_frames}"
        )
    fi = cdf["frame_idx"].to_numpy()
    if not np.array_equal(fi, np.arange(expected_n_frames)):
        raise ValueError(
            f"{animal}/{date}/{bodypart}: cleaned_traces frame_idx is not 0..N-1 dense"
        )
    return (cdf["is_baseline_fill"].to_numpy(),
            cdf["likelihood_raw"].to_numpy())


def _ws_cam_frame_bounds(manifest, resolver: PathResolver,
                        n_cam_frames: int) -> tuple[int, int]:
    """Mirror render_on_demand._ws_cam_frame_bounds for whole_session scope."""
    align_path = manifest.alignment_template
    if align_path is None or not align_path.exists():
        align_path = resolver.alignment_template_for_reading(
            manifest.animal, manifest.date, cam="cam2",
        )
    aln = np.load(str(align_path), allow_pickle=True)
    lut = np.asarray(aln["sig_camIdx__idx_ws"], dtype=float)
    finite = np.isfinite(lut)
    if not finite.any():
        return 0, n_cam_frames - 1
    valid = lut[finite]
    lo = int(np.clip(np.floor(valid.min()), 0, n_cam_frames - 1))
    hi = int(np.clip(np.ceil(valid.max()), 0, n_cam_frames - 1))
    return lo, hi


def _build_production_window(
    animal: str, date: dt.date, scope: str,
    resolver: PathResolver, n_frames: int, tone_config: dict,
) -> MaskWindow | None:
    """Build production window mask for the given scope. Returns None for
    tone scopes with zero qualifying tone events."""
    animal_info = get_animal(animal)
    manifest = build_manifest(animal, date, resolver, animal_info,
                              analysis_context="dlc.spatial")

    if scope == "whole_session":
        lo, hi = _ws_cam_frame_bounds(manifest, resolver, n_frames)
        m = np.zeros(n_frames, dtype=bool)
        m[lo:hi + 1] = True
        return MaskWindow(m, label_str="whole")

    # tone_all / tone_L / tone_R
    trial_group = {"tone_all": "all", "tone_L": "L", "tone_R": "R"}[scope]
    licks = resolver.spout_licks_and_rewards_npz(animal, date)
    if not licks.exists():
        raise FileNotFoundError(f"{animal}/{date}: licks NPZ missing")
    tone_ws = load_tone_events(
        licks, trial_group,
        wavesurfer_sides_match_mouse_sides=animal_info.wavesurfer_sides_match_mouse_sides,
    )
    if len(tone_ws) == 0:
        return None
    align_path = manifest.alignment_template
    if align_path is None or not align_path.exists():
        align_path = resolver.alignment_template_for_reading(
            animal, date, cam="cam2",
        )
    aln = np.load(str(align_path), allow_pickle=True)
    sig_camIdx = aln["sig_camIdx__idx_ws"]
    fps = float(tone_config.get("fps", 250.0))
    tone_window = build_tone_aligned_window(
        tone_ws, sig_camIdx, TONE_WINDOW_MS, fps, n_frames,
    )
    # Use the EventAlignedWindow's internal mask via its public select_frames.
    # We can't call select_frames(df) here yet (caller has df); instead the
    # mask is stored on the instance — pull it via select_frames over a
    # zero-row placeholder is not possible. Use the private attribute by
    # accepting the contract (window_selector.py line 105 sets _mask).
    return MaskWindow(tone_window._mask.copy(),
                      label_str=f"tone_{int(TONE_WINDOW_MS[0])}_{int(TONE_WINDOW_MS[1])}ms_{trial_group}")


def _build_config_for_hist(
    spatial_config: dict, tone_config: dict, bodypart: str, center_mode: str,
    lik_thr_override: float | None,
) -> tuple[dict, tuple[float, float] | None, int]:
    """Match production's spatial_config build (tone-family lik_thr override
    via deepcopy of bodyparts entry). Returns (config, x_range, nbins).
    """
    try:
        family = lookup_tone_family(tone_config, bodypart, center_mode)
    except KeyError:
        family = {"likelihood_thresholds": [0.8], "x_range": None}
    bp_x_range = (tuple(family["x_range"])
                  if family.get("x_range") is not None else None)
    lik_thresholds = family.get("likelihood_thresholds", [0.8])
    family_lik_thr = lik_thresholds[0] if lik_thresholds else 0.8
    effective_lik = (family_lik_thr if lik_thr_override is None
                     else lik_thr_override)
    nbins_cfg = tone_config.get("default_nbins", [80, 80])
    nbins = int(nbins_cfg[0]) if isinstance(nbins_cfg, list) else int(nbins_cfg)

    cfg = dict(spatial_config)
    cfg["bodyparts"] = dict(cfg.get("bodyparts", {}))
    bp_existing = dict(cfg["bodyparts"].get(bodypart, {}))
    bp_existing["likelihood_threshold"] = effective_lik
    cfg["bodyparts"][bodypart] = bp_existing
    return cfg, bp_x_range, nbins


def _wasserstein_2(H_R1_prop: np.ndarray, H_R3_prop: np.ndarray,
                  xedges: np.ndarray, yedges: np.ndarray) -> float:
    """Exact W-2 between two 2D histograms via POT's network simplex
    (ot.emd2 with squared-Euclidean cost matrix on bin centers).

    Prunes zero-mass bins to keep the cost matrix small.
    """
    xc = 0.5 * (xedges[:-1] + xedges[1:])
    yc = 0.5 * (yedges[:-1] + yedges[1:])
    Xc, Yc = np.meshgrid(xc, yc, indexing="ij")
    pts = np.column_stack([Xc.ravel(), Yc.ravel()])
    a = H_R1_prop.ravel().astype(np.float64)
    b = H_R3_prop.ravel().astype(np.float64)
    nz = (a > 0) | (b > 0)
    if not nz.any():
        return 0.0
    pts = pts[nz]
    a = a[nz]
    b = b[nz]
    # Re-normalize to 1.0 (POT requires probability vectors that sum equal).
    a = a / a.sum() if a.sum() > 0 else a
    b = b / b.sum() if b.sum() > 0 else b
    if a.sum() == 0 or b.sum() == 0:
        return float("nan")
    M = ot.dist(pts, pts, metric="sqeuclidean")
    cost = ot.emd2(a, b, M, numItermax=1_000_000)
    return float(np.sqrt(max(cost, 0.0)))


def _wasserstein_1(H_R1_prop: np.ndarray, H_R3_prop: np.ndarray,
                  xedges: np.ndarray, yedges: np.ndarray) -> float:
    """Exact W-1 via POT's network simplex on pruned histogram bins.

    Same machinery as ``_wasserstein_2`` but with Euclidean (not squared)
    ground metric. scipy's ``wasserstein_distance_nd`` is O(n²) memory in
    the sample count via HiGHS-MILP and blows up at 20k samples; POT's
    bin-level EMD scales by nonzero-bin count which is bounded by
    nbins² = 6400.
    """
    xc = 0.5 * (xedges[:-1] + xedges[1:])
    yc = 0.5 * (yedges[:-1] + yedges[1:])
    Xc, Yc = np.meshgrid(xc, yc, indexing="ij")
    pts = np.column_stack([Xc.ravel(), Yc.ravel()])
    a = H_R1_prop.ravel().astype(np.float64)
    b = H_R3_prop.ravel().astype(np.float64)
    nz = (a > 0) | (b > 0)
    if not nz.any():
        return 0.0
    pts = pts[nz]
    a = a[nz]
    b = b[nz]
    a = a / a.sum() if a.sum() > 0 else a
    b = b / b.sum() if b.sum() > 0 else b
    if a.sum() == 0 or b.sum() == 0:
        return float("nan")
    M = ot.dist(pts, pts, metric="euclidean")
    return float(ot.emd2(a, b, M, numItermax=1_000_000))


def _kl_divergence(H_R1_prop: np.ndarray, H_R3_prop: np.ndarray) -> float:
    """KL(R3 ‖ R1) with epsilon smoothing on R1."""
    p = H_R3_prop.ravel().astype(np.float64)
    q = H_R1_prop.ravel().astype(np.float64) + KL_EPS
    p_sum = p.sum()
    if p_sum <= 0:
        return float("nan")
    p = p / p_sum
    q = q / q.sum()
    mask = p > 0
    return float(np.sum(p[mask] * np.log(p[mask] / q[mask])))


def _render_png(H_counts: np.ndarray, extent: list[float], bodypart: str,
                center_mode: str, spatial_config: dict, title: str,
                path: Path, n_total_frames: int | None = None) -> None:
    """Match render_h_counts_panel's PNG output (LogNorm + per-bp cmap).

    Trimmed down — audit PNGs are diagnostic, not production figures.
    """
    bp_cfg = spatial_config.get("bodyparts", {}).get(bodypart, {}) or {}
    cmap_name = bp_cfg.get("cmap", "viridis")
    per_mode_block = (bp_cfg.get("per_center_mode", {}) or {}).get(
        center_mode, {}
    ) or {}
    xlim = per_mode_block.get("xlim") or (extent[0], extent[1])
    ylim = per_mode_block.get("ylim") or (extent[2], extent[3])

    fig, ax = plt.subplots(figsize=(7, 6))
    total = float(n_total_frames) if (n_total_frames and n_total_frames > 0) else float(H_counts.sum())
    if total > 0 and H_counts.sum() > 0:
        H_prop = H_counts / total
        try:
            cmap = plt.get_cmap(cmap_name)
        except ValueError:
            cmap = plt.get_cmap("viridis")
        finite_nonzero = H_prop[np.isfinite(H_prop) & (H_prop > 0)]
        if finite_nonzero.size > 0:
            vmin = float(finite_nonzero.min())
            vmax = float(H_prop.max())
            norm = mcolors.LogNorm(vmin=max(vmin, 1e-10), vmax=vmax)
        else:
            norm = None
        im = ax.imshow(H_prop.T, origin="lower", extent=extent, cmap=cmap,
                       aspect="auto", norm=norm)
        plt.colorbar(im, ax=ax, label="frame proportion")
    else:
        ax.text(0.5, 0.5, "no data", ha="center", va="center",
                transform=ax.transAxes)

    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.invert_yaxis()
    ax.set_xlabel(f"{bodypart}_x (centered, px)")
    ax.set_ylabel(f"{bodypart}_y (centered, px)")
    ax.set_title(title, fontsize=10)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=120, bbox_inches="tight")
    plt.close(fig)


def _process_cell(
    animal: str, date: dt.date, severity: str,
    bodypart: str, center_mode: str, scope: str,
    resolver: PathResolver, defaults: dict, out_root: Path,
) -> CellResult | None:
    """Render R1/R2/R3 for one cell and compute W1/W2/KL."""
    spatial_config = defaults["dlc_spatial"]
    tone_config = defaults["dlc_spatial_tone_aligned"]

    df = _load_centered_df(animal, date, center_mode, resolver)
    n_frames = len(df)
    baseline_fill, lik_raw = _load_cleaned_baseline_mask(
        animal, date, bodypart, resolver, expected_n_frames=n_frames,
    )

    prod_window = _build_production_window(
        animal, date, scope, resolver, n_frames, tone_config,
    )
    if prod_window is None:
        logger.info("%s/%s/%s/%s: skip (no tone events for this group)",
                    animal, date, bodypart, scope)
        return None
    prod_mask = prod_window.select_frames(df)
    n_total_in_scope = int(prod_mask.sum())

    cleaned_mask = prod_mask & ~baseline_fill  # R2 / R3 scope membership

    # Build configs.
    cfg_R1, x_range, nbins = _build_config_for_hist(
        spatial_config, tone_config, bodypart, center_mode, lik_thr_override=None,
    )
    cfg_R2 = cfg_R1  # same lik gate as R1
    cfg_R3, _, _ = _build_config_for_hist(
        spatial_config, tone_config, bodypart, center_mode, lik_thr_override=0.0,
    )

    # Build histograms.
    window_R1 = prod_window
    window_R2 = MaskWindow(cleaned_mask, label_str=f"{prod_window.label}_NObaseline")
    window_R3 = MaskWindow(cleaned_mask, label_str=f"{prod_window.label}_NObaseline_R3")

    h_R1 = build_histogram(df, bodypart, cfg_R1, center_mode=center_mode,
                          x_range=x_range, nbins=nbins, window=window_R1,
                          n_total_frames=n_total_in_scope)
    h_R2 = build_histogram(df, bodypart, cfg_R2, center_mode=center_mode,
                          x_range=x_range, nbins=nbins, window=window_R2,
                          n_total_frames=n_total_in_scope)
    h_R3 = build_histogram(df, bodypart, cfg_R3, center_mode=center_mode,
                          x_range=x_range, nbins=nbins, window=window_R3,
                          n_total_frames=n_total_in_scope)
    if h_R1 is None or h_R3 is None:
        logger.info("%s/%s/%s/%s: skip (R1 or R3 hist is None)",
                    animal, date, bodypart, scope)
        return None

    n_R1 = int(h_R1["H_counts"].sum())
    n_R2 = int(h_R2["H_counts"].sum()) if h_R2 is not None else 0
    n_R3 = int(h_R3["H_counts"].sum())

    # Pre-aggregate census stats over the scope-selected frames.
    bf_in_scope = baseline_fill[prod_mask]
    lik_in_scope = lik_raw[prod_mask]
    bf_frac = float(bf_in_scope.mean()) if len(bf_in_scope) else 0.0
    real_in_scope = ~bf_in_scope
    if real_in_scope.any():
        lik_below = (lik_in_scope[real_in_scope] < 0.8).mean()
    else:
        lik_below = 0.0

    # Renders.
    bp_dir = out_root / "renders" / animal / date.isoformat() / bodypart / scope
    extent = h_R1["extent"]
    _render_png(h_R1["H_counts"], extent, bodypart, center_mode, spatial_config,
                title=f"R1 {animal}/{date}/{bodypart}/{scope}  n={n_R1}",
                path=bp_dir / "R1.png", n_total_frames=n_total_in_scope)
    if h_R2 is not None:
        _render_png(h_R2["H_counts"], h_R2["extent"], bodypart, center_mode,
                    spatial_config,
                    title=f"R2 {animal}/{date}/{bodypart}/{scope}  n={n_R2}",
                    path=bp_dir / "R2.png", n_total_frames=n_total_in_scope)
    _render_png(h_R3["H_counts"], h_R3["extent"], bodypart, center_mode,
                spatial_config,
                title=f"R3 {animal}/{date}/{bodypart}/{scope}  n={n_R3}",
                path=bp_dir / "R3.png", n_total_frames=n_total_in_scope)

    # Metrics R1 vs R3 on H_proportion (Q17-style: counts / scope_total).
    p_R1 = h_R1["H_counts"] / max(n_total_in_scope, 1)
    p_R3 = h_R3["H_counts"] / max(n_total_in_scope, 1)
    if p_R1.sum() == 0 or p_R3.sum() == 0:
        w1 = w2 = kl = float("nan")
    else:
        # Re-normalize each separately for distance metrics (so we compare
        # distribution shapes; the n_R1 vs n_R3 difference is captured in
        # the count columns).
        p_R1_n = p_R1 / p_R1.sum()
        p_R3_n = p_R3 / p_R3.sum()
        w1 = _wasserstein_1(p_R1_n, p_R3_n, h_R1["xedges"], h_R1["yedges"])
        w2 = _wasserstein_2(p_R1_n, p_R3_n, h_R1["xedges"], h_R1["yedges"])
        kl = _kl_divergence(p_R1_n, p_R3_n)

    if (np.isfinite(w1) and w1 >= W1_MAX) or \
       (np.isfinite(w2) and w2 >= W2_MAX) or \
       (np.isfinite(kl) and kl >= KL_MAX):
        verdict = "FAIL"
    elif not (np.isfinite(w1) and np.isfinite(w2) and np.isfinite(kl)):
        verdict = "NA"
    else:
        verdict = "PASS"

    return CellResult(
        animal=animal, date=date.isoformat(), severity=severity,
        bodypart=bodypart, center_mode=center_mode, scope=scope,
        n_frames_total=n_total_in_scope,
        n_frames_R1=n_R1, n_frames_R2=n_R2, n_frames_R3=n_R3,
        baseline_fill_frac=bf_frac,
        lik_below_thresh_among_real=float(lik_below),
        W1_R1_R3=w1, W2_R1_R3=w2, KL_R3_R1=kl,
        verdict=verdict,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-root", default=".scratch_v7_spatial_audit",
                        help="Output root (gitignored).")
    parser.add_argument("--only-animal", default=None,
                        help="Restrict to one animal (debug).")
    parser.add_argument("--only-scope", default=None,
                        help="Restrict to one scope (debug).")
    args = parser.parse_args()
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    resolver = PathResolver()
    defaults = load_defaults()

    rows: list[CellResult] = []
    for animal, date, severity in SESSIONS:
        if args.only_animal and animal != args.only_animal:
            continue
        for bodypart, center_mode in BODYPARTS:
            for scope in SCOPES:
                if args.only_scope and scope != args.only_scope:
                    continue
                logger.info("processing %s/%s/%s/%s", animal, date, bodypart, scope)
                try:
                    res = _process_cell(animal, date, severity, bodypart,
                                        center_mode, scope, resolver, defaults,
                                        out_root)
                except Exception as e:
                    logger.exception("FAIL %s/%s/%s/%s: %s", animal, date,
                                     bodypart, scope, e)
                    continue
                if res is None:
                    continue
                rows.append(res)
                logger.info("  W1=%.3f W2=%.3f KL=%.4f verdict=%s",
                            res.W1_R1_R3, res.W2_R1_R3, res.KL_R3_R1, res.verdict)

    metrics_path = out_root / "metrics" / "wasserstein_kl.csv"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    df_out = pd.DataFrame([r.__dict__ for r in rows])
    df_out.to_csv(metrics_path, index=False)

    verdict_overall = "FAIL" if any(r.verdict == "FAIL" for r in rows) else \
                       ("NA" if not rows else "PASS")
    verdict_doc = {
        "overall": verdict_overall,
        "thresholds": {"W1_max": W1_MAX, "W2_max": W2_MAX, "KL_max": KL_MAX},
        "n_cells_total": len(rows),
        "n_fail": int(sum(1 for r in rows if r.verdict == "FAIL")),
        "n_pass": int(sum(1 for r in rows if r.verdict == "PASS")),
        "n_na":   int(sum(1 for r in rows if r.verdict == "NA")),
        "fail_cells": [
            {"animal": r.animal, "date": r.date, "bodypart": r.bodypart,
             "scope": r.scope, "W1": r.W1_R1_R3, "W2": r.W2_R1_R3,
             "KL": r.KL_R3_R1}
            for r in rows if r.verdict == "FAIL"
        ],
    }
    (out_root / "verdict.json").write_text(json.dumps(verdict_doc, indent=2))
    logger.info("VERDICT: %s (fail=%d pass=%d na=%d, %d cells)",
                verdict_overall, verdict_doc["n_fail"], verdict_doc["n_pass"],
                verdict_doc["n_na"], verdict_doc["n_cells_total"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
