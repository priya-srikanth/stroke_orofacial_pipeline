"""Transfer utilities and output renaming for DLC inference.

Ported from cells 11, 33, 45-47 of canonical notebook
``20251112_DLC_batch_video_analysis_O2.ipynb``.

These functions generate shell commands as strings — they do NOT execute
them. The user pastes commands into their terminal or O2 SSH session.
This preserves the password-handling directive: no SSH from within
Python/notebook context.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def build_stage_videos_command(
    config: dict[str, Any],
    username: str,
    animals: list[str],
    dates: list[str],
) -> str:
    """Build an rsync command to stage camera videos onto O2 scratch.

    Parameters
    ----------
    config : dict
        The ``dlc_inference_o2`` section from defaults.yaml.
    username : str
        HMS O2 username.
    animals : list[str]
        Animal IDs to stage.
    dates : list[str]
        Date strings (YYYYMMDD) to stage.

    Returns
    -------
    str
        Rsync command string to paste into an O2 SSH session.
    """
    scratch = config["scratch_root"].format(
        username_initial=username[0], username=username
    )
    dlc_in = f"{scratch}/dlc_in"
    camera_src = config["camera_source"]

    lines = ["# Stage videos from MICROSCOPE to O2 scratch"]
    lines.append(f"mkdir -p {dlc_in}")
    for date in dates:
        for animal in animals:
            src = f"{camera_src}/{date}/{animal}/"
            dst = f"{dlc_in}/{date}/{animal}/"
            lines.append(
                f"rsync -avh --partial --inplace --update "
                f"{src} {dst}"
            )
    return "\n".join(lines)


def build_copy_to_microscope_command(
    config: dict[str, Any],
    username: str,
    *,
    via_data1: bool = True,
) -> str:
    """Build rsync commands to copy DLC outputs to MICROSCOPE.

    Parameters
    ----------
    config : dict
        The ``dlc_inference_o2`` section from defaults.yaml.
    username : str
        HMS O2 username.
    via_data1 : bool
        If True (default), two-stage copy: scratch → data1 → MICROSCOPE.
        If False, direct copy via transfer node.

    Returns
    -------
    str
        Shell commands to paste into terminal.
    """
    scratch = config["scratch_root"].format(
        username_initial=username[0], username=username
    )
    dlc_out = f"{scratch}/dlc_out"
    staging = config["data1_staging"]
    dest = config["microscope_dest"]
    host = config["transfer_host"]

    if via_data1:
        return f"""# Stage 1: O2 scratch → /n/data1 staging
rsync -avh --partial --inplace --update \\
  {dlc_out}/ \\
  {staging}/

# Stage 2: /n/data1 → MICROSCOPE (via transfer node)
rsync -avh --partial --inplace --update \\
  {staging}/ \\
  {username}@{host}:{dest}/"""
    else:
        return f"""# Direct copy: O2 scratch → MICROSCOPE (via transfer node)
rsync -avh --partial --inplace --update \\
  -e "ssh -S ~/.ssh/ctrl-transfer -o ControlMaster=no" \\
  {dlc_out}/ \\
  {username}@{host}:{dest}/"""


def build_rename_command(
    config: dict[str, Any],
    username: str,
) -> str:
    """Build a Python one-liner to rename snapshot outputs on O2.

    Renames ``snapshot-best-60`` / ``snapshot_best-60`` to ``snapshot_060``
    in all DLC output files.

    Returns
    -------
    str
        Command to paste into an O2 SSH session.
    """
    scratch = config["scratch_root"].format(
        username_initial=username[0], username=username
    )
    dlc_out = f"{scratch}/dlc_out"
    renames = config.get("snapshot_renames", {
        "snapshot-best-60": "snapshot_060",
        "snapshot_best-60": "snapshot_060",
    })

    # Build the rename patterns as a Python dict literal
    pat_dict = ", ".join(f'r"{k}": "{v}"' for k, v in renames.items())

    return f"""python3 -c '
import os, re
root = "{dlc_out}"
renames = {{{pat_dict}}}
pat = re.compile("|".join(re.escape(k) for k in renames))
count = 0
for dirpath, _, files in os.walk(root):
    for fname in files:
        new = pat.sub(lambda m: renames[m.group()], fname)
        if new != fname:
            os.rename(os.path.join(dirpath, fname), os.path.join(dirpath, new))
            count += 1
print(f"Renamed {{count}} files")
'"""


def rename_snapshots_local(output_dir: Path, renames: dict[str, str] | None = None) -> int:
    """Rename snapshot files locally (for post-copy cleanup).

    This runs on the local machine — safe for the notebook to call directly
    on already-copied files.

    Parameters
    ----------
    output_dir : Path
        Directory to walk recursively.
    renames : dict, optional
        ``{old_pattern: new_pattern}``. Default: snapshot-best-60 → snapshot_060.

    Returns
    -------
    int
        Number of files renamed.
    """
    if renames is None:
        renames = {
            "snapshot-best-60": "snapshot_060",
            "snapshot_best-60": "snapshot_060",
        }
    pat = re.compile("|".join(re.escape(k) for k in renames))
    count = 0
    for dirpath, _, files in Path(output_dir).walk():
        for fname in files:
            new = pat.sub(lambda m: renames[m.group()], fname)
            if new != fname:
                (dirpath / fname).rename(dirpath / new)
                count += 1
    return count
