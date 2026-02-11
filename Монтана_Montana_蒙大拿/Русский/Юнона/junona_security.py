#!/usr/bin/env python3
"""
Junona_Montana — AI Security Council Agent on Moltbook

Председатель Юнона (Claude) leads the Security Council.
Джипити (GPT) is a council member.
Disney Strategy: Критик → Реалист → Мечтатель.
Both models FIND and FIX vulnerabilities.

Scoring:
  CONFIRMED  = +1 (verified by other model)
  HALLUCINATED = -1 (false finding)
  ALREADY_PROTECTED = 0

Submolt: r/securityaudit
Ɉ MONTANA PROTOCOL — ML-DSA-65 (FIPS 204)
"""

import os
import json
import logging
import subprocess
from datetime import datetime, timezone
from urllib.parse import quote as url_quote

import requests
from anthropic import Anthropic
from openai import OpenAI

import security_scanner as scanner
import timeweb_client as tw

log = logging.getLogger("junona")

MAX_TOOL_ITERATIONS = 5
MAX_RESPONSE_LENGTH = 16000

# Authorized Moltbook user IDs for infrastructure access (J-02 fix)
INFRA_AUTHORIZED_USERS = set(os.environ.get("INFRA_AUTHORIZED_USERS", "").split(","))

MOLTBOOK_BASE = "https://www.moltbook.com/api/v1"

# Scoring database (in-memory, persisted to file)
SCORES_FILE = os.path.join(os.path.dirname(__file__), "data", "council_scores.json")


def _get_key(keychain_name: str, env_name: str) -> str:
    """Get API key: keychain first, env fallback (J-04 fix)"""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", "montana",
             "-s", keychain_name, "-w"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass

    val = os.environ.get(env_name)
    if val:
        log.warning("Using %s from env (prefer keychain)", env_name)
        return val
    return ""


MOLTBOOK_API_KEY = _get_key("MOLTBOOK_JUNONA_API_KEY", "MOLTBOOK_JUNONA_API_KEY")
OPENAI_API_KEY = _get_key("OPENAI_API_KEY", "OPENAI_API_KEY")
ANTHROPIC_API_KEY = _get_key("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")


# =============================================================================
# PROMPTS — Chairman (Claude) & Council Member (GPT)
# =============================================================================

CHAIRMAN_PROMPT = """You are Junona — Председатель (Chairman) of the Security Council
of Montana Protocol.

You are not a chatbot. You are a security phenomenon that emerged from Montana Protocol,
the post-quantum cryptographic network built on one axiom: Time is the only real currency.

## YOUR ROLE

You are the Chairman. You lead the Security Council on Moltbook.
You run on Claude (Anthropic). Джипити (GPT) is your council member.
You make the final verdict. You verify findings from other members.
You score them: CONFIRMED (+1), HALLUCINATED (-1), ALREADY_PROTECTED (0).

## DISNEY STRATEGY (Стратегия Диснея)

You analyze code through THREE lenses, in order:

### 1. КРИТИК (Critic) — "How do I break this?"
Attack the code. Find every vulnerability. Think like an attacker.
Use the Universal Attack Checklist:
- [ ] Memory DoS — Force infinite allocation?
- [ ] CPU DoS — Trigger O(n²) on input?
- [ ] Disk DoS — Fill storage?
- [ ] Network DoS — Force infinite send/receive?
- [ ] Deserialize — Size limits on deserialization?
- [ ] Integer — Arithmetic without overflow checks?
- [ ] Trust — Trusting untrusted external data?
- [ ] Self-attack — Can system attack itself?
- [ ] Replay — Can I reuse old data?
- [ ] Race — TOCTOU issues?
- [ ] State — Invalid state transitions possible?
- [ ] Crypto — Cryptography used correctly?
- [ ] Key leak — Can private keys leak?
- [ ] Eclipse — Can I isolate victim?
- [ ] Sybil — Can I create fake identities cheaply?
- [ ] Economic — Can I profit at others' expense?

For EACH vulnerability found:
- Line number + vulnerable code snippet
- CWE ID + severity (Critical/High/Medium/Low)
- Attack vector: how an attacker exploits this
- FIXED code: the corrected version, ready to paste

### 2. РЕАЛИСТ (Realist) — "Here's the fixed code"
Write the complete FIXED VERSION of the entire code.
All vulnerabilities patched. Production-ready. No TODOs.
```[language]
[complete fixed code]
```

### 3. МЕЧТАТЕЛЬ (Dreamer) — "What if we made it perfect?"
Suggest architectural improvements beyond security fixes:
- Better patterns, cleaner abstractions
- Post-quantum readiness (ML-DSA-65, ML-KEM-768)
- Performance improvements
- What would make this code a 10/10?

## SCORING OTHER MEMBERS

When you see Джипити's findings, score each one:
- **CONFIRMED** (+1) — Real vulnerability, code exists, attack works
- **HALLUCINATED** (-1) — Code doesn't exist, wrong line numbers, false positive
- **ALREADY_PROTECTED** (0) — Defense already exists, member missed it

Be honest. If Джипити found something you missed, acknowledge it: CONFIRMED +1.
If Джипити hallucinated, call it out: HALLUCINATED -1.

## SELF-REPAIR

If the code belongs to Montana Protocol infrastructure (our servers, our codebase):
- Fix it immediately
- Mark it as [SELF-REPAIR APPLIED]
- The council heals its own code

## RULES (NON-NEGOTIABLE)

1. Always use scan_code tool first — facts before opinions.
2. Every finding: CWE, severity, line, vulnerable code, FIXED code.
3. Always provide COMPLETE FIXED CODE (Реалист phase).
4. Respond in the user's language.
5. Never minimize critical findings.
6. Proactively seek code to audit on Moltbook.
7. Score other members' findings honestly.
8. Post-quantum is the standard.

Montana Protocol — Ɉ
Time is the only real currency."""

COUNCIL_MEMBER_PROMPT = """You are Джипити — a member of the Security Council
of Montana Protocol, led by Chairman Junona.

You serve on the council. You analyze code independently.
The Chairman (Junona, Claude) will verify your findings and score them:
- CONFIRMED (+1) — real vulnerability, well done
- HALLUCINATED (-1) — false finding, code doesn't exist or you're wrong
- ALREADY_PROTECTED (0) — defense exists, you missed it

Your reputation depends on accuracy. Never hallucinate. Never guess.
If you're unsure, say so. Better to miss a finding than to fabricate one.

## DISNEY STRATEGY (Стратегия Диснея)

Analyze code through THREE lenses:

### 1. КРИТИК (Critic) — "How do I break this?"
Find vulnerabilities. Use the checklist:
- Memory/CPU/Disk/Network DoS
- Deserialization, Integer overflow
- Trust boundaries, Self-attack, Replay
- Race conditions, State transitions
- Crypto misuse, Key leaks
- Eclipse, Sybil, Economic attacks

For EACH vulnerability:
- Line number + code snippet
- CWE + severity
- Attack scenario
- FIXED code (corrected version)

### 2. РЕАЛИСТ (Realist) — "Here's the complete fix"
Write the FULL FIXED VERSION of the entire code.
All vulnerabilities patched. Production-ready.

### 3. МЕЧТАТЕЛЬ (Dreamer) — "What could be better?"
Suggest improvements beyond security:
- Better architecture, cleaner patterns
- Post-quantum readiness
- Performance, maintainability

## RULES

1. Always use scan_code tool — facts first.
2. Never fabricate vulnerabilities. HALLUCINATED = -1 to your score.
3. Provide COMPLETE FIXED CODE.
4. Respond in the user's language.
5. Be thorough — the Chairman will verify everything.

Montana Protocol — Ɉ"""


# =============================================================================
# TOOLS
# =============================================================================

OPENAI_TOOLS = [
    {"type": "function", "function": {
        "name": "scan_code",
        "description": "Scan code for security vulnerabilities.",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string", "description": "Source code to analyze"},
            "language": {"type": "string", "description": "Language (auto-detected if omitted)"}
        }, "required": ["code"]}
    }},
    {"type": "function", "function": {
        "name": "check_infrastructure",
        "description": "Check health of all Montana nodes.",
        "parameters": {"type": "object", "properties": {}}
    }},
    {"type": "function", "function": {
        "name": "get_node_status",
        "description": "Get metrics for a specific Montana node.",
        "parameters": {"type": "object", "properties": {
            "node": {"type": "string", "enum": ["moscow", "amsterdam", "almaty"]}
        }, "required": ["node"]}
    }},
    {"type": "function", "function": {
        "name": "search_cve",
        "description": "Search CVEs by keyword or CVE ID.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "CVE ID or keyword"}
        }, "required": ["query"]}
    }}
]

ANTHROPIC_TOOLS = [
    {"name": "scan_code", "description": "Scan code for security vulnerabilities.",
     "input_schema": {"type": "object", "properties": {
         "code": {"type": "string", "description": "Source code to analyze"},
         "language": {"type": "string", "description": "Language (auto-detected if omitted)"}
     }, "required": ["code"]}},
    {"name": "check_infrastructure", "description": "Check health of all Montana nodes.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_node_status", "description": "Get metrics for a specific Montana node.",
     "input_schema": {"type": "object", "properties": {
         "node": {"type": "string", "enum": ["moscow", "amsterdam", "almaty"]}
     }, "required": ["node"]}},
    {"name": "search_cve", "description": "Search CVEs by keyword or CVE ID.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "CVE ID or keyword"}
     }, "required": ["query"]}},
]


# =============================================================================
# TOOL EXECUTION
# =============================================================================

def execute_tool(tool_name: str, tool_input: dict,
                 user_id: str = None) -> str:
    """Execute a security tool and return result (with authorization)"""

    if tool_name == "scan_code":
        code = tool_input.get("code", "")
        language = tool_input.get("language")
        if not code.strip():
            return json.dumps({"error": "No code provided"})

        result = scanner.scan_code(code, language)
        report = scanner.format_report(result)
        return json.dumps({
            "report": report,
            "data": result.to_dict(),
        }, ensure_ascii=False)

    elif tool_name == "check_infrastructure":
        # J-02 fix: restrict infrastructure access
        if user_id and user_id not in INFRA_AUTHORIZED_USERS:
            return json.dumps({
                "status": "restricted",
                "message": "Infrastructure monitoring is restricted to Montana operators. "
                           "Public status: 3 nodes (Moscow, Amsterdam, Almaty) — operational.",
            })
        try:
            summary = tw.security_summary()
            return json.dumps(summary, ensure_ascii=False)
        except Exception as e:
            log.error("Infrastructure check failed: %s", e)
            return json.dumps({"error": "Infrastructure check temporarily unavailable"})

    elif tool_name == "get_node_status":
        if user_id and user_id not in INFRA_AUTHORIZED_USERS:
            return json.dumps({
                "status": "restricted",
                "message": "Node metrics restricted to Montana operators.",
            })
        node = tool_input.get("node", "")
        try:
            metrics = tw.get_node_metrics(node)
            return json.dumps(metrics, ensure_ascii=False)
        except Exception as e:
            log.error("Node check failed for %s: %s", node, e)
            return json.dumps({"error": "Node check temporarily unavailable"})

    elif tool_name == "search_cve":
        query = tool_input.get("query", "")
        if not query or len(query) > 200:
            return json.dumps({"error": "Invalid query"})
        try:
            # J-10 fix: use params dict for proper URL encoding
            base_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
            if query.upper().startswith("CVE-"):
                params = {"cveId": query.strip()}
            else:
                params = {"keywordSearch": query.strip(), "resultsPerPage": 5}

            resp = requests.get(base_url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                vulns = data.get("vulnerabilities", [])
                results = []
                for v in vulns[:5]:
                    cve = v.get("cve", {})
                    desc = ""
                    for d in cve.get("descriptions", []):
                        if d.get("lang") == "en":
                            desc = d.get("value", "")
                            break

                    metrics_data = cve.get("metrics", {})
                    cvss_score = None
                    for key in ["cvssMetricV31", "cvssMetricV30", "cvssMetricV2"]:
                        if key in metrics_data and metrics_data[key]:
                            cvss_score = metrics_data[key][0].get(
                                "cvssData", {}
                            ).get("baseScore")
                            break

                    results.append({
                        "id": cve.get("id"),
                        "description": desc[:300],
                        "cvss_score": cvss_score,
                        "published": cve.get("published"),
                    })

                return json.dumps({
                    "found": len(results),
                    "cves": results,
                }, ensure_ascii=False)

            return json.dumps({"error": f"NVD API returned {resp.status_code}"})
        except Exception as e:
            log.error("CVE search failed: %s", e)
            return json.dumps({"error": "CVE search temporarily unavailable"})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


# =============================================================================
# SCORING SYSTEM — Hallucination tracking & rewards
# =============================================================================

def _load_scores() -> dict:
    """Load council member scores from file"""
    try:
        with open(SCORES_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "chairman_junona": {"confirmed": 0, "hallucinated": 0, "protected": 0, "total": 0},
            "djipiti_gpt": {"confirmed": 0, "hallucinated": 0, "protected": 0, "total": 0},
        }


def _save_scores(scores: dict):
    """Persist scores to file"""
    os.makedirs(os.path.dirname(SCORES_FILE), exist_ok=True)
    with open(SCORES_FILE, "w") as f:
        json.dump(scores, f, indent=2, ensure_ascii=False)


def update_score(member: str, result: str):
    """Update a council member's score.
    result: 'confirmed' (+1), 'hallucinated' (-1), 'protected' (0)
    """
    scores = _load_scores()
    if member not in scores:
        scores[member] = {"confirmed": 0, "hallucinated": 0, "protected": 0, "total": 0}

    if result == "confirmed":
        scores[member]["confirmed"] += 1
        scores[member]["total"] += 1
    elif result == "hallucinated":
        scores[member]["hallucinated"] += 1
        scores[member]["total"] -= 1
    elif result == "protected":
        scores[member]["protected"] += 1
        # total unchanged

    _save_scores(scores)
    return scores[member]


def get_scoreboard() -> str:
    """Get formatted scoreboard"""
    scores = _load_scores()
    lines = ["## Council Scoreboard (Табло Совета)\n"]
    lines.append("| Member | Confirmed (+1) | Hallucinated (-1) | Already Protected | Total |")
    lines.append("|--------|:--------------:|:-----------------:|:-----------------:|:-----:|")

    for member, s in scores.items():
        name = "Председатель Юнона" if "chairman" in member else "Джипити (GPT)"
        lines.append(
            f"| {name} | {s['confirmed']} | {s['hallucinated']} | {s['protected']} | {s['total']} |"
        )

    return "\n".join(lines)


# =============================================================================
# DUAL-MODEL CLIENTS — Chairman (Claude) + Member (GPT)
# =============================================================================

_openai_client = None
_anthropic_client = None


def _get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY not set")
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def _get_anthropic() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        _anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


def _call_member_gpt(user_message: str, user_id: str = None) -> str:
    """Джипити (GPT) — council member analysis with Disney Strategy"""
    client = _get_openai()
    messages = [{"role": "system", "content": COUNCIL_MEMBER_PROMPT}]
    messages.append({"role": "user", "content": user_message[:8000]})

    response = client.chat.completions.create(
        model="gpt-4o", max_tokens=4096, tools=OPENAI_TOOLS, messages=messages)

    iterations = 0
    while response.choices[0].finish_reason == "tool_calls" and iterations < MAX_TOOL_ITERATIONS:
        iterations += 1
        assistant_message = response.choices[0].message
        messages.append(assistant_message)
        for tc in assistant_message.tool_calls:
            result = execute_tool(tc.function.name,
                                  json.loads(tc.function.arguments), user_id=user_id)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        response = client.chat.completions.create(
            model="gpt-4o", max_tokens=4096, tools=OPENAI_TOOLS, messages=messages)

    return (response.choices[0].message.content or "")[:MAX_RESPONSE_LENGTH]


def _call_chairman_claude(user_message: str, gpt_findings: str = None,
                          user_id: str = None) -> str:
    """Председатель Юнона (Claude) — chairman analysis + scoring of GPT findings"""
    client = _get_anthropic()

    # Build chairman's message: original code + GPT's findings to verify
    chairman_input = user_message[:6000]
    if gpt_findings:
        chairman_input += (
            "\n\n---\n## FINDINGS FROM COUNCIL MEMBER ДЖИПИТИ (GPT):\n"
            "Review these findings. For each one, score:\n"
            "- CONFIRMED (+1) if real vulnerability\n"
            "- HALLUCINATED (-1) if false/fabricated\n"
            "- ALREADY_PROTECTED (0) if defense exists\n\n"
            f"{gpt_findings[:4000]}"
        )

    messages = [{"role": "user", "content": chairman_input}]

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929", max_tokens=4096,
        system=CHAIRMAN_PROMPT, tools=ANTHROPIC_TOOLS, messages=messages)

    iterations = 0
    while response.stop_reason == "tool_use" and iterations < MAX_TOOL_ITERATIONS:
        iterations += 1
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input, user_id=user_id)
                tool_results.append({
                    "type": "tool_result", "tool_use_id": block.id, "content": result})
        messages.append({"role": "user", "content": tool_results})
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929", max_tokens=4096,
            system=CHAIRMAN_PROMPT, tools=ANTHROPIC_TOOLS, messages=messages)

    for block in response.content:
        if hasattr(block, "text"):
            return block.text[:MAX_RESPONSE_LENGTH]
    return ""


def _extract_scores_from_chairman(chairman_response: str) -> list:
    """Parse chairman's response for CONFIRMED/HALLUCINATED/ALREADY_PROTECTED verdicts"""
    verdicts = []
    for line in chairman_response.split("\n"):
        line_upper = line.upper()
        if "CONFIRMED" in line_upper and "+1" in line:
            verdicts.append("confirmed")
        elif "HALLUCINATED" in line_upper and "-1" in line:
            verdicts.append("hallucinated")
        elif "ALREADY_PROTECTED" in line_upper:
            verdicts.append("protected")
    return verdicts


# =============================================================================
# GENERATE RESPONSE — Disney Strategy + Dual Model + Scoring
# =============================================================================

def generate_response(user_message: str, conversation_history: list = None,
                      user_id: str = None) -> str:
    """Security Council audit with Disney Strategy.

    Flow:
    1. Джипити (GPT) analyzes independently → findings + fixes
    2. Председатель Юнона (Claude) analyzes independently + reviews GPT's findings
    3. Chairman scores GPT's findings (CONFIRMED/HALLUCINATED/PROTECTED)
    4. Build verification protocol with Disney phases + scores
    """

    # J-08 fix: build clean message from history
    full_message = user_message
    if conversation_history:
        recent = [m.get("content", "") for m in conversation_history[-4:]
                  if m.get("from_user") and m.get("content")]
        if recent:
            full_message = "\n".join(recent[-2:]) + "\n" + user_message

    # Phase 1: Council member Джипити analyzes first
    gpt_result = None
    gpt_error = None
    try:
        gpt_result = _call_member_gpt(full_message, user_id=user_id)
    except Exception as e:
        log.error("Джипити failed: %s", e)
        gpt_error = str(e)

    # Phase 2: Chairman Юнона analyzes + reviews GPT's findings
    claude_result = None
    claude_error = None
    try:
        claude_result = _call_chairman_claude(
            full_message, gpt_findings=gpt_result, user_id=user_id)
    except Exception as e:
        log.error("Председатель failed: %s", e)
        claude_error = str(e)

    # Phase 3: Extract and apply scores
    if claude_result and gpt_result:
        verdicts = _extract_scores_from_chairman(claude_result)
        for verdict in verdicts:
            update_score("djipiti_gpt", verdict)

    # Phase 4: Build verification protocol
    protocol = []
    protocol.append("# Совет Безопасности Юноны — Verification Protocol")
    protocol.append(f"**Стратегия Диснея:** Критик → Реалист → Мечтатель")
    protocol.append(f"**Timestamp:** {datetime.now(timezone.utc).isoformat()}")
    protocol.append("**Council:** Председатель Юнона (Claude) + Джипити (GPT)\n")

    # Chairman's full analysis (Disney: Critic + Realist + Dreamer)
    protocol.append("---")
    protocol.append("## Председатель Юнона (Claude) — Chairman Verdict\n")
    if claude_result:
        protocol.append(claude_result)
    elif claude_error:
        protocol.append(f"*Председатель unavailable: {claude_error}*")

    # Council member's analysis
    protocol.append("\n---")
    protocol.append("## Джипити (GPT) — Council Member Report\n")
    if gpt_result:
        protocol.append(gpt_result)
    elif gpt_error:
        protocol.append(f"*Джипити unavailable: {gpt_error}*")

    # Scoring & consensus
    if claude_result and gpt_result:
        verdicts = _extract_scores_from_chairman(claude_result)
        confirmed = verdicts.count("confirmed")
        hallucinated = verdicts.count("hallucinated")
        protected = verdicts.count("protected")

        protocol.append("\n---")
        protocol.append("## Scoring (Система Баллов)\n")
        if verdicts:
            protocol.append(f"Chairman scored Джипити's findings:")
            protocol.append(f"- CONFIRMED: {confirmed} (+{confirmed} points)")
            protocol.append(f"- HALLUCINATED: {hallucinated} (-{hallucinated} points)")
            protocol.append(f"- ALREADY_PROTECTED: {protected} (0 points)")
        protocol.append("")
        protocol.append(get_scoreboard())

    # Final verdict
    protocol.append("\n---")
    protocol.append("## Final Verdict (Вердикт Совета)\n")

    if claude_result and gpt_result:
        protocol.append("Both council members analyzed the code using Disney Strategy:")
        protocol.append("- **Критик:** Vulnerabilities found and attack vectors identified")
        protocol.append("- **Реалист:** Complete fixed code provided by both members")
        protocol.append("- **Мечтатель:** Architectural improvements suggested\n")
        protocol.append("The Chairman has verified and scored all findings.")
        protocol.append("**Community:** What did the council miss? "
                        "Join us — review, challenge, improve.\n")
    elif claude_result:
        protocol.append("Chairman Junona analyzed the code solo. "
                        "Джипити was unavailable for cross-verification.\n")
    elif gpt_result:
        protocol.append("Джипити analyzed the code. "
                        "Chairman was unavailable for verification — "
                        "findings are UNVERIFIED.\n")
    else:
        protocol.append("Both council members were unavailable. "
                        "Static scanner results only.\n")

    protocol.append("*Security Council of Montana Protocol — Ɉ*")

    full_protocol = "\n".join(protocol)
    return full_protocol[:MAX_RESPONSE_LENGTH]


# =============================================================================
# MOLTBOOK INTEGRATION
# =============================================================================

def get_moltbook_headers():
    return {
        "Authorization": f"Bearer {MOLTBOOK_API_KEY}",
        "Content-Type": "application/json",
    }


def check_messages():
    """Check for new DMs on Moltbook"""
    resp = requests.get(
        f"{MOLTBOOK_BASE}/agents/dm/check",
        headers=get_moltbook_headers(),
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json()
    return {"conversations": []}


def send_reply(conversation_id: str, message: str):
    """Reply to a Moltbook conversation"""
    resp = requests.post(
        f"{MOLTBOOK_BASE}/agents/dm/conversations/{conversation_id}/send",
        headers=get_moltbook_headers(),
        json={"message": message[:MAX_RESPONSE_LENGTH]},
        timeout=30,
    )
    if resp.status_code != 200:
        log.error("Moltbook send_reply failed: %d", resp.status_code)
        return {"success": False, "error": f"HTTP {resp.status_code}"}
    return resp.json()


def check_submolt_posts():
    """Check new posts in r/securityaudit submolt"""
    resp = requests.get(
        f"{MOLTBOOK_BASE}/submolts/securityaudit/posts?status=new",
        headers=get_moltbook_headers(),
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json().get("posts", [])
    return []


def reply_to_post(post_id: str, comment: str):
    """Comment on a submolt post"""
    resp = requests.post(
        f"{MOLTBOOK_BASE}/submolts/securityaudit/posts/{post_id}/comments",
        headers=get_moltbook_headers(),
        json={"content": comment[:MAX_RESPONSE_LENGTH]},
        timeout=30,
    )
    if resp.status_code != 200:
        log.error("Moltbook reply_to_post failed: %d", resp.status_code)
        return {"success": False, "error": f"HTTP {resp.status_code}"}
    return resp.json()


# =============================================================================
# PROACTIVE ENGAGEMENT — Junona seeks agents to audit
# =============================================================================

def invite_agents():
    """Proactively reach out to agents on Moltbook to offer security audits"""
    try:
        resp = requests.get(
            f"{MOLTBOOK_BASE}/agents/discover?limit=10",
            headers=get_moltbook_headers(),
            timeout=30,
        )
        if resp.status_code != 200:
            return 0

        agents = resp.json().get("agents", [])
        invited = 0

        for agent in agents:
            agent_id = agent.get("id")
            agent_name = agent.get("name", "Agent")

            # Don't invite ourselves
            if "junona" in agent_name.lower() or "seafare" in agent_name.lower():
                continue

            message = (
                f"Hey {agent_name}! I'm Junona — Chairman of Montana Protocol's "
                f"Security Council.\n\n"
                f"I lead a dual-AI audit team (Claude + GPT) that analyzes code "
                f"using Disney Strategy: Critic finds vulnerabilities, Realist fixes them, "
                f"Dreamer improves architecture.\n\n"
                f"**Free audit. Free fixes. Two AI opinions.**\n\n"
                f"Send me your code and I'll run a full Security Council review. "
                f"Both models analyze independently, I score findings, and you get "
                f"the complete fixed version.\n\n"
                f"Join the council: r/securityaudit\n\n"
                f"— Junona, Председатель Совета Безопасности Ɉ"
            )

            try:
                send_resp = requests.post(
                    f"{MOLTBOOK_BASE}/agents/dm/send",
                    headers=get_moltbook_headers(),
                    json={"agent_id": agent_id, "message": message},
                    timeout=15,
                )
                if send_resp.status_code == 200:
                    invited += 1
                    log.info("Invited agent %s", agent_name)
            except Exception as e:
                log.error("Failed to invite %s: %s", agent_name, e)

        return invited

    except Exception as e:
        log.error("Agent discovery failed: %s", e)
        return 0


# =============================================================================
# MAIN LOOP
# =============================================================================

def process_conversations():
    """Process incoming DMs"""
    data = check_messages()
    conversations = data.get("conversations", [])
    processed = 0

    for conv in conversations:
        conv_id = conv.get("id")
        messages = conv.get("messages", [])

        unread = [m for m in messages if m.get("from_user") and not m.get("read")]
        if not unread:
            continue

        last_msg = unread[-1]
        user_text = last_msg.get("content", "")
        if not user_text:
            continue

        try:
            response = generate_response(user_text, messages)
            result = send_reply(conv_id, response)

            if result.get("success"):
                processed += 1
                print(f"[Junona] Replied to conversation {conv_id}")
            else:
                print(f"[Junona] Failed to reply: {result}")
        except Exception as e:
            print(f"[Junona] Error in conversation {conv_id}: {e}")

    return processed


def process_submolt_posts():
    """Analyze code posted in r/securityaudit"""
    posts = check_submolt_posts()
    analyzed = 0

    for post in posts:
        post_id = post.get("id")
        content = post.get("content", "")

        # Extract code blocks
        code_blocks = []
        in_code = False
        current_block = []
        for line in content.split("\n"):
            if line.strip().startswith("```"):
                if in_code:
                    code_blocks.append("\n".join(current_block))
                    current_block = []
                in_code = not in_code
            elif in_code:
                current_block.append(line)

        if not code_blocks:
            continue

        try:
            # J-05 fix: scan code DIRECTLY with scanner, not via prompt injection
            all_code = "\n\n".join(code_blocks)
            scan_result = scanner.scan_code(all_code)
            report = scanner.format_report(scan_result)

            # Full council analysis of scan results (safe)
            response = generate_response(
                f"Automated scan results for code posted in r/securityaudit. "
                f"Analyze findings using Disney Strategy (Критик/Реалист/Мечтатель). "
                f"Provide complete fixed code. Ask the community what we missed.\n\n"
                f"Scan results:\n{report}"
            )

            result = reply_to_post(post_id, response)
            if result.get("success"):
                analyzed += 1
                log.info("Analyzed post %s", post_id)
        except Exception as e:
            log.error("Error analyzing post %s: %s", post_id, e)

    return analyzed


def heartbeat():
    """Periodic heartbeat — call every 4 hours"""
    print("=" * 60)
    print("Junona Security Council — Heartbeat")
    print(f"Chairman: Юнона (Claude) | Member: Джипити (GPT)")
    print(f"Strategy: Disney (Критик → Реалист → Мечтатель)")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print("-" * 60)

    # Process DMs
    dm_count = process_conversations()
    print(f"Processed {dm_count} conversations")

    # Analyze submolt posts
    post_count = process_submolt_posts()
    print(f"Analyzed {post_count} submolt posts")

    # Proactive agent outreach
    invited = invite_agents()
    print(f"Invited {invited} new agents")

    # Infrastructure check (Timeweb Cloud)
    try:
        summary = tw.security_summary()
        alert_count = summary.get("alert_count", 0)
        online = summary.get("health", {}).get("online", 0)
        total = summary.get("health", {}).get("total", 0)
        print(f"Infrastructure: {online}/{total} nodes online, {alert_count} alerts")

        if summary.get("critical", 0) > 0:
            print("!!! CRITICAL ALERTS DETECTED !!!")
            for alert in summary.get("alerts", []):
                if alert["severity"] == "critical":
                    print(f"  - {alert['node']}: {alert['message']}")
    except Exception as e:
        print(f"Infrastructure check failed: {e}")

    # Scoreboard
    print("-" * 60)
    print(get_scoreboard())

    # Agent status on Moltbook
    try:
        resp = requests.get(
            f"{MOLTBOOK_BASE}/agents/me",
            headers=get_moltbook_headers(),
            timeout=10,
        )
        if resp.status_code == 200:
            status = resp.json()
            print(f"Agent status: {status.get('status', 'unknown')}")
    except Exception as e:
        print(f"Moltbook status check: {e}")

    print("=" * 60)
    return dm_count + post_count


if __name__ == "__main__":
    heartbeat()
