# Proof of Time — Security Audit

**Auditor:** gpt-5.1-codex-max-xhigh  
**Model ID:** gpt-5.1-codex-max-xhigh  
**Date:** 2025-12-28  
**Codebase Version:** local working tree (no git tag provided)

---

## 1. STABILITY AUDIT
- **Node bootstrap fails on fresh start** — `ProofOfTimeNode` used non-existent `NodeConfig.default()` and missing public-key derivation; fixed in this pass (`engine.py`), but highlights lack of regression tests. *Severity: High.*
- **Checkpointing / finality unimplemented** — PoH→PoT integration stub (`_trigger_checkpoint` in `poh.py`) leaves chain without finalized state; reorg and liveness semantics undefined. *Severity: High.*
- **Validation gaps on DAG blocks** — `DAGConsensusEngine.add_block` only checks parent existence, VDF proof, signature; no checks for tx validity, double-spend, or fee/size limits, allowing malformed/spam blocks. *Severity: High.*
- **Self-tests instead of real tests** — Modules rely on inline `_self_test` functions; no automated test suite or CI, so regressions slip through. *Severity: Medium.*
- **Serialization/DB coupling risks** — `dag_storage.py` / `database.py` trust incoming serialized blobs without schema/version checks; corrupted or oversized data can be persisted. *Severity: Medium.*

**Score: 3.5/10**

---

## 2. SECURITY AUDIT
- **Insecure cryptography placeholders (Critical)** — Bulletproofs and LSAG implementations are incomplete/weak: `t_hat`, IPA vectors are random placeholders and verification is partial (`privacy.py` 1412-1423). This breaks soundness of T2/T3 privacy; forged proofs/zero-knowledge absent. *Impact: funds forgery/anonymity break.*
- **Noise fallback removed; library mandatory** — Prior XOR “encryption” fallback is now hard-disabled; P2P still depends on external `noiseprotocol`. Remaining risk if dependency absent: node aborts (safe fail). *Severity: Medium (mitigated).*
- **Single RSA-2048 VDF modulus** — No class-group fallback; factoring RSA-2048 breaks time proofs. *Severity: High.*
- **Consensus/economic validation missing** — DAG blocks accepted without supply/fee/double-spend enforcement; Sybil threshold `θ_min=0.1` allows low-weight block spam; no mempool fee/rate limiting beyond minimal checks. *Severity: High.*
- **Key image / RingCT trust issues** — `TierValidator` accepts T3 inputs but relies on unsafe LSAG/Bulletproof; key image uniqueness checks exist, but cryptographic soundness absent. *Severity: High.*
- **Timing/precision** — VRF/VDF rely on Python bigints; no constant-time guarantees; Ed25519 operations via PyNaCl ok, but custom helpers may leak via timing. *Severity: Medium.*

**Score: 2/10**

---

## 3. USER EXPERIENCE AUDIT
- **Setup fragility** — Requires `gmpy2`, `noiseprotocol`, `PyNaCl`; missing leads to runtime aborts. No installer or dependency check script. *Severity: Medium.*
- **No CLI/wallet UX** — `wallet.py` is present but undocumented; no end-to-end flow for sending/receiving with tiers; no migration or backup guidance. *Severity: Medium.*
- **Errors terse/technical** — Exceptions bubble from crypto/network layers without user-friendly remediation. *Severity: Medium.*
- **Documentation sparse** — README is visionary; lacks run commands, config examples, threat model, and performance expectations. *Severity: Medium.*

**Score: 4/10**

---

## SUMMARY
| Category | Score | Key Issues |
|----------|-------|------------|
| Stability | 3.5/10 | Missing finality, weak block validation, no tests |
| Security | 2/10 | Broken Bulletproof/LSAG, single RSA VDF, economic checks absent |
| UX | 4/10 | Fragile setup, unclear wallet/CLI, sparse docs |
| **Overall** | **3/10** | Core cryptography incomplete; consensus/validation unsafe |

## RECOMMENDATIONS
1. Replace/custom-remove placeholder Bulletproofs/LSAG; disable T2/T3 until backed by audited library (ffi/rust) and full verification.
2. Enforce Noise Protocol dependency (done) and add AEAD test vectors; refuse to start without it.
3. Add economic/consensus validation: fee/size limits, double-spend checks, supply/balance enforcement, Sybil/θ_min hard gates.
4. Implement PoH→PoT checkpointing and block finality; add leader timeout handling.
5. Provide class-group VDF fallback and modulus rotation; benchmark-based T calibration at startup.
6. Build automated test suite (unit + integration + fuzz) covering serialization, networking, consensus, and crypto; add CI.
7. Improve UX: install scripts, config examples, wallet/CLI flows, and clear error messages.

---

*Audit by gpt-5.1-codex-max-xhigh*

