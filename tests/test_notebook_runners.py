"""Unit tests for the Phase 6.8a notebook-12 runner script.

Scoped to the counter-split introduced in v6.8a.3: the save loop used
to collapse "zero rewards for trial_group" (``build_tone_aligned_analysis``
returns None), "zero qualifying DLC frames" (``result['histogram']`` is
None), and every other error path into one ``n_err`` bucket. Post-split,
the runner reports five buckets (``ok``, ``skip``, ``skip_no_rewards``,
``skip_no_frames``, ``err``), and each of the two new skip buckets
emits a distinct ``logging.info`` line per skipped (animal, date).

These tests monkey-patch ``build_tone_aligned_analysis`` inside the
runner module so no parquet / licks / alignment / DLC I/O happens,
and inspect the runner's stdout + the ``INFO``-level log records to
confirm the split lands correctly.
"""
from __future__ import annotations

import datetime
import logging
from unittest.mock import MagicMock

import pytest

from stroke_orofacial.animals import AnimalInfo
from stroke_orofacial.manifest import SessionManifest


def _make_animal_info(animal_id: str) -> AnimalInfo:
    """Minimal AnimalInfo sufficient for the runner's use: it only
    reads ``session_start`` / ``session_end`` (to enumerate dates) and
    ``wavesurfer_sides_match_mouse_sides`` (to forward to the analysis
    call)."""
    return AnimalInfo(
        animal_id=animal_id,
        stroke_date=datetime.date(2025, 4, 29),
        session_start=datetime.date(2025, 4, 30),
        session_end=datetime.date(2025, 4, 30),
        wavesurfer_sides_match_mouse_sides=False,
    )


def _make_manifest(animal_id: str, date: datetime.date) -> SessionManifest:
    """Minimal manifest with a non-empty dlc_h5_files list (the runner
    doesn't actually use it because build_tone_aligned_analysis is
    mocked, but a realistic manifest avoids surprises if downstream
    fixture code ever inspects it)."""
    return SessionManifest(
        session_id=f"{animal_id}_{date:%Y%m%d}",
        animal=animal_id,
        date=date,
        day_relative_to_stroke=0,
        phase="post",
        dlc_h5_files=[],
        dlc_csv_files=[],
    )


class _ScriptedAnalysis:
    """Callable that returns a scripted sequence of results for each
    call, so we can drive the save loop through each skip branch in
    a single run. A ``None`` script entry means "return None" (zero
    rewards); a dict with ``histogram=None`` means "zero qualifying
    frames"; a dict with a populated histogram means "ok"."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self._script.pop(0)


@pytest.fixture
def patched_runner(monkeypatch, tmp_path):
    """Set up the runner module with every external dependency
    monkeypatched out. Yields a helper that lets each test specify a
    result-script, then invokes ``main()`` with canned args."""
    from scripts import run_notebook_12_first_emit as runner

    # Redirect the output root to a clean tmp dir so existing on-disk
    # PNGs can't trigger the "skip because already-exists" branch.
    mock_resolver = MagicMock()
    mock_resolver.pipeline_outputs.return_value = tmp_path
    monkeypatch.setattr(runner, "PathResolver", lambda: mock_resolver)

    # One animal, one date, flag=False.
    animals = {"PS51": _make_animal_info("PS51")}
    monkeypatch.setattr(runner, "load_animals", lambda: animals)
    monkeypatch.setattr(
        runner, "load_defaults",
        lambda: {"dlc_spatial": {}, "dlc_spatial_tone_aligned": {}},
    )

    # Build a single manifest for the test animal/date.
    manifest = _make_manifest("PS51", datetime.date(2025, 4, 30))
    monkeypatch.setattr(
        runner, "build_manifest",
        lambda animal_id, date, resolver, info: manifest,
    )

    # Suppress the matplotlib save path — only reachable for the "ok"
    # branch and never exercised by the skip tests below.
    monkeypatch.setattr(runner, "_render_and_save", lambda *a, **kw: None)

    def drive(script, extra_args=None):
        analysis = _ScriptedAnalysis(script)
        monkeypatch.setattr(
            runner, "build_tone_aligned_analysis", analysis,
        )
        args = [
            "--animals", "PS51",
            "--dates", "20250430",
            "--bodyparts", "tongue",
            "--center-modes", "eye_midpoint",
            "--trial-groups", "R",
            "--reward-windows-ms=-100,1000",
            "--overwrite", "force",
        ]
        if extra_args:
            args += extra_args
        exit_code = runner.main(args)
        return exit_code, analysis

    return drive


class TestCounterSplit:
    """The v6.8a.3 behaviour: the two legitimate-empty skip branches
    get their own counters + their own log lines, distinct from the
    generic ``n_err`` bucket."""

    def test_skip_no_rewards_increments_and_logs(
        self, patched_runner, caplog, capsys,
    ):
        with caplog.at_level(logging.INFO):
            exit_code, _ = patched_runner(script=[None])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "skip_no_rewards=1" in out
        assert "skip_no_frames=0" in out
        assert "err=0" in out
        assert any(
            "skip_no_rewards" in r.getMessage() and "PS51" in r.getMessage()
            for r in caplog.records
        ), "expected a skip_no_rewards INFO log line for PS51"

    def test_skip_no_frames_increments_and_logs(
        self, patched_runner, caplog, capsys,
    ):
        with caplog.at_level(logging.INFO):
            exit_code, _ = patched_runner(
                script=[{"histogram": None, "n_tones": 10}],
            )
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "skip_no_rewards=0" in out
        assert "skip_no_frames=1" in out
        assert "err=0" in out
        assert any(
            "skip_no_frames" in r.getMessage() and "PS51" in r.getMessage()
            for r in caplog.records
        ), "expected a skip_no_frames INFO log line for PS51"

    def test_err_path_untouched_by_split(self, patched_runner, capsys):
        """A FileNotFoundError during the analysis call still lands in
        ``n_err``, not in either skip bucket — the split is for the
        ``return None`` + ``histogram=None`` paths only."""
        from scripts import run_notebook_12_first_emit as runner

        def raiser(*a, **kw):
            raise FileNotFoundError("simulated missing centered parquet")

        # Override the scripted analysis with a raiser for this test.
        runner.build_tone_aligned_analysis = raiser
        exit_code = runner.main([
            "--animals", "PS51",
            "--dates", "20250430",
            "--bodyparts", "tongue",
            "--center-modes", "eye_midpoint",
            "--trial-groups", "R",
            "--reward-windows-ms=-100,1000",
            "--overwrite", "force",
        ])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "err=1" in out
        assert "skip_no_rewards=0" in out
        assert "skip_no_frames=0" in out
