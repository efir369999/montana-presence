#!/usr/bin/env python3
"""
Genesis Block Generator for Proof of Time Testnet

Creates the genesis block with:
- Initial VDF proof (iteration 0)
- Founder allocations
- Testnet faucet
- Validator rewards pool
"""

import json
import time
import hashlib
import struct
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from crypto import sha256, sha256d, Ed25519
from structures import Block, BlockHeader, Transaction, TxType


# ============================================================================
# TESTNET GENESIS PARAMETERS
# ============================================================================

GENESIS_TIMESTAMP = int(time.time())
CHAIN_ID = 1001
NETWORK_NAME = "pot-testnet-1"

# Initial token distribution (1 billion total)
TOTAL_SUPPLY = 1_000_000_000

# Allocations
FOUNDER_PERCENT = 0.10      # 10% = 100M
FAUCET_PERCENT = 0.20       # 20% = 200M
REWARDS_PERCENT = 0.70      # 70% = 700M

# Genesis addresses (deterministic from seed)
GENESIS_SEED = b"Proof of Time Testnet Genesis 2025"


def generate_genesis_keypair(role: str) -> tuple:
    """Generate deterministic keypair for genesis role."""
    # Use seed to create deterministic keypair
    seed = sha256(GENESIS_SEED + role.encode())[:32]
    # Ed25519 uses nacl which can derive from seed
    import nacl.signing
    signing_key = nacl.signing.SigningKey(seed)
    secret_key = signing_key.encode()
    public_key = signing_key.verify_key.encode()
    return public_key, secret_key


def create_genesis_block() -> dict:
    """Create the genesis block."""

    # Generate genesis addresses
    founder_pub, founder_priv = generate_genesis_keypair("founder")
    faucet_pub, faucet_priv = generate_genesis_keypair("faucet")
    rewards_pub, rewards_priv = generate_genesis_keypair("rewards")

    # Calculate allocations
    founder_amount = int(TOTAL_SUPPLY * FOUNDER_PERCENT)
    faucet_amount = int(TOTAL_SUPPLY * FAUCET_PERCENT)
    rewards_amount = int(TOTAL_SUPPLY * REWARDS_PERCENT)

    # Genesis transactions
    genesis_txs = [
        {
            "type": "GENESIS",
            "recipient": founder_pub.hex(),
            "amount": founder_amount,
            "memo": "Founder allocation"
        },
        {
            "type": "GENESIS",
            "recipient": faucet_pub.hex(),
            "amount": faucet_amount,
            "memo": "Testnet faucet"
        },
        {
            "type": "GENESIS",
            "recipient": rewards_pub.hex(),
            "amount": rewards_amount,
            "memo": "Validator rewards pool"
        }
    ]

    # Genesis VDF proof (placeholder - actual proof computed at block 1)
    genesis_vdf = {
        "input": sha256(b"genesis").hex(),
        "output": sha256(b"genesis_vdf_output").hex(),
        "iterations": 0,
        "proof": None
    }

    # Genesis header
    genesis_header = {
        "version": 2,
        "height": 0,
        "timestamp": GENESIS_TIMESTAMP,
        "prev_hash": "0" * 64,
        "merkle_root": compute_merkle_root(genesis_txs),
        "vdf_proof": genesis_vdf,
        "vrf_output": None,
        "leader_pubkey": founder_pub.hex(),
        "chain_id": CHAIN_ID
    }

    # Compute block hash
    block_hash = sha256d(json.dumps(genesis_header, sort_keys=True).encode())

    genesis_block = {
        "hash": block_hash.hex(),
        "header": genesis_header,
        "transactions": genesis_txs,
        "signature": None
    }

    # Genesis info
    genesis_info = {
        "network": NETWORK_NAME,
        "chain_id": CHAIN_ID,
        "genesis_time": GENESIS_TIMESTAMP,
        "genesis_time_human": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(GENESIS_TIMESTAMP)),
        "total_supply": TOTAL_SUPPLY,
        "allocations": {
            "founder": {
                "address": founder_pub.hex(),
                "amount": founder_amount,
                "percent": FOUNDER_PERCENT * 100
            },
            "faucet": {
                "address": faucet_pub.hex(),
                "amount": faucet_amount,
                "percent": FAUCET_PERCENT * 100
            },
            "rewards": {
                "address": rewards_pub.hex(),
                "amount": rewards_amount,
                "percent": REWARDS_PERCENT * 100
            }
        },
        "block": genesis_block
    }

    return genesis_info


def compute_merkle_root(transactions: list) -> str:
    """Compute Merkle root of transactions."""
    if not transactions:
        return "0" * 64

    hashes = [sha256(json.dumps(tx, sort_keys=True).encode()) for tx in transactions]

    while len(hashes) > 1:
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])

        new_hashes = []
        for i in range(0, len(hashes), 2):
            combined = hashes[i] + hashes[i + 1]
            new_hashes.append(sha256(combined))
        hashes = new_hashes

    return hashes[0].hex()


def save_genesis(genesis_info: dict, output_dir: Path):
    """Save genesis files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Full genesis info
    with open(output_dir / "genesis.json", "w") as f:
        json.dump(genesis_info, f, indent=2)

    # Block only (for node initialization)
    with open(output_dir / "genesis_block.json", "w") as f:
        json.dump(genesis_info["block"], f, indent=2)

    # Addresses only (for reference)
    addresses = {
        "founder": genesis_info["allocations"]["founder"]["address"],
        "faucet": genesis_info["allocations"]["faucet"]["address"],
        "rewards": genesis_info["allocations"]["rewards"]["address"]
    }
    with open(output_dir / "genesis_addresses.json", "w") as f:
        json.dump(addresses, f, indent=2)

    print(f"Genesis files saved to {output_dir}")
    print(f"  - genesis.json (full info)")
    print(f"  - genesis_block.json (block only)")
    print(f"  - genesis_addresses.json (addresses)")


def main():
    """Generate testnet genesis."""
    print("=" * 60)
    print("Proof of Time Testnet Genesis Generator")
    print("=" * 60)
    print()

    genesis_info = create_genesis_block()

    print(f"Network: {genesis_info['network']}")
    print(f"Chain ID: {genesis_info['chain_id']}")
    print(f"Genesis Time: {genesis_info['genesis_time_human']}")
    print(f"Total Supply: {genesis_info['total_supply']:,} POT")
    print()
    print("Allocations:")
    for role, alloc in genesis_info["allocations"].items():
        print(f"  {role.capitalize()}: {alloc['amount']:,} POT ({alloc['percent']}%)")
        print(f"    Address: {alloc['address'][:32]}...")
    print()
    print(f"Genesis Block Hash: {genesis_info['block']['hash']}")
    print()

    # Save files
    output_dir = Path(__file__).parent
    save_genesis(genesis_info, output_dir)

    print()
    print("Genesis generation complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
