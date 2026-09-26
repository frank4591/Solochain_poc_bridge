#!/usr/bin/env python3
"""
Register multiple trainer nodes on the chain (SubnetFl) for the given subnet_id.
Uses dev URIs by default (//Charlie, //Dave, //Eve, //Ferdie, //One, //Two) for 6 trainers.
Fund each trainer account at CHAIN_UI before running (see README).
"""
import logging
import os
import sys

from substrateinterface import Keypair

from config import get_chain_config, DEFAULT_SUBNET_ID, MIN_TRAINER_STAKE, CHAIN_UI_URL
from blockchain_client import SubnetFlClient

log = logging.getLogger(__name__)

# Default 6 trainers per chain_accounts.txt: Dave, Eve, Ferdie, One, Two, Trainer6 (Charlie = validator)
DEFAULT_TRAINER_URIS = [
    "//Dave",
    "//Eve",
    "//Ferdie",
    "//One",
    "//Two",
    "//Trainer6",
]
DEFAULT_MODEL_SPEC = b"cifar10"


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    config = get_chain_config()
    subnet_id = int(os.getenv("SUBNET_ID", str(DEFAULT_SUBNET_ID)))
    model_spec = os.getenv("TRAINER_MODEL_SPEC", DEFAULT_MODEL_SPEC.decode()).encode()[:64]

    # Trainer URIs: env TRAINER_URIS="//Dave,//Eve,..." or default 6; extend to NUM_CLIENTS (e.g. 20) with //Trainer7..//TrainerN
    uris_str = os.getenv("TRAINER_URIS")
    if uris_str:
        trainer_uris = [u.strip() for u in uris_str.split(",") if u.strip()]
    else:
        trainer_uris = list(DEFAULT_TRAINER_URIS)
    num_clients_env = os.getenv("NUM_CLIENTS")
    if num_clients_env and not uris_str:
        try:
            n = int(num_clients_env)
            while len(trainer_uris) < n:
                trainer_uris.append(f"//Trainer{len(trainer_uris) + 1}")
            trainer_uris = trainer_uris[:n]
        except ValueError:
            pass

    if not trainer_uris:
        log.error("No trainer URIs. Set TRAINER_URIS or use default (and optionally NUM_CLIENTS for more).")
        sys.exit(1)

    log.info("Registering %s trainers on subnet_id=%s", len(trainer_uris), subnet_id)

    ok = 0
    for i, uri in enumerate(trainer_uris):
        try:
            kp = Keypair.create_from_uri(uri)
        except Exception as e:
            log.error("Trainer %s: invalid URI %s: %s", i + 1, uri, e)
            continue
        try:
            client = SubnetFlClient(config, keypair=kp)
        except (ConnectionRefusedError, OSError) as e:
            log.error(
                "Cannot connect to chain at %s. Start the chain node or set BLOCKCHAIN_RPC. %s",
                config.rpc_url,
                e,
            )
            log.info("Chain UI: %s", CHAIN_UI_URL)
            sys.exit(1)
        try:
            if client.register_trainer(subnet_id, model_spec, MIN_TRAINER_STAKE):
                log.info("Trainer %s registered: %s (%s)", i + 1, kp.ss58_address, uri)
                ok += 1
            else:
                log.warning("Trainer %s (%s): register_trainer returned False (may already be registered).", i + 1, uri)
        except Exception as e:
            log.warning("Trainer %s (%s): %s", i + 1, uri, e)

    log.info("Done: %s/%s trainers registered.", ok, len(trainer_uris))
    if ok < len(trainer_uris):
        sys.exit(1)


if __name__ == "__main__":
    main()
