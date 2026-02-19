"""
Bridge: chain (SubnetFl subnet_id=0) <-> NVFlare POC.
Registers as aggregator, starts rounds on chain, runs NVFlare job per round,
downloads aggregated model, reports hash to chain via finalize_round.
"""
import hashlib
import logging
import os
import sys
import time

from substrateinterface import Keypair
from substrateinterface.exceptions import SubstrateRequestException

from config import get_bridge_config, BridgeConfig, MIN_AGGREGATOR_STAKE, CHAIN_UI_URL
from blockchain_client import SubnetFlClient, _ensure_hash

log = logging.getLogger(__name__)

# NVFlare Session is optional (only when job path and POC workspace exist)
def _nvflare_session(config: BridgeConfig):
    try:
        from nvflare.fuel.flare_api.flare_api import new_secure_session
    except ImportError:
        raise RuntimeError(
            "NVFlare not installed. Activate flockTest and ensure nvflare is installed (e.g. pip install nvflare or use NVFlare repo)."
        )
    poc = config.nvflare_poc_workspace
    if not poc or not os.path.isdir(poc):
        raise RuntimeError(f"NVFLARE_POC_WORKSPACE not a directory: {poc}")
    # POC layout: {workspace}/example_project/prod_00/{admin_username}
    admin_dir = os.path.join(poc, "example_project", "prod_00", config.nvflare_admin_username)
    if not os.path.isdir(admin_dir):
        raise RuntimeError(
            f"Admin startup kit not found at {admin_dir}. Run setup_poc.sh first (nvflare poc prepare -n 1)."
        )
    return new_secure_session(
        username=config.nvflare_admin_username,
        startup_kit_location=admin_dir,
        timeout=10.0,
    )


def _find_global_model_pt(result_dir: str) -> str:
    """Locate FL_global_model.pt under result_dir (recursive)."""
    for root, _dirs, files in os.walk(result_dir):
        for f in files:
            if f == "FL_global_model.pt":
                return os.path.join(root, f)
    raise FileNotFoundError(f"FL_global_model.pt not found under {result_dir}")


def _hash_model_file(path: str) -> bytes:
    """SHA-256 of file contents; return 32 bytes for chain."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.digest()


def run_bridge_once(
    config: BridgeConfig,
    chain_client: SubnetFlClient,
    sess,
) -> bool:
    """Run one bridge cycle: start_round (or use current if RoundAlreadyActive) -> submit job -> wait -> download -> finalize_round."""
    subnet_id = config.subnet_id

    block = chain_client.get_block_number()
    update_deadline = block + config.update_deadline_blocks
    validation_deadline = block + config.validation_deadline_blocks
    initial_hash = bytes(32)

    try:
        started = chain_client.start_round(
            subnet_id,
            initial_hash,
            update_deadline,
            validation_deadline,
        )
    except SubstrateRequestException as e:
        err = str(e)
        if "1010" in err or "balance" in err.lower() or "fee" in err.lower():
            addr = chain_client.keypair.ss58_address if chain_client.keypair else "aggregator SS58"
            log.error(
                "start_round failed: aggregator account has insufficient balance. "
                "Fund it at %s (transfer to %s). Then re-run the bridge.",
                CHAIN_UI_URL,
                addr,
            )
        raise

    if started:
        time.sleep(1)
        round_num = chain_client.get_current_round(subnet_id)
        if round_num <= 0:
            round_num = 1
        log.info("Round started: subnet_id=%s round=%s", subnet_id, round_num)
    else:
        # start_round failed (e.g. RoundAlreadyActive) — complete the active round
        round_num = chain_client.get_current_round(subnet_id)
        if round_num <= 0:
            log.error("start_round failed and no active round (current_round=0)")
            return False
        log.info("Round already active: subnet_id=%s round=%s (running job then finalizing)", subnet_id, round_num)

    job_path = config.nvflare_job_path
    if not job_path or not os.path.isdir(job_path):
        log.error("Job path not a directory: %s", job_path)
        return False

    job_id = sess.submit_job(job_path)
    log.info("Submitted NVFlare job_id=%s", job_id)

    from nvflare.fuel.flare_api.api_spec import MonitorReturnCode

    rc, _meta = sess.monitor_job_and_return_job_meta(
        job_id,
        timeout=config.job_monitor_timeout_sec,
        poll_interval=config.job_poll_interval_sec,
    )
    if rc != MonitorReturnCode.JOB_FINISHED:
        log.error("Job did not finish: %s", rc)
        return False

    result_path = sess.download_job_result(job_id)
    log.info("Job result downloaded to %s", result_path)

    model_path = _find_global_model_pt(result_path)
    agg_hash = _hash_model_file(model_path)
    agg_hash = _ensure_hash(agg_hash)
    log.info("Aggregated model hash: %s", agg_hash.hex())

    # Reconnect to chain before finalize_round to avoid stale WebSocket (idle timeout after long job).
    chain_client.reconnect()
    if not chain_client.finalize_round(subnet_id, round_num, agg_hash):
        log.error("finalize_round failed")
        return False
    log.info("finalize_round success for round %s", round_num)
    return True


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    config = get_bridge_config()

    # Chain keypair (aggregator)
    try:
        kp = Keypair.create_from_uri(config.aggregator_mnemonic)
    except Exception as e:
        log.error("Failed to create keypair from mnemonic: %s", e)
        sys.exit(1)

    # Connect to chain and register
    chain_client = SubnetFlClient(config.chain, keypair=kp)
    if not chain_client.subnet_status_active(config.subnet_id):
        log.warning("Subnet %s not active; attempting register_aggregator anyway.", config.subnet_id)
    try:
        chain_client.register_aggregator(config.subnet_id, MIN_AGGREGATOR_STAKE)
    except Exception as e:
        log.warning("register_aggregator (may already be registered): %s", e)

    # NVFlare session
    sess = _nvflare_session(config)
    try:
        sess.try_connect(10.0)
    except Exception as e:
        log.error("NVFlare session connect failed. Is POC running? nvflare poc start. %s", e)
        sys.exit(1)

    log.info("Bridge running: subnet_id=%s, job=%s", config.subnet_id, config.nvflare_job_path)
    try:
        while True:
            ok = run_bridge_once(config, chain_client, sess)
            if not ok:
                log.error("Bridge cycle failed; retrying in 30s")
                time.sleep(30)
                continue
            log.info("Cycle done; next round in 60s")
            time.sleep(60)
    except KeyboardInterrupt:
        log.info("Bridge stopped by user")
    finally:
        sess.close()


if __name__ == "__main__":
    main()
