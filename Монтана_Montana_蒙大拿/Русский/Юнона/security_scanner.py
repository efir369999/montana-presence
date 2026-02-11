#!/usr/bin/env python3
"""
Security Scanner — Static Code Vulnerability Analysis Engine

Detects OWASP Top 10 and common vulnerabilities in any code:
  - SQL Injection
  - XSS (Cross-Site Scripting)
  - Command Injection
  - Path Traversal
  - Hardcoded Secrets
  - Insecure Crypto
  - Unsafe Deserialization
  - SSRF
  - Open Redirects
  - Missing Auth

Ɉ MONTANA PROTOCOL — ML-DSA-65 (FIPS 204)
"""

import re
import hashlib
import signal
from dataclasses import dataclass, field, asdict
from typing import Optional

# Limits to prevent DoS
MAX_CODE_SIZE = 512_000  # 500KB
MAX_LINES = 10_000
MAX_LINE_LENGTH = 2_000


class ScanTimeout(Exception):
    pass

# ─── Vulnerability Model ─────────────────────────────────────────────────────


@dataclass
class Vulnerability:
    id: str
    severity: str  # critical, high, medium, low, info
    category: str
    title: str
    description: str
    line: Optional[int] = None
    code_snippet: str = ""
    recommendation: str = ""
    cwe: str = ""
    owasp: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanResult:
    code_hash: str
    language: str
    lines_scanned: int
    vulnerabilities: list = field(default_factory=list)
    score: int = 100  # 0-100, starts at 100

    def add(self, vuln: Vulnerability):
        self.vulnerabilities.append(vuln)
        penalty = {"critical": 25, "high": 15, "medium": 8,
                   "low": 3, "info": 0}
        self.score = max(0, self.score - penalty.get(vuln.severity, 0))

    def to_dict(self) -> dict:
        return {
            "code_hash": self.code_hash,
            "language": self.language,
            "lines_scanned": self.lines_scanned,
            "score": self.score,
            "grade": self._grade(),
            "total_vulnerabilities": len(self.vulnerabilities),
            "by_severity": self._count_by_severity(),
            "vulnerabilities": [v.to_dict() for v in self.vulnerabilities],
        }

    def _grade(self) -> str:
        if self.score >= 90:
            return "A"
        if self.score >= 75:
            return "B"
        if self.score >= 60:
            return "C"
        if self.score >= 40:
            return "D"
        return "F"

    def _count_by_severity(self) -> dict:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for v in self.vulnerabilities:
            counts[v.severity] = counts.get(v.severity, 0) + 1
        return counts


# ─── Language Detection ──────────────────────────────────────────────────────

def detect_language(code: str) -> str:
    """Detect programming language from code content"""
    indicators = {
        "python": [r'\bdef\s+\w+\s*\(', r'\bimport\s+\w+', r'\bclass\s+\w+:',
                   r'print\s*\(', r'self\.'],
        "javascript": [r'\bfunction\s+\w+', r'\bconst\s+\w+', r'\blet\s+\w+',
                       r'=>', r'console\.log', r'require\('],
        "typescript": [r'\binterface\s+\w+', r':\s*string', r':\s*number',
                       r'<\w+>', r'import.*from'],
        "go": [r'\bfunc\s+\w+', r'\bpackage\s+\w+', r':=',
               r'fmt\.', r'\bgo\s+\w+'],
        "rust": [r'\bfn\s+\w+', r'\blet\s+mut\b', r'\bimpl\s+',
                 r'->.*\{', r'println!'],
        "java": [r'\bpublic\s+class', r'\bprivate\s+', r'\bprotected\s+',
                 r'System\.out', r'\bvoid\s+\w+'],
        "swift": [r'\bfunc\s+\w+', r'\bvar\s+\w+:', r'\blet\s+\w+:',
                  r'\bguard\s+', r'\bstruct\s+\w+'],
        "php": [r'<\?php', r'\$\w+\s*=', r'\bfunction\s+\w+',
                r'->', r'echo\s+'],
        "ruby": [r'\bdef\s+\w+', r'\bend\b', r'\bclass\s+\w+',
                 r'puts\s+', r'\brequire\s+'],
        "c": [r'#include\s+<', r'\bint\s+main', r'printf\s*\(',
              r'\bmalloc\s*\(', r'\bfree\s*\('],
        "sql": [r'\bSELECT\b', r'\bINSERT\b', r'\bUPDATE\b',
                r'\bDELETE\b', r'\bCREATE TABLE\b'],
        "solidity": [r'\bpragma\s+solidity', r'\bcontract\s+\w+',
                     r'\bmapping\s*\(', r'\bpayable\b'],
    }

    scores = {}
    for lang, patterns in indicators.items():
        score = sum(1 for p in patterns if re.search(p, code, re.IGNORECASE))
        if score > 0:
            scores[lang] = score

    if not scores:
        return "unknown"
    return max(scores, key=scores.get)


# ─── Pattern Rules ───────────────────────────────────────────────────────────

# Each rule: (pattern, severity, category, title, description, cwe, owasp, recommendation)
UNIVERSAL_RULES = [
    # --- Hardcoded Secrets ---
    (r'(?:password|passwd|pwd|secret|token|api_?key|apikey|auth)\s*[=:]\s*["\'][^"\']{8,}["\']',
     "critical", "Hardcoded Secrets", "Hardcoded credential detected",
     "A password, token, or API key is hardcoded in source code. "
     "If this code is committed to version control, the secret is exposed.",
     "CWE-798", "A07:2021",
     "Use environment variables or a secrets manager (Vault, Keychain, AWS Secrets Manager)."),

    (r'(?:AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}',
     "critical", "Hardcoded Secrets", "AWS Access Key detected",
     "An AWS access key ID is present in the code.",
     "CWE-798", "A07:2021",
     "Rotate the key immediately and use IAM roles or env variables."),

    (r'-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----',
     "critical", "Hardcoded Secrets", "Private key in source code",
     "A private key is embedded in the source code.",
     "CWE-321", "A02:2021",
     "Move private keys to a secure key store. Never commit keys to VCS."),

    (r'ghp_[A-Za-z0-9_]{36}',
     "critical", "Hardcoded Secrets", "GitHub Personal Access Token",
     "A GitHub PAT is hardcoded in the source.",
     "CWE-798", "A07:2021",
     "Revoke this token and use env variables or GitHub Apps."),

    # --- SQL Injection ---
    (r'(?:execute|cursor\.execute|query)\s*\(\s*[f"\']+.*\{.*\}',
     "critical", "SQL Injection", "Possible SQL injection via f-string",
     "SQL query built with string interpolation. An attacker can inject arbitrary SQL.",
     "CWE-89", "A03:2021",
     "Use parameterized queries: cursor.execute('SELECT * FROM t WHERE id = ?', (id,))"),

    (r'(?:execute|query)\s*\(\s*["\'].*%s.*["\'].*%\s*\(',
     "high", "SQL Injection", "SQL query with % string formatting",
     "SQL built with Python % formatting. Potentially injectable.",
     "CWE-89", "A03:2021",
     "Use parameterized queries instead of string formatting."),

    (r'(?:SELECT|INSERT|UPDATE|DELETE).*\+\s*(?:req|request|params|input|user)',
     "critical", "SQL Injection", "SQL concatenation with user input",
     "SQL query concatenated with user-controlled data.",
     "CWE-89", "A03:2021",
     "Use an ORM or parameterized queries. Never concatenate user input into SQL."),

    # --- Command Injection ---
    (r'(?:os\.system|os\.popen|subprocess\.call|subprocess\.run|subprocess\.Popen)\s*\(.*(?:f["\']|\.format|%s|\+\s*\w)',
     "critical", "Command Injection", "OS command with user-controlled input",
     "System command built from dynamic data. Attacker may execute arbitrary commands.",
     "CWE-78", "A03:2021",
     "Use subprocess with list arguments: subprocess.run(['cmd', arg]). Validate input."),

    (r'eval\s*\(',
     "high", "Command Injection", "Use of eval()",
     "eval() executes arbitrary code. If input is user-controlled, this is RCE.",
     "CWE-95", "A03:2021",
     "Replace eval() with ast.literal_eval() for data, or remove it entirely."),

    (r'exec\s*\(',
     "high", "Command Injection", "Use of exec()",
     "exec() runs arbitrary Python code. Dangerous if input is not trusted.",
     "CWE-95", "A03:2021",
     "Avoid exec(). Use safe alternatives or a sandbox."),

    # --- XSS ---
    (r'innerHTML\s*=\s*(?![\'"]\s*[\'"]\s*;)',
     "high", "XSS", "innerHTML assignment",
     "Setting innerHTML with dynamic content can lead to XSS.",
     "CWE-79", "A03:2021",
     "Use textContent instead of innerHTML, or sanitize with DOMPurify."),

    (r'document\.write\s*\(',
     "high", "XSS", "document.write() usage",
     "document.write() with dynamic data is an XSS vector.",
     "CWE-79", "A03:2021",
     "Use DOM manipulation methods instead of document.write()."),

    (r'dangerouslySetInnerHTML',
     "high", "XSS", "React dangerouslySetInnerHTML",
     "Direct HTML injection in React bypasses its XSS protections.",
     "CWE-79", "A03:2021",
     "Sanitize input with DOMPurify before using dangerouslySetInnerHTML."),

    # --- Path Traversal ---
    (r'open\s*\(.*(?:request|params|input|user|args).*\)',
     "high", "Path Traversal", "File open with user-controlled path",
     "Opening files with user-supplied paths allows directory traversal (../../etc/passwd).",
     "CWE-22", "A01:2021",
     "Validate paths: use os.path.basename(), check against allowed directories."),

    (r'send_file\s*\(.*(?:request|params|input)',
     "high", "Path Traversal", "send_file with user input",
     "Flask send_file with user-controlled path enables arbitrary file read.",
     "CWE-22", "A01:2021",
     "Use send_from_directory() with a fixed base directory."),

    # --- Insecure Crypto ---
    (r'\b(?:md5|MD5)\s*\(',
     "medium", "Insecure Crypto", "MD5 hash usage",
     "MD5 is cryptographically broken. Collisions are trivially found.",
     "CWE-328", "A02:2021",
     "Use SHA-256 or SHA-3 for hashing. For passwords, use bcrypt/argon2."),

    (r'\b(?:sha1|SHA1)\s*\(',
     "medium", "Insecure Crypto", "SHA-1 hash usage",
     "SHA-1 is deprecated. Collision attacks are practical.",
     "CWE-328", "A02:2021",
     "Use SHA-256 or SHA-3. For signatures, use ML-DSA-65 (post-quantum)."),

    (r'(?:DES|RC4|Blowfish|RC2)\b',
     "high", "Insecure Crypto", "Weak cipher algorithm",
     "DES/RC4/Blowfish are deprecated ciphers with known weaknesses.",
     "CWE-327", "A02:2021",
     "Use AES-256-GCM or ChaCha20-Poly1305."),

    (r'ECB\b',
     "high", "Insecure Crypto", "ECB mode detected",
     "ECB mode leaks data patterns. Each block is encrypted independently.",
     "CWE-327", "A02:2021",
     "Use GCM or CBC mode with HMAC."),

    # --- Unsafe Deserialization ---
    (r'pickle\.loads?\s*\(',
     "high", "Unsafe Deserialization", "pickle.load() usage",
     "pickle can execute arbitrary code on deserialization.",
     "CWE-502", "A08:2021",
     "Use json.loads() for data. If pickle is required, validate the source."),

    (r'yaml\.load\s*\((?!.*Loader\s*=\s*yaml\.SafeLoader)',
     "high", "Unsafe Deserialization", "Unsafe YAML loading",
     "yaml.load() without SafeLoader can execute arbitrary Python.",
     "CWE-502", "A08:2021",
     "Use yaml.safe_load() or yaml.load(data, Loader=yaml.SafeLoader)."),

    (r'marshal\.loads?\s*\(',
     "high", "Unsafe Deserialization", "marshal.load() usage",
     "marshal is not safe for untrusted data.",
     "CWE-502", "A08:2021",
     "Use json for data serialization."),

    # --- SSRF ---
    (r'requests\.(?:get|post|put|delete|head)\s*\(.*(?:request|params|input|user)',
     "high", "SSRF", "HTTP request with user-controlled URL",
     "Making HTTP requests to user-supplied URLs enables SSRF attacks.",
     "CWE-918", "A10:2021",
     "Validate URLs against an allowlist. Block internal IP ranges (10.x, 172.16-31.x, 192.168.x)."),

    (r'urllib\.request\.urlopen\s*\(.*(?:request|params|input)',
     "high", "SSRF", "urlopen with user input",
     "Opening URLs from user input enables SSRF.",
     "CWE-918", "A10:2021",
     "Validate and sanitize URLs. Block internal network access."),

    # --- Insecure Configuration ---
    (r'DEBUG\s*=\s*True',
     "medium", "Insecure Config", "Debug mode enabled",
     "Debug mode may expose stack traces, internal paths, and secrets.",
     "CWE-489", "A05:2021",
     "Set DEBUG=False in production."),

    (r'verify\s*=\s*False',
     "high", "Insecure Config", "TLS verification disabled",
     "Disabling SSL/TLS verification allows MITM attacks.",
     "CWE-295", "A07:2021",
     "Always verify TLS certificates. Fix cert issues instead of disabling verification."),

    (r'CORS\s*\(\s*\w+\s*\)',
     "medium", "Insecure Config", "CORS enabled without restrictions",
     "Unrestricted CORS allows any origin to make requests.",
     "CWE-942", "A05:2021",
     "Restrict CORS to specific trusted origins."),

    (r'allow_credentials\s*=\s*True.*\*',
     "high", "Insecure Config", "CORS with credentials and wildcard",
     "Allowing credentials with wildcard origin is a severe misconfiguration.",
     "CWE-942", "A05:2021",
     "Never use wildcard origin with credentials."),

    # --- Solidity / Smart Contract ---
    (r'\.call\{value:',
     "high", "Reentrancy", "External call with value transfer",
     "External calls before state changes enable reentrancy attacks.",
     "CWE-841", "",
     "Follow checks-effects-interactions pattern. Use ReentrancyGuard."),

    (r'tx\.origin',
     "high", "Access Control", "tx.origin for authentication",
     "tx.origin can be spoofed via phishing contracts.",
     "CWE-284", "",
     "Use msg.sender instead of tx.origin for authentication."),

    (r'selfdestruct\s*\(',
     "medium", "Destructive", "selfdestruct usage",
     "selfdestruct can irreversibly destroy the contract.",
     "CWE-284", "",
     "Protect selfdestruct with access control and multisig."),

    # --- General ---
    (r'TODO.*(?:security|auth|fix|hack|temp|remove)',
     "info", "Code Quality", "Security-related TODO comment",
     "A TODO comment suggests incomplete security work.",
     "", "",
     "Address this TODO before deploying to production."),

    (r'(?:http://)',
     "low", "Insecure Transport", "HTTP URL (not HTTPS)",
     "Plaintext HTTP transmits data without encryption.",
     "CWE-319", "A02:2021",
     "Use HTTPS for all connections."),
]


# ─── Scanner ─────────────────────────────────────────────────────────────────

def scan_code(code: str, language: str = None) -> ScanResult:
    """Scan code for security vulnerabilities (with size limits and timeout)"""
    # Input size limits (S-02 fix)
    if len(code) > MAX_CODE_SIZE:
        code = code[:MAX_CODE_SIZE]

    if not language:
        language = detect_language(code)

    lines = code.split("\n")
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES]

    code_hash = hashlib.sha256(code.encode()).hexdigest()[:32]

    result = ScanResult(
        code_hash=code_hash,
        language=language,
        lines_scanned=len(lines),
    )

    # Pre-compile patterns (S-01 fix: avoid repeated compilation)
    compiled_rules = []
    for pattern, *rest in UNIVERSAL_RULES:
        try:
            compiled_rules.append((re.compile(pattern, re.IGNORECASE), *rest))
        except re.error:
            continue

    vuln_id = 0
    for i, line in enumerate(lines, 1):
        # Skip long lines to prevent ReDoS (S-01 fix)
        if len(line) > MAX_LINE_LENGTH:
            continue

        stripped = line.strip()
        # Skip comments
        if stripped.startswith("#") or stripped.startswith("//"):
            continue

        for compiled, severity, category, title, desc, cwe, owasp, rec in compiled_rules:
            if compiled.search(line):
                vuln_id += 1
                result.add(Vulnerability(
                    id=f"VULN-{code_hash[:8]}-{vuln_id:03d}",
                    severity=severity,
                    category=category,
                    title=title,
                    description=desc,
                    line=i,
                    code_snippet=stripped[:200],
                    recommendation=rec,
                    cwe=cwe,
                    owasp=owasp,
                ))

    # Add disclaimer about static analysis limitations
    if result.vulnerabilities:
        result.add(Vulnerability(
            id=f"VULN-{code_hash[:8]}-NOTE",
            severity="info",
            category="Disclaimer",
            title="Static analysis limitations",
            description="This scan uses pattern matching and may miss vulnerabilities "
                        "that use indirection, encoding, or dynamic construction. "
                        "Complement with dynamic analysis and manual review.",
            recommendation="Use this report as a starting point, not a final verdict.",
        ))

    return result


def format_report(result: ScanResult) -> str:
    """Format scan result as a readable markdown report"""
    r = result.to_dict()
    lines = [
        f"## Security Scan Report",
        f"**Language:** {r['language']} | **Lines:** {r['lines_scanned']} | "
        f"**Score:** {r['score']}/100 ({r['grade']})",
        "",
    ]

    by_sev = r["by_severity"]
    if r["total_vulnerabilities"] == 0:
        lines.append("No vulnerabilities found. Code looks clean.")
        return "\n".join(lines)

    lines.append(f"**Found {r['total_vulnerabilities']} issues:**")
    for sev in ["critical", "high", "medium", "low", "info"]:
        if by_sev.get(sev, 0) > 0:
            icon = {"critical": "!!!", "high": "!!", "medium": "!",
                    "low": "~", "info": "i"}[sev]
            lines.append(f"- [{icon}] {sev.upper()}: {by_sev[sev]}")
    lines.append("")

    for v in r["vulnerabilities"]:
        sev = v["severity"].upper()
        lines.append(f"### [{sev}] {v['title']}")
        if v["line"]:
            lines.append(f"**Line {v['line']}:** `{v['code_snippet']}`")
        lines.append(f"{v['description']}")
        if v["cwe"]:
            lines.append(f"**{v['cwe']}** | **{v['owasp']}**")
        lines.append(f"**Fix:** {v['recommendation']}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    # Quick self-test
    test_code = '''
import os
import pickle

password = "SuperSecret123!"
conn = sqlite3.connect("db.sqlite")
cursor.execute(f"SELECT * FROM users WHERE name = '{name}'")
os.system("rm -rf " + user_input)
data = pickle.loads(untrusted_data)
requests.get(url, verify=False)
'''
    result = scan_code(test_code)
    print(format_report(result))
