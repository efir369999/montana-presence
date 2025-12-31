"""
Proof of Time (PoT) Protocol v6
Asymptotic Trust Consensus

Production-ready implementation based on PROOF_OF_TIME_v6_TECHNICAL_SPECIFICATION.md

Trust(t) -> 0 as t -> infinity

Dedicated to Hal Finney (1956-2014)
"Running bitcoin" - January 11, 2009
"""

__version__ = "6.1.0"
__author__ = "PoT Protocol"

from pot.constants import PROTOCOL_VERSION, NETWORK_ID_MAINNET, NETWORK_ID_TESTNET

__all__ = [
    "PROTOCOL_VERSION",
    "NETWORK_ID_MAINNET",
    "NETWORK_ID_TESTNET",
    "__version__",
]
