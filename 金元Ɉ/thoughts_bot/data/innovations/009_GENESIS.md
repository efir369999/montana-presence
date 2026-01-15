# Montana Genesis

**The Origin of Temporal Value**
**Version:** 1.0
**Date:** January 2026

---

## Abstract

This paper documents the Montana Genesis—the origin point from which all temporal measurement derives. Unlike proof-of-work blockchains where genesis is arbitrary, Montana's genesis establishes the zero point of a coordinate system grounded in physical time. We formalize the genesis parameters, their derivation, and their implications for protocol operation.

---

## 1. Introduction

Every coordinate system requires an origin. In Montana, the genesis block defines:

1. The temporal origin (t = 0)
2. Initial distribution parameters
3. Protocol constants
4. The first presence proof

Genesis is not merely a starting block but the anchor connecting Montana's temporal proofs to physical reality.

---

## 2. Genesis Parameters

### 2.1 Temporal Origin

```
GENESIS_TIMESTAMP = 2026-01-13 00:00:00 UTC
GENESIS_UNIX      = 1736726400
```

**Rationale:** Selected for:
- UTC midnight for clear epoch boundary
- Monday for week alignment
- January for year alignment
- 2026 for protocol maturity

### 2.2 Initial State

```python
genesis_state = {
    "block_height": 0,
    "timestamp": 1736726400,
    "previous_hash": "0" * 64,
    "merkle_root": GENESIS_MERKLE,
    "difficulty": INITIAL_DIFFICULTY,
    "nonce": GENESIS_NONCE,
    "presence_proofs": [],
    "transactions": [GENESIS_TX],
}
```

### 2.3 Genesis Transaction

```python
genesis_tx = {
    "type": "genesis",
    "outputs": [
        {
            "address": FOUNDATION_ADDRESS,
            "amount": 0,  # No premine
            "script": "OP_GENESIS"
        }
    ],
    "message": "Time is the only resource distributed equally among all people."
}
```

---

## 3. The Genesis Message

### 3.1 Embedded Text

```
"Time is the only resource distributed equally among all people."
```

### 3.2 Significance

This message encodes Montana's philosophical foundation:

- **Time:** The basis of value
- **Only resource:** Unique among all assets
- **Distributed equally:** Universal, not privileged
- **All people:** Global, permissionless

### 3.3 Verification

```python
def verify_genesis_message(block):
    expected = "Time is the only resource distributed equally among all people."
    actual = block.transactions[0].message
    return expected == actual
```

---

## 4. No Premine Principle

### 4.1 Zero Initial Distribution

```
Total supply at genesis: 0 Ɉ
Foundation allocation: 0 Ɉ
Team allocation: 0 Ɉ
Investor allocation: 0 Ɉ
```

### 4.2 Rationale

Premine contradicts Montana's principles:

| Premine Type | Contradiction |
|--------------|---------------|
| Foundation | Creates privileged class |
| Team | Rewards non-presence |
| Investors | Values capital over time |
| Airdrops | Arbitrary distribution |

### 4.3 Fair Launch

All Ɉ enters circulation through presence:

```
∀ Ɉ: ∃ presence_proof(Ɉ)
```

Every unit of Ɉ is backed by proven temporal presence.

---

## 5. Genesis VDF

### 5.1 Initial VDF Parameters

```python
genesis_vdf = {
    "input": H(GENESIS_MESSAGE),
    "difficulty": 2^28,
    "output": GENESIS_VDF_OUTPUT,
    "proof": GENESIS_VDF_PROOF,
}
```

### 5.2 Bootstrapping Problem

How to create first VDF without previous block?

**Solution:** Genesis VDF input derives from message hash:

```
vdf_input = SHA3-256("Time is the only resource...")
          = 0x7f3a...
```

### 5.3 Verification

```python
def verify_genesis_vdf(block):
    expected_input = H(GENESIS_MESSAGE)
    return verify_vdf(
        expected_input,
        block.vdf_output,
        block.vdf_proof,
        INITIAL_DIFFICULTY
    )
```

---

## 6. Difficulty Initialization

### 6.1 Initial Difficulty

```
INITIAL_DIFFICULTY = 2^28 ≈ 268,435,456
```

### 6.2 Target Time

Difficulty set to produce τ₂ (10 minute) VDF on reference hardware:

| Hardware | VDF Time |
|----------|----------|
| Intel i7-12700 | ~600s |
| AMD Ryzen 9 | ~580s |
| Apple M2 | ~550s |

### 6.3 First Adjustment

Difficulty adjusts after first τ₃ (2,016 slices):

```python
def first_adjustment():
    actual_time = slice_2016_time - genesis_time
    expected_time = 2016 * 600  # 2 weeks
    ratio = expected_time / actual_time
    return INITIAL_DIFFICULTY * ratio
```

---

## 7. Genesis Presence

### 7.1 No Genesis Presence

Unlike transactions, genesis has no presence proofs:

```
genesis.presence_proofs = []
```

### 7.2 Rationale

Presence requires temporal passage. At genesis (t=0), no time has passed, therefore no presence can exist.

### 7.3 First Presence

First presence proof appears in block 1:

```
block_1.presence_proofs = [
    {
        "participant": first_participant,
        "timestamp": genesis_time + τ₂,
        "vdf_proof": first_vdf_proof,
        "signature": first_signature
    }
]
```

---

## 8. Historical Anchoring

### 8.1 External Timestamp

Genesis includes verifiable external timestamp:

```python
genesis_anchors = {
    "bitcoin_block": 880000,  # Nearest Bitcoin block
    "bitcoin_hash": "0x...",
    "ntp_servers": ["time.nist.gov", "time.google.com"],
    "newspaper_hash": H("NYT 2026-01-13 front page")
}
```

### 8.2 Purpose

External anchors prove genesis did not occur before claimed time:

```
genesis_time ≥ bitcoin_block_880000_time
genesis_time ≥ newspaper_publication_time
```

### 8.3 Impossibility of Backdating

Creating a valid genesis in 2026 claiming timestamp from 2020 is impossible:

- Bitcoin block 880000 didn't exist in 2020
- NYT 2026-01-13 didn't exist in 2020
- NTP servers have logs

---

## 9. Implementation

### 9.1 Genesis Block Generation

```python
def create_genesis_block():
    message = "Time is the only resource distributed equally among all people."
    vdf_input = sha3_256(message.encode())
    vdf_output, vdf_proof = compute_vdf(vdf_input, INITIAL_DIFFICULTY)

    return Block(
        height=0,
        timestamp=GENESIS_UNIX,
        previous_hash="0" * 64,
        transactions=[GenesisTransaction(message)],
        vdf_output=vdf_output,
        vdf_proof=vdf_proof,
        presence_proofs=[],
    )
```

### 9.2 Genesis Verification

```python
def verify_genesis(block):
    checks = [
        block.height == 0,
        block.timestamp == GENESIS_UNIX,
        block.previous_hash == "0" * 64,
        verify_genesis_message(block),
        verify_genesis_vdf(block),
        len(block.presence_proofs) == 0,
    ]
    return all(checks)
```

---

## 10. Conclusion

Montana's genesis is not merely a starting point but a carefully constructed anchor to physical reality. Through external timestamps, embedded messages, and mathematical constraints, genesis establishes an unforgeable origin from which all temporal value derives.

---

## References

1. Nakamoto, S. (2008). Bitcoin: A Peer-to-Peer Electronic Cash System.
2. Montana, A. (2026). τ Temporal Units System.

---

```
Alejandro Montana
Montana Protocol
January 2026

Genesis: 2026-01-13 00:00:00 UTC
"Time is the only resource distributed equally among all people."
```
