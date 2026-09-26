#!/usr/bin/env bash
# One-command: register 6 trainers (if needed), start NVFlare POC (6 clients), then run bridge for training.
# Uses chain_accounts.txt: aggregator=Bob, trainers=Dave,Eve,Ferdie,One,Two,Trainer6.
# Prerequisite: run ./setup_poc.sh once (NUM_CLIENTS=6). Fund Bob + 6 trainer accounts at chain UI first.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
export NVFLARE_POC_WORKSPACE="${NVFLARE_POC_WORKSPACE:-$ROOT/nvflare_poc_workspace}"
export SUBNET_ID="${SUBNET_ID:-1}"
export BLOCKCHAIN_RPC="${BLOCKCHAIN_RPC:-ws://172.206.89.225:9944}"
export AGGREGATOR_MNEMONIC="${AGGREGATOR_MNEMONIC:-//Bob}"
export NUM_CLIENTS="${NUM_CLIENTS:-6}"

cd "$SCRIPT_DIR"

# Check chain is reachable before starting anything
if ! python -c "
import sys
from substrateinterface import SubstrateInterface
try:
    SubstrateInterface(url='$BLOCKCHAIN_RPC', ss58_format=42)
except Exception as e:
    print('Chain connection failed:', e, file=sys.stderr)
    sys.exit(1)
" 2>/dev/null; then
  echo "ERROR: Chain at $BLOCKCHAIN_RPC is not reachable (connection refused or timeout)."
  echo "  - Start the chain node on that host/port, or"
  echo "  - Set BLOCKCHAIN_RPC to your node (e.g. export BLOCKCHAIN_RPC=ws://YOUR_IP:9944)"
  echo "  - Chain UI: http://172.206.89.225:8080"
  exit 1
fi

if [[ ! -d "$NVFLARE_POC_WORKSPACE" ]] || [[ ! -d "$NVFLARE_POC_WORKSPACE/example_project" ]]; then
  echo "POC workspace not found. Run first: ./setup_poc.sh"
  exit 1
fi

# Number of sites in workspace is fixed at setup time (poc prepare -n N)
PROD_DIR="$NVFLARE_POC_WORKSPACE/example_project/prod_00"
WORKSPACE_SITES=$(ls -d "$PROD_DIR"/site-* 2>/dev/null | wc -l)
if [[ "$WORKSPACE_SITES" -ne "$NUM_CLIENTS" ]]; then
  echo "ERROR: Workspace has $WORKSPACE_SITES clients (site-1 ... site-$WORKSPACE_SITES) but NUM_CLIENTS=$NUM_CLIENTS."
  echo "  To run with $NUM_CLIENTS sites only: stop POC (pkill -f nvflare), then run:"
  echo "    NUM_CLIENTS=$NUM_CLIENTS ./setup_poc.sh"
  echo "  then run this script again (with NUM_CLIENTS=$NUM_CLIENTS if desired)."
  exit 1
fi

echo "=== 1. Register $NUM_CLIENTS trainers on chain (subnet_id=$SUBNET_ID) ==="
python register_trainers.py || true

echo ""
echo "=== 2. Starting NVFlare POC (server + $NUM_CLIENTS clients) in background ==="
nohup ./start_nvflare.sh > /tmp/nvflare_poc.log 2>&1 &
NVFLARE_PID=$!
echo "NVFlare POC PID: $NVFLARE_PID (log: /tmp/nvflare_poc.log)"
echo "Waiting 15s for server and clients to come up..."
sleep 15

echo ""
echo "=== 3. Running bridge (aggregator=Bob, submit job, finalize_round) ==="
echo "Press Ctrl+C to stop the bridge. To stop NVFlare: nvflare poc stop (or kill $NVFLARE_PID)"
echo ""
exec ./run_bridge.sh
