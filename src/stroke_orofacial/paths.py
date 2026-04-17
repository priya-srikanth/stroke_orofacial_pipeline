"""Path resolution: logical roots -> platform-specific mount points.

PathResolver loads configs/paths.yaml and maps logical root names
(e.g. 'microscope_server') to concrete filesystem paths based on the
current platform (Darwin/Windows) or the STROKE_PIPELINE_MACHINE env var.
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

        # Resolve logical roots to concrete Path objects
        self._roots: dict[str, Path | None] = {}
        for name, spec in self._config.get("logical_roots", {}).items():
            mount = spec.get("mounts", {}).get(self.platform_key)
            if mount is None:
                self._roots[name] = None
            elif self.platform_key == "windows":
                self._roots[name] = PureWindowsPath(mount)  # type: ignore[assignment]
            else:
                self._roots[name] = PurePosixPath(mount)  # type: ignore[assignment]

    def root(self, name: str) -> Path:
        """Return the resolved root path for a logical name.

        Raises
        ------
        KeyError
            If the logical root name is not defined in paths.yaml.
        RuntimeError
            If the logical root has no mount for the current platform.
        """
        if name not in self._roots:
            raise KeyError(
                f"Unknown logical root '{name}'. "
                f"Available: {list(self._roots.keys())}"
            )
        path = self._roots[name]
        if path is None:
            raise RuntimeError(
                f"Logical root '{name}' has no mount defined for platform '{self.platform_key}'."
            )
        return Path(path)

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

    def session_processing_out(self, version: str = "v2") -> Path:
        """Return the output directory for processed session data.

        E.g. ``/Users/.../analysis/session_processing_v2``
        """
        return self.root("local_processed_spout") / f"session_processing_{version}"
