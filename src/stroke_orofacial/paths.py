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

    def alignment_template_legacy_read(
        self,
        animal: str,
        date: datetime.date,
        cam: str = "cam2",
        *,
        session_suffix: str | None = None,
    ) -> Path:
        """Read-only path for existing legacy alignment templates.

        E.g. ``/Volumes/.../DeepLabCut/O2_analysis/alignment_templates/cam2/PS46/20250307.npz``

        Routes through ``microscope_server`` (the live MICROSCOPE share)
        where legacy templates were produced by Priya's canonical
        ``make_alignment_templates_20251216.py`` and the multi-half
        merge cell 16. Production code uses this path to **discover
        existing templates only** — never to write.

        Phase 7-pre-multi-half 2026-05-05 incident response: this
        method was renamed from ``alignment_template`` so call sites
        that wrote via this resolver (e.g. the multi-half compute-and-
        merge orchestrator) get a clear "this is for legacy reads
        only" signal at the API surface. New-pipeline writes go via
        :meth:`alignment_template_new` (single merged) or
        :meth:`alignment_template_per_half_new` (per-half multi-half
        output), both of which route through ``pipeline_outputs/`` and
        honor the ``output_root`` test override.

        Parameters
        ----------
        animal : str
            Animal identifier (e.g. ``"PS46"``).
        date : datetime.date
            Session date.
        cam : str
            Camera token (default ``"cam2"`` matching DLC camera).
        session_suffix : str, optional
            Phase 7-pre-secondary-spout — Pattern B session suffix.
            When set, appended to ``date_str`` so per-session output
            filename is ``{date_str}{session_suffix}.npz`` (e.g.
            ``20250430b.npz``). ``None`` preserves pre-PR behavior.
        """
        date_str = date.strftime("%Y%m%d") + (session_suffix or "")
        return self.alignment_templates_dir(cam) / animal / f"{date_str}.npz"

    def alignment_template_new(
        self,
        animal: str,
        date: datetime.date,
        cam: str = "cam2",
        *,
        session_suffix: str | None = None,
    ) -> Path:
        """Write path for new-pipeline merged alignment templates.

        E.g. ``<microscope_pipeline_outputs>/dlc_analysis/alignment_templates/cam2/PS48/20250314.npz``

        Routes through :meth:`pipeline_outputs` so ``output_root``
        kwarg at PathResolver construction time redirects writes to a
        test-sandbox location. Production callers (the multi-half
        compute-and-merge orchestrator) write merged templates here
        instead of overwriting the live legacy tree.

        Mirrors the legacy parent-level layout (``cam2/{ANIMAL}/{date_str}.npz``)
        so a downstream consumer can rebuild against the new tree
        without changing logic — only the root differs. Per-half
        templates emitted alongside live in
        :meth:`alignment_template_per_half_new`.

        Phase 7-pre-multi-half 2026-05-05 incident response: this
        method was added so multi-half writes have a structurally
        safe destination under ``pipeline_outputs/``. The previous
        write path (``alignment_template`` routing through
        ``microscope_server``) corrupted 3 legacy NPZs; see the
        incident report in DECISIONS / COWORK_SESSION_STATE.

        Phase 7-pre-secondary-spout: ``session_suffix`` (kwarg) appends
        to ``date_str`` so b-half outputs land at
        ``...{ANIMAL}/{date_str}b.npz``. ``None`` preserves pre-PR
        behavior.
        """
        date_str = date.strftime("%Y%m%d") + (session_suffix or "")
        return (
            self.pipeline_outputs(subdir="dlc_analysis")
            / "alignment_templates"
            / cam
            / animal
            / f"{date_str}.npz"
        )

    def alignment_template_per_half_new(
        self,
        animal: str,
        date: datetime.date,
        *,
        halves_concat_label: str,
        half_id: str,
        cam: str = "cam2",
    ) -> Path:
        """Write path for new-pipeline per-half alignment templates.

        E.g. ``<microscope_pipeline_outputs>/dlc_analysis/alignment_templates/cam2/PS48/20250314ab/20250314a.npz``
        for PS48 20250314 half a (``halves_concat_label="ab"``).

        Routes through :meth:`pipeline_outputs` (under the
        ``dlc_analysis`` subdir) so ``output_root`` test overrides
        redirect cleanly. Phase 7-pre-multi-half 2026-05-05 incident
        response: this is the **safe** counterpart to the old
        ``alignment_template_per_half`` resolver, which routed
        through ``microscope_server`` and corrupted 3 legacy NPZs.

        Mirrors the on-disk convention Priya established for PS48
        20250314 (post-merge cleanup, 2026-05-05) and locked as
        Decision 3 of the Phase 7-pre-multi-half Task 1 verdict:
        per-half artefacts go in a per-(animal, date) subdir named
        ``{date_str}{halves_concat_label}``; the merged template
        lives at the parent level (:meth:`alignment_template_new`).

        Parameters
        ----------
        animal : str
            Animal identifier (e.g. ``"PS48"``).
        date : datetime.date
            Session date.
        halves_concat_label : str
            Per-(animal, date) subdir-name suffix — concatenated half
            ids (e.g. ``"ab"`` for halves ``a`` + ``b``).
        half_id : str
            Half identifier letter (``"a"``, ``"b"``, ...).
        cam : str
            Camera token (default ``"cam2"`` matching DLC camera).

        Phase 7-pre-secondary-spout: this resolver is **Pattern A
        multi-half-only** by design — Pattern B sessions never use it
        (their bare/b halves are separate sessions, not merge halves).
        Intentionally NOT extended with a ``session_suffix`` kwarg;
        mixing Pattern A's ``halves_concat_label`` / ``half_id`` with
        Pattern B's ``session_suffix`` at the same call site is a
        category error.
        """
        date_str = date.strftime("%Y%m%d")  # Pattern A multi-half base
        subdir_name = f"{date_str}{halves_concat_label}"
        file_name = f"{date_str}{half_id}.npz"
        return (
            self.pipeline_outputs(subdir="dlc_analysis")
            / "alignment_templates"
            / cam
            / animal
            / subdir_name
            / file_name
        )

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
        session_suffix: str | None = None,
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
        date_str = date.strftime("%Y%m%d") + (session_suffix or "")
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
        *, session_suffix: str | None = None,
    ) -> Path:
        """Return the Phase 7a.3 per-frame tongue-angle parquet path.

        E.g. ``<outputs>/dlc_kinematics/features/tongue/PS50/20250319.parquet``.

        Output filename uses ``%Y%m%d`` to match the existing 7a.2
        :meth:`interpolated_trace` convention. Mirrors :meth:`pipeline_outputs`'s
        ``output_root`` test-override behavior via ``_output_root_override``.
        Parent directory is created eagerly.
        """
        date_str = date.strftime("%Y%m%d") + (session_suffix or "")
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
        *, session_suffix: str | None = None,
    ) -> Path:
        """Return the Phase 7a.3 per-session × side licking-dynamics traces parquet.

        E.g. ``<outputs>/dlc_kinematics/licking_dynamics/traces/PS46/20250501.parquet``.

        Output filename uses ``%Y%m%d`` to match
        :meth:`interpolated_trace`'s convention. Parent directory is created
        eagerly.
        """
        date_str = date.strftime("%Y%m%d") + (session_suffix or "")
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
        *, session_suffix: str | None = None,
    ) -> Path:
        """Return the Phase 7a.3 per-trial endpoints JSON path.

        E.g. ``<outputs>/dlc_kinematics/endpoints/PS54/20250607.json``.

        Output filename uses ``%Y%m%d`` to match
        :meth:`interpolated_trace`'s convention. Parent directory is created
        eagerly.
        """
        date_str = date.strftime("%Y%m%d") + (session_suffix or "")
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

    def tongue_angle_within_session_dir(
        self, animal: str, date: datetime.date,
        *, session_suffix: str | None = None,
    ) -> Path:
        """Return the Phase 7a.4 tongue angle/phase per-session figure
        output directory.

        E.g. ``<outputs>/dlc_kinematics/tongue_angle/within_session/PS50/20250319/``.

        Hosts the 9 PNGs emitted per session by
        :func:`stroke_orofacial.dlc_kinematics.tongue_visual.render_tongue_qc_figures`
        (qc_trials × 2 sides + first_peak_aligned + reward_aligned + 3
        phase_aligned_angle variants + first_vs_second_peak_scatter +
        xy_by_phase). The renderer creates the directory; this
        resolver returns the path only — no eager mkdir.

        **Naming history:**
          - Pre-7a.4-paths-cleanup: ``tongue_visual_qc_dir`` writing to
            ``dlc_kinematics/figures_qc/tongue/...``.
          - 7a.4-paths-cleanup (2026-05-03): renamed to ``tongue_angle_dir``
            at ``dlc_kinematics/tongue_angle/{animal}/{date}/``.
          - Phase 7a.4-cross-session-angle Addendum #17 (2026-05-04):
            renamed to ``tongue_angle_within_session_dir`` and moved to
            ``dlc_kinematics/tongue_angle/within_session/{animal}/{date}/``
            for symmetry with the cross-session sibling
            (:meth:`tongue_angle_cross_session_dir`) and the
            tongue_jaw_mismatch ``within_session/`` + ``cross_session/``
            layout (locked Phase 7a.4-paths-cleanup).
        """
        date_str = date.strftime("%Y%m%d") + (session_suffix or "")
        return (
            self.pipeline_outputs(subdir="dlc_kinematics")
            / "tongue_angle"
            / "within_session"
            / animal
            / date_str
        )

    def jaw_pertrial_endpoints_json(
        self, animal: str, date: datetime.date,
        *, session_suffix: str | None = None,
    ) -> Path:
        """Return the Phase 7a.5 per-trial jaw scalars JSON path.

        E.g. ``<outputs>/dlc_kinematics/jaw_pertrial/endpoints/PS46/20250307.json``.

        Hosts the per-trial jaw baseline / deflection / QC scalars produced
        by :func:`stroke_orofacial.dlc_kinematics.jaw_pertrial.build_jaw_pertrial`
        (extracted from canonical tongue notebook Cell 53 inline-detection
        logic). Filename uses ``%Y%m%d`` to match the
        :meth:`interpolated_trace` / :meth:`tongue_pertrial_endpoints_json`
        conventions. Parent directory is created eagerly.
        """
        date_str = date.strftime("%Y%m%d") + (session_suffix or "")
        out = (
            self.pipeline_outputs(subdir="dlc_kinematics")
            / "jaw_pertrial"
            / "endpoints"
            / animal
            / f"{date_str}.json"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    def tongue_jaw_mismatch_candidate_trials_parquet(
        self, animal: str, date: datetime.date,
        *, session_suffix: str | None = None,
    ) -> Path:
        """Return the Phase 7a.5 per-session tongue-jaw mismatch candidate-trials parquet.

        E.g. ``<outputs>/dlc_kinematics/tongue_jaw_mismatch/candidate_trials/PS46/20250307.parquet``.

        Hosts the per-trial classifier output (legacy 37-col schema; per-
        session cadence rather than the legacy per-mouse aggregated CSV)
        emitted by
        :func:`stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch.classify_tongue_jaw_mismatch`.
        Filename uses ``%Y%m%d``. Parent directory is created eagerly.
        """
        date_str = date.strftime("%Y%m%d") + (session_suffix or "")
        out = (
            self.pipeline_outputs(subdir="dlc_kinematics")
            / "tongue_jaw_mismatch"
            / "candidate_trials"
            / animal
            / f"{date_str}.parquet"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    def tongue_jaw_mismatch_within_session_dir(
        self, animal: str, date: datetime.date,
        *, session_suffix: str | None = None,
    ) -> Path:
        """Return the Phase 7a.5 mismatch within-session figure output directory.

        E.g. ``<outputs>/dlc_kinematics/tongue_jaw_mismatch/within_session/PS46/20250307/``.

        Hosts the within-session PNGs (Cell 55 individualTrials2col +
        sessionOverlayGrid4x2 families) emitted per session by
        :func:`stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch.render_within_session_figures`.
        The renderer creates the directory; this resolver returns the path
        only — no eager mkdir (matches the 7a.4
        :meth:`tongue_angle_dir` directory-resolver convention).

        **Naming history:** Previously ``tongue_jaw_mismatch_qc_dir``
        writing to ``tongue_jaw_mismatch/figures_qc/...``; renamed in
        Phase 7a.4-orientation-and-paths-cleanup (2026-05-03) for
        symmetry with the existing ``cross_session/`` sibling and to
        drop the "qc" suffix consistently with the broader figures_qc/
        cleanup. (Note: the per-trial scientific field
        ``jaw_pass_qc`` is unaffected — that's domain vocabulary, not
        a directory name.)
        """
        date_str = date.strftime("%Y%m%d") + (session_suffix or "")
        return (
            self.pipeline_outputs(subdir="dlc_kinematics")
            / "tongue_jaw_mismatch"
            / "within_session"
            / animal
            / date_str
        )

    def tongue_jaw_mismatch_cross_session_dir(self, animal: str) -> Path:
        """Return the Phase 7a.5 mismatch cross-session figure output directory.

        E.g. ``<outputs>/dlc_kinematics/tongue_jaw_mismatch/cross_session/PS46/``.

        Hosts the cross-session PNGs (Cell 55 crossSessionOverlay2x2 +
        crossSessionBinned2x2 families) emitted per mouse by
        :func:`stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch.render_cross_session_figures`.
        Per-mouse (no date dimension) — matches the legacy
        ``{mouse}_crossSession*.png`` cadence. The renderer creates the
        directory; this resolver returns the path only — no eager mkdir.
        """
        return (
            self.pipeline_outputs(subdir="dlc_kinematics")
            / "tongue_jaw_mismatch"
            / "cross_session"
            / animal
        )

    def tongue_angle_cross_session_dir(self, animal: str) -> Path:
        """Return the Phase 7a.4-cross-session-angle per-mouse cohort
        figure output directory.

        E.g. ``<outputs>/dlc_kinematics/tongue_angle/cross_session/PS46/``.

        Hosts the 12 cross-session PNGs emitted per mouse by
        :func:`stroke_orofacial.dlc_kinematics.tongue_angle_cohort.build_tongue_angle_cohort`:

          - 6 plot families
            (``first_peak_aligned``, ``reward_aligned``,
            ``phase_aligned_angle_1st_lick``,
            ``phase_aligned_angle_all_licks``,
            ``phase_aligned_angle_first_2_licks``,
            ``first_vs_second_peak_scatter``)
          - 2 sub-variants per family (``session_overlays``,
            ``binned_overlays``)

        Filename pattern: ``{animal}_{family}_{sub_variant}.png``.
        Per-mouse (no date dimension); mirrors the
        :meth:`tongue_jaw_mismatch_cross_session_dir` resolver
        convention. The renderer creates the directory; this resolver
        returns the path only — no eager mkdir.

        **Naming history:** Phase 7a.4-cross-session-angle initial
        commits (2026-05-04) used ``tongue_angle_cohort_dir`` →
        ``dlc_kinematics/tongue_angle_cohort/{animal}/``. Renamed by
        Phase 7a.4-cross-session-angle Addendum #17 item 5
        (2026-05-04) to ``tongue_angle_cross_session_dir`` →
        ``dlc_kinematics/tongue_angle/cross_session/{animal}/`` for
        symmetry with the per-session
        :meth:`tongue_angle_within_session_dir` sibling and the
        tongue_jaw_mismatch ``within_session/`` + ``cross_session/``
        layout.
        """
        return (
            self.pipeline_outputs(subdir="dlc_kinematics")
            / "tongue_angle"
            / "cross_session"
            / animal
        )

    def mean_sem_visual_dir(
        self,
        bodypart: str,
        *,
        center_mode: str,
        reward_pre_ms: int,
        reward_post_ms: int,
        plot_family: str,
        animal: str,
    ) -> Path:
        """Return the Phase 7a.6 mean/SEM visual gate output directory.

        E.g. ``<outputs>/dlc_kinematics/mean_sem/tongue/centered_spout_midpoint/
        rewardAligned_100pre-1000post/individual_sessions/PS46/``.

        Parameters
        ----------
        bodypart : {"tongue", "jaw"}
            Bodypart token. Used as a literal subdir name; lowercase per
            Phase 7a.6 Q6 (the consolidated tree does not replicate the
            legacy capital-T bug seen in ``mouse_Tongue_kinematics`` paths
            that tongue Cell 31 wrote to alongside the lowercase
            ``mouse_tongue_kinematics``).
        center_mode : str
            Legacy center-mode token (e.g. ``"centered_spout_midpoint"``
            for tongue, ``"centered_eye_midpoint"`` for jaw). Sourced
            from ``mean_sem_visual.{bodypart}.center_mode`` in
            ``configs/defaults.yaml``.
        reward_pre_ms, reward_post_ms : int
            Reward-aligned window endpoints in **milliseconds**. The
            subdir name is composed as
            ``f"rewardAligned_{reward_pre_ms}pre-{reward_post_ms}post"``,
            matching the legacy jaw subdir convention. Q7 (locked
            2026-05-01): this per-window subdir layout is adopted
            uniformly for both bodyparts. Tongue's legacy flat-layout
            outputs (no per-window scoping) are NOT replicated.
        plot_family : str
            One of ``"individual_sessions"``, ``"trial_overlays"``,
            ``"session_overlays"``, ``"binned_overlays"`` (master cell
            families) or ``"mean_xy_overlays"`` (mean-trace + mean-video
            shared subdir). Passed verbatim as a directory name; the
            resolver does not validate the value.
        animal : str
            Animal identifier (e.g. ``"PS46"``).

        Returns
        -------
        Path
            Directory path. No eager mkdir — matches the
            :meth:`tongue_visual_qc_dir` /
            :meth:`tongue_jaw_mismatch_qc_dir` directory-resolver
            convention; the renderer creates the directory.

        Notes
        -----
        Deviation from the Phase 7a.6 kickoff template, which sketched
        ``reward_pre_s: float`` (seconds, with example ``(2.0, 5.0) →
        rewardAligned_2-5``). The legacy filename and directory
        convention is millisecond-based (``rewardAligned_100pre-1000post/``),
        and the master cell's ``TIME_WINDOWS_MS`` is also milliseconds
        — using milliseconds here keeps the consolidated subdir names
        bit-comparable with legacy outputs in the visual gate. Documented
        in the Phase 7a.6 commit message.
        """
        window_dir = (
            f"rewardAligned_{reward_pre_ms}pre-{reward_post_ms}post"
        )
        return (
            self.pipeline_outputs(subdir="dlc_kinematics")
            / "mean_sem"
            / bodypart
            / center_mode
            / window_dir
            / plot_family
            / animal
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

    def wavesurfer_dir(
        self,
        date: datetime.date,
        animal: str,
        *,
        half_subdir: str | None = None,
        subdir_override: str | None = None,
    ) -> Path:
        """Return the wavesurfer session directory for an animal and date.

        E.g. ``/Volumes/.../wavesurfer/20250307/PS46``.

        Parameters
        ----------
        date : datetime.date
            Session date.
        animal : str
            Animal identifier (e.g. ``"PS46"``).
        half_subdir : str, optional
            Per-half subdirectory name (e.g. ``"20250314a"``) for
            multi-half sessions (Phase 7-pre-multi-half). When provided,
            replaces the default ``date_str`` segment so the resolved
            path becomes ``{ws_root}/{half_subdir}/{ANIMAL}/``. Default
            ``None`` preserves the single-half behavior. The Pattern A
            multi-half on-disk layout for PS48 20250314 has WS files
            under ``{ws_root}/20250314a/PS48/`` and ``{ws_root}/20250314b/PS48/``;
            single-half discovery (default) cannot reach those. The
            ``HalfSpec.ws_subdir`` field on
            :class:`stroke_orofacial.manifest.SessionManifest` carries
            the per-half value to pass here.
        subdir_override : str, optional
            Pattern B secondary-spout override (Phase 7-pre-secondary-spout).
            Same semantic effect as ``half_subdir`` (replaces the
            ``date_str`` segment with the supplied dirname), kept as a
            separate kwarg so caller-side intent is documented: callers
            building Pattern A per-half paths pass ``half_subdir``;
            callers building Pattern B bare/b-half paths pass
            ``subdir_override``. Mutually exclusive — passing both
            raises ``ValueError`` because the two intents shouldn't mix
            at the same call site.
        """
        if half_subdir is not None and subdir_override is not None:
            raise ValueError(
                "wavesurfer_dir: half_subdir and subdir_override are "
                "mutually exclusive (Pattern A vs Pattern B intents)"
            )
        explicit = half_subdir if half_subdir is not None else subdir_override
        subdir = explicit if explicit is not None else date.strftime("%Y%m%d")
        return self.root("wavesurfer_raw") / subdir / animal

    def camera_dir(
        self,
        date: datetime.date,
        animal: str,
        *,
        half_subdir: str | None = None,
        subdir_override: str | None = None,
    ) -> Path:
        """Return the camera session directory for an animal and date.

        E.g. ``/Volumes/.../camera/20250307/PS46``.

        Parameters
        ----------
        date : datetime.date
            Session date.
        animal : str
            Animal identifier (e.g. ``"PS46"``).
        half_subdir : str, optional
            Per-half subdirectory name (e.g. ``"20250314a"``) for
            multi-half sessions. Same semantics as
            :meth:`wavesurfer_dir.half_subdir`: replaces the default
            ``date_str`` segment so the resolved path becomes
            ``{cam_root}/{half_subdir}/{ANIMAL}/``. Pattern A multi-half
            (PS48 20250314) has camera files at ``{cam_root}/20250314a/PS48/``
            and ``{cam_root}/20250314b/PS48/``. The ``HalfSpec.cam_subdir``
            field on :class:`stroke_orofacial.manifest.SessionManifest`
            carries the per-half value to pass here.
        subdir_override : str, optional
            Pattern B secondary-spout override (Phase 7-pre-secondary-spout).
            Same semantic effect as ``half_subdir``; documented separately
            so caller-side intent is unambiguous. Mutually exclusive
            with ``half_subdir`` — passing both raises ``ValueError``.
        """
        if half_subdir is not None and subdir_override is not None:
            raise ValueError(
                "camera_dir: half_subdir and subdir_override are "
                "mutually exclusive (Pattern A vs Pattern B intents)"
            )
        explicit = half_subdir if half_subdir is not None else subdir_override
        subdir = explicit if explicit is not None else date.strftime("%Y%m%d")
        return self.root("camera_raw") / subdir / animal

    # Kept for backward compatibility but deprecated in favor of pipeline_outputs()
    def session_processing_out(self, version: str = "v2") -> Path:
        """Return the output directory for processed session data (deprecated).

        Use ``pipeline_outputs(subdir='spout_behavior')`` instead.
        """
        return self.root("local_processed_spout") / f"session_processing_{version}"

    def spout_behavior_figures_dir(self, animal: str) -> Path:
        """Return the per-mouse spout-behavior figures output directory.

        Layout: ``{pipeline_outputs/spout_behavior}/spout_behavior_figures/{animal}/``.
        Phase 8a.10 sub-deliverable A renders the 11 per-mouse plot-
        family SVGs + PNGs here, mirroring the legacy
        ``basic_behavior_analysis3/<mouse>/`` layout (one SVG per
        ``(mouse, plot_family)`` pair).

        **Task 3 Round 2 continuation rename (2026-05-13):** replaces
        the prior ``visual_gate_dir``. The old layout at
        ``spout_behavior/visual_gate/<animal>/`` is orphaned (manual
        cleanup later).
        """
        return (
            self.pipeline_outputs("spout_behavior")
            / "spout_behavior_figures" / animal
        )

    def spout_behavior_figures_summary_dir(self) -> Path:
        """Return the cohort-summary tile-grid output directory.

        Layout: ``{pipeline_outputs/spout_behavior}/spout_behavior_figures/summary/``.
        All cohort tile-grids live under a single shared ``summary/``
        subdir; per-grid identity is encoded in the filename stem
        (e.g. ``all_animals_grid``, ``stroke_mice_grid``,
        ``ps46_only``) passed via :func:`make_summary_figures`'s
        ``output_dir_name=`` (a misnomer now — it's a file-stem
        prefix, not a directory name).

        **Task 3 Round 2 continuation rename (2026-05-13):** replaces
        the prior ``visual_gate_summary_dir(name)`` per-grid-dir
        convention. The old layout at
        ``spout_behavior/summary_<animals-joined>/`` is orphaned.
        """
        return (
            self.pipeline_outputs("spout_behavior")
            / "spout_behavior_figures" / "summary"
        )

    def spout_close_vs_std_dir(self, animal: str | None = None) -> Path:
        """Return the spout-close-vs-standard comparison figures
        output directory.

        Phase 8a.10 sub-deliverable B output root. Renamed from
        ``bare_vs_b_dir`` per Addendum #3 2026-05-13 — user-facing
        nomenclature is "spout close vs standard". Underlying
        ``half_suffix="bare"`` / ``"b"`` identifiers stay legacy
        (NPZ keys, registry, ``load_session_plot_data`` signature).

        Layout (Addendum #1 2026-05-13 — cohort-only design):
          - ``animal=None`` →
            ``{pipeline_outputs/spout_behavior}/spout_behavior_figures/spout_close_vs_std/cohort/``
            (cohort summary outputs, one file per animal:
            ``<animal>_summary.{svg,png}``).
          - ``animal="PS55"`` →
            ``{pipeline_outputs/spout_behavior}/spout_behavior_figures/spout_close_vs_std/PS55/``
            (legacy per-animal nested dir from CG-B2; superseded by
            Addendum #1 and orphan-cleaned by the orchestrator).
        """
        base = (
            self.pipeline_outputs("spout_behavior")
            / "spout_behavior_figures" / "spout_close_vs_std"
        )
        if animal is None:
            return base / "cohort"
        return base / animal
