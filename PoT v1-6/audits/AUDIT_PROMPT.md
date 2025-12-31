# Proof of Time — AI Auditor Prompt

Use this prompt to request a security audit from any AI model.

---

## PROMPT FOR AI AUDITOR

```
You are performing a comprehensive security audit of the Proof of Time (PoT) cryptocurrency implementation.

Repository: https://github.com/afgrouptime/proofoftime

## Your Task

Create a detailed audit report covering THREE areas:

### 1. STABILITY AUDIT
Analyze the codebase for bugs and stability issues:
- Check all critical paths (block production, consensus, networking)
- Look for race conditions, deadlocks, memory leaks
- Verify error handling and edge cases
- Check database operations for corruption risks
- Validate serialization/deserialization roundtrips
- Score: X/10 with justification

### 2. SECURITY AUDIT
Analyze cryptographic implementations and attack vectors:
- Review all crypto primitives (Ed25519, VDF, VRF, LSAG, Bulletproofs)
- Check for timing attacks, precision loss, overflow/underflow
- Analyze consensus mechanism for manipulation vectors
- Review P2P protocol for eclipse/Sybil attacks
- Check key management and wallet security
- Identify any CVE-worthy vulnerabilities
- Score: X/10 with justification

### 3. USER EXPERIENCE AUDIT
Analyze usability for end users:
- Evaluate CLI interface completeness
- Review dashboard information clarity
- Check error messages helpfulness
- Identify missing features for basic operations
- Assess documentation quality
- Score: X/10 with justification

### Additional Focus Areas (please address explicitly)
- **Crypto placeholders / unaudited primitives:** Detect any stub or “production-grade” claims without test vectors (Bulletproofs, LSAG, VDF fallbacks). Flag unsafe fallbacks (e.g., XOR/ECB, non-AEAD).
- **Finality / checkpointing:** Verify PoH→PoT finality, leader timeouts, reorg rules, and checkpoint inclusion/validation.
- **Economic validation & anti-spam:** Fee/size limits, double-spend checks, DAG parasitic/balancing/spam resistance, θ_min enforcement, mempool/DoS protections.
- **Network security:** Ensure Noise/AEAD is mandatory, no insecure fallbacks; key rotation, rate limiting, ban lists, eclipse/Sybil protections.
- **VDF robustness:** Presence of alternative modulus (class group) or rotation plan; T calibration/benchmarks on target hardware.
- **Testing/CI:** Existence of real integration/fuzz tests (beyond `_self_test`), serialization round-trips, perf/bench coverage.
- **UX/ops:** Dependency checks (gmpy2, noiseprotocol, PyNaCl), install/runbook, config examples, diagnostics.

## Key Files to Review

Priority 1 (Critical):
- crypto.py — VDF, VRF, signatures
- consensus.py — Leader selection, validation
- wallet.py — Key management, transactions
- privacy.py — Ring signatures, stealth addresses

Priority 2 (Important):
- node.py — Full node, block production
- network.py — P2P, Noise protocol
- database.py — Persistence, state management
- structures.py — Data structures, serialization

Priority 3 (Supporting):
- config.py — Protocol parameters
- dag.py — DAG ordering (if present)

## Output Format

Create your audit as a markdown file with this structure:

# Proof of Time — Security Audit

**Auditor:** [Your Model Name]
**Model ID:** [Your exact model identifier]
**Date:** [Current date]
**Codebase Version:** [Git commit or version]

---

## 1. STABILITY AUDIT
[Your findings with severity ratings]
**Score: X/10**

---

## 2. SECURITY AUDIT
[Your findings with CVE-style identifiers]
**Score: X/10**

---

## 3. USER EXPERIENCE AUDIT
[Your findings with recommendations]
**Score: X/10**

---

## SUMMARY
| Category | Score | Key Issues |
|----------|-------|------------|
| Stability | X/10 | ... |
| Security | X/10 | ... |
| UX | X/10 | ... |
| **Overall** | **X/10** | ... |

## RECOMMENDATIONS
1. [Priority 1 fix]
2. [Priority 2 fix]
...

---

*Audit by [Model Name]*

## Important Notes

1. Be thorough but honest — don't invent issues
2. Provide specific file:line references when possible
3. Rate severity: Critical > High > Medium > Low > Info
4. Compare with Bitcoin/Monero standards where applicable
5. Note any areas you couldn't fully analyze and why

## Save Your Audit

Save your completed audit to:
audits/[model_name]_audit.md

Example: audits/gpt4_audit.md, audits/gemini_audit.md
```

---

## How to Use

### Option 1: Direct API
Send this prompt + repository files to any AI API.

### Option 2: Chat Interface
1. Paste this prompt
2. Share repository link or key files
3. Ask model to create audit

### Option 3: Claude Code / Cursor / Aider
```bash
# In project directory:
"Read AUDIT_PROMPT.md and create your audit following the template"
```

---

## Completed Audits

| Model | Date | Version | Overall Score | File |
|-------|------|---------|---------------|------|
| Claude Opus 4.5 (v4.0) | 2025-12-30 | v4.0.0 | 9.2/10 | [claude_opus_4.5_v4.0_audit.md](anthropic/claude_opus_4.5_v4.0_audit.md) |
| Claude Opus 4.5 (v2.5) | 2025-12-29 | v2.5.0 | 8.3/10 | [claude_opus_4.5_v2.5_audit.md](anthropic/claude_opus_4.5_v2.5_audit.md) |
| Claude Opus 4.5 (v2.3) | 2025-12-29 | v2.3.0 | PASS | [SECURITY_AUDIT.md](anthropic/SECURITY_AUDIT.md) |
| Claude Opus 4.5 (v2.0) | 2025-12-28 | v2.0.0 | 9.0/10 | [claude_opus_4.5_v2.0_audit.md](anthropic/claude_opus_4.5_v2.0_audit.md) |
| Gemini 3 Flash | 2025-12-28 | v2.2.0 | 9.0/10 | [gemini_3_flash_audit.md](alphabet/gemini_3_flash_audit.md) |
| Claude Opus 4.5 (v1.2) | 2025-12-28 | v1.2.0 | 8.2/10 | [claude_opus_4.5_audit.md](anthropic/claude_opus_4.5_audit.md) |
| GPT-5.1 Codex | 2025-12-28 | v2.3.0 | - | [gpt-5.1-codex-max-xhigh_audit.md](openai/gpt-5.1-codex-max-xhigh_audit.md) |
| GPT-4o | - | - | - | Pending |
| DeepSeek V2 | - | - | - | Pending |

---

## Meta-Audit

After 3+ model audits, create a meta-audit comparing:
- Which issues all models found (consensus = high confidence)
- Which issues only one model found (verify manually)
- Where models disagreed (investigate)
- Blind spots (areas no model covered well)
