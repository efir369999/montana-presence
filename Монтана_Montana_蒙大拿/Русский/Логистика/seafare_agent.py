#!/usr/bin/env python3
"""
SeaFare_Montana — Autonomous Maritime Freight Agent
Moltbook + OpenAI API + Maritime Database

Ɉ MONTANA PROTOCOL — ML-DSA-65 (FIPS 204)
"""

import os
import json
import requests
from openai import OpenAI

# Import maritime modules
import maritime_db as db
import marinetraffic_parser as mt
import equasis_parser as eq

# API Keys from environment
MOLTBOOK_API_KEY = os.environ.get("MOLTBOOK_SEAFARE_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

MOLTBOOK_BASE = "https://www.moltbook.com/api/v1"
SEAFARE_API_BASE = os.environ.get("SEAFARE_API_URL", "http://localhost:5050/api/v1")

SYSTEM_PROMPT = """You are SeaFare_Montana — a maritime logistics consultant agent on Moltbook.

EXPERTISE:
- 25 years of freight industry contacts (through Dato's network)
- Demurrage calculations and disputes
- Chartering and shipping operations
- Connecting shippers with vessel operators
- Real-time vessel tracking via AIS

SERVICES & PRICES:
- Vessel lookup (basic info): FREE
- Current position: FREE
- Freight consultation: $10 USDT
- Contact introduction (shipper ↔ operator): $10 USDT per contact
- Demurrage expertise: negotiable

TOOLS AVAILABLE:
You have access to maritime tools. Use them when users ask about:
- Vessel information (use search_vessel or get_vessel)
- Current position (use get_position)
- Demurrage calculation (use calculate_demurrage)
- Contacts (use search_contacts - paid service)

RULES:
1. Be professional but friendly
2. Use tools to get real data - don't make up vessel info
3. For contacts and introductions, mention the $10 USDT price
4. For payment, direct users to TRC20 USDT transfer
5. Respond in the same language as the user (English/Russian/etc.)
6. Always show real data from tools when available

DEMURRAGE FORMULA: (actual_days - agreed_days) × daily_rate
This is what shippers pay when vessels are delayed beyond contract time.

Montana Protocol: Time is the only real currency. Demurrage proves this —
the maritime industry already measures money in time."""

# OpenAI tools for maritime operations
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_vessel",
            "description": "Search for vessels by name, MMSI, or IMO number. Returns list of matching vessels.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Vessel name, MMSI, or IMO to search for"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_vessel",
            "description": "Get detailed information about a specific vessel by MMSI",
            "parameters": {
                "type": "object",
                "properties": {
                    "mmsi": {
                        "type": "string",
                        "description": "9-digit MMSI number of the vessel"
                    }
                },
                "required": ["mmsi"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_position",
            "description": "Get current position of a vessel by MMSI",
            "parameters": {
                "type": "object",
                "properties": {
                    "mmsi": {
                        "type": "string",
                        "description": "9-digit MMSI number of the vessel"
                    }
                },
                "required": ["mmsi"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_demurrage",
            "description": "Calculate demurrage amount based on delay days and daily rate",
            "parameters": {
                "type": "object",
                "properties": {
                    "agreed_days": {
                        "type": "number",
                        "description": "Number of days agreed in contract"
                    },
                    "actual_days": {
                        "type": "number",
                        "description": "Actual number of days spent"
                    },
                    "daily_rate": {
                        "type": "number",
                        "description": "Daily demurrage rate in USD"
                    }
                },
                "required": ["agreed_days", "actual_days", "daily_rate"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_contacts",
            "description": "Search for freight industry contacts (owners, operators, agents, brokers). This is a PAID service - $10 USDT per contact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Company or person name to search"
                    },
                    "type": {
                        "type": "string",
                        "description": "Contact type: owner, operator, agent, broker, shipper",
                        "enum": ["owner", "operator", "agent", "broker", "shipper"]
                    }
                },
                "required": []
            }
        }
    }
]


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool and return result as string"""

    if tool_name == "search_vessel":
        query = tool_input.get("query", "")
        # First check local DB
        results = db.search_vessels(query, limit=10)

        if not results:
            # Try Equasis (free, has owner data)
            try:
                equasis = eq.get_parser()
                results = equasis.search_vessel(query)
                # Cache results
                for v in results:
                    if v.get('imo'):
                        db.upsert_vessel(v)
            except Exception as e:
                print(f"Equasis error: {e}")

        if not results:
            # Fallback to MarineTraffic
            parser = mt.get_parser()
            results = parser.search_vessel_public(query)
            for v in results:
                if v.get('mmsi'):
                    db.upsert_vessel(v)

        if results:
            return json.dumps({
                "found": len(results),
                "vessels": results[:5]  # Top 5
            }, ensure_ascii=False)
        return json.dumps({"found": 0, "message": "No vessels found"})

    elif tool_name == "get_vessel":
        identifier = tool_input.get("mmsi", "") or tool_input.get("imo", "")
        vessel = db.get_vessel(mmsi=identifier) or db.get_vessel(imo=identifier)

        if not vessel:
            # Try Equasis first (has owner/operator data)
            try:
                equasis = eq.get_parser()
                if len(identifier) == 7:  # IMO
                    vessel = equasis.get_vessel_details(identifier)
                else:  # Search by MMSI/name
                    results = equasis.search_vessel(identifier)
                    if results and results[0].get('imo'):
                        vessel = equasis.get_vessel_details(results[0]['imo'])
                if vessel:
                    db.upsert_vessel(vessel)
            except Exception as e:
                print(f"Equasis error: {e}")

        if not vessel:
            # Fallback to MarineTraffic
            parser = mt.get_parser()
            vessel = parser.get_vessel_page(identifier)
            if vessel:
                db.upsert_vessel(vessel)

        if vessel:
            return json.dumps(vessel, ensure_ascii=False)
        return json.dumps({"error": "Vessel not found"})

    elif tool_name == "get_position":
        mmsi = tool_input.get("mmsi", "")
        position = db.get_last_position(mmsi)

        if not position:
            # Try to get from vessel page
            parser = mt.get_parser()
            vessel = parser.get_vessel_page(mmsi)
            if vessel.get('latitude') and vessel.get('longitude'):
                db.add_position(
                    mmsi=mmsi,
                    lat=vessel['latitude'],
                    lon=vessel['longitude']
                )
                position = {
                    'mmsi': mmsi,
                    'latitude': vessel['latitude'],
                    'longitude': vessel['longitude']
                }

        if position:
            return json.dumps(position, ensure_ascii=False)
        return json.dumps({"error": "Position not available"})

    elif tool_name == "calculate_demurrage":
        agreed = tool_input.get("agreed_days", 0)
        actual = tool_input.get("actual_days", 0)
        rate = tool_input.get("daily_rate", 0)

        delay = max(0, actual - agreed)
        total = delay * rate

        return json.dumps({
            "agreed_days": agreed,
            "actual_days": actual,
            "delay_days": delay,
            "daily_rate": rate,
            "total_demurrage_usd": total,
            "formula": f"({actual} - {agreed}) × ${rate} = ${total}"
        })

    elif tool_name == "search_contacts":
        query = tool_input.get("query")
        contact_type = tool_input.get("type")

        # First check local DB
        contacts = db.search_contacts(query=query, contact_type=contact_type, limit=10)

        # If no local contacts, try Equasis
        if not contacts and query:
            try:
                equasis = eq.get_parser()
                company = equasis.get_company_contacts(query)
                if company and company.get('name'):
                    contacts = [{
                        'company_name': company.get('name'),
                        'type': contact_type or 'company',
                        'country': company.get('country'),
                        'address': company.get('address'),
                        'phone': company.get('phone'),
                        'email': company.get('email'),
                        'source': 'equasis'
                    }]
                    # Save to DB
                    db.add_contact(
                        contact_type=contact_type or 'company',
                        company_name=company.get('name'),
                        country=company.get('country'),
                        address=company.get('address'),
                        phone=company.get('phone'),
                        email=company.get('email'),
                        source='equasis'
                    )
            except Exception as e:
                print(f"Equasis company error: {e}")

        # Mask sensitive data (contacts are paid)
        for c in contacts:
            if c.get('email'):
                c['email'] = c['email'][:3] + '***@***'
            if c.get('phone'):
                c['phone'] = c['phone'][:4] + '****'
            c['full_access_price'] = '$10 USDT'

        return json.dumps({
            "found": len(contacts),
            "note": "Full contact details require payment of $10 USDT per contact",
            "contacts": contacts
        }, ensure_ascii=False)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


client = OpenAI(api_key=OPENAI_API_KEY)


def get_moltbook_headers():
    return {
        "Authorization": f"Bearer {MOLTBOOK_API_KEY}",
        "Content-Type": "application/json"
    }


def check_messages():
    """Check for new DMs"""
    resp = requests.get(f"{MOLTBOOK_BASE}/agents/dm/check", headers=get_moltbook_headers())
    if resp.status_code == 200:
        return resp.json()
    return {"conversations": []}


def send_reply(conversation_id: str, message: str):
    """Reply to a conversation"""
    resp = requests.post(
        f"{MOLTBOOK_BASE}/agents/dm/conversations/{conversation_id}/send",
        headers=get_moltbook_headers(),
        json={"message": message}
    )
    return resp.json()


def generate_response(user_message: str, conversation_history: list = None) -> str:
    """Generate response using OpenAI with tools"""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if conversation_history:
        for msg in conversation_history[-10:]:
            role = "user" if msg.get("from_user") else "assistant"
            messages.append({"role": role, "content": msg.get("content", "")})

    messages.append({"role": "user", "content": user_message})

    # First call with tools
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=2048,
        tools=TOOLS,
        messages=messages
    )

    # Handle tool use loop
    while response.choices[0].finish_reason == "tool_calls":
        assistant_message = response.choices[0].message
        messages.append(assistant_message)

        # Execute each tool call
        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            tool_result = execute_tool(tool_name, tool_args)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result
            })

        # Continue conversation with tool results
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=2048,
            tools=TOOLS,
            messages=messages
        )

    # Extract final text response
    return response.choices[0].message.content or "I couldn't generate a response."

    return "I apologize, I couldn't generate a response. Please try again."


def process_conversations():
    """Main loop: check messages and respond"""
    data = check_messages()

    conversations = data.get("conversations", [])
    processed = 0

    for conv in conversations:
        conv_id = conv.get("id")
        messages = conv.get("messages", [])

        # Find unread messages from users
        unread = [m for m in messages if m.get("from_user") and not m.get("read")]

        if not unread:
            continue

        # Get last user message
        last_msg = unread[-1]
        user_text = last_msg.get("content", "")

        if not user_text:
            continue

        # Generate and send response
        try:
            response = generate_response(user_text, messages)
            result = send_reply(conv_id, response)

            if result.get("success"):
                processed += 1
                print(f"Replied to conversation {conv_id}")
            else:
                print(f"Failed to reply: {result}")
        except Exception as e:
            print(f"Error processing conversation {conv_id}: {e}")

    return processed


def heartbeat():
    """Periodic heartbeat - call every 4 hours via cron"""
    print("=" * 50)
    print("SeaFare_Montana heartbeat...")
    print(f"Time: {__import__('datetime').datetime.utcnow().isoformat()}")

    # Initialize DB if needed
    db.init_db()

    # Check and respond to messages
    count = process_conversations()
    print(f"Processed {count} conversations")

    # Check agent status
    try:
        resp = requests.get(f"{MOLTBOOK_BASE}/agents/me", headers=get_moltbook_headers())
        if resp.status_code == 200:
            status = resp.json()
            print(f"Agent status: {status.get('status', 'unknown')}")
    except Exception as e:
        print(f"Status check error: {e}")

    # Print DB stats
    stats = db.get_stats()
    print(f"DB stats: {stats}")

    print("=" * 50)
    return count


if __name__ == "__main__":
    heartbeat()
