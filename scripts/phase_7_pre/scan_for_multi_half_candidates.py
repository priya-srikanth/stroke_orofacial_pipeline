"""Productized cohort scan for multi-half acquisition candidates.

Walks every (animal, date) per ``configs/animals.yaml`` and counts three
auto-detect signals against the on-disk MICROSCOPE state:

  - ``n_ws``  — wavesurfer subdirs matching ``{DATE}*/{ANIMAL}/`` containing
    at least one ``.h5`` file.
  - ``n_dlc`` — filtered DLC H5 files at ``O2_analysis/{ANIMAL}/`` matching
    ``video2_{date_iso}T*_filtered.h5``.
  - ``n_cam`` — camera subdirs matching ``{DATE}*/{ANIMAL}/`` containing
    at least one ``video*.avi`` file.

Classification (Phase 7-pre-multi-half Task 1 verdict, Decision 2):

  - **Pattern A** — ``n_dlc >= 2``. Both halves DLC-inferred. The only
    case the new pipeline merges (audit-locked Pattern A scope —
    PS48 20250314 is the sole production candidate; future Pattern A
    sessions trip the loud
    :class:`stroke_orofacial.manifest.MultiHalfNotDeclaredError`).

  - **Pattern B** — ``n_dlc < 2 AND n_ws >= 2 AND n_cam >= 2``. WS+camera
    multi-half but DLC single-half. Exploratory by design; the bare-
    ``{DATE}`` half (or ``a`` for some PS55 sessions) is the analyzed
    half. Pattern B sessions stay on the existing single-half
    discovery path — log notice only, never blocks the scan.

  - **Weak** — exactly 1 of ``{n_ws, n_dlc, n_cam}`` is ``>= 2``. Usually
    a partial-acquisition or experimenter-restart corner case. Log
    notice only.

Read-only by design: never writes to ``configs/session_overrides.yaml``.
The script EMITS:

  - A markdown report at ``--output`` (default
    ``docs/phase-7-pre/multi_half_scan_latest.md``).
  - YAML stubs for Pattern A undeclared candidates (printed to stdout
    for copy-paste into ``configs/session_overrides.yaml`` after
    review).

Exit codes (per the verdict's Decision):

  - 0 — scan completed with no Pattern A undeclared (or all Pattern A
    candidates already covered by ``multi_half_sessions:`` in
    ``session_overrides.yaml``).
  - 1 — at least one Pattern A candidate is on-disk but NOT declared in
    YAML. Action: review and add the printed YAML stub to
    ``configs/session_overrides.yaml``.
  - 2 — scan errored (e.g. MICROSCOPE mount unreachable, animals.yaml
    missing).

Usage::

    # Default: MICROSCOPE mounts via PathResolver; report at
    # docs/phase-7-pre/multi_half_scan_latest.md
    python scripts/phase_7_pre/scan_for_multi_half_candidates.py

    # Custom output:
    python scripts/phase_7_pre/scan_for_multi_half_candidates.py \\
        --output /tmp/multi_half_scan.md

    # Quiet mode (suppress stdout summary; useful in CI):
    python scripts/phase_7_pre/scan_for_multi_half_candidates.py --quiet
"""
from __future__ import annotations

import argparse
import datetime
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

# Logically the script lives under scripts/, not src/, so `python -m`
# users get the lazy imports. The package itself is on sys.path via
# editable install.
from stroke_orofacial.animals import AnimalInfo, load_animals
from stroke_orofacial.config_loader import load_session_overrides
from stroke_orofacial.paths import PathResolver

DEFAULT_OUTPUT_PATH = Path("docs/phase-7-pre/multi_half_scan_latest.md")

Classification = Literal["pattern_a", "pattern_b", "weak"]


@dataclass
class ScanCandidate:
    """Per-(animal, date) on-disk scan result.

    Holds the raw counts + the discovered subdir / filenames. The
    ``classification`` field is derived via :func:`_classify` and
    used by the YAML-comparison + exit-code logic downstream.
    """

    animal: str
    date: datetime.date
    n_ws: int
    n_dlc: int
    n_cam: int
    ws_dirs: list[str] = field(default_factory=list)
    dlc_filenames: list[str] = field(default_factory=list)
    cam_dirs: list[str] = field(default_factory=list)
    classification: Classification = "weak"

    @property
    def date_str(self) -> str:
        return self.date.strftime("%Y%m%d")


@dataclass
class ScanResult:
    """Cohort-wide scan output: candidate lists partitioned by class."""

    pattern_a: list[ScanCandidate] = field(default_factory=list)
    pattern_b: list[ScanCandidate] = field(default_factory=list)
    weak: list[ScanCandidate] = field(default_factory=list)
    n_sessions_scanned: int = 0

    @property
    def all_candidates(self) -> list[ScanCandidate]:
        return self.pattern_a + self.pattern_b + self.weak


def _classify(n_ws: int, n_dlc: int, n_cam: int) -> Classification | None:
    """Return classification per the verdict's Decision 2 rule.

    Pattern A: n_dlc >= 2 (the discriminator). Both halves DLC-inferred.
    Pattern B: n_dlc < 2 AND n_ws >= 2 AND n_cam >= 2.
    Weak: exactly 1 of {n_ws, n_dlc, n_cam} is >= 2.
    None: no signal (each count <= 1).
    """
    if n_dlc >= 2:
        return "pattern_a"
    if n_ws >= 2 and n_cam >= 2:
        return "pattern_b"
    n_high = sum(1 for n in (n_ws, n_dlc, n_cam) if n >= 2)
    if n_high == 1:
        return "weak"
    return None


def _scan_single_session(
    animal: str,
    date: datetime.date,
    ws_root: Path,
    dlc_root: Path,
    cam_root: Path,
) -> ScanCandidate | None:
    """Count auto-detect signals for one (animal, date) pair.

    Returns ``None`` when the session shows no multi-half signal at all
    (every count <= 1). The caller filters None entries from the
    cohort sweep.

    Pure I/O — listed via ``Path.glob``. No writes, no side effects.
    """
    date_str = date.strftime("%Y%m%d")
    date_iso = date.strftime("%Y-%m-%d")

    # WS subdirs: walk ws_root/{DATE}*/{animal}/ for *.h5
    ws_dirs: list[str] = []
    if ws_root.exists():
        for entry in sorted(ws_root.iterdir()):
            if not entry.is_dir() or not entry.name.startswith(date_str):
                continue
            animal_dir = entry / animal
            if animal_dir.exists() and any(animal_dir.glob("*.h5")):
                ws_dirs.append(entry.name)

    # DLC: glob filtered H5 at flat O2_analysis/{animal}/ level
    dlc_filenames: list[str] = []
    dlc_animal_dir = dlc_root / animal
    if dlc_animal_dir.exists():
        dlc_filenames = sorted(
            p.name for p in dlc_animal_dir.glob(f"video2_{date_iso}T*_filtered.h5")
        )

    # Camera subdirs: cam_root/{DATE}*/{animal}/ with *.avi
    cam_dirs: list[str] = []
    if cam_root.exists():
        for entry in sorted(cam_root.iterdir()):
            if not entry.is_dir() or not entry.name.startswith(date_str):
                continue
            animal_dir = entry / animal
            if animal_dir.exists() and any(animal_dir.glob("video*.avi")):
                cam_dirs.append(entry.name)

    n_ws = len(ws_dirs)
    n_dlc = len(dlc_filenames)
    n_cam = len(cam_dirs)
    cls = _classify(n_ws, n_dlc, n_cam)
    if cls is None:
        return None

    return ScanCandidate(
        animal=animal,
        date=date,
        n_ws=n_ws,
        n_dlc=n_dlc,
        n_cam=n_cam,
        ws_dirs=ws_dirs,
        dlc_filenames=dlc_filenames,
        cam_dirs=cam_dirs,
        classification=cls,
    )


def _date_range(start: datetime.date, end: datetime.date):
    cur = start
    while cur <= end:
        yield cur
        cur += datetime.timedelta(days=1)


def scan_cohort(
    animals: dict[str, AnimalInfo],
    ws_root: Path,
    dlc_root: Path,
    cam_root: Path,
) -> ScanResult:
    """Walk every (animal, date) in scope; partition into classification buckets.

    Pure function — takes path roots explicitly so tests can pass
    tmp_path-rooted directories without monkeypatching the resolver.
    Production callers use :func:`_path_roots_from_resolver` to derive
    the roots from the live :class:`PathResolver`.
    """
    result = ScanResult()
    for animal_id, info in animals.items():
        if info.session_start is None or info.session_end is None:
            continue
        for date in _date_range(info.session_start, info.session_end):
            result.n_sessions_scanned += 1
            cand = _scan_single_session(
                animal_id, date, ws_root, dlc_root, cam_root,
            )
            if cand is None:
                continue
            if cand.classification == "pattern_a":
                result.pattern_a.append(cand)
            elif cand.classification == "pattern_b":
                result.pattern_b.append(cand)
            else:
                result.weak.append(cand)
    return result


def _yaml_declared_keys(
    overrides_config: dict[str, Any],
) -> set[tuple[str, str]]:
    """Return the set of (animal, date_str) pairs declared under
    ``multi_half_sessions:`` in the supplied overrides config."""
    multi_half = overrides_config.get("multi_half_sessions", {}) or {}
    declared: set[tuple[str, str]] = set()
    for animal_id, animal_block in multi_half.items():
        if not animal_block:
            continue
        for date_str in animal_block:
            declared.add((animal_id, str(date_str)))
    return declared


def _format_yaml_stub_for_undeclared(
    undeclared: list[ScanCandidate],
) -> str:
    """Return the YAML stub block for Pattern A candidates that need to
    be added to ``session_overrides.yaml``.

    The stub uses ``ws_subdir`` / ``cam_subdir`` from the discovered
    subdir names verbatim (no auto-naming-convention assumption — the
    on-disk truth wins). ``file_timestamp`` is parsed from the DLC
    filename (matches the .avi acquisition timestamp).
    """
    if not undeclared:
        return ""
    lines: list[str] = ["multi_half_sessions:"]
    by_animal: dict[str, list[ScanCandidate]] = {}
    for cand in undeclared:
        by_animal.setdefault(cand.animal, []).append(cand)
    for animal_id, cands in by_animal.items():
        lines.append(f"  {animal_id}:")
        for cand in sorted(cands, key=lambda c: c.date):
            lines.append(f'    "{cand.date_str}":')
            lines.append("      halves:")
            # Letters in acquisition order (DLC filenames sort by
            # timestamp; ws_dirs / cam_dirs sort by name which usually
            # matches but verify).
            letters = ["a", "b", "c", "d", "e"]
            ws_dirs = sorted(cand.ws_dirs)
            cam_dirs = sorted(cand.cam_dirs)
            dlc_files = sorted(cand.dlc_filenames)
            n_halves = max(len(ws_dirs), len(cam_dirs), len(dlc_files))
            for i in range(n_halves):
                letter = letters[i] if i < len(letters) else f"h{i}"
                ws_sd = ws_dirs[i] if i < len(ws_dirs) else "?"
                cam_sd = cam_dirs[i] if i < len(cam_dirs) else "?"
                ts = "?"
                if i < len(dlc_files):
                    fname = dlc_files[i]
                    if "T" in fname:
                        # Extract YYYY-MM-DDTHH_MM_SS
                        rest = fname.split("video2_", 1)[-1]
                        ts = rest.split("DLC", 1)[0] if "DLC" in rest else rest
                lines.append(f"        - id: {letter}")
                lines.append(f'          ws_subdir: "{ws_sd}"')
                lines.append(f'          cam_subdir: "{cam_sd}"')
                lines.append(f'          file_timestamp: "{ts}"')
            lines.append(
                '      reason: "auto-detected by scan_for_multi_half_candidates; '
                'review on-disk per-half subdirs before committing"'
            )
    return "\n".join(lines) + "\n"


def render_markdown_report(
    result: ScanResult,
    declared_keys: set[tuple[str, str]],
    *,
    n_sessions_scanned: int | None = None,
) -> str:
    """Render the cohort scan as Markdown.

    Includes a summary line, a Pattern-A-undeclared section (if any —
    these are the action-needed entries), then tables for each class.
    """
    if n_sessions_scanned is None:
        n_sessions_scanned = result.n_sessions_scanned

    pattern_a_declared = [
        c for c in result.pattern_a
        if (c.animal, c.date_str) in declared_keys
    ]
    pattern_a_undeclared = [
        c for c in result.pattern_a
        if (c.animal, c.date_str) not in declared_keys
    ]

    lines: list[str] = []
    lines.append(
        "# Multi-half candidate scan — productized "
        "(`scripts/phase_7_pre/scan_for_multi_half_candidates.py`)\n"
    )
    lines.append(
        f"Scanned **{n_sessions_scanned} sessions** across "
        f"{len({c.animal for c in result.all_candidates})} animals.\n"
    )
    lines.append(
        f"- **Pattern A** (n_dlc≥2; mergeable): "
        f"{len(result.pattern_a)} "
        f"({len(pattern_a_declared)} declared, "
        f"{len(pattern_a_undeclared)} undeclared)\n"
    )
    lines.append(
        f"- **Pattern B** (n_ws=2, n_cam=2, n_dlc<2; exploratory; half-a only): "
        f"{len(result.pattern_b)}\n"
    )
    lines.append(
        f"- **Weak** (exactly 1 signal): {len(result.weak)}\n"
    )
    lines.append("\n")

    # Pattern A undeclared = action needed
    if pattern_a_undeclared:
        lines.append("## ⚠ Pattern A undeclared (action required)\n")
        lines.append(
            "The following sessions show Pattern A on-disk signals "
            "(>=2 filtered DLC H5 files matching the date glob) but no "
            "`multi_half_sessions:` entry covers them. The pipeline raises "
            "`MultiHalfNotDeclaredError` on these sessions until they "
            "are declared.\n\n"
        )
        lines.append(_pattern_a_table(pattern_a_undeclared))
        lines.append("\n### Suggested YAML stub\n\n")
        lines.append("```yaml\n")
        lines.append(_format_yaml_stub_for_undeclared(pattern_a_undeclared))
        lines.append("```\n\n")
        lines.append(
            "Review the on-disk per-half subdirs before committing — the "
            "auto-detected `ws_subdir` / `cam_subdir` / `file_timestamp` "
            "values are best-effort.\n\n"
        )

    if pattern_a_declared:
        lines.append("## Pattern A declared\n\n")
        lines.append(
            "The following Pattern A sessions are covered by current "
            "`multi_half_sessions:` entries. The new pipeline merges them "
            "into parent-level outputs.\n\n"
        )
        lines.append(_pattern_a_table(pattern_a_declared))
        lines.append("\n")

    if result.pattern_b:
        lines.append("## Pattern B (exploratory; half-a only by design)\n\n")
        lines.append(
            "These sessions have multi-half WS + camera acquisition but "
            "DLC inference was run on only one half (the analyzed half — "
            "bare `{DATE}` WS subdir, or `a` for some PS55 sessions). "
            "Half-b is exploratory and silently discarded by design "
            "(verdict Decision 1). The existing single-half discovery "
            "path is correct for these.\n\n"
        )
        lines.append(_table_with_class(result.pattern_b))
        lines.append("\n")

    if result.weak:
        lines.append("## Weak candidates (1 signal)\n\n")
        lines.append(
            "Exactly one of {n_ws, n_dlc, n_cam} is ≥2 — usually a "
            "partial-acquisition or experimenter-restart corner case. "
            "Treat as needing manual review; the pipeline doesn't "
            "automatically multi-half-process these.\n\n"
        )
        lines.append(_table_with_class(result.weak))
        lines.append("\n")

    return "".join(lines)


def _pattern_a_table(cands: list[ScanCandidate]) -> str:
    lines: list[str] = []
    lines.append("| Animal | Date | n_ws | WS dirs | n_dlc | n_cam | Cam dirs |\n")
    lines.append("|---|---|---|---|---|---|---|\n")
    for c in cands:
        ws = ", ".join(f"`{x}`" for x in c.ws_dirs) or "—"
        cam = ", ".join(f"`{x}`" for x in c.cam_dirs) or "—"
        lines.append(
            f"| {c.animal} | {c.date_str} | {c.n_ws} | {ws} | "
            f"{c.n_dlc} | {c.n_cam} | {cam} |\n"
        )
    return "".join(lines)


def _table_with_class(cands: list[ScanCandidate]) -> str:
    """Same as _pattern_a_table but used for B / weak — same shape."""
    return _pattern_a_table(cands)


def _path_roots_from_resolver(resolver: PathResolver) -> tuple[Path, Path, Path]:
    """Resolve the three on-disk roots from a live :class:`PathResolver`.

    - ``ws_root`` — wavesurfer_raw (date-keyed top level).
    - ``dlc_root`` — microscope_server / DeepLabCut / O2_analysis (animal-
      keyed; per-animal dir contains flat filtered H5 files).
    - ``cam_root`` — camera_raw (date-keyed).
    """
    ws_root = Path(resolver.root("wavesurfer_raw"))
    dlc_root = Path(
        resolver.root("microscope_server") / "DeepLabCut" / "O2_analysis"
    )
    cam_root = Path(resolver.root("camera_raw"))
    return ws_root, dlc_root, cam_root


def main(argv: list[str] | None = None) -> int:
    """CLI entry. Returns exit code per the script's docstring."""
    parser = argparse.ArgumentParser(
        description="Productized cohort scan for multi-half acquisition candidates."
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT_PATH,
        help="Markdown report output path (default: %(default)s)",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress stdout summary (only write the markdown report).",
    )
    args = parser.parse_args(argv)

    try:
        animals = load_animals()
        overrides_config = load_session_overrides()
        resolver = PathResolver()
        ws_root, dlc_root, cam_root = _path_roots_from_resolver(resolver)
    except Exception as exc:
        print(f"ERROR: scan setup failed: {exc}", file=sys.stderr)
        return 2

    declared_keys = _yaml_declared_keys(overrides_config)

    try:
        result = scan_cohort(animals, ws_root, dlc_root, cam_root)
    except Exception as exc:
        print(f"ERROR: scan walk failed: {exc}", file=sys.stderr)
        return 2

    pattern_a_undeclared = [
        c for c in result.pattern_a
        if (c.animal, c.date_str) not in declared_keys
    ]

    # Markdown report
    report = render_markdown_report(result, declared_keys)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")

    # Stdout summary
    if not args.quiet:
        print(
            f"scan_for_multi_half_candidates: {result.n_sessions_scanned} sessions scanned\n"
            f"  Pattern A: {len(result.pattern_a)} "
            f"(declared={len(result.pattern_a) - len(pattern_a_undeclared)}, "
            f"undeclared={len(pattern_a_undeclared)})\n"
            f"  Pattern B: {len(result.pattern_b)} (exploratory; half-a only)\n"
            f"  Weak:      {len(result.weak)}\n"
            f"  Report:    {args.output}\n"
        )
        if pattern_a_undeclared:
            print(
                "Pattern A undeclared — copy the following YAML stub into "
                "configs/session_overrides.yaml after review:\n",
            )
            print(_format_yaml_stub_for_undeclared(pattern_a_undeclared))

    return 1 if pattern_a_undeclared else 0


if __name__ == "__main__":
    sys.exit(main())
