"""Phase 7a.6 — visual gate runner: side-by-side legacy vs consolidated grids.

Produces 2-col comparison PNGs (legacy | consolidated) for each plot
family, sample, and bodypart. NOT a numerical pass/fail — outputs are
for Priya's eyeball verdict during the C7.x iteration loop.

Per the kickoff §"Task 7":
- Aspect-aware ``fig_h = panel_w / consolidated_aspect`` for crisp
  consolidated PNG rendering (matplotlib hard-limits ~100 in / DPI).
- LANCZOS resampling in PIL for compare-grid downsampling (matches
  7a.5 C6.2 fix — fine line detail preserved on 30-100× downsample).
- Comparison grid per (bodypart, plot_family, animal, date, window).

Default sample (kickoff sample-session-set + Cowork C7.1 review focus):

- ``PS46/2025-03-07`` — pre-stroke baseline (Task 6 parity verified
  this is in scope for both bodyparts).
- ``PS55/2025-05-02`` — post-stroke d+2 (PS55 d0 = 2025-04-30); the
  PS55 STRESS session.

Per (animal, date, bodypart, window): emit comparison grids for the
five static-plot families (individual_sessions, trial_overlays,
session_overlays, binned_overlays, mean_trace). ``mean_video`` is
visual-gate-only at the animation level and excluded from the still-
PNG comparison grid runner — visual verification of MP4/GIF runs
through the cohort-emit output directly.

CLI::

    python tests/scripts/parity_phase7a6_visual_gate.py \\
        --animals PS46 \\
        --bodyparts tongue,jaw \\
        --windows 100,1000 \\
        --sample-dates auto \\
        --emit-root .scratch_7a6/cohort_run/comparison_grids
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parity_phase7a3_tongue_pertrial as h7a3  # type: ignore[import]  # noqa: E402

from stroke_orofacial.paths import PathResolver  # noqa: E402

# Default "first-pass" sample. Two animals, one each from pre-stroke
# baseline and post-stroke recovery, that exercise the layout fixes:
#   - PS46/2025-03-07: pre-stroke baseline; both bodyparts present.
#   - PS55/2025-05-02: post-stroke d+2; PS55 STRESS session.
DEFAULT_SAMPLE: tuple[tuple[str, dt.date], ...] = (
    ("PS46", dt.date(2025, 3, 7)),
    ("PS55", dt.date(2025, 5, 2)),
)
DEFAULT_BODYPARTS: tuple[str, ...] = ("tongue", "jaw")
DEFAULT_WINDOWS: tuple[tuple[int, int], ...] = ((100, 1000),)

# Static-plot families covered by the comparison grid runner. mean_video
# excluded — animation frames don't compare meaningfully as a PNG grid.
PER_SESSION_FAMILIES: tuple[str, ...] = (
    "individual_sessions",
    "trial_overlays",
)
COHORT_FAMILIES: tuple[str, ...] = (
    "session_overlays",
    "binned_overlays",
    "mean_trace",
)

# Per-bodypart legacy center mode (matches the consolidated config block).
_LEGACY_CENTER_MODE = {
    "tongue": "centered_spout_midpoint",
    "jaw": "centered_eye_midpoint",
}


def _legacy_kinematics_dir(
    animal: str, bodypart: str, real_resolver: PathResolver,
) -> Path:
    """Match the legacy
    ``{animal}/{animal}_{bodypart}_kinematics/kinematics_figures/
    {center_mode}/`` tree on MICROSCOPE.
    """
    cm = _LEGACY_CENTER_MODE[bodypart]
    return (
        real_resolver.dlc_output_dir(animal)
        / f"{animal}_{bodypart}_kinematics" / "kinematics_figures" / cm
    )


def _consolidated_dir(
    animal: str, bodypart: str, real_resolver: PathResolver,
    *,
    tone_pre_ms: int, tone_post_ms: int, plot_family: str,
) -> Path:
    cm = _LEGACY_CENTER_MODE[bodypart]
    return real_resolver.mean_sem_visual_dir(
        bodypart,
        center_mode=cm,
        tone_pre_ms=tone_pre_ms,
        tone_post_ms=tone_post_ms,
        plot_family=plot_family,
        animal=animal,
    )


def _per_session_legacy_filename(
    animal: str, date: dt.date, family: str,
    cam: str, interp_version: str, win_tag: str, rel_day_label: str,
) -> str:
    """Legacy filename pattern (matches what's saved on MICROSCOPE under
    ``individual_sessions/`` and ``trial_overlays/``):

        {animal}_{date}_{win_tag}_{cam}_{interp}_meanSEM_2x2[_trials][_legend].png
    """
    date_str = date.strftime("%Y%m%d")
    base = (
        f"{animal}_{date_str}_{win_tag}_{cam}_"
        f"{interp_version}_meanSEM_2x2"
    )
    if family == "trial_overlays":
        base += "_trials"
    if rel_day_label:
        base += f"_{rel_day_label}"
    return base + ".png"


def _resolve_legacy_per_session_path(
    animal: str, date: dt.date, bodypart: str, family: str,
    pre_ms: int, post_ms: int, real_resolver: PathResolver,
) -> Path | None:
    """Glob the legacy dir for the closest matching PNG. Robust to small
    legacy filename variations across animals (e.g., presence/absence of
    leading-minus in pre-token, version suffix differences).
    """
    legacy_dir = _legacy_kinematics_dir(animal, bodypart, real_resolver) / family
    if not legacy_dir.exists():
        return None
    date_str = date.strftime("%Y%m%d")
    # Use a permissive glob; pre-token may be ``-100`` or ``100``.
    win_glob_a = f"-{pre_ms}pre-{post_ms}post"
    win_glob_b = f"{pre_ms}pre-{post_ms}post"
    family_token = "_meanSEM_2x2_trials_" if family == "trial_overlays" else "_meanSEM_2x2_"
    for win_tag in (win_glob_a, win_glob_b):
        pattern = f"{animal}_{date_str}_{win_tag}_*{family_token}*.png"
        matches = sorted(legacy_dir.glob(pattern))
        if matches:
            # Prefer exact match if possible; else first.
            return matches[0]
    return None


# For session_overlays / binned_overlays, pick a canonical label so the
# legacy + consolidated panes show the SAME (axis × side) variant of the
# 4-fold family. Y_mouseLtones is the most informative single subject
# for layout verification (Y is the primary licking axis; L the
# canonical default-prefer side).
_COHORT_LABEL_DEFAULT = "Y_mouseLtones"


def _resolve_legacy_cohort_path(
    animal: str, bodypart: str, family: str,
    pre_ms: int, post_ms: int, real_resolver: PathResolver,
    *, label: str = _COHORT_LABEL_DEFAULT,
) -> Path | None:
    """Locate the legacy cohort PNG. Differs by family — session_overlays
    and binned_overlays sit under ``overlays/`` and ``binned_overlays/``
    subdirs respectively; mean_trace under ``mean_xy_overlays/``.

    For session_overlays + binned_overlays, the ``label`` arg picks one
    of the 4 (axis × side) variants so the legacy + consolidated panes
    in the comparison grid show the SAME subject.

    Returns the first sample matching a permissive glob, or None if no
    legacy file is found.
    """
    legacy_root = _legacy_kinematics_dir(animal, bodypart, real_resolver)
    win_token_a = f"-{pre_ms}pre-{post_ms}post"
    win_token_b = f"{pre_ms}pre-{post_ms}post"

    if family == "session_overlays":
        candidate_dir = legacy_root / "overlays"
    elif family == "binned_overlays":
        candidate_dir = legacy_root / "binned_overlays"
    elif family == "mean_trace":
        candidate_dir = legacy_root / "mean_xy_overlays"
    else:
        return None
    if not candidate_dir.exists():
        return None

    if family == "session_overlays":
        for win in (win_token_a, win_token_b):
            matches = sorted(
                candidate_dir.glob(
                    f"{animal}_*_{win}_*overlay_{label}*.png",
                ),
            )
            if matches:
                return matches[0]
        return None
    if family == "binned_overlays":
        for win in (win_token_a, win_token_b):
            matches = sorted(
                candidate_dir.glob(
                    f"{animal}_*_{win}_*binnedOverlay_{label}*.png",
                ),
            )
            if matches:
                return matches[0]
        return None
    if family == "mean_trace":
        # mean_trace doesn't have the (axis × side) family split — single
        # PNG per (animal, window). Glob permissively across legacy
        # variants (filename evolved between tongue cell 45 and jaw 32).
        for win in (win_token_a, win_token_b):
            patterns = [
                f"{animal}_*sessionMeanXY*win-{pre_ms}to{post_ms}ms*.png",
                f"{animal}_*sessionMeanXY_interp-v5p3_win{win}*.png",
                f"{animal}_*sessionMeanXY*.png",
            ]
            for pat in patterns:
                matches = sorted(candidate_dir.glob(pat))
                if matches:
                    return matches[0]
        return None
    return None


def _consolidated_per_session_path(
    animal: str, date: dt.date, bodypart: str, family: str,
    pre_ms: int, post_ms: int, real_resolver: PathResolver,
    *, interp_version: str = "v5p3", cam: str = "cam2",
) -> Path | None:
    """Find the consolidated PNG emitted by the harness for this session."""
    cons_dir = _consolidated_dir(
        animal, bodypart, real_resolver,
        tone_pre_ms=pre_ms, tone_post_ms=post_ms,
        plot_family=family,
    )
    if not cons_dir.exists():
        return None
    date_str = date.strftime("%Y%m%d")
    win_tag = f"{pre_ms}pre-{post_ms}post"
    family_token = "_meanSEM_2x2_trials_" if family == "trial_overlays" else "_meanSEM_2x2_"
    pattern = (
        f"{animal}_{date_str}_{win_tag}_{cam}_{interp_version}"
        f"{family_token.rstrip('_')}*.png"
    )
    matches = sorted(cons_dir.glob(pattern))
    return matches[0] if matches else None


def _consolidated_cohort_path(
    animal: str, bodypart: str, family: str,
    pre_ms: int, post_ms: int, real_resolver: PathResolver,
    *, label: str = _COHORT_LABEL_DEFAULT,
) -> Path | None:
    """Find the consolidated cohort PNG. For session_overlays /
    binned_overlays, ``label`` picks the same (axis × side) variant
    used by the legacy resolver so panes stay aligned.
    """
    cons_dir = _consolidated_dir(
        animal, bodypart, real_resolver,
        tone_pre_ms=pre_ms, tone_post_ms=post_ms,
        plot_family=(
            "mean_xy_overlays" if family == "mean_trace" else family
        ),
    )
    if not cons_dir.exists():
        return None
    if family == "session_overlays":
        matches = sorted(cons_dir.glob(f"*overlay_{label}*.png"))
    elif family == "binned_overlays":
        matches = sorted(cons_dir.glob(f"*binnedOverlay_{label}*.png"))
    else:
        # mean_trace: single PNG per (animal, window).
        matches = sorted(cons_dir.glob("*.png"))
    return matches[0] if matches else None


def _render_comparison_grid(
    legacy_path: Path | None, consolidated_path: Path | None,
    out_path: Path, *, title: str,
) -> None:
    """2-col side-by-side comparison: legacy | consolidated.

    Aspect-aware figsize + LANCZOS resampling per kickoff Task 7 (mirrors
    7a.5 C6.2's fix for fine-line-detail preservation under heavy
    downsample).
    """
    panel_w_in = 10.0
    fig_h_min = 6.0
    fig_h_max = 60.0

    aspect = 1.0
    for p in (consolidated_path, legacy_path):
        if p is not None and p.exists():
            try:
                with Image.open(p) as _img:
                    iw, ih = _img.size
                if ih > 0:
                    aspect = float(iw) / float(ih)
                break
            except Exception:  # noqa: BLE001
                continue

    panel_h_natural = panel_w_in / max(aspect, 1e-3)
    fig_h = float(np.clip(panel_h_natural, fig_h_min, fig_h_max))
    fig_w = 2.0 * panel_w_in

    fig, axes = plt.subplots(1, 2, figsize=(fig_w, fig_h))
    panes = [(legacy_path, "legacy"), (consolidated_path, "consolidated")]
    for ax, (pane_path, label) in zip(axes, panes):
        if pane_path is not None and pane_path.exists():
            try:
                img = mpimg.imread(pane_path)
                ax.imshow(img, interpolation="lanczos")
                ax.set_title(f"{label}\n{pane_path.name}", fontsize=9)
            except Exception as exc:  # noqa: BLE001
                ax.text(
                    0.5, 0.5,
                    f"{label}: load error\n{type(exc).__name__}: {exc}",
                    ha="center", va="center", transform=ax.transAxes,
                )
        else:
            ax.text(
                0.5, 0.5,
                f"{label}: not found"
                + (f"\n{pane_path}" if pane_path else ""),
                ha="center", va="center", transform=ax.transAxes,
                fontsize=10, color="0.5",
            )
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(title, fontsize=11)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="parity_phase7a6_visual_gate",
        description="Phase 7a.6 visual gate (legacy vs consolidated PNG comparison grids).",
    )
    parser.add_argument(
        "--animals", default=None,
        help="Comma-separated animals. Default: PS46,PS55 (sample).",
    )
    parser.add_argument(
        "--sample-dates", default="auto",
        help=(
            "'auto' = default sample (PS46/2025-03-07, PS55/2025-05-02). "
            "'cohort' = every (animal, date) in PARITY_SESSIONS_14."
        ),
    )
    parser.add_argument(
        "--bodyparts", default=",".join(DEFAULT_BODYPARTS),
        help=f"Comma-separated. Default {','.join(DEFAULT_BODYPARTS)}",
    )
    parser.add_argument(
        "--windows",
        default=":".join(f"{p},{q}" for p, q in DEFAULT_WINDOWS),
        help="Colon-separated 'pre_ms,post_ms' pairs. Default 100,1000.",
    )
    parser.add_argument(
        "--families",
        default=",".join(PER_SESSION_FAMILIES + COHORT_FAMILIES),
        help=(
            "Comma-separated family names. Default: all 5 static-plot "
            "families (mean_video excluded — animation, see kickoff)."
        ),
    )
    parser.add_argument(
        "--emit-root", type=Path,
        default=(
            Path(__file__).resolve().parent.parent.parent
            / ".scratch_7a6" / "cohort_run" / "comparison_grids"
        ),
        help="Output root for the comparison grids.",
    )
    args = parser.parse_args(argv)

    bodyparts = [b.strip() for b in args.bodyparts.split(",") if b.strip()]
    families = [f.strip() for f in args.families.split(",") if f.strip()]
    windows: list[tuple[int, int]] = []
    for chunk in args.windows.split(":"):
        chunk = chunk.strip()
        if not chunk:
            continue
        a, b = chunk.split(",")
        windows.append((int(a), int(b)))

    if args.sample_dates == "auto":
        sample = list(DEFAULT_SAMPLE)
    elif args.sample_dates == "cohort":
        sample = list(h7a3.PARITY_SESSIONS_14)
    else:
        raise ValueError(
            f"--sample-dates must be 'auto' or 'cohort'; got "
            f"{args.sample_dates!r}",
        )
    if args.animals is not None:
        wanted = {a.strip() for a in args.animals.split(",") if a.strip()}
        sample = [(a, d) for a, d in sample if a in wanted]

    real_resolver = PathResolver()  # consolidated tree on MICROSCOPE
    args.emit_root.mkdir(parents=True, exist_ok=True)

    print("Phase 7a.6 visual gate runner")
    print(f"  bodyparts: {bodyparts}")
    print(f"  windows: {windows}")
    print(f"  families: {families}")
    print(f"  sample: {[(a, d.isoformat()) for a, d in sample]}")
    print(f"  emit_root: {args.emit_root}")
    print()

    n_emitted = 0
    n_legacy_missing = 0
    n_consolidated_missing = 0

    for animal, date in sample:
        for bodypart in bodyparts:
            for pre_ms, post_ms in windows:
                for family in families:
                    if family in PER_SESSION_FAMILIES:
                        legacy = _resolve_legacy_per_session_path(
                            animal, date, bodypart, family, pre_ms, post_ms,
                            real_resolver,
                        )
                        consolidated = _consolidated_per_session_path(
                            animal, date, bodypart, family, pre_ms, post_ms,
                            real_resolver,
                        )
                    elif family in COHORT_FAMILIES:
                        legacy = _resolve_legacy_cohort_path(
                            animal, bodypart, family, pre_ms, post_ms,
                            real_resolver,
                        )
                        consolidated = _consolidated_cohort_path(
                            animal, bodypart, family, pre_ms, post_ms,
                            real_resolver,
                        )
                    else:
                        print(f"  [skip] unknown family {family!r}")
                        continue

                    if legacy is None:
                        n_legacy_missing += 1
                    if consolidated is None:
                        n_consolidated_missing += 1

                    cmp_dir = (
                        args.emit_root / bodypart
                        / f"rewardAligned_{pre_ms}pre-{post_ms}post"
                        / family / animal
                    )
                    cmp_path = (
                        cmp_dir
                        / f"{animal}_{date.strftime('%Y%m%d')}_{family}_compare.png"
                    )
                    title = (
                        f"{animal} {date.isoformat()} | {bodypart} | "
                        f"{family} | win {pre_ms}-{post_ms}ms"
                    )
                    _render_comparison_grid(
                        legacy, consolidated, cmp_path, title=title,
                    )
                    n_emitted += 1
                    legacy_str = (
                        legacy.name if legacy and legacy.exists()
                        else "<missing>"
                    )
                    cons_str = (
                        consolidated.name if consolidated and consolidated.exists()
                        else "<missing>"
                    )
                    print(
                        f"  [{animal} {date.isoformat()} {bodypart} "
                        f"{family} {pre_ms}-{post_ms}ms]"
                    )
                    print(f"    legacy:       {legacy_str}")
                    print(f"    consolidated: {cons_str}")
                    print(f"    grid: {cmp_path}")

    print()
    print(f"Total grids emitted: {n_emitted}")
    print(f"Legacy missing: {n_legacy_missing}")
    print(f"Consolidated missing: {n_consolidated_missing}")
    print(f"Output root: {args.emit_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
