#!/usr/bin/env bash
# Sanitized reference wrapper for the Phase 6.8a unattended runner +
# health-report chain. Committed under Phase 6.8a.3 as the canonical
# shape for any future "run notebook 12 headless, then check, then
# notify" invocation.
#
# Context: during the 2026-04-21 Phase 6.8a cohort first emit, the
# ad-hoc Windows task-runner wrapper invoked
# ``scripts/phase_6_8a_first_run_health_report.py`` through
# ``| tail -80`` to cap the stdout shown in the task-completion
# notification. Without ``set -o pipefail``, bash reports the exit
# code of the LAST command in a pipeline — and ``tail`` almost always
# exits 0, so a non-zero health-report exit (``execute(125)`` in
# conda, or exit 1 on a bundle-level failure) was silently masked
# to "task completed successfully".
#
# Fix: ``set -o pipefail`` makes bash propagate the first non-zero
# exit from any pipeline stage, so the wrapper's overall exit code
# reflects the health-report script's actual status. Also
# ``set -e`` to fail fast on any earlier setup step.
#
# Usage:
#   ./scripts/task_runner_wrapper.sh                        # default
#   ./scripts/task_runner_wrapper.sh --animals PS51         # subset
#
# All CLI args are forwarded to the runner; the health-report step
# runs unconditionally after the runner returns.

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

echo
echo "=== Phase 6.8a health report ==="
# pipefail is what makes this line honest: a non-zero exit from the
# python script propagates through `tail` instead of being swallowed.
python scripts/phase_6_8a_first_run_health_report.py --verbose 2>&1 | tail -80
