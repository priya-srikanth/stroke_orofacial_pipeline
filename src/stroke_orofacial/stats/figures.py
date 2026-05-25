"""Phase 9 Task 7 — per-animal figure family (forest plots, recovery curves,
paired-difference distributions, V1/V2/V3 grid for headlines).

Per-endpoint output layout:

    pipeline_outputs/stats/figures/
      per_animal/<endpoint>/
        recovery_curve.{svg,png}              # cohort overlay (reuses Task 6 fn)
        paired_diff_distribution_<axis>.{svg,png}
      headlines/<endpoint>/                   # 7 headline kinematics
        v1_per_session_recovery.{svg,png}
        v2_per_bin_recovery.{svg,png}
        v3_per_epoch_boxplot.{svg,png}
      forest_plots/
        forest_<axis>_<granularity>.{svg,png} # cohort-level

V1/V2/V3 designs per Addendum #8:

- V1: per-animal × per_session scatter with the cohort recovery LMM
  line + bootstrap CI ribbon overlay. Each animal plotted as a
  distinct colored series; cohort mean ± SEM aggregated above the
  scatter.
- V2: per-animal × per_bin aggregated mean ± SEM (bins per
  cohort_bin_size days). Line + shaded ribbon per animal; cohort
  mean overlaid in bold black.
- V3: per-animal × per_epoch boxplot. Each epoch on x-axis (pre +
  acute + sub_acute + chronic); boxes side-by-side per side (L/R for
  side-aware endpoints, single box for global endpoints). Per-comparison
  q-value annotations from headline_summary v2: asterisk markers
  reading from `q_within_endpoint_holm` for each `pre_vs_<epoch>`
  comparison (* < 0.05, ** < 0.01, *** < 0.001).

Side handling per Addendum #8 H: L / R overlaid as color-coded series
in V1/V2; side-by-side boxes in V3.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# Significance marker thresholds per Addendum #8 V3 annotation spec.
_SIG_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (0.001, "***"),
    (0.01, "**"),
    (0.05, "*"),
)


# Side colors aligned with visual_gate.SIDE_COLORS (loaded from defaults
# at module import to avoid drift across plot layers).
def _side_colors() -> dict[str, str]:
    try:
        from stroke_orofacial.spout_behavior.visual_gate import SIDE_COLORS
        return dict(SIDE_COLORS)
    except Exception:
        return {"L": "#1f77b4", "R": "#d62728", "global": "0.3"}


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _parse_details_dict(details_str: Any) -> dict:
    """Parse the str(dict) repr stored in `_all.csv` `details` column.

    Substitutes nan/inf bare literals (rejected by ast.literal_eval)
    with None before parsing. Mirrors the same parser in visual_gate +
    build_task_5_headline_summary.
    """
    if not isinstance(details_str, str) or not details_str.strip():
        return {}
    try:
        import ast
        cleaned = re.sub(
            r"\b(nan|NaN|NAN|inf|-inf|Inf)\b", "None", details_str,
        )
        return ast.literal_eval(cleaned)
    except Exception:
        return {}


def load_cohort_parquet(
    slug: str, inputs_root: Path,
) -> pd.DataFrame:
    """Concat all per-animal parquets for one endpoint slug."""
    d = inputs_root / slug
    if not d.exists():
        return pd.DataFrame()
    parquets = sorted(d.glob("*.parquet"))
    if not parquets:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(p) for p in parquets], ignore_index=True)


def _per_session_view(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse to one row per (animal, date, side) via mean of value.

    Drops sentinel + NaN rows. If `granularity` column exists, filters
    to ``granularity == "per_session"`` first.
    """
    if df.empty:
        return df
    if "granularity" in df.columns and (df["granularity"] == "per_session").any():
        df = df[df["granularity"] == "per_session"]
    if "is_sentinel" in df.columns:
        df = df[~df["is_sentinel"].astype(bool)]
    df = df.dropna(subset=["value"])
    by_cols = ["animal", "date", "rel_day"]
    if "side" in df.columns:
        by_cols.append("side")
    return df.groupby(by_cols, as_index=False)["value"].mean()


def _epoch_label_for_rel_day(rel_day: int, eb: dict) -> str:
    if rel_day <= 0:
        return "pre"
    if rel_day <= eb["acute"]:
        return "acute"
    if rel_day <= eb["subacute"]:
        return "sub_acute"
    if rel_day >= eb["chronic_min"]:
        return "chronic"
    return "transitional_gap"


def _load_animal_epoch_boundaries() -> dict[str, dict]:
    from stroke_orofacial.animals import load_animals
    out: dict[str, dict] = {}
    for aid, info in load_animals().items():
        eb = info.epoch_boundaries
        out[aid] = {
            "acute": eb.acute_max_rel_day,
            "subacute": eb.subacute_max_rel_day,
            "chronic_min": eb.chronic_min_rel_day,
        }
    return out


def _attach_epoch_labels(
    df: pd.DataFrame, eb_by_animal: dict[str, dict],
) -> pd.DataFrame:
    df = df.copy()
    df["epoch_label"] = [
        _epoch_label_for_rel_day(int(rd), eb_by_animal[a])
        for a, rd in zip(df["animal"], df["rel_day"])
    ]
    return df


def load_recovery_lmm_result(
    slug: str, results_root: Path,
) -> Any | None:
    """Load the cohort recovery LMM FitResult-like proxy for one endpoint."""
    csv_path = (
        results_root / "recovery" / "per_session" / f"{slug}.csv"
    )
    if not csv_path.exists():
        return None
    import csv as _csv
    rows = list(_csv.DictReader(open(csv_path, "r", encoding="utf-8")))
    if not rows:
        return None
    r = rows[0]
    details = _parse_details_dict(r.get("details", ""))

    class _Proxy:
        pass

    p = _Proxy()
    p.details = details
    p.model_name = r.get("model_name", "")
    p.statistic = float(r["statistic"]) if r.get("statistic") else float("nan")
    p.p_value = float(r["p_value"]) if r.get("p_value") else float("nan")
    return p


def load_headline_rows_for_endpoint(
    slug: str, headline_summary_path: Path,
) -> pd.DataFrame:
    if not headline_summary_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(headline_summary_path)
    return df[df["endpoint_slug"] == slug].copy()


# ---------------------------------------------------------------------------
# Significance marker helper
# ---------------------------------------------------------------------------

def _sig_marker(q: float) -> str:
    if not np.isfinite(q):
        return "ns"
    for thr, marker in _SIG_THRESHOLDS:
        if q < thr:
            return marker
    return "ns"


# ---------------------------------------------------------------------------
# V1 — per-animal × per_session scatter + cohort LMM fit + CI ribbon
# ---------------------------------------------------------------------------

def plot_v1_per_session_recovery(
    cohort_df: pd.DataFrame,
    *,
    endpoint_slug: str,
    fit_proxy: Any | None,
    title: str | None = None,
    ylabel: str | None = None,
    figsize: tuple[float, float] = (8.0, 4.0),
):
    """V1 figure: per-animal scatter at per_session granularity with
    cohort LMM fit + bootstrap CI ribbon overlay.

    Per Addendum #8 V1 spec.
    """
    import matplotlib.pyplot as plt
    from stroke_orofacial.spout_behavior.recovery_trajectories import (
        TrajectoryPoint, plot_recovery_trajectories_with_fit,
    )

    per_session = _per_session_view(cohort_df)
    if per_session.empty:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, "No per-session data", ha="center", va="center",
                transform=ax.transAxes)
        return fig

    side_col = "side" if "side" in per_session.columns else None
    points: list[TrajectoryPoint] = []
    for _, row in per_session.iterrows():
        d = row["date"]
        if not isinstance(d, dt.date):
            d = dt.date.fromisoformat(str(d))
        points.append(TrajectoryPoint(
            animal=row["animal"], date=d,
            day_relative_to_stroke=int(row["rel_day"]),
            endpoint_name=endpoint_slug, metric_path=endpoint_slug,
            value=float(row["value"]),
            group=row[side_col] if side_col else "all",
        ))

    fig = plot_recovery_trajectories_with_fit(
        points, fit_proxy,
        title=title or f"{endpoint_slug} — V1 per_session recovery",
        ylabel=ylabel or endpoint_slug,
        show_individual=True,
        show_cohort_mean=True,
        cohort_points=points,
    )
    fig.set_size_inches(*figsize)
    return fig


# ---------------------------------------------------------------------------
# V2 — per-animal × per_bin mean ± SEM
# ---------------------------------------------------------------------------

def _bin_rel_day(rel_day: int, bin_size: int) -> int:
    """Map rel_day to bin index. Negative pre, ceiling for post."""
    if rel_day <= 0:
        return -int(np.ceil(-rel_day / bin_size))
    return int(np.ceil(rel_day / bin_size))


def plot_v2_per_bin_recovery(
    cohort_df: pd.DataFrame,
    *,
    endpoint_slug: str,
    bin_size: int = 7,
    title: str | None = None,
    ylabel: str | None = None,
    figsize: tuple[float, float] = (8.0, 4.0),
):
    """V2 figure: per-animal × per_bin aggregated mean ± SEM.

    Lines + shaded SEM ribbon per animal; cohort mean overlaid in bold
    black. One bin = `bin_size` days (default 7).
    """
    import matplotlib.pyplot as plt

    df = _per_session_view(cohort_df)
    if df.empty:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        return fig

    df = df.copy()
    df["bin_idx"] = [_bin_rel_day(int(rd), bin_size) for rd in df["rel_day"]]
    df["bin_center_day"] = df["bin_idx"] * bin_size - (bin_size // 2 if df["bin_idx"].iloc[0] > 0 else 0)
    # Use bin_idx * bin_size as a stable x; doesn't need to be the exact midpoint.
    df["bin_x"] = df["bin_idx"] * bin_size

    fig, ax = plt.subplots(figsize=figsize)
    colors = _side_colors()
    has_sides = "side" in df.columns and df["side"].nunique() > 1 and not (df["side"] == "global").all()

    if has_sides:
        for side, side_df in df.groupby("side"):
            agg = (
                side_df.groupby(["animal", "bin_idx", "bin_x"], as_index=False)["value"].mean()
            )
            cohort = agg.groupby("bin_x")["value"].agg(["mean", "sem"]).reset_index()
            ax.errorbar(
                cohort["bin_x"], cohort["mean"], yerr=cohort["sem"],
                color=colors.get(str(side), "0.3"),
                marker="o", linewidth=2.0, capsize=3, label=f"{side}",
            )
            for animal, anim_df in agg.groupby("animal"):
                ax.plot(
                    anim_df["bin_x"], anim_df["value"], alpha=0.25,
                    color=colors.get(str(side), "0.3"), linewidth=0.8,
                )
    else:
        agg = df.groupby(["animal", "bin_idx", "bin_x"], as_index=False)["value"].mean()
        cohort = agg.groupby("bin_x")["value"].agg(["mean", "sem"]).reset_index()
        ax.errorbar(
            cohort["bin_x"], cohort["mean"], yerr=cohort["sem"],
            color="black", marker="o", linewidth=2.0, capsize=3, label="cohort mean",
        )
        for animal, anim_df in agg.groupby("animal"):
            ax.plot(
                anim_df["bin_x"], anim_df["value"], alpha=0.30,
                linewidth=0.8, label=animal,
            )

    ax.axvline(0.5, color="crimson", linestyle="--", linewidth=1.0)
    ax.axhline(0, color="0.85", linewidth=0.8, zorder=0)
    ax.set_xlabel(f"Day relative to stroke (bin size = {bin_size}d)")
    ax.set_ylabel(ylabel or endpoint_slug)
    ax.set_title(title or f"{endpoint_slug} — V2 per_bin recovery")
    ax.legend(loc="best", fontsize=8, framealpha=0.85)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# V3 — per-animal × per_epoch boxplot with significance annotations
# ---------------------------------------------------------------------------

def plot_v3_per_epoch_boxplot(
    cohort_df: pd.DataFrame,
    *,
    endpoint_slug: str,
    headline_rows: pd.DataFrame | None = None,
    eb_by_animal: dict[str, dict] | None = None,
    title: str | None = None,
    ylabel: str | None = None,
    figsize: tuple[float, float] = (8.0, 4.5),
):
    """V3 figure: per-animal × per_epoch boxplot with per-comparison
    q-value asterisk annotations from headline summary v2.

    Per Addendum #8 V3 spec + Addendum #10 q-value plumbing.

    Annotations use ``q_within_endpoint_holm`` from each pre_vs_<epoch>
    row of `headline_rows` (filtered to ``endpoint_slug``). Asterisk
    markers: ``*`` (q<0.05), ``**`` (q<0.01), ``***`` (q<0.001),
    ``ns`` otherwise.
    """
    import matplotlib.pyplot as plt

    if eb_by_animal is None:
        eb_by_animal = _load_animal_epoch_boundaries()

    df = _per_session_view(cohort_df)
    if df.empty:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        return fig
    df = _attach_epoch_labels(df, eb_by_animal)
    df = df[df["epoch_label"] != "transitional_gap"]

    epochs = ["pre", "acute", "sub_acute", "chronic"]
    epochs_present = [e for e in epochs if e in df["epoch_label"].unique()]
    if len(epochs_present) < 2:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, f"Only {len(epochs_present)} epoch(s) present",
                ha="center", va="center", transform=ax.transAxes)
        return fig

    has_sides = "side" in df.columns and df["side"].nunique() > 1 and not (df["side"] == "global").all()
    colors = _side_colors()

    fig, ax = plt.subplots(figsize=figsize)
    epoch_positions = list(range(len(epochs_present)))

    if has_sides:
        sides = sorted(df["side"].unique())
        offsets = np.linspace(-0.2, 0.2, len(sides))
        for i, side in enumerate(sides):
            side_df = df[df["side"] == side]
            per_animal_means = (
                side_df.groupby(["animal", "epoch_label"])["value"].mean().reset_index()
            )
            data_per_epoch = [
                per_animal_means.loc[per_animal_means["epoch_label"] == e, "value"].to_numpy()
                for e in epochs_present
            ]
            positions = [p + offsets[i] for p in epoch_positions]
            bp = ax.boxplot(
                data_per_epoch, positions=positions, widths=0.18,
                patch_artist=True, showfliers=False,
            )
            for patch in bp["boxes"]:
                patch.set_facecolor(colors.get(side, "0.3"))
                patch.set_alpha(0.55)
            # Scatter per-animal means.
            for ep_idx, ep in enumerate(epochs_present):
                vals = data_per_epoch[ep_idx]
                jitter = np.random.default_rng(seed=hash((endpoint_slug, side, ep)) % 2**31).normal(
                    0, 0.02, size=len(vals),
                )
                ax.scatter(
                    [positions[ep_idx] + j for j in jitter], vals,
                    color=colors.get(side, "0.3"), alpha=0.7, s=14, zorder=3,
                    edgecolor="white", linewidth=0.4,
                )
        ax.set_xticks(epoch_positions)
        ax.set_xticklabels(epochs_present)
        # Two-color legend.
        from matplotlib.patches import Patch
        handles = [
            Patch(facecolor=colors.get(s, "0.3"), alpha=0.55, label=str(s))
            for s in sides
        ]
        ax.legend(handles=handles, loc="best", fontsize=8)
    else:
        per_animal_means = (
            df.groupby(["animal", "epoch_label"])["value"].mean().reset_index()
        )
        data_per_epoch = [
            per_animal_means.loc[per_animal_means["epoch_label"] == e, "value"].to_numpy()
            for e in epochs_present
        ]
        bp = ax.boxplot(
            data_per_epoch, positions=epoch_positions, widths=0.4,
            patch_artist=True, showfliers=False,
        )
        for patch in bp["boxes"]:
            patch.set_facecolor("0.7")
            patch.set_alpha(0.55)
        # Scatter per-animal means with jitter.
        for ep_idx, ep in enumerate(epochs_present):
            vals = data_per_epoch[ep_idx]
            jitter = np.random.default_rng(seed=hash((endpoint_slug, ep)) % 2**31).normal(
                0, 0.05, size=len(vals),
            )
            ax.scatter(
                [epoch_positions[ep_idx] + j for j in jitter], vals,
                color="black", alpha=0.7, s=14, zorder=3,
                edgecolor="white", linewidth=0.4,
            )
        ax.set_xticks(epoch_positions)
        ax.set_xticklabels(epochs_present)

    # Significance annotations from headline summary v2.
    if headline_rows is not None and not headline_rows.empty:
        eligible = headline_rows[
            (headline_rows["axis"] == "recovery")
            & headline_rows["comparison"].isin(("pre_vs_acute", "pre_vs_sub_acute", "pre_vs_chronic"))
        ]
        comparison_to_epoch = {
            "pre_vs_acute": "acute",
            "pre_vs_sub_acute": "sub_acute",
            "pre_vs_chronic": "chronic",
        }
        # Marker positioned above each post-epoch box at the top of the data
        # range for that epoch.
        ymax = ax.get_ylim()[1]
        ymin = ax.get_ylim()[0]
        marker_y = ymax + 0.04 * (ymax - ymin)
        for _, row in eligible.iterrows():
            epoch = comparison_to_epoch[row["comparison"]]
            if epoch not in epochs_present:
                continue
            ep_idx = epochs_present.index(epoch)
            q = row.get("q_within_endpoint_holm")
            try:
                q = float(q)
            except (TypeError, ValueError):
                q = float("nan")
            marker = _sig_marker(q)
            ax.text(
                ep_idx, marker_y, marker, ha="center", va="bottom",
                fontsize=11, fontweight="bold", color="C3",
            )
        # Bump ylim to accommodate marker.
        ax.set_ylim(ymin, ymax + 0.12 * (ymax - ymin))

    ax.set_xlabel("Epoch")
    ax.set_ylabel(ylabel or endpoint_slug)
    ax.set_title(title or f"{endpoint_slug} — V3 per_epoch boxplot")
    ax.axhline(0, color="0.85", linewidth=0.8, zorder=0)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Forest plot — cohort-level, one per (axis, granularity)
# ---------------------------------------------------------------------------

def plot_forest_by_endpoint(
    headline_df: pd.DataFrame,
    *,
    axis: str,
    comparison: str,
    title: str | None = None,
    figsize_per_row: float = 0.30,
):
    """Cohort-level forest plot of effect_size + 95% CI across endpoints
    for one (axis, comparison) family.

    Endpoints split into subplots by ``effect_size_metric`` — metrics
    aren't comparable across types (a ms shift on tongue_lick1_t_peak
    isn't on the same scale as a spatial Wasserstein delta). One column
    per metric, sorted by effect_size within column. Confirmatory
    endpoints highlighted in red with larger markers.
    """
    import matplotlib.pyplot as plt

    sub = headline_df[
        (headline_df["axis"] == axis) & (headline_df["comparison"] == comparison)
    ].copy()
    if sub.empty:
        fig, ax = plt.subplots(figsize=(6.0, 2.0))
        ax.text(0.5, 0.5, f"No rows for ({axis}, {comparison})",
                ha="center", va="center", transform=ax.transAxes)
        return fig

    metrics = sorted(sub["effect_size_metric"].dropna().unique().tolist())
    n_panels = len(metrics)
    if n_panels == 0:
        fig, ax = plt.subplots(figsize=(6.0, 2.0))
        ax.text(0.5, 0.5, "No effect_size_metric column",
                ha="center", va="center", transform=ax.transAxes)
        return fig

    # Per-panel row counts → vertical layout where each panel scales to
    # its own row count.
    panel_dfs = {
        m: sub[sub["effect_size_metric"] == m]
        .sort_values("effect_size", ascending=True)
        .reset_index(drop=True)
        for m in metrics
    }
    fig_heights = [max(1.8, len(df) * figsize_per_row) for df in panel_dfs.values()]
    fig, axes = plt.subplots(
        n_panels, 1, figsize=(8.0, sum(fig_heights)),
        squeeze=False, gridspec_kw={"height_ratios": fig_heights},
    )

    for ax, metric in zip(axes.flat, metrics):
        df_m = panel_dfs[metric]
        y_positions = np.arange(len(df_m))
        for i, (_, row) in enumerate(df_m.iterrows()):
            ci_lo, ci_hi = row.get("ci_lower"), row.get("ci_upper")
            eff = row["effect_size"]
            is_conf = bool(row["is_confirmatory"])
            if pd.notna(ci_lo) and pd.notna(ci_hi):
                ax.plot([ci_lo, ci_hi], [i, i], color="black", linewidth=1.2)
            ax.scatter(
                [eff], [i],
                color="C3" if is_conf else "0.4",
                s=42 if is_conf else 22,
                zorder=3, edgecolor="black", linewidth=0.4,
            )
        ax.set_yticks(y_positions)
        ax.set_yticklabels(df_m["endpoint_slug"].tolist(), fontsize=8)
        ax.axvline(0, color="0.5", linewidth=0.8, linestyle="--")
        ax.set_xlabel(f"Effect size ({metric})")
        ax.set_title(f"{metric}  (n={len(df_m)})", fontsize=10)

    fig.suptitle(title or f"Forest: {axis} / {comparison}", y=1.005)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Paired-difference distribution per (endpoint, axis)
# ---------------------------------------------------------------------------

def plot_paired_diff_distribution(
    cohort_df: pd.DataFrame,
    *,
    endpoint_slug: str,
    axis: str = "pre_post",
    post_epoch: str = "acute",
    eb_by_animal: dict[str, dict] | None = None,
    figsize: tuple[float, float] = (6.0, 3.5),
):
    """Per-endpoint paired-difference distribution.

    For axis=pre_post: distribution of per-animal (post_epoch_mean −
    pre_mean) across the 8 cohort animals. Shown as a strip-plot + KDE
    + a vertical line at zero.
    """
    import matplotlib.pyplot as plt

    df = _per_session_view(cohort_df)
    if df.empty:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        return fig

    if eb_by_animal is None:
        eb_by_animal = _load_animal_epoch_boundaries()
    df = _attach_epoch_labels(df, eb_by_animal)
    if axis == "pre_post":
        left, right = post_epoch, "pre"
        per_animal = (
            df.groupby(["animal", "epoch_label"])["value"].mean().unstack("epoch_label")
        )
    elif axis == "ipsi_contra" and "ipsi_contra" in df.columns:
        left, right = "ipsi", "contra"
        per_animal = (
            df.groupby(["animal", "ipsi_contra"])["value"].mean().unstack("ipsi_contra")
        )
    else:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, f"axis={axis} not supported here",
                ha="center", va="center", transform=ax.transAxes)
        return fig

    if left not in per_animal.columns or right not in per_animal.columns:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, f"Missing {left} or {right} for this endpoint",
                ha="center", va="center", transform=ax.transAxes)
        return fig
    diffs = (per_animal[left] - per_animal[right]).dropna().to_numpy()

    fig, ax = plt.subplots(figsize=figsize)
    if diffs.size > 0:
        # KDE via scipy if available; fallback to histogram.
        try:
            from scipy.stats import gaussian_kde
            kde = gaussian_kde(diffs)
            xs = np.linspace(diffs.min() - 0.2 * (diffs.ptp() or 1.0),
                             diffs.max() + 0.2 * (diffs.ptp() or 1.0), 200)
            ax.plot(xs, kde(xs), color="C3", linewidth=2.0, label="KDE")
            ax.fill_between(xs, 0, kde(xs), color="C3", alpha=0.18)
        except Exception:
            ax.hist(diffs, bins=8, color="C3", alpha=0.5)
        # Strip plot of individual diffs.
        ax.scatter(
            diffs, np.zeros_like(diffs) - 0.05,
            color="black", s=30, zorder=3, edgecolor="white", linewidth=0.4,
            label="per-animal diff",
        )
    ax.axvline(0, color="0.4", linestyle="--", linewidth=1.0)
    ax.set_xlabel(f"{left} − {right}")
    ax.set_ylabel("Density")
    ax.set_title(f"{endpoint_slug} — paired diff distribution ({axis})")
    ax.legend(loc="best", fontsize=8, framealpha=0.85)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Save helper
# ---------------------------------------------------------------------------

def save_figure(fig: Any, out_path: Path, *, dpi: int = 150) -> tuple[Path, Path]:
    """Save fig as both SVG + PNG; create parent dir."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    svg = out_path.with_suffix(".svg")
    png = out_path.with_suffix(".png")
    fig.savefig(svg, bbox_inches="tight")
    fig.savefig(png, dpi=dpi, bbox_inches="tight")
    return svg, png
