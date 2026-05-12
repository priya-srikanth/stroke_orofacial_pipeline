"""Synthetic-fixture unit tests for the Phase 7-pre-secondary-spout
parity harness's Layer 1 byte-identity comparator.

The full harness at ``tests/scripts/parity_phase7_pre_secondary_spout.py``
runs against MICROSCOPE for Layers 1-2. These tests exercise the
comparator's helper functions with fabricated baselines + tmp_paths so
comparator bugs are caught without needing the mount. Mirrors the
multi-half harness's analogous synthetic test pattern.

Covers:
  - ``_is_params_json`` (excludes ``params/*.json`` from byte-identity).
  - ``_is_bare_half_path`` (distinguishes bare from b half + Pattern A
    subdirs).
  - ``_compare_bare_half_byte_identity`` (full comparator: PASS, byte
    mismatch, missing-in-baseline, missing-post-PR).
"""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

import pytest


# Import the harness as a module. It lives outside the package tree
# so we add its parent dir to sys.path explicitly.
def _import_harness():
    import importlib.util
    import sys

    harness_path = (
        Path(__file__).resolve().parent
        / "scripts" / "parity_phase7_pre_secondary_spout.py"
    )
    spec = importlib.util.spec_from_file_location(
        "parity_harness_secondary_spout", harness_path,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def harness():
    return _import_harness()


# ---- _is_params_json ----


class TestIsParamsJson:
    def test_top_level_params_json(self, harness):
        assert harness._is_params_json("params/PS51/20250430.json")

    def test_nested_params_json(self, harness):
        assert harness._is_params_json(
            "spout_behavior/params/PS51/20250430.json"
        )

    def test_non_params_npz(self, harness):
        assert not harness._is_params_json(
            "licks_and_rewards/PS51/20250430.npz"
        )

    def test_params_only_matches_slash_boundary(self, harness):
        """The heuristic is "params/" at start OR "/params/" anywhere —
        not just substring containing "params". A subdir named
        "output_params" (no slash boundary at "params") does NOT match.
        """
        assert not harness._is_params_json(
            "output_params/PS51/foo.json"
        )
        assert not harness._is_params_json("paramsy/PS51/foo.json")


# ---- _is_bare_half_path ----


class TestIsBareHalfPath:
    def test_bare_half_npz(self, harness):
        assert harness._is_bare_half_path(
            "licks_and_rewards/PS51/20250430.npz", "PS51", "20250430",
        )

    def test_b_half_npz(self, harness):
        assert not harness._is_bare_half_path(
            "licks_and_rewards/PS51/20250430b.npz", "PS51", "20250430",
        )

    def test_pattern_a_subdir(self, harness):
        """Pattern A per-half subdir paths (``{date_str}ab/{date_str}a.npz``)
        contain a {date_str}a or {date_str}b filename — those are NOT
        bare-half files."""
        assert not harness._is_bare_half_path(
            "licks_and_rewards/PS48/20250314ab/20250314a.npz",
            "PS48", "20250314",
        )

    def test_params_json_bare(self, harness):
        """params/{animal}/{date_str}.json IS a bare-half path
        (excluded from byte-identity by _is_params_json, but
        structurally it's bare-half-scoped)."""
        assert harness._is_bare_half_path(
            "params/PS51/20250430.json", "PS51", "20250430",
        )

    def test_filename_doesnt_start_with_date_str(self, harness):
        """A filename not starting with date_str isn't a bare-half
        per-session output (e.g., subdir-only paths)."""
        assert not harness._is_bare_half_path(
            "running_bouts/PS51/something_else.npz", "PS51", "20250430",
        )


# ---- _compare_bare_half_byte_identity ----


def _write_npz(path: Path, content: bytes = b"\x00\x00\x00") -> str:
    """Touch ``path`` with ``content`` and return its SHA256 hex."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


class TestCompareBareHalfByteIdentity:
    def test_all_match_returns_empty_failures(self, harness, tmp_path):
        """Baseline + post-PR have identical bare-half output hashes →
        no failures."""
        animal = "PS51"
        date = datetime.date(2025, 4, 30)
        date_str = "20250430"
        # Touch synthetic bare-half files
        h1 = _write_npz(
            tmp_path / "licks_and_rewards" / animal / f"{date_str}.npz",
            b"licks-bytes",
        )
        h2 = _write_npz(
            tmp_path / "running_bouts" / animal / f"{date_str}.npz",
            b"running-bytes",
        )
        baseline = {
            f"{animal}/{date_str}/licks_and_rewards/{animal}/{date_str}.npz": h1,
            f"{animal}/{date_str}/running_bouts/{animal}/{date_str}.npz": h2,
        }

        failures, info = harness._compare_bare_half_byte_identity(
            animal, date, tmp_path, baseline, {},
        )
        assert failures == []
        assert info["n_files_checked"] == 2
        assert info["n_files_excluded_params"] == 0

    def test_byte_mismatch_returns_failure(self, harness, tmp_path):
        animal = "PS51"
        date = datetime.date(2025, 4, 30)
        date_str = "20250430"
        # Post-PR writes different bytes than baseline expected
        _write_npz(
            tmp_path / "licks_and_rewards" / animal / f"{date_str}.npz",
            b"new-bytes",
        )
        baseline = {
            f"{animal}/{date_str}/licks_and_rewards/{animal}/{date_str}.npz":
                hashlib.sha256(b"old-bytes").hexdigest(),
        }

        failures, info = harness._compare_bare_half_byte_identity(
            animal, date, tmp_path, baseline, {},
        )
        assert len(failures) == 1
        assert "BYTE MISMATCH" in failures[0]
        assert "licks_and_rewards" in failures[0]

    def test_excludes_params_json(self, harness, tmp_path):
        """params/*.json files are NOT byte-compared (run_timestamp
        non-determinism). Both halves of the comparison ignore them."""
        animal = "PS51"
        date = datetime.date(2025, 4, 30)
        date_str = "20250430"
        # Touch a params file; baseline has a DIFFERENT hash for it
        # — but the comparator should ignore it entirely.
        _write_npz(
            tmp_path / "params" / animal / f"{date_str}.json",
            b'{"run_timestamp": "2026-05-12T16:00:00"}',
        )
        baseline = {
            f"{animal}/{date_str}/params/{animal}/{date_str}.json":
                "some-old-hash-that-does-not-match",
        }

        failures, info = harness._compare_bare_half_byte_identity(
            animal, date, tmp_path, baseline, {},
        )
        assert failures == [], (
            f"params/*.json byte-mismatch was NOT excluded: {failures}"
        )
        assert info["n_files_excluded_params"] == 1
        assert info["n_files_checked"] == 0

    def test_missing_in_baseline_returns_failure(self, harness, tmp_path):
        """A new file emitted post-PR that's NOT in the baseline →
        FAIL (signals an inadvertent new emit)."""
        animal = "PS51"
        date = datetime.date(2025, 4, 30)
        date_str = "20250430"
        _write_npz(
            tmp_path / "new_output_type" / animal / f"{date_str}.npz",
            b"surprise-bytes",
        )

        failures, info = harness._compare_bare_half_byte_identity(
            animal, date, tmp_path, {}, {},
        )
        assert len(failures) == 1
        assert "NEW file emitted post-PR" in failures[0]
        assert info["n_files_missing_in_baseline"] == 1

    def test_missing_post_pr_returns_failure(self, harness, tmp_path):
        """A file that WAS in the baseline but DIDN'T emit post-PR →
        FAIL (signals a regression in output emission)."""
        animal = "PS51"
        date = datetime.date(2025, 4, 30)
        date_str = "20250430"
        baseline = {
            f"{animal}/{date_str}/licks_and_rewards/{animal}/{date_str}.npz":
                hashlib.sha256(b"expected").hexdigest(),
        }
        # NO files touched on tmp_path

        failures, info = harness._compare_bare_half_byte_identity(
            animal, date, tmp_path, baseline, {},
        )
        assert len(failures) == 1
        assert "MISSING file post-PR" in failures[0]
        assert info["n_files_extra_in_baseline"] == 1

    def test_ignores_b_half_files(self, harness, tmp_path):
        """B-half output files MUST be ignored by Layer 1 (they're
        Layer 2's job). A b-half file with mismatched bytes does NOT
        trigger a Layer 1 failure."""
        animal = "PS51"
        date = datetime.date(2025, 4, 30)
        date_str = "20250430"
        # Touch a b-half file (mismatching some hypothetical baseline)
        _write_npz(
            tmp_path / "licks_and_rewards" / animal / f"{date_str}b.npz",
            b"b-half-bytes",
        )
        # Empty baseline + only a b-half file in tmp → no Layer 1 work
        failures, info = harness._compare_bare_half_byte_identity(
            animal, date, tmp_path, {}, {},
        )
        assert failures == []
        assert info["n_files_checked"] == 0
