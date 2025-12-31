"""
Asymptotic Trust Consensus (ATC) Protocol v7

Production-ready implementation based on Asymptotic_Trust_Consensus_TECH_SPECIFICATION.md

Trust(t) -> 0 as t -> infinity

Dedicated to Hal Finney (1956-2014)
"Running bitcoin" - January 11, 2009
"""

__version__ = "7.0.0"
__author__ = "ATC Protocol"

from atc.constants import PROTOCOL_VERSION, NETWORK_ID_MAINNET, NETWORK_ID_TESTNET

__all__ = [
    "PROTOCOL_VERSION",
    "NETWORK_ID_MAINNET",
    "NETWORK_ID_TESTNET",
    "__version__",
]
