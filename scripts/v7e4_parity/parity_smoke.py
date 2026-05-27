"""Phase 7e.4 Stage 4 — parity smoke against F-P-1 R3 reference.

For each (animal, date, bodypart, scope) cell, computes H_counts two ways
and asserts allclose at 1e-12:

  (A) 7e.4 routing: build_tone_aligned_analysis(use_v7_cleaned=True)
      OR render_whole_session_heatmap(use_v7_cleaned=True)

  (B) F-P-1 audit equivalent: load cleaned_traces explicitly, AND
      `~is_baseline_fill` into the frame_mask, pass
      drop_likelihood_gate=True to build_histogram. This reproduces
      the F-P-1 R3 variant byte-identically.

If (A) ≡ (B), the 7e.4 routing reproduces F-P-1's R3 reference
exactly — the kickoff Stage 4 parity claim.

Run from the 7e.4 worktree:
    python scripts/v7e4_parity/parity_smoke.py
"""
from __future__ import annotations

import datetime as dt
import logging
import sys

import numpy as np
import pandas as pd

from stroke_orofacial.animals import get_animal
from stroke_orofacial.config_loader import load_defaults, lookup_tone_family
from stroke_orofacial.dlc_io.parquet import _param_sig, read_centered_parquet
from stroke_orofacial.dlc_kinematics.cleaned_traces_io import (
    load_baseline_fill_mask,
)
from stroke_orofacial.dlc_spatial.pixel_bins import build_histogram
from stroke_orofacial.dlc_spatial.render_on_demand import (
    compute_animal_aggregated_histogram,
)
from stroke_orofacial.dlc_spatial.tone_aligned import (
    build_tone_aligned_analysis,
    build_tone_aligned_window,
    load_tone_events,
)
from stroke_orofacial.manifest import build_manifest
from stroke_orofacial.paths import PathResolver

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("v7e4_parity")

# Same acute sessions as F-P-1 audit Addendum #1.
CELLS: list[tuple[str, dt.date, str, str]] = [
    # (animal, date, bodypart, center_mode)
    ("PS54", dt.date(2025, 5, 6),  "tongue", "spout_midpoint"),
    ("PS54", dt.date(2025, 5, 6),  "jaw",    "eye_midpoint"),
    ("PS51", dt.date(2025, 5, 6),  "tongue", "spout_midpoint"),
    ("PS47", dt.date(2025, 3, 19), "jaw",    "eye_midpoint"),
]
TONE_WINDOW_MS = (0.0, 8000.0)


def _explicit_R3_tone_aligned(animal: str, date: dt.date, bodypart: str,
                              center_mode: str, trial_group: str,
                              resolver: PathResolver, defaults: dict) -> np.ndarray | None:
    """F-P-1 R3 computation: load cleaned_traces + AND ~is_baseline_fill into
    frame_mask + drop lik gate. Returns H_counts."""
    spatial_config = defaults["dlc_spatial"]
    tone_config = defaults["dlc_spatial_tone_aligned"]
    animal_info = get_animal(animal)
    manifest = build_manifest(animal, date, resolver, animal_info,
                              analysis_context="dlc.spatial")
    # Centered parquet.
    sig = _param_sig(center_mode, 0.7)
    parquet_dir = resolver.dlc_centered_parquet_dir(center_mode, animal)
    parquet_path = parquet_dir / (
        f"{manifest.dlc_h5_files[0].name}.intermediate.{sig}.parquet"
    )
    df = read_centered_parquet(parquet_path)
    n_frames = len(df)

    # Cleaned-traces baseline-fill mask.
    baseline_fill_mask = load_baseline_fill_mask(
        bodypart, animal, date, resolver, expected_n_frames=n_frames,
    )

    # Tone window.
    licks = resolver.spout_licks_and_rewards_npz(animal, date)
    tone_ws = load_tone_events(
        licks, trial_group,
        wavesurfer_sides_match_mouse_sides=animal_info.wavesurfer_sides_match_mouse_sides,
    )
    if len(tone_ws) == 0:
        return None
    align_path = manifest.alignment_template
    if align_path is None or not align_path.exists():
        align_path = resolver.alignment_template_for_reading(animal, date, cam="cam2")
    aln = np.load(str(align_path), allow_pickle=True)
    sig_camIdx = aln["sig_camIdx__idx_ws"]
    fps = float(tone_config.get("fps", 250.0))
    window = build_tone_aligned_window(tone_ws, sig_camIdx, TONE_WINDOW_MS, fps, n_frames)

    # Tone-family config.
    family = lookup_tone_family(tone_config, bodypart, center_mode)
    bp_x_range = (tuple(family["x_range"]) if family.get("x_range") is not None else None)
    lik_thresholds = family.get("likelihood_thresholds", [0.8])
    lik_thr = lik_thresholds[0] if lik_thresholds else 0.8
    nbins_list = tone_config.get("default_nbins", [80, 80])
    nbins = nbins_list[0] if isinstance(nbins_list[0], int) else int(nbins_list[0])

    cfg = dict(spatial_config)
    cfg["bodyparts"] = dict(cfg.get("bodyparts", {}))
    bp = dict(cfg["bodyparts"].get(bodypart, {}))
    bp["likelihood_threshold"] = lik_thr
    cfg["bodyparts"][bodypart] = bp

    hist = build_histogram(
        df, bodypart, cfg,
        center_mode=center_mode,
        x_range=bp_x_range,
        nbins=nbins,
        window=window,
        n_total_frames=int(window.n_selected),
        baseline_fill_mask=baseline_fill_mask,
        drop_likelihood_gate=True,
    )
    return hist["H_counts"] if hist is not None else None


def main() -> int:
    resolver = PathResolver()
    defaults = load_defaults()
    n_pass = n_fail = 0
    for animal, date, bodypart, center_mode in CELLS:
        for trial_group in ("all", "L", "R"):
            label = f"{animal}/{date}/{bodypart}/{center_mode}/{trial_group}"
            # (A) 7e.4 routing via build_tone_aligned_analysis(use_v7_cleaned=True)
            animal_info = get_animal(animal)
            manifest = build_manifest(animal, date, resolver, animal_info,
                                       analysis_context="dlc.spatial")
            result_v74 = build_tone_aligned_analysis(
                manifest, bodypart, center_mode, trial_group, TONE_WINDOW_MS,
                resolver, defaults["dlc_spatial"], defaults["dlc_spatial_tone_aligned"],
                wavesurfer_sides_match_mouse_sides=animal_info.wavesurfer_sides_match_mouse_sides,
                use_v7_cleaned=True,
            )
            H_v74 = result_v74["histogram"]["H_counts"] if (
                result_v74 is not None and result_v74["histogram"] is not None
            ) else None
            # (B) F-P-1 R3 explicit
            H_ref = _explicit_R3_tone_aligned(
                animal, date, bodypart, center_mode, trial_group,
                resolver, defaults,
            )
            if H_v74 is None and H_ref is None:
                logger.info("PASS (both None — no tones for tg=%s) %s", trial_group, label)
                n_pass += 1
                continue
            if H_v74 is None or H_ref is None:
                logger.error("FAIL (one-side None) %s  v74=%s  ref=%s",
                             label, H_v74 is not None, H_ref is not None)
                n_fail += 1
                continue
            if H_v74.shape != H_ref.shape:
                logger.error("FAIL (shape) %s  v74=%s  ref=%s",
                             label, H_v74.shape, H_ref.shape)
                n_fail += 1
                continue
            if not np.allclose(H_v74, H_ref, atol=1e-12, rtol=0):
                max_abs = float(np.max(np.abs(H_v74 - H_ref)))
                logger.error("FAIL (allclose) %s  max|diff|=%.3e", label, max_abs)
                n_fail += 1
                continue
            logger.info("PASS %s  sum=%.0f", label, float(H_v74.sum()))
            n_pass += 1
    logger.info("PARITY VERDICT: %d pass, %d fail", n_pass, n_fail)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
