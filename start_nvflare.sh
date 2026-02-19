#!/usr/bin/env bash
# Start NVFlare POC (server + 1 client). Run after setup_poc.sh.
# Requires NVFLARE_POC_WORKSPACE set (or default from setup_poc.sh).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
export NVFLARE_POC_WORKSPACE="${NVFLARE_POC_WORKSPACE:-$ROOT/nvflare_poc_workspace}"

if [[ ! -d "$NVFLARE_POC_WORKSPACE" ]]; then
  echo "POC workspace not found: $NVFLARE_POC_WORKSPACE. Run ./setup_poc.sh first."
  exit 1
fi
if command -v nvflare &>/dev/null; then
  nvflare poc start
else
  ROOT="$(dirname "$SCRIPT_DIR")"
  export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$ROOT/NVFlare"
  python -m nvflare.cli poc start
fi
