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

| Model | Date | Overall Score | File |
|-------|------|---------------|------|
| Claude Opus 4.5 | 2025-12-28 | 8.2/10 | [claude_opus_4.5_audit.md](claude_opus_4.5_audit.md) |
| GPT-4o | - | - | Pending |
| Gemini 1.5 Pro | - | - | Pending |
| DeepSeek V2 | - | - | Pending |

---

## Meta-Audit

After 3+ model audits, create a meta-audit comparing:
- Which issues all models found (consensus = high confidence)
- Which issues only one model found (verify manually)
- Where models disagreed (investigate)
- Blind spots (areas no model covered well)
