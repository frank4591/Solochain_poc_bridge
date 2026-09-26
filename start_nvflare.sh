#!/usr/bin/env bash
# Start NVFlare POC (server + 1 client). Run after setup_poc.sh.
# Requires NVFLARE_POC_WORKSPACE set (or default from setup_poc.sh).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
export NVFLARE_POC_WORKSPACE="${NVFLARE_POC_WORKSPACE:-$ROOT/nvflare_poc_workspace}"
# POC uses self-signed certs; allow internal/backbone connections in dev runs.
# Set to 1 to re-enable verification.
export NVFLARE_POC_SSL_VERIFY="${NVFLARE_POC_SSL_VERIFY:-0}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python 2>/dev/null || true)}"
if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 2>/dev/null || true)"
fi

# Ensure all POC-spawned processes use the same Python environment.
# nvflare's generated startup scripts rely on PATH for "python".
if [[ -n "${PYTHON_BIN:-}" ]]; then
  PY_DIR="$(dirname "$PYTHON_BIN")"
  export PATH="$PY_DIR:$PATH"
fi

if [[ ! -d "$NVFLARE_POC_WORKSPACE" ]]; then
  echo "POC workspace not found: $NVFLARE_POC_WORKSPACE. Run ./setup_poc.sh first."
  echo "If you meant standalone FL, run:"
  echo "  NUM_CLIENTS=10 ./setup_standalone_fl.sh"
  echo "  NVFLARE_POC_WORKSPACE=$ROOT/nvflare_standalone_workspace NVFLARE_POC_SSL_VERIFY=0 ./start_nvflare.sh"
  exit 1
fi
if command -v nvflare &>/dev/null; then
  nvflare poc start
else
  ROOT="$(dirname "$SCRIPT_DIR")"
  export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$ROOT/NVFlare"
  if [[ -z "${PYTHON_BIN:-}" ]]; then
    echo "python not found on PATH. Activate your env or set PYTHON_BIN=/path/to/python"
    exit 1
  fi
  "$PYTHON_BIN" -m nvflare.cli poc start
fi
