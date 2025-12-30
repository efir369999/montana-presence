"""
PANTHEON - The 14 Gods of Proof of Time

Each god represents a core protocol component:

| # | God        | Domain      | Module        | Status  |
|---|------------|-------------|---------------|---------|
| 1 | Chronos    | Time/VDF    | chronos/      | Active  |
| 2 | Hermes     | Network     | hermes/       | Active  |
| 3 | Hades      | Storage     | hades/        | Active  |
| 4 | Athena     | Consensus   | athena/       | Active  |
| 5 | Prometheus | Crypto      | prometheus/   | Active  |
| 6 | Mnemosyne  | Mempool     | mnemosyne/    | Active  |
| 7 | Plutus     | Wallet      | plutus/       | Active  |
| 8 | Nyx        | Privacy     | nyx/          | Active  |
| 9 | Themis     | Validation  | themis/       | Active  |
|10 | Iris       | API/RPC     | iris/         | Active  |
|11 | Ananke     | Governance  | ananke/       | Planned |
|12 | Apostles   | Trust/12    | apostles/     | Active  |
|13 | Hal        | Humanity    | hal/          | Active  |

HAL = Human Analyse Language (unified reputation + humanity system)
Named after Hal Finney, who understood Sybil resistance before anyone else.

Usage:
    from pantheon.chronos import WesolowskiVDF
    from pantheon.hal import HalEngine, HumanityTier
    from pantheon.athena import ConsensusCalculator
"""

import sys
from pathlib import Path

# Add root to path for cross-module imports
_root = str(Path(__file__).parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

GENESIS_TIMESTAMP = 1766966400  # Dec 28, 2025 00:00:00 UTC

GODS = {
    1:  "CHRONOS",     # Time / VDF
    2:  "HERMES",      # Network / P2P
    3:  "HADES",       # Storage / DAG
    4:  "ATHENA",      # Consensus / Leader Selection
    5:  "PROMETHEUS",  # Cryptography
    6:  "MNEMOSYNE",   # Mempool
    7:  "PLUTUS",      # Wallet
    8:  "NYX",         # Privacy
    9:  "THEMIS",      # Validation
    10: "IRIS",        # API / RPC
    11: "ANANKE",      # Governance
    12: "APOSTLES",    # Trust / 12 Apostles
    13: "HAL",         # Humanity / Reputation
}

PROTOCOL_PROMPT = "Proof of Time: Chronos proves, Athena selects, Hal trusts."
