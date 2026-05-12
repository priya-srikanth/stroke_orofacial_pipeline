"""Phase 7-pre-secondary-spout Task 6 — 3-layer live parity gate.

Mirrors the structure of
``tests/scripts/parity_phase7_pre_multi_half.py`` but targets the
Pattern B (closer-spout 2nd-acquisition) cohort: 19 sessions across
PS51/PS54/PS55 declared in
``configs/session_overrides.yaml::secondary_spout_sessions``.

Three layers, exit-code-driven verdict per the kickoff Task 6 spec:

  Layer 1 — Bare-half byte-identity.
    For each Pattern B session, run ``process_session_by_animal_date``
    against the feature-branch checkout with ``output_root=tmp_path``,
    SHA256 every bare-half output, compare against
    ``tests/scripts/_baselines/phase_7_pre_secondary_spout/sha256.json``
    (captured in Task 0.5 against ``main`` HEAD before the feature
    branch was created). Proves the bare-half code path is unchanged.

    Excludes ``params/*.json`` from byte-identity per Task 0.5
    finding (``run_timestamp`` is non-deterministic).

    Edge case PS55/2025-04-24 (a-suffix bare WS dir, captured as
    error in baseline): two valid outcomes post-PR — bare half still
    errors (trivial parity) OR bare half succeeds via the
    ``bare_ws_subdir_override`` in the registry (expected divergence;
    structurally validated). Either outcome = PASS.

  Layer 2 — b-half structural validation.
    For each Pattern B session's b-half outputs (when produced):
    schema-correctness checks on the emitted NPZs / params JSON. No
    legacy comparison — b halves were silently discarded pre-PR per
    the kickoff. Required keys, shape sanity, side-convention stamps
    inherited from the bare half.

  Layer 3 — Defensive-check synthetic.
    No MICROSCOPE required. Thin re-execution of 5 unit-test
    scenarios as a single-script flow:
      1. Pattern A still merges (PS48/20250314 path unaffected).
      2. Pattern B yields two manifests (PS51/20250430).
      3. Overlapping-registry config raises OverlappingRegistryError.
      4. n_dlc=2 on Pattern B does NOT trip MultiHalfNotDeclaredError.
      5. Single-half non-Pattern-B unchanged.

Forensic log
------------

Every run writes
``.scratch_phase_7_pre/parity_run_secondary_spout_<timestamp>.log``
with the full stdout + per-layer detail. Path is printed to stdout
for the operator. Logs are NOT git-committed.

Exit codes
----------

  0 — all 3 layers PASS (skip_no_b_half counts as PASS per layer).
  1 — at least one layer FAILED.
  2 — at least one SKIP_NO_LEGACY surfaced as warning.
  5 — preflight error (manifest build, env, path resolver).

CLI
---

  python tests/scripts/parity_phase7_pre_secondary_spout.py
  python tests/scripts/parity_phase7_pre_secondary_spout.py --layer 1
  python tests/scripts/parity_phase7_pre_secondary_spout.py --no-write-log
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from stroke_orofacial.manifest import (
    OverlappingRegistryError,
    load_secondary_spout_sessions,
)

# tempfile, numpy, PathResolver, process_session_by_animal_date,
# OUTPUT_TYPES are imported lazily by Layer 1/2/3 implementations
# (Tasks 6b/c/d) to keep the Task 6a skeleton's import surface
# minimal + ruff-clean.


# ---- Constants ----

BASELINE_JSON_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts" / "_baselines"
    / "phase_7_pre_secondary_spout" / "sha256.json"
)

# Layer 1: SHA256 of empty file. Used to flag accidentally-empty
# outputs (zero-byte NPZs would byte-match each other but indicate
# a broken pipeline).
EMPTY_FILE_SHA = (
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)

# Layer 2: required keys on b-half NPZs (per OUTPUT_TYPE). The bare-
# half NPZ schema is treated as ground truth — Layer 2 compares the
# b half's keyset against the bare half's keyset (subset/equality
# checks). Plus a few explicit-required-keys lists for the most
# Pattern-B-relevant output types.
_LICKS_REQUIRED_KEYS: tuple[str, ...] = (
    "Lick_L", "Lick_R", "Reward_L", "Reward_R",
    "Tone_L", "Tone_R",
    "Fs", "n_samples",
    "side_convention_version", "wavesurfer_sides_match_mouse_sides",
)
_SIDE_CONVENTION_KEYS: tuple[str, ...] = (
    "side_convention_version",
    "wavesurfer_sides_match_mouse_sides",
)


# ---- Data structures ----

LayerStatus = Literal["pass", "fail", "skip_no_legacy", "error"]


@dataclass
class LayerResult:
    """Per-layer verdict + diagnostic detail."""

    layer: int
    name: str
    status: LayerStatus
    summary: str
    failures: list[str] = field(default_factory=list)
    info: dict[str, Any] = field(default_factory=dict)
    traceback_str: str | None = None


# ---- Forensic log writer ----


class _ForensicLog:
    """Tee-style writer: prints every line to stdout AND appends to a log
    file. Used by all 3 layers + the dispatcher."""

    def __init__(self, log_path: Path | None) -> None:
        self.log_path = log_path
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(log_path, "w", encoding="utf-8")
            self._fh.write(
                f"# parity_phase7_pre_secondary_spout log\n"
                f"# started: {datetime.datetime.now().isoformat()}\n"
            )
        else:
            self._fh = None

    def __call__(self, msg: str = "") -> None:
        # ASCII-safe stdout write for Windows cp1252 consoles
        safe = msg.encode("ascii", "replace").decode("ascii")
        print(safe)
        if self._fh is not None:
            # The log file is UTF-8 — write the original message
            # untouched so unicode-bearing notes survive intact.
            self._fh.write(msg + "\n")

    def close(self) -> None:
        if self._fh is not None:
            self._fh.write(
                f"# ended: {datetime.datetime.now().isoformat()}\n"
            )
            self._fh.close()


# ---- Cohort + baseline loaders ----


def _load_baseline() -> dict[str, Any]:
    """Load the Task 0.5 baseline JSON.

    Returns the full top-level dict (metadata + hashes + errors).
    """
    if not BASELINE_JSON_PATH.exists():
        raise FileNotFoundError(
            f"baseline JSON not found at {BASELINE_JSON_PATH}. "
            f"Task 0.5 should have committed this; was the chore PR "
            f"merged into main?"
        )
    with BASELINE_JSON_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _verify_baseline_git_sha_in_history(baseline_git_sha: str) -> bool:
    """Sanity-check: confirm the baseline's captured_against_git_sha
    is reachable in the local git history. Guards against running
    against a baseline from an unrelated history line."""
    try:
        result = subprocess.run(
            ["git", "cat-file", "-e", baseline_git_sha],
            capture_output=True, text=True, check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def _load_pattern_b_cohort(
    overrides_config: dict[str, Any],
) -> list[tuple[str, datetime.date]]:
    """Iterate the 19 Pattern B (animal, date) pairs from the registry,
    sorted by (animal, date) for deterministic order.

    Returns a list of tuples; mirrors the Task 0.5 capture script's
    ``SECONDARY_SPOUT_COHORT`` ordering convention.
    """
    registry = load_secondary_spout_sessions(overrides_config)
    cohort: list[tuple[str, datetime.date]] = []
    for animal in sorted(registry.keys()):
        for iso_date in sorted(registry[animal].keys()):
            date = datetime.date.fromisoformat(iso_date)
            cohort.append((animal, date))
    return cohort


def _sha256_file(path: Path) -> str:
    """Return SHA256 hex digest of ``path``."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _walk_and_hash(root: Path) -> dict[str, str]:
    """Walk every file under ``root`` and return ``{relpath: sha256}``.

    Mirrors the Task 0.5 capture script's helper of the same name.
    Keys are POSIX relative paths from ``root`` so the JSON is
    portable across Windows / Mac.
    """
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        out[rel] = _sha256_file(p)
    return out


# ---- Layer 1, 2, 3 placeholders (filled in by Tasks 6b/c/d) ----


def _layer1_bare_half_byte_identity(
    log: _ForensicLog,
    cohort: list[tuple[str, datetime.date]],
    baseline: dict[str, Any],
    overrides_config: dict[str, Any],
) -> LayerResult:
    """Layer 1 — bare-half byte-identity vs Task 0.5 baseline.

    Filled in by Task 6b. Placeholder returns SKIP_NO_LEGACY so the
    Task 6a skeleton run produces a sensible verdict.
    """
    log("=" * 70)
    log("Layer 1 — bare-half byte-identity vs Task 0.5 baseline")
    log("=" * 70)
    log("  (Task 6a skeleton — Layer 1 implementation lands in Task 6b)")
    return LayerResult(
        layer=1, name="bare_half_byte_identity",
        status="skip_no_legacy",
        summary="Task 6a skeleton placeholder; Task 6b implements",
    )


def _layer2_b_half_structural(
    log: _ForensicLog,
    cohort: list[tuple[str, datetime.date]],
    overrides_config: dict[str, Any],
) -> LayerResult:
    """Layer 2 — b-half structural validation.

    Filled in by Task 6c. Placeholder returns SKIP_NO_LEGACY for
    Task 6a.
    """
    log("=" * 70)
    log("Layer 2 — b-half structural validation")
    log("=" * 70)
    log("  (Task 6a skeleton — Layer 2 implementation lands in Task 6c)")
    return LayerResult(
        layer=2, name="b_half_structural",
        status="skip_no_legacy",
        summary="Task 6a skeleton placeholder; Task 6c implements",
    )


def _layer3_defensive_check_synthetic(
    log: _ForensicLog,
) -> LayerResult:
    """Layer 3 — defensive-check synthetic. No MICROSCOPE required.

    Filled in by Task 6d. Placeholder returns SKIP_NO_LEGACY for
    Task 6a.
    """
    log("=" * 70)
    log("Layer 3 — defensive-check synthetic scenarios")
    log("=" * 70)
    log("  (Task 6a skeleton — Layer 3 implementation lands in Task 6d)")
    return LayerResult(
        layer=3, name="defensive_check_synthetic",
        status="skip_no_legacy",
        summary="Task 6a skeleton placeholder; Task 6d implements",
    )


# ---- Dispatcher + exit-code logic ----


def _exit_code_for_results(results: list[LayerResult]) -> int:
    """Map per-layer results to a single exit code.

    0 — all PASS.
    1 — at least one FAIL or ERROR.
    2 — no FAIL/ERROR but at least one SKIP_NO_LEGACY surfaced as
        worth-the-operator's-attention.
    """
    if any(r.status in ("fail", "error") for r in results):
        return 1
    if any(r.status == "skip_no_legacy" for r in results):
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 7-pre-secondary-spout 3-layer parity gate (Task 6). "
            "Live MICROSCOPE execution required for Layers 1 + 2."
        ),
    )
    parser.add_argument(
        "--layer", type=int, choices=(1, 2, 3),
        help="Run only one layer (1/2/3); default = all 3.",
    )
    parser.add_argument(
        "--no-write-log", action="store_true",
        help="Skip the forensic .log file under .scratch_phase_7_pre/.",
    )
    parser.add_argument(
        "--output-log", type=Path, default=None,
        help=(
            "Explicit log path. Default: "
            ".scratch_phase_7_pre/parity_run_secondary_spout_<ISO_TIMESTAMP>.log."
        ),
    )
    args = parser.parse_args(argv)

    # Forensic log setup
    if args.no_write_log:
        log_path: Path | None = None
    elif args.output_log is not None:
        log_path = args.output_log
    else:
        ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        log_path = (
            Path(".scratch_phase_7_pre")
            / f"parity_run_secondary_spout_{ts}.log"
        )
    log = _ForensicLog(log_path)

    log("=" * 70)
    log("Phase 7-pre-secondary-spout parity gate")
    log(f"started: {datetime.datetime.now().isoformat()}")
    if log_path:
        log(f"log file: {log_path}")
    log("=" * 70)
    log("")

    # Preflight
    try:
        log("Preflight — loading baseline + cohort...")
        baseline = _load_baseline()
        baseline_sha = baseline["metadata"]["captured_against_git_sha"]
        log(f"  baseline captured against git sha: {baseline_sha}")
        if not _verify_baseline_git_sha_in_history(baseline_sha):
            log(
                "  WARNING: baseline git sha not in local history. "
                "Baseline may be from an unrelated branch — verify "
                "this is expected before trusting Layer 1 results."
            )
        log(
            f"  baseline successes: {baseline['metadata']['successes']}, "
            f"errors: {baseline['metadata']['errors']}, "
            f"hashes: {len(baseline['hashes'])}"
        )

        from stroke_orofacial.config_loader import load_session_overrides
        overrides_config = load_session_overrides()
        cohort = _load_pattern_b_cohort(overrides_config)
        log(f"  cohort: {len(cohort)} Pattern B sessions")
        for animal, date in cohort:
            log(f"    {animal}/{date.isoformat()}")
    except OverlappingRegistryError as e:
        log(f"PREFLIGHT ERROR (OverlappingRegistryError): {e}")
        log.close()
        return 5
    except Exception as e:
        log(f"PREFLIGHT ERROR: {e!r}")
        log(traceback.format_exc())
        log.close()
        return 5

    log("")

    # Run layers
    results: list[LayerResult] = []
    layers_to_run = [args.layer] if args.layer else [1, 2, 3]

    for layer_num in layers_to_run:
        if layer_num == 1:
            results.append(_layer1_bare_half_byte_identity(
                log, cohort, baseline, overrides_config,
            ))
        elif layer_num == 2:
            results.append(_layer2_b_half_structural(
                log, cohort, overrides_config,
            ))
        elif layer_num == 3:
            results.append(_layer3_defensive_check_synthetic(log))
        log("")

    # Verdict
    log("=" * 70)
    log("VERDICT SUMMARY")
    log("=" * 70)
    for r in results:
        log(f"  Layer {r.layer} ({r.name:30s}): {r.status.upper():16s} — {r.summary}")
        if r.traceback_str:
            log("    traceback:")
            for line in r.traceback_str.splitlines():
                log(f"      {line}")
    log("")

    rc = _exit_code_for_results(results)
    log(f"exit code: {rc}")
    log("")
    if rc == 0:
        log("ALL LAYERS PASS. Phase 7-pre-secondary-spout parity gate cleared.")
    elif rc == 2:
        log(
            "Layers ran but at least one SKIP_NO_LEGACY surfaced — "
            "operator review the per-layer info above before declaring "
            "Task 6 complete."
        )
    else:
        log(
            "PARITY GATE FAILED — see per-layer details above. Investigate "
            "before declaring Task 6 done."
        )
    log.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
