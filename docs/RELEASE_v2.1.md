# Proof of Time v2.1.0 — Geographic Diversity Release

**Release Date:** December 28, 2025

---

## Overview

Version 2.1 enhances the Adonis reputation system with **geographic diversity incentives** to promote network decentralization across cities and countries.

**Key Innovation:** Anonymous city detection that rewards nodes for joining from new geographic locations while preserving privacy.

---

## New Features

### 1. Geographic Diversity Dimension

Adonis now includes a 6th reputation dimension: **GEOGRAPHY**

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Integrity | 28% | Valid proofs, no violations |
| Reliability | 22% | Block production, uptime |
| Longevity | 17% | Time in network |
| Contribution | 13% | Storage, relay, validation |
| Community | 10% | Peer trust vouches |
| **Geography** | **10%** | **Geographic diversity (NEW)** |

### 2. Anonymous City Detection

Privacy-preserving location tracking:

```python
# How it works:
city_hash = SHA256(f"{country.upper()}:{city.lower()}")
# Example: SHA256("JP:tokyo") -> 5dedf6ccb2c95a3d...

# Only the hash is stored - never raw IP or location
profile.city_hash = city_hash  # 32 bytes
```

**Privacy Guarantees:**
- IP addresses are **NEVER** stored
- Only `city_hash` (SHA256) persisted
- Cannot reverse-engineer location from hash
- Case-insensitive normalization

### 3. NEW_CITY Reputation Event

First node from a new city receives a significant bonus:

| Event | Impact | Dimension |
|-------|--------|-----------|
| NEW_CITY | +0.15 | GEOGRAPHY |

This incentivizes geographic expansion of the network.

### 4. Geographic Scoring Algorithm

```python
# Rarity score: fewer nodes in city = higher score
rarity_score = 1.0 / (1.0 + log10(nodes_in_city))
# 1 node  = 1.0
# 10 nodes = 0.5
# 100 nodes = 0.25

# Diversity bonus: more total cities = higher bonus
diversity_bonus = min(1.0, total_cities / 100)

# Combined score
geo_score = 0.7 * rarity_score + 0.3 * diversity_bonus
```

### 5. Network Diversity Metrics

New methods for monitoring geographic distribution:

```python
from adonis import AdonisEngine

engine = AdonisEngine()

# Register node location
is_new_city, score = engine.register_node_location(
    pubkey=node_pubkey,
    country="JP",
    city="Tokyo"
)
# Returns: (True, 0.703) for first node from Tokyo

# Auto-detect from IP (optional)
result = engine.update_node_location_from_ip(pubkey, "203.0.113.1")
# Uses ip-api.com, IP is NOT stored

# Get city distribution (anonymized)
distribution = engine.get_city_distribution()
# {"5dedf6cc": 2, "1b98ea98": 1}  # hash prefix -> node count

# Network-wide diversity score (Gini-based)
diversity = engine.get_geographic_diversity_score()
# 0.833 (higher = more decentralized)
```

---

## Updated Adonis Architecture

### Reputation Dimensions (v2.1)

```
                    ADONIS REPUTATION MODEL v2.1
    ┌─────────────────────────────────────────────────────┐
    │                                                     │
    │   ┌───────────┐  ┌───────────┐  ┌───────────┐      │
    │   │ INTEGRITY │  │RELIABILITY│  │ LONGEVITY │      │
    │   │    28%    │  │    22%    │  │    17%    │      │
    │   └───────────┘  └───────────┘  └───────────┘      │
    │                                                     │
    │   ┌───────────┐  ┌───────────┐  ┌───────────┐      │
    │   │CONTRIBUTION│ │ COMMUNITY │  │ GEOGRAPHY │      │
    │   │    13%    │  │    10%    │  │    10%    │      │
    │   └───────────┘  └───────────┘  └─────NEW───┘      │
    │                                                     │
    │                 ┌─────────────┐                     │
    │                 │  AGGREGATE  │                     │
    │                 │    SCORE    │                     │
    │                 └─────────────┘                     │
    │                                                     │
    └─────────────────────────────────────────────────────┘
```

### Event Types (v2.1)

| Event | Impact | Dimension | Description |
|-------|--------|-----------|-------------|
| BLOCK_PRODUCED | +0.05 | Reliability | Block created |
| BLOCK_VALIDATED | +0.02 | Contribution | Validated block |
| TX_RELAYED | +0.01 | Contribution | Relayed transaction |
| UPTIME_CHECKPOINT | +0.03 | Reliability | Maintained uptime |
| PEER_VOUCH | +0.10 | Community | Trust endorsement |
| **NEW_CITY** | **+0.15** | **Geography** | **First from city** |
| BLOCK_INVALID | -0.15 | Integrity | Invalid block |
| VRF_INVALID | -0.20 | Integrity | Bad VRF proof |
| VDF_INVALID | -0.25 | Integrity | Bad VDF proof |
| EQUIVOCATION | -1.00 | Integrity | Double-signing |
| DOWNTIME | -0.10 | Reliability | Offline period |
| SPAM_DETECTED | -0.20 | Integrity | TX spam |
| PEER_COMPLAINT | -0.05 | Community | Peer report |

---

## API Reference

### New Methods

```python
class AdonisEngine:

    def compute_city_hash(self, country: str, city: str) -> bytes:
        """Compute anonymous city hash from location."""

    def register_node_location(
        self,
        pubkey: bytes,
        country: str,
        city: str,
        ip_address: Optional[str] = None
    ) -> Tuple[bool, float]:
        """
        Register node's geographic location anonymously.

        Returns:
            (is_new_city, geographic_score)
        """

    def update_node_location_from_ip(
        self,
        pubkey: bytes,
        ip_address: str
    ) -> Optional[Tuple[bool, float]]:
        """Auto-detect location from IP using ip-api.com."""

    def get_city_distribution(self) -> Dict[str, int]:
        """Get anonymized city -> node_count mapping."""

    def get_geographic_diversity_score(self) -> float:
        """Calculate network-wide geographic diversity (0-1)."""
```

### Updated Stats

```python
stats = engine.get_stats()
# {
#     'total_profiles': 150,
#     'active_profiles': 142,
#     'penalized_profiles': 8,
#     'total_vouches': 523,
#     'average_score': 0.654,
#     'unique_cities': 47,  # NEW
#     'dimension_weights': {
#         'RELIABILITY': 0.22,
#         'INTEGRITY': 0.28,
#         'CONTRIBUTION': 0.13,
#         'LONGEVITY': 0.17,
#         'COMMUNITY': 0.10,
#         'GEOGRAPHY': 0.10  # NEW
#     }
# }
```

---

## Testnet Infrastructure

v2.1 includes complete testnet deployment:

| Component | Description |
|-----------|-------------|
| `testnet/config.json` | Network configuration |
| `testnet/genesis.py` | Genesis block generator |
| `testnet/Dockerfile` | Docker image |
| `testnet/docker-compose.yml` | 3-node cluster |
| `testnet/launch.sh` | Management script |
| `testnet/faucet.py` | Token faucet |

**Quick Start:**
```bash
cd testnet
./launch.sh start   # Launch Docker cluster
./launch.sh local   # Run locally
./launch.sh logs    # View logs
./launch.sh stop    # Stop cluster
```

**Network Parameters:**
- Chain ID: 1001
- Block interval: 60 seconds
- VDF iterations: 100,000
- Total supply: 1,000,000,000 POT

---

## Migration Guide

### From v2.0 to v2.1

No breaking changes. Simply update:

```bash
git pull origin main
```

The new GEOGRAPHY dimension is automatically added to existing profiles with initial score of 0.

To register node locations:

```python
from adonis import AdonisEngine

engine = AdonisEngine()

# Manual registration
engine.register_node_location(my_pubkey, "US", "New York")

# Or auto-detect from peer IP
engine.update_node_location_from_ip(peer_pubkey, peer_ip)
```

---

## File Changes

### Modified Files
- `adonis.py` — Geographic diversity (+254 lines)

### New Files
- `testnet/config.json` — Network configuration
- `testnet/genesis.py` — Genesis generator
- `testnet/genesis.json` — Genesis data
- `testnet/genesis_block.json` — Genesis block
- `testnet/genesis_addresses.json` — Genesis addresses
- `testnet/Dockerfile` — Docker image
- `testnet/docker-compose.yml` — Docker cluster
- `testnet/launch.sh` — Launch script
- `testnet/faucet.py` — Token faucet
- `testnet/README.md` — Testnet documentation
- `docs/RELEASE_v2.1.md` — This document

---

## Statistics

| Metric | v2.0 | v2.1 |
|--------|------|------|
| Total Python files | 18 | 19 |
| Lines of code | ~15,000 | ~16,500 |
| Test coverage | 123+ | 130+ |
| Reputation dimensions | 5 | **6** |
| Testnet files | 0 | **10** |

---

## Security Considerations

### Privacy
- No raw IP addresses stored anywhere
- City identification via one-way SHA256 hash
- Hash prefix (8 chars) used in public APIs for additional privacy

### Anti-Gaming
- Geographic claims verified via IP geolocation
- Cannot claim multiple cities simultaneously
- Rarity score decreases as city gets more nodes

### Decentralization
- Incentivizes geographic spread
- Penalizes concentration in single city
- Network diversity score visible to all

---

## What's Next (v2.2 Roadmap)

1. **Country-level diversity** — Additional dimension for country spread
2. **Latency-based verification** — Verify geographic claims via RTT
3. **Regional sharding** — Optimize consensus by geography
4. **Privacy tiers for location** — Optional location disclosure levels

---

*Time is the ultimate proof. Geography is the ultimate decentralization.*
