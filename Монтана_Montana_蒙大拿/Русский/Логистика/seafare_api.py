#!/usr/bin/env python3
"""
SeaFare API — Maritime Data Service
Serves data from local DB, falls back to MarineTraffic

Ɉ MONTANA PROTOCOL — ML-DSA-65 (FIPS 204)
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from flask import Flask, request, jsonify
from flask_cors import CORS

import maritime_db as db
import marinetraffic_parser as mt

app = Flask(__name__)
CORS(app)

# Cache duration for live data
POSITION_CACHE_MINUTES = 5
VESSEL_CACHE_HOURS = 24


# =============================================================================
# VESSEL ENDPOINTS
# =============================================================================

@app.route('/api/v1/vessel/<identifier>', methods=['GET'])
def get_vessel(identifier: str):
    """
    Get vessel by MMSI, IMO, or name
    First checks local DB, then fetches from MarineTraffic
    """
    # Determine identifier type
    if identifier.isdigit() and len(identifier) == 9:
        vessel = db.get_vessel(mmsi=identifier)
        search_param = {'mmsi': identifier}
    elif identifier.isdigit() and len(identifier) == 7:
        vessel = db.get_vessel(imo=identifier)
        search_param = {'imo': identifier}
    else:
        vessel = db.get_vessel(name=identifier)
        search_param = {'name': identifier}

    # Check if we need to refresh
    if vessel:
        updated = datetime.fromisoformat(vessel.get('updated_at', '2000-01-01'))
        if datetime.utcnow() - updated < timedelta(hours=VESSEL_CACHE_HOURS):
            return jsonify({
                'success': True,
                'source': 'cache',
                'vessel': vessel
            })

    # Fetch from MarineTraffic
    parser = mt.get_parser()
    mmsi = search_param.get('mmsi') or (vessel.get('mmsi') if vessel else None)

    if mmsi:
        fresh_data = parser.get_vessel_page(mmsi)
        if fresh_data:
            db.upsert_vessel(fresh_data)
            return jsonify({
                'success': True,
                'source': 'marinetraffic',
                'vessel': fresh_data
            })

    if vessel:
        return jsonify({
            'success': True,
            'source': 'cache_stale',
            'vessel': vessel
        })

    return jsonify({
        'success': False,
        'error': 'Vessel not found'
    }), 404


@app.route('/api/v1/vessel/search', methods=['GET'])
def search_vessels():
    """
    Search vessels by query
    """
    query = request.args.get('q', '')
    if not query or len(query) < 2:
        return jsonify({
            'success': False,
            'error': 'Query too short (min 2 chars)'
        }), 400

    # Search local DB first
    results = db.search_vessels(query, limit=20)

    # If few results, search MarineTraffic
    if len(results) < 5:
        mt_results = mt.search_vessel(query)
        for v in mt_results:
            if v.get('mmsi') and not any(r.get('mmsi') == v.get('mmsi') for r in results):
                results.append(v)
                # Cache to DB
                db.upsert_vessel(v)

    return jsonify({
        'success': True,
        'count': len(results),
        'vessels': results[:20]
    })


# =============================================================================
# POSITION ENDPOINTS
# =============================================================================

@app.route('/api/v1/position/<mmsi>', methods=['GET'])
def get_position(mmsi: str):
    """
    Get current vessel position
    """
    # Check cache
    cached = db.get_last_position(mmsi)
    if cached:
        received = datetime.fromisoformat(cached.get('received_at', '2000-01-01'))
        if datetime.utcnow() - received < timedelta(minutes=POSITION_CACHE_MINUTES):
            return jsonify({
                'success': True,
                'source': 'cache',
                'position': cached
            })

    # Fetch fresh from MarineTraffic
    parser = mt.get_parser()
    vessel_data = parser.get_vessel_page(mmsi)

    if vessel_data.get('latitude') and vessel_data.get('longitude'):
        db.add_position(
            mmsi=mmsi,
            lat=vessel_data['latitude'],
            lon=vessel_data['longitude'],
            speed=vessel_data.get('speed'),
            course=vessel_data.get('course'),
            heading=vessel_data.get('heading'),
            destination=vessel_data.get('destination'),
            eta=vessel_data.get('eta')
        )

        return jsonify({
            'success': True,
            'source': 'marinetraffic',
            'position': {
                'mmsi': mmsi,
                'latitude': vessel_data['latitude'],
                'longitude': vessel_data['longitude'],
                'speed': vessel_data.get('speed'),
                'course': vessel_data.get('course'),
                'timestamp': datetime.utcnow().isoformat()
            }
        })

    if cached:
        return jsonify({
            'success': True,
            'source': 'cache_stale',
            'position': cached
        })

    return jsonify({
        'success': False,
        'error': 'Position not available'
    }), 404


@app.route('/api/v1/position/<mmsi>/history', methods=['GET'])
def get_position_history(mmsi: str):
    """
    Get vessel position history
    """
    hours = request.args.get('hours', 24, type=int)
    history = db.get_position_history(mmsi, hours=hours)

    return jsonify({
        'success': True,
        'mmsi': mmsi,
        'hours': hours,
        'count': len(history),
        'positions': history
    })


# =============================================================================
# CONTACT ENDPOINTS (paid service - $10 USDT)
# =============================================================================

@app.route('/api/v1/contacts/vessel/<mmsi>', methods=['GET'])
def get_vessel_contacts(mmsi: str):
    """
    Get contacts for vessel (owner, operator, agent)
    This is a PAID service
    """
    # Check authorization (payment verification would go here)
    auth_token = request.headers.get('Authorization', '')
    if not auth_token.startswith('Bearer paid_'):
        return jsonify({
            'success': False,
            'error': 'Payment required',
            'price': '$10 USDT',
            'instructions': 'Contact SeaFare_Montana for payment'
        }), 402

    contacts = db.get_contacts_for_vessel(mmsi)

    return jsonify({
        'success': True,
        'mmsi': mmsi,
        'count': len(contacts),
        'contacts': contacts
    })


@app.route('/api/v1/contacts/search', methods=['GET'])
def search_contacts():
    """
    Search contacts (owners, operators, agents, brokers)
    """
    query = request.args.get('q', '')
    contact_type = request.args.get('type', '')

    # Check authorization for full data
    auth_token = request.headers.get('Authorization', '')
    is_paid = auth_token.startswith('Bearer paid_')

    contacts = db.search_contacts(
        query=query if query else None,
        contact_type=contact_type if contact_type else None,
        limit=20
    )

    # Mask sensitive data for unpaid users
    if not is_paid:
        for c in contacts:
            if c.get('email'):
                c['email'] = c['email'][:3] + '***@***'
            if c.get('phone'):
                c['phone'] = c['phone'][:4] + '****'
            c['full_access'] = False
            c['price'] = '$10 USDT per contact'

    return jsonify({
        'success': True,
        'paid_access': is_paid,
        'count': len(contacts),
        'contacts': contacts
    })


# =============================================================================
# DEMURRAGE CALCULATOR
# =============================================================================

@app.route('/api/v1/demurrage/calculate', methods=['POST'])
def calculate_demurrage():
    """
    Calculate demurrage
    Formula: (actual_days - agreed_days) × daily_rate
    """
    data = request.get_json()

    agreed_days = data.get('agreed_days', 0)
    actual_days = data.get('actual_days', 0)
    daily_rate = data.get('daily_rate', 0)
    currency = data.get('currency', 'USD')

    delay_days = max(0, actual_days - agreed_days)
    total = delay_days * daily_rate

    return jsonify({
        'success': True,
        'calculation': {
            'agreed_days': agreed_days,
            'actual_days': actual_days,
            'delay_days': delay_days,
            'daily_rate': daily_rate,
            'currency': currency,
            'total_demurrage': total,
            'formula': f"({actual_days} - {agreed_days}) × {daily_rate} = {total} {currency}"
        }
    })


# =============================================================================
# STATS & HEALTH
# =============================================================================

@app.route('/api/v1/stats', methods=['GET'])
def get_stats():
    """Get database statistics"""
    stats = db.get_stats()
    stats['api_version'] = '1.0'
    stats['marinetraffic_api'] = mt.get_parser().has_api_key()

    return jsonify({
        'success': True,
        'stats': stats
    })


@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'service': 'SeaFare API',
        'timestamp': datetime.utcnow().isoformat()
    })


# =============================================================================
# MAIN
# =============================================================================

def init():
    """Initialize database"""
    db.init_db()


if __name__ == '__main__':
    init()
    port = int(os.environ.get('SEAFARE_PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=True)
