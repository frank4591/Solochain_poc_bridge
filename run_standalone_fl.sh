#!/usr/bin/env bash
# Start standalone NVFlare POC (10 clients + server) and run MNIST + SimpleCNN training.
# No blockchain. Prerequisite: ./setup_standalone_fl.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
export NVFLARE_POC_WORKSPACE="${NVFLARE_STANDALONE_WORKSPACE:-$ROOT/nvflare_standalone_workspace}"

if [[ ! -d "$NVFLARE_POC_WORKSPACE" ]] || [[ ! -d "$NVFLARE_POC_WORKSPACE/example_project" ]]; then
  echo "Standalone workspace not found. Run first: ./setup_standalone_fl.sh"
  exit 1
fi

cd "$SCRIPT_DIR"

echo "=== Starting NVFlare POC (server + clients) in background ==="
echo "Workspace: $NVFLARE_POC_WORKSPACE"
nohup ./start_nvflare.sh > /tmp/nvflare_standalone.log 2>&1 &
NVFLARE_PID=$!
echo "POC PID: $NVFLARE_PID (log: /tmp/nvflare_standalone.log)"
echo "Waiting 20s for server and clients to come up..."
sleep 20

# POC server often uses self-signed certs; allow admin client to connect (NVFlare net_utils)
export NVFLARE_POC_SSL_VERIFY="${NVFLARE_POC_SSL_VERIFY:-0}"

echo ""
echo "=== Submitting MNIST SimpleCNN job and waiting for completion ==="
python3 run_standalone_mnist_job.py

echo ""
echo "Done. To stop the POC: nvflare poc stop (or kill $NVFLARE_PID)"
