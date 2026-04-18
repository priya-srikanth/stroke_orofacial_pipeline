"""SBATCH script generation for DLC inference on O2.

Ported from cell 14 of canonical notebook
``20251112_DLC_batch_video_analysis_O2.ipynb``.
"""

from __future__ import annotations

from typing import Any


def generate_sbatch_script(
    config: dict[str, Any],
    username: str,
    selection_yaml_name: str = "video_selection.yaml",
) -> str:
    """Generate an SBATCH script for DLC batch inference on O2.

    Parameters
    ----------
    config : dict
        The ``dlc_inference_o2`` section from defaults.yaml.
    username : str
        HMS O2 username (e.g. ``"ps150"``).
    selection_yaml_name : str
        Name of the YAML selection file (uploaded to DLC_CFG on O2).

    Returns
    -------
    str
        Complete SBATCH script content.
    """
    scratch = config["scratch_root"].format(
        username_initial=username[0], username=username
    )
    dlc_in = f"{scratch}/dlc_in"
    dlc_out = f"{scratch}/dlc_out"
    dlc_cfg = f"{scratch}/dlc_cfg/DLC_train_config"
    dlc_code = f"{scratch}/dlc_code"
    log_dir = f"{scratch}/logs"

    return f"""#!/bin/bash -l
#SBATCH -J dlc_batch
#SBATCH -p {config['partition']}
#SBATCH --gres={config['gres']}
#SBATCH --exclude={config['exclude_nodes']}
#SBATCH --cpus-per-task={config['cpus_per_task']}
#SBATCH --mem={config['mem']}
#SBATCH -t {config['time']}
#SBATCH -o {log_dir}/dlc_%j.out
#SBATCH -e {log_dir}/dlc_%j.err
#SBATCH -D {scratch}

module load {config['conda_module']}
conda activate {config['conda_env']}

# GPU utilization logger (5-min interval)
/n/cluster/bin/job_gpu_monitor.sh &

echo "=== nvidia-smi ==="; nvidia-smi || true; echo "=================="

export CUDA_VISIBLE_DEVICES={config['gputouse']}

python {dlc_code}/run_dlc_batch.py \\
  --config {dlc_cfg}/config.yaml \\
  --inroot {dlc_in} \\
  --outroot {dlc_out} \\
  --selection-yaml {dlc_cfg}/{selection_yaml_name} \\
  --videoglob "{config['video_glob']}" \\
  --shuffle {config['shuffle']} --trainingsetindex {config['trainingsetindex']} --gputouse {config['gputouse']} \\
  --batchsize {config['batchsize']} --allow_growth \\
  --skip_if_exists
"""


def o2_paths(config: dict[str, Any], username: str) -> dict[str, str]:
    """Return a dict of all O2 path templates resolved for a username.

    Useful for the notebook to display paths and build commands.
    """
    scratch = config["scratch_root"].format(
        username_initial=username[0], username=username
    )
    return {
        "scratch": scratch,
        "dlc_in": f"{scratch}/dlc_in",
        "dlc_out": f"{scratch}/dlc_out",
        "dlc_cfg": f"{scratch}/dlc_cfg/DLC_train_config",
        "dlc_code": f"{scratch}/dlc_code",
        "log_dir": f"{scratch}/logs",
        "camera_source": config["camera_source"],
        "dlc_config_source": config["dlc_config_source"],
        "data1_staging": config["data1_staging"],
        "microscope_dest": config["microscope_dest"],
        "transfer_host": config["transfer_host"],
    }
