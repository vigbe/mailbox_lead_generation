#!/usr/bin/env bash
# Build a clean, store-ready zip for mailbox_lead_generation.
#
# The Odoo Apps Store expects the module directory at the ROOT of the zip:
#     mailbox_lead_generation/__manifest__.py
# This script stages a clean copy (no git, caches, CI, agent state or internal
# design docs) and produces dist/mailbox_lead_generation-<version>.zip.
#
# Usage:  scripts/build_store_zip.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MODULE_NAME="mailbox_lead_generation"

VERSION="$(python3 - <<'PY'
import ast

manifest = ast.literal_eval(open("__manifest__.py").read())
print(manifest["version"])
PY
)"

STAGE="$(mktemp -d)/$MODULE_NAME"
mkdir -p "$STAGE"

# Copy only what ships to the store.
rsync -a \
    --exclude '.git*' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.ruff_cache/' \
    --exclude '.atl/' \
    --exclude '.pi-subagents/' \
    --exclude '.pi/' \
    --exclude '.agents/' \
    --exclude '.vscode/' \
    --exclude '.codegraph/' \
    --exclude '.github/' \
    --exclude 'dist/' \
    --exclude 'scripts/' \
    --exclude 'docs/' \
    --exclude '.DS_Store' \
    --exclude 'pi' \
    --exclude '.gitignore' \
    --exclude 'CLAUDE.md' \
    __init__.py __manifest__.py README.md \
    controllers models security views data tests static \
    "$STAGE"/

mkdir -p dist
ZIP="dist/${MODULE_NAME}-${VERSION}.zip"
rm -f "$ZIP"
(cd "$(dirname "$STAGE")" && zip -r -q "$REPO_ROOT/$ZIP" "$MODULE_NAME")

echo "Built: $ZIP ($(du -h "$ZIP" | cut -f1))"
echo "Layout check (module must be at zip root):"
unzip -l "$ZIP" | head -8
