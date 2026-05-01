"""Path resolution: logical roots -> platform-specific mount points.

PathResolver loads configs/paths.yaml and maps logical root names
(e.g. 'microscope_server') to concrete filesystem paths based on the
current platform (Darwin/Windows) or the STROKE_PIPELINE_MACHINE env var.

Mount values in paths.yaml may be:
  - A single string path
  - A list of string paths (tried in order; first existing path wins)
  - null (not available on this platform)
"""

from __future__ import annotations

import datetime
import os
import platform
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    pass

# Map platform.system() values to the keys used in paths.yaml mounts
_PLATFORM_KEY = {
    "Darwin": "mac",
    "Windows": "windows",
}


def _default_config_path() -> Path:
    """Return the default path to configs/paths.yaml relative to this package."""
    return Path(__file__).resolve().parent.parent.parent / "configs" / "paths.yaml"


def _make_path(mount_str: str, platform_key: str) -> Path:
    """Convert a mount string to the appropriate Path type for the platform."""
    if platform_key == "windows":
        return PureWindowsPath(mount_str)  # type: ignore[return-value]
    return PurePosixPath(mount_str)  # type: ignore[return-value]


class PathResolver:
    """Resolves logical path roots from configs/paths.yaml to concrete paths.

    Parameters
    ----------
    config_path : Path or str, optional
        Path to the paths.yaml config file. Defaults to ``configs/paths.yaml``
        at the repo root.
    output_root : Path or str, optional
        If provided, overrides the ``microscope_pipeline_outputs`` logical
        root that backs ``pipeline_outputs()``. All OTHER logical roots
        (wavesurfer_raw, camera_raw, microscope_server, etc.) continue to
        resolve from the real config unchanged. Primarily a test-fixture
        hook — production callers should leave this ``None`` so the real
        config-driven default stands (task #20). When omitted, behavior
        is byte-identical to the pre-task-#20 code path.

    Attributes
    ----------
    platform_key : str
        The platform key used for resolution ('mac' or 'windows').
    """

    def __init__(
        self,
        config_path: Path | str | None = None,
        *,
        output_root: Path | str | None = None,
    ) -> None:
        if config_path is None:
            config_path = _default_config_path()
        config_path = Path(config_path)

        with open(config_path) as f:
            self._config = yaml.safe_load(f)

        self._output_root_override: Path | None = (
            Path(output_root) if output_root is not None else None
        )

        # Determine platform key: env var override or auto-detect
        env_override = os.environ.get("STROKE_PIPELINE_MACHINE")
        if env_override:
            if env_override not in ("mac", "windows"):
                raise ValueError(
                    f"STROKE_PIPELINE_MACHINE must be 'mac' or 'windows', got '{env_override}'"
                )
            self.platform_key = env_override
        else:
            system = platform.system()
            if system not in _PLATFORM_KEY:
                raise RuntimeError(
                    f"Unsupported platform '{system}'. Set STROKE_PIPELINE_MACHINE='mac' or "
                    f"'windows' to override."
                )
            self.platform_key = _PLATFORM_KEY[system]

        # Resolve logical roots to concrete Path objects.
        # Mount values may be a string, a list of strings, or null.
        # For lists, we store all candidates and resolve at lookup time.
        self._roots: dict[str, Path | None] = {}
        self._root_candidates: dict[str, list[Path]] = {}
        for name, spec in self._config.get("logical_roots", {}).items():
            mount = spec.get("mounts", {}).get(self.platform_key)
            if mount is None:
                self._roots[name] = None
                self._root_candidates[name] = []
            elif isinstance(mount, list):
                # List of fallback paths — resolved lazily in root()
                self._roots[name] = None  # sentinel; resolved on first access
                self._root_candidates[name] = [
                    _make_path(m, self.platform_key) for m in mount
                ]
            else:
                path = _make_path(mount, self.platform_key)
                self._roots[name] = Path(path)
                self._root_candidates[name] = [path]

    def root(self, name: str) -> Path:
        """Return the resolved root path for a logical name.

        For single-path mounts, returns the configured path directly (no
        existence check — caller is responsible).

        For list mounts (fallback chains), tries each path in order and
        returns the first that exists on disk. Raises FileNotFoundError
        if none exist.

        Raises
        ------
        KeyError
            If the logical root name is not defined in paths.yaml.
        RuntimeError
            If the logical root has no mount for the current platform.
        FileNotFoundError
            If the mount is a list and none of the candidates exist.
        """
        if name not in self._root_candidates:
            raise KeyError(
                f"Unknown logical root '{name}'. "
                f"Available: {list(self._root_candidates.keys())}"
            )

        candidates = self._root_candidates[name]
        if not candidates:
            raise RuntimeError(
                f"Logical root '{name}' has no mount defined for platform '{self.platform_key}'."
            )

        # Single-path mount: return directly (backward compatible, no existence check)
        if len(candidates) == 1:
            return Path(candidates[0])

        # List mount: try each in order, return first existing
        for candidate in candidates:
            p = Path(candidate)
            if p.exists():
                return p

        paths_str = "\n  ".join(str(c) for c in candidates)
        raise FileNotFoundError(
            f"Raw data for '{name}' not found at any of:\n  {paths_str}\n"
            f"On Windows, ensure the data has been mirrored to MICROSCOPE."
        )

    # ---- Convenience methods ----

    def dlc_output_dir(self, animal: str) -> Path:
        """Return the DLC output directory for an animal.

        E.g. ``/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/O2_analysis/PS46``
        """
        return self.root("microscope_server") / "DeepLabCut" / "O2_analysis" / animal

    def alignment_templates_dir(self, cam: str = "cam2") -> Path:
        """Return the alignment templates directory for a camera.

        E.g. ``/Volumes/.../alignment_templates/cam2``
        """
        return (
            self.root("microscope_server")
            / "DeepLabCut"
            / "O2_analysis"
            / "alignment_templates"
            / cam
        )

    def alignment_template(
        self, animal: str, date: datetime.date, cam: str = "cam2"
    ) -> Path:
        """Return the path to a specific alignment template .npz file.

        E.g. ``/Volumes/.../alignment_templates/cam2/PS46/20250307.npz``
        """
        date_str = date.strftime("%Y%m%d")
        return self.alignment_templates_dir(cam) / animal / f"{date_str}.npz"

    def pipeline_outputs(self, subdir: str = "spout_behavior") -> Path:
        """Return the output directory for pipeline outputs on MICROSCOPE.

        E.g. ``/Volumes/.../stroke_orofacial_pipeline_outputs/spout_behavior``

        If the resolver was constructed with ``output_root=<path>`` (test
        hook — task #20), returns ``<path>/<subdir>`` instead. All other
        methods are unaffected by the override.
        """
        if self._output_root_override is not None:
            return self._output_root_override / subdir
        return self.root("microscope_pipeline_outputs") / subdir

    def interpolated_trace(
        self,
        bodypart: str,
        animal: str,
        date: datetime.date,
        *,
        variant: str = "parquet",
    ) -> Path:
        """Return the output path for a Phase 7a interpolated-trace artifact.

        E.g. ``<outputs>/dlc_analysis/interpolated_traces/tongue/PS46/20250307.parquet``

        Parameters
        ----------
        bodypart : {"tongue", "jaw"}
        animal : str
            Animal identifier (e.g. "PS46").
        date : datetime.date
        variant : {"parquet", "qc_npz"}
            ``"parquet"`` → canonical output (always emitted by
            :func:`stroke_orofacial.dlc_kinematics.build_interpolated_trace`).
            ``"qc_npz"`` → optional QC sidecar (emitted when
            ``emit_qc_bundle=True`` is passed to the builder).

        Parent directory is created eagerly. Mirrors
        :meth:`pipeline_outputs`'s ``output_root`` test-override behavior
        via the same ``_output_root_override`` hook.
        """
        date_str = date.strftime("%Y%m%d")
        ext = {"parquet": "parquet", "qc_npz": "qc.npz"}[variant]
        out = (
            self.pipeline_outputs(subdir="dlc_analysis")
            / "interpolated_traces"
            / bodypart
            / animal
            / f"{date_str}.{ext}"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    def tongue_pertrial_angle_parquet(
        self, animal: str, date: datetime.date,
    ) -> Path:
        """Return the Phase 7a.3 per-frame tongue-angle parquet path.

        E.g. ``<outputs>/dlc_kinematics/features/tongue/PS50/20250319.parquet``.

        Output filename uses ``%Y%m%d`` to match the existing 7a.2
        :meth:`interpolated_trace` convention. Mirrors :meth:`pipeline_outputs`'s
        ``output_root`` test-override behavior via ``_output_root_override``.
        Parent directory is created eagerly.
        """
        date_str = date.strftime("%Y%m%d")
        out = (
            self.pipeline_outputs(subdir="dlc_kinematics")
            / "features"
            / "tongue"
            / animal
            / f"{date_str}.parquet"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    def tongue_pertrial_licking_dynamics_traces_parquet(
        self, animal: str, date: datetime.date,
    ) -> Path:
        """Return the Phase 7a.3 per-session × side licking-dynamics traces parquet.

        E.g. ``<outputs>/dlc_kinematics/licking_dynamics/traces/PS46/20250501.parquet``.

        Output filename uses ``%Y%m%d`` to match
        :meth:`interpolated_trace`'s convention. Parent directory is created
        eagerly.
        """
        date_str = date.strftime("%Y%m%d")
        out = (
            self.pipeline_outputs(subdir="dlc_kinematics")
            / "licking_dynamics"
            / "traces"
            / animal
            / f"{date_str}.parquet"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    def tongue_pertrial_endpoints_json(
        self, animal: str, date: datetime.date,
    ) -> Path:
        """Return the Phase 7a.3 per-trial endpoints JSON path.

        E.g. ``<outputs>/dlc_kinematics/endpoints/PS54/20250607.json``.

        Output filename uses ``%Y%m%d`` to match
        :meth:`interpolated_trace`'s convention. Parent directory is created
        eagerly.
        """
        date_str = date.strftime("%Y%m%d")
        out = (
            self.pipeline_outputs(subdir="dlc_kinematics")
            / "endpoints"
            / animal
            / f"{date_str}.json"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    def tongue_pertrial_licking_dynamics_day_binned_parquet(
        self, animal: str, rel_day_bin_label: str,
    ) -> Path:
        """Return the Phase 7a.4 day-binned cross-session traces parquet path.

        E.g. ``<outputs>/dlc_kinematics/licking_dynamics/day_binned/PS54/1..7.parquet``.

        ``rel_day_bin_label`` follows the legacy convention ``f"{lo}..{hi}"``
        (e.g. ``"-1..0"``, ``"1..2"``, ``"-6..0"``, ``"1..7"``) emitted by
        the day-binner — bit-identical to legacy CSV labels for traceability.
        Literal ``..`` is NTFS-legal and preserved deliberately. Parent
        directory is created eagerly.
        """
        out = (
            self.pipeline_outputs(subdir="dlc_kinematics")
            / "licking_dynamics"
            / "day_binned"
            / animal
            / f"{rel_day_bin_label}.parquet"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    def tongue_visual_qc_dir(
        self, animal: str, date: datetime.date,
    ) -> Path:
        """Return the Phase 7a.4 tongue visual-gate QC PNG output directory.

        E.g. ``<outputs>/dlc_kinematics/figures_qc/tongue/PS50/20250319/``.

        Hosts the 6 PNGs emitted per session by
        :func:`stroke_orofacial.dlc_kinematics.tongue_visual.render_tongue_qc_figures`
        (Family 1 = 2 PNGs per side; Families 2-5 = 1 PNG each). The
        renderer creates the directory; this resolver returns the path
        only — no eager mkdir.
        """
        date_str = date.strftime("%Y%m%d")
        return (
            self.pipeline_outputs(subdir="dlc_kinematics")
            / "figures_qc"
            / "tongue"
            / animal
            / date_str
        )

    def tongue_visual_comparison_dir(
        self, animal: str, date: datetime.date,
    ) -> Path:
        """Return the Phase 7a.4 tongue visual-gate comparison-grid output directory.

        E.g. ``<outputs>/dlc_kinematics/figures_qc/tongue_comparison/PS46/20250307/``.

        Hosts the legacy-vs-consolidated side-by-side PNGs emitted per
        session by
        :func:`stroke_orofacial.dlc_kinematics.tongue_visual.render_comparison_grid`
        for the visual-gate parity runner. The renderer creates the
        directory; this resolver returns the path only — no eager mkdir.
        """
        date_str = date.strftime("%Y%m%d")
        return (
            self.pipeline_outputs(subdir="dlc_kinematics")
            / "figures_qc"
            / "tongue_comparison"
            / animal
            / date_str
        )

    def dlc_centered_spout_midpoint_parquet(
        self, animal: str, date: datetime.date,
    ) -> Path:
        """Resolve the consolidated centered_spout_midpoint parquet for one
        ``(animal, date)``.

        E.g. ``<outputs>/dlc_analysis/centered_spout_midpoint/PS50/
        video2_2025-03-19T16_18_28DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5.intermediate.2a6efb6a.parquet``.

        The upstream filename embeds a session-start timestamp + DLC model
        name + param-signature hash, so the date alone does not uniquely
        identify the file. This resolver globs ``video2_{YYYY-MM-DD}T*.parquet``
        under
        ``pipeline_outputs("dlc_analysis") / "centered_spout_midpoint" / animal``
        and returns the unique match.

        Date is formatted with :meth:`datetime.date.isoformat` (``YYYY-MM-DD``,
        with hyphens) to match the upstream filename convention — this is
        intentionally different from :meth:`interpolated_trace`'s ``%Y%m%d``
        OUTPUT convention.

        Caller invariant: the centered_spout_midpoint tree should have exactly
        one parquet per session per animal in the current cohort
        (Task 1.5 verified 14/15 in-scope sessions match this invariant; the
        one missing is PS54/2025-05-12, a known data gap inheriting the
        7a.1/7a.2 ``skip_missing`` pattern).

        Raises
        ------
        FileNotFoundError
            If zero parquets match the glob pattern.
        RuntimeError
            If multiple parquets match (signals an upstream re-emit produced
            two param-sig versions; downstream loaders should not silently
            guess which to use).
        """
        candidate_dir = (
            self.pipeline_outputs(subdir="dlc_analysis")
            / "centered_spout_midpoint"
            / animal
        )
        # NB: isoformat = YYYY-MM-DD with hyphens, matches upstream filename.
        pattern = f"video2_{date.isoformat()}T*.parquet"
        matches = sorted(candidate_dir.glob(pattern))
        if not matches:
            raise FileNotFoundError(
                f"No centered_spout_midpoint parquet for {animal}/{date.isoformat()} "
                f"(searched {pattern!r} in {candidate_dir})"
            )
        if len(matches) > 1:
            raise RuntimeError(
                f"Multiple centered_spout_midpoint parquets for "
                f"{animal}/{date.isoformat()}: {[m.name for m in matches]}"
            )
        return matches[0]

    def wavesurfer_dir(self, date: datetime.date, animal: str) -> Path:
        """Return the wavesurfer session directory for an animal and date.

        E.g. ``/Volumes/.../wavesurfer/20250307/PS46``
        """
        date_str = date.strftime("%Y%m%d")
        return self.root("wavesurfer_raw") / date_str / animal

    def camera_dir(self, date: datetime.date, animal: str) -> Path:
        """Return the camera session directory for an animal and date.

        E.g. ``/Volumes/.../camera/20250307/PS46``
        """
        date_str = date.strftime("%Y%m%d")
        return self.root("camera_raw") / date_str / animal

    # Kept for backward compatibility but deprecated in favor of pipeline_outputs()
    def session_processing_out(self, version: str = "v2") -> Path:
        """Return the output directory for processed session data (deprecated).

        Use ``pipeline_outputs(subdir='spout_behavior')`` instead.
        """
        return self.root("local_processed_spout") / f"session_processing_{version}"
