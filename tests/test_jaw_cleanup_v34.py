"""Tests for the reconstructed jaw v3.4 cleanup producer.

Chore ``substrate-routing-and-secondary-spout-per-half-fix`` Stage 0b. The
production Step-1 producer was lost (gitignored scratch); the algorithm was
lifted from ``audit_jaw_cleanup_sim_v3p4.py`` and validated to reproduce the
scratch ``compute_v3_clean_trace`` exactly (0-diff on a full session, live).

These tests pin the per-rule behavior on synthetic inputs, the writer schema +
metadata, and — most importantly — the **real-lick-preservation** property that
distinguishes v3.4 from the over-aggressive on-disk version: a sustained jaw
plateau must NOT be wiped to baseline.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from stroke_orofacial.dlc_kinematics import jaw_cleanup_v34 as J

_FPS = 250.0
_RAW, _INTERP, _BASELINE = 0, 1, 3


def _all_raw(n: int) -> np.ndarray:
    return np.full(n, _RAW, dtype=np.int8)


class TestRuleR1:
    def test_r1y_wipes_positive_ceiling_raw_frame(self):
        """A raw frame above bmean + Y_CEILING is wiped (positive side only)."""
        n = 60
        y = np.zeros(n)
        y[30] = J.Y_CEILING_PX + 50.0  # well above ceiling
        _, wy, wx, wiso, wfo = J.compute_v3_clean_trace(
            y, _all_raw(n), baseline_mean=0.0, fps=_FPS,
        )
        assert wy[30] and not wy[29]

    def test_r1y_does_not_wipe_negative_excursion(self):
        """Negative deflections are NOT ceiling-wiped (positive-side only)."""
        n = 60
        y = np.zeros(n)
        y[30] = -(J.Y_CEILING_PX + 50.0)
        _, wy, _, _, _ = J.compute_v3_clean_trace(
            y, _all_raw(n), baseline_mean=0.0, fps=_FPS,
        )
        assert not wy[30]

    def test_r1x_bidirectional_ceiling(self):
        """R1-x wipes raw frames with |x - bmean_x| > X_CEILING, both signs."""
        n = 60
        y = np.zeros(n)
        x = np.zeros(n)
        x[20] = J.X_CEILING_PX + 10.0   # +x over ceiling
        x[40] = -(J.X_CEILING_PX + 10.0)  # -x over ceiling (bidirectional)
        _, _, wx, _, _ = J.compute_v3_clean_trace(
            y, _all_raw(n), baseline_mean=0.0, fps=_FPS,
            x_final=x, baseline_mean_x=0.0,
        )
        assert wx[20] and wx[40]


class TestRuleR2Isolated:
    def test_isolated_short_cluster_wiped(self):
        """A lone short raw cluster (<= ISOLATED_MAX_N) with no neighbor is
        wiped."""
        n = 400
        y = np.zeros(n)
        fm = np.full(n, _BASELINE, dtype=np.int8)
        # one isolated 3-frame raw cluster, far from any other raw frame
        fm[200:203] = _RAW
        y[200:203] = 20.0
        out = J.clean_jaw_session_arrays(y * 0 + 1.0, y, fm, 0.0, 0.0, _FPS)
        assert np.all(out["fill_method"][200:203] == _BASELINE)

    def test_short_cluster_with_nearby_neighbor_kept(self):
        """A short cluster with another raw cluster within the radius is
        kept (not isolated)."""
        n = 400
        y = np.zeros(n)
        fm = np.full(n, _BASELINE, dtype=np.int8)
        # two 3-frame raw clusters 4 frames apart (< ISOLATED_RADIUS 30ms)
        fm[200:203] = _RAW
        fm[206:209] = _RAW
        y[200:203] = 20.0
        y[206:209] = 22.0
        _, _, _, wiso, _ = J.compute_v3_clean_trace(
            y, fm, baseline_mean=0.0, fps=_FPS,
        )
        assert not wiso[200:203].any() and not wiso[206:209].any()


class TestRealLickPreservation:
    """THE key property: a sustained jaw plateau is NOT wiped to baseline.
    This is what distinguishes v3.4 from the over-aggressive on-disk version
    (which dropped real ~100px licks to y=0)."""

    def test_sustained_plateau_kept_not_baselined(self):
        n = 400
        y = np.zeros(n)
        x = np.zeros(n)
        fm = np.full(n, _BASELINE, dtype=np.int8)
        # a sustained 60-frame (240ms) raw plateau at y=50 (< ceiling 125)
        fm[150:210] = _RAW
        y[150:210] = 50.0
        out = J.clean_jaw_session_arrays(x, y, fm, 0.0, 0.0, _FPS)
        # The plateau survives as anchors and keeps its value — NOT baseline 0.
        assert np.allclose(out["y_final"][150:210], 50.0)
        assert np.all(out["fill_method"][150:210] == _RAW)

    def test_small_gap_inside_lick_pchip_filled_not_baselined(self):
        """A short non-raw gap inside a sustained lick is PCHIP-filled (interp),
        not dropped to baseline."""
        n = 400
        y = np.zeros(n)
        x = np.zeros(n)
        fm = np.full(n, _BASELINE, dtype=np.int8)
        fm[150:210] = _RAW
        y[150:210] = 50.0
        # punch a 5-frame interp gap mid-plateau (< MAX_GAP_MS_PCHIP=120ms)
        fm[178:183] = _INTERP
        out = J.clean_jaw_session_arrays(x, y, fm, 0.0, 0.0, _FPS)
        assert np.all(out["fill_method"][178:183] == _INTERP)
        assert np.allclose(out["y_final"][178:183], 50.0, atol=1e-6)
        assert not out["is_baseline_fill"][178:183].any()


class TestFillEncoding:
    def test_fill_method_and_flags_consistent(self):
        n = 400
        y = np.zeros(n)
        x = np.zeros(n)
        fm = np.full(n, _BASELINE, dtype=np.int8)
        fm[150:210] = _RAW
        y[150:210] = 50.0
        fm[178:183] = _INTERP
        out = J.clean_jaw_session_arrays(x, y, fm, 0.0, 0.0, _FPS)
        assert out["fill_method"].dtype == np.int8
        assert np.array_equal(out["is_interp_fill"], out["fill_method"] == _INTERP)
        assert np.array_equal(out["is_baseline_fill"], out["fill_method"] == _BASELINE)
        # baseline frames are zeroed in BOTH x and y
        base = out["fill_method"] == _BASELINE
        assert np.allclose(out["x_final"][base], 0.0)
        assert np.allclose(out["y_final"][base], 0.0)

    def test_x_and_y_repchip_from_same_anchors(self):
        """x and y share the surviving-anchor set: anchor frames keep raw
        x and y; baseline frames zero both."""
        n = 400
        y = np.zeros(n)
        x = np.zeros(n)
        fm = np.full(n, _BASELINE, dtype=np.int8)
        fm[150:210] = _RAW
        y[150:210] = 50.0
        x[150:210] = 10.0
        out = J.clean_jaw_session_arrays(x, y, fm, 0.0, 0.0, _FPS)
        assert np.allclose(out["x_final"][150:210], 10.0)
        assert np.allclose(out["y_final"][150:210], 50.0)


class TestSessionBaselines:
    def test_session_baseline_median_of_trial_means(self):
        n = 2000
        fps = _FPS
        y = np.full(n, np.nan)
        x = np.full(n, np.nan)
        # two trials; baseline window is [-500, 0] ms = [-125, 0] frames
        events = [SimpleNamespace(tone_frame_idx=500),
                  SimpleNamespace(tone_frame_idx=1500)]
        y[375:501] = 4.0    # trial 1 baseline mean = 4
        y[1375:1501] = 8.0  # trial 2 baseline mean = 8
        x[375:501] = 1.0
        x[1375:1501] = 3.0
        bm = J.compute_session_baselines(x, y, events, fps, n)
        assert bm is not None
        assert bm[0] == pytest.approx(6.0)  # median(4, 8)
        assert bm[1] == pytest.approx(2.0)  # median(1, 3)

    def test_no_finite_baseline_returns_none(self):
        n = 1000
        y = np.full(n, np.nan)
        x = np.full(n, np.nan)
        events = [SimpleNamespace(tone_frame_idx=500)]
        assert J.compute_session_baselines(x, y, events, _FPS, n) is None


class TestWriterSchemaAndMetadata:
    @staticmethod
    def _make_v5p3_input(path, n=300):
        """Write a minimal v5p3-shaped interpolated_traces/jaw parquet."""
        fm = np.full(n, _BASELINE, dtype=np.int8)
        fm[100:160] = _RAW
        y = np.zeros(n, dtype=np.float64)
        y[100:160] = 30.0
        df = pd.DataFrame({
            "frame_idx": np.arange(n, dtype=np.int64),
            "x_final": np.zeros(n, dtype=np.float64),
            "y_final": y,
            "likelihood_raw": np.full(n, 0.9, dtype=np.float64),
            "is_interp_fill": fm == _INTERP,
            "is_baseline_fill": fm == _BASELINE,
            "fill_method": fm,
        })
        table = pa.Table.from_pandas(df, preserve_index=False)
        md = dict(table.schema.metadata or {})
        md[b"fps"] = b"250.0"
        md[b"n_frames"] = str(n).encode()
        md[b"interpolation_version"] = b"v5p3"
        table = table.replace_schema_metadata(md)
        pq.write_table(table, str(path))

    def test_writer_preserves_schema_adds_cleanup_metadata(self, tmp_path):
        in_path = tmp_path / "in.parquet"
        out_path = tmp_path / "out.parquet"
        self._make_v5p3_input(in_path)
        di = pd.read_parquet(in_path)
        cleaned = J.clean_jaw_session_arrays(
            di.x_final.to_numpy(), di.y_final.to_numpy(),
            di.fill_method.to_numpy(), 0.0, 0.0, _FPS,
        )
        J._write_cleaned_jaw_parquet(in_path, out_path, cleaned)

        do = pd.read_parquet(out_path)
        assert list(do.columns) == list(di.columns)
        assert do.fill_method.dtype == di.fill_method.dtype  # int8 preserved
        meta = pq.read_schema(str(out_path)).metadata
        assert meta[b"cleanup_version"] == b"v3.4"
        assert meta[b"interpolation_version"] == b"v5p3"  # v5p3 keys preserved
        # cleanup_constants_json round-trips + carries the locked constants
        cc = json.loads(meta[b"cleanup_constants_json"].decode())
        assert cc["cleanup_version"] == "v3.4"
        assert cc["Y_CEILING_PX"] == 125.0 and cc["X_CEILING_PX"] == 40.0
        assert "BOTH x and y" in cc["rules_applied"][4]

    def test_cleanup_constants_json_is_stable(self):
        """The metadata string is deterministic (json.dumps default order)."""
        assert J.cleanup_constants_json() == json.dumps(J._CLEANUP_CONSTANTS)
