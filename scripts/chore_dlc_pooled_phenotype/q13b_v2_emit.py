"""Q13b v2 re-emit — phase-aligned scalar endpoints, filtered + ipsi/contra.

Chore ``vChore-dlc-pooled-phenotype-unification`` Stage 4 (run first per the
locked Q13b -> Q13/Q13c -> Q12 order).

v2 differences vs the shipped (no_filter) Q13b phase-aligned endpoint figures:

1. **On-the-fly DLC filtering** (the phase-aligned endpoints are NOT in the
   materialized ``filtered_v1`` tree, so the filter is applied here using the
   filter classes directly, Priya 2026-05-29):
   - ``DlcTrialFilter`` (phase-aligned-trajectory family ``min_licks_per_trial``)
     joined per-trial via ``build_dlc_pertrial_lick_frame`` — at
     ``min_licks_per_trial=1`` this is ~no-op (a finite endpoint already
     implies >=1 lick) but coded for the locked per-family config.
   - ``DlcSessionFilter`` (``min_trials_with_detected_lick``) is the real gate;
     sparse severe-acute (animal, date, side) sessions are dropped.
2. **Ipsi/contra recoding**: the rig-frame ``side`` (L/R) is replaced by the
   lesion-relative ipsi/contra label; signed endpoint values are sign-flipped
   for right-stroke animals (no-op on the current all-L cohort). Sham animals
   are excluded.
3. **Line + per-session jittered-dots convention** (Stage-1
   ``render_line_with_jitter_dots``) replacing the box plots. Pooled line walks
   the per-phenotype median across epochs; per-session medians are the dots.

Output (both scopes):
  figures: stats/figures/phenotype_pooled/phase_aligned_endpoints/<scope>/v2/
  results: stats/results/phenotype_pooled/phase_aligned_endpoints/<scope>/v2/
where ``<scope>`` is ``4_tier`` (default) or ``3_tier`` (``--remap-phenotypes 3tier``).

Stage-0 surfacing trigger (Priya 2026-05-29): if any phenotype x epoch cell
goes to n_sessions_kept=0 in v2 while the no_filter sibling has n>0, the run
prints a ``CELL-LOSS`` warning so the operator can STOP before fanout.

Usage::

    # PS46 pilot, 4-tier.
    python -m scripts.chore_dlc_pooled_phenotype.q13b_v2_emit \\
        --animals PS46 --overwrite force

    # Full cohort, both scopes.
    python -m scripts.chore_dlc_pooled_phenotype.q13b_v2_emit \\
        --animals PS46,PS47,PS48,PS49,PS50,PS51,PS54,PS55 \\
        --remap-phenotypes none --overwrite force
    python -m scripts.chore_dlc_pooled_phenotype.q13b_v2_emit \\
        --animals PS46,PS47,PS48,PS49,PS50,PS51,PS54,PS55 \\
        --remap-phenotypes 3tier --overwrite force
"""
from __future__ import annotations

import argparse
import dataclasses
import logging
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from stroke_orofacial.animals import load_animals  # noqa: E402
from stroke_orofacial.cohort_filters import (  # noqa: E402
    DLC_SESSION_N_KEPT_LICKS_COL,
    DLC_SESSION_N_TRIALS_TOTAL_COL,
    DLC_SESSION_N_TRIALS_WITH_LICK_COL,
    DlcSessionFilter,
    build_dlc_pertrial_lick_frame,
    compute_dlc_session_lick_stats,
    load_dlc_filter_spec_from_defaults,
    resolve_dlc_trial_filter,
)
from stroke_orofacial.config_loader import load_defaults  # noqa: E402
from stroke_orofacial.figures._line_with_jitter_dots import (  # noqa: E402
    AGGREGATION_SUBTITLE,
    render_line_with_jitter_dots,
)
from stroke_orofacial.figures.palette import (  # noqa: E402
    PHENOTYPE_ORDER,
    phenotype_display_name,
    phenotype_marker,
    phenotype_palette,
)
from stroke_orofacial.figures.phase_aligned_endpoint_stats import (  # noqa: E402
    DELTA_ENDPOINT_DISPLAY_NAMES,
    ENDPOINT_DISPLAY_NAMES,
    EPOCH_DISPLAY_NAMES,
    EPOCH_ORDER,
    compute_phase_aligned_endpoint_stats,
)
from stroke_orofacial.ipsi_contra_recoding import (  # noqa: E402
    cue_side_to_ipsi_contra,
    is_sham,
    signed_value_to_ipsi_contra,
)
from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.aggregators import (  # noqa: E402
    PHASE_ALIGNED_ENDPOINT_SLUGS,
    aggregate_per_session_mean,
    aggregate_phenotype_pooled_mean_sem,
    apply_baseline_delta,
    attach_phenotype_and_epoch,
    compute_per_animal_baseline,
    enumerate_session_dates,
    load_session_phase_aligned_endpoints_long,
)

logger = logging.getLogger("chore.q13b_v2_emit")

COHORT_8 = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")

# All three phase-aligned endpoints are signed (angle / x), so all get the
# right-stroke sign-flip (no-op on the all-L cohort). There is no y endpoint
# here (y is symmetric and lives in the Q13c trajectory family).
SIGNED_ENDPOINTS: frozenset[str] = frozenset(PHASE_ALIGNED_ENDPOINT_SLUGS)

IPSI_CONTRA_ORDER: tuple[str, ...] = ("ipsi", "contra")
PHENOTYPE_REMAP_3TIER: dict[str, str] = {"moderate-severe": "moderate"}
PHENOTYPE_ORDER_3TIER: tuple[str, ...] = ("mild", "moderate", "severe")

FAMILY_FIG_SUBDIR = "stats/figures/phenotype_pooled/phase_aligned_endpoints"
FAMILY_RESULTS_SUBDIR = "stats/results/phenotype_pooled/phase_aligned_endpoints"
V2_SUBTITLE = (
    "Source: filtered_v1 (on-the-fly DlcSession+TrialFilter) + ipsi/contra "
    "coding + line+jitter convention (chore vChore-dlc-pooled-phenotype-unification)"
)
PROVENANCE = "v2_filtered_v1_ipsi_contra"


# ---------------------------------------------------------------------------
# Load + filter + recode
# ---------------------------------------------------------------------------


def _session_stats_frame(
    animal: str, resolver: PathResolver,
) -> pd.DataFrame:
    """Per-(animal, date, side) DLC v7-kept session lick stats for one animal."""
    rows: list[dict[str, object]] = []
    for d in enumerate_session_dates(animal, resolver):
        stats = compute_dlc_session_lick_stats(animal, d, resolver)
        if stats is None:
            continue
        for s in stats:
            rows.append({
                "animal": s.animal, "date": s.date, "side": s.side,
                DLC_SESSION_N_TRIALS_TOTAL_COL: s.n_trials_of_side,
                DLC_SESSION_N_TRIALS_WITH_LICK_COL: s.n_trials_with_detected_lick,
                DLC_SESSION_N_KEPT_LICKS_COL: s.n_kept_licks,
            })
    return pd.DataFrame(rows)


def load_filtered_recoded_long(
    *,
    animals: list[str],
    animals_map: dict,
    resolver: PathResolver,
    defaults: dict,
    apply_filter: bool = True,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Build the per-trial long-form, filtered + ipsi/contra-recoded.

    Returns ``(long_df, report)`` where ``long_df`` has the canonical
    per-session-aggregator columns (``animal, date, side, endpoint, value``)
    with ``side`` already the ipsi/contra label and values sign-flipped for
    right-stroke animals. ``report`` carries filter counts for the manifest.
    """
    trial_filter = resolve_dlc_trial_filter(
        "dlc_tongue_trajectory_metrics", defaults,
    )
    session_filter: DlcSessionFilter = load_dlc_filter_spec_from_defaults(defaults)
    logger.info(
        "TrialFilter min_licks_per_trial=%s; SessionFilter "
        "min_trials_with_detected_lick=%s",
        trial_filter.min_licks_per_trial,
        session_filter.min_trials_with_detected_lick,
    )

    # 1) Per-trial endpoints long-form + per-trial lick-count join.
    frames: list[pd.DataFrame] = []
    for animal in animals:
        if is_sham(animals_map[animal]):
            logger.info("[%s] sham — excluded from ipsi/contra v2.", animal)
            continue
        for d in enumerate_session_dates(animal, resolver):
            ep = load_session_phase_aligned_endpoints_long(animal, d, resolver)
            if ep.empty:
                continue
            licks = build_dlc_pertrial_lick_frame(animal, d, resolver)
            if licks is not None:
                ep = ep.merge(
                    licks[["animal", "date", "side", "trial_index",
                           "n_licks_per_trial"]],
                    on=["animal", "date", "side", "trial_index"],
                    how="left",
                )
            else:
                ep["n_licks_per_trial"] = np.nan
            frames.append(ep)
    if not frames:
        return pd.DataFrame(columns=[
            "animal", "date", "side", "endpoint", "value",
        ]), {"n_trials_in": 0, "n_trials_kept": 0,
             "n_sessions_in": 0, "n_sessions_kept": 0}
    long_df = pd.concat(frames, ignore_index=True)
    n_trials_in = len(long_df)

    # 2) Per-trial filter (drop rows below min_licks_per_trial). Rows with a
    #    missing lick join are kept (the endpoint is finite, so >=1 lick).
    if apply_filter and not trial_filter.is_pass_through():
        keep = (
            long_df["n_licks_per_trial"].isna()
            | (long_df["n_licks_per_trial"] >= trial_filter.min_licks_per_trial)
        )
        long_df = long_df[keep].copy()
    n_trials_kept = len(long_df)

    # 3) Session filter (drop sparse (animal, date, side) sessions).
    sess_frames = [_session_stats_frame(a, resolver) for a in animals]
    sess_frames = [f for f in sess_frames if not f.empty]
    n_sessions_in = n_sessions_kept = 0
    if apply_filter and sess_frames and not session_filter.is_pass_through():
        sess_df = pd.concat(sess_frames, ignore_index=True)
        kept_sess, sess_result = session_filter.filter(sess_df)
        n_sessions_in = sess_result.n_sessions_in
        n_sessions_kept = sess_result.n_sessions_kept
        kept_keys = {
            (r["animal"], r["date"], r["side"])
            for _, r in kept_sess.iterrows()
        }
        long_df = long_df[
            long_df.apply(
                lambda r: (r["animal"], r["date"], r["side"]) in kept_keys,
                axis=1,
            )
        ].copy()

    # 4) Ipsi/contra recode: relabel side + sign-flip signed endpoints.
    rec_side: list[str] = []
    rec_value: list[float] = []
    for _, r in long_df.iterrows():
        lat = animals_map[r["animal"]].stroke_laterality
        rec_side.append(cue_side_to_ipsi_contra(r["side"], lat))
        v = float(r["value"])
        if r["endpoint"] in SIGNED_ENDPOINTS:
            v = signed_value_to_ipsi_contra(v, lat)
        rec_value.append(v)
    long_df = long_df.assign(side=rec_side, value=rec_value)

    report = {
        "n_trials_in": n_trials_in, "n_trials_kept": n_trials_kept,
        "n_sessions_in": n_sessions_in, "n_sessions_kept": n_sessions_kept,
    }
    return long_df[["animal", "date", "side", "endpoint", "value"]], report


# ---------------------------------------------------------------------------
# Renderer (line + per-session jittered dots, ipsi/contra panels)
# ---------------------------------------------------------------------------


#: Ipsi/contra panel titles (all-L cohort → ipsi = mouse-L, contra = mouse-R,
#: matching the Q14 reference panel labels).
_PANEL_TITLES: dict[str, str] = {
    "ipsi": "Ipsi (mouse-L)",
    "contra": "Contra (mouse-R)",
}


def _draw_endpoint_panel(
    ax: object,
    *,
    per_session_df: pd.DataFrame,
    pooled_df: pd.DataFrame,
    endpoint: str,
    side: str,
    phenotype_order: tuple[str, ...],
    n_animals_by_phenotype: dict[str, int],
    value_col: str,
    pooled_value_col: str,
    sem_col: str,
    is_delta: bool,
) -> None:
    """Draw one ipsi/contra panel: per-phenotype line + SEM bars + dots."""
    sess = per_session_df[
        (per_session_df["endpoint"] == endpoint)
        & (per_session_df["side"] == side)
    ]
    pooled = pooled_df[
        (pooled_df["endpoint"] == endpoint) & (pooled_df["side"] == side)
    ]
    if is_delta:
        ax.axhline(0.0, color="0.6", linewidth=0.8, alpha=0.6, zorder=0)

    for phenotype in phenotype_order:
        color = phenotype_palette(phenotype)
        marker = phenotype_marker(phenotype)
        p_pool = pooled[pooled["recovery_phenotype"] == phenotype]
        p_sess = sess[sess["recovery_phenotype"] == phenotype]

        line_x: list[int] = []
        line_y: list[float] = []
        line_yerr: list[float] = []
        scatter_centers: list[int] = []
        scatter_values: list[np.ndarray] = []
        for ei, epoch in enumerate(EPOCH_ORDER):
            prow = p_pool[p_pool["epoch_label"] == epoch]
            if not prow.empty:
                m = float(prow[pooled_value_col].iloc[0])
                if np.isfinite(m):
                    line_x.append(ei)
                    line_y.append(m)
                    sem = float(prow[sem_col].iloc[0]) if sem_col in prow else np.nan
                    line_yerr.append(sem)
            cell = p_sess[p_sess["epoch_label"] == epoch]
            vals = cell[value_col].to_numpy(dtype=np.float64)
            vals = vals[np.isfinite(vals)]
            if vals.size:
                scatter_centers.append(ei)
                scatter_values.append(vals)
        if not line_x and not scatter_centers:
            continue
        n_an = n_animals_by_phenotype.get(phenotype, 0)
        label = f"{phenotype_display_name(phenotype)} (n={n_an})"
        render_line_with_jitter_dots(
            ax,
            line_x=line_x, line_y=line_y,
            line_yerr=line_yerr if any(np.isfinite(line_yerr)) else None,
            scatter_centers=scatter_centers, scatter_values=scatter_values,
            color=color, marker=marker, label=label,
        )

    ax.set_xticks(list(range(len(EPOCH_ORDER))))
    ax.set_xticklabels(
        [EPOCH_DISPLAY_NAMES.get(e, e) for e in EPOCH_ORDER], fontsize=12,
    )
    ax.set_xlim(-0.5, len(EPOCH_ORDER) - 0.5)
    ax.set_xlabel("Epoch", fontsize=13)
    ax.set_title(_PANEL_TITLES.get(side, side), fontsize=12)
    ax.legend(loc="best", fontsize=8, framealpha=0.9)


def render_endpoint_v2_figure(
    *,
    per_session_df: pd.DataFrame,
    pooled_df: pd.DataFrame,
    endpoint: str,
    phenotype_order: tuple[str, ...],
    output_path: Path,
    sides: tuple[str, ...] = IPSI_CONTRA_ORDER,
    value_col: str = "mean",
    pooled_value_col: str = "mean",
    sem_col: str = "sem",
    display_names: dict[str, str] | None = None,
    aggregation_subtitle: str = AGGREGATION_SUBTITLE,
    is_delta: bool = False,
    dpi: int = 150,
) -> Path:
    """One endpoint figure with side-by-side Ipsi + Contra panels (Q14 layout).

    Each panel: per-phenotype line through the pooled mean with SEM error
    bars, faded jittered per-session dots, phenotype color + marker. Legend
    shows ``n_animals`` per phenotype (Q14 form). Delta figures get a y=0
    reference line. A two-line footer (provenance + aggregation method) sits
    at the bottom-left.
    """
    names = display_names or ENDPOINT_DISPLAY_NAMES
    fig, axes = plt.subplots(
        1, len(sides), figsize=(6.5 * len(sides), 5.6), dpi=dpi, sharey=True,
    )
    if len(sides) == 1:
        axes = [axes]

    # n_animals per phenotype tier (constant across epochs/sides; Q14 form).
    n_an_by = {
        p: int(
            per_session_df.loc[
                per_session_df["recovery_phenotype"] == p, "animal",
            ].nunique()
        )
        for p in phenotype_order
    }

    for ax, side in zip(axes, sides):
        _draw_endpoint_panel(
            ax,
            per_session_df=per_session_df, pooled_df=pooled_df,
            endpoint=endpoint, side=side, phenotype_order=phenotype_order,
            n_animals_by_phenotype=n_an_by,
            value_col=value_col, pooled_value_col=pooled_value_col,
            sem_col=sem_col, is_delta=is_delta,
        )
    axes[0].set_ylabel(names.get(endpoint, endpoint), fontsize=12)

    fig.suptitle(names.get(endpoint, endpoint), fontsize=14, y=0.99)
    fig.text(
        0.01, 0.005, f"{V2_SUBTITLE}\n{aggregation_subtitle}",
        fontsize=7, va="bottom", ha="left",
    )
    fig.tight_layout(rect=[0.0, 0.07, 1.0, 0.97])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format="svg")
    fig.savefig(output_path.with_suffix(".png"), format="png", dpi=dpi)
    plt.close(fig)
    return output_path


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def parse_animals(raw: str) -> list[str]:
    out: list[str] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if not re.fullmatch(r"PS\d{2}", tok):
            raise argparse.ArgumentTypeError(f"bad animal id {tok!r}")
        out.append(tok)
    if not out:
        raise argparse.ArgumentTypeError("no animals")
    return out


_CELL_KEYS = ["recovery_phenotype", "epoch_label", "side", "endpoint"]


def _cell_loss_check(
    pooled_filtered: pd.DataFrame,
    pooled_nofilter: pd.DataFrame,
    scope: str,
) -> list[str]:
    """Flag cells populated in the no-filter pool but emptied by the v2 filter.

    Priya's surfacing trigger (2026-05-29): a (phenotype, epoch, side,
    endpoint) cell with ``n_sessions>0`` in the no_filter pool but 0 (or
    absent) in the filtered v2 pool is a real loss the operator must STOP on.
    """
    nf = pooled_nofilter[pooled_nofilter["n_sessions"] > 0][
        _CELL_KEYS + ["n_sessions"]
    ].rename(columns={"n_sessions": "n_nofilter"})
    f = pooled_filtered[_CELL_KEYS + ["n_sessions"]].rename(
        columns={"n_sessions": "n_filtered"},
    )
    merged = nf.merge(f, on=_CELL_KEYS, how="left")
    merged["n_filtered"] = merged["n_filtered"].fillna(0)
    lost = merged[merged["n_filtered"] == 0]
    warns: list[str] = []
    for _, r in lost.iterrows():
        warns.append(
            f"CELL-LOSS[{scope}]: {r['recovery_phenotype']}/{r['epoch_label']}"
            f"/{r['side']}/{r['endpoint']} -> no_filter n={int(r['n_nofilter'])}"
            f" but v2 n=0"
        )
    return warns


def run_scope(
    *,
    long_df: pd.DataFrame,
    long_df_nofilter: pd.DataFrame,
    animals_map: dict,
    scope: str,
    phenotype_order: tuple[str, ...],
    resolver: PathResolver,
    overwrite: str,
) -> dict[str, object]:
    """Aggregate + stats + render one scope (4_tier or 3_tier).

    Mean+SEM session-pooled convention (matches Q14): per-session means
    pooled to a per-(phenotype, epoch, side, endpoint) mean with
    SEM = SD/sqrt(n_sessions). The Wilcoxon test pairs per-animal means
    upstream (aggregator="mean").
    """
    per_session = aggregate_per_session_mean(long_df)
    per_session_meta = attach_phenotype_and_epoch(per_session, animals_map)
    pooled = aggregate_phenotype_pooled_mean_sem(
        per_session_meta, value_col="mean", by_side=True,
    )
    stats_df = compute_phase_aligned_endpoint_stats(
        per_session_meta,
        phenotype_order=phenotype_order,
        side_order=IPSI_CONTRA_ORDER,
        aggregator="mean",
        value_col="mean",
    )

    # No-filter pooled (same recode, no DLC filter) for the cell-loss check.
    per_session_nf = attach_phenotype_and_epoch(
        aggregate_per_session_mean(long_df_nofilter), animals_map,
    )
    pooled_nf = aggregate_phenotype_pooled_mean_sem(
        per_session_nf, value_col="mean", by_side=True,
    )

    # Baseline-delta layer (per-animal pre-stroke mean of per-session means).
    baseline = compute_per_animal_baseline(per_session_meta, value_col="mean")
    delta_df = apply_baseline_delta(per_session_meta, baseline, value_col="mean")
    if "delta_mean" in delta_df.columns and not delta_df.empty:
        pooled_delta = aggregate_phenotype_pooled_mean_sem(
            delta_df, value_col="delta_mean", by_side=True,
        )
    else:
        pooled_delta = pooled

    fig_base = resolver.pipeline_outputs(subdir=FAMILY_FIG_SUBDIR) / scope / "v2"
    res_base = resolver.pipeline_outputs(subdir=FAMILY_RESULTS_SUBDIR) / scope / "v2"
    fig_base.mkdir(parents=True, exist_ok=True)
    res_base.mkdir(parents=True, exist_ok=True)

    ok: list[str] = []
    skip: list[str] = []
    # One 2-panel (ipsi+contra) figure per endpoint, for raw + delta layers.
    for endpoint in PHASE_ALIGNED_ENDPOINT_SLUGS:
        for kind, src, pooled_src, vcol, names in (
            ("raw", per_session_meta, pooled, "mean", ENDPOINT_DISPLAY_NAMES),
            ("delta", delta_df, pooled_delta, "delta_mean",
             DELTA_ENDPOINT_DISPLAY_NAMES),
        ):
            if vcol not in src.columns:
                continue
            fname = (
                f"{endpoint}_v2.svg" if kind == "raw"
                else f"delta_{endpoint}_v2.svg"
            )
            target = fig_base / fname
            if target.exists() and overwrite == "skip":
                skip.append(fname)
                continue
            render_endpoint_v2_figure(
                per_session_df=src,
                pooled_df=pooled_src,
                endpoint=endpoint,
                phenotype_order=phenotype_order,
                output_path=target,
                value_col=vcol,
                display_names=names,
                is_delta=(kind == "delta"),
            )
            ok.append(fname)

    # Provenance-stamped CSVs.
    pooled = pooled.assign(provenance=PROVENANCE)
    stats_df = stats_df.assign(provenance=PROVENANCE)
    per_session_meta = per_session_meta.assign(provenance=PROVENANCE)
    pooled.to_csv(res_base / "phenotype_pooled_mean_sem.csv", index=False)
    stats_df.to_csv(res_base / "phase_aligned_endpoint_stats.csv", index=False)
    per_session_meta.to_csv(res_base / "per_session_means.csv", index=False)

    warns = _cell_loss_check(pooled, pooled_nf, scope)
    return {
        "scope": scope, "n_figures": len(ok), "n_skip": len(skip),
        "n_pooled_rows": len(pooled), "fig_base": str(fig_base),
        "cell_loss": warns,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--animals", type=parse_animals, default=list(COHORT_8))
    parser.add_argument("--overwrite", choices=("skip", "force"), default="skip")
    parser.add_argument(
        "--remap-phenotypes", choices=("none", "3tier", "both"), default="none",
    )
    parser.add_argument(
        "--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S",
    )

    resolver = PathResolver()
    defaults = load_defaults()
    animals = args.animals
    animals_map_full = {a: i for a, i in load_animals().items() if a in animals}
    missing = set(animals) - set(animals_map_full)
    if missing:
        logger.error("animals missing from animals.yaml: %s", sorted(missing))
        return 1

    logger.info("=" * 72)
    logger.info("Q13b v2 re-emit — animals=%s overwrite=%s remap=%s",
                ",".join(animals), args.overwrite, args.remap_phenotypes)
    logger.info("=" * 72)

    long_df, report = load_filtered_recoded_long(
        animals=animals, animals_map=animals_map_full,
        resolver=resolver, defaults=defaults, apply_filter=True,
    )
    long_df_nofilter, _ = load_filtered_recoded_long(
        animals=animals, animals_map=animals_map_full,
        resolver=resolver, defaults=defaults, apply_filter=False,
    )
    logger.info(
        "Filter report: trials %d->%d, sessions %d->%d; long rows=%d "
        "(no_filter rows=%d)",
        report["n_trials_in"], report["n_trials_kept"],
        report["n_sessions_in"], report["n_sessions_kept"], len(long_df),
        len(long_df_nofilter),
    )
    if long_df.empty:
        logger.error("No rows after load+filter; aborting.")
        return 1

    scopes: list[tuple[str, tuple[str, ...], dict]] = []
    if args.remap_phenotypes in ("none", "both"):
        scopes.append(("4_tier", PHENOTYPE_ORDER, animals_map_full))
    if args.remap_phenotypes in ("3tier", "both"):
        remapped = {
            a: dataclasses.replace(
                info,
                recovery_phenotype=PHENOTYPE_REMAP_3TIER.get(
                    info.recovery_phenotype, info.recovery_phenotype),
            )
            for a, info in animals_map_full.items()
        }
        scopes.append(("3_tier", PHENOTYPE_ORDER_3TIER, remapped))

    all_warns: list[str] = []
    for scope, phenotype_order, amap in scopes:
        result = run_scope(
            long_df=long_df, long_df_nofilter=long_df_nofilter,
            animals_map=amap, scope=scope,
            phenotype_order=phenotype_order, resolver=resolver,
            overwrite=args.overwrite,
        )
        logger.info(
            "[%s] figures=%d skip=%d pooled_rows=%d -> %s",
            scope, result["n_figures"], result["n_skip"],
            result["n_pooled_rows"], result["fig_base"],
        )
        all_warns.extend(result["cell_loss"])

    if all_warns:
        logger.warning("=" * 72)
        logger.warning("CELL-LOSS warnings (%d) — STOP and review before fanout:",
                       len(all_warns))
        for w in all_warns:
            logger.warning("  %s", w)
        logger.warning("=" * 72)

    logger.info("Q13b v2 re-emit complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
