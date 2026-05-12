"""Phase 7-pre-multi-half synthetic 2-half integration test.

Builds two synthetic per-half NPZs / templates / parquets, runs all
three Architecture X merge functions
(``merge_licks_and_rewards``, ``merge_alignment_templates``,
``merge_centered_parquet``), and verifies output shape + provenance +
offset semantics in a single end-to-end pass. No MICROSCOPE dependency.

The unit tests in ``test_multi_half_merge.py`` cover each merge
function in isolation; this integration test covers the **composition**
of all three under the same per-(animal, date) per-half subdir layout
that the production pipeline writes — a regression guard for any
future schema drift across the three layers.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from stroke_orofacial.spout_behavior.multi_half_merge import (
    merge_alignment_templates,
    merge_centered_parquet,
    merge_licks_and_rewards,
)


# ---------- synthetic per-half builders ----------


def _build_per_half_licks_npz(
    out_path: Path,
    *,
    n_cam: int,
    n_licks: int,
    seed: int,
) -> Path:
    """Synthetic per-half licks_and_rewards NPZ with the typical schema:

      - ``cam_times`` (n_cam timeseries)
      - ``Lick_L`` / ``Lick_R`` (frame-index arrays of length n_licks)
      - ``Reward_L`` / ``Reward_R`` (frame-index arrays)
      - ``Tone_L`` / ``Tone_R`` (frame-index arrays)
      - ``treadmill_voltage`` (1D timeseries)
    """
    rng = np.random.default_rng(seed)
    payload: dict = {
        "cam_times": np.linspace(0.0, n_cam * 4e-3, n_cam),
        "Lick_L": np.sort(rng.integers(0, n_cam, size=n_licks).astype(float)),
        "Lick_R": np.sort(rng.integers(0, n_cam, size=n_licks).astype(float)),
        "Reward_L": np.sort(rng.integers(0, n_cam, size=10).astype(float)),
        "Reward_R": np.sort(rng.integers(0, n_cam, size=10).astype(float)),
        "Tone_L": np.sort(rng.integers(0, n_cam, size=10).astype(float)),
        "Tone_R": np.sort(rng.integers(0, n_cam, size=10).astype(float)),
        "treadmill_voltage": rng.standard_normal(n_cam),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(str(out_path), **payload, allow_pickle=False)
    return out_path


def _build_per_half_alignment_template(
    out_path: Path,
    *,
    Fs_ws: float,
    n_cam: int,
    n_ws: int,
    cam_t0: float = 0.0,
    ws_t0: float = 0.0,
) -> Path:
    """Synthetic per-half alignment template NPZ matching cell-16 REQ_KEYS."""
    dt_ws = 1.0 / Fs_ws
    dt_cam = (n_ws / Fs_ws) / n_cam
    payload = {
        "Fs_ws_input": np.float64(Fs_ws),
        "sig_wsIdx__idx_cam": np.linspace(0.0, n_ws - 1, n_cam),
        "sig_camIdx__idx_ws": np.linspace(0.0, n_cam - 1, n_ws),
        "sig_camTimes__idx_cam": cam_t0 + np.arange(n_cam) * dt_cam,
        "sig_wsTimes__idx_ws": ws_t0 + np.arange(n_ws) * dt_ws,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(str(out_path), **payload, allow_pickle=False)
    return out_path


def _build_per_half_centered_parquet(
    out_path: Path, *, n_rows: int, seed: int,
) -> Path:
    """Synthetic per-half centered DLC parquet (39 float32 columns)."""
    rng = np.random.default_rng(seed)
    bodyparts = [
        "tongue", "L_eye", "R_eye", "nose", "L_paw", "R_paw",
        "L_ear", "R_ear", "L_spout", "R_spout", "jaw", "tail", "whisker_pad",
    ]
    cols: dict[str, np.ndarray] = {}
    for bp in bodyparts:
        cols[f"{bp}_x"] = rng.standard_normal(n_rows).astype("float32")
        cols[f"{bp}_y"] = rng.standard_normal(n_rows).astype("float32")
        cols[f"{bp}_likelihood"] = rng.uniform(0.5, 1.0, n_rows).astype("float32")
    df = pd.DataFrame(cols)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    return out_path


# ---------- end-to-end test ----------


class TestMultiHalfIntegration:
    """Builds an in-tmp_path per-(animal, date) layout matching the
    production output schema (Decision 3: per-half subdirs +
    parent-level merged), runs all three merge functions, asserts
    the merged outputs are mutually consistent."""

    def test_synthetic_two_half_end_to_end(self, tmp_path: Path):
        # Per-half lengths chosen so each layer's merge produces
        # readable totals and the licks frame-index merging exercises
        # the offset path.
        Fs_ws = 1000.0
        n_cam_a, n_cam_b = 1000, 2000
        n_ws_a, n_ws_b = 4000, 8000
        n_rows_a, n_rows_b = n_cam_a, n_cam_b  # parquet row count == n_cam

        # Production-style per-(animal, date) per-half subdir layout
        animal = "PS48"
        date_str = "20250314"
        halves_label = "ab"
        per_half_subdir = (
            tmp_path / "outputs" / animal / f"{date_str}{halves_label}"
        )
        per_half_subdir.mkdir(parents=True, exist_ok=True)
        parent_dir = per_half_subdir.parent

        # ----- LICKS NPZ -----
        licks_a = _build_per_half_licks_npz(
            per_half_subdir / f"{date_str}a.npz",
            n_cam=n_cam_a, n_licks=50, seed=1,
        )
        licks_b = _build_per_half_licks_npz(
            per_half_subdir / f"{date_str}b.npz",
            n_cam=n_cam_b, n_licks=80, seed=2,
        )
        merged_licks = parent_dir / f"{date_str}.npz"
        merge_licks_and_rewards([licks_a, licks_b], merged_licks)
        with np.load(merged_licks, allow_pickle=True) as merged:
            # 1D timeseries concat — n_cam total
            assert merged["cam_times"].shape == (n_cam_a + n_cam_b,)
            assert merged["treadmill_voltage"].shape == (n_cam_a + n_cam_b,)
            # Frame-index arrays: half-A has 50 licks; half-B has 80;
            # half-B values are offset by n_cam_a.
            n_licks_a, n_licks_b = 50, 80
            assert merged["Lick_L"].shape == (n_licks_a + n_licks_b,)
            # Half-A values stay in [0, n_cam_a); half-B values land in
            # [n_cam_a, n_cam_a + n_cam_b) after offset.
            assert merged["Lick_L"][:n_licks_a].max() < n_cam_a
            assert merged["Lick_L"][n_licks_a:].min() >= n_cam_a
            assert merged["Lick_L"][n_licks_a:].max() < (n_cam_a + n_cam_b)
            # Provenance — legacy + list-style schema
            assert int(merged["merged_n_cam_A"]) == n_cam_a
            assert int(merged["merged_n_cam_B"]) == n_cam_b
            assert int(merged["cam_frame_offset_for_B"]) == n_cam_a
            assert list(merged["merged_n_cam_per_half"]) == [n_cam_a, n_cam_b]

        # ----- ALIGNMENT TEMPLATE -----
        # Per-half templates for the alignment layer match the Decision 3
        # subdir convention but live under a separate cam2/{ANIMAL}/
        # tree in production (resolver.alignment_template_per_half). For
        # the integration test we just put them in the same per-half
        # subdir as licks since the merge function only cares about
        # input paths.
        align_a = _build_per_half_alignment_template(
            per_half_subdir / f"{date_str}a.alignment.npz",
            Fs_ws=Fs_ws, n_cam=n_cam_a, n_ws=n_ws_a,
        )
        align_b = _build_per_half_alignment_template(
            per_half_subdir / f"{date_str}b.alignment.npz",
            Fs_ws=Fs_ws, n_cam=n_cam_b, n_ws=n_ws_b,
            cam_t0=999.0, ws_t0=999.0,  # native times will be shifted to A's end
        )
        merged_align = parent_dir / f"{date_str}.alignment.npz"
        merge_alignment_templates([align_a, align_b], merged_align)
        with np.load(merged_align, allow_pickle=True) as merged:
            # Index-array offsets: half-B's wsIdx_cam shifted by n_ws_a;
            # camIdx_ws shifted by n_cam_a.
            assert merged["sig_wsIdx__idx_cam"].shape == (n_cam_a + n_cam_b,)
            assert merged["sig_camIdx__idx_ws"].shape == (n_ws_a + n_ws_b,)
            # Half-A's first wsIdx is 0; half-B's first wsIdx is offset
            # by n_ws_a (40_000) from its original 0.
            assert merged["sig_wsIdx__idx_cam"][n_cam_a] == n_ws_a
            # Time-axis continuity: half-B's first cam time lands at
            # last_finite(A) + dt_cam (NOT 999.0).
            cam_times = merged["sig_camTimes__idx_cam"]
            assert cam_times[n_cam_a] < 5.0  # close to A's end ~4s, not 999s
            # Monotonic non-decreasing (verifies merge succeeded with
            # no monotonicity-fail-loud RuntimeError).
            diffs = np.diff(cam_times)
            assert (diffs >= -1e-9).all()
            # Provenance — legacy + list-style
            assert int(merged["ws_offset_samples"]) == n_ws_a
            assert int(merged["cam_offset_frames"]) == n_cam_a

        # ----- CENTERED PARQUET -----
        parquet_a = _build_per_half_centered_parquet(
            per_half_subdir / f"{date_str}a.parquet",
            n_rows=n_rows_a, seed=10,
        )
        parquet_b = _build_per_half_centered_parquet(
            per_half_subdir / f"{date_str}b.parquet",
            n_rows=n_rows_b, seed=20,
        )
        merged_parquet = parent_dir / f"{date_str}.parquet"
        merge_centered_parquet([parquet_a, parquet_b], merged_parquet)
        merged_df = pd.read_parquet(merged_parquet)
        # Row count == sum of per-half row counts
        assert len(merged_df) == n_rows_a + n_rows_b
        # 39-col schema preserved (13 bodyparts × 3 coords)
        assert len(merged_df.columns) == 39
        # RangeIndex 0..n_total-1 (frame-index continuity)
        assert list(merged_df.index) == list(range(n_rows_a + n_rows_b))

        # ----- CROSS-LAYER CONSISTENCY -----
        # Licks merged n_cam == alignment merged n_cam (number of
        # cam-frames in the merged session) == parquet row count.
        # Verifies all three merges agree on the total cam-frame count
        # — the load-bearing invariant for downstream Phase 5+ readers.
        with np.load(merged_licks) as merged:
            licks_n_cam = merged["cam_times"].shape[0]
        with np.load(merged_align) as merged:
            align_n_cam = merged["sig_wsIdx__idx_cam"].shape[0]
        parquet_n_cam = len(merged_df)
        assert licks_n_cam == align_n_cam == parquet_n_cam == (n_cam_a + n_cam_b)

    def test_synthetic_three_half_end_to_end(self, tmp_path: Path):
        """N=3 generalization: same layout, three per-half files per
        layer → cumulative offsets / row totals at the merged level."""
        Fs_ws = 1000.0
        n_cam_per = [500, 700, 600]
        n_ws_per = [n * 4 for n in n_cam_per]

        animal = "PS48"
        date_str = "20250314"
        halves_label = "abc"  # 3 halves
        per_half_subdir = (
            tmp_path / "outputs" / animal / f"{date_str}{halves_label}"
        )
        per_half_subdir.mkdir(parents=True, exist_ok=True)
        parent_dir = per_half_subdir.parent

        # Licks
        licks_paths = []
        for letter, n_cam in zip(("a", "b", "c"), n_cam_per):
            licks_paths.append(_build_per_half_licks_npz(
                per_half_subdir / f"{date_str}{letter}.npz",
                n_cam=n_cam, n_licks=20, seed=ord(letter),
            ))
        merge_licks_and_rewards(licks_paths, parent_dir / f"{date_str}.npz")
        with np.load(parent_dir / f"{date_str}.npz", allow_pickle=True) as m:
            assert m["cam_times"].shape == (sum(n_cam_per),)
            np.testing.assert_array_equal(
                m["merged_n_cam_per_half"],
                np.array(n_cam_per, dtype=np.int64),
            )

        # Alignment templates
        align_paths = []
        for letter, n_cam, n_ws in zip(("a", "b", "c"), n_cam_per, n_ws_per):
            align_paths.append(_build_per_half_alignment_template(
                per_half_subdir / f"{date_str}{letter}.alignment.npz",
                Fs_ws=Fs_ws, n_cam=n_cam, n_ws=n_ws,
            ))
        merge_alignment_templates(
            align_paths, parent_dir / f"{date_str}.alignment.npz",
        )
        with np.load(parent_dir / f"{date_str}.alignment.npz", allow_pickle=True) as m:
            assert m["sig_wsIdx__idx_cam"].shape == (sum(n_cam_per),)
            assert m["sig_camIdx__idx_ws"].shape == (sum(n_ws_per),)
            # Cumulative ws offsets
            np.testing.assert_array_equal(
                m["ws_offsets_per_half"],
                np.array([0, n_ws_per[0], n_ws_per[0] + n_ws_per[1]], dtype=np.int64),
            )
            np.testing.assert_array_equal(
                m["cam_offsets_per_half"],
                np.array([0, n_cam_per[0], n_cam_per[0] + n_cam_per[1]], dtype=np.int64),
            )

        # Centered parquet
        parquet_paths = []
        for letter, n_rows in zip(("a", "b", "c"), n_cam_per):
            parquet_paths.append(_build_per_half_centered_parquet(
                per_half_subdir / f"{date_str}{letter}.parquet",
                n_rows=n_rows, seed=ord(letter) * 10,
            ))
        merge_centered_parquet(
            parquet_paths, parent_dir / f"{date_str}.parquet",
        )
        merged_df = pd.read_parquet(parent_dir / f"{date_str}.parquet")
        assert len(merged_df) == sum(n_cam_per)
