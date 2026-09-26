# Evaluation Metrics for Federated Learning + Blockchain (Trustless Coordination)

This document outlines **evaluation dimensions**, **metrics**, **baselines**, and **scaling strategies** for a paper on FL with blockchain-based trustless coordination, aligned with your current POC (NVFlare + SubnetFl chain).

---

## 1. Evaluation Dimensions and Metrics

### 1.1 Communication

| Metric | Definition | What to compare | With current setup |
|--------|------------|------------------|--------------------|
| **On-chain messages per round** | Number of chain transactions per FL round (e.g. `start_round`, `finalize_round`, optional `register_*`) | Your system vs. central-server FL (0 on-chain) vs. other blockchain-FL designs | ✅ Count: 1 `start_round` + 1 `finalize_round` per round; add `register_aggregator`/`register_trainer` once per role |
| **Bytes on-chain per round** | Total payload size of chain calls (e.g. 32-byte hash in `finalize_round`) | Same as above | ✅ Hash = 32 B; extrinsic overhead (account, nonce, signature) is fixed per chain |
| **Off-chain FL traffic** | Client↔server model/gradient uploads (NVFlare) | Same across FL; blockchain adds no extra off-chain FL traffic | ✅ Can measure job duration / bytes from NVFlare job logs if needed |
| **Round-trip latency (chain)** | Time from “submit tx” to “in block” for `start_round` and `finalize_round` | Your chain vs. other L1/L2; vs. central coordinator (no chain) | ✅ Possible: timestamp before/after `submit_extrinsic(..., wait_for_inclusion=True)` in `blockchain_client.py` |

**Baselines:** Central FL (no blockchain); another blockchain-FL design (e.g. different chain or commit scheme).

---

### 1.2 Efficiency

| Metric | Definition | What to compare | With current setup |
|--------|------------|------------------|--------------------|
| **Time per FL round (end-to-end)** | Wall time from round start to round finalization on chain | Your system vs. central FL; vs. different chain params (block time, deadlines) | ✅ Can measure in bridge: from `start_round` success to `finalize_round` success |
| **Blockchain overhead** | Extra time/latency due to chain (wait for blocks, deadlines) | Same | ✅ e.g. “time waiting for block ≥ update_deadline” vs. “pure FL job duration” |
| **Throughput (rounds per hour)** | Completed rounds per hour | Your system vs. central FL | ✅ From bridge: count successful cycles per hour |
| **Gas/fee cost per round** | Cost in native token per `start_round` + `finalize_round` (and registration if applicable) | Your chain vs. other chains; vs. cost of running a central server | ⚠️ Need chain to expose fee or decode from receipt (you have receipt in `blockchain_client`) |
| **FL model quality** | Test accuracy / loss at given round or wall time | Same FL task with/without blockchain coordination | ✅ Job already reports accuracy; can log from job result or server-side metrics |

**Baselines:** Same FL job with central NVFlare (no chain); same chain with different `update_deadline_blocks` / `validation_deadline_blocks`.

---

### 1.3 Resilience and Reliability

| Metric | Definition | What to compare | With current setup |
|--------|------------|------------------|--------------------|
| **Round completion rate** | Fraction of started rounds that reach `finalize_round` success | Your system under failure injection | ✅ Count success vs. failure in bridge over many cycles |
| **Recovery from coordinator disconnect** | Whether rounds can complete after bridge/aggregator disconnects and reconnects | With/without reconnect logic | ✅ You have reconnect/retry in bridge; can log reconnect count and success after reconnect |
| **Recovery from client churn** | Effect of clients leaving/joining (or failing) mid-round | Different `min_clients`; dropout rates | ✅ Vary `min_clients` and number of trainers; measure job success rate and accuracy |
| **Chain reorg / fork handling** | Behavior when chain reorgs (e.g. finalization reverted) | With/without confirmation depth | ⚠️ Optional: wait for N confirmations; measure reorg rate if chain supports it |
| **Byzantine aggregator** | Impact of malicious aggregator (wrong hash, no finalize); detectability on chain | Trusted vs. trustless; slashing/evidence | 📝 Conceptually: your design makes “wrong hash” visible on-chain; can describe and optionally simulate (e.g. wrong hash once, show detection) |

**Baselines:** Same FL with central coordinator (single point of failure); your system with reconnect vs. without.

---

### 1.4 Adversary and Trust

| Metric | Definition | What to compare | With current setup |
|--------|------------|------------------|--------------------|
| **Trust assumptions** | Who must be trusted (clients, aggregator, chain validators)? | Your design vs. central FL vs. other blockchain-FL | 📝 Qualitative: aggregator can’t finalize wrong hash without detection; chain enforces deadlines and order |
| **Detection of equivocation** | Can the system detect aggregator publishing two different hashes for same round? | Your design vs. others | 📝 On-chain state is single; two hashes would be two different rounds or rejected |
| **Slashing / accountability** | Can malicious aggregator be penalized (e.g. stake slashing)? | Depends on chain pallet design | 📝 If SubnetFl has slashing, describe; otherwise “future work” |
| **Client poisoning robustness** | Effect of a fraction of malicious clients on global model; optional: with/without robust aggregation | Accuracy under attack; compare robust vs. FedAvg | ✅ Can run with a subset of “bad” clients (e.g. wrong labels) and measure accuracy drop; optional: add robust aggregator in job |
| **Sybil resistance** | Cost to register many fake trainers (stake, identity) | Your chain’s `MIN_TRAINER_STAKE` and registration rules | 📝 Describe: stake and chain rules; no extra code needed for narrative |

**Baselines:** Central FL (trust in server); FL with verifiable aggregation (e.g. proof of correct aggregation); your system with 0% vs. 10% vs. 20% malicious clients.

---

### 1.5 Scalability (clients and rounds)

| Metric | Definition | What to compare | With current setup |
|--------|------------|------------------|--------------------|
| **On-chain cost vs. number of clients** | Does on-chain cost grow with N? | Your design: typically O(1) per round (one hash); others may log per-client | ✅ You already have O(1) per round; state it and optionally plot “cost vs. N” (constant) |
| **FL convergence vs. N** | Accuracy/loss vs. number of participants (with fixed total data or fixed per-client data) | N=2 vs. N=10 vs. N=100 (simulated) | ✅ With simulated clients (see Section 3): run with different N and log accuracy |
| **Time per round vs. N** | Wall-clock time per round as N grows | NVFlare + chain overhead vs. N | ✅ With simulated clients: measure round duration vs. N |

---

## 2. What You Can Measure With the Current POC (2 Trainers)

With **two physical trainers** and the existing bridge + chain you can already:

- **Count on-chain actions:** e.g. 1 `start_round` + 1 `finalize_round` per round; registration once per aggregator/trainer.
- **Measure round timings:** start round → job submit → job end → wait for block ≥ update_deadline → finalize; total cycle time; “blockchain wait” time.
- **Measure FL quality:** accuracy (and loss if exposed) from the CIFAR10 job (e.g. from job result or NVFlare logs).
- **Measure resilience:** run many cycles; count successes, failures, and reconnect events (you already have reconnect/retry in the bridge).
- **Vary deadlines:** e.g. `UPDATE_DEADLINE_BLOCKS` / `VALIDATION_DEADLINE_BLOCKS` and report impact on round completion and latency.

To make this systematic, add **lightweight logging** in the bridge (and optionally in `blockchain_client`) and dump one line per round (e.g. CSV): round_id, job_id, t_start_round, t_finalize_round, block_at_finalize, success, reconnect_count, etc. Then you can compute all “efficiency” and “resilience” metrics above from logs.

---

## 3. Simulating 100s of Clients (When You Can Run Only 2 Physical Trainers)

You have three main options.

### 3.1 Option A: FL simulator with “virtual” clients (recommended for 100+ clients)

Run a **single process** that simulates many clients using the same FL algorithm (e.g. FedAvg) and optionally the same model/dataset as your job:

- **Idea:** One script that loads CIFAR10 (or same data split), creates N “virtual” clients, each with a local dataset partition; each round: each client trains locally, then you aggregate (e.g. average) and broadcast the global model; repeat for many rounds.
- **Pros:** No need for 100 NVFlare sites; easy to scale to 100, 500, 1000 clients; full control over data split (IID/non-IID), dropout, and poisoning.
- **Cons:** Not the real NVFlare + blockchain stack; you’re measuring “FL convergence vs. N” and “scalability of the algorithm,” not real network/coordinator behavior.
- **Use in paper:** “We evaluate FL convergence and scalability in simulation with N ∈ {2, 10, 50, 100, 200} clients; our real deployment uses N=2 and matches the same FL algorithm and model.”

**Tools:** Custom PyTorch script (simple), or **Flower** (e.g. `flwr.simulation`), **FLSim** (NVIDIA), or **FedML** simulation mode. You can reuse your `Net`, data loading, and training loop from `cifar10_fl.py`.

### 3.2 Option B: Many lightweight NVFlare clients on one machine

Run **many NVFlare client processes** (e.g. 10–20) on the same machine, each as a separate “site”:

- **Idea:** Start 20 (or more) NVFlare clients, each with a small partition of CIFAR10 (or synthetic data); set `min_clients` to the desired number; run the same job and bridge.
- **Pros:** Real NVFlare + real blockchain; real communication and coordinator behavior.
- **Cons:** Resource-bound (CPU/memory); 100 clients on one machine may be impractical; you can still push to 10–20 and report “up to N=20 in real deployment.”

**With current setup:** You already have `NUM_CLIENTS` and `register_trainers`; increase `NUM_CLIENTS` and run multiple clients on the same host (different ports) to test 10–20.

### 3.3 Option C: Hybrid – real stack for “system” metrics, simulator for “scaling” metrics

- **Real stack (2–20 clients):** Report on-chain messages, round latency, round completion rate, reconnect recovery, and FL accuracy with 2 (and optionally 10–20) trainers.
- **Simulator (100s of clients):** Report accuracy vs. N, time per round vs. N, and optionally robustness to dropout/poisoning with N up to 100–500 in simulation.

This keeps the paper honest (“real deployment: N=2 or N=20; scaling: simulation up to N=200”) and still gives strong evaluation.

---

## 4. Suggested Baselines and Comparisons

- **Central FL (no blockchain):** Same NVFlare job, same dataset/model, no chain; compare round duration, throughput, and accuracy. Shows “cost of trustlessness.”
- **Your system with different chain parameters:** e.g. longer vs. shorter `update_deadline_blocks`; show impact on round completion and latency.
- **Your system with/without reconnect:** Demonstrate that reconnect/retry improves round completion under connection loss.
- **Malicious clients (if you add poisoning):** Same FL task with 0% vs. 10% vs. 20% label-flipped (or gradient) attackers; with/without robust aggregation.
- **Other blockchain-FL (if available):** Compare on-chain messages and latency with another design (different chain or commit pattern).

---

## 5. Minimal Instrumentation You Can Add Now

Below is a minimal set of additions so you can **create the metrics** from the current setup without changing the rest of the flow.

1. **Bridge: per-round CSV log**  
   For each cycle, append one row:  
   `round_num, job_id, t_start_round, t_submit_job, t_job_finished, t_finalize_round, block_at_finalize, success, nvflare_reconnect_count`

2. **Blockchain client: optional latency**  
   For `start_round` and `finalize_round`, record time before and after `submit_extrinsic(..., wait_for_inclusion=True)` and either log or return it so the bridge can write it to the CSV.

3. **Job result: accuracy/loss**  
   Parse the downloaded job result (or NVFlare job meta) for final accuracy (and loss if available) and either log it in the bridge or write it to the same CSV (e.g. `accuracy_last_round`).

4. **Reconnect counter**  
   In the bridge, increment a counter on each `_reconnect_nvflare` call and include it in the per-round row as `nvflare_reconnect_count`.

With that CSV you can compute:

- **Efficiency:** round duration, blockchain wait time, rounds per hour.
- **Resilience:** success rate, reconnect rate.
- **Communication:** you already know 1 start + 1 finalize per round; optional: log extrinsic sizes if needed.

If you want, the next step is to add this instrumentation (bridge CSV + optional timing in `blockchain_client` + optional accuracy from job result) in your repo so you can run experiments and plug numbers directly into the paper.

---

## 6. Standalone FL benchmarking (50 clients, MNIST + SimpleCNN)

For **evaluation and benchmarking without blockchain**, use the standalone FL setup with configurable client count (e.g. 50):

1. **Run benchmark (default 50 clients):**
   ```bash
   cd ~/nvflare_dev/blockchain_nvflare_poc
   ./run_benchmark.sh
   ```
   This will: (1) run `setup_standalone_fl.sh` with `NUM_CLIENTS=50`, (2) start the POC in the background, (3) run `benchmark_standalone_fl.py` to submit the MNIST SimpleCNN job, time the run, evaluate the final model on the MNIST test set, and write results.

2. **Results** are written under `benchmark_results/`:
   - `benchmark_YYYYMMDD_HHMMSS.json` — run_id, num_clients, job_id, status, total_time_sec, final_accuracy_pct, result_path.
   - `benchmark_results.csv` — one row per run (run_id, num_clients, job_id, status, total_time_sec, final_accuracy_pct) for easy comparison across runs.

3. **Vary client count:** e.g. `NUM_CLIENTS=20 ./run_benchmark.sh` or `NUM_CLIENTS=100 ./run_benchmark.sh` (ensure your machine can run that many client processes).

4. **Metrics collected:** total job time (submit → completion), final test accuracy (by loading the downloaded global model and evaluating on MNIST), status. Use these for efficiency and model-quality comparisons (e.g. time and accuracy vs. number of clients).
