#!/usr/bin/env python3
"""
Submit the MNIST SimpleCNN job to the running NVFlare POC and wait for completion.
No blockchain. Uses NVFLARE_POC_WORKSPACE and NVFLARE_JOB_PATH (default: jobs/mnist_simplecnn).
"""
import os
import sys
import logging
import time
from nvflare.fuel.flare_api.flare_api import new_secure_session
from nvflare.fuel.flare_api.api_spec import MonitorReturnCode

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

def main():
    workspace = os.environ.get("NVFLARE_POC_WORKSPACE")
    if not workspace or not os.path.isdir(workspace):
        log.error("NVFLARE_POC_WORKSPACE not set or not a directory. Set it to the standalone FL workspace.")
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_job = os.path.join(script_dir, "jobs", "mnist_simplecnn")
    job_path = os.environ.get("NVFLARE_JOB_PATH", default_job)
    if not os.path.isdir(job_path):
        log.error("Job path not a directory: %s", job_path)
        sys.exit(1)

    admin_username = os.environ.get("NVFLARE_ADMIN_USERNAME", "admin@nvidia.com")
    admin_dir = os.path.join(workspace, "example_project", "prod_00", admin_username)
    if not os.path.isdir(admin_dir):
        log.error("Admin startup kit not found at %s. Run ./setup_standalone_fl.sh first.", admin_dir)
        sys.exit(1)

    connect_retries = int(os.environ.get("CONNECT_RETRIES", "10"))
    connect_retry_wait = float(os.environ.get("CONNECT_RETRY_WAIT", "3"))
    sess = None
    for attempt in range(connect_retries):
        try:
            sess = new_secure_session(
                username=admin_username,
                startup_kit_location=admin_dir,
                timeout=10.0,
            )
            sess.try_connect(10.0)
            break
        except Exception as e:
            if sess:
                try:
                    sess.close()
                except Exception:
                    pass
            sess = None
            log.warning(
                "Cannot connect to NVFlare server (attempt %d/%d): %s",
                attempt + 1,
                connect_retries,
                e,
            )
            time.sleep(connect_retry_wait)
    if not sess:
        log.error("Cannot connect to NVFlare server after %d attempts.", connect_retries)
        sys.exit(1)

    log.info("Submitting job: %s", job_path)
    job_id = sess.submit_job(job_path)
    log.info("Job submitted: job_id=%s", job_id)

    timeout_sec = float(os.environ.get("JOB_MONITOR_TIMEOUT", "600"))
    poll_interval = float(os.environ.get("JOB_POLL_INTERVAL", "5"))
    monitor_retries = int(os.environ.get("MONITOR_RETRIES", "10"))
    monitor_retry_wait = float(os.environ.get("MONITOR_RETRY_WAIT", "5"))
    rc, meta = None, None
    for attempt in range(monitor_retries):
        try:
            rc, meta = sess.monitor_job_and_return_job_meta(
                job_id, timeout=timeout_sec, poll_interval=poll_interval
            )
            break
        except (ConnectionError, OSError) as e:
            log.warning(
                "Monitor failed (attempt %d/%d): %s",
                attempt + 1,
                monitor_retries,
                e,
            )
            time.sleep(monitor_retry_wait)
    if rc is None:
        log.error("Failed to monitor job after %d attempts.", monitor_retries)
        sys.exit(1)

    if rc != MonitorReturnCode.JOB_FINISHED:
        log.error("Job did not finish: %s", rc)
        sys.exit(1)

    download_retries = int(os.environ.get("DOWNLOAD_RETRIES", "10"))
    download_retry_wait = float(os.environ.get("DOWNLOAD_RETRY_WAIT", "5"))
    result_path = None
    for attempt in range(download_retries):
        try:
            result_path = sess.download_job_result(job_id)
            break
        except (ConnectionError, OSError) as e:
            log.warning(
                "Download failed (attempt %d/%d): %s",
                attempt + 1,
                download_retries,
                e,
            )
            time.sleep(download_retry_wait)
    if not result_path:
        log.error("Failed to download job result after %d attempts.", download_retries)
        sys.exit(1)
    log.info("Job finished. Result downloaded to: %s", result_path)
    sess.close()

if __name__ == "__main__":
    main()
