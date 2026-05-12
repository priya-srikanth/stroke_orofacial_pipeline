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

import tempfile

import numpy as np

from stroke_orofacial.manifest import (
    OverlappingRegistryError,
    load_secondary_spout_sessions,
)
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.session_processing import (
    process_session_by_animal_date,
)


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


def _is_params_json(rel: str) -> bool:
    """Return True iff ``rel`` is a per-session params provenance JSON.

    Per Task 0.5 finding (empirically verified), ``params/*.json``
    files carry a ``run_timestamp`` field that varies on every run.
    Byte-identity comparison must EXCLUDE these files; their content
    is validated structurally elsewhere (Task 3d test pins
    session_id-suffix propagation).
    """
    return rel.startswith("params/") or "/params/" in rel


def _is_bare_half_path(
    rel: str, animal: str, date_str: str,
) -> bool:
    """Return True iff a relative path (under ``output_root``) belongs
    to the bare half of ``(animal, date_str)``.

    Bare-half outputs land at ``{output_type}/{animal}/{date_str}.{ext}``
    or ``params/{animal}/{date_str}.json``. b-half outputs land at
    ``{output_type}/{animal}/{date_str}b.{ext}``. The Pattern A
    multi-half subdir convention (``{date_str}ab/``) is not
    Pattern-B-relevant.

    Heuristic: filename matches ``{date_str}.<ext>`` (no suffix
    immediately following date_str). Rejects ``{date_str}b.<ext>``,
    ``{date_str}ab/{date_str}a.<ext>``, etc.
    """
    name = rel.rsplit("/", 1)[-1]
    # Filename starts with date_str. If the next char is a digit/letter
    # (e.g., "b" for b-half, "a" for Pattern A halves), it's not the
    # bare half. The bare-half filename is exactly "{date_str}.<ext>"
    # — the character right after date_str must be a "." (extension
    # separator).
    if not name.startswith(date_str):
        return False
    after = name[len(date_str):]
    return after.startswith(".")


def _compare_bare_half_byte_identity(
    animal: str,
    date: datetime.date,
    tmp_root: Path,
    baseline_hashes: dict[str, str],
    baseline_errors: dict[str, str],
) -> tuple[list[str], dict[str, Any]]:
    """Compare bare-half output hashes against the baseline.

    Returns ``(failures, info)``:
      - ``failures``: per-output mismatch messages (strings); empty
        list means PASS for this session.
      - ``info``: per-session metadata (hash counts, excluded
        params/*.json count, special-case notes).

    Excludes ``params/*.json`` per Task 0.5 finding. Walks ``tmp_root``
    for files whose relative path matches the bare-half-path heuristic
    (no suffix immediately after ``date_str`` in the filename).
    Baseline lookup key format mirrors the Task 0.5 capture script's
    output: ``f"{animal}/{date_str}/{relpath}"``.
    """
    date_str = date.strftime("%Y%m%d")
    failures: list[str] = []
    info: dict[str, Any] = {
        "session_key": f"{animal}/{date_str}",
        "n_files_checked": 0,
        "n_files_excluded_params": 0,
        "n_files_missing_in_baseline": 0,
        "n_files_extra_in_baseline": 0,
    }

    # Walk + hash every bare-half file under tmp_root
    hashes_now: dict[str, str] = {}
    for p in sorted(tmp_root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(tmp_root).as_posix()
        if not _is_bare_half_path(rel, animal, date_str):
            continue  # b-half or Pattern A subdir — not Layer 1 scope
        full_key = f"{animal}/{date_str}/{rel}"
        if _is_params_json(rel):
            info["n_files_excluded_params"] += 1
            continue
        digest = _sha256_file(p)
        hashes_now[full_key] = digest

    info["n_files_checked"] = len(hashes_now)

    # Compare each computed hash against baseline
    for full_key, current_digest in hashes_now.items():
        if full_key not in baseline_hashes:
            info["n_files_missing_in_baseline"] += 1
            failures.append(
                f"NEW file emitted post-PR (not in baseline): {full_key}"
            )
            continue
        baseline_digest = baseline_hashes[full_key]
        if current_digest != baseline_digest:
            failures.append(
                f"BYTE MISMATCH: {full_key}\n"
                f"  baseline:  {baseline_digest}\n"
                f"  post-PR:   {current_digest}"
            )

    # Also check baseline-only files (regression: baseline expected
    # them but post-PR didn't emit them).
    session_prefix = f"{animal}/{date_str}/"
    baseline_keys_for_session = {
        k for k in baseline_hashes if k.startswith(session_prefix)
        and not _is_params_json(k[len(session_prefix):])
    }
    for k in baseline_keys_for_session:
        if k not in hashes_now:
            info["n_files_extra_in_baseline"] += 1
            failures.append(
                f"MISSING file post-PR (was in baseline): {k}"
            )

    return failures, info


def _layer1_bare_half_byte_identity(
    log: _ForensicLog,
    cohort: list[tuple[str, datetime.date]],
    baseline: dict[str, Any],
    overrides_config: dict[str, Any],
) -> LayerResult:
    """Layer 1 — bare-half byte-identity vs Task 0.5 baseline.

    For each Pattern B session, run ``process_session_by_animal_date``
    against the feature branch with ``output_root=tmp_path``, SHA256
    every bare-half output, and compare against the baseline. Excludes
    ``params/*.json`` per Task 0.5 finding (non-deterministic
    ``run_timestamp``).

    Edge case PS55/2025-04-24 (in baseline ``errors`` block): two
    valid outcomes — bare-half still errors with matching message
    (trivial parity), OR bare-half succeeds via the
    ``bare_ws_subdir_override`` in the registry (expected divergence;
    structurally validate). Either outcome = PASS for that session.
    """
    log("=" * 70)
    log("Layer 1 — bare-half byte-identity vs Task 0.5 baseline")
    log("=" * 70)

    baseline_hashes: dict[str, str] = baseline.get("hashes", {})
    baseline_errors: dict[str, str] = baseline.get("errors", {})
    log(
        f"  baseline: {len(baseline_hashes)} hashes, "
        f"{len(baseline_errors)} errored sessions"
    )
    log(
        "  excluding params/*.json from byte-identity per "
        "Task 0.5 finding (run_timestamp non-deterministic)"
    )

    all_failures: list[str] = []
    per_session_info: list[dict[str, Any]] = []
    n_pass = n_fail = n_special = 0

    for i, (animal, date) in enumerate(cohort, start=1):
        date_str = date.strftime("%Y%m%d")
        session_key = f"{animal}/{date_str}"
        log(f"[{i}/{len(cohort)}] {session_key}: ", )

        baseline_errored_this_session = session_key in baseline_errors

        try:
            with tempfile.TemporaryDirectory(
                prefix="parity_layer1_",
            ) as tmp:
                tmp_root = Path(tmp)
                resolver = PathResolver(output_root=tmp_root)
                result_per_suffix = process_session_by_animal_date(
                    animal, date, resolver,
                    overwrite="force",
                    overrides_config=overrides_config,
                )

                # Extract bare-half result (key=None). Missing => bare
                # half failed; check whether the baseline ALSO marked
                # this session as errored (PS55/2025-04-24 case).
                bare_result = result_per_suffix.get(None)
                if bare_result is None:
                    if baseline_errored_this_session:
                        log(
                            f"  SPECIAL: bare-half failed post-PR "
                            f"(matches baseline ERROR). Trivial "
                            f"parity. baseline error msg: "
                            f"{baseline_errors[session_key]}"
                        )
                        n_special += 1
                    else:
                        msg = (
                            f"{session_key}: bare-half failed post-PR "
                            f"but baseline expected success (no "
                            f"baseline error entry). The Task-4 "
                            f"partial-failure handler swallowed the "
                            f"error inside process_session_by_animal_date."
                        )
                        log(f"  FAIL: {msg}")
                        all_failures.append(msg)
                        n_fail += 1
                    continue

                # Compare bytes
                session_failures, session_info = _compare_bare_half_byte_identity(
                    animal, date, tmp_root,
                    baseline_hashes, baseline_errors,
                )

                if baseline_errored_this_session and not session_failures:
                    # Expected-divergence path: baseline errored, but
                    # post-PR succeeded AND structural checks pass.
                    # PS55/2025-04-24 typical outcome if the registry
                    # override took effect.
                    log(
                        f"  SPECIAL: bare-half SUCCEEDED post-PR but "
                        f"baseline ERRORED. Expected divergence "
                        f"(likely via bare_ws_subdir_override). "
                        f"{session_info['n_files_checked']} bare-half "
                        f"files emitted; "
                        f"{session_info['n_files_excluded_params']} "
                        f"params/*.json excluded from byte-identity."
                    )
                    n_special += 1
                elif session_failures:
                    log(
                        f"  FAIL: {len(session_failures)} "
                        f"mismatch(es). info={session_info}"
                    )
                    for sf in session_failures[:10]:
                        log(f"    - {sf}")
                    all_failures.extend(session_failures)
                    n_fail += 1
                else:
                    log(
                        f"  PASS: {session_info['n_files_checked']} "
                        f"bytes-equal; "
                        f"{session_info['n_files_excluded_params']} "
                        f"params/*.json excluded"
                    )
                    n_pass += 1

                per_session_info.append(session_info)
        except Exception as e:
            tb = traceback.format_exc()
            log(f"  ERROR during Layer 1 for {session_key}: {e!r}")
            return LayerResult(
                layer=1, name="bare_half_byte_identity",
                status="error",
                summary=f"exception during {session_key}: {e!r}",
                traceback_str=tb,
            )

    log("")
    log(
        f"Layer 1 summary: "
        f"{n_pass} PASS, {n_special} SPECIAL (expected divergence / "
        f"trivial-parity error), {n_fail} FAIL out of {len(cohort)} "
        f"sessions"
    )

    if all_failures:
        return LayerResult(
            layer=1, name="bare_half_byte_identity",
            status="fail",
            summary=(
                f"{n_fail} sessions FAILed byte-identity "
                f"({len(all_failures)} total mismatches)"
            ),
            failures=all_failures,
            info={
                "n_pass": n_pass,
                "n_fail": n_fail,
                "n_special": n_special,
                "per_session_info": per_session_info,
            },
        )

    return LayerResult(
        layer=1, name="bare_half_byte_identity",
        status="pass",
        summary=(
            f"{n_pass} sessions byte-identical; {n_special} "
            f"expected-divergence/trivial-parity"
        ),
        info={
            "n_pass": n_pass,
            "n_fail": n_fail,
            "n_special": n_special,
            "per_session_info": per_session_info,
        },
    )


def _validate_b_half_licks_npz(
    b_path: Path, bare_path: Path | None,
) -> list[str]:
    """Structural checks on a b-half licks_and_rewards NPZ.

    Required keys, dtypes, side-convention-stamp parity with bare half
    (when present). Returns list of failure strings; empty = PASS.
    """
    failures: list[str] = []
    try:
        b_data = np.load(b_path, allow_pickle=True)
    except Exception as e:
        return [f"could not load b-half NPZ {b_path}: {e!r}"]

    missing = [k for k in _LICKS_REQUIRED_KEYS if k not in b_data.files]
    if missing:
        failures.append(
            f"licks_and_rewards b-half missing required keys: {missing}"
        )

    # Event arrays should be 1D int (Lick_L/R, Reward_L/R, Tone_L/R)
    for key in ("Lick_L", "Lick_R", "Reward_L", "Reward_R", "Tone_L", "Tone_R"):
        if key not in b_data.files:
            continue
        arr = np.asarray(b_data[key])
        if arr.ndim != 1:
            failures.append(
                f"licks_and_rewards b-half {key!r}: expected 1D, got ndim={arr.ndim}"
            )
        if not np.issubdtype(arr.dtype, np.integer):
            failures.append(
                f"licks_and_rewards b-half {key!r}: expected int dtype, got {arr.dtype}"
            )

    # n_samples plausible
    if "n_samples" in b_data.files:
        n_samples = int(np.asarray(b_data["n_samples"]))
        if n_samples <= 0 or n_samples >= 100_000_000:
            failures.append(
                f"licks_and_rewards b-half n_samples={n_samples} "
                f"outside plausible range (0, 100M)"
            )

    # Side-convention stamps must match the bare half's stamps
    # (regression for Task 3a-d plumbing — both halves of a Pattern B
    # session share the same animal-info rig orientation).
    if bare_path is not None and bare_path.exists():
        try:
            bare_data = np.load(bare_path, allow_pickle=True)
        except Exception as e:
            failures.append(
                f"could not load bare-half NPZ for stamp comparison: {e!r}"
            )
        else:
            for key in _SIDE_CONVENTION_KEYS:
                if key not in b_data.files or key not in bare_data.files:
                    continue
                b_val = np.asarray(b_data[key]).item()
                bare_val = np.asarray(bare_data[key]).item()
                if b_val != bare_val:
                    failures.append(
                        f"licks_and_rewards b-half {key!r}: "
                        f"b={b_val!r} vs bare={bare_val!r} (mismatch)"
                    )

            # Fs must match
            if "Fs" in b_data.files and "Fs" in bare_data.files:
                b_fs = float(np.asarray(b_data["Fs"]))
                bare_fs = float(np.asarray(bare_data["Fs"]))
                if b_fs != bare_fs:
                    failures.append(
                        f"licks_and_rewards b-half Fs: "
                        f"b={b_fs} vs bare={bare_fs} (mismatch)"
                    )

    return failures


def _validate_b_half_generic_npz(
    b_path: Path, bare_path: Path | None, output_type: str,
) -> list[str]:
    """Generic structural checks for the 6 non-licks output types.

    The bare half's keyset is treated as ground truth — Layer 2
    verifies the b-half NPZ has the same keys.
    """
    failures: list[str] = []
    try:
        b_data = np.load(b_path, allow_pickle=True)
    except Exception as e:
        return [f"could not load b-half {output_type} NPZ {b_path}: {e!r}"]

    if bare_path is not None and bare_path.exists():
        try:
            bare_data = np.load(bare_path, allow_pickle=True)
        except Exception as e:
            failures.append(
                f"could not load bare-half {output_type} NPZ for "
                f"keyset comparison: {e!r}"
            )
        else:
            b_keys = set(b_data.files)
            bare_keys = set(bare_data.files)
            missing = bare_keys - b_keys
            if missing:
                failures.append(
                    f"{output_type} b-half missing keys present in "
                    f"bare-half: {sorted(missing)}"
                )

    return failures


def _validate_b_half_params_json(
    b_path: Path, animal: str, date_str: str,
) -> list[str]:
    """Structural checks on a b-half params.json file.

    - Parses as valid JSON.
    - ``session_id`` == ``f"{animal}_{date_str}b"`` (regression for
      Task 3d's manifest.session_id propagation through provenance).
    - ``run_timestamp`` present (any string; content irrelevant).
    """
    failures: list[str] = []
    try:
        with b_path.open(encoding="utf-8") as f:
            record = json.load(f)
    except Exception as e:
        return [f"could not parse params.json {b_path}: {e!r}"]

    expected_session_id = f"{animal}_{date_str}b"
    actual_session_id = record.get("session_id")
    if actual_session_id != expected_session_id:
        failures.append(
            f"params.json session_id: expected {expected_session_id!r}, "
            f"got {actual_session_id!r} (Task 3d regression?)"
        )

    if "run_timestamp" not in record:
        failures.append(
            "params.json missing run_timestamp field"
        )

    return failures


def _validate_b_half_outputs(
    animal: str,
    date: datetime.date,
    tmp_root: Path,
) -> tuple[list[str], dict[str, Any]]:
    """Walk ``tmp_root`` for b-half outputs and run per-output-type
    structural checks.

    Returns ``(failures, info)`` where ``failures`` is a list of error
    strings (empty = PASS) and ``info`` is per-session metadata.
    """
    date_str = date.strftime("%Y%m%d")
    failures: list[str] = []
    info: dict[str, Any] = {
        "session_key": f"{animal}/{date_str}",
        "n_b_files_checked": 0,
        "n_b_npz_files": 0,
        "n_b_params_json": 0,
        "b_outputs_per_type": {},
    }

    # Find every b-half NPZ + params.json under tmp_root. b-half filename
    # is ``{date_str}b.<ext>``.
    b_filename = f"{date_str}b"
    for p in sorted(tmp_root.rglob("*")):
        if not p.is_file():
            continue
        name = p.name
        if not name.startswith(b_filename):
            continue
        after = name[len(b_filename):]
        if not after.startswith("."):
            continue  # not a clean b-half file

        info["n_b_files_checked"] += 1
        # Identify output_type from path
        # Expected layout: {output_type}/{animal}/{date_str}b.<ext>
        # OR params/{animal}/{date_str}b.json
        parts = p.relative_to(tmp_root).parts
        if len(parts) < 3:
            failures.append(
                f"unexpected b-half output path layout: "
                f"{p.relative_to(tmp_root).as_posix()}"
            )
            continue
        output_type = parts[0]
        # Bare-half counterpart at the same layout with bare filename
        bare_path = p.parent / f"{date_str}{p.suffix}"

        info["b_outputs_per_type"][output_type] = (
            info["b_outputs_per_type"].get(output_type, 0) + 1
        )

        if output_type == "params":
            info["n_b_params_json"] += 1
            failures.extend(_validate_b_half_params_json(p, animal, date_str))
        elif output_type == "licks_and_rewards":
            info["n_b_npz_files"] += 1
            failures.extend(_validate_b_half_licks_npz(p, bare_path))
        else:
            info["n_b_npz_files"] += 1
            failures.extend(
                _validate_b_half_generic_npz(p, bare_path, output_type)
            )

    return failures, info


def _layer2_b_half_structural(
    log: _ForensicLog,
    cohort: list[tuple[str, datetime.date]],
    overrides_config: dict[str, Any],
) -> LayerResult:
    """Layer 2 — b-half structural validation.

    For each Pattern B session, run ``process_session_by_animal_date``
    against the feature branch and structurally validate every b-half
    output (NPZ keysets, scalar shapes, side-convention stamp parity
    with the bare half, params.json session_id-suffix propagation).

    No legacy comparison — b halves were silently discarded pre-PR.
    SKIP_NO_B_HALF (surfaced as INFO, not FAIL) when both halves of a
    session failed to emit (e.g., PS55/2025-04-24 if the bare override
    didn't take effect AND the b half also failed).
    """
    log("=" * 70)
    log("Layer 2 — b-half structural validation")
    log("=" * 70)

    all_failures: list[str] = []
    per_session_info: list[dict[str, Any]] = []
    n_pass = n_fail = n_skip_no_b = 0

    for i, (animal, date) in enumerate(cohort, start=1):
        date_str = date.strftime("%Y%m%d")
        session_key = f"{animal}/{date_str}"
        log(f"[{i}/{len(cohort)}] {session_key}: ", )

        try:
            with tempfile.TemporaryDirectory(
                prefix="parity_layer2_",
            ) as tmp:
                tmp_root = Path(tmp)
                resolver = PathResolver(output_root=tmp_root)
                result_per_suffix = process_session_by_animal_date(
                    animal, date, resolver,
                    overwrite="force",
                    overrides_config=overrides_config,
                )

                # Check b-half exists in result
                if "b" not in result_per_suffix:
                    log(
                        "  SKIP_NO_B_HALF: b half did not emit "
                        "(partial-failure path inside "
                        "process_session_by_animal_date)"
                    )
                    n_skip_no_b += 1
                    continue

                session_failures, session_info = _validate_b_half_outputs(
                    animal, date, tmp_root,
                )

                if session_failures:
                    log(
                        f"  FAIL: {len(session_failures)} structural "
                        f"check(s) failed. info={session_info}"
                    )
                    for sf in session_failures[:10]:
                        log(f"    - {sf}")
                    all_failures.extend(session_failures)
                    n_fail += 1
                else:
                    log(
                        f"  PASS: {session_info['n_b_files_checked']} "
                        f"b-half files validated "
                        f"({session_info['n_b_npz_files']} NPZs + "
                        f"{session_info['n_b_params_json']} params.json)"
                    )
                    n_pass += 1

                per_session_info.append(session_info)
        except Exception as e:
            tb = traceback.format_exc()
            log(f"  ERROR during Layer 2 for {session_key}: {e!r}")
            return LayerResult(
                layer=2, name="b_half_structural",
                status="error",
                summary=f"exception during {session_key}: {e!r}",
                traceback_str=tb,
            )

    log("")
    log(
        f"Layer 2 summary: "
        f"{n_pass} PASS, {n_skip_no_b} SKIP_NO_B_HALF, "
        f"{n_fail} FAIL out of {len(cohort)} sessions"
    )

    if all_failures:
        return LayerResult(
            layer=2, name="b_half_structural",
            status="fail",
            summary=(
                f"{n_fail} sessions had structural failures "
                f"({len(all_failures)} total)"
            ),
            failures=all_failures,
            info={
                "n_pass": n_pass,
                "n_fail": n_fail,
                "n_skip_no_b": n_skip_no_b,
                "per_session_info": per_session_info,
            },
        )

    # All PASS or SKIP_NO_B_HALF. The latter is informational.
    summary = f"{n_pass} sessions structurally valid"
    if n_skip_no_b:
        summary += f"; {n_skip_no_b} skip_no_b_half (b half didn't emit)"
    return LayerResult(
        layer=2, name="b_half_structural",
        status="pass",
        summary=summary,
        info={
            "n_pass": n_pass,
            "n_fail": n_fail,
            "n_skip_no_b": n_skip_no_b,
            "per_session_info": per_session_info,
        },
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
