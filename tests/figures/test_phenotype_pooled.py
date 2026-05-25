"""Tests for ``figures.phenotype_pooled`` — V4/V5 phenotype-pooled emitters.

Phase 9.1 Task 1a skeleton. CLI smoke + binning helpers. Full output-validation
tests deferred until Task 1b scaffold review locks the rendering style.

Per [docs/testing-conventions.md](../../docs/testing-conventions.md), any test
that invokes a pipeline writer must use ``PathResolver(output_root=tmp_path)``.
The smoke tests below do not touch the real ``pipeline_outputs/`` tree.
"""
from __future__ import annotations

import pytest

from stroke_orofacial.figures import _io, phenotype_pooled


def test_cli_help_parses() -> None:
    """`--help` exits 0 without invoking the runner."""
    with pytest.raises(SystemExit) as exc:
        phenotype_pooled._parse_args(["--help"])
    assert exc.value.code == 0


def test_cli_required_flags() -> None:
    """`--endpoint-list` is required."""
    with pytest.raises(SystemExit):
        phenotype_pooled._parse_args([])


def test_cli_default_args() -> None:
    """Default flags parse with only the required --endpoint-list."""
    ns = phenotype_pooled._parse_args(["--endpoint-list", "dummy.txt"])
    assert str(ns.endpoint_list) == "dummy.txt"
    assert ns.phenotype_tiers == "all"
    assert ns.output_dir is None
    assert ns.overwrite == "skip"


def test_cli_all_flags() -> None:
    """All advertised flags accept values."""
    ns = phenotype_pooled._parse_args([
        "--endpoint-list", "list.txt",
        "--phenotype-tiers", "mild,severe",
        "--output-dir", "/tmp/out",
        "--overwrite", "force",
        "--dpi", "300",
    ])
    assert ns.phenotype_tiers == "mild,severe"
    assert ns.overwrite == "force"
    assert ns.dpi == 300


def test_bin_rel_day_post_stroke() -> None:
    """Post-stroke rel_day → 1-indexed bin_idx, ceil(rel_day / bin_days)."""
    assert _io._bin_rel_day(1, 2) == 1
    assert _io._bin_rel_day(2, 2) == 1
    assert _io._bin_rel_day(3, 2) == 2
    assert _io._bin_rel_day(7, 7) == 1
    assert _io._bin_rel_day(14, 7) == 2


def test_bin_rel_day_pre_stroke() -> None:
    """Pre-stroke rel_day → negative bin_idx mirroring post."""
    assert _io._bin_rel_day(0, 2) == 0
    assert _io._bin_rel_day(-1, 2) == -1
    assert _io._bin_rel_day(-2, 2) == -1
    assert _io._bin_rel_day(-3, 2) == -2


def test_bin_midpoint_is_bin_center() -> None:
    """Bin midpoint = (rel_day_min + rel_day_max) / 2 within the bin."""
    # bin_days=2: bin_idx=1 ↔ rel_days {1, 2} ↔ midpoint 1.5.
    assert _io._bin_midpoint_rel_day(1, 2) == 1.5
    assert _io._bin_midpoint_rel_day(2, 2) == 3.5
    # bin_days=7: bin_idx=1 ↔ rel_days {1..7} ↔ midpoint 4.0.
    assert _io._bin_midpoint_rel_day(1, 7) == 4.0
    # Pre mirrors.
    assert _io._bin_midpoint_rel_day(-1, 2) == -1.5
    assert _io._bin_midpoint_rel_day(0, 2) == 0.0


def test_load_endpoint_list_strips_comments(tmp_path) -> None:
    """Comment lines + blanks are ignored; inline ``# tail`` is stripped."""
    p = tmp_path / "list.txt"
    p.write_text(
        "# header\n"
        "\n"
        "tongue_lick1_y_peak\n"
        "first_lick_accuracy_all  # confirmatory\n"
        "\n"
        "# another comment\n"
        "num_correct_licks_per_trial\n",
        encoding="utf-8",
    )
    slugs = _io.load_endpoint_list(p)
    assert slugs == [
        "tongue_lick1_y_peak",
        "first_lick_accuracy_all",
        "num_correct_licks_per_trial",
    ]
