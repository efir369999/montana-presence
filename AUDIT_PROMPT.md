# Proof of Time — Audit Prompt

**Repository:** https://github.com/afgrouptime/proofoftime
**Run tests:** `python3 tests/test_security_proofs.py`

---

## Pantheon Modules

| Module | God | File | Purpose |
|--------|-----|------|---------|
| Chronos | Time | `pantheon/chronos/poh.py` | VDF, Proof of History |
| Adonis | Beauty | `pantheon/adonis/adonis.py` | Reputation, 5 Fingers |
| Hermes | Messenger | `pantheon/hermes/network.py` | P2P, Noise Protocol |
| Hades | Underworld | `pantheon/hades/database.py`, `dag.py` | Storage, DAG |
| Athena | Wisdom | `pantheon/athena/consensus.py`, `engine.py` | Consensus, VRF |
| Prometheus | Fire | `pantheon/prometheus/crypto.py` | Crypto, ECVRF, VDF |
| Mnemosyne | Memory | `pantheon/mnemosyne/mempool.py` | Mempool |
| Plutus | Wealth | `pantheon/plutus/wallet.py` | Wallet, Transactions |
| Nyx | Night | `pantheon/nyx/privacy.py`, `tiered_privacy.py` | Privacy T0-T3 |
| Themis | Justice | `pantheon/themis/structures.py` | Validation, Types |
| Iris | Rainbow | `pantheon/iris/rpc.py` | RPC API |
| Ananke | Necessity | `pantheon/ananke/governance.py` | Governance |

---

## Audit Checkpoints

### 1. Chronos (VDF)
- [ ] VDF cannot be parallelized
- [ ] Checkpoint interval = 10 min
- [ ] Proof verification O(log t)

### 2. Adonis (Reputation)
- [ ] TIME saturates at 180 days
- [ ] Weights: TIME=50%, INTEGRITY=20%, STORAGE=15%, GEO=10%, HANDSHAKE=5%
- [ ] ClusterDetector correlation threshold = 0.7
- [ ] GlobalByzantineTracker 33% cap
- [ ] Handshake requires different countries

### 3. Hermes (Network)
- [ ] Noise Protocol XX encryption
- [ ] Peer diversity (no subnet dominance)
- [ ] Eclipse attack resistance

### 4. Hades (Storage/DAG)
- [ ] PHANTOM ordering correct
- [ ] 1-8 parent references
- [ ] Finality score calculation
- [ ] No orphan manipulation

### 5. Athena (Consensus)
- [ ] ECVRF leader selection
- [ ] 64-bit integer comparison (not float!)
- [ ] Byzantine threshold = 33%
- [ ] Finality threshold = 67%

### 6. Prometheus (Crypto)
- [ ] ECVRF hash-to-curve uses 32 bytes
- [ ] VDF checkpoint cleanup (memory leak prevention)
- [ ] Ed25519 signatures
- [ ] Secure random generation

### 7. Nyx (Privacy)
- [ ] T0: Public (nothing hidden)
- [ ] T1: Stealth address (receiver hidden)
- [ ] T2: Pedersen commitment (amount hidden)
- [ ] T3: Ring signature (sender hidden)
- [ ] Range proofs prevent negative amounts

### 8. Plutus (Wallet)
- [ ] UTXO model
- [ ] Double-spend prevention
- [ ] Fee calculation correct

---

## Security Properties (PROVEN)

| Property | Test | Status |
|----------|------|--------|
| Cluster-cap bypass | `test_cluster_cap_bypass_proof` | PROVEN |
| Adaptive adversary | `test_adaptive_adversary_proof` | PROVEN |
| 33% = Byzantine | `test_byzantine_proof` | PROVEN |
| TIME = human time | `test_time_proof` | PROVEN |

---

## Known Limitations

1. **Geography** (10% weight) — VPN can spoof location
2. **Small networks** — Need 10+ nodes for Byzantine tracking
3. **Off-chain coordination** — Undetectable by design

---

## Audit Command

```bash
# Clone and audit
git clone https://github.com/afgrouptime/proofoftime
cd proofoftime
python3 -m pytest tests/ -v
python3 tests/test_security_proofs.py
```

---

**Focus:** Integer overflow, timing attacks, cryptographic correctness, consensus safety/liveness.

**Goal:** Production-ready (Bitcoin-level stability).
