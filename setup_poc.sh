#!/usr/bin/env bash
# Prepare NVFlare POC: 1 server + 1 client, subnet_id=0, chain at 172.206.89.225.
# Run with flockTest env active. Uses NVFLARE_POC_WORKSPACE (default: nvflare_dev/nvflare_poc_workspace).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
export NVFLARE_POC_WORKSPACE="${NVFLARE_POC_WORKSPACE:-$ROOT/nvflare_poc_workspace}"
JOB_DIR="$SCRIPT_DIR/jobs/hello_pt_blockchain"

echo "NVFLARE_POC_WORKSPACE=$NVFLARE_POC_WORKSPACE"
echo "Job dir: $JOB_DIR"

# Use nvflare CLI if on PATH, else run from NVFlare repo via python -m
NVFLARE_CMD=""
if command -v nvflare &>/dev/null; then
  NVFLARE_CMD="nvflare"
elif [[ -d "$ROOT/NVFlare" ]]; then
  export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$ROOT/NVFlare"
  NVFLARE_CMD="python -m nvflare.cli"
fi
if [[ -z "$NVFLARE_CMD" ]]; then
  echo "nvflare CLI not found. Either: pip install -e ~/nvflare_dev/NVFlare, or run from nvflare_dev with NVFlare repo at ./NVFlare."
  exit 1
fi

mkdir -p "$NVFLARE_POC_WORKSPACE"
echo 'y' | $NVFLARE_CMD poc prepare -n 1
$NVFLARE_CMD poc prepare-jobs-dir -j "$JOB_DIR"
echo "POC prepared. Start with: ./start_nvflare.sh (or nvflare poc start)"
echo "Then run bridge: ./run_bridge.sh"
