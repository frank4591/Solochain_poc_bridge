#!/usr/bin/env bash
# Run the blockchain–NVFlare bridge (aggregator: start_round -> job -> finalize_round).
# Requires: flockTest env, POC running (./start_nvflare.sh), chain at 172.206.89.225.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
export NVFLARE_POC_WORKSPACE="${NVFLARE_POC_WORKSPACE:-$ROOT/nvflare_poc_workspace}"
export SUBNET_ID="${SUBNET_ID:-0}"
export BLOCKCHAIN_RPC="${BLOCKCHAIN_RPC:-ws://172.206.89.225:9944}"

cd "$SCRIPT_DIR"
exec python bridge.py
