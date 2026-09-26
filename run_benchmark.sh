#!/usr/bin/env bash
# Benchmark standalone FL: 50 clients (or NUM_CLIENTS), MNIST + SimpleCNN.
# 1) Setup workspace with N clients and job min_clients
# 2) Start POC in background
# 3) Run benchmark (submit job, time, evaluate final model, write benchmark_results/)
# Usage: ./run_benchmark.sh   or   NUM_CLIENTS=20 ./run_benchmark.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
export NVFLARE_POC_WORKSPACE="${NVFLARE_STANDALONE_WORKSPACE:-$ROOT/nvflare_standalone_workspace}"
export NUM_CLIENTS="${NUM_CLIENTS:-50}"

cd "$SCRIPT_DIR"

echo "=== Benchmark: $NUM_CLIENTS clients, MNIST + SimpleCNN ==="
echo "Workspace: $NVFLARE_POC_WORKSPACE"
echo ""

echo "=== 1. Setup workspace ($NUM_CLIENTS clients) ==="
./setup_standalone_fl.sh

echo ""
echo "=== 2. Starting NVFlare POC in background ==="
# Free ports 8002/8003 and stop any existing POC so we don't get "address already in use"
if [[ -f "$SCRIPT_DIR/stop_poc_and_free_ports.sh" ]]; then
  chmod +x "$SCRIPT_DIR/stop_poc_and_free_ports.sh" 2>/dev/null || true
  "$SCRIPT_DIR/stop_poc_and_free_ports.sh" || true
else
  NVFLARE_POC_SSL_VERIFY=0 nvflare poc stop &>/dev/null || true
  sleep 3
fi
echo "Starting POC server and clients..."
sleep 5
nohup ./start_nvflare.sh > /tmp/nvflare_benchmark.log 2>&1 &
NVFLARE_PID=$!
echo "POC PID: $NVFLARE_PID (log: /tmp/nvflare_benchmark.log)"
# With more clients, server and sites take longer to start (avoid "Connection reset by peer")
# 10 clients: 30s; 11–50: 90s; 51–200: 120s; 200+: 180s. Override with POC_WAIT_SEC.
WAIT_SEC="${POC_WAIT_SEC:-30}"
if [[ -z "$POC_WAIT_SEC" ]]; then
  if [[ "$NUM_CLIENTS" -gt 200 ]]; then
    WAIT_SEC=180
  elif [[ "$NUM_CLIENTS" -gt 50 ]]; then
    WAIT_SEC=120
  elif [[ "$NUM_CLIENTS" -gt 10 ]]; then
    WAIT_SEC=90
  fi
fi
echo "Waiting ${WAIT_SEC}s for server and $NUM_CLIENTS clients to come up..."
sleep "$WAIT_SEC"

# POC server often uses self-signed certs; allow admin client to connect (NVFlare net_utils checks this env)
export NVFLARE_POC_SSL_VERIFY="${NVFLARE_POC_SSL_VERIFY:-0}"
echo "NVFLARE_POC_SSL_VERIFY=$NVFLARE_POC_SSL_VERIFY (0=skip server cert verify for POC)"

echo ""
echo "=== 3. Running benchmark (submit job, time, evaluate, write results) ==="
python3 benchmark_standalone_fl.py

echo ""
echo "Results in: $SCRIPT_DIR/benchmark_results/"
echo "To stop POC: nvflare poc stop   (or kill $NVFLARE_PID)"
