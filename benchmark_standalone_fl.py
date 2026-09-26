#!/usr/bin/env python3
"""
Benchmark standalone FL (MNIST + SimpleCNN): submit job, time run, evaluate final model.
Writes results to benchmark_results/ (JSON + CSV). No blockchain.
Usage:
  NUM_CLIENTS=50 ./run_benchmark.sh   # setup, start POC, run this, save results
  Or with POC already running: NVFLARE_POC_WORKSPACE=... python benchmark_standalone_fl.py
"""
import json
import logging
import os
import sys
import time
from datetime import datetime

from nvflare.fuel.flare_api.flare_api import new_secure_session
from nvflare.fuel.flare_api.api_spec import MonitorReturnCode

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESULTS_DIR = "benchmark_results"


def _find_global_model_pt(result_dir: str) -> str:
    """Locate FL_global_model.pt under result_dir (recursive)."""
    for root, _dirs, files in os.walk(result_dir):
        for f in files:
            if f == "FL_global_model.pt":
                return os.path.join(root, f)
    raise FileNotFoundError(f"FL_global_model.pt not found under {result_dir}")


def evaluate_mnist_model(model_pt_path: str, num_test_samples: int = 2000) -> float:
    """Load SimpleCNN from model_pt_path, evaluate on MNIST test set; return accuracy %."""
    # Import from job's custom code
    job_custom = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "jobs", "mnist_simplecnn", "app", "custom"
    )
    if job_custom not in sys.path:
        sys.path.insert(0, job_custom)
    from simple_cnn import SimpleCNN

    import torch
    import torchvision
    import torchvision.transforms as transforms

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,)),
    ])
    testset = torchvision.datasets.MNIST(
        root=os.environ.get("MNIST_ROOT", "/tmp/nvflare/data"),
        train=False,
        download=True,
        transform=transform,
    )
    if num_test_samples and num_test_samples < len(testset):
        import random
        random.seed(42)
        indices = random.sample(range(len(testset)), num_test_samples)
        testset = torch.utils.data.Subset(testset, indices)
    testloader = torch.utils.data.DataLoader(testset, batch_size=64, shuffle=False, num_workers=0)

    net = SimpleCNN()
    state = torch.load(model_pt_path, map_location=device)
    if isinstance(state, dict):
        # NVFlare PT persistor saves with key "model"; some checkpoints use "state_dict"
        state = state.get("model", state.get("state_dict", state))
    net.load_state_dict(state, strict=False)
    net.to(device)
    net.eval()

    correct, total = 0, 0
    with torch.no_grad():
        for data in testloader:
            images, labels = data[0].to(device), data[1].to(device)
            outputs = net(images)
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
    return 100.0 * correct / total if total else 0.0


def main():
    workspace = os.environ.get("NVFLARE_POC_WORKSPACE")
    if not workspace or not os.path.isdir(workspace):
        log.error("NVFLARE_POC_WORKSPACE not set or not a directory.")
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_job = os.path.join(script_dir, "jobs", "mnist_simplecnn")
    job_path = os.environ.get("NVFLARE_JOB_PATH", default_job)
    if not os.path.isdir(job_path):
        log.error("Job path not a directory: %s", job_path)
        sys.exit(1)

    num_clients = int(os.environ.get("NUM_CLIENTS", "10"))
    admin_username = os.environ.get("NVFLARE_ADMIN_USERNAME", "admin@nvidia.com")
    admin_dir = os.path.join(workspace, "example_project", "prod_00", admin_username)
    if not os.path.isdir(admin_dir):
        log.error("Admin startup kit not found at %s. Run setup (e.g. ./setup_standalone_fl.sh) first.", admin_dir)
        sys.exit(1)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {
        "run_id": run_id,
        "num_clients": num_clients,
        "job_id": None,
        "status": "failed",
        "total_time_sec": None,
        "final_accuracy_pct": None,
        "result_path": None,
    }

    # Retry initial connection: server may still be starting (e.g. "Connection reset by peer")
    connect_retries = int(os.environ.get("BENCHMARK_CONNECT_RETRIES", "5"))
    connect_retry_wait = float(os.environ.get("BENCHMARK_CONNECT_RETRY_WAIT", "10"))
    sess = None
    for attempt in range(connect_retries):
        try:
            sess = new_secure_session(
                username=admin_username,
                startup_kit_location=admin_dir,
                timeout=15.0,
            )
            sess.try_connect(15.0)
            break
        except Exception as e:
            if attempt + 1 >= connect_retries:
                log.error("Cannot connect to NVFlare server after %s attempts. Is POC running? %s", connect_retries, e)
                with open(os.path.join(RESULTS_DIR, f"benchmark_{run_id}.json"), "w") as f:
                    json.dump(results, f, indent=2)
                sys.exit(1)
            log.warning("Connect attempt %s/%s failed (%s); retrying in %ss...", attempt + 1, connect_retries, e, connect_retry_wait)
            time.sleep(connect_retry_wait)

    log.info("Submitting job (num_clients=%s): %s", num_clients, job_path)
    t_start = time.perf_counter()
    job_id = sess.submit_job(job_path)
    results["job_id"] = job_id

    timeout_sec = float(os.environ.get("JOB_MONITOR_TIMEOUT", "1200"))
    poll_interval = float(os.environ.get("JOB_POLL_INTERVAL", "5"))
    max_reconnect_retries = 5
    reconnect_wait_sec = 3

    def reconnect_session():
        nonlocal sess
        try:
            sess.close()
        except Exception:
            pass
        new_sess = new_secure_session(
            username=admin_username,
            startup_kit_location=admin_dir,
            timeout=10.0,
        )
        new_sess.try_connect(10.0)
        sess = new_sess

    rc, meta = None, None
    for attempt in range(max_reconnect_retries):
        try:
            rc, meta = sess.monitor_job_and_return_job_meta(
                job_id, timeout=timeout_sec, poll_interval=poll_interval
            )
            break
        except (ConnectionError, OSError) as e:
            if attempt + 1 >= max_reconnect_retries:
                log.error("Connection lost during job monitor; max retries reached: %s", e)
                raise
            log.warning(
                "Connection lost during monitor (attempt %s/%s): %s; reconnecting in %ss...",
                attempt + 1, max_reconnect_retries, e, reconnect_wait_sec,
            )
            time.sleep(reconnect_wait_sec)
            reconnect_session()

    t_end = time.perf_counter()
    results["total_time_sec"] = round(t_end - t_start, 2)

    if rc != MonitorReturnCode.JOB_FINISHED:
        log.error("Job did not finish: %s", rc)
        results["status"] = str(rc)
        with open(os.path.join(RESULTS_DIR, f"benchmark_{run_id}.json"), "w") as f:
            json.dump(results, f, indent=2)
        sess.close()
        sys.exit(1)

    result_path = None
    for attempt in range(max_reconnect_retries):
        try:
            result_path = sess.download_job_result(job_id)
            break
        except (ConnectionError, OSError) as e:
            if attempt + 1 >= max_reconnect_retries:
                log.error("Connection lost during download; max retries reached: %s", e)
                raise
            log.warning(
                "Connection lost during download (attempt %s/%s): %s; reconnecting in %ss...",
                attempt + 1, max_reconnect_retries, e, reconnect_wait_sec,
            )
            time.sleep(reconnect_wait_sec)
            reconnect_session()
    results["result_path"] = result_path
    results["status"] = "completed"
    sess.close()

    # Evaluate final model if present
    try:
        model_path = _find_global_model_pt(result_path)
        acc = evaluate_mnist_model(model_path)
        results["final_accuracy_pct"] = round(acc, 2)
        log.info("Final model accuracy on MNIST test set: %.2f%%", acc)
    except FileNotFoundError as e:
        log.warning("Could not evaluate final model: %s", e)
    except Exception as e:
        log.warning("Evaluation failed: %s", e)

    # Write results
    json_path = os.path.join(script_dir, RESULTS_DIR, f"benchmark_{run_id}.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    log.info("Results written to %s", json_path)

    # Append CSV row for easy comparison
    csv_path = os.path.join(script_dir, RESULTS_DIR, "benchmark_results.csv")
    write_header = not os.path.isfile(csv_path)
    with open(csv_path, "a") as f:
        if write_header:
            f.write("run_id,num_clients,job_id,status,total_time_sec,final_accuracy_pct\n")
        f.write(
            f"{run_id},{num_clients},{job_id},{results['status']},{results['total_time_sec']},"
            f"{results.get('final_accuracy_pct') or ''}\n"
        )
    log.info("Appended to %s", csv_path)

    print("\n--- Benchmark summary ---")
    print(f"  Run ID:       {run_id}")
    print(f"  Num clients:  {num_clients}")
    print(f"  Job ID:       {job_id}")
    print(f"  Status:       {results['status']}")
    print(f"  Total time:   {results['total_time_sec']} s")
    print(f"  Test acc:     {results.get('final_accuracy_pct', 'N/A')}%")
    print("------------------------\n")


if __name__ == "__main__":
    main()
