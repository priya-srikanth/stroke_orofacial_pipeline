#!/usr/bin/env bash
# One-command install for the repo's git hooks.
#
# Run once per clone:
#   bash scripts/setup-hooks.sh

set -e

cd "$(dirname "$0")/.."

git config core.hooksPath .githooks
chmod +x .githooks/pre-commit

echo "Git hooks configured. .githooks/ is now active for this clone."
echo "Verify: git config --get core.hooksPath"
