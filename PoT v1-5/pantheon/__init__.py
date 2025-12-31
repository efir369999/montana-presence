"""
PANTHEON - The 11 Gods of Proof of Time

Each god represents a core protocol component:

| # | God        | Domain      | Module        | Status  |
|---|------------|-------------|---------------|---------|
| 1 | Adam       | Time        | adam/         | Active  |
| 2 | Paul       | Network     | paul/         | Active  |
| 3 | Hades      | Storage     | hades/        | Active  |
| 4 | Athena     | Consensus   | athena/       | Active  |
| 5 | Prometheus | Crypto      | prometheus/   | Active  |
| 6 | Plutus     | Wallet      | plutus/       | Active  |
| 7 | Nyx        | Privacy     | nyx/          | Active  |
| 8 | Themis     | Validation  | themis/       | Active  |
| 9 | Iris       | API/RPC     | iris/         | Active  |
|10 | Apostles   | Trust/12    | apostles/     | Active  |
|11 | Hal        | Humanity    | hal/          | Active  |

ADAM = Anchored Deterministic Asynchronous Mesh (God of Time)
HAL = Human Analyse Language (reputation + humanity system)
PAUL = Peer Authenticated Unified Link (P2P network)

Usage:
    from pantheon.adam import Adam, AdamLevel
    from pantheon.hal import HalEngine, HumanityTier
    from pantheon.athena import ConsensusCalculator
"""

import sys
from pathlib import Path

_root = str(Path(__file__).parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

GENESIS_TIMESTAMP = 1766966400  # Dec 28, 2025 00:00:00 UTC

GODS = {
    1:  "ADAM",        # Time / VDF / Bitcoin Oracle
    2:  "PAUL",        # Network / P2P
    3:  "HADES",       # Storage / DAG
    4:  "ATHENA",      # Consensus / Leader Selection
    5:  "PROMETHEUS",  # Cryptography
    6:  "PLUTUS",      # Wallet
    7:  "NYX",         # Privacy
    8:  "THEMIS",      # Validation
    9:  "IRIS",        # API / RPC
    10: "APOSTLES",    # Trust / 12 Apostles
    11: "HAL",         # Humanity / Reputation
}

PROTOCOL_PROMPT = "Proof of Time: Adam proves, Athena selects, Hal trusts."
