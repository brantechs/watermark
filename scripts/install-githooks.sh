#!/usr/bin/env sh
# この clone で .githooks/ を有効にする(作業開始時に1回)。
set -eu
cd "$(git rev-parse --show-toplevel)"
chmod +x .githooks/* scripts/qa-gate.sh
git config core.hooksPath .githooks
echo "core.hooksPath=.githooks (pre-commit: scripts/qa-gate.sh change --staged)"
