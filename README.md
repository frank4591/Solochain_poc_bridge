# Blockchain–NVFlare POC Bridge

POC: **1 aggregator** (bridge), **1 subnet** (`subnet_id = 0`), **1 trainer**. Chain at **172.206.89.225** (RPC 9944, UI 8080). Environment: **flockTest**.

The bridge registers as the aggregator on chain, starts a round (`start_round`), submits the NVFlare job (hello_pt_blockchain, CIFAR10 FedAvg with `min_clients=1`), waits for job completion, downloads the aggregated model, hashes it, and calls `finalize_round` on chain.

## Prerequisites

- **flockTest** environment with:
  - **NVFlare** – recommended: install from repo so the `nvflare` command and all dependencies are available:
    ```bash
    pip install -e ~/nvflare_dev/NVFlare
    ```
    For the PyTorch job (CIFAR10): `pip install -e "~/nvflare_dev/NVFlare[PT]"`  
    Alternatively, keep the repo at `~/nvflare_dev/NVFlare` and run from `blockchain_nvflare_poc`; the scripts use `python -m nvflare.cli`. You must still install NVFlare’s dependencies (e.g. `pip install pyhocon` and others as needed, or the full install above).
  - `substrate-interface` (see `requirements.txt`)
- Chain node at **172.206.89.225** (RPC `ws://172.206.89.225:9944`) with SubnetFl pallet and **subnet 0** (create/activate subnet if required).
- Aggregator account (e.g. `//Aggregator`) **funded** on chain (use UI at http://172.206.89.225:8080 to transfer from //Alice or another funded account).

## Quick start

1. **Activate environment**
   ```bash
   conda activate flockTest   # or your flockTest env
   pip install -r requirements.txt
   ```

2. **Prepare POC** (1 server + 1 client, job `hello_pt_blockchain` with `min_clients=1`)
   ```bash
   cd ~/nvflare_dev/blockchain_nvflare_poc
   chmod +x setup_poc.sh start_nvflare.sh run_bridge.sh
   ./setup_poc.sh
   ```

3. **Start NVFlare POC**
   ```bash
   ./start_nvflare.sh
   ```
   Leave this running (server + 1 client). In another terminal:

4. **Run the bridge**
   ```bash
   cd ~/nvflare_dev/blockchain_nvflare_poc
   ./run_bridge.sh
   ```
   The bridge will: register as aggregator (if not already), then loop: `start_round` → submit job → wait for job → download result → hash model → `finalize_round`.

## Config (env)

| Variable | Default | Description |
|----------|---------|-------------|
| `BLOCKCHAIN_RPC` | `ws://172.206.89.225:9944` | Chain RPC URL |
| `SUBNET_ID` | `0` | SubnetFl subnet id |
| `NVFLARE_POC_WORKSPACE` | `../nvflare_poc_workspace` | POC workspace (created by `setup_poc.sh`) |
| `NVFLARE_JOB_PATH` | `./jobs/hello_pt_blockchain` | Path to job folder |
| `AGGREGATOR_MNEMONIC` | `//Aggregator` | Aggregator keypair URI |
| `JOB_MONITOR_TIMEOUT` | `600` | Max seconds to wait for job |
| `JOB_POLL_INTERVAL` | `5` | Job status poll interval (seconds) |

## Layout

- `config.py` – Chain and bridge config (subnet_id=0, 172.206.89.225).
- `blockchain_client.py` – SubnetFl client (register_aggregator, start_round, finalize_round).
- `bridge.py` – Bridge loop: chain ↔ NVFlare POC (submit job, wait, download, hash, finalize).
- `jobs/hello_pt_blockchain/` – NVFlare job (CIFAR10, min_clients=1), same style as NVFlare’s pt_client_api.
- `setup_poc.sh` – POC prepare and prepare-jobs-dir.
- `start_nvflare.sh` – Start POC (server + 1 client).
- `run_bridge.sh` – Run bridge with default env.

## Chain connection robustness

After the NVFlare job runs (often 2+ minutes), the WebSocket to the chain can idle out. The bridge reconnects to the chain right before `finalize_round` (after the job and hash computation) and retries `start_round` and `finalize_round` up to 3 times on connection/JSON errors, reconnecting before each retry. So a one-off `JSONDecodeError` or dropped connection during `finalize_round` is handled without failing the whole cycle.

## Funding

If you see “insufficient balance” or “1010” from the chain, fund the aggregator account (e.g. `//Aggregator`) via the chain UI: http://172.206.89.225:8080 (Transfer from //Alice or another funded account).

## Optional: trainer on chain

To have the single trainer also report to the chain (`submit_model_update`) for rewards, you would add a custom executor or side process that calls `blockchain_client.submit_model_update` with the trainer’s keypair after training. This POC focuses on the aggregator bridge only.
