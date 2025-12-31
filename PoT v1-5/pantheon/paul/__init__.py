"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                              PAUL - GOD OF NETWORKS                           ║
║                                                                               ║
║       PAUL = Peer Authenticated Unified Link                                  ║
║                                                                               ║
║       P2P networking with Noise Protocol XX encryption.                       ║
║       Handles peer discovery, message propagation, and network topology.      ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  COMPONENTS:                                                                  ║
║  ───────────                                                                  ║
║  - P2PNode:       Main networking node with encrypted channels                ║
║  - Bootstrap:     Peer discovery and initial connection                       ║
║  - IPValidator:   IP address validation and geolocation                       ║
║  - Rheuma:        Network health monitoring and diagnostics                   ║
║                                                                               ║
║  FEATURES:                                                                    ║
║  ─────────                                                                    ║
║  - Noise Protocol XX for forward secrecy                                      ║
║  - Gossip protocol for message propagation                                    ║
║  - Peer reputation and banning                                                ║
║  - NAT traversal and hole punching                                            ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""
from .network import *
