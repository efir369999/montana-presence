# P2P Messages API Endpoints
# Add these routes to junona_api.py on server 72.56.102.240

"""
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    from_phone TEXT NOT NULL,
    to_phone TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    is_read INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_messages_phones ON messages(from_phone, to_phone);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
"""

from flask import jsonify, request
import sqlite3
import uuid
from datetime import datetime

# Add to existing Flask app

@app.route('/api/messages', methods=['POST'])
def send_message():
    """Send P2P message to contact"""
    device_id = request.headers.get('X-Device-ID')
    if not device_id:
        return jsonify({"error": "No device ID"}), 401

    data = request.get_json() or {}
    to_phone = data.get('to_phone')
    content = data.get('content')

    if not to_phone or not content:
        return jsonify({"error": "Missing to_phone or content"}), 400

    # Get sender's phone from device_id
    conn = sqlite3.connect('/opt/junona/montana.db')
    cursor = conn.cursor()
    cursor.execute("SELECT phone FROM users WHERE device_id = ?", (device_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    from_phone = row[0]

    # Create message
    message_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat() + 'Z'

    # Create messages table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            from_phone TEXT NOT NULL,
            to_phone TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            is_read INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        INSERT INTO messages (id, from_phone, to_phone, content, timestamp, is_read)
        VALUES (?, ?, ?, ?, ?, 0)
    ''', (message_id, from_phone, to_phone, content, timestamp))

    conn.commit()
    conn.close()

    return jsonify({
        "id": message_id,
        "from_phone": from_phone,
        "to_phone": to_phone,
        "content": content,
        "timestamp": timestamp,
        "is_read": False
    })


@app.route('/api/messages', methods=['GET'])
def get_messages():
    """Get messages with specific contact"""
    device_id = request.headers.get('X-Device-ID')
    if not device_id:
        return jsonify({"error": "No device ID"}), 401

    with_phone = request.args.get('with')
    if not with_phone:
        return jsonify({"error": "Missing 'with' parameter"}), 400

    conn = sqlite3.connect('/opt/junona/montana.db')
    cursor = conn.cursor()

    # Get user's phone
    cursor.execute("SELECT phone FROM users WHERE device_id = ?", (device_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    my_phone = row[0]

    # Get messages between user and contact
    cursor.execute('''
        SELECT id, from_phone, to_phone, content, timestamp, is_read
        FROM messages
        WHERE (from_phone = ? AND to_phone = ?)
           OR (from_phone = ? AND to_phone = ?)
        ORDER BY timestamp ASC
        LIMIT 100
    ''', (my_phone, with_phone, with_phone, my_phone))

    messages = []
    for row in cursor.fetchall():
        messages.append({
            "id": row[0],
            "from_phone": row[1],
            "to_phone": row[2],
            "content": row[3],
            "timestamp": row[4],
            "is_read": bool(row[5])
        })

    # Mark received messages as read
    cursor.execute('''
        UPDATE messages SET is_read = 1
        WHERE from_phone = ? AND to_phone = ? AND is_read = 0
    ''', (with_phone, my_phone))

    conn.commit()
    conn.close()

    return jsonify({"messages": messages})


@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Get list of conversations with last message"""
    device_id = request.headers.get('X-Device-ID')
    if not device_id:
        return jsonify({"error": "No device ID"}), 401

    conn = sqlite3.connect('/opt/junona/montana.db')
    cursor = conn.cursor()

    # Get user's phone
    cursor.execute("SELECT phone FROM users WHERE device_id = ?", (device_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    my_phone = row[0]

    # Get all unique contacts with messages
    cursor.execute('''
        SELECT DISTINCT
            CASE WHEN from_phone = ? THEN to_phone ELSE from_phone END as contact_phone
        FROM messages
        WHERE from_phone = ? OR to_phone = ?
    ''', (my_phone, my_phone, my_phone))

    contact_phones = [row[0] for row in cursor.fetchall()]

    conversations = []
    for contact_phone in contact_phones:
        # Get last message
        cursor.execute('''
            SELECT content, timestamp FROM messages
            WHERE (from_phone = ? AND to_phone = ?)
               OR (from_phone = ? AND to_phone = ?)
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (my_phone, contact_phone, contact_phone, my_phone))

        last_msg = cursor.fetchone()
        if not last_msg:
            continue

        # Get unread count
        cursor.execute('''
            SELECT COUNT(*) FROM messages
            WHERE from_phone = ? AND to_phone = ? AND is_read = 0
        ''', (contact_phone, my_phone))
        unread_count = cursor.fetchone()[0]

        # Get contact name from contacts table
        cursor.execute('''
            SELECT name FROM contacts
            WHERE phone = ? AND telegram_id = (
                SELECT telegram_id FROM users WHERE phone = ?
            )
        ''', (contact_phone, my_phone))
        name_row = cursor.fetchone()
        contact_name = name_row[0] if name_row else contact_phone

        conversations.append({
            "contact_phone": contact_phone,
            "contact_name": contact_name,
            "last_message": last_msg[0],
            "last_message_time": last_msg[1],
            "unread_count": unread_count
        })

    conn.close()

    return jsonify({"conversations": conversations})
