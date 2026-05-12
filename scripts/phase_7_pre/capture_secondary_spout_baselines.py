"""Phase 7-pre-secondary-spout Task 0.5 — Pre-PR baseline SHA256 capture.

Captures SHA256 of every emitted output file from running
``process_session_by_animal_date`` on each of the 19 Pattern B sessions
(PS51 ×2, PS54 ×11, PS55 ×6), against the current ``main`` HEAD.

The captured baselines are the byte-identity target for the Phase
7-pre-secondary-spout Layer 1 parity gate (Task 6): after the feature
branch's source/config/test changes land, re-running this same set of
sessions on the feature branch must produce byte-identical bare-half
outputs — proving the single-half code path is unchanged for sessions
that previously single-half-processed through the bare ``{DATE}`` half.

**Why this lives BEFORE branch creation:** if any commit between
branching and Task 6 accidentally changes single-half output paths or
behavior, the baseline becomes "what the feature branch produces"
rather than "what main produces." Capturing on main first is the only
way to keep the baseline as a forward fence-post.

**Read-only against MICROSCOPE.** The script reads the per-session
wavesurfer ``.h5`` files but writes every emitted output to a
``tempfile.TemporaryDirectory()`` per session. Nothing lands on
``stroke_orofacial_pipeline_outputs/`` or on MICROSCOPE itself.

**Per-session graceful failure.** If a single session fails (e.g.,
PS55/20250424 where the bare WS dir is named ``20250424a`` not
``20250424`` — surfaced by the kickoff doc as an edge case), the
script records the exception message under the session's key in the
``errors`` block of the output JSON and continues with the next
session. End-of-run report distinguishes successes vs errors.

**Output JSON path:**
``tests/scripts/_baselines/phase_7_pre_secondary_spout/sha256.json``

**Idempotence:** re-running on the same git SHA produces an identical
JSON modulo the ``metadata.captured_at_iso`` timestamp. The hashes
themselves are deterministic because ``process_session`` is
deterministic on real input data, and SHA256 is content-addressed.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.session_processing import (
    process_session_by_animal_date,
)


# ---- Cohort (19 sessions) ----
# Mirrors the kickoff doc's table at docs/prompts/phase-7-pre-secondary-spout-kickoff.md
# lines 26-44. Ordering: PS51 (2), PS54 (11), PS55 (6) = 19 total.
SECONDARY_SPOUT_COHORT: list[tuple[str, datetime.date]] = [
    ("PS51", datetime.date(2025, 4, 30)),
    ("PS51", datetime.date(2025, 5, 5)),
    ("PS54", datetime.date(2025, 4, 30)),
    ("PS54", datetime.date(2025, 5, 30)),
    ("PS54", datetime.date(2025, 6, 16)),
    ("PS54", datetime.date(2025, 6, 18)),
    ("PS54", datetime.date(2025, 6, 19)),
    ("PS54", datetime.date(2025, 6, 20)),
    ("PS54", datetime.date(2025, 6, 21)),
    ("PS54", datetime.date(2025, 6, 23)),
    ("PS54", datetime.date(2025, 6, 24)),
    ("PS54", datetime.date(2025, 6, 25)),
    ("PS54", datetime.date(2025, 6, 26)),
    ("PS55", datetime.date(2025, 4, 24)),  # a-suffix edge case
    ("PS55", datetime.date(2025, 4, 28)),  # n_dlc=0 edge case (Phase 2 unaffected)
    ("PS55", datetime.date(2025, 4, 30)),
    ("PS55", datetime.date(2025, 5, 30)),
    ("PS55", datetime.date(2025, 6, 1)),
    ("PS55", datetime.date(2025, 6, 5)),
]

OUTPUT_JSON_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests" / "scripts" / "_baselines"
    / "phase_7_pre_secondary_spout" / "sha256.json"
)

SCRIPT_RELPATH_FROM_REPO_ROOT = "scripts/phase_7_pre/capture_secondary_spout_baselines.py"


logger = logging.getLogger(__name__)


def _sha256_file(path: Path) -> str:
    """Return the SHA256 hex digest of ``path``."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_rev_parse_head() -> str:
    """Return ``main`` HEAD SHA at capture time (full 40-char)."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _git_current_branch() -> str:
    """Return current branch name (used for the metadata block)."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _walk_and_hash(root: Path) -> dict[str, str]:
    """Walk every file under ``root``; return {relpath: sha256_hex}.

    Keys are POSIX-style relative paths from ``root`` so the JSON is
    portable across Windows / Mac. Hidden files (dotfiles) are
    included — ``process_session`` may emit ``.params.json`` or
    similar provenance artefacts that count toward parity.
    """
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        out[rel] = _sha256_file(p)
    return out


def _human_size(n_bytes: int) -> str:
    """Format byte count as a short string (used in stdout progress)."""
    units = ["B", "KB", "MB", "GB"]
    size = float(n_bytes)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} {units[-1]}"


def _process_one_session(
    animal: str, date: datetime.date,
) -> tuple[dict[str, str], int, str | None]:
    """Run process_session for one (animal, date); return (hashes, total_bytes, error).

    Returns ``(hashes, total_bytes, None)`` on success — ``hashes``
    maps ``{output_type}/{relpath}`` to SHA256, and ``total_bytes``
    is the sum of file sizes for the stdout progress line.

    Returns ``({}, 0, "<exception message>")`` on failure. The
    exception is logged to stderr (full traceback) so the operator
    can triage; the per-session error message lands in the JSON's
    ``errors`` block.
    """
    try:
        with tempfile.TemporaryDirectory(prefix="capture_baselines_") as tmp:
            tmp_root = Path(tmp)
            resolver = PathResolver(output_root=tmp_root)
            process_session_by_animal_date(
                animal, date, resolver, overwrite="force",
            )
            hashes = _walk_and_hash(tmp_root)
            total_bytes = sum(
                (tmp_root / rel).stat().st_size for rel in hashes
            )
            return hashes, total_bytes, None
    except Exception as exc:
        # Full traceback to stderr for operator triage; short message
        # into the JSON.
        print(
            f"\nERROR processing {animal}/{date.strftime('%Y%m%d')}:",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)
        return {}, 0, f"{type(exc).__name__}: {exc}"


def main() -> int:
    """Run the capture across the 19-session cohort.

    Returns
    -------
    int
        Exit code: 0 if every session succeeded; 1 if any session
        recorded an error (operator must triage before proceeding to
        Task 1).
    """
    logging.basicConfig(level=logging.WARNING)

    git_sha = _git_rev_parse_head()
    branch = _git_current_branch()
    captured_at_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    print("=" * 70)
    print("Phase 7-pre-secondary-spout Task 0.5 — baseline SHA256 capture")
    print(f"  git HEAD : {git_sha}")
    print(f"  branch   : {branch}")
    print(f"  cohort   : {len(SECONDARY_SPOUT_COHORT)} sessions")
    print(f"  out file : {OUTPUT_JSON_PATH}")
    print("=" * 70)

    all_hashes: dict[str, str] = {}
    errors: dict[str, str] = {}
    successes = 0

    for i, (animal, date) in enumerate(SECONDARY_SPOUT_COHORT, start=1):
        date_str = date.strftime("%Y%m%d")
        session_key = f"{animal}/{date_str}"
        print(f"[{i}/{len(SECONDARY_SPOUT_COHORT)}] {session_key}: ", end="", flush=True)

        hashes, total_bytes, err = _process_one_session(animal, date)
        if err is not None:
            errors[session_key] = err
            print(f"ERROR — {err}")
            continue

        # Re-key per the spec: {animal}/{date_str}/<relpath>
        for relpath, digest in hashes.items():
            full_key = f"{session_key}/{relpath}"
            all_hashes[full_key] = digest

        successes += 1
        print(f"{len(hashes)} files, {_human_size(total_bytes)}")

    payload = {
        "metadata": {
            "captured_at_iso": captured_at_iso,
            "captured_against_git_sha": git_sha,
            "captured_against_branch": branch,
            "script_path": SCRIPT_RELPATH_FROM_REPO_ROOT,
            "cohort_size": len(SECONDARY_SPOUT_COHORT),
            "successes": successes,
            "errors": len(errors),
        },
        "hashes": dict(sorted(all_hashes.items())),
        "errors": dict(sorted(errors.items())),
    }

    OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=False)
        f.write("\n")

    print("=" * 70)
    print(f"DONE. wrote {OUTPUT_JSON_PATH}")
    print(
        f"  cohort_size={len(SECONDARY_SPOUT_COHORT)}  "
        f"successes={successes}  errors={len(errors)}  "
        f"hash_count={len(all_hashes)}"
    )
    if errors:
        print(f"  ERRORED sessions ({len(errors)}):")
        for k, v in errors.items():
            print(f"    - {k}: {v}")
        print("=" * 70)
        print(
            "Exit 1: at least one session failed. Triage the per-session "
            "errors above before proceeding to Task 1."
        )
        return 1
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
