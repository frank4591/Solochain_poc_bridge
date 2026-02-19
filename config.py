"""
Configuration for blockchain–NVFlare POC bridge.
Chain at 172.206.89.225; subnet_id = 0; 1 aggregator, 1 trainer.
"""
import os
from dataclasses import dataclass
from typing import Optional

# Chain constants (must match sora-solochain runtime)
SS58_FORMAT = 42
UNIT = 1_000_000_000_000
MIN_AGGREGATOR_STAKE = 100 * UNIT
MIN_TRAINER_STAKE = 100 * UNIT

# Chain RPC and UI
DEFAULT_BLOCKCHAIN_RPC = "ws://172.206.89.225:9944"
CHAIN_UI_URL = "http://172.206.89.225:8080"

# POC: 1 aggregator (bridge), 1 subnet (subnet_id=0), 1 trainer
DEFAULT_SUBNET_ID = 0
DEFAULT_UPDATE_DEADLINE_BLOCKS = 100
DEFAULT_VALIDATION_DEADLINE_BLOCKS = 200


@dataclass
class ChainConfig:
    rpc_url: str
    ss58_format: int = SS58_FORMAT
    unit: int = UNIT
    min_aggregator_stake: int = MIN_AGGREGATOR_STAKE
    min_trainer_stake: int = MIN_TRAINER_STAKE


@dataclass
class BridgeConfig:
    chain: ChainConfig
    subnet_id: int = DEFAULT_SUBNET_ID
    aggregator_mnemonic: str = "//Aggregator"  #   export AGGREGATOR_MNEMONIC="//Bob"
    update_deadline_blocks: int = DEFAULT_UPDATE_DEADLINE_BLOCKS
    validation_deadline_blocks: int = DEFAULT_VALIDATION_DEADLINE_BLOCKS
    # NVFlare POC: admin startup kit and job path
    nvflare_poc_workspace: Optional[str] = None  # set from NVFLARE_POC_WORKSPACE
    nvflare_job_path: Optional[str] = None
    nvflare_admin_username: str = "admin@nvidia.com"
    job_monitor_timeout_sec: float = 600.0
    job_poll_interval_sec: float = 5.0


def get_chain_config() -> ChainConfig:
    return ChainConfig(
        rpc_url=os.getenv("BLOCKCHAIN_RPC", DEFAULT_BLOCKCHAIN_RPC),
        ss58_format=SS58_FORMAT,
    )


def get_bridge_config() -> BridgeConfig:
    root = os.path.dirname(os.path.abspath(__file__))
    default_job = os.path.join(root, "jobs", "hello_pt_blockchain")
    return BridgeConfig(
        chain=get_chain_config(),
        subnet_id=int(os.getenv("SUBNET_ID", str(DEFAULT_SUBNET_ID))),
        aggregator_mnemonic=os.getenv("AGGREGATOR_MNEMONIC", "//Aggregator"),
        update_deadline_blocks=int(os.getenv("UPDATE_DEADLINE_BLOCKS", str(DEFAULT_UPDATE_DEADLINE_BLOCKS))),
        validation_deadline_blocks=int(os.getenv("VALIDATION_DEADLINE_BLOCKS", str(DEFAULT_VALIDATION_DEADLINE_BLOCKS))),
        nvflare_poc_workspace=os.getenv("NVFLARE_POC_WORKSPACE") or os.path.join(os.path.dirname(root), "nvflare_poc_workspace"),
        nvflare_job_path=os.getenv("NVFLARE_JOB_PATH", default_job),
        nvflare_admin_username=os.getenv("NVFLARE_ADMIN_USERNAME", "admin@nvidia.com"),
        job_monitor_timeout_sec=float(os.getenv("JOB_MONITOR_TIMEOUT", "600")),
        job_poll_interval_sec=float(os.getenv("JOB_POLL_INTERVAL", "5")),
    )
