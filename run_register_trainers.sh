#!/usr/bin/env bash
# Register trainers on chain (subnet_id=1 by default). Fund trainer accounts first at CHAIN_UI.
# Override: SUBNET_ID=0 TRAINER_URIS="//Charlie,//Dave,..." ./run_register_trainers.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export SUBNET_ID="${SUBNET_ID:-1}"
export BLOCKCHAIN_RPC="${BLOCKCHAIN_RPC:-ws://172.206.89.225:9944}"
exec python register_trainers.py
