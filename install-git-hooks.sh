#!/bin/bash
# Use repo hooks (strip Cursor co-author, enforce Karim-Termanini identity on commits).
set -euo pipefail
ROOT="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
chmod +x "$ROOT/.githooks/"*
git config core.hooksPath "$ROOT/.githooks"
echo "Installed git hooks from $ROOT/.githooks"
