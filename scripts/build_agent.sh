#!/usr/bin/env bash
# Vendor packages/common and the policy documents into agent/_vendor/ so the agent
# directory is self-contained for AgentCore (agentcore configure/launch) or Lambda.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR="$ROOT/agent/_vendor"

rm -rf "$VENDOR"
mkdir -p "$VENDOR/policies"
cp -R "$ROOT/packages/common/src/resolveai_common" "$VENDOR/resolveai_common"
cp "$ROOT/rag/policies/"*.md "$VENDOR/policies/"
find "$VENDOR" -type d -name __pycache__ -prune -exec rm -rf {} +

echo "vendored resolveai_common + $(ls "$VENDOR/policies" | wc -l | tr -d ' ') policy docs into $VENDOR"
