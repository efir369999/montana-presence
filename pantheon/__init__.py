"""
PANTHEON - The 12 Gods of Proof of Time

Each god represents a core protocol component:

| # | God        | Domain      | Module        | Status  |
|---|------------|-------------|---------------|---------|
| 1 | Chronos    | Time/VDF    | crypto.py     | Active  |
| 2 | Adonis     | Reputation  | adonis.py     | Active  |
| 3 | Hermes     | Network     | network.py    | Active  |
| 4 | Hades      | Storage     | database.py   | Active  |
| 5 | Athena     | Consensus   | consensus.py  | Active  |
| 6 | Prometheus | Crypto      | crypto.py     | Active  |
| 7 | Mnemosyne  | Mempool     | node.py       | Active  |
| 8 | Plutus     | Wallet      | wallet.py     | Active  |
| 9 | Nyx        | Privacy     | privacy.py    | Limited |
|10 | Themis     | Validation  | structures.py | Active  |
|11 | Iris       | API/RPC     | rpc.py        | Active  |
|12 | Ananke     | Governance  | -             | Planned |

Usage:
    from pantheon.chronos import WesolowskiVDF
    from pantheon.adonis import AdonisEngine
    from pantheon.athena import ConsensusCalculator
"""

GENESIS_TIMESTAMP = 1766966400  # Dec 28, 2025 00:00:00 UTC

GODS = {
    1:  "CHRONOS",     # Time
    2:  "ADONIS",      # Reputation
    3:  "HERMES",      # Network
    4:  "HADES",       # Storage
    5:  "ATHENA",      # Consensus
    6:  "PROMETHEUS",  # Cryptography
    7:  "MNEMOSYNE",   # Memory
    8:  "PLUTUS",      # Wallet
    9:  "NYX",         # Privacy
    10: "THEMIS",      # Validation
    11: "IRIS",        # API
    12: "ANANKE",      # Governance
}

PROTOCOL_PROMPT = "Proof of Time: Chronos proves, Athena selects, Adonis trusts."
