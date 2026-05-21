#!/usr/bin/env bash
# Phase 6.8a unattended notebook-12 runner. Committed under Phase 6.8a.3
# as the canonical shape for "run notebook 12 headless and notify."
#
# Phase 7c.2 Task 7 (Q68) retired the post-runner health-report tail step
# alongside the spatial_reward_aligned/ legacy tree it audited.
# `set -o pipefail` is kept on principle for any future pipe composition.
#
# Usage:
#   ./scripts/task_runner_wrapper.sh                        # default
#   ./scripts/task_runner_wrapper.sh --animals PS51         # subset
#
# All CLI args are forwarded to the runner.

set -euo pipefail

# Activate the analysis env. Adjust the conda.sh path if your install
# location differs (CLAUDE.md "Environment activation" rule).
# shellcheck disable=SC1091
source "${HOME}/miniconda3/etc/profile.d/conda.sh" 2>/dev/null \
  || source "/c/ProgramData/anaconda3/etc/profile.d/conda.sh"
conda activate stroke_orofacial

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

echo "=== Phase 6.8a runner ==="
python scripts/run_notebook_12_first_emit.py "$@"
