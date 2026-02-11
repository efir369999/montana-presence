#!/usr/bin/env python3
"""
Maritime Database — Schema and Operations
SeaFare_Montana Data Layer

Ɉ MONTANA PROTOCOL — ML-DSA-65 (FIPS 204)
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "maritime.db"


def get_connection():
    """Get database connection"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database schema"""
    conn = get_connection()
    cursor = conn.cursor()

    # Vessels table — основные данные судна
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vessels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mmsi TEXT UNIQUE NOT NULL,
            imo TEXT,
            name TEXT,
            type TEXT,
            type_code INTEGER,
            flag TEXT,
            flag_code TEXT,
            callsign TEXT,
            length REAL,
            width REAL,
            draught REAL,
            gross_tonnage INTEGER,
            deadweight INTEGER,
            year_built INTEGER,

            -- Owner/Operator info
            owner TEXT,
            owner_country TEXT,
            operator TEXT,
            operator_country TEXT,

            -- Technical
            engine_type TEXT,
            speed_max REAL,

            -- Metadata
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source TEXT DEFAULT 'marinetraffic'
        )
    """)

    # Positions table — позиции (история)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mmsi TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            speed REAL,
            course REAL,
            heading REAL,
            status TEXT,
            destination TEXT,
            eta TEXT,
            timestamp TIMESTAMP NOT NULL,
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (mmsi) REFERENCES vessels(mmsi)
        )
    """)

    # Contacts table — контакты участников фрахта
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,  -- owner, operator, agent, broker, shipper
            company_name TEXT NOT NULL,
            country TEXT,
            city TEXT,
            address TEXT,
            phone TEXT,
            email TEXT,
            website TEXT,
            contact_person TEXT,
            notes TEXT,

            -- Links
            vessels_mmsi TEXT,  -- JSON array of MMSI numbers

            -- Source tracking
            source TEXT,  -- marinetraffic, dato_network, manual
            verified BOOLEAN DEFAULT 0,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Port calls — заходы в порты
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS port_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mmsi TEXT NOT NULL,
            port_name TEXT NOT NULL,
            port_code TEXT,
            country TEXT,
            arrival TIMESTAMP,
            departure TIMESTAMP,
            berth TEXT,
            cargo_type TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (mmsi) REFERENCES vessels(mmsi)
        )
    """)

    # Demurrage records — записи о демердже
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS demurrage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mmsi TEXT NOT NULL,
            port_name TEXT NOT NULL,

            -- Time
            agreed_days REAL NOT NULL,
            actual_days REAL NOT NULL,
            delay_days REAL GENERATED ALWAYS AS (actual_days - agreed_days) STORED,

            -- Money
            daily_rate REAL,
            currency TEXT DEFAULT 'USD',
            total_amount REAL GENERATED ALWAYS AS (
                CASE WHEN actual_days > agreed_days
                THEN (actual_days - agreed_days) * daily_rate
                ELSE 0 END
            ) STORED,

            -- Status
            status TEXT DEFAULT 'pending',  -- pending, paid, disputed
            notes TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (mmsi) REFERENCES vessels(mmsi)
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vessels_mmsi ON vessels(mmsi)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vessels_imo ON vessels(imo)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vessels_name ON vessels(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_mmsi ON positions(mmsi)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_timestamp ON positions(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_type ON contacts(type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_port_calls_mmsi ON port_calls(mmsi)")

    conn.commit()
    conn.close()

    print(f"Database initialized: {DB_PATH}")
    return True


# =============================================================================
# VESSEL OPERATIONS
# =============================================================================

def upsert_vessel(data: dict) -> int:
    """Insert or update vessel"""
    conn = get_connection()
    cursor = conn.cursor()

    data['updated_at'] = datetime.utcnow().isoformat()

    columns = ', '.join(data.keys())
    placeholders = ', '.join(['?' for _ in data])
    updates = ', '.join([f"{k}=excluded.{k}" for k in data.keys() if k != 'mmsi'])

    cursor.execute(f"""
        INSERT INTO vessels ({columns}) VALUES ({placeholders})
        ON CONFLICT(mmsi) DO UPDATE SET {updates}
    """, list(data.values()))

    conn.commit()
    vessel_id = cursor.lastrowid
    conn.close()

    return vessel_id


def get_vessel(mmsi: str = None, imo: str = None, name: str = None) -> dict:
    """Get vessel by MMSI, IMO, or name"""
    conn = get_connection()
    cursor = conn.cursor()

    if mmsi:
        cursor.execute("SELECT * FROM vessels WHERE mmsi = ?", (mmsi,))
    elif imo:
        cursor.execute("SELECT * FROM vessels WHERE imo = ?", (imo,))
    elif name:
        cursor.execute("SELECT * FROM vessels WHERE name LIKE ?", (f"%{name}%",))
    else:
        return None

    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def search_vessels(query: str, limit: int = 20) -> list:
    """Search vessels by name, MMSI, or IMO"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM vessels
        WHERE name LIKE ? OR mmsi LIKE ? OR imo LIKE ?
        ORDER BY updated_at DESC
        LIMIT ?
    """, (f"%{query}%", f"%{query}%", f"%{query}%", limit))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


# =============================================================================
# POSITION OPERATIONS
# =============================================================================

def add_position(mmsi: str, lat: float, lon: float, speed: float = None,
                 course: float = None, heading: float = None, status: str = None,
                 destination: str = None, eta: str = None, timestamp: str = None):
    """Add vessel position"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO positions (mmsi, latitude, longitude, speed, course,
                              heading, status, destination, eta, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (mmsi, lat, lon, speed, course, heading, status, destination, eta,
          timestamp or datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()


def get_last_position(mmsi: str) -> dict:
    """Get last known position for vessel"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM positions
        WHERE mmsi = ?
        ORDER BY timestamp DESC
        LIMIT 1
    """, (mmsi,))

    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_position_history(mmsi: str, hours: int = 24) -> list:
    """Get position history for vessel"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM positions
        WHERE mmsi = ? AND timestamp > datetime('now', ?)
        ORDER BY timestamp DESC
    """, (mmsi, f"-{hours} hours"))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


# =============================================================================
# CONTACT OPERATIONS
# =============================================================================

def add_contact(contact_type: str, company_name: str, **kwargs) -> int:
    """Add contact"""
    conn = get_connection()
    cursor = conn.cursor()

    data = {
        'type': contact_type,
        'company_name': company_name,
        **kwargs
    }

    columns = ', '.join(data.keys())
    placeholders = ', '.join(['?' for _ in data])

    cursor.execute(f"INSERT INTO contacts ({columns}) VALUES ({placeholders})",
                   list(data.values()))

    conn.commit()
    contact_id = cursor.lastrowid
    conn.close()

    return contact_id


def search_contacts(query: str = None, contact_type: str = None, limit: int = 20) -> list:
    """Search contacts"""
    conn = get_connection()
    cursor = conn.cursor()

    if query and contact_type:
        cursor.execute("""
            SELECT * FROM contacts
            WHERE type = ? AND (company_name LIKE ? OR contact_person LIKE ?)
            ORDER BY updated_at DESC LIMIT ?
        """, (contact_type, f"%{query}%", f"%{query}%", limit))
    elif contact_type:
        cursor.execute("""
            SELECT * FROM contacts WHERE type = ?
            ORDER BY updated_at DESC LIMIT ?
        """, (contact_type, limit))
    elif query:
        cursor.execute("""
            SELECT * FROM contacts
            WHERE company_name LIKE ? OR contact_person LIKE ?
            ORDER BY updated_at DESC LIMIT ?
        """, (f"%{query}%", f"%{query}%", limit))
    else:
        cursor.execute("SELECT * FROM contacts ORDER BY updated_at DESC LIMIT ?", (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_contacts_for_vessel(mmsi: str) -> list:
    """Get all contacts associated with a vessel"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM contacts
        WHERE vessels_mmsi LIKE ?
    """, (f'%"{mmsi}"%',))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


# =============================================================================
# STATS
# =============================================================================

def get_stats() -> dict:
    """Get database statistics"""
    conn = get_connection()
    cursor = conn.cursor()

    stats = {}

    cursor.execute("SELECT COUNT(*) FROM vessels")
    stats['vessels'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM positions")
    stats['positions'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM contacts")
    stats['contacts'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM port_calls")
    stats['port_calls'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM demurrage")
    stats['demurrage_records'] = cursor.fetchone()[0]

    conn.close()

    return stats


if __name__ == "__main__":
    init_db()
    print("Stats:", get_stats())
