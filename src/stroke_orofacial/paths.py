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

    Attributes
    ----------
    platform_key : str
        The platform key used for resolution ('mac' or 'windows').
    """

    def __init__(self, config_path: Path | str | None = None) -> None:
        if config_path is None:
            config_path = _default_config_path()
        config_path = Path(config_path)

        with open(config_path) as f:
            self._config = yaml.safe_load(f)

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

        E.g. ``/Volumes/.../pipeline_outputs_v2/spout_behavior``
        """
        return self.root("microscope_pipeline_outputs") / subdir

    def wavesurfer_dir(self, date: datetime.date, animal: str) -> Path:
        """Return the wavesurfer session directory for an animal and date.

        E.g. ``/Volumes/.../wavesurfer/20250307/PS46``
        """
        date_str = date.strftime("%Y%m%d")
        return self.root("wavesurfer_raw") / date_str / animal

    # Kept for backward compatibility but deprecated in favor of pipeline_outputs()
    def session_processing_out(self, version: str = "v2") -> Path:
        """Return the output directory for processed session data (deprecated).

        Use ``pipeline_outputs(subdir='spout_behavior')`` instead.
        """
        return self.root("local_processed_spout") / f"session_processing_{version}"
