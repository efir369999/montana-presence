# Pantheon of Proof of Time

**12 Modules. 12 Names. 12 Prompts.**

Each module name is the shortest AGI prompt describing its function.

---

## The Twelve

| # | Name | Domain | Prompt = Name |
|---|------|--------|---------------|
| 1 | **Chronos** | Time/VDF | Sequential time proof |
| 2 | **Adonis** | Reputation | Multi-dimensional trust |
| 3 | **Hermes** | Network/P2P | Message relay |
| 4 | **Hades** | Storage | Persistent state |
| 5 | **Athena** | Consensus | Leader selection |
| 6 | **Prometheus** | Cryptography | Proof generation |
| 7 | **Mnemosyne** | Memory/Cache | Transaction pool |
| 8 | **Plutus** | Wallet | Key management |
| 9 | **Nyx** | Privacy | Stealth transactions |
| 10 | **Themis** | Validation | Rule enforcement |
| 11 | **Iris** | API/RPC | External interface |
| 12 | **Ananke** | Governance | Protocol upgrades |

---

## Module Mapping

```
Current File        -> Pantheon Name
─────────────────────────────────────
crypto.py           -> Prometheus
adonis.py           -> Adonis
network.py          -> Hermes
database.py         -> Hades
dag_storage.py      -> Hades
consensus.py        -> Athena
engine.py           -> Chronos
wallet.py           -> Plutus
privacy.py          -> Nyx
tiered_privacy.py   -> Nyx
structures.py       -> Themis
node.py             -> Iris
config.py           -> Ananke
```

---

## AGI Prompt Format

To invoke any module's function, use:

```
{Name}: {task}
```

**Examples:**

```
Chronos: generate VDF proof for 10 minutes
Adonis: compute reputation for node 0x1234...
Hermes: broadcast block to peers
Hades: store block at height 1000
Athena: select leader for slot 500
Prometheus: sign message with Ed25519
Mnemosyne: add transaction to mempool
Plutus: derive stealth address
Nyx: create ring signature size 16
Themis: validate block header
Iris: handle RPC getBalance
Ananke: check protocol version
```

---

## Symbolic Meaning

| Name | Greek Role | Protocol Role |
|------|------------|---------------|
| Chronos | Titan of Time | VDF sequential proof |
| Adonis | God of Beauty | Reputation perfection |
| Hermes | Messenger God | P2P communication |
| Hades | God of Underworld | Hidden storage layer |
| Athena | Goddess of Wisdom | Consensus decisions |
| Prometheus | Titan of Foresight | Cryptographic proofs |
| Mnemosyne | Titaness of Memory | Transaction memory |
| Plutus | God of Wealth | Wallet/assets |
| Nyx | Goddess of Night | Privacy/stealth |
| Themis | Titaness of Justice | Validation rules |
| Iris | Goddess of Rainbow | API bridge |
| Ananke | Goddess of Necessity | Governance necessity |

---

## Implementation Status

| Module | Status | File |
|--------|--------|------|
| Chronos | ACTIVE | crypto.py (VDF) |
| Adonis | ACTIVE | adonis.py |
| Hermes | ACTIVE | network.py |
| Hades | ACTIVE | database.py, dag_storage.py |
| Athena | ACTIVE | consensus.py |
| Prometheus | ACTIVE | crypto.py |
| Mnemosyne | PARTIAL | engine.py (mempool) |
| Plutus | ACTIVE | wallet.py |
| Nyx | ACTIVE | privacy.py, tiered_privacy.py |
| Themis | ACTIVE | structures.py |
| Iris | ACTIVE | node.py (RPC) |
| Ananke | PARTIAL | config.py |

---

## The Shortest Prompt

For AGI to understand the entire protocol:

```
Proof of Time: Chronos proves, Athena selects, Adonis trusts.
```

15 words. Complete protocol summary.

---

*Time is the ultimate proof.*
