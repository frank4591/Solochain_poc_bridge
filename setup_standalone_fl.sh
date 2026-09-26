#!/usr/bin/env bash
# Prepare standalone NVFlare FL (no blockchain): 10 clients + 1 server, MNIST + SimpleCNN.
# Uses a separate workspace so the 2-client blockchain POC is untouched.
# Run with: ./setup_standalone_fl.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
export NVFLARE_POC_WORKSPACE="${NVFLARE_STANDALONE_WORKSPACE:-$ROOT/nvflare_standalone_workspace}"
NUM_CLIENTS="${NUM_CLIENTS:-10}"
JOB_DIR="$SCRIPT_DIR/jobs/mnist_simplecnn"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python 2>/dev/null || true)}"
if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 2>/dev/null || true)"
fi

echo "Standalone FL workspace: $NVFLARE_POC_WORKSPACE"
echo "NUM_CLIENTS=$NUM_CLIENTS"
echo "Job dir: $JOB_DIR"
echo "Python: ${PYTHON_BIN:-<not found>}"

if [[ ! -d "$JOB_DIR" ]]; then
  echo "ERROR: Job not found: $JOB_DIR"
  exit 1
fi

# Use nvflare CLI if on PATH, else run from NVFlare repo
NVFLARE_CMD=""
if command -v nvflare &>/dev/null; then
  NVFLARE_CMD="nvflare"
elif [[ -d "$ROOT/NVFlare" ]]; then
  export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$ROOT/NVFlare"
  if [[ -z "${PYTHON_BIN:-}" ]]; then
    echo "python not found on PATH. Activate your env or set PYTHON_BIN=/path/to/python"
    exit 1
  fi
  NVFLARE_CMD="$PYTHON_BIN -m nvflare.cli"
fi
if [[ -z "$NVFLARE_CMD" ]]; then
  echo "nvflare CLI not found. pip install -e ~/nvflare_dev/NVFlare or set PYTHONPATH."
  exit 1
fi

mkdir -p "$NVFLARE_POC_WORKSPACE"
echo 'y' | $NVFLARE_CMD poc prepare -n "$NUM_CLIENTS"
$NVFLARE_CMD poc prepare-jobs-dir -j "$JOB_DIR"

# Sync min_clients in job to NUM_CLIENTS
if [[ -f "$JOB_DIR/meta.json" ]]; then
  sed -i "s/\"min_clients\":[0-9]*/\"min_clients\":$NUM_CLIENTS/" "$JOB_DIR/meta.json"
  echo "Set meta.json min_clients=$NUM_CLIENTS"
fi
if [[ -f "$JOB_DIR/app/config/config_fed_server.conf" ]]; then
  sed -i "s/min_clients = [0-9]*/min_clients = $NUM_CLIENTS/" "$JOB_DIR/app/config/config_fed_server.conf"
  echo "Set config_fed_server.conf min_clients=$NUM_CLIENTS"
fi

echo ""
echo "Standalone FL prepared: 1 server + $NUM_CLIENTS clients, job=mnist_simplecnn (MNIST + SimpleCNN)."
echo "Start and run training: ./run_standalone_fl.sh"
echo "Or start only: NVFLARE_POC_WORKSPACE=$NVFLARE_POC_WORKSPACE ./start_nvflare.sh"
