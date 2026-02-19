"""
Blockchain client for SubnetFl pallet (sora-solochain).
Uses exact storage and call names from pallets/subnet-fl/src/lib.rs.
Blockchain runs remotely; this module only connects via RPC.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException

from config import ChainConfig, CHAIN_UI_URL

log = logging.getLogger(__name__)

# Retry chain RPC calls after reconnect when connection may have gone stale (e.g. after long job).
CHAIN_RPC_RETRIES = 3
CONNECTION_ERROR_TYPES = (SubstrateRequestException, json.JSONDecodeError, ConnectionError, OSError)


def _log_funding_hint(account_ss58: str, role: str) -> None:
    log.error(
        "Account %s has insufficient balance to pay fees and/or stake (%s). "
        "Fund it via the chain UI: %s — use Transfer or get tokens from a genesis account (e.g. //Alice).",
        account_ss58,
        role,
        CHAIN_UI_URL,
    )

HASH_LEN = 32


def _ensure_hash(h: bytes) -> bytes:
    if len(h) >= HASH_LEN:
        return bytes(h[:HASH_LEN])
    return h.ljust(HASH_LEN, b"\x00")


def _hash_to_hex_list(h: bytes) -> List[int]:
    h = _ensure_hash(h)
    return list(h)


class SubnetFlClient:
    def __init__(self, config: ChainConfig, keypair: Optional[Keypair] = None):
        self.config = config
        self.keypair = keypair
        self.substrate = self._new_connection()
        if keypair:
            log.info("Blockchain client address: %s", keypair.ss58_address)

    def _new_connection(self) -> SubstrateInterface:
        return SubstrateInterface(
            url=self.config.rpc_url,
            ss58_format=self.config.ss58_format,
        )

    def reconnect(self) -> None:
        """Replace the WebSocket connection with a fresh one. Call after long gaps (e.g. after NVFlare job) to avoid idle timeout / stale connection."""
        try:
            if getattr(self.substrate, "close", None):
                self.substrate.close()
        except Exception:
            pass
        self.substrate = self._new_connection()
        log.info("Chain connection reconnected to %s", self.config.rpc_url)

    def get_block_number(self) -> int:
        """Current (chain head) block number."""
        block_hash = self.substrate.get_chain_head()
        block = self.substrate.get_block_number(block_hash) if block_hash else 0
        return block or 0

    def get_subnet(self, subnet_id: int) -> Optional[Dict[str, Any]]:
        result = self.substrate.query(
            module="SubnetFl",
            storage_function="Subnets",
            params=[subnet_id],
        )
        return result.value if result else None

    def get_current_round(self, subnet_id: int) -> int:
        result = self.substrate.query(
            module="SubnetFl",
            storage_function="CurrentRound",
            params=[subnet_id],
        )
        return result.value if result is not None else 0

    def get_round_info(self, subnet_id: int, round_num: int) -> Optional[Dict[str, Any]]:
        result = self.substrate.query(
            module="SubnetFl",
            storage_function="RoundInfo",
            params=[subnet_id, round_num],
        )
        return result.value if result else None

    def get_subnet_members(self, subnet_id: int) -> Optional[Dict[str, Any]]:
        result = self.substrate.query(
            module="SubnetFl",
            storage_function="SubnetMembersStorage",
            params=[subnet_id],
        )
        return result.value if result else None

    def get_model_commit(
        self, subnet_id: int, round_num: int, trainer_ss58: str
    ) -> Optional[Dict[str, Any]]:
        result = self.substrate.query(
            module="SubnetFl",
            storage_function="ModelCommits",
            params=[subnet_id, round_num, trainer_ss58],
        )
        return result.value if result else None

    def subnet_status_active(self, subnet_id: int) -> bool:
        sub = self.get_subnet(subnet_id)
        if not sub:
            return False
        status = sub.get("status")
        if isinstance(status, dict):
            return status.get("Active") is not None
        return status == 1 or status == "Active"

    def _ensure_keypair(self) -> Keypair:
        if not self.keypair:
            raise RuntimeError("This call requires a keypair")
        return self.keypair

    def register_aggregator(self, subnet_id: int, stake_amount: int) -> bool:
        kp = self._ensure_keypair()
        call = self.substrate.compose_call(
            call_module="SubnetFl",
            call_function="register_aggregator",
            call_params={"subnet_id": subnet_id, "stake_amount": stake_amount},
        )
        extrinsic = self.substrate.create_signed_extrinsic(call=call, keypair=kp)
        try:
            receipt = self.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
        except SubstrateRequestException as e:
            err = str(e).lower()
            if "1010" in str(e) or "balance" in err or "fee" in err:
                _log_funding_hint(kp.ss58_address, "aggregator")
            raise
        if receipt.is_success:
            log.info("register_aggregator success, block %s", receipt.block_hash)
            return True
        log.error("register_aggregator failed: %s", getattr(receipt, "error_message", receipt))
        return False

    def start_round(
        self,
        subnet_id: int,
        initial_global_model_hash: bytes,
        update_deadline: int,
        validation_deadline: int,
    ) -> bool:
        kp = self._ensure_keypair()
        last_err = None
        for attempt in range(CHAIN_RPC_RETRIES):
            try:
                call = self.substrate.compose_call(
                    call_module="SubnetFl",
                    call_function="start_round",
                    call_params={
                        "subnet_id": subnet_id,
                        "initial_global_model_hash": "0x" + _ensure_hash(initial_global_model_hash).hex(),
                        "update_deadline": update_deadline,
                        "validation_deadline": validation_deadline,
                    },
                )
                extrinsic = self.substrate.create_signed_extrinsic(call=call, keypair=kp)
                receipt = self.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
                if receipt.is_success:
                    log.info("start_round success, block %s", receipt.block_hash)
                    return True
                log.error("start_round failed: %s", getattr(receipt, "error_message", receipt))
                return False
            except CONNECTION_ERROR_TYPES as e:
                last_err = e
                if attempt < CHAIN_RPC_RETRIES - 1:
                    log.warning("start_round chain error (attempt %s/%s): %s; reconnecting.", attempt + 1, CHAIN_RPC_RETRIES, e)
                    self.reconnect()
                else:
                    raise
        if last_err is not None:
            raise last_err
        return False

    def finalize_round(
        self,
        subnet_id: int,
        round_num: int,
        aggregated_model_hash: bytes,
    ) -> bool:
        kp = self._ensure_keypair()
        last_err = None
        for attempt in range(CHAIN_RPC_RETRIES):
            try:
                call = self.substrate.compose_call(
                    call_module="SubnetFl",
                    call_function="finalize_round",
                    call_params={
                        "subnet_id": subnet_id,
                        "round": round_num,
                        "aggregated_model_hash": "0x" + _ensure_hash(aggregated_model_hash).hex(),
                    },
                )
                extrinsic = self.substrate.create_signed_extrinsic(call=call, keypair=kp)
                receipt = self.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
                if receipt.is_success:
                    log.info("finalize_round success, block %s", receipt.block_hash)
                    return True
                log.error("finalize_round failed: %s", getattr(receipt, "error_message", receipt))
                return False
            except CONNECTION_ERROR_TYPES as e:
                last_err = e
                if attempt < CHAIN_RPC_RETRIES - 1:
                    log.warning("finalize_round chain error (attempt %s/%s): %s; reconnecting.", attempt + 1, CHAIN_RPC_RETRIES, e)
                    self.reconnect()
                else:
                    raise
        if last_err is not None:
            raise last_err
        return False
