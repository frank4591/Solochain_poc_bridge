# Blockchain–NVFlare POC Bridge

POC: **1 aggregator** (bridge), **1 subnet** (`subnet_id = 1` by default), **6 trainers** (default; up to **20** with `NUM_CLIENTS=20`). Chain at **172.206.89.225** (RPC 9944, UI 8080). Environment: **flockTest**.

The bridge registers as the aggregator on chain, starts a round (`start_round`), submits the NVFlare job (hello_pt_blockchain, CIFAR10 FedAvg; `min_clients` is set from `NUM_CLIENTS` in `setup_poc.sh`), waits for job completion, downloads the aggregated model, hashes it, and calls `finalize_round` on chain. **GPU**: training uses CUDA if available (e.g. 8GB VRAM); clients typically run one-at-a-time per round, so 8GB is enough for many clients.

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

2. **Register trainers on chain** (for 6-trainer setup; fund accounts first at chain UI)
   ```bash
   cd ~/nvflare_dev/blockchain_nvflare_poc
   chmod +x run_register_trainers.sh
   # Fund //Charlie, //Dave, //Eve, //Ferdie, //One, //Two at http://172.206.89.225:8080
   ./run_register_trainers.sh
   ```

3. **Prepare POC** (1 server + N clients; default 6, or `NUM_CLIENTS=20` for 20 clients). Job `min_clients` is set automatically from `NUM_CLIENTS`.
   ```bash
   chmod +x setup_poc.sh start_nvflare.sh run_bridge.sh
   ./setup_poc.sh
   # Or for 20 clients: NUM_CLIENTS=20 ./setup_poc.sh
   ```
   For single-trainer POC: `NUM_CLIENTS=1 ./setup_poc.sh`.

4. **Start NVFlare POC**
   ```bash
   ./start_nvflare.sh
   ```
   Leave this running (server + 6 clients). In another terminal:

5. **Run the bridge**
   ```bash
   cd ~/nvflare_dev/blockchain_nvflare_poc
   ./run_bridge.sh
   ```
   The bridge will: register as aggregator (if not already), then loop: `start_round` → submit job → wait for job → download result → hash model → `finalize_round`.

## Config (env)

| Variable | Default | Description |
|----------|---------|-------------|
| `BLOCKCHAIN_RPC` | `ws://172.206.89.225:9944` | Chain RPC URL |
| `SUBNET_ID` | `1` | SubnetFl subnet id |
| `NVFLARE_POC_WORKSPACE` | `../nvflare_poc_workspace` | POC workspace (created by `setup_poc.sh`) |
| `NVFLARE_JOB_PATH` | `./jobs/hello_pt_blockchain` | Path to job folder |
| `AGGREGATOR_MNEMONIC` | `//Aggregator` | Aggregator keypair URI |
| `JOB_MONITOR_TIMEOUT` | `600` | Max seconds to wait for job |
| `JOB_POLL_INTERVAL` | `5` | Job status poll interval (seconds) |
| `UPDATE_DEADLINE_BLOCKS` | `30` | Blocks after start_round before round becomes ValidatingUpdates (must pass before finalize_round). Lower = less wait after job. |
| `VALIDATION_DEADLINE_BLOCKS` | `60` | Blocks for validation phase. |
| `FINALIZE_WAIT_TIMEOUT` | `900` | Max seconds to wait for chain block >= update_deadline before finalize_round. |
| `FINALIZE_WAIT_POLL` | `5` | Seconds between polls when waiting for update_deadline. |
| `NUM_CLIENTS` | `6` | Number of NVFlare POC clients (trainers). Job `min_clients` is synced in `setup_poc.sh`. Use `NUM_CLIENTS=20` for 20 clients (register_trainers extends to //Trainer7..//Trainer20; fund those accounts). |
| `TRAINER_URIS` | (optional) | Comma-separated trainer keypair URIs. If unset, default 6 (Dave,Eve,Ferdie,One,Two,Trainer6); if `NUM_CLIENTS` is set, extended with //Trainer7..//TrainerN. |
| `CIFAR10_TRAIN_SUBSET` | `500` | Max training samples per client (Subset of CIFAR10). |
| `CIFAR10_TEST_SUBSET` | `200` | Max test samples per client. |

**finalize_round failed: FundsUnavailable:** The aggregator (e.g. //Bob) does not have enough balance to pay transaction fees. Fund the aggregator at the chain UI (e.g. http://172.206.89.225:8080).

## Standalone FL (no blockchain): MNIST + SimpleCNN

To run **independent NVFlare FL** with no chain: 1 server + N clients (default 10), **SimpleCNN** on **MNIST**.

1. **Prepare workspace** (creates `nvflare_standalone_workspace` with N sites and job `mnist_simplecnn`):
   ```bash
   cd ~/nvflare_dev/blockchain_nvflare_poc
   ./setup_standalone_fl.sh
   ```
   Optional: `NUM_CLIENTS=20 ./setup_standalone_fl.sh` or `NUM_CLIENTS=50 ./setup_standalone_fl.sh`.

2. **Start POC and run training** (starts server + clients, submits job, waits for completion):
   ```bash
   ./run_standalone_fl.sh
   ```
   Or start only: `NVFLARE_POC_WORKSPACE=$PWD/nvflare_standalone_workspace ./start_nvflare.sh`, then submit the job from the admin UI or run `python3 run_standalone_mnist_job.py` (with `NVFLARE_POC_WORKSPACE` set to the standalone workspace).

3. **Benchmark and evaluation (e.g. 50 clients):** Run the full benchmark (setup + POC + submit + timing + final model evaluation). Results go to `benchmark_results/` (JSON per run + CSV summary).
   ```bash
   ./run_benchmark.sh              # default: 50 clients
   NUM_CLIENTS=20 ./run_benchmark.sh
   ```
   See `docs/EVALUATION_METRICS_AND_PAPER.md` §6 for metrics and CSV columns. **SSL:** The scripts set `NVFLARE_POC_SSL_VERIFY=0` so the admin client skips server cert verification when connecting to the POC (NVFlare `net_utils.py` checks this env). With **more clients** (e.g. 20+), the server needs longer to start; the script waits 90s for 11–50 clients and 120s for 51–200. If you still see "Connection reset by peer", set a longer wait, e.g. `POC_WAIT_SEC=120 NUM_CLIENTS=20 ./run_benchmark.sh`. For 500 clients the script waits 180s; if it still cannot connect, start POC separately, wait 2–3 min, then run `python3 benchmark_standalone_fl.py` with `NVFLARE_POC_WORKSPACE` set.

Job: `jobs/mnist_simplecnn` — SimpleCNN (2 conv + 2 FC), MNIST, 5 rounds, `min_clients` set from `NUM_CLIENTS`. No blockchain; add validation later if needed.

## GPU and VRAM (8GB)

Training uses **CUDA if available** (`cuda:0`), otherwise CPU. With one GPU (e.g. 8GB VRAM), NVFlare usually runs clients **one at a time** per round, so 8GB is enough for 6 or 20 clients. If you see GPU OOM with many clients, set `CUDA_VISIBLE_DEVICES=""` in the client environment to force CPU, or reduce `CIFAR10_TRAIN_SUBSET` / batch size in the job.

## RoundNotValidating and deadlines

The chain only allows `finalize_round` when the round status is **ValidatingUpdates** or **Finalizing**. Status moves from CollectingUpdates to ValidatingUpdates when **current block > update_deadline**. So if the bridge calls `finalize_round` right after the job (e.g. 3 min later), the chain may still be in CollectingUpdates and return `RoundNotValidating`. The bridge now **waits** until the chain block is >= `update_deadline` (polling every `FINALIZE_WAIT_POLL` seconds) before calling `finalize_round`. Default `UPDATE_DEADLINE_BLOCKS=30` (e.g. ~3 min at 6 s/block) so the round is usually in ValidatingUpdates by the time the job finishes.

## Layout

- `config.py` – Chain and bridge config (subnet_id=1 by default, 172.206.89.225).
- `blockchain_client.py` – SubnetFl client (register_aggregator, register_trainer, start_round, finalize_round).
- `bridge.py` – Bridge loop: chain ↔ NVFlare POC (submit job, wait, download, hash, finalize).
- `jobs/hello_pt_blockchain/` – NVFlare job (CIFAR10 with Subset; min_clients set from NUM_CLIENTS in setup). Small CNN for low RAM/VRAM.
- `Scripts/chain_accounts.txt` – Account mapping (aggregator=Bob, trainers=Dave,Eve,Ferdie,One,Two,Trainer6; for 20 clients fund //Trainer7..//Trainer20).
- `register_trainers.py` – Register trainers on chain (default 6; set NUM_CLIENTS=20 to register //Trainer7..//Trainer20 as well).
- `run_register_trainers.sh` – Run register_trainers with default env.
- `run_poc_and_training.sh` – One command: register trainers, start NVFlare POC, run bridge (1 aggregator + 6 trainers).
- `setup_poc.sh` – POC prepare (default 6 clients) and prepare-jobs-dir.
- `start_nvflare.sh` – Start POC (server + N clients).
- `run_bridge.sh` – Run bridge with default env (aggregator=Bob).

## Chain connection robustness

After the NVFlare job runs (often 2+ minutes), the WebSocket to the chain can idle out. The bridge reconnects to the chain right before `finalize_round` (after the job and hash computation) and retries `start_round` and `finalize_round` up to 3 times on connection/JSON errors, reconnecting before each retry. So a one-off `JSONDecodeError` or dropped connection during `finalize_round` is handled without failing the whole cycle.

## Funding

If you see “insufficient balance” or “1010” from the chain, fund the relevant account via the chain UI: http://172.206.89.225:8080 (Transfer from //Alice or another funded account).

- **Aggregator** (bridge): e.g. `//Aggregator` or `//Bob` (set `AGGREGATOR_MNEMONIC`).
- **Trainers**: for 6 clients fund **//Dave**, **//Eve**, **//Ferdie**, **//One**, **//Two**, **//Trainer6**. For 20 clients also fund **//Trainer7** … **//Trainer20** (see `Scripts/chain_accounts.txt`).

## One command: POC + training (1 aggregator, 6 or 20 trainers)

Account mapping is in **`Scripts/chain_accounts.txt`** (aggregator=Bob, trainers=Dave, Eve, Ferdie, One, Two, Trainer6).

1. **First-time setup:** fund Bob and the 6 trainer accounts at the chain UI, then:
   ```bash
   ./setup_poc.sh
   ```
2. **Run POC and training:**
   ```bash
   ./run_poc_and_training.sh
   ```
   This registers trainers on chain (6 by default, or 20 if `NUM_CLIENTS=20`), starts NVFlare POC (server + N clients) in the background, then runs the bridge. Press Ctrl+C to stop the bridge; run `nvflare poc stop` to stop the POC.

## Multi-trainer (6 or 20 clients) – manual steps

The **number of sites (site-1, site-2, …)** is fixed when you run **setup**: `nvflare poc prepare -n N` creates exactly N clients in the workspace. So to run with **2 sites only** you must run setup with 2 before starting the POC.

**For 2 sites (e.g. to save memory):**
1. Stop any running POC: `pkill -f nvflare`
2. Recreate workspace with 2 clients: **`NUM_CLIENTS=2 ./setup_poc.sh`**
3. Start and run: **`NUM_CLIENTS=2 ./run_poc_and_training.sh`** (or `./start_nvflare.sh` then `./run_bridge.sh`)

**For 6 or 20 sites:** Run `./setup_poc.sh` (6) or `NUM_CLIENTS=20 ./setup_poc.sh` (20), then run the training script with the same NUM_CLIENTS. If you run `NUM_CLIENTS=2 ./run_poc_and_training.sh` but the workspace was created with 6, the script will error and tell you to run `NUM_CLIENTS=2 ./setup_poc.sh` first.

Steps (any N):
1. Fund the trainer accounts (see Funding above and `Scripts/chain_accounts.txt`).
2. Run `./run_register_trainers.sh` (or with SUBNET_ID/ NUM_CLIENTS as needed).
3. Run **`NUM_CLIENTS=N ./setup_poc.sh`** so the POC workspace has N clients (N=2, 6, or 20).
4. Start NVFlare with `./start_nvflare.sh`; N client processes will run.
5. Run the bridge: `./run_bridge.sh`.

## Troubleshooting: WSL crash when job runs

If WSL or Cursor crashes when the job is submitted and the bridge runs (e.g. memory reaches ~6 GB), the cause is usually **total memory**: 1 server + 6 clients + bridge + Cursor all in one environment.

**What the logs showed (from your last run):**
- NVFlare server and all 6 sites started and the job was scheduled. Client logs show the job starting and SubprocessLauncher downloading the job package (~170 MB). Logs stop abruptly during that phase (e.g. around 42% of the download). No Python traceback or OOM message in `log_error.txt`. So the crash is almost certainly **memory** (WSL or Windows killing the VM), not an application error.
- **Where to check next time:**
  - **NVFlare POC (if run via run_poc_and_training.sh):** `cat /tmp/nvflare_poc.log`
  - **Kernel (OOM / kills):** `dmesg | tail -100` and `grep -i oom /var/log/syslog`
  - **NVFlare workspace:**  
    `.../nvflare_poc_workspace/example_project/prod_00/server/log.txt`  
    and `.../site-1/.../log.txt` (and site-2 … site-6) for the last run. Job run folders are named by job UUID (e.g. `0f6a717e-ee74-4762-8fa7-1316130b8b75`).
  - **Windows:** Event Viewer → Windows Logs → Application, or look for WSL / Hyper-V related errors (WSL often doesn’t log OOM inside Linux when the host terminates the VM).

**What to do:**

1. **Run outside Cursor**  
   Run `./run_poc_and_training.sh` (or `./start_nvflare.sh` + `./run_bridge.sh`) from a **normal WSL terminal** (e.g. Windows Terminal), not from Cursor. That avoids Cursor’s memory on top of the POC.

2. **Raise WSL memory limit**  
   WSL2’s default cap can be low. Create or edit **`.wslconfig`** in your Windows user profile (e.g. `C:\Users\<YourUser>\.wslconfig`):
   ```ini
   [wsl2]
   memory=12GB
   swap=4GB
   ```
   Then in PowerShell (Admin): `wsl --shutdown`, and reopen WSL. Increase `memory` if you have 16GB+ RAM.

3. **Use fewer clients to confirm**  
   Try 2 clients so total processes (and memory) are lower:
   ```bash
   NUM_CLIENTS=2 ./setup_poc.sh
   # Start POC, then run bridge (with 2 clients only site-1 and site-2 need to be up)
   ```
   If that runs without crashing, the issue is total memory with 6 clients.

4. **Keep data subset small**  
   The job already uses a small CIFAR10 subset (500 train / 200 test) and a small model. Don’t set `CIFAR10_TRAIN_SUBSET=50000` unless you have more RAM.

5. **Capture logs before a crash**  
   From a WSL terminal (outside Cursor):
   ```bash
   ./run_poc_and_training.sh 2>&1 | tee ~/poc_run.log
   ```
   If WSL dies, the log may be truncated but you’ll have everything up to the crash.

## Optional: trainer on chain

To have each trainer also report to the chain (`submit_model_update`) for rewards, you would add a custom executor or side process that calls `blockchain_client.submit_model_update` with the trainer’s keypair after training. This POC focuses on the aggregator bridge; trainer registration on chain is done via `register_trainers.py`.
