#!/usr/bin/env bash
set -euo pipefail

# ── fabric-drawio runner ───────────────────────────────────────────────────────
#
# Usage examples:
#   ./run.sh --demo
#   ./run.sh --demo --llm codex
#   ./run.sh --state Active
#   ./run.sh --workspace <collection-id>
#   ./run.sh --cross-workspace <id1> <id2> <id3>
#   ./run.sh --state Active --area-path "MyProject\Data Team"
#
# Required env vars (in .env or set in environment):
#   ANTHROPIC_API_KEY              (or OPENAI_API_KEY for --llm codex)
#   AZURE_DEVOPS_ORG, AZURE_DEVOPS_PROJECT, AZURE_DEVOPS_PAT
#   AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
#   PURVIEW_ACCOUNT_NAME
#
# In --demo mode only ANTHROPIC_API_KEY (or OPENAI_API_KEY) is required.
# ─────────────────────────────────────────────────────────────────────────────

if ! command -v uv &>/dev/null; then
    echo "ERROR: uv is not installed or not on PATH."
    echo "Install it from https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -f ".env" ]]; then
    echo "WARNING: .env not found. Copy .env.example to .env and fill in your credentials."
    echo "         Continuing — values may already be set in the environment."
    echo
fi

exec uv run python -m agent.main "$@"
