# Ɉ Montana

> *Mechanism for asymptotic trust in the value of time*

**Version:** 3.1
**Ticker:** $MONT

---

## What Is Ɉ Montana?

**Ɉ Montana** is a mechanism for asymptotic trust in the value of time.

**Ɉ** is a **Temporal Time Unit** (TTU) — a unit that asymptotically approaches:

```
lim(evidence → ∞) 1 Ɉ → 1 second
```

Montana builds trust through **Asymptotic Trust Consensus** (ATC):
- Physical constraints (atomic time, thermodynamics)
- Computational hardness (post-quantum cryptography)
- Protocol primitives (VDF, VRF)
- Consensus mechanisms (DAG, finality)

**v3.1:** Explicit tier system (1-2-3), node type definitions.

---

## Definition

```
1 Ɉ     ≈ 1 second
60 Ɉ    ≈ 1 minute
3600 Ɉ  ≈ 1 hour
86400 Ɉ ≈ 1 day

Total: 1,260,000,000 Ɉ ≈ 21 million minutes
```

---

## Time Verification

| Layer | Method | Guarantee |
|-------|--------|-----------|
| **Atomic** | 34 NTP sources, 8 regions | Physical (10⁻¹⁹ precision) |
| **VDF** | Sequential computation | Cannot accelerate |
| **Finality** | Accumulated VDF depth | Physics-based (self-sovereign) |

---

## Finality Model

```
Hard Finality (40+ min)    → 1000+ VDF checkpoints
     ↑
Medium Finality (minutes)  → 100 VDF checkpoints + DAG
     ↑
Soft Finality (seconds)    → 1 VDF checkpoint
```

**Attack cost:** Rewriting N seconds of history requires N seconds of real time.

This is a physical law.

---

## Participation (3 Tiers, 2 Node Types)

**Node Types:**
| Type | Storage | Tier |
|------|---------|------|
| **Full Node** | Full blockchain history | Tier 1 |
| **Light Node** | From connection only | Tier 2 |

**Tiers:**
| Tier | Participants | Lottery |
|------|--------------|---------|
| **1** | Full Node operators | 70% |
| **2** | Light Node / TG Bot owners | 20% |
| **3** | TG Community users | 10% |

---

## Key Properties

| Property | Value |
|----------|-------|
| Project | Ɉ Montana |
| Symbol | Ɉ |
| Ticker | $MONT |
| Definition | lim(evidence → ∞) 1 Ɉ → 1 second |
| Total Supply | 1,260,000,000 Ɉ |
| Pre-allocation | 0 |
| Node Types | 2 (Full, Light) |
| Tiers | 3 (numbered 1-2-3) |
| Cryptography | Post-quantum (NIST 2024) |
| Finality | Self-sovereign (accumulated VDF) |

---

## Documentation

| Document | Description |
|----------|-------------|
| [WHITEPAPER.md](WHITEPAPER.md) | Complete specification |
| [MONTANA_TECHNICAL_SPECIFICATION.md](MONTANA_TECHNICAL_SPECIFICATION.md) | Implementation details |
| [MONTANA_ATC_MAPPING.md](MONTANA_ATC_MAPPING.md) | ATC layer mapping |

---

## ATC Foundation

```
Layer 3+: Ɉ Montana (TTU)
       ↑
Layer 2:  Consensus (DAG, VDF Finality)
       ↑
Layer 1:  Primitives (VDF, VRF)
       ↑
Layer 0:  Computation (SHA-3, SPHINCS+)
       ↑
Layer -1: Physics (Atomic Time, Thermodynamics)
```

---

## Principle

```
lim(evidence → ∞) Trust = 1
∀t: Trust(t) < 1
```

We approach certainty; we never claim to reach it.

**Time is the universal constant. Ɉ Montana builds trust in its value.**

---

<div align="center">

**Ɉ Montana**

*lim(evidence → ∞) 1 Ɉ → 1 second*

**Self-sovereign. Physics-based.**

**$MONT**

</div>
