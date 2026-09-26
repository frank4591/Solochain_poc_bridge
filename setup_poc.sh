#!/usr/bin/env bash
# Prepare NVFlare POC: 1 server + N clients (default 6), subnet_id=1 by default, chain at 172.206.89.225.
# Run with flockTest env active. Uses NVFLARE_POC_WORKSPACE (default: nvflare_dev/nvflare_poc_workspace).
# Set NUM_CLIENTS=6 (default) or NUM_CLIENTS=20 for more clients; job min_clients is synced automatically.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
export NVFLARE_POC_WORKSPACE="${NVFLARE_POC_WORKSPACE:-$ROOT/nvflare_poc_workspace}"
NUM_CLIENTS="${NUM_CLIENTS:-6}"
JOB_DIR="$SCRIPT_DIR/jobs/hello_pt_blockchain"

echo "NVFLARE_POC_WORKSPACE=$NVFLARE_POC_WORKSPACE"
echo "NUM_CLIENTS=$NUM_CLIENTS"
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
echo 'y' | $NVFLARE_CMD poc prepare -n "$NUM_CLIENTS"
$NVFLARE_CMD poc prepare-jobs-dir -j "$JOB_DIR"
# Sync job min_clients to NUM_CLIENTS so 6 or 20 (or any N) works without editing job by hand
if [[ -f "$JOB_DIR/meta.json" ]]; then
  sed -i "s/\"min_clients\":[0-9]*/\"min_clients\":$NUM_CLIENTS/" "$JOB_DIR/meta.json"
  echo "Set meta.json min_clients=$NUM_CLIENTS"
fi
if [[ -f "$JOB_DIR/app/config/config_fed_server.conf" ]]; then
  sed -i "s/min_clients = [0-9]*/min_clients = $NUM_CLIENTS/" "$JOB_DIR/app/config/config_fed_server.conf"
  echo "Set config_fed_server.conf min_clients=$NUM_CLIENTS"
fi
echo "POC prepared. Start with: ./start_nvflare.sh (or nvflare poc start)"
echo "Then run bridge: ./run_bridge.sh"
